"""The Interpreter's pages and calls (Phase 3, chapter 3).

The Session page, its Start, each Turn as it ends, and the rows the page
polls. Stop is the Record page's own /ended, since a Session is a Live
recording and ends as one.
"""

from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core import cases, interpreter, live, settings_store
from core.recordings import Recording

# A Turn's audio is seconds of Opus; a megabyte is minutes of it.
LONGEST_TURN_BYTES = 4 * 1024 * 1024


def _on_or_404() -> None:
    if not interpreter.on():
        raise Http404("the Interpreter is off")


def _their_session(request, recording_id) -> Recording:
    recording = get_object_or_404(Recording, pk=recording_id, user=request.user)
    if not recording.is_live or not interpreter.is_session(recording):
        raise Http404("not this person's session")
    return recording


def _body(request) -> dict:
    try:
        return json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return {}


@login_required
def session(request: HttpRequest) -> HttpResponse:
    """The Session page: the Visitor's language, then Start; two columns while
    it runs; the recording's page after."""
    _on_or_404()
    asked = request.GET.get("case", "")
    case = None
    if asked:
        case = cases.cases_for(request.user).filter(pk=asked).first()
        if case is None:
            raise Http404("no such case")
    offered = interpreter.languages_offered()
    return render(
        request,
        "interpret.html",
        {
            "page": "record",
            "chosen_case": str(case.pk) if case is not None else "",
            "case_name": case.name if case is not None else "",
            "languages": offered,
            "notice": interpreter.notice_lines(
                offered[0]["code"] if len(offered) == 1 else ""
            ),
            "phrases": interpreter.phrases(),
            "turn_taking": settings_store.get("interpreter_turn_taking") or "tap",
            "readback": bool(settings_store.get("interpreter_readback")),
            "longest": live.longest_seconds(),
            "csrf": request.META.get("CSRF_COOKIE", ""),
        },
    )


@login_required
@require_POST
def start(request: HttpRequest, *args) -> JsonResponse:
    _on_or_404()
    told = _body(request)
    case = None
    asked = str(told.get("case") or "")
    if asked:
        case = cases.cases_for(request.user).filter(pk=asked).first()
        if case is None:
            return JsonResponse(
                {"ok": False, "why": "That case is not yours."}, status=400
            )
    try:
        recording = interpreter.start(
            request.user,
            case,
            language=str(told.get("language") or ""),
            title=str(told.get("title") or ""),
            browser=request.headers.get("User-Agent", "")[:120],
            request=request,
        )
    except live.Refused as refusal:
        return JsonResponse({"ok": False, "why": str(refusal)}, status=400)
    return JsonResponse(
        {
            "ok": True,
            "id": str(recording.pk),
            "title": recording.title,
            "filename": recording.original_filename,
            "language": interpreter.visitor_language(recording),
            "language_name": interpreter.name_of(
                interpreter.visitor_language(recording)
            ),
            "notice": interpreter.notice_lines(interpreter.visitor_language(recording)),
            "after": (
                reverse("case", args=[case.pk]) if case is not None else reverse("home")
            ),
            "longest_seconds": live.longest_seconds(),
        }
    )


@login_required
@require_POST
def turn(request: HttpRequest, recording_id) -> JsonResponse:
    """A Turn has ended: its audio as a form field, or its words typed as JSON."""
    recording = _their_session(request, recording_id)
    if (recording.live or {}).get("ended"):
        return JsonResponse({"ok": False, "why": "The session has ended."}, status=400)
    if request.content_type and "json" in request.content_type:
        told = _body(request)
        typed = str(told.get("typed") or "").strip()
        if not typed:
            return JsonResponse({"ok": False, "why": "Nothing typed."}, status=400)
        made = interpreter.turn_arrived(
            recording,
            start_at=float(told.get("start") or 0),
            end_at=float(told.get("end") or 0),
            side=str(told.get("side") or ""),
            typed=typed,
        )
        return JsonResponse({"ok": True, "number": made.number})
    audio = request.FILES.get("audio")
    if audio is None or audio.size == 0:
        return JsonResponse({"ok": False, "why": "No sound arrived."}, status=400)
    if audio.size > LONGEST_TURN_BYTES:
        return JsonResponse({"ok": False, "why": "That turn is too long."}, status=400)
    try:
        start_at = float(request.POST.get("start") or 0)
        end_at = float(request.POST.get("end") or 0)
    except ValueError:
        start_at, end_at = 0.0, 0.0
    made = interpreter.turn_arrived(
        recording,
        start_at=start_at,
        end_at=end_at,
        side=str(request.POST.get("side") or ""),
        audio=audio.read(),
    )
    return JsonResponse({"ok": True, "number": made.number})


@login_required
def turns(request: HttpRequest, recording_id) -> JsonResponse:
    """The Turns after `since`, and any still changing, for the page's poll."""
    recording = _their_session(request, recording_id)
    try:
        since = int(request.GET.get("since") or 0)
    except ValueError:
        since = 0
    return JsonResponse(
        {
            "turns": interpreter.rows(recording, since),
            "language": interpreter.visitor_language(recording),
            "language_name": interpreter.name_of(
                interpreter.visitor_language(recording)
            ),
            "notice": interpreter.notice_lines(interpreter.visitor_language(recording)),
        }
    )
