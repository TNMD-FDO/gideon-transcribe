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
        if isinstance(at, dict):
            # A report's paragraph (Phase 8 chapter 4): kept resolved.
            out[whole] = at
            continue
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
        # The report for this incident (Phase 8 chapter 4, part 2).
        from core import documents

        papers, papers_note, named = documents.reading_block(
            documents.for_incident(incident),
            turn.question,
            heading="The report for this incident:",
        )
        system = prompts.system_message(
            ground.text,
            template.text,
            prompts.INCIDENT_CHAT_FORMAT
            + "\n\n"
            + prompts.NARRATIVE_RULES
            + "\n\n"
            + prompts.INCIDENT_RULES
            + ("\n\n" + notes.RULE if noted else "")
            + ("\n\n" + documents.RULE if papers else ""),
        )
        wanted = settings_store.incident_chat_answer_cap()
        history = [
            (one.question, one.answer)
            for one in chat.turns.filter(state=DONE, number__lt=turn.number)
        ]

        # One sitting (Phase 8 chapter 9): everything said is read; the
        # longest cameras' pictures go first when the whole does not fit.
        from core import sitting

        record, user, words_alone = sitting.fit(
            incident,
            system=system,
            wrap=lambda body: (
                prompts.incident_memo_input(
                    _cameras_line(incident), event_lines, body, about=incident.about
                )
                + ("\n\n" + noted if noted else "")
                + ("\n\n" + papers if papers else "")
                + "\n\nThe question: "
                + turn.question
            ),
            answer_cap=assistant.cap(wanted),
        )
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
        if words_alone:
            count = len(record["used"]) + len(record["transcript_only"])
            text = (
                "(Answered from "
                + sitting.read_words(count, count - len(words_alone), words_alone)
                + f": {', '.join(words_alone)}.)\n\n"
                + text
            )
        turn.answer = documents.with_note(text, papers_note)
        turn.citations = {
            **memo_citations(incident, turn.answer),
            **documents.citations_in(turn.answer, named),
        }
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
            cameras=len(record["used"]) + len(record["transcript_only"]),
            words_alone=len(words_alone),
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
