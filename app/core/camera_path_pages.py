"""The Map tab's endpoints (Phase 12 chapter 1): a path file added to or
removed from a recording, several files matched to their videos at once,
and the one reading the tab draws from."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, JsonResponse
from django.views.decorators.http import require_POST

from core import camera_paths, cases
from core.case_pages import _on_or_404, _their_case
from core.recordings import Recording


def _maps_or_404() -> None:
    _on_or_404()
    if not camera_paths.on():
        raise Http404("Maps are off")


def _recording_for(request: HttpRequest, recording_id):
    recording = (
        Recording.objects.filter(pk=recording_id).select_related("case", "user").first()
    )
    if recording is None or not cases.standing(recording, request.user):
        return None
    return recording


@login_required
@require_POST
def add(request: HttpRequest, recording_id) -> JsonResponse:
    """One file onto one recording, from a camera's row."""
    _maps_or_404()
    recording = _recording_for(request, recording_id)
    if recording is None:
        return JsonResponse({"error": "no such recording"}, status=404)
    upload = request.FILES.get("file")
    if upload is None:
        return JsonResponse(
            {"error": "Choose the camera's path file first."}, status=400
        )
    if upload.size > camera_paths.MOST_BYTES:
        return JsonResponse(
            {
                "error": f"That file is too large; a path file is under "
                f"{camera_paths.MOST_BYTES // (1024 * 1024)} MB."
            },
            status=400,
        )
    try:
        path, warnings = camera_paths.add(
            recording,
            data=upload.read(),
            filename=upload.name,
            by=request.user,
            request=request,
            replace=request.POST.get("replace") == "1",
        )
    except camera_paths.Refused as refused:
        return JsonResponse({"error": str(refused)}, status=400)
    return JsonResponse(
        {
            "ok": True,
            "fixes": path.fix_count,
            "words": camera_paths.words(path),
            "warnings": warnings,
        }
    )


@login_required
@require_POST
def remove(request: HttpRequest, recording_id) -> JsonResponse:
    _maps_or_404()
    recording = _recording_for(request, recording_id)
    if recording is None:
        return JsonResponse({"error": "no such recording"}, status=404)
    path = camera_paths.of(recording)
    if path is None:
        return JsonResponse({"error": "This recording has no path file."}, status=400)
    camera_paths.remove(path, by=request.user, request=request)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def offer(request: HttpRequest, recording_id) -> JsonResponse:
    """A reading offered to the chronology (chapter 3): JSON t, words, until."""
    import json

    _maps_or_404()
    recording = _recording_for(request, recording_id)
    if recording is None:
        return JsonResponse({"error": "no such recording"}, status=404)
    try:
        body = json.loads(request.body or b"{}")
        t = float(body.get("t", 0.0))
        until = body.get("until")
        until = None if until in (None, "") else float(until)
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({"error": "The reading's moment was not read."}, status=400)
    try:
        camera_paths.offer_to_chronology(
            recording,
            t=t,
            words=str(body.get("words", "")),
            until=until,
            by=request.user,
            request=request,
        )
    except camera_paths.Refused as refused:
        return JsonResponse({"error": str(refused)}, status=400)
    return JsonResponse(
        {
            "ok": True,
            "words": (
                "Offered: it waits on the Proposed events tab, for Accept or Dismiss."
            ),
        }
    )


def _waiting_for(request: HttpRequest, case_id, waiting_id):
    _maps_or_404()
    case = _their_case(request, case_id)
    if not case.role_of(request.user):
        return None, JsonResponse({"error": "You cannot change this case."}, status=403)
    one = camera_paths.WaitingPathFile.objects.filter(pk=waiting_id, case=case).first()
    if one is None:
        return None, JsonResponse(
            {"error": "That file is no longer waiting."}, status=404
        )
    return one, None


@login_required
@require_POST
def waiting_remove(request: HttpRequest, case_id, waiting_id) -> JsonResponse:
    """Remove one path file that waits for its video (chapter 6)."""
    one, refused = _waiting_for(request, case_id, waiting_id)
    if refused is not None:
        return refused
    camera_paths.remove_waiting(one, by=request.user, request=request)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def waiting_add_anyway(request: HttpRequest, case_id, waiting_id) -> JsonResponse:
    """Add anyway: a flagged waiting file onto the video it was flagged against."""
    one, refused = _waiting_for(request, case_id, waiting_id)
    if refused is not None:
        return refused
    try:
        path = camera_paths.pair_anyway(one, by=request.user, request=request)
    except camera_paths.Refused as told:
        return JsonResponse({"error": str(told)}, status=400)
    return JsonResponse({"ok": True, "words": camera_paths.words(path)})


@login_required
@require_POST
def waiting_remove_all(request: HttpRequest, case_id) -> JsonResponse:
    _maps_or_404()
    case = _their_case(request, case_id)
    if not case.role_of(request.user):
        return JsonResponse({"error": "You cannot change this case."}, status=403)
    count = camera_paths.remove_all_waiting(case, by=request.user, request=request)
    return JsonResponse({"ok": True, "count": count})


@login_required
@require_POST
def note_all(request: HttpRequest, case_id) -> JsonResponse:
    """Note on all shown (chapter 6): one note written on every camera the
    page names, each at its own moment, as ordinary notes with one shared
    mark so the Notes tab lists them once. JSON: note, at {recording: seconds}."""
    import json
    import uuid

    from core import notes, numbers

    _maps_or_404()
    case = _their_case(request, case_id)
    if not case.role_of(request.user):
        return JsonResponse({"error": "You cannot add to this case."}, status=403)
    try:
        wanted = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "That could not be read."}, status=400)
    words = notes.clean(wanted.get("note", ""))
    moments = wanted.get("at") if isinstance(wanted.get("at"), dict) else {}
    if not words:
        return JsonResponse({"error": "The note is empty."}, status=400)
    if not moments:
        return JsonResponse({"error": "No camera is shown to note."}, status=400)
    recordings = {
        str(one.pk): one
        for one in Recording.objects.filter(case=case, pk__in=list(moments)[:200])
    }
    if len(recordings) != len(moments):
        return JsonResponse(
            {"error": "A camera named is not in this case."}, status=400
        )
    origin = {
        "kind": "map-all",
        "group": uuid.uuid4().hex,
        "count": len(recordings),
        "words": f"from the map, on {len(recordings)} cameras",
    }
    kept = 0
    for recording_id, recording in recordings.items():
        at = numbers.finite(
            moments[recording_id], least=0.0, most=numbers.A_DAY_AND_MORE
        )
        if at is None:
            continue
        length = recording.duration_seconds
        if length and at > float(length) + 1:
            continue
        spoken = notes.spoken_at(getattr(recording, "transcript", None), at)
        if spoken is not None:
            notes.set_note(
                spoken, words, by=request.user, request=request, origin=origin
            )
        else:
            notes.note_at(
                recording, at, words, by=request.user, request=request, origin=origin
            )
        kept += 1
    if not kept:
        return JsonResponse(
            {"error": "No camera is at that moment of its recording."}, status=400
        )
    return JsonResponse(
        {"ok": True, "count": kept, "words": f"Note kept on {kept} cameras."}
    )


@login_required
@require_POST
def picture(request: HttpRequest, case_id) -> JsonResponse:
    """Save a picture of the map (chapter 5): the PNG the browser drew, kept
    as a Document on the incident or the recording the picture is about."""
    from core import documents
    from core.incidents import Incident

    _maps_or_404()
    case = _their_case(request, case_id)
    if not case.role_of(request.user):
        return JsonResponse({"error": "You cannot add to this case."}, status=403)
    if not documents.on():
        return JsonResponse(
            {"error": "Documents are off, so the picture has nowhere to go."},
            status=400,
        )
    upload = request.FILES.get("file")
    if upload is None:
        return JsonResponse({"error": "No picture arrived."}, status=400)
    if upload.size > documents.PICTURE_MOST:
        return JsonResponse({"error": "That picture is too large to keep."}, status=400)
    incident = None
    recording = None
    if request.POST.get("incident"):
        incident = Incident.objects.filter(
            pk=request.POST.get("incident"), case=case
        ).first()
    if request.POST.get("recording"):
        recording = Recording.objects.filter(
            pk=request.POST.get("recording"), case=case
        ).first()
    try:
        home = documents.home_of(case, incident=incident, recording=recording)
        document = documents.add_picture(
            case,
            home=home,
            data=upload.read(),
            filename=upload.name or "map.png",
            title=request.POST.get("title", ""),
            by=request.user,
            request=request,
        )
    except documents.Refused as refused:
        return JsonResponse({"error": str(refused)}, status=400)
    return JsonResponse(
        {
            "ok": True,
            "url": document.url(),
            "title": document.title,
            "words": f"Saved as a Document on {documents.home_words(home)}.",
        }
    )


@login_required
def where(request: HttpRequest, recording_id) -> JsonResponse:
    """Where the camera was at a moment (chapter 4): a fix or none, and the
    case's other cameras by distance; never a position."""
    _maps_or_404()
    recording = _recording_for(request, recording_id)
    if recording is None:
        return JsonResponse({"error": "no such recording"}, status=404)
    try:
        t = float(request.GET.get("t", "0"))
    except ValueError:
        return JsonResponse({"error": "The moment was not read."}, status=400)
    return JsonResponse(camera_paths.where_at(recording, t))


@login_required
@require_POST
def paths_add(request: HttpRequest, case_id) -> JsonResponse:
    """Several files at once: `files` repeated; `chosen` repeated beside
    them, the recording id a person picked for a file (or ""); `replace`
    repeated, the recording ids a person said to replace."""
    _maps_or_404()
    case = _their_case(request, case_id)
    files = request.FILES.getlist("files")
    if not files:
        return JsonResponse({"error": "Choose the path files first."}, status=400)
    chosen = request.POST.getlist("chosen")
    chosen = chosen + [""] * (len(files) - len(chosen))
    uploads = []
    for upload, pick in zip(files, chosen, strict=False):
        if upload.size > camera_paths.MOST_BYTES:
            uploads.append((upload.name, b"", pick))
            continue
        uploads.append((upload.name, upload.read(), pick))
    told = camera_paths.match_files(
        case,
        uploads,
        by=request.user,
        request=request,
        replace_ids=request.POST.getlist("replace"),
    )
    return JsonResponse({"ok": True, **told})


@login_required
def map_json(request: HttpRequest, case_id) -> JsonResponse:
    """What the Map tab reads once on opening, and again after a change."""
    _maps_or_404()
    case = _their_case(request, case_id)
    day = request.GET.get("day", "").strip()[:10]
    return JsonResponse(camera_paths.map_of(case, day=day, viewer=request.user))
