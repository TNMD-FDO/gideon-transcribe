"""The case's chronology's pages (Phase 10 chapter 1): the day's reading as
JSON for the case page's Notes tab and the Notes page, the running list, a
recording placed on or taken off the clock, To check on a note, and the
two exports."""

from __future__ import annotations

import datetime as dt
import json

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST

from core import audit, case_chronology, cases, exports, incidents, sitting
from core.case_pages import _on_or_404, _their_case
from core.recordings import Recording


def _date(text: str) -> dt.date | None:
    try:
        return dt.date.fromisoformat((text or "").strip())
    except ValueError:
        return None


def _seconds(text: str) -> float | None:
    """A time of day typed as hh:mm or hh:mm:ss, as seconds of the day."""
    parts = (text or "").strip().split(":")
    if len(parts) not in (2, 3) or not all(part.isdigit() for part in parts):
        return None
    hours, minutes = int(parts[0]), int(parts[1])
    seconds = int(parts[2]) if len(parts) == 3 else 0
    if hours > 23 or minutes > 59 or seconds > 59:
        return None
    return float(hours * 3600 + minutes * 60 + seconds)


def _span(request) -> tuple[float, float] | None:
    start = _seconds(request.GET.get("from", ""))
    end = _seconds(request.GET.get("to", ""))
    if start is None or end is None or end <= start:
        return None
    return start, end


@login_required
def day(request: HttpRequest, case_id) -> JsonResponse:
    """The Date strip and one day (the day asked for, else the newest with
    notes), with a span when the address names one."""
    _on_or_404()
    case = _their_case(request, case_id)
    days = case_chronology.days_of(case)
    asked = _date(request.GET.get("day", ""))
    if asked is None and days:
        asked = dt.date.fromisoformat(days[-1]["date"])
    reading = case_chronology.day_of(case, asked, _span(request)) if asked else None
    return JsonResponse(
        {
            "days": days,
            "day": reading,
            "me": request.user.pk,
            "may_place": True,
            "fold_notes": case_chronology.FOLD_NOTES,
            "bars_most": case_chronology.BARS_MOST,
        }
    )


@login_required
def running(request: HttpRequest, case_id) -> JsonResponse:
    """The recordings running at a moment of a day: the Coverage lane's press."""
    _on_or_404()
    case = _their_case(request, case_id)
    when = _date(request.GET.get("day", ""))
    at = _seconds(request.GET.get("at", ""))
    if when is None or at is None:
        raise Http404
    return JsonResponse({"rows": case_chronology.running_at(case, when, at)})


def _span_asked(request, body=None) -> tuple:
    """The day and the span, from the address or a JSON body; 404 without."""
    source = body if body is not None else request.GET
    when = _date(str(source.get("day", "")))
    start = _seconds(str(source.get("from", "")))
    end = _seconds(str(source.get("to", "")))
    if when is None or start is None or end is None or end <= start:
        raise Http404
    return when, (start, end)


@login_required
def span(request: HttpRequest, case_id) -> JsonResponse:
    """The Make an incident sheet's reading of a span (chapter 2)."""
    _on_or_404()
    if not incidents.on():
        raise Http404
    case = _their_case(request, case_id)
    when, asked = _span_asked(request)
    return JsonResponse(case_chronology.span_reading(case, when, asked))


@login_required
def span_sitting(request: HttpRequest, case_id) -> JsonResponse:
    """The sitting bar for the recordings ticked in the sheet, redrawn on
    each tick (Phase 8 chapter 10's bar for an incident not yet made)."""
    _on_or_404()
    case = _their_case(request, case_id)
    wanted = [one for one in request.GET.get("recordings", "").split(",") if one]
    chosen = list(case.recordings.filter(pk__in=wanted))
    return JsonResponse({"sitting": sitting.json_for_recordings(chosen)})


def _body(request) -> dict:
    try:
        return json.loads(request.body or b"{}")
    except ValueError:
        return {}


@login_required
@require_POST
def make_incident(request: HttpRequest, case_id) -> JsonResponse:
    """Make the incident: the span's recordings ticked, named, opened."""
    _on_or_404()
    if not incidents.on():
        raise Http404
    case = _their_case(request, case_id)
    body = _body(request)
    when, asked = _span_asked(request, body)
    wanted = [str(one) for one in (body.get("recordings") or [])]
    chosen = list(case.recordings.filter(pk__in=wanted).order_by("created"))
    if not chosen:
        return JsonResponse({"error": "Tick at least one recording."}, status=400)
    name = str(body.get("name", "") or "").strip()
    incident = case_chronology.make_incident(
        case, when, asked, name, chosen, by=request.user, request=request
    )
    return JsonResponse({"ok": True, "url": incident.url(), "id": str(incident.pk)})


@login_required
@require_POST
def add_to_incident(request: HttpRequest, case_id, incident_id) -> JsonResponse:
    """Add the span's recordings to the incident it touches, widening it."""
    _on_or_404()
    if not incidents.on():
        raise Http404
    case = _their_case(request, case_id)
    incident = incidents.Incident.objects.filter(pk=incident_id, case=case).first()
    if incident is None:
        raise Http404
    body = _body(request)
    when, asked = _span_asked(request, body)
    wanted = [str(one) for one in (body.get("recordings") or [])]
    chosen = list(case.recordings.filter(pk__in=wanted).order_by("created"))
    added = case_chronology.add_to_incident(
        incident, when, asked, chosen, by=request.user, request=request
    )
    return JsonResponse({"ok": True, "url": incident.url(), "added": added})


def _their_recording(request, recording_id) -> Recording:
    recording = (
        Recording.objects.filter(pk=recording_id)
        .select_related("case", "case__owner", "user")
        .first()
    )
    if recording is None or not cases.standing(recording, request.user):
        raise Http404("not this person's recording")
    return recording


@login_required
@require_POST
def place(request: HttpRequest, recording_id) -> JsonResponse:
    """A person places the recording on the clock: a date with a time, or
    the day alone, or the file's time taken."""
    _on_or_404()
    recording = _their_recording(request, recording_id)
    try:
        body = json.loads(request.body or b"{}")
    except ValueError:
        body = {}
    when = _date(str(body.get("date", "")))
    if when is None:
        return JsonResponse({"error": "A date is needed."}, status=400)
    how = str(body.get("how", "") or "")
    start = None
    if how != case_chronology.DAY and not body.get("day_alone"):
        start = _seconds(str(body.get("start", "")))
        if start is None and how != case_chronology.FILE:
            return JsonResponse(
                {"error": "A time as hh:mm, or tick the day alone."}, status=400
            )
        if how == case_chronology.FILE:
            offered = case_chronology.file_suggestion(recording)
            if offered is None:
                return JsonResponse({"error": "The file carries no time."}, status=400)
            start = offered["seconds"]
    try:
        case_chronology.place(
            recording,
            when,
            start,
            by=request.user,
            request=request,
            how=how if how in (case_chronology.HAND, case_chronology.FILE) else "",
        )
    except ValueError as refused:
        return JsonResponse({"error": str(refused)}, status=400)
    if recording.case_id:
        cases.note_activity(recording.case, by=request.user)
    return JsonResponse({"ok": True, "placed": case_chronology.placed_words(recording)})


@login_required
@require_POST
def unplace(request: HttpRequest, recording_id) -> JsonResponse:
    _on_or_404()
    recording = _their_recording(request, recording_id)
    done = case_chronology.unplace(recording, by=request.user, request=request)
    return JsonResponse({"ok": done})


@login_required
@require_POST
def to_check(request: HttpRequest, recording_id) -> JsonResponse:
    """To check on a note of this recording, pressed on or off."""
    _on_or_404()
    recording = _their_recording(request, recording_id)
    try:
        body = json.loads(request.body or b"{}")
    except ValueError:
        body = {}
    kind = str(body.get("kind", ""))
    note_id = body.get("id")
    wanted = bool(body.get("wanted"))
    if kind == "line":
        owned = (
            recording.transcript.segments.filter(pk=note_id).exists()
            if hasattr(recording, "transcript")
            else False
        )
    elif kind == "moment":
        owned = recording.moment_notes.filter(pk=note_id).exists()
    else:
        owned = False
    if not owned:
        raise Http404
    case_chronology.set_to_check(kind, note_id, wanted)
    audit.write(
        audit.Category.EDITS,
        "note marked to check" if wanted else "note to check cleared",
        actor=request.user,
        request=request,
        affected_user=recording.user,
        object_type="recording",
        object_id=str(recording.pk),
        object_label=recording.title,
    )
    return JsonResponse({"ok": True, "to_check": wanted})


@login_required
def export(request: HttpRequest, case_id, kind: str) -> HttpResponse:
    """Chronology to Word, or as a spreadsheet, for one day or every day."""
    _on_or_404()
    case = _their_case(request, case_id)
    when = _date(request.GET.get("day", ""))
    if kind == "docx":
        body = case_chronology.word(case, when, request.user.shown_name)
        content_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    elif kind == "csv":
        body = case_chronology.spreadsheet(case, when)
        content_type = "text/csv; charset=utf-8"
    else:
        raise Http404
    case_chronology.record_export(request, case, kind, when)
    cases.note_activity(case, by=request.user)
    return exports.hand_over(
        body, case_chronology.export_name(case, when, kind), content_type
    )
