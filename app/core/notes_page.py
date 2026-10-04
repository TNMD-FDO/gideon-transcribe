"""The Notes page (Phase 9 chapter 4): the Case's work page for its notes.

The incident page's shape without the wall: on the left one recording at
one moment (the Preview, mounted into the page rather than floating), with
the note under its line and Previous and Next; on the right the work panel
(Notes grouped by recording in call order, Recordings, Details, a Find box).
The Note is the spine, as the Event is on an incident. Open the call opens
the whole recording in a pop-out over the page, never a jump away.

Everything the right panel draws comes from one reading of the case,
`list_json`, in a handful of queries whatever the count (a case of 800
calls and 1,200 notes is the design point); the page keeps it and draws.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from core import (
    assignments,
    case_chat,
    case_search,
    cases,
    documents,
    engine,
    exports,
    home,
    incidents,
    notes,
    sharing,
    vocabulary,
)
from core.assistant import DONE, Summary
from core.case_pages import _on_or_404, _sharing_context, _their_case
from core.jobs import Segment
from core.notes import MomentNote

LINES_MOST = 20000


@login_required
def page(request: HttpRequest, case_id) -> HttpResponse:
    _on_or_404()
    case = _their_case(request, case_id)
    cases.note_activity(case, by=request.user)
    role = case.role_of(request.user)
    if role == "collaborator":
        sharing.note_opened(case, request.user)
    chat_here = case_chat.available()
    return render(
        request,
        "notes-page.html",
        {
            "page": "cases",
            "case": case,
            "role": role,
            "here_case": home.here_case_for(request.user, case),
            "list_url": reverse("notes-page-list", args=[case.pk]),
            "find_url": reverse("notes-page-find", args=[case.pk]),
            "notes_url": reverse("case-notes", args=[case.pk]),
            "csv_url": reverse("case-list", args=[case.pk]),
            # ?note=line:<id> or moment:<id> opens on that note.
            "opening": request.GET.get("note", "")[:40],
            "case_chat_available": chat_here,
            "gideon_on": bool(chat_here and engine.is_reachable()),
            "gideon_why": (
                "" if engine.is_reachable() else engine.WHAT_TO_SAY[engine.UNREACHABLE]
            ),
            "vocabulary": vocabulary.entries(case),
            "may_remove_terms": role != "collaborator",
            "documents_on": documents.on(),
            **_sharing_context(case, role, request.user),
            **_facts(case),
        },
    )


def _facts(case) -> dict:
    """The Details tab's figures."""
    rows = case.recordings
    total = rows.count()
    seconds = sum(
        float(one or 0) for one in rows.values_list("duration_seconds", flat=True)
    )
    summarised = (
        Summary.objects.filter(recording__case=case, state=DONE)
        .values("recording_id")
        .distinct()
        .count()
    )
    return {
        "facts": {
            "recordings": total,
            "hours": f"{seconds / 3600:.1f}",
            "summarised": summarised,
            "notes": notes.count(case),
            "size": exports.as_size(case.disk_bytes())
            if hasattr(exports, "as_size")
            else "",
        }
    }


@login_required
def list_json(request: HttpRequest, case_id) -> JsonResponse:
    """Everything the right panel draws: the recordings in call order with
    their facts, every note on a line or at a moment, the writers and the
    types with their counts."""
    _on_or_404()
    case = _their_case(request, case_id)
    recordings = list(
        case.recordings.select_related("assigned_to", "reviewed_by").order_by(
            "created", "title"
        )
    )
    names = assignments.names_for(case)
    ids = [one.pk for one in recordings]
    summarised = set(
        Summary.objects.filter(recording_id__in=ids, state=DONE).values_list(
            "recording_id", flat=True
        )
    )
    with_words = set(
        Segment.objects.filter(transcript__recording_id__in=ids)
        .values_list("transcript__recording_id", flat=True)
        .distinct()
    )
    note_rows = []
    writers: dict = {}
    for one in (
        Segment.objects.filter(
            transcript__recording_id__in=ids, same_as_other_side=False
        )
        .exclude(note="")
        .select_related("transcript", "note_by")
        .order_by("start")[:LINES_MOST]
    ):
        note_rows.append(
            {
                "key": f"line:{one.pk}",
                "kind": "line",
                "id": one.pk,
                "recording": str(one.transcript.recording_id),
                "at": float(one.start),
                "clock": exports.clock(one.start),
                "text": one.note,
                "said": one.text,
                "who": one.speaker,
                "by": one.note_by.shown_name if one.note_by else "",
                "by_id": one.note_by_id,
                "when": notes.date_of(one.note_changed),
                "changed": one.note_changed.isoformat() if one.note_changed else "",
            }
        )
    for one in (
        MomentNote.objects.filter(recording_id__in=ids)
        .select_related("note_by")
        .order_by("at")[:LINES_MOST]
    ):
        note_rows.append(
            {
                "key": f"moment:{one.pk}",
                "kind": "moment",
                "id": one.pk,
                "recording": str(one.recording_id),
                "at": float(one.at),
                "clock": exports.clock(one.at),
                "text": one.note,
                "said": "",
                "who": "",
                "by": one.note_by.shown_name if one.note_by else "",
                "by_id": one.note_by_id,
                "when": notes.date_of(one.note_changed),
                "changed": one.note_changed.isoformat() if one.note_changed else "",
            }
        )
    note_rows.extend(_event_rows(case, recordings))
    order = {str(one.pk): index for index, one in enumerate(recordings)}
    note_rows.sort(key=lambda row: (order.get(row["recording"], 0), row["at"]))
    counts: dict = {}
    for row in note_rows:
        here = counts.setdefault(row["recording"], {"count": 0, "writers": []})
        here["count"] += 1
        if row["by"] and row["by"] not in here["writers"]:
            here["writers"].append(row["by"])
        if row["by_id"]:
            writers.setdefault(
                row["by_id"], {"id": row["by_id"], "name": row["by"], "count": 0}
            )
            writers[row["by_id"]]["count"] += 1
    types: dict = {}
    rows = []
    for one in recordings:
        kind = one.recording_type or ""
        if kind:
            types[kind] = types.get(kind, 0) + 1
        found = counts.get(str(one.pk), {"count": 0, "writers": []})
        rows.append(
            {
                "id": str(one.pk),
                "title": exports.title_of(one),
                "type": kind,
                "date": f"{timezone.localtime(one.created):%a %d %b %Y, %H:%M}",
                "length": exports.clock(one.duration_seconds or 0)
                if one.duration_seconds
                else "",
                "seconds": float(one.duration_seconds or 0),
                "summarised": one.pk in summarised,
                "words": one.pk in with_words,
                "assigned": (
                    names.get(one.assigned_to_id, one.assigned_to.shown_name)
                    if one.assigned_to_id
                    else ""
                ),
                "assigned_id": one.assigned_to_id,
                "reviewed": assignments.reviewed_words(one, request.user),
                "notes": found["count"],
                "writers": found["writers"],
                "open": reverse("viewer", args=[one.pk]),
            }
        )
    kinds: dict = {}
    for row in note_rows:
        kinds[row["kind"]] = kinds.get(row["kind"], 0) + 1
    return JsonResponse(
        {
            "recordings": rows,
            "notes": note_rows,
            # How many of each kind, and how many recordings carry a note,
            # for the lead line (v1.121.1).
            "kinds": kinds,
            "noted": len([one for one in rows if one["notes"]]),
            "writers": sorted(
                writers.values(), key=lambda one: (-one["count"], one["name"])
            ),
            "types": [{"name": name, "count": n} for name, n in sorted(types.items())],
            "no_note": len([one for one in rows if not one["notes"]]),
            "me": request.user.pk,
            "may_direct": case.may_direct(request.user),
        }
    )


def _event_rows(case, recordings) -> list[dict]:
    """The notes on an incident's events (v1.121.1, from the walk): each
    listed under the camera the event sits on, at the event's moment by that
    camera's own clock, read-only on the page since the chronology owns it,
    with the event's time of day and a link to the event. A note event that
    is a line's or a moment's note is already listed as that."""
    if not incidents.on():
        return []
    from core.chronology import Event
    from core.incidents import IncidentCamera

    known = {str(one.pk) for one in recordings}
    found = (
        Event.objects.filter(
            incident__case=case,
            proposed=False,
            segment__isnull=True,
            moment_note__isnull=True,
        )
        .exclude(note="")
        .select_related("incident", "camera", "note_by")
    )
    cameras: dict = {}
    rows = []
    for event in found:
        incident = event.incident
        if incident.pk not in cameras:
            cameras[incident.pk] = [
                one
                for one in IncidentCamera.objects.filter(
                    incident=incident, starts_at__isnull=False
                ).select_related("recording")
            ]
        camera = (
            event.camera
            if event.camera and event.camera.starts_at is not None
            else None
        )
        if camera is None:
            # The first placed camera that was running at the event's moment.
            for one in cameras[incident.pk]:
                length = float(one.recording.duration_seconds or 0)
                if one.starts_at <= event.at <= one.starts_at + length:
                    camera = one
                    break
        if camera is None or str(camera.recording_id) not in known:
            continue
        seconds = max(0.0, float(event.at) - float(camera.starts_at))
        rows.append(
            {
                "key": f"event:{event.pk}",
                "kind": "event",
                "id": str(event.pk),
                "recording": str(camera.recording_id),
                "at": seconds,
                "clock": exports.clock(seconds),
                "text": event.note,
                "said": event.text,
                "who": "",
                "by": event.note_by.shown_name if event.note_by else "",
                "by_id": event.note_by_id,
                "when": notes.date_of(event.note_changed),
                "changed": event.note_changed.isoformat() if event.note_changed else "",
                "event_clock": incidents.time_of_day(incident, event.at),
                "event_url": f"{incident.url()}?t={event.at:.2f}",
                "readonly": True,
            }
        )
    return rows


@login_required
def find(request: HttpRequest, case_id) -> JsonResponse:
    """The Find box: the case's notes and the recordings' words. Never logged."""
    _on_or_404()
    case = _their_case(request, case_id)
    return JsonResponse(case_search.find_notes(case, request.GET.get("q", "")[:200]))
