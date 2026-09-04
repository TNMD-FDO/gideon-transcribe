"""What a person does with a Clip: save one, adjust it, download it, delete it.

Every Clip belongs to a Recording and follows it everywhere. An Admin may play
and download another person's Clip, each download an audit row naming whose it
was, and may not adjust, rename, or delete it: those are the owner's.
"""

from __future__ import annotations

import io
import json
import logging
import shutil
import zipfile
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core import audit, clip_work, settings_store
from core.clips import SHORTEST_SECONDS, Clip, RenderState, next_title
from core.recordings import Recording

log = logging.getLogger("transcribe.clips")


def clips_are_on() -> bool:
    return bool(settings_store.get("clips_available"))


def _their_recording(request, recording_id) -> Recording | None:
    recording = (
        Recording.objects.filter(pk=recording_id).select_related("user").first()
    )
    if recording is None:
        return None
    if recording.user_id == request.user.pk or request.user.is_admin:
        return recording
    return None


def _their_clip(request, clip_id) -> Clip | None:
    clip = (
        Clip.objects.filter(pk=clip_id)
        .select_related("recording", "recording__user", "user")
        .first()
    )
    if clip is None:
        return None
    if clip.recording.user_id == request.user.pk or request.user.is_admin:
        return clip
    return None


def _row(clip: Clip) -> dict:
    return {
        "id": str(clip.pk),
        "recording": str(clip.recording_id),
        "recording_title": clip.recording.title,
        "title": clip.title,
        "note": clip.note,
        "start": clip.start,
        "end": clip.end,
        "seconds": clip.seconds,
        "burn_captions": clip.burn_captions,
        "include_excerpt": clip.include_excerpt,
        "state": clip.state,
        "shown_state": clip.shown_state,
        "stale": clip.captions_are_stale,
        "size": clip.size_bytes,
        "downloaded": (
            f"Downloaded {clip.first_downloaded:%d %b %H:%M}"
            if clip.first_downloaded
            else "Not yet"
        ),
        "is_video": clip.is_video,
        "url": f"/media/{clip.recording.user_id}/{clip.recording_id}/clips/"
        f"{clip.pk}{clip.suffix}",
    }


def _record(request, clip: Clip, event: str) -> None:
    """Every row carries the id, the span, and the options, never the title."""
    audit.write(
        audit.Category.CLIPS,
        event,
        actor=request.user,
        request=request,
        affected_user=(
            clip.recording.user
            if clip.recording.user_id != request.user.pk
            else None
        ),
        object_type="clip",
        object_id=clip.pk,
        object_label=f"{clip.start:.1f}-{clip.end:.1f}",
        burn_captions=clip.burn_captions,
        include_excerpt=clip.include_excerpt,
    )


def _start_render(clip: Clip) -> None:
    from core.tasks import render_clip

    render_clip.defer(clip_id=str(clip.pk))


# Saving, adjusting, deleting ---------------------------------------------------


@login_required
def clips_of(request: HttpRequest, recording_id) -> JsonResponse:
    """The Clips sheet's list, for one Recording."""
    recording = _their_recording(request, recording_id)
    if recording is None:
        return JsonResponse({"error": "no such recording"}, status=404)
    if not clips_are_on():
        return JsonResponse({"clips": [], "available": False})

    return JsonResponse(
        {
            "available": True,
            "next_title": next_title(recording),
            "longest_seconds": settings_store.longest_clip_seconds(),
            "clips": [_row(one) for one in recording.clips.all()],
        }
    )


@login_required
@require_POST
def save_clip(request: HttpRequest, recording_id) -> JsonResponse:
    """A new Clip, which starts rendering at once."""
    recording = _their_recording(request, recording_id)
    if recording is None:
        return JsonResponse({"error": "no such recording"}, status=404)
    if not clips_are_on():
        return JsonResponse({"error": "clips are switched off"}, status=403)
    if not recording.playback_ready:
        return JsonResponse(
            {"error": "this recording cannot be played yet"}, status=400
        )

    try:
        wanted = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "that could not be read"}, status=400)

    problem, start, end = _span(wanted, recording)
    if problem:
        return JsonResponse({"error": problem}, status=400)

    clip = Clip.objects.create(
        recording=recording,
        user=request.user,
        title=(wanted.get("title") or next_title(recording))[:120],
        note=(wanted.get("note") or "")[:1000],
        start=start,
        end=end,
        burn_captions=bool(wanted.get("burn_captions")),
        include_excerpt=wanted.get("include_excerpt", True),
    )
    _record(request, clip, "Clip created")
    _start_render(clip)
    return JsonResponse({"clip": _row(clip)})


def _span(wanted: dict, recording) -> tuple[str, float, float]:
    """The two times, checked against the shortest and longest a Clip may be."""
    try:
        start = max(0.0, float(wanted.get("start", 0)))
        end = float(wanted.get("end", 0))
    except (TypeError, ValueError):
        return "those times could not be read", 0.0, 0.0

    length = recording.duration_seconds or end
    end = min(end, length)

    if end - start < SHORTEST_SECONDS:
        return "A clip is at least one second long.", 0.0, 0.0

    longest = settings_store.longest_clip_seconds()
    if end - start > longest:
        return (
            f"A clip may be up to {longest // 60} minutes long.",
            0.0,
            0.0,
        )
    return "", start, end


@login_required
@require_POST
def change_clip(request: HttpRequest, clip_id) -> JsonResponse:
    """Adjust or Rename.

    Adjust changes the span or an option and re-renders. Rename changes the
    title or the note and renders nothing, which is why the two are told
    apart here rather than by two endpoints: what a person changed decides.
    """
    clip = _their_clip(request, clip_id)
    if clip is None:
        return JsonResponse({"error": "no such clip"}, status=404)
    if clip.recording.user_id != request.user.pk:
        # An Admin plays and downloads another person's Clip and no more.
        return JsonResponse({"error": "this clip is not yours"}, status=403)

    try:
        wanted = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "that could not be read"}, status=400)

    if "title" in wanted:
        clip.title = (wanted.get("title") or clip.title)[:120]
    if "note" in wanted:
        clip.note = (wanted.get("note") or "")[:1000]

    adjusting = False
    if "start" in wanted or "end" in wanted:
        problem, start, end = _span(
            {
                "start": wanted.get("start", clip.start),
                "end": wanted.get("end", clip.end),
            },
            clip.recording,
        )
        if problem:
            return JsonResponse({"error": problem}, status=400)
        adjusting = adjusting or (start != clip.start or end != clip.end)
        clip.start, clip.end = start, end

    for option in ("burn_captions", "include_excerpt"):
        if option in wanted and bool(wanted[option]) != getattr(clip, option):
            setattr(clip, option, bool(wanted[option]))
            adjusting = True

    clip.save()

    if adjusting:
        _start_render(clip)
    return JsonResponse({"clip": _row(clip), "rendering": adjusting})


@login_required
@require_POST
def rerender_clip(request: HttpRequest, clip_id) -> JsonResponse:
    """Retry a failed render, or bring burned captions up to date."""
    clip = _their_clip(request, clip_id)
    if clip is None:
        return JsonResponse({"error": "no such clip"}, status=404)
    if clip.recording.user_id != request.user.pk:
        return JsonResponse({"error": "this clip is not yours"}, status=403)

    _start_render(clip)
    return JsonResponse({"rendering": True})


@login_required
@require_POST
def delete_clip(request: HttpRequest, clip_id) -> JsonResponse:
    """Remove one Clip and its file, and nothing else."""
    clip = _their_clip(request, clip_id)
    if clip is None:
        return JsonResponse({"error": "no such clip"}, status=404)
    if clip.recording.user_id != request.user.pk:
        return JsonResponse({"error": "this clip is not yours"}, status=403)

    _record(request, clip, "Clip deleted")
    clip.path.unlink(missing_ok=True)
    clip.delete()
    return JsonResponse({"deleted": True})


# Downloading -------------------------------------------------------------------


def _hand_over(body: bytes, filename: str, content_type: str) -> HttpResponse:
    from urllib.parse import quote

    answer = HttpResponse(body, content_type=content_type)
    answer["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
    return answer


@login_required
def download_clip(request: HttpRequest, clip_id) -> HttpResponse:
    """One Clip: the file alone, or a zip with its excerpt and captions."""
    clip = _their_clip(request, clip_id)
    if clip is None or clip.state != RenderState.READY or not clip.path.exists():
        return HttpResponse("There is no such clip.", status=404)

    body, name, kind = clip_work.one_clip(clip)
    _record(request, clip, "Clip downloaded")
    clip_work.mark_downloaded(clip, clip.recording.user_id == request.user.pk)
    return _hand_over(body, name, kind)


@login_required
def download_all_clips(request: HttpRequest) -> HttpResponse:
    """Every Ready Clip in the Workspace, flat, with no zip inside a zip."""
    clips = [
        one
        for one in Clip.objects.filter(recording__user=request.user).select_related(
            "recording", "recording__user"
        )
        if one.state == RenderState.READY and one.path.exists()
    ]

    holder = io.BytesIO()
    taken: set[str] = set()
    with zipfile.ZipFile(holder, "w", zipfile.ZIP_DEFLATED) as bundle:
        for clip in clips:
            clip_work.add_to_zip(bundle, clip, taken)
            _record(request, clip, "Clip downloaded")
            clip_work.mark_downloaded(clip, True)

    return _hand_over(
        holder.getvalue(),
        f"clips {datetime.now():%Y-%m-%d %H%M}.zip",
        "application/zip",
    )


# The Clips page ----------------------------------------------------------------


@login_required
def clips_page(request: HttpRequest) -> HttpResponse:
    """Every Clip in the Workspace, grouped by Recording in upload order."""
    if not clips_are_on():
        return redirect(reverse("home"))

    from core.pages import standing_line

    groups = []
    total = 0
    for recording in (
        Recording.objects.filter(user=request.user, clips__isnull=False)
        .distinct()
        .order_by("created")
    ):
        rows = list(recording.clips.all())
        total += sum(one.size_bytes for one in rows)
        groups.append({"recording": recording, "clips": rows})

    return render(
        request,
        "clips.html",
        {
            "groups": groups,
            "total": f"{total / 1024 / 1024:.1f} MB",
            "any_ready": any(
                one.state == RenderState.READY
                for group in groups
                for one in group["clips"]
            ),
            "standing_line": standing_line(),
        },
    )


# Used by the Recording's own deletion, so that a render in flight leaves
# nothing behind.
def remove_files_of(recording) -> None:
    shutil.rmtree(recording.folder / "clips", ignore_errors=True)
