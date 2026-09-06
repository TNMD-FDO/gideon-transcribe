"""Recorded here on My recordings, and its calls (Phase 3, Dictation and the styles).

One tab, one door: everything the person recorded from it (dictations,
meetings in the room, calls on the computer), newest first, with what
colleagues have sent them under "Sent to you"; New recording; and, on each
row, Open, the memo or summary, Send to, Add to a case, Delete.
"""

from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from core import cases, dictation, exports, live, media_access, retention
from core.dictation import DictationShare
from core.recordings import Recording


def _on_or_404() -> None:
    if not dictation.on():
        raise Http404("Dictation is off")


def _my_dictation(request, recording_id) -> Recording:
    recording = get_object_or_404(Recording, pk=recording_id, is_dictation=True)
    if recording.user_id != request.user.pk:
        raise Http404("not this person's dictation")
    return recording


def _body(request) -> dict:
    try:
        return json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return {}


def _memo_state(recording) -> tuple[str, str]:
    """The Memo's state word and its id: none, queued, running, done, failed."""
    from core import assistant

    memo = dictation.memo_of(recording)
    if memo is None:
        return "none", ""
    if memo.state == assistant.QUEUED:
        return "queued", str(memo.pk)
    if memo.state == assistant.RUNNING:
        return "running", str(memo.pk)
    if memo.state == assistant.FAILED:
        return "failed", str(memo.pk)
    return ("done" if memo.text else "failed"), str(memo.pk)


def _style_name(recording: Recording) -> str:
    key = (recording.live or {}).get("style") or "dictation"
    return live.STYLES.get(key, live.STYLES["dictation"])["name"]


def _row(recording: Recording, viewer, mine: bool) -> dict:
    line = (
        live.line_for(recording)
        if recording.is_live
        else {"state": "ready", "says": ""}
    )
    memo_state, memo_id = _memo_state(recording)
    left = dictation.days_left(recording) if not recording.case_id else None
    playback = recording.playback_path() if recording.playback_ready else None
    return {
        "recording": recording,
        "line": line,
        "ready": hasattr(recording, "transcript"),
        # Play, to check it is the right recording before sending it on.
        "media_url": (
            f"{media_access.media_root(recording)}/{playback.name}" if playback else ""
        ),
        "length": exports.clock(recording.duration_seconds or 0),
        "memo_state": memo_state,
        "memo_id": memo_id,
        "sent_to": list(recording.dictation_shares.select_related("person"))
        if mine
        else [],
        "days_left": left,
        "warned": left is not None and retention.is_warned(left),
        "deletes_line": (
            retention.deletes_line(left).replace("unless used", "unless opened")
            if left is not None
            else ""
        ),
        "in_case": recording.case.name if recording.case_id else "",
        "mine": mine,
        "style": _style_name(recording),
        "product": dictation.product_of(recording),
    }


def tab_context(request) -> dict:
    """What "Recorded here" on the My recordings page needs."""
    mine = [_row(one, request.user, True) for one in dictation.mine(request.user)]
    received = [
        {**_row(share.recording, request.user, False), "share": share}
        for share in dictation.sent_to(request.user)
        if cases.reachable(share.recording)
    ]
    return {
        "mine": mine,
        "received": received,
        # The recording just made, marked on top so the person finds it.
        "new_id": request.GET.get("new", ""),
        "by_email": dictation.by_email(),
        "send_words": (
            dictation.SEND_WORDS_WITH_FILE
            if dictation.by_email()
            else dictation.SEND_WORDS
        ),
    }


@login_required
def record_tab(request: HttpRequest) -> HttpResponse:
    """The Record tab's old address: My recordings now, with Recorded here on it."""
    from django.shortcuts import redirect

    new = request.GET.get("new", "")
    return redirect(reverse("home") + (f"?new={new}" if new else ""))


@login_required
def dictate(request: HttpRequest) -> HttpResponse:
    """The old address of the Dictate page: the New recording page now."""
    from django.shortcuts import redirect

    return redirect(reverse("record-new"))


@login_required
def dictations(request: HttpRequest) -> HttpResponse:
    """The old address of the Dictations page: My recordings now."""
    from django.shortcuts import redirect

    return redirect(reverse("home"))


@login_required
def state(request: HttpRequest, recording_id) -> JsonResponse:
    """Where a Dictation and its Memo stand, for the page's rows."""
    _on_or_404()
    recording = get_object_or_404(Recording, pk=recording_id, is_dictation=True)
    if not cases.standing(recording, request.user):
        raise Http404("not this person's dictation")
    line = (
        live.line_for(recording)
        if recording.is_live
        else {"state": "ready", "says": ""}
    )
    memo_state, memo_id = _memo_state(recording)
    return JsonResponse(
        {
            **line,
            "memo": memo_state,
            "memo_id": memo_id,
            "viewer": reverse("viewer", args=[recording.pk]),
        }
    )


@login_required
@require_POST
def memo(request: HttpRequest, recording_id) -> JsonResponse:
    """Write the memo: one click."""
    _on_or_404()
    recording = _my_dictation(request, recording_id)
    try:
        summary = dictation.write_memo(recording, request.user, request=request)
    except dictation.Refused as why:
        return JsonResponse({"ok": False, "why": str(why)}, status=400)
    return JsonResponse({"ok": True, "memo_id": str(summary.pk)})


@login_required
def who(request: HttpRequest, recording_id) -> JsonResponse:
    _on_or_404()
    recording = _my_dictation(request, recording_id)
    return JsonResponse(
        {
            "people": [
                {"username": one.username, "name": one.shown_name}
                for one in dictation.candidates(recording)
            ]
        }
    )


@login_required
@require_POST
def send(request: HttpRequest, recording_id) -> JsonResponse:
    _on_or_404()
    recording = _my_dictation(request, recording_id)
    try:
        person = dictation.find(recording, str(_body(request).get("who") or ""))
        share = dictation.send(recording, person, request.user, request=request)
    except dictation.Refused as why:
        return JsonResponse({"ok": False, "why": str(why)}, status=400)
    return JsonResponse(
        {
            "ok": True,
            "share": {
                "id": share.pk,
                "name": person.shown_name,
                "attached": share.attached,
                "sent_on": share.sent_on.strftime("%d %b %Y"),
            },
        }
    )


@login_required
@require_POST
def take_back(request: HttpRequest, recording_id) -> JsonResponse:
    _on_or_404()
    recording = _my_dictation(request, recording_id)
    share = get_object_or_404(
        DictationShare,
        pk=request.POST.get("share") or _body(request).get("share"),
        recording=recording,
    )
    dictation.take_back(share, request.user, request=request)
    return JsonResponse({"ok": True})
