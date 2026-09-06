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

from core import audit, cases, clip_work, exports, settings_store
from core.clips import SHORTEST_SECONDS, Clip, RenderState, next_title
from core.media_access import media_root
from core.recordings import Recording

log = logging.getLogger("transcribe.clips")


def clips_are_on() -> bool:
    return bool(settings_store.get("clips_available"))


def _their_recording(request, recording_id) -> Recording | None:
    recording = Recording.objects.filter(pk=recording_id).select_related("user").first()
    if recording is None or not cases.standing(recording, request.user):
        # Not theirs, not a Case they are in, not an Admin; or a Recording in
        # a binned Case, which is nobody's until the Case is restored.
        return None
    return recording


def _their_clip(request, clip_id) -> Clip | None:
    clip = (
        Clip.objects.filter(pk=clip_id)
        .select_related("recording", "recording__user", "user")
        .first()
    )
    if clip is None or not cases.standing(clip.recording, request.user):
        return None
    return clip


def _may_change(clip: Clip, asker) -> bool:
    """Who may adjust, re-render, or delete a Clip.

    The uploader and every member of the Case, because a Clip can be redone
    and nothing inside a shared Case is one person's. An Admin who is not on
    the Case plays and downloads and no more.
    """
    return asker is None or cases.standing(clip.recording, asker) == "own"


def spell(seconds: float) -> str:
    """A length a person reads: "45 s", "1 min 37 s", "1 h 2 min"."""
    whole = int(round(seconds or 0))
    hours, rest = divmod(whole, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours} h {minutes} min" if minutes else f"{hours} h"
    if minutes:
        return f"{minutes} min {secs} s" if secs else f"{minutes} min"
    return f"{secs} s"


def _row(clip: Clip, here=None, asker=None) -> dict:
    """One Clip, as the sheet and the Case's Clips tab both draw it.

    `here` is the Recording whose page this is, so a Clip from elsewhere in
    the Case can say where it came from. `asker` decides what may be changed:
    an Admin who does not own the Recording may play and download and nothing
    else, in a Case as in a Workspace.
    """
    in_a_case = bool(clip.recording.case_id)
    may_change = _may_change(clip, asker)
    return {
        "here": here is None or clip.recording_id == here.pk,
        "in_a_case": in_a_case,
        "may_change": may_change,
        # Who saved it, which a Case shows because Collaborators exist. In a
        # Workspace it is always the one person, so it is not drawn.
        "saved_by": clip.user.shown_name or clip.user.username,
        "id": str(clip.pk),
        "recording": str(clip.recording_id),
        "recording_title": clip.recording.title,
        "title": clip.title,
        "note": clip.note,
        "start": clip.start,
        "end": clip.end,
        "seconds": clip.seconds,
        # As a person reads them: clocks for the span, words for the length.
        "span": f"{exports.clock(clip.start)} to {exports.clock(clip.end)}",
        "length": spell(clip.seconds),
        "burn_captions": clip.burn_captions,
        "include_excerpt": clip.include_excerpt,
        "state": clip.state,
        "shown_state": clip.shown_state,
        "stale": clip.captions_are_stale,
        "size": clip.size_bytes,
        # Nothing is lost at sign-out in a Case, so a Case never says
        # whether a Clip has been downloaded.
        "downloaded": (
            ""
            if clip.recording.case_id
            else (
                f"Downloaded {clip.first_downloaded:%d %b %H:%M}"
                if clip.first_downloaded
                else "Not yet"
            )
        ),
        "saved": f"{clip.created:%d %b %H:%M}",
        "is_video": clip.is_video,
        "url": f"{media_root(clip.recording)}/clips/{clip.pk}{clip.suffix}",
    }


def _record(request, clip: Clip, event: str) -> None:
    """Every row carries the id, the span, and the options, never the title."""
    audit.write(
        audit.Category.CLIPS,
        event,
        actor=request.user,
        request=request,
        affected_user=(
            clip.recording.user if clip.recording.user_id != request.user.pk else None
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
    """The Clips sheet's list.

    One Recording's Clips in the Workspace. In a Case, every Clip of every
    Recording in that Case, with this Recording's own first, because somebody
    working through a matter wants the Clips they have already taken from it
    to hand rather than a page away.
    """
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
            "in_case": bool(recording.case_id) and cases.folder_management_on(),
            "clips": [
                _row(one, here=recording, asker=request.user)
                for one in _the_ones_to_show(recording)
            ],
        }
    )


def _the_ones_to_show(recording):
    """This Recording's Clips, or the whole Case's with these first."""
    if not recording.case_id or not cases.folder_management_on():
        return list(recording.clips.all())

    mine = list(recording.clips.all())
    others = list(
        Clip.objects.filter(recording__case_id=recording.case_id)
        .exclude(recording_id=recording.pk)
        .select_related("recording", "user")
        .order_by("recording__created", "created")
    )
    return mine + others


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

    from core.viewer import being_replaced

    if being_replaced(recording):
        return JsonResponse(
            {
                "error": "This recording is being transcribed again, so a new "
                "clip cannot be saved until it lands."
            },
            status=409,
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

    from core import cases

    # Saving a Clip is use of the Case the Recording is in.
    cases.used(recording, by=request.user)

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
    if not _may_change(clip, request.user):
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
    if not _may_change(clip, request.user):
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
    if not _may_change(clip, request.user):
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
        for one in Clip.objects.filter(
            recording__user=request.user, recording__case__isnull=True
        ).select_related("recording", "recording__user")
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
    """Every Clip in the Workspace, grouped by Recording in upload order.

    The Workspace's only: a Clip of a Recording in a Case is listed on that
    Case's own page, so a Clip appears in one place and not two. The Case's
    Clips tab is the Clips in Cases chapter's and is not built, so those Clips
    have no list yet; their files are made and kept either way.
    """
    if not clips_are_on():
        return redirect(reverse("home"))

    from core.pages import standing_line

    # One table for every clip, in the order of the recordings' upload and
    # the clips' start inside each, with the recording as a column and a
    # filter by recording above. Each clip knows its file's address so the
    # page can play it where it is chosen.
    recordings = list(
        Recording.objects.filter(
            user=request.user, case__isnull=True, clips__isnull=False
        )
        .distinct()
        .order_by("created")
    )
    clips = []
    total = 0
    for recording in recordings:
        for one in recording.clips.all():
            one.url = f"{media_root(recording)}/clips/{one.pk}{one.suffix}"
            total += one.size_bytes
            clips.append(one)

    return render(
        request,
        "clips.html",
        {
            "page": "clips",
            "clips": clips,
            "recordings": recordings,
            "total": f"{total / 1024 / 1024:.1f} MB",
            "any_ready": any(one.state == RenderState.READY for one in clips),
            "standing_line": standing_line(),
        },
    )


# Used by the Recording's own deletion, so that a render in flight leaves
# nothing behind.
def remove_files_of(recording) -> None:
    shutil.rmtree(recording.folder / "clips", ignore_errors=True)
