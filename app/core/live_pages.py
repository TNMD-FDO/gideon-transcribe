"""The Record page and its calls (Phase 3, Live recording).

One page in three states: before (the case, the type, the title, the
language), during (the clock, the meter, Pause and Stop), and after (the
queue line until the Transcript is there). The browser records and uploads;
these views make the Recording, remember the upload, write down how it
ended, and answer where it stands.
"""

from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core import cases, live, uploads
from core.cases import Case
from core.recordings import Recording

LANGUAGES = [("", "Automatic"), ("es", "Spanish"), ("en", "English")]


def _on_or_404() -> None:
    if not live.on():
        raise Http404("Live recording is off")


def _their_live_recording(request, recording_id) -> Recording:
    """The Live recording this person is making; nobody else's, and no upload's."""
    recording = get_object_or_404(Recording, pk=recording_id, user=request.user)
    if not recording.is_live:
        raise Http404("not a live recording")
    return recording


def _body(request) -> dict:
    try:
        return json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return {}


@login_required
def record(request: HttpRequest) -> HttpResponse:
    """The Record page, before anything is recorded."""
    _on_or_404()
    choices = []
    for one in cases.cases_for(request.user):
        theirs = one.owner_id != request.user.pk
        choices.append(
            {
                "id": str(one.pk),
                "name": one.name,
                "shared_by": one.owner.shown_name if theirs else "",
                "room": uploads.as_gb(uploads.room_left(one.owner)) if theirs else "",
            }
        )
    asked = request.GET.get("case", "")
    chosen = asked if any(one["id"] == asked for one in choices) else ""
    return render(
        request,
        "record.html",
        {
            "page": "cases",
            "cases": choices,
            "chosen_case": chosen,
            "types": cases.recording_types(),
            "languages": LANGUAGES,
            "longest_seconds": live.longest_seconds(),
            "longest_minutes": live.longest_seconds() // 60,
        },
    )


@login_required
@require_POST
def start(request: HttpRequest) -> JsonResponse:
    """Record pressed: the Recording is made, and the browser may upload into it."""
    _on_or_404()
    wanted = _body(request)
    case = Case.objects.filter(
        pk=wanted.get("case") or None, deleted_on__isnull=True
    ).first()
    if case is None:
        return JsonResponse(
            {"ok": False, "why": "Choose a case to record into."}, status=400
        )
    try:
        recording = live.start(
            request.user,
            case,
            recording_type=str(wanted.get("recording_type") or ""),
            title=str(wanted.get("title") or ""),
            language=str(wanted.get("language") or ""),
            translate=bool(wanted.get("translate")),
            browser=request.headers.get("User-Agent", "")[:120],
            with_computer=bool(wanted.get("with_computer")),
            request=request,
        )
    except live.Refused as why:
        return JsonResponse({"ok": False, "why": str(why)}, status=400)
    return JsonResponse(
        {
            "ok": True,
            "id": str(recording.pk),
            "title": recording.title,
            "filename": recording.original_filename,
            "case": reverse("case", args=[case.pk]),
            "longest_seconds": live.longest_seconds(),
        }
    )


@login_required
@require_POST
def note_upload(request: HttpRequest, recording_id) -> JsonResponse:
    """The sidecar upload the pieces go into, so an early end can take them."""
    recording = _their_live_recording(request, recording_id)
    live.note_upload(recording, str(_body(request).get("tus") or ""))
    return JsonResponse({"ok": True})


@login_required
@require_POST
def ended(request: HttpRequest, recording_id) -> JsonResponse:
    """The recording ended: by Stop, the limit, or the page closing (a beacon).

    A beacon arrives as a form, with the CSRF token in it, because a beacon
    carries no headers of its own; Stop arrives as JSON.
    """
    recording = _their_live_recording(request, recording_id)
    if request.content_type and "json" in request.content_type:
        told = _body(request)
        pauses = told.get("pauses") or []
    else:
        told = request.POST
        try:
            pauses = json.loads(told.get("pauses") or "[]")
        except json.JSONDecodeError:
            pauses = []
    try:
        seconds = float(told.get("seconds") or 0) or None
    except (TypeError, ValueError):
        seconds = None
    try:
        computer_ended_at = float(told.get("computer_ended_at"))
    except (TypeError, ValueError):
        computer_ended_at = None
    live.ended(
        recording,
        how=str(told.get("how") or "closed"),
        pauses=pauses if isinstance(pauses, list) else [],
        seconds=seconds,
        computer_ended_at=computer_ended_at,
        request=request,
    )
    return JsonResponse({"ok": True})


@login_required
def state(request: HttpRequest, recording_id) -> JsonResponse:
    """Where the recording stands, for the page's after state and the Case row."""
    recording = _their_live_recording(request, recording_id)
    told = live.line_for(recording)
    told["viewer"] = (
        reverse("viewer", args=[recording.pk]) if told["state"] == "ready" else ""
    )
    told["case"] = (
        reverse("case", args=[recording.case_id]) if recording.case_id else ""
    )
    return JsonResponse(told)
