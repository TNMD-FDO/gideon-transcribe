"""Clip this event: the clip across cameras (Phase 7 chapter 1).

One press on an Event cuts one file from the event's cameras over its span,
the focus camera large or a grid, the Incident clock and the camera ids
burned in, the sound from one camera. What is made is a Clip like any other,
on the Recording of the camera it is heard from, carrying its picture: the
cameras with each one's offset and id, the layout, the sound camera, the
burn choices and the clock, copied here so that Render again remakes it the
same whatever happens to the Incident afterwards.
"""

from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from core import cases, clip_pages, incidents, media, settings_store
from core.chronology import Event
from core.clips import SHORTEST_SECONDS, Clip
from core.incidents import DAY, Incident, IncidentCamera

# The span the box offers: ten seconds either side of the event.
AROUND_SECONDS = 10


def on() -> bool:
    """Clip this event is offered while Incidents, Clips and Incident clips
    are all on."""
    return bool(
        incidents.on()
        and settings_store.get("clips_available")
        and settings_store.get("incidents_clips")
    )


def clock_delta(incident: Incident, from_at: float) -> int | None:
    """The second of the day on the Incident clock at the clip's first frame,
    a whole number in [0, 86400), or None while the Incident has no clock.

    Whole, so that the frame burned at the first second reads exactly what
    the box said (drawtext floors where the page rounds); wrapped, so that
    the sum drawtext takes never goes negative and a clip across midnight
    reads 00:00:05 as the page does.
    """
    if incident.clock_zero is None:
        return None
    return int(round(incident.clock_zero + from_at)) % int(DAY)


def picture_for(
    incident: Incident,
    cameras: list[IncidentCamera],
    sound: IncidentCamera,
    layout: str,
    span: tuple[float, float],
    *,
    burn_clock: bool,
    burn_ids: bool,
) -> dict:
    """Everything Render again needs, copied now."""
    from_at, until_at = span
    delta = clock_delta(incident, from_at)
    return {
        "span": [round(from_at, 3), round(until_at, 3)],
        "clock": delta,
        "layout": layout,
        "sound": str(sound.pk),
        "burn_clock": bool(burn_clock) and delta is not None,
        "burn_ids": bool(burn_ids),
        "cameras": [
            {
                "camera": str(one.pk),
                "recording": str(one.recording_id),
                # The camera's own second at the clip's first frame; negative
                # when it starts inside the span.
                "offset": round(from_at - float(one.starts_at), 3),
                "label": media.id_label(one.camera_id(), media.WALL_WIDTH),
            }
            for one in cameras
        ],
    }


def _number(value, fallback=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def keeps_in_case(recording) -> str:
    """Why a recording cannot leave its case: the Incident clips on it.

    An Incident cannot cross a case's edge (Phase 6 chapter 1), and a clip
    cut from one carries the other cameras' pictures in its file and their
    recording ids in its picture, so it must not follow its sound recording
    into a case whose people may not open the incident. The words for the
    person, or "" when nothing holds it.
    """
    count = Clip.objects.filter(recording=recording, picture__isnull=False).count()
    if not count:
        return ""
    return (
        f"This recording carries {count} clip{'' if count == 1 else 's'} cut from "
        "an incident in this case. Delete them first, or leave the recording here."
    )


@login_required
@require_POST
def make_clip(request: HttpRequest, case_id, incident_id, event_id) -> JsonResponse:
    """Make the clip: the checks in the chapter's order, then a Clip row and
    its render. The answer carries the row and the page's state, so the
    event's clip mark redraws."""
    from core.incident_pages import _incident, state_json

    case, incident = _incident(request, case_id, incident_id)
    if not on():
        return JsonResponse({"error": "Incident clips are switched off."}, status=403)
    event = get_object_or_404(
        Event, pk=event_id, incident=incident, proposed=False, dismissed=False
    )
    try:
        wanted = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        wanted = None
    if not isinstance(wanted, dict):
        return JsonResponse({"error": "That could not be read."}, status=400)

    from_at = _number(wanted.get("from"))
    until_at = _number(wanted.get("until"))
    if from_at is None or until_at is None:
        return JsonResponse({"error": "Those times could not be read."}, status=400)
    if until_at - from_at < SHORTEST_SECONDS:
        return JsonResponse(
            {"error": "A clip is at least one second long."}, status=400
        )
    longest = settings_store.longest_clip_seconds()
    if until_at - from_at > longest:
        return JsonResponse(
            {"error": f"A clip may be up to {longest // 60} minutes long."}, status=400
        )

    # In the box's order, a camera listed twice counted once.
    asked = list(
        dict.fromkeys(str(one) for one in (wanted.get("cameras") or []) if one)
    )
    if not asked:
        return JsonResponse({"error": "Tick at least one camera."}, status=400)
    if len(asked) > media.WALL_MOST:
        return JsonResponse({"error": "Up to nine cameras in one clip."}, status=400)
    layout = media.FOCUS if wanted.get("layout") == media.FOCUS else media.GRID
    if layout == media.FOCUS and len(asked) > media.FOCUS_MOST:
        return JsonResponse({"error": "Focus holds up to five cameras."}, status=400)

    known = {
        str(one.pk): one for one in incident.cameras.select_related("recording").all()
    }
    chosen = []
    for camera_id in asked:
        camera = known.get(camera_id)
        if camera is None:
            return JsonResponse(
                {"error": "That camera is not on this incident."}, status=400
            )
        playback = camera.recording.playback_path()
        if not camera.is_synced() or playback is None or not playback.exists():
            return JsonResponse(
                {"error": f"{camera.camera_id()} is not synced with a playback copy."},
                status=400,
            )
        if not (camera.starts_at < until_at and camera.ends_at() > from_at):
            return JsonResponse(
                {"error": f"{camera.camera_id()} is not running then."}, status=400
            )
        chosen.append(camera)

    sound = known.get(str(wanted.get("sound") or ""))
    if sound is None or sound not in chosen:
        return JsonResponse(
            {"error": "The sound must come from one of the clip's cameras."}, status=400
        )
    from core.viewer import being_replaced

    if being_replaced(sound.recording):
        # The Clips chapter's rule, which principle 4 makes this clip's too:
        # a locked Transcript takes no new Clip until Process again lands.
        return JsonResponse(
            {
                "error": (
                    f"{sound.camera_id()} is being transcribed again, so a new "
                    "clip cannot be saved until it lands."
                )
            },
            status=409,
        )

    picture = picture_for(
        incident,
        chosen,
        sound,
        layout,
        (from_at, until_at),
        burn_clock=wanted.get("burn_clock", True),
        burn_ids=wanted.get("burn_ids", True),
    )
    clip = Clip.objects.create(
        recording=sound.recording,
        user=request.user,
        title=(str(wanted.get("title") or "").strip() or event.text)[:120],
        # The span on the sound camera's own clock, unclamped: negative when
        # that camera starts inside the span, so the excerpt and the caption
        # file stay in step with the picture.
        start=from_at - float(sound.starts_at),
        end=until_at - float(sound.starts_at),
        burn_captions=False,
        include_excerpt=True,
        incident=incident,
        event=event,
        picture=picture,
    )
    clip_pages._record(
        request, clip, "Clip created", cameras=len(chosen), layout=layout
    )
    clip_pages._start_render(clip)
    # Making a Clip is use of the Case, as saving one on a recording is.
    cases.used(sound.recording, by=request.user)
    return JsonResponse(
        {
            "ok": True,
            "clip": clip_pages._row(clip, asker=request.user),
            "event_clips": Clip.objects.filter(event=event).count(),
            "said": "The clip is rendering; it is on the case's Clips tab.",
            "state": state_json(incident, request.user),
        }
    )
