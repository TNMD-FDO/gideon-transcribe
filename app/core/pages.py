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

from core import audit, lifecycle, settings_store, tasks, uploads, whisperx
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
            "page": "recordings",
            "recordings": _with_their_state(
                request.user.recordings.order_by("-created")
            ),
            "standing_line": standing_line(),
            "storage_warning": uploads.storage_warning(request.user),
        },
    )


def _with_their_state(recordings):
    """Each Recording with the one word its row shows.

    A Recording being transcribed again says so, rather than looking done
    while its transcript is about to be replaced.
    """
    rows = []
    for one in recordings:
        job = one.jobs.order_by("-created").first()
        one.being_replaced = bool(
            job is not None and job.is_live and job.batch.is_reprocessing
        )
        one.in_the_queue = bool(job is not None and job.is_live)
        rows.append(one)
    return rows


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
            "page": "upload",
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
            "page": "upload",
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

    arriving = uploads.in_flight()

    # One call for the whole page rather than one per Recording: the speed the
    # service publishes is the same figure for all of them, and every Run in
    # the line is needed to say who is directly ahead of whom.
    speed = _service_speed()
    in_line = _runs_in_line()

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
                "received": arriving.get(str(recording.pk), (0, 0))[0],
                "job": _job_state(job, speed, in_line, request.user),
                "has_transcript": hasattr(recording, "transcript"),
                "can_retry": _can_retry(recording, job),
                "can_process_again": (
                    hasattr(recording, "transcript")
                    and job is not None
                    and not job.is_live
                ),
                "reprocessing": found.is_reprocessing,
            }
        )

    return JsonResponse(
        {
            "finished": found.is_finished,
            "started": found.created.isoformat(),
            "reprocessing": found.is_reprocessing,
            "everything_done_by": _everything_done_by(found, speed),
            "recordings": rows,
        }
    )


def _service_speed() -> dict | None:
    """The speed the service publishes, or nothing when it cannot be asked."""
    try:
        return (whisperx.status() or {}).get("speed")
    except Exception:  # noqa: BLE001 - a wait is not worth failing a page for
        return None


def _can_retry(recording, job) -> bool:
    """Whether this Recording is one a person can try again.

    A failed media step and a failed Job are both offered a Retry; nothing is
    thrown away by either failure, so the work that already succeeded is
    reused.
    """
    if recording.media_state == MediaState.FAILED:
        return True
    return job is not None and job.state == JobState.FAILED


def _everything_done_by(batch, speed) -> str | None:
    from core import waiting

    unfinished = []
    for recording in batch.recordings.all():
        job = recording.jobs.order_by("-created").first()
        if job is None or not job.is_live:
            continue
        unfinished.append(
            {
                "run": job.runs.order_by("side__number").first(),
                "model": recording.model or settings_store.get("model"),
                "diarize": recording.diarize,
                "minutes": (recording.duration_seconds or 0) / 60,
            }
        )
    return waiting.everything_done_by(unfinished, speed)


def _runs_in_line():
    """Every Run the app has at the service now, with whose it is.

    Needed to name the person directly ahead. Only the sign-in name of that
    one person is ever shown, and never a title or a file name of theirs.
    """
    from core.jobs import Run

    return list(
        Run.objects.filter(job__state__in=JobState.LIVE).select_related(
            "job__recording__user"
        )
    )


def _job_state(job, speed=None, in_line=None, user=None) -> dict | None:
    from core import waiting

    if job is None:
        return None
    run = job.runs.order_by("side__number").first()
    return {
        "state": job.state,
        "step": job.step,
        "percent": run.percent if run else None,
        "position": run.position if run else None,
        "audio_minutes_ahead": run.audio_minutes_ahead if run else None,
        "wait": waiting.for_run(run, speed) if run else None,
        "line": (
            waiting.queued_line(run, in_line or [], user, speed)
            if run is not None and user is not None
            else None
        ),
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
    lifecycle.remove_recording(
        recording, cause=cause, actor=request.user, request=request
    )


@login_required
@require_POST
def retry(request: HttpRequest, recording_id) -> JsonResponse:
    """Try a Failed Recording again, in a Batch of its own.

    Nothing was thrown away by the failure, so the media work that already
    succeeded is not repeated: a Recording that reached Ready goes straight
    back into the line, and one that failed earlier goes through the media
    steps again from where it stopped.
    """
    recording = Recording.objects.filter(pk=recording_id, user=request.user).first()
    if recording is None:
        return JsonResponse({"error": "no such recording"}, status=404)

    job = recording.jobs.order_by("-created").first()
    if not _can_retry(recording, job):
        return JsonResponse(
            {"error": "there is nothing to try again on this recording"}, status=400
        )

    unfinished = Batch.unfinished_for(request.user)
    if unfinished is not None:
        return JsonResponse(
            {
                "error": Refusal.MESSAGES[Refusal.BATCH_IN_PROGRESS],
                "reason_class": Refusal.BATCH_IN_PROGRESS,
                "batch": str(unfinished.pk),
            },
            status=409,
        )

    if not whisperx.is_alive():
        return JsonResponse(
            {
                "error": "Transcription is not available right now. Try again later.",
                "reason_class": Refusal.SERVICE_UNREACHABLE,
            },
            status=503,
        )

    batch = Batch.objects.create(user=request.user)
    recording.batch = batch
    recording.failure_message = ""
    recording.refusal_class = ""

    if recording.media_state == MediaState.FAILED:
        # The media work stopped part way. It starts again, and the steps that
        # already produced a file are not repeated.
        recording.media_state = MediaState.CHECKING
        recording.save()
        tasks.prepare_recording.defer(recording_id=str(recording.pk))
    else:
        recording.save()
        from core import queue

        again = queue.make_job(recording)
        tasks.hand_over_job.defer(job_id=str(again.pk))

    audit.write(
        audit.Category.JOBS,
        "Batch submitted",
        actor=request.user,
        request=request,
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
        why="retry",
    )
    return JsonResponse({"batch": str(batch.pk)})


@login_required
@require_POST
def process_again(request: HttpRequest, recording_id) -> JsonResponse:
    """Transcribe a Done Recording again, with settings a person may change.

    The old Transcript stays readable while the new one is made, and is locked
    meanwhile: a Correction to text that is about to be replaced would be lost
    without anybody being told. Cancelling unlocks it untouched.
    """
    recording = Recording.objects.filter(pk=recording_id, user=request.user).first()
    if recording is None:
        return JsonResponse({"error": "no such recording"}, status=404)
    if not hasattr(recording, "transcript"):
        return JsonResponse(
            {"error": "this recording has no transcript to replace"}, status=400
        )

    unfinished = Batch.unfinished_for(request.user)
    if unfinished is not None:
        return JsonResponse(
            {
                "error": Refusal.MESSAGES[Refusal.BATCH_IN_PROGRESS],
                "reason_class": Refusal.BATCH_IN_PROGRESS,
                "batch": str(unfinished.pk),
            },
            status=409,
        )

    if not whisperx.is_alive():
        return JsonResponse(
            {
                "error": "Transcription is not available right now. Try again later.",
                "reason_class": Refusal.SERVICE_UNREACHABLE,
            },
            status=503,
        )

    try:
        wanted = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        wanted = {}

    # The settings come pre-filled from the Recording and a person may change
    # any of them before submitting.
    for field, key in (
        ("spoken_language", "language"),
        ("context", "context"),
    ):
        if key in wanted:
            setattr(recording, field, (wanted.get(key) or "")[:500])
    if "diarize" in wanted:
        recording.diarize = bool(wanted["diarize"])
    if "translate" in wanted:
        recording.translate = bool(wanted["translate"])
    if "vocabulary" in wanted:
        recording.vocabulary = [
            line.strip()
            for line in str(wanted.get("vocabulary") or "").splitlines()
            if line.strip()
        ]

    batch = Batch.objects.create(user=request.user, is_reprocessing=True)
    recording.batch = batch
    recording.save()

    from core import queue

    again = queue.make_job(recording)
    tasks.hand_over_job.defer(job_id=str(again.pk))

    audit.write(
        audit.Category.JOBS,
        "Batch submitted",
        actor=request.user,
        request=request,
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
        why="process again",
        diarize=recording.diarize,
        translate=recording.translate,
    )
    return JsonResponse({"batch": str(batch.pk)})


@login_required
@require_POST
def delete_recording(request: HttpRequest, recording_id) -> JsonResponse:
    """Remove one Recording and everything about it.

    There is one Delete rather than a "remove the files, keep the text" pair:
    with nothing kept past the session the two would be the same thing.
    On a Recording whose Job has not ended this is the Cancel, because
    stopping the work and keeping the half of it that arrived is not
    something anybody wants.
    """
    recording = Recording.objects.filter(pk=recording_id).select_related("user").first()
    if recording is None or (
        recording.user_id != request.user.pk and not request.user.is_admin
    ):
        return JsonResponse({"error": "no such recording"}, status=404)

    cause = "owner" if recording.user_id == request.user.pk else "admin"

    live = list(recording.jobs.filter(state__in=JobState.LIVE))
    for job in live:
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
    if live:
        cause = "cancel"

    _remove(request, recording, cause=cause)
    return JsonResponse({"deleted": True})
