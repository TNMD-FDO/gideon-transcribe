"""The Chat tab of a Case page: its state, and what a person does there.

Mirrors the viewer's Chat endpoints, keyed to the Case instead of a Recording:
one state answer the tab polls every two seconds while a question runs, New
chat, Ask, Delete, and Export to Word. Hidden while Folder management is Off,
and while the AI assistant or Chat across cases is Off.
"""

from __future__ import annotations

import json
import re

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from core import (
    assistant,
    audit,
    case_chat,
    case_scope,
    cases,
    engine,
    expectation,
    exports,
    incidents,
    one_reading,
    prompts,
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


def _expected(chat, case, scope: dict | None = None) -> dict:
    """The turn's time expectation at the ask (v1.95.0): an incident chat is
    given the incident's record, a case chat every readable transcript in its
    scope; over the ceiling (Phase 9 chapter 6) the two-pass figure, sized by
    the overviews and the Readings the picks may fill."""
    from core import case_scope, sitting

    if chat.incident_id:
        return expectation.note("incident_chat", sitting.record_tokens(chat.incident))
    scope = scope or {}
    readable = case_chat.readable(
        case, scope.get("recordings") if case_scope.narrowed(scope) else None
    )[0]
    overviews = assistant.overviews_for(readable)
    if case_scope.route_for(readable, overviews, scope) == case_scope.OVERVIEWS:
        size = sum(prompts.tokens(one) for one in overviews.values()) + (
            settings_store.reading_tokens() * case_scope.readings_after()
        )
        return expectation.note("case_chat_two_pass", size)
    size = sum(
        assistant.reading_size(getattr(one, "transcript", None)) for one in readable
    )
    return expectation.note("case_chat_turn", size)


def _turn_json(
    turn: CaseChatTurn,
    still_here: dict,
    me=None,
    lines: dict | None = None,
    links: dict | None = None,
) -> dict:
    """One turn as the tab draws it, its Citations resolved to links or not.
    `lines` holds the cited lines by (recording id, second) and `links`
    every synced camera's All cameras link by recording id, both from one
    query for the whole state (v1.134.0)."""
    asker = turn.asked_by or turn.chat.asked_by
    cited = {}
    for text, where in (turn.citations or {}).items():
        if where.get("kind") == "document":
            # A report's paragraph (Phase 8 chapter 4): kept resolved.
            cited[text] = where
            continue
        recording = still_here.get(where["recording"])
        if recording is None:
            cited[text] = {"removed": True}
            continue
        cited[text] = {
            "title": exports.title_of(recording),
            "clock": exports.clock(where["seconds"]),
            "href": f"{reverse('viewer', args=[recording.pk])}?t={where['seconds']}",
            # The preview under an answer (Phase 7 chapter 5): the playback
            # copy at that moment, the same route the viewer plays.
            "seconds": where["seconds"],
            "media": _media_of(recording),
            # The Preview (v1.98.0) reads the lines around the moment itself.
            "recording": str(recording.pk),
            # The line it points to, for the pill's hover; never logged.
            "line": _line_at(recording, where["seconds"], lines),
            # All cameras (Phase 6 chapter 1): the incident page at that
            # moment, for a placed camera of an incident; "" otherwise.
            "all": (
                incidents.url_at(links.get(recording.pk), where["seconds"])
                if links is not None
                else incidents.all_cameras_url(recording, where["seconds"])
            ),
        }
    running = turn.state in (assistant.QUEUED, assistant.RUNNING)
    count = len(turn.readings or [])
    if running and turn.route == case_scope.OVERVIEWS and not count:
        overviews = (turn.selection or {}).get("overviews_read") or len(
            (turn.scope or {}).get("recordings") or []
        )
        reading = (
            f"Reading the overviews of {overviews} recordings..."
            if overviews
            else "Reading the overviews..."
        )
    elif running and turn.route == case_scope.OVERVIEWS:
        reading = f"Reading {count} recording{'' if count == 1 else 's'} whole..."
    elif running and turn.parts:
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
        # What the question read (Phase 9 chapter 6), for the page's line.
        "route": turn.route or "",
        "read_words": case_scope.read_words(turn) if turn.route else "",
        # Under the answer (Phase 9 chapter 6, v1.163.0): what it read, in how
        # many Readings, and how long it took.
        "read_line": one_reading.read_line(turn),
        "expectation": expectation.json_of(turn.expectation, turn.state, "chat"),
        "asked_at": turn.asked_at.isoformat() if turn.asked_at else "",
        "answered_at": turn.answered_at.isoformat() if turn.answered_at else "",
        # Whose question (v1.126.0), for a colleague's chat.
        "asked_by": asker.shown_name if asker else "",
        "yours": bool(me is not None and asker is not None and asker.pk == me.pk),
    }


def _media_of(recording) -> str:
    # From the record, never the disk (v1.134.0).
    from core.media_access import playback_url

    return playback_url(recording)


def _line_at(recording, seconds: float, lines: dict | None = None) -> str:
    """The line the pill's hover shows: the transcript line at that second, or,
    when nothing was said there, what the camera showed as the Digest has it
    (v1.82.0). With `lines` from lines_at, nothing is asked here."""
    if lines is None:
        lines = lines_at([(recording.pk, seconds)])
    segment = lines.get((recording.pk, int(seconds)))
    if segment is None:
        return _seen_at(recording, seconds)
    who = f"{segment.speaker}: " if segment.speaker else ""
    return (who + segment.text)[:200]


def lines_at(moments) -> dict:
    """The first line starting inside each cited second, for every
    (recording id, seconds) pair at once, keyed by (recording id, whole
    second): one query for a whole state (v1.134.0), where each citation
    had asked for its own."""
    from django.db.models import Q

    from core.jobs import Segment

    wanted = {(recording_id, int(seconds)) for recording_id, seconds in moments}
    if not wanted:
        return {}
    asked = Q()
    for recording_id, second in wanted:
        asked |= Q(
            transcript__recording_id=recording_id,
            start__gte=second,
            start__lt=second + 1,
        )
    found: dict = {}
    for segment in (
        Segment.objects.filter(asked)
        .order_by("start", "id")
        .only("transcript_id", "transcript__recording_id", "start", "speaker", "text")
        .select_related("transcript")
    ):
        key = (segment.transcript.recording_id, int(segment.start))
        found.setdefault(key, segment)
    return found


STAMPED = re.compile(r"\[(\d{1,2}):(\d{2}):(\d{2})\]")
MARKED = re.compile(r"\((said|seen|both)\)")


def _seen_at(recording, seconds: float) -> str:
    """The Digest's line whose span holds the second, marked seen or both, as
    "Seen: ..."; "" when the Digest has none there."""
    transcript = getattr(recording, "transcript", None)
    if transcript is None or not assistant.digests_on():
        return ""
    for line in assistant.digest_text(transcript).splitlines():
        marked = MARKED.search(line)
        if marked is None or marked.group(1) == "said":
            continue
        times = [
            int(h) * 3600 + int(m) * 60 + int(s)
            for h, m, s in STAMPED.findall(line[: marked.start()])
        ]
        if not times:
            continue
        low, high = min(times), max(times)
        if low <= int(seconds) <= high:
            words = " ".join(line[marked.end() :].split())
            return f"Seen: {words}"[:200] if words else ""
    return ""


def _earlier_line(chat: CaseChat, still_here: dict, turns=None) -> str:
    """Process again on a Recording since an answer used its Transcript."""
    replaced = []
    if turns is None:
        turns = list(chat.turns.all())
    for turn in turns:
        if turn.state != assistant.DONE:
            continue
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


def _chat_json(
    chat: CaseChat,
    still_here: dict,
    me=None,
    lines: dict | None = None,
    links: dict | None = None,
) -> dict:
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
        "earlier": _earlier_line(chat, still_here, turns),
        "turns": [_turn_json(one, still_here, me, lines, links) for one in turns],
        # Whose chat (v1.126.0): the panel lists yours first, everyone's a
        # tab away, and a colleague's chat says whose it is.
        "asked_by": chat.asked_by.shown_name if chat.asked_by else "",
        "yours": bool(me is not None and chat.asked_by_id == me.pk),
    }


def _readable(recordings) -> tuple[list, list[dict]]:
    """case_chat.readable, from the recordings already loaded with their
    transcripts and one query for the jobs of those without (v1.134.0): the
    poll had asked two questions of every recording every two seconds."""
    from core import pages

    rows = sorted(recordings, key=lambda one: (one.created, str(one.pk)))
    read = [one for one in rows if getattr(one, "transcript", None) is not None]
    without = [one for one in rows if getattr(one, "transcript", None) is None]
    newest = pages.newest_jobs_of(without) if without else {}
    skipped = []
    for recording in without:
        job = newest.get(recording.pk)
        failed = recording.media_state in ("failed", "rejected") or (
            job is not None and job.state == "failed"
        )
        skipped.append(
            {
                "recording": str(recording.pk),
                "title": case_chat._title(recording),
                "why": "failed" if failed else "still transcribing",
            }
        )
    return read, skipped


@login_required
def state(request: HttpRequest, case_id) -> JsonResponse:
    case = _the_case(request, case_id)
    # The case's recordings with their transcripts, once (v1.134.0).
    still_here = {
        str(one.pk): one
        for one in Recording.objects.filter(case=case).select_related("transcript")
    }
    # The incident's conversations live on the incident page (Phase 7 chapter 5).
    chats_here = list(
        case.chats.filter(incident__isnull=True)
        .select_related("asked_by")
        .prefetch_related("turns", "turns__asked_by")
    )
    # Every citation's line in one query, and every camera's link in one.
    moments = [
        (still_here[where["recording"]].pk, where["seconds"])
        for chat in chats_here
        for turn in chat.turns.all()
        for where in (turn.citations or {}).values()
        if where.get("kind") != "document" and where.get("recording") in still_here
    ]
    lines = lines_at(moments)
    links = incidents.links_in(case)
    chats = [
        _chat_json(one, still_here, request.user, lines, links) for one in chats_here
    ]
    read, skipped = _readable(still_here.values())
    # What a whole-case question would do (Phase 9 chapter 6), for the
    # drawer's head and its grounding line.
    # One reading (Phase 9 chapter 6, v1.163.0): the same figures the case
    # page's strip draws, for the head line and the grounding line.
    # The poll counts no share: the case page's draw does that.
    figures = one_reading.figures(case, count=False)
    hours = figures["hours"]
    allowed = figures["allowed"]
    summarised = figures["summarised"]
    return JsonResponse(
        {
            "reachable": engine.is_reachable(),
            "unavailable_line": engine.WHAT_TO_SAY[engine.UNREACHABLE],
            "busy": any(one["busy"] for one in chats),
            "readable": len(read),
            "skipped": len(skipped),
            "hours": figures["hours_words"],
            "hours_allowed": allowed,
            "over": hours > allowed,
            "summarised": summarised,
            "no_summary": figures["no_summary"],
            "readings": figures["readings"],
            "at_once": figures["at_once"],
            "head": figures["head"],
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
    body = _body(request)
    question = str(body.get("question", "")).strip()
    if not question:
        return JsonResponse({"error": "ask something"}, status=400)
    # The scope the page posted (Phase 9 chapter 6), kept honest.
    scope = case_scope.scope_of(case, body.get("scope"))
    if chat.turns.filter(state__in=(assistant.QUEUED, assistant.RUNNING)).exists():
        return JsonResponse(
            {"error": "the last question is still being answered"}, status=409
        )
    if chat.incident_id:
        # Gideon on the incident page (Phase 7 chapter 5): the record, not
        # the case's transcripts.
        from core import incident_chat

        if not incident_chat.on():
            return JsonResponse({"error": "the incident chat is off"}, status=409)
        if not incident_chat.readable(chat.incident):
            return JsonResponse(
                {"error": "no synced camera of this incident has a transcript yet"},
                status=409,
            )
    else:
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
        chat=chat,
        number=chat.turns.count() + 1,
        question=question[:4000],
        asked_by=request.user,
        scope=scope if not chat.incident_id else {},
        expectation=_expected(chat, case, scope),
    )
    if chat.incident_id:
        tasks.answer_incident_turn.defer(turn_id=str(turn.pk))
    else:
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
