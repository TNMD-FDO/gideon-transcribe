"""The pages a person uses: their recordings, uploading, and a Batch running.

The Upload page and the Batch page are one page. Before a Batch it takes
files; after Submit it shows that Batch until every Recording in it has ended,
and then it takes files again. There is no list of past Batches.
"""

from __future__ import annotations

import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core import audit, settings_store, uploads, whisperx
from core.jobs import JobState
from core.recordings import Batch, MediaState, Recording, Refusal

log = logging.getLogger("transcribe.pages")

# What the standing line says, with the hours from the idle timeout.
STANDING_LINE = (
    "Your recordings and transcripts are removed when you sign out or after "
    "{hours} hours without activity. Download or export anything you want to keep."
)


def standing_line() -> str:
    hours = settings_store.get("idle_timeout_minutes") / 60
    return STANDING_LINE.format(hours=f"{hours:g}")


@login_required
def recordings(request: HttpRequest) -> HttpResponse:
    """Where a person lands: everything they have uploaded this session."""
    return render(
        request,
        "recordings.html",
        {
            "recordings": request.user.recordings.order_by("-created"),
            "standing_line": standing_line(),
            "storage_warning": uploads.storage_warning(request.user),
        },
    )


@login_required
def upload(request: HttpRequest) -> HttpResponse:
    """Choose files, choose settings, and start; or watch the Batch running."""
    batch = Batch.unfinished_for(request.user)
    if batch is not None:
        return redirect(reverse("batch", args=[batch.pk]))

    return render(
        request,
        "upload.html",
        {
            "standing_line": standing_line(),
            "storage_warning": uploads.storage_warning(request.user),
            "service_is_up": whisperx.is_alive(),
            "limits": {
                "largest_file": uploads.as_gb(settings_store.largest_file_bytes()),
                "longest_hours": settings_store.longest_recording_seconds() // 3600,
                "files_per_batch": settings_store.files_per_batch(),
            },
            "disk_is_low": (
                uploads.free_disk_bytes() < settings_store.minimum_free_disk_bytes()
            ),
        },
    )


@login_required
@require_POST
def submit(request: HttpRequest) -> JsonResponse:
    """Make the Batch and its Recordings. The browser then uploads the bytes.

    Nothing is sent before this, and there is no draft Batch: the Batch exists
    from the moment somebody presses the button and not before.
    """
    if Batch.unfinished_for(request.user) is not None:
        return JsonResponse(
            {
                "error": Refusal.MESSAGES[Refusal.BATCH_IN_PROGRESS],
                "reason_class": Refusal.BATCH_IN_PROGRESS,
            },
            status=409,
        )

    # Asked when the page opens and again here, because the answer can change
    # in between and a Batch nobody can transcribe is worse than a refusal.
    if not whisperx.is_alive():
        return JsonResponse(
            {
                "error": Refusal.MESSAGES[Refusal.SERVICE_UNREACHABLE],
                "reason_class": Refusal.SERVICE_UNREACHABLE,
            },
            status=503,
        )

    try:
        wanted = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "The request could not be read."}, status=400)

    files = wanted.get("files") or []
    if not files:
        return JsonResponse({"error": "Choose at least one file."}, status=400)

    per_batch = settings_store.files_per_batch()
    if len(files) > per_batch:
        return JsonResponse(
            {
                "error": Refusal.MESSAGES[Refusal.LIMIT_EXCEEDED].format(
                    limit=per_batch, over=len(files) - per_batch
                ),
                "reason_class": Refusal.LIMIT_EXCEEDED,
            },
            status=400,
        )

    batch = Batch.objects.create(user=request.user)
    made = []
    for one in files:
        settings_for_file = _settings_from(one, wanted.get("batch") or {})
        recording = Recording.objects.create(
            batch=batch,
            user=request.user,
            title=(
                (one.get("title") or "").strip()[:300] or one.get("name", "recording")
            ),
            original_filename=one.get("name", "recording")[:400],
            size_bytes=int(one.get("size") or 0),
            media_state=MediaState.UPLOADING,
            **settings_for_file,
        )
        made.append({"id": str(recording.pk), "name": one.get("name", "")})

    audit.write(
        audit.Category.JOBS,
        "Batch submitted",
        actor=request.user,
        request=request,
        object_type="batch",
        object_id=batch.pk,
        object_label=f"{len(made)} recordings",
        recordings=[
            {
                "diarize": recording.diarize,
                "speakers": recording.speakers_exactly or recording.speakers_between,
                "translate": recording.translate,
                "language": recording.spoken_language,
                "vocabulary_given": bool(recording.vocabulary),
                "preprocessing": recording.preprocessing,
                "model": recording.model,
            }
            for recording in batch.recordings.all()
        ],
    )

    return JsonResponse({"batch": str(batch.pk), "recordings": made})


def _settings_from(one: dict, batch_settings: dict) -> dict:
    """What this file was asked for: its own settings, or the Batch's."""
    chosen = one.get("settings") or batch_settings
    hint = chosen.get("speakers") or {}

    return {
        "diarize": bool(chosen.get("diarize")),
        "speakers_exactly": hint.get("exactly"),
        "speakers_between": hint.get("between"),
        "translate": bool(chosen.get("translate")),
        "spoken_language": (chosen.get("language") or "")[:10],
        "vocabulary": [
            term.strip()
            for term in (chosen.get("vocabulary") or [])
            if str(term).strip()
        ][:200],
        "context": (chosen.get("context") or "").strip()[:500],
        "model": "",
        "preprocessing": "standard",
    }


@login_required
def batch(request: HttpRequest, batch_id) -> HttpResponse:
    """The Batch, while it runs and until every Recording in it has ended."""
    found = Batch.objects.filter(pk=batch_id, user=request.user).first()
    if found is None:
        return redirect(reverse("upload"))

    return render(
        request,
        "batch.html",
        {
            "batch": found,
            "standing_line": standing_line(),
        },
    )


@login_required
def batch_state(request: HttpRequest, batch_id) -> JsonResponse:
    """What the Batch page asks for every few seconds.

    One request for the whole Batch rather than one per Recording, because a
    Batch of twenty-five would otherwise be twenty-five requests every five
    seconds.
    """
    found = Batch.objects.filter(pk=batch_id, user=request.user).first()
    if found is None:
        return JsonResponse({"error": "no such batch"}, status=404)

    rows = []
    for recording in found.recordings.order_by("created"):
        job = recording.jobs.order_by("-created").first()
        rows.append(
            {
                "id": str(recording.pk),
                "title": recording.title,
                "state": recording.media_state,
                "playback_ready": recording.playback_ready,
                "minutes": round((recording.duration_seconds or 0) / 60, 1),
                "sides": recording.sides.count(),
                "two_channel_call": recording.is_two_channel_call,
                "message": recording.failure_message,
                "reason": recording.refusal_class,
                "job": _job_state(job),
                "has_transcript": hasattr(recording, "transcript"),
            }
        )

    return JsonResponse(
        {
            "finished": found.is_finished,
            "started": found.created.isoformat(),
            "recordings": rows,
        }
    )


def _job_state(job) -> dict | None:
    if job is None:
        return None
    run = job.runs.order_by("side__number").first()
    return {
        "state": job.state,
        "step": job.step,
        "position": run.position if run else None,
        "audio_minutes_ahead": run.audio_minutes_ahead if run else None,
        "message": job.failure_message,
        "reason": job.failure_class,
    }


@login_required
@require_POST
def cancel_batch(request: HttpRequest, batch_id) -> JsonResponse:
    """Stop everything in a Batch, and remove what it made.

    Cancelling removes the recording, which is what the confirmation says, so
    that a person is never left with half of something they meant to be rid
    of.
    """
    found = Batch.objects.filter(pk=batch_id, user=request.user).first()
    if found is None:
        return JsonResponse({"error": "no such batch"}, status=404)

    for recording in found.recordings.all():
        for job in recording.jobs.filter(state__in=JobState.LIVE):
            for run in job.runs.exclude(service_job_id=""):
                whisperx.delete(run.service_job_id)
            job.state = JobState.CANCELLED
            job.finished = timezone.now()
            job.save()
            audit.write(
                audit.Category.JOBS,
                "Job cancelled",
                actor=request.user,
                request=request,
                object_type="recording",
                object_id=recording.pk,
                object_label=recording.original_filename,
            )
        _remove(request, recording, cause="cancel")

    return JsonResponse({"cancelled": True})


def _remove(request, recording: Recording, cause: str) -> None:
    """Take a Recording and everything it made off the disk and the database."""
    import shutil

    audit.write(
        audit.Category.RECORDINGS,
        "Recording deleted",
        actor=request.user if cause != "discard" else None,
        system="sweeper" if cause == "discard" else None,
        request=request if cause != "discard" else None,
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
        cause=cause,
    )
    folder = recording.folder
    recording.delete()
    shutil.rmtree(folder, ignore_errors=True)
