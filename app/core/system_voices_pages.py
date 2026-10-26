"""The phone system's voice's pages (v1.159.0; Phase 5 chapter 2, "The
phone system's voice"): the Phone systems tab of the Voices place, its
Admin actions (rename, start or stop the giving, forget), and the guided
page's way back for a line given by voice."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core import system_voices, units, voice_book
from core.assistant_pages import _body, _recording
from core.system_voices import SystemVoice


def _place_or_404(request) -> list[str]:
    """The tab sits on the Voices place, so it needs the place: the book on
    and the reader in a unit (an Admin in every one)."""
    if not voice_book.on():
        raise Http404("voices are not kept for the unit")
    seen = units.seen_by(request.user)
    if not seen:
        raise Http404("not in a unit")
    return seen


def _admin_or_404(request) -> None:
    if not getattr(request.user, "is_admin", False):
        raise Http404("an Admin's action")


def tab_counts() -> dict:
    """The chip's count and whether the tab is there at all."""
    if not system_voices.on():
        return {"shown": False, "count": 0}
    return {"shown": True, "count": SystemVoice.objects.count()}


@login_required
def systems(request: HttpRequest) -> HttpResponse:
    seen = _place_or_404(request)
    if not system_voices.on():
        raise Http404("the Call system is off")
    rows = system_voices.rows_for(request.user)
    totals = {"calls": 0, "words": 0, "would": 0, "given": 0, "held": 0, "back": 0}
    for row in rows:
        for key in totals:
            totals[key] += row["month"][key]
    return render(
        request,
        "voices-systems.html",
        {
            "page": "voices",
            "units": [
                {"name": one, "count": voice_book.counts_for_switch().get(one, 0)}
                for one in seen
            ],
            "chooser": len(seen) > 1,
            "systems": tab_counts(),
            "rows": rows,
            "month": totals,
            "is_admin": bool(getattr(request.user, "is_admin", False)),
            "back_to_stop": system_voices.BACK_TO_STOP,
            "said": request.session.pop("voices_said", ""),
        },
    )


@login_required
@require_POST
def act(request: HttpRequest, voice_id, action: str) -> HttpResponse:
    """Rename, start or stop the giving, forget: an Admin's acts."""
    _place_or_404(request)
    _admin_or_404(request)
    voice = get_object_or_404(SystemVoice, pk=voice_id)
    try:
        if action == "rename":
            system_voices.rename(
                voice, request.POST.get("name", ""), by=request.user, request=request
            )
            request.session["voices_said"] = (
                f"The phone system is now called {voice.name}."
            )
        elif action == "giving":
            giving = request.POST.get("giving") == "1"
            system_voices.set_giving(voice, giving, by=request.user, request=request)
            request.session["voices_said"] = (
                f"{voice.name} now gives the Call system the lines its voice finds, "
                "under the guards; each carries Not the system on the Speakers page."
                if giving
                else f"{voice.name} is back to counting: its voice moves nothing until "
                "you start it again."
            )
        elif action == "forget":
            name = voice.name
            system_voices.forget(voice, by=request.user, request=request)
            request.session["voices_said"] = (
                f"{name}'s print is forgotten. The next jail call makes it again, "
                "counting, not moving. The Call system's lines on every transcript "
                "stay as they are."
            )
        else:
            raise Http404("no such action")
    except ValueError as refused:
        request.session["voices_said"] = str(refused)
    return redirect(reverse("voices-systems"))


@login_required
@require_POST
def line(request: HttpRequest, recording_id, verdict: str) -> JsonResponse:
    """Not the system (back), or the system after all (again), on one line
    of the guided page."""
    recording = _recording(request, recording_id)
    if recording is None:
        return JsonResponse({"error": "no such recording"}, status=404)
    transcript = recording.transcript
    if transcript is None:
        return JsonResponse({"error": "no transcript"}, status=404)
    try:
        segment = int(_body(request).get("segment") or 0)
        if verdict == "back":
            was = system_voices.give_back(
                transcript, segment, by=request.user, request=request
            )
            return JsonResponse({"ok": True, "was": was})
        if verdict == "again":
            system_voices.give_again(
                transcript, segment, by=request.user, request=request
            )
            return JsonResponse({"ok": True})
    except ValueError as refused:
        return JsonResponse({"error": str(refused)}, status=400)
    return JsonResponse({"error": "no such verdict"}, status=404)
