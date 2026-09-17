"""The Incident page and its endpoints (Phase 6 chapter 1).

A page of its own inside a case, in the Speakers page's shape: the Wall of
cameras playing in step, one transport, one clock, the strip across the
width, and the Cameras and Details tabs. The browser keeps the cameras in
step; this side keeps the rows and says what each camera is.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core import cases, incidents, sharing
from core.case_pages import _their_case
from core.incidents import Incident, IncidentCamera
from core.media_access import media_root
from core.recordings import Recording
from core.viewer import colour_for


def _on_or_404() -> None:
    if not incidents.on():
        raise Http404("Incidents are off")


def _incident(request, case_id, incident_id) -> tuple:
    _on_or_404()
    case = _their_case(request, case_id)
    incident = get_object_or_404(Incident, pk=incident_id, case=case)
    return case, incident


@login_required
def page(request: HttpRequest, case_id, incident_id) -> HttpResponse:
    case, incident = _incident(request, case_id, incident_id)
    role = case.role_of(request.user)
    if role != "admin":
        cases.note_activity(case, by=request.user)
    if role == "collaborator":
        sharing.note_opened(case, request.user)
    state = state_json(incident, request.user)
    return render(
        request,
        "incident.html",
        {
            "page": "cases",
            "case": case,
            "incident": incident,
            "role": role,
            "state": state,
            "at": _asked_moment(request, incident, state),
            "others": _others(case, incident),
        },
    )


def _asked_moment(request, incident: Incident, state: dict) -> float:
    """Where the page opens: ?t= on the Incident clock, ?recording=&at= on a
    camera's own clock, else the first placed camera's start."""
    try:
        if request.GET.get("t"):
            return max(0.0, float(request.GET["t"]))
        if request.GET.get("recording") and request.GET.get("at"):
            camera = IncidentCamera.objects.filter(
                incident=incident, recording_id=request.GET["recording"]
            ).first()
            if camera is not None and camera.is_placed():
                return camera.starts_at + float(request.GET["at"])
    except (TypeError, ValueError):
        pass
    low = state["incident"]["span_low"]
    return float(low) if low is not None else 0.0


def _others(case, incident: Incident) -> list[dict]:
    """The case's videos not in this Incident, for Add cameras."""
    inside = set(incident.cameras.values_list("recording_id", flat=True))
    rows = []
    for recording in case.recordings.order_by("title"):
        if recording.pk in inside or not incidents.is_video(recording):
            continue
        elsewhere = incidents.incident_of(recording)
        words, tone = incidents.stamp_words(recording)
        rows.append(
            {
                "recording": recording,
                "clock": words,
                "tone": tone,
                "elsewhere": elsewhere.incident.name if elsewhere else "",
            }
        )
    return rows


def _camera_json(camera: IncidentCamera, colour: str, on_wall: bool) -> dict:
    recording = camera.recording
    playback = recording.playback_path() if recording.playback_ready else None
    words, tone = incidents.stamp_words(recording)
    file_words, _ = incidents.file_time_of(recording)
    return {
        "id": str(camera.pk),
        "recording": str(recording.pk),
        "title": recording.title,
        "camera_id": camera.camera_id(),
        "colour": colour,
        "starts_at": camera.starts_at,
        "length": camera.length(),
        "placed": camera.placed,
        "placed_words": incidents.PLACED_WORDS.get(camera.placed, ""),
        "placed_tone": incidents.PLACED_TONES.get(camera.placed, ""),
        "placed_by": camera.placed_by.shown_name if camera.placed_by else "",
        "placed_at": camera.placed_at.isoformat() if camera.placed_at else "",
        "on_wall": on_wall,
        "media_url": f"{media_root(recording)}/{playback.name}" if playback else "",
        "clock": words,
        "clock_tone": tone,
        "file_time": file_words,
        "has_clock": incidents.clock_zero_of(recording) is not None,
        "has_transcript": hasattr(recording, "transcript"),
        "viewer_url": reverse("viewer", args=[recording.pk]),
        "match": {
            "state": camera.match_state,
            "against": str(camera.match_against_id) if camera.match_against_id else "",
            "lag": camera.match_lag,
            "strength": camera.match_strength,
            "reason": camera.match_reason,
        },
    }


def state_json(incident: Incident, user) -> dict:
    """Everything the page draws from, in one answer."""
    cameras = list(incident.cameras.select_related("recording", "placed_by"))
    placed = sorted(
        (one for one in cameras if one.is_placed()),
        key=lambda one: (one.starts_at, one.added),
    )
    unplaced = [one for one in cameras if not one.is_placed()]
    ordered = placed + unplaced
    colours = {str(one.pk): colour_for(index) for index, one in enumerate(ordered)}
    wall = {str(one.pk) for one in incidents.wall_of(incident)}
    low, high = incidents.span_of(incident)
    placed_words, placed_tone = incidents.placed_words(incident)
    return {
        "incident": {
            "id": str(incident.pk),
            "name": incident.name,
            "case": incident.case.name,
            "case_url": reverse("case", args=[incident.case_id]),
            "has_clock": incident.has_clock(),
            "clock_zero": incident.clock_zero,
            "clock_date": incident.clock_date,
            "span_low": low,
            "span_high": high,
            "span_words": incidents.span_words(incident),
            "placed_words": placed_words,
            "placed_tone": placed_tone,
            "count": len(cameras),
            "wall_size": incidents.wall_size(),
            "most": incidents.most_cameras(),
            "sound_match": incidents.sound_match_on(),
            "created_by": incident.created_by.shown_name if incident.created_by else "",
            "created": incident.created.isoformat(),
            "how": incident.how,
        },
        "cameras": [
            _camera_json(one, colours[str(one.pk)], str(one.pk) in wall)
            for one in ordered
        ],
    }


@login_required
def state(request: HttpRequest, case_id, incident_id) -> JsonResponse:
    _, incident = _incident(request, case_id, incident_id)
    return JsonResponse(state_json(incident, request.user))


@login_required
def lines(request: HttpRequest, camera_id) -> JsonResponse:
    """One camera's words and camera lines, for the line under its tile."""
    _on_or_404()
    camera = get_object_or_404(IncidentCamera, pk=camera_id)
    recording = camera.recording
    if not cases.standing(recording, request.user):
        raise Http404("not this person's recording")
    transcript = getattr(recording, "transcript", None)
    if transcript is None:
        return JsonResponse({"segments": [], "moments": []})
    names = list(
        transcript.segments.filter(same_as_other_side=False)
        .exclude(speaker="")
        .order_by("speaker")
        .values_list("speaker", flat=True)
        .distinct()
    )
    colours = {name: colour_for(index) for index, name in enumerate(names)}
    from core.assistant import DONE, Moment

    return JsonResponse(
        {
            "segments": [
                {
                    "start": one.start,
                    "end": one.end,
                    "speaker": one.speaker,
                    "colour": colours.get(one.speaker, ""),
                    "text": one.text,
                }
                for one in transcript.segments.filter(same_as_other_side=False)
            ],
            "moments": [
                {"start": one.span_start, "end": one.span_end, "text": one.text}
                for one in transcript.moments.filter(state=DONE, source=Moment.INTERVAL)
                .exclude(text="")
                .order_by("span_start")
            ],
        }
    )


def _camera_of(incident: Incident, camera_id) -> IncidentCamera:
    return get_object_or_404(
        IncidentCamera.objects.select_related("recording"),
        pk=camera_id,
        incident=incident,
    )


@login_required
@require_POST
def act(request: HttpRequest, case_id, incident_id) -> JsonResponse:
    """The page's changes, one endpoint: place, match, wall, rename, add,
    remove, delete. Every answer carries the state, so the page redraws."""
    case, incident = _incident(request, case_id, incident_id)
    action = request.POST.get("action", "")
    user = request.user
    said = ""
    if action == "place":
        camera = _camera_of(incident, request.POST.get("camera"))
        how = request.POST.get("how", "")
        if how == "clock":
            if not incidents.place_from_clock(camera, by=user, request=request):
                return JsonResponse(
                    {"error": "This camera has no clock in its picture."}, status=400
                )
        elif how == "file":
            if not incidents.place_from_file(camera, by=user, request=request):
                return JsonResponse(
                    {
                        "error": (
                            "The file carries no time, or the incident "
                            "has no clock yet."
                        )
                    },
                    status=400,
                )
        elif how == "hand":
            try:
                starts_at = float(request.POST.get("starts_at", ""))
            except ValueError:
                return JsonResponse({"error": "Where should it start?"}, status=400)
            incidents.place_by_hand(camera, starts_at, by=user, request=request)
        elif how == "match":
            if not incidents.apply_match(camera, by=user, request=request):
                return JsonResponse({"error": "No finished match to take."}, status=400)
        else:
            return JsonResponse({"error": "How?"}, status=400)
    elif action == "match":
        camera = _camera_of(incident, request.POST.get("camera"))
        against = _camera_of(incident, request.POST.get("against"))
        if not incidents.ask_for_match(camera, against, by=user):
            return JsonResponse(
                {"error": "The sound match needs a placed camera to match against."},
                status=400,
            )
        said = "Matching the sound; about a minute."
    elif action == "wall":
        wanted = [one for one in request.POST.get("cameras", "").split(",") if one]
        incidents.set_wall(incident, wanted)
    elif action == "rename":
        incidents.rename(
            incident, request.POST.get("name", ""), by=user, request=request
        )
    elif action == "add":
        wanted = request.POST.getlist("recordings")
        chosen = list(case.recordings.filter(pk__in=wanted))
        added = incidents.add_cameras(incident, chosen, by=user, request=request)
        said = f"{added} camera{'' if added == 1 else 's'} added."
    elif action == "remove":
        camera = _camera_of(incident, request.POST.get("camera"))
        incidents.remove_camera(camera, by=user, request=request)
    elif action == "delete":
        incidents.delete(incident, by=user, request=request)
        return JsonResponse({"ok": True, "redirect": reverse("case", args=[case.pk])})
    else:
        return JsonResponse({"error": "Unknown action"}, status=400)
    return JsonResponse({"ok": True, "said": said, "state": state_json(incident, user)})


# From the case page --------------------------------------------------------------


@login_required
@require_POST
def new_incident(request: HttpRequest, case_id) -> HttpResponse:
    """New incident, or the offer's Make it: the videos ticked, named, opened."""
    _on_or_404()
    case = _their_case(request, case_id)
    wanted = request.POST.getlist("recordings")
    chosen = [
        one
        for one in case.recordings.filter(pk__in=wanted).order_by("created")
        if incidents.is_video(one)
    ]
    if not chosen:
        messages.error(request, "Tick at least one video for the incident.")
        return redirect("case", case.pk)
    how = (
        incidents.FROM_OFFER
        if request.POST.get("how") == "offer"
        else incidents.BY_HAND
    )
    name = request.POST.get("name", "").strip() or _suggested_name(chosen)
    incident = incidents.make(
        case, name, chosen, by=request.user, how=how, request=request
    )
    return redirect(incident.url())


def _suggested_name(recordings) -> str:
    """The date of the first clock among them, else the first title."""
    for recording in recordings:
        date = ((recording.stamp or {}).get("date") or "").strip()
        if date and incidents.stamp_checked(recording):
            return date
    return recordings[0].title


@login_required
@require_POST
def decline_offer(request: HttpRequest, case_id) -> HttpResponse:
    """Not these: the offer is not shown again for that set of videos."""
    _on_or_404()
    case = _their_case(request, case_id)
    key = request.POST.get("key", "")[:2000]
    if key:
        incidents.decline(case, key)
    return redirect("case", case.pk)


@login_required
@require_POST
def add_to_incident(request: HttpRequest, case_id) -> HttpResponse:
    """The offer's Add it: one video into the Incident it ran during."""
    _on_or_404()
    case = _their_case(request, case_id)
    incident = get_object_or_404(Incident, pk=request.POST.get("incident"), case=case)
    recording = get_object_or_404(
        Recording, pk=request.POST.get("recording"), case=case
    )
    incidents.add_cameras(incident, [recording], by=request.user, request=request)
    return redirect(incident.url())
