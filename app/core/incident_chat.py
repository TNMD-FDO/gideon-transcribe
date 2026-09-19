"""Gideon on the incident page (Phase 7 chapter 5): a conversation grounded
in the incident record (the cameras' Digests merged onto the Incident clock)
and the Chronology with its notes and About, and nothing else. Every time in
an answer is a citation on the Incident clock that plays every camera. The
conversations are the Case Chat's rows with the Incident set; the shape on
the page is the shared chat's.
"""

from __future__ import annotations

import time

from django.utils import timezone

from core import assistant, engine, incidents, prompts, settings_store
from core.assistant import DONE, FAILED, QUEUED, RUNNING, PromptTemplate
from core.case_chat import CaseChat, CaseChatTurn

FEATURE = "incident_chat"


def on() -> bool:
    return bool(
        incidents.on()
        and settings_store.get("assistant_available")
        and settings_store.get("incidents_chat")
    )


def readable(incident) -> bool:
    """Whether some synced camera has a transcript to answer from."""
    from core.incident_assistant import synced_cameras

    return any(hasattr(one.recording, "transcript") for one in synced_cameras(incident))


def new_chat(incident, *, by) -> CaseChat:
    return CaseChat.objects.create(case=incident.case, incident=incident, asked_by=by)


def _citations_json(incident, citations: dict) -> dict:
    """The page's citations: the time of day, the seconds on the clock, and
    the incident page at that moment."""
    out = {}
    for whole, at in (citations or {}).items():
        out[whole] = {
            "clock": incidents.time_of_day(incident, float(at)),
            "seconds": float(at),
            "href": f"{incident.url()}?t={float(at):.2f}",
        }
    return out


def _turn_json(incident, turn: CaseChatTurn) -> dict:
    from core import case_chat

    running = turn.state in (QUEUED, RUNNING)
    return {
        "id": str(turn.pk),
        "number": turn.number,
        "question": turn.question,
        "answer": turn.answer,
        "citations": _citations_json(incident, turn.citations),
        "state": turn.state,
        "reading": "Reading the incident record..." if running else "",
        "said": case_chat.what_to_say(turn) if turn.state == FAILED else "",
        "cut_short": turn.cut_short,
        "parts": 0,
        "parts_done": 0,
        "asked_at": turn.asked_at.isoformat() if turn.asked_at else "",
        "answered_at": turn.answered_at.isoformat() if turn.answered_at else "",
    }


def _chat_json(incident, chat: CaseChat) -> dict:
    turns = list(chat.turns.all())
    first = next((one for one in turns if one.state == DONE), None)
    return {
        "id": str(chat.pk),
        "name": chat.name or "New chat",
        "started": chat.created.isoformat(),
        "busy": any(one.state in (QUEUED, RUNNING) for one in turns),
        "notice": (
            assistant.notice(first.model, first.answered_at)
            if first is not None and first.answered_at
            else ""
        ),
        "earlier": "",
        "turns": [_turn_json(incident, one) for one in turns],
    }


def state_json(incident) -> dict:
    """What the drawer asks for every few seconds."""
    from core.incident_assistant import synced_cameras

    cameras = [
        one for one in synced_cameras(incident) if hasattr(one.recording, "transcript")
    ]
    left_out = [
        one.camera_id()
        for one in incident.cameras.select_related("recording")
        if not one.is_synced()
    ]
    chats = [_chat_json(incident, one) for one in incident.chats.all()]
    return {
        "reachable": engine.is_reachable(),
        "unavailable_line": engine.WHAT_TO_SAY[engine.UNREACHABLE],
        "busy": any(one["busy"] for one in chats),
        "readable": len(cameras),
        "left_out": left_out,
        "starters": settings_store.lines_of("case_chat_starters"),
        "chats": chats,
        "url": incident.url(),
    }


def answer_incident_turn(turn_id, attempt: int = 1) -> None:
    """One question: the record and the chronology in, the answer out, its
    citations checked against the incident's span, one audit row."""
    from core import case_chat
    from core.incident_assistant import (
        _cameras_line,
        _chronology_lines,
        _record_audit,
        _record_text,
        memo_citations,
        record_of,
    )

    turn = (
        CaseChatTurn.objects.filter(pk=turn_id)
        .select_related(
            "chat", "chat__incident", "chat__incident__case", "chat__asked_by"
        )
        .first()
    )
    if turn is None or turn.chat.incident is None:
        return
    if turn.state not in (QUEUED, RUNNING):
        return
    chat = turn.chat
    incident = chat.incident
    started = time.monotonic()
    ground = PromptTemplate.named(PromptTemplate.GROUND_RULES)
    template = PromptTemplate.named(PromptTemplate.INCIDENT_CHAT)
    templates_line = (
        f"ground-rules v{ground.version}; Incident chat v{template.version}"
    )
    turn.state = RUNNING
    turn.save(update_fields=["state"])
    usage: dict = {"input_tokens": 0, "output_tokens": 0}
    try:
        problem = assistant._unreachable()
        if problem:
            raise problem
        if not on():
            raise engine.Problem(engine.ERROR, "the incident chat is off")
        record = record_of(incident)
        if not record["rows"]:
            raise engine.Problem(engine.ERROR, "the cameras gave nothing to read")
        event_lines, _ = _chronology_lines(incident)
        # The office's notes on the synced cameras' lines (Phase 8 chapter 2).
        from core import notes

        noted = notes.incident_block(incident)
        system = prompts.system_message(
            ground.text,
            template.text,
            prompts.INCIDENT_CHAT_FORMAT
            + "\n\n"
            + prompts.NARRATIVE_RULES
            + "\n\n"
            + prompts.INCIDENT_RULES
            + ("\n\n" + notes.RULE if noted else ""),
        )
        wanted = settings_store.incident_chat_answer_cap()
        dropped: set[str] = set()
        history = [
            (one.question, one.answer)
            for one in chat.turns.filter(state=DONE, number__lt=turn.number)
        ]

        def user_text() -> str:
            return (
                prompts.incident_memo_input(
                    _cameras_line(incident),
                    event_lines,
                    _record_text(incident, record, dropped),
                    about=incident.about,
                )
                + ("\n\n" + noted if noted else "")
                + "\n\nThe question: "
                + turn.question
            )

        by_size = sorted(
            record["transcript_only"],
            key=lambda name: -sum(1 for _, who, _ in record["rows"] if who == name),
        )
        user = user_text()
        while not prompts.fits(
            system, user, answer_cap=assistant.cap(wanted), window=assistant.window()
        ):
            if not by_size:
                raise engine.Problem(engine.TOO_LONG, "the incident is too long")
            dropped.add(by_size.pop(0))
            user = user_text()
        answer = engine.complete(
            case_chat._messages(system, user, history),
            max_completion_tokens=assistant.cap(wanted),
            thinking=assistant.thinking(),
            timeout=assistant.time_limit(FEATURE),
            **assistant.SAMPLING,
        )
        usage = answer
        if assistant.thought_it_away(answer):
            raise assistant.ThoughtItAway()
        if not CaseChatTurn.objects.filter(pk=turn.pk).exists():
            return
        text = answer["text"].strip()
        if dropped:
            text = (
                f"({', '.join(sorted(dropped))} could not be read for this answer.)\n\n"
                + text
            )
        turn.answer = text
        turn.citations = memo_citations(incident, turn.answer)
        turn.cut_short = answer.get("finish_reason") == "length"
        turn.model = answer.get("model", "")
        turn.state = DONE
        turn.reason_class = ""
        turn.answered_at = timezone.now()
        turn.save()
        _record_audit(
            incident,
            FEATURE,
            actor=chat.asked_by,
            templates=templates_line,
            model=turn.model,
            usage=usage,
            started=started,
            outcome="ok",
            cameras=len(record["used"]) + len(record["transcript_only"]) - len(dropped),
            cut_short=turn.cut_short,
        )
    except engine.Problem as problem:
        turn.state = FAILED
        turn.reason_class = (
            assistant.THOUGHT_AWAY
            if isinstance(problem, assistant.ThoughtItAway)
            else problem.reason
        )
        turn.save(update_fields=["state", "reason_class"])
        _record_audit(
            incident,
            FEATURE,
            actor=chat.asked_by,
            templates=templates_line,
            model="",
            usage=usage if isinstance(usage, dict) else {},
            started=started,
            outcome=problem.reason,
            reason=problem.reason,
        )
