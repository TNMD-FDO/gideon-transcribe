"""The unit's voice book's pages (Phase 5 chapter 2, v1.146.0): the Voices
place on the rail, Forget, Check against the unit's voices on a card, and
Accept or Not them on its answer."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core import units, voice_book
from core.assistant_pages import _body, _recording
from core.voice_book import UnitVoice, UnitVoiceCheck


def _units_or_404(request) -> list[str]:
    if not voice_book.on():
        raise Http404("voices are not kept for the unit")
    seen = units.seen_by(request.user)
    if not seen:
        raise Http404("not in a unit")
    return seen


@login_required
def voices(request: HttpRequest) -> HttpResponse:
    """The Voices place: the unit's book, or every unit's for an Admin, one
    tab per unit."""
    seen = _units_or_404(request)
    wanted = request.GET.get("unit", "")
    unit = wanted if wanted in seen else seen[0]
    rows = voice_book.page_rows(unit, request.user)
    live = [one for one in rows if one["live"]]
    roles = voice_book.roles_allowed()
    counts = voice_book.counts_for_switch()
    return render(
        request,
        "voices.html",
        {
            "page": "voices",
            "unit": unit,
            "units": [{"name": one, "count": counts.get(one, 0)} for one in seen],
            "chooser": len(seen) > 1,
            "rows": rows,
            "live_count": len(live),
            "cases_count": len(
                {
                    share.get("case")
                    for one in live
                    for share in (one["book"].parts or {}).values()
                    if share.get("case")
                }
            ),
            "roles": roles,
            "decided": voice_book.decided_by_month(unit),
            "said": request.session.pop("voices_said", ""),
        },
    )


@login_required
@require_POST
def forget(request: HttpRequest, voice_id) -> HttpResponse:
    """Forget, the row's one action: the book's print goes; the names
    accepted from it and the cases' own prints stay."""
    seen = _units_or_404(request)
    book = get_object_or_404(UnitVoice, pk=voice_id, forgotten_at=None)
    if book.unit not in seen:
        raise Http404("not this person's unit")
    stopped = voice_book.forget(book, by=request.user, request=request)
    request.session["voices_said"] = (
        f"{book.name}'s voice is forgotten for the {book.unit} unit: "
        f"{stopped} case{'' if stopped == 1 else 's'} stopped keeping it. "
        "The names accepted from it stay, and so do the cases' own prints."
    )
    return redirect(reverse("voices") + f"?unit={book.unit}")


@login_required
@require_POST
def check(request: HttpRequest, recording_id) -> JsonResponse:
    """Check against the unit's voices, pressed on an unnamed card."""
    recording = _recording(request, recording_id)
    if recording is None:
        return JsonResponse({"error": "no such recording"}, status=404)
    label = (_body(request).get("speaker") or "").strip()
    try:
        answer = voice_book.check(recording, label, by=request.user, request=request)
    except ValueError as refused:
        return JsonResponse({"error": str(refused)}, status=400)
    return JsonResponse({"ok": True, "answer": answer})


@login_required
@require_POST
def decide(request: HttpRequest, check_id: int, verdict: str) -> JsonResponse:
    """Accept names the Speaker as the book's Person and teaches both
    prints; dismiss counts against the book's print."""
    row = get_object_or_404(
        UnitVoiceCheck.objects.select_related("transcript", "voice"),
        pk=check_id,
        state=UnitVoiceCheck.PENDING,
    )
    recording = _recording(request, row.transcript.recording_id)
    if recording is None:
        return JsonResponse({"error": "no such recording"}, status=404)
    if verdict == "accept":
        try:
            changed = voice_book.accept(row, by=request.user, request=request)
        except ValueError as refused:
            return JsonResponse({"error": str(refused)}, status=400)
        return JsonResponse(
            {
                "ok": True,
                "changed": changed,
                "made": row.voice.name if row.voice else "",
            }
        )
    voice_book.dismiss(row, by=request.user, request=request)
    return JsonResponse({"ok": True, "changed": 0})
