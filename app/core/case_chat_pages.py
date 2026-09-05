"""The Chat tab of a Case page: its state, and what a person does there.

Mirrors the viewer's Chat endpoints, keyed to the Case instead of a Recording:
one state answer the tab polls every two seconds while a question runs, New
chat, Ask, Delete, and Export to Word. Hidden while Folder management is Off,
and while the AI assistant or Chat across cases is Off.
"""

from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from core import (
    assistant,
    audit,
    case_chat,
    cases,
    engine,
    exports,
    settings_store,
    tasks,
)
from core.assistant import Chat
from core.case_chat import CaseChat, CaseChatTurn
from core.case_pages import _on_or_404, _their_case
from core.cases import Case
from core.recordings import Recording


def _the_case(request, case_id, *, opening: bool = False):
    """The Case, if this person may open it and the tab exists.

    The Case page's own gate writes the ADR 0004 row when an Admin opens
    somebody else's Case; the tab's polling must not write one every two
    seconds, so only an act that opens a Chat (`opening`) records again.
    """
    _on_or_404()
    if not case_chat.available():
        raise Http404("Chat across cases is off")
    if opening:
        return _their_case(request, case_id)
    case = get_object_or_404(Case, pk=case_id, deleted_on__isnull=True)
    if not case.may_be_opened_by(request.user):
        raise Http404("not this person's case")
    return case


def _body(request) -> dict:
    try:
        return json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return {}


def _turn_json(turn: CaseChatTurn, still_here: dict) -> dict:
    """One turn as the tab draws it, its Citations resolved to links or not."""
    cited = {}
    for text, where in (turn.citations or {}).items():
        recording = still_here.get(where["recording"])
        if recording is None:
            cited[text] = {"removed": True}
            continue
        cited[text] = {
            "title": exports.title_of(recording),
            "clock": exports.clock(where["seconds"]),
            "href": f"{reverse('viewer', args=[recording.pk])}?t={where['seconds']}",
            # The line it points to, for the pill's hover; never logged.
            "line": _line_at(recording, where["seconds"]),
        }
    running = turn.state in (assistant.QUEUED, assistant.RUNNING)
    count = len(turn.readings or [])
    if running and turn.parts:
        reading = (
            f"Reading {count} transcripts in {turn.parts} parts. "
            "This takes a few minutes."
        )
    elif running and count:
        reading = f"Reading {count} transcript{'' if count == 1 else 's'}..."
    else:
        reading = "Reading the case..."
    return {
        "id": str(turn.pk),
        "number": turn.number,
        "question": turn.question,
        "answer": turn.answer,
        "citations": cited,
        "state": turn.state,
        "reading": reading if running else "",
        "said": case_chat.what_to_say(turn) if turn.state == assistant.FAILED else "",
        "cut_short": turn.cut_short,
        "parts": turn.parts,
        "parts_done": turn.parts_done,
        "asked_at": turn.asked_at.isoformat() if turn.asked_at else "",
        "answered_at": turn.answered_at.isoformat() if turn.answered_at else "",
    }


def _line_at(recording, seconds: float) -> str:
    from core.jobs import Segment

    segment = (
        Segment.objects.filter(
            transcript__recording=recording,
            start__gte=int(seconds),
            start__lt=int(seconds) + 1,
        )
        .order_by("start")
        .first()
    )
    if segment is None:
        return ""
    who = f"{segment.speaker}: " if segment.speaker else ""
    return (who + segment.text)[:200]


def _earlier_line(chat: CaseChat, still_here: dict) -> str:
    """Process again on a Recording since an answer used its Transcript."""
    replaced = []
    for turn in chat.turns.filter(state=assistant.DONE):
        for one in turn.readings or []:
            recording = still_here.get(one["recording"])
            transcript = getattr(recording, "transcript", None) if recording else None
            if (
                transcript is not None
                and transcript.created.isoformat() > one["transcript_created"]
                and one["title"] not in replaced
            ):
                replaced.append(one["title"])
    if not replaced:
        return ""
    return (
        f"Earlier answers used a previous transcript of {', '.join(replaced)}; "
        "new questions use the current one."
    )


def _chat_json(chat: CaseChat, still_here: dict) -> dict:
    turns = list(chat.turns.all())
    first_model = next((one.model for one in turns if one.model), "")
    first_when = next((one.answered_at for one in turns if one.answered_at), None)
    return {
        "id": str(chat.pk),
        "name": chat.name or "New chat",
        "started": chat.created.isoformat(),
        "busy": any(
            one.state in (assistant.QUEUED, assistant.RUNNING) for one in turns
        ),
        "notice": assistant.notice(first_model, first_when) if first_when else "",
        "earlier": _earlier_line(chat, still_here),
        "turns": [_turn_json(one, still_here) for one in turns],
    }


@login_required
def state(request: HttpRequest, case_id) -> JsonResponse:
    case = _the_case(request, case_id)
    still_here = {str(one.pk): one for one in Recording.objects.filter(case=case)}
    chats = [_chat_json(one, still_here) for one in case.chats.all()]
    read, skipped = case_chat.readable(case)
    return JsonResponse(
        {
            "reachable": engine.is_reachable(),
            "unavailable_line": engine.WHAT_TO_SAY[engine.UNREACHABLE],
            "busy": any(one["busy"] for one in chats),
            "readable": len(read),
            "skipped": len(skipped),
            "starters": settings_store.lines_of("case_chat_starters"),
            "chats": chats,
        }
    )


@login_required
@require_POST
def new_chat(request: HttpRequest, case_id) -> JsonResponse:
    case = _the_case(request, case_id)
    chat = CaseChat.objects.create(case=case, asked_by=request.user)
    cases.note_activity(case, by=request.user)
    return JsonResponse({"id": str(chat.pk)})


@login_required
@require_POST
def ask(request: HttpRequest, chat_id) -> JsonResponse:
    chat = get_object_or_404(CaseChat, pk=chat_id)
    case = _the_case(request, chat.case_id, opening=True)
    question = str(_body(request).get("question", "")).strip()
    if not question:
        return JsonResponse({"error": "ask something"}, status=400)
    if chat.turns.filter(state__in=(assistant.QUEUED, assistant.RUNNING)).exists():
        return JsonResponse(
            {"error": "the last question is still being answered"}, status=409
        )
    read, _ = case_chat.readable(case)
    if not read:
        return JsonResponse(
            {"error": "no recording in this case has a transcript yet"}, status=409
        )
    cases.note_activity(case, by=request.user)
    if not chat.name:
        chat.name = Chat.name_from(question)
        chat.save(update_fields=["name"])
    turn = CaseChatTurn.objects.create(
        chat=chat, number=chat.turns.count() + 1, question=question[:4000]
    )
    tasks.answer_case_turn.defer(turn_id=str(turn.pk))
    return JsonResponse({"id": str(turn.pk)})


@login_required
@require_POST
def delete_chat(request: HttpRequest, chat_id) -> JsonResponse:
    chat = get_object_or_404(CaseChat, pk=chat_id)
    case = _the_case(request, chat.case_id)
    chat.delete()
    # Deleting a Case Chat is not Last activity, and the row carries no words.
    audit.write(
        audit.Category.EDITS,
        "Chat deleted",
        actor=request.user,
        request=request,
        affected_user=case.owner if case.owner_id != request.user.pk else None,
        object_type="case",
        object_id=case.pk,
        object_label=case.name,
        kind="case chat",
    )
    return JsonResponse({"ok": True})


@login_required
def export(request: HttpRequest, chat_id) -> HttpResponse:
    chat = get_object_or_404(CaseChat, pk=chat_id)
    case = _the_case(request, chat.case_id, opening=True)
    cases.note_activity(case, by=request.user)
    audit.write(
        audit.Category.EXPORTS,
        "export made",
        actor=request.user,
        request=request,
        affected_user=case.owner if case.owner_id != request.user.pk else None,
        object_type="case",
        object_id=case.pk,
        object_label=case.name,
        kind="case chat",
    )
    answer = HttpResponse(
        exports.case_chat_word(chat, request.user.username),
        content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )
    answer["Content-Disposition"] = (
        f'attachment; filename="{exports.case_chat_name(chat)}"'
    )
    return answer
