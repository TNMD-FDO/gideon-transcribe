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
