"""Gideon reads what fits (Phase 9 chapter 6, ADR 0018).

The Scope of a question is the recordings it is put to: the whole Case, or the
recordings a person narrowed to on the page (the filter box, a Search's hits,
the Notes page's pills). The route is decided by one rule the page's
expectation and the task both use: within the ceiling the words are read
whole, in Readings as before; over it, when any recording has a Summary, two
passes: the Overviews first (one short line per recording and the Summary's
first part, cut to a budget so that every recording fits one Reading), which
name the recordings that bear on the question in order of relevance; then
those recordings whole, as many as fill the allowed Readings, exactly as the
Case Chat reads today, so the citations are to real lines. Size is never a
refusal; the drawer says what it read. No index: the Overview is the Summary's
first part, kept for its own sake.
"""

from __future__ import annotations

import json
import uuid

from django.utils import timezone

from core import engine, prompts, settings_store
from core.assistant import SUGGESTION_SAMPLING, PromptTemplate, cap, time_limit

WHOLE, NARROWED, OVERVIEWS, DIGEST = "whole", "narrowed", "overviews", "digest"
KINDS = ("all", "filter", "search", "notes")

# The selection answer's cap, and the least an Overview may be cut to before
# pass one is itself split into two Readings and the picks merged by rank.
SELECT_CAP = 4000
BUDGET_LEAST = 60
BUDGET_FLOOR = 24
MOST_IDS = 5000


# The scope ---------------------------------------------------------------------------


def scope_of(case, posted) -> dict:
    """The scope as the page posted it, kept honest: a kind the chapter names
    and the ids of recordings in this Case, nothing typed. Anything else is
    the whole Case."""
    if not isinstance(posted, dict):
        return {"kind": "all", "recordings": [], "dropped": 0}
    kind = str(posted.get("kind", "all"))
    ids = posted.get("recordings") or []
    if kind not in KINDS or kind == "all" or not isinstance(ids, list) or not ids:
        return {"kind": "all", "recordings": [], "dropped": 0}
    wanted = []
    for one in ids[:MOST_IDS]:
        try:
            wanted.append(str(uuid.UUID(str(one))))
        except (ValueError, AttributeError, TypeError):
            continue
    known = set(
        str(pk)
        for pk in case.recordings.filter(pk__in=wanted).values_list("pk", flat=True)
    )
    kept = [one for one in wanted if one in known]
    dropped = len(ids[:MOST_IDS]) - len(kept)
    if not kept:
        return {"kind": "all", "recordings": [], "dropped": dropped}
    return {"kind": kind, "recordings": kept, "dropped": dropped}


def narrowed(scope: dict) -> bool:
    return bool(scope and scope.get("kind", "all") != "all" and scope.get("recordings"))


# The route ---------------------------------------------------------------------------


def hours_of(read) -> float:
    return sum((one.duration_seconds or 0) for one in read) / 3600


def route_for(read, overviews: dict, scope: dict | None = None) -> str:
    """One rule for the page and the task: whole (or narrowed) within the
    ceiling; the overviews first over it when any recording has one; the
    Digest fallback, today's, when none has."""
    from core import case_chat

    if hours_of(read) <= case_chat.hours_allowed():
        return NARROWED if narrowed(scope or {}) else WHOLE
    if any(overviews.get(one.pk) for one in read):
        return OVERVIEWS
    return DIGEST


def picks_most() -> int:
    return int(settings_store.get("case_chat_picks_most") or 30)


def readings_after() -> int:
    return int(settings_store.get("case_chat_readings_after") or 1)


# Pass one: the overviews -------------------------------------------------------------


def cut_overview(text: str, budget: int) -> str:
    """The Overview cut at a sentence end to about the budget in tokens."""
    text = " ".join((text or "").split())
    if not text or prompts.tokens(text) <= budget:
        return text
    most = max(40, budget * 3)
    cut = text[:most]
    for mark in (". ", "; ", ", "):
        at = cut.rfind(mark)
        if at > most // 3:
            return cut[: at + 1].strip()
    return cut.rstrip() + "..."


def overview_line(number: int, recording, overview: str) -> str:
    from core import exports

    kind = recording.recording_type or "recording"
    head = (
        f"{number}. {exports.title_of(recording)}, {kind}, "
        f"{timezone.localtime(recording.created):%d %b %Y}, "
        f"{exports.length_of(recording)}"
    )
    return head + "\n" + (overview if overview else "(no summary yet)")


def budget_for(count: int, fixed_tokens: int) -> int:
    """What each recording's Overview may cost so that every recording fits
    one Reading beside the fixed parts of the request."""
    room = settings_store.reading_tokens() - fixed_tokens
    return max(BUDGET_FLOOR, room // max(count, 1))


def select_schema(most: int) -> dict:
    return {
        "type": "object",
        "properties": {
            "picks": {
                "type": "array",
                "maxItems": most,
                "items": {
                    "type": "object",
                    "properties": {
                        "recording": {"type": "integer"},
                        "why": {"type": "string", "maxLength": 160},
                    },
                    "required": ["recording", "why"],
                    "additionalProperties": False,
                },
            },
            "none": {"type": "boolean"},
            "note": {"type": "string", "maxLength": 240},
        },
        "required": ["picks", "none", "note"],
        "additionalProperties": False,
    }


def parse_selection(text: str, by_number: dict, most: int) -> tuple[list, str]:
    """The picks as recordings in the order the engine gave them, unknown
    numbers and repeats dropped; and the note."""
    try:
        parsed = json.loads(text)
    except ValueError:
        try:
            parsed = json.loads(prompts.salvage_json(text))
        except ValueError:
            raise engine.Problem(
                engine.BAD_OUTPUT, "the selection was unreadable"
            ) from None
    if not isinstance(parsed, dict):
        raise engine.Problem(engine.BAD_OUTPUT, "the selection was not a selection")
    picks: list = []
    seen: set = set()
    for one in parsed.get("picks") or []:
        if not isinstance(one, dict):
            continue
        try:
            number = int(one.get("recording"))
        except (TypeError, ValueError):
            continue
        recording = by_number.get(number)
        if recording is None or number in seen:
            continue
        seen.add(number)
        picks.append({"recording": recording, "why": str(one.get("why", ""))[:160]})
        if len(picks) >= most:
            break
    note = str(parsed.get("note", "") or "")[:240]
    return picks, note


def select(
    *,
    read,
    overviews: dict,
    people: str,
    question: str,
    earlier_questions: list[str],
    ground_text: str,
    one_call,
) -> dict:
    """Pass one: the overviews read once, into data. Returns the picks in
    relevance order with their reasons, the note, and the counts."""
    template = PromptTemplate.named(PromptTemplate.CASE_CHAT_SELECT)
    most = picks_most()
    system = prompts.system_message(
        ground_text, template.text, prompts.CASE_CHAT_SELECT_FORMAT
    )
    asked_before = (
        "Earlier questions in this chat:\n" + "\n".join(earlier_questions)
        if earlier_questions
        else ""
    )
    fixed = (
        prompts.tokens(system)
        + prompts.tokens(people)
        + prompts.tokens(asked_before)
        + prompts.tokens(question)
        + cap(SELECT_CAP)
        + 200
    )
    numbered = list(enumerate(read, start=1))
    by_number = {number: recording for number, recording in numbered}
    budget = budget_for(len(read), fixed)
    halves = [numbered]
    if budget < BUDGET_LEAST and len(read) > 1:
        middle = len(numbered) // 2
        halves = [numbered[:middle], numbered[middle:]]
        budget = budget_for(max(len(half) for half in halves), fixed)

    def lines_of(part) -> str:
        return "\n\n".join(
            overview_line(
                number, recording, cut_overview(overviews.get(recording.pk, ""), budget)
            )
            for number, recording in part
        )

    results = []
    for part in halves:
        told = (
            f"These are recordings {part[0][0]} to {part[-1][0]} of {len(read)}; "
            "the rest are put to the same question separately."
            if len(halves) > 1
            else f"The {len(read)} recordings of this case, numbered."
        )
        user = "\n\n".join(
            one
            for one in (
                people,
                told,
                lines_of(part),
                asked_before,
                "The question: " + question,
            )
            if one
        )
        answer = one_call(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            cap(SELECT_CAP),
            schema=select_schema(most),
            think=False,
            sampling=SUGGESTION_SAMPLING,
            timeout=time_limit("chat_turn"),
        )
        results.append(parse_selection(answer["text"], by_number, most))
    # Merged by rank: the first pick of each half, then the second, and so on.
    picks: list = []
    seen: set = set()
    longest = max(len(found) for found, _ in results)
    for rank in range(longest):
        for found, _ in results:
            if rank < len(found) and found[rank]["recording"].pk not in seen:
                seen.add(found[rank]["recording"].pk)
                picks.append(found[rank])
    picks = picks[:most]
    notes = [note for _, note in results if note]
    return {
        "picks": picks,
        "note": " ".join(notes)[:240],
        "overviews_read": sum(1 for one in read if overviews.get(one.pk)),
        "no_summary": sum(1 for one in read if not overviews.get(one.pk)),
        "calls": len(halves),
        "budget": budget,
        "template_version": template.version,
    }


# Pass two: which picks fit ---------------------------------------------------------


def fitting(picks: list, size_of, reading_tokens: int, readings: int) -> list:
    """The picks in relevance order until their whole transcripts fill the
    allowed Readings, packed as the question will pack them, in upload order;
    one that would not fit a Reading alone is passed over."""
    from core.case_chat import pack

    kept: list = []
    sizes: dict = {}

    def upload_order(one) -> tuple:
        recording = one["recording"]
        return (str(getattr(recording, "created", "")), str(recording.pk))

    for pick in picks:
        recording = pick["recording"]
        sizes[recording.pk] = size_of(recording)
        if sizes[recording.pk] > reading_tokens:
            continue
        trial = sorted(kept + [pick], key=upload_order)
        rendered = [
            (index, "x" * (sizes[one["recording"].pk] * prompts.CHARS_PER_TOKEN))
            for index, one in enumerate(trial, start=1)
        ]
        if len(pack(rendered, reading_tokens)) > readings:
            continue
        kept = trial
    return kept


# The history --------------------------------------------------------------------------


def without_openings(answer: str) -> str:
    """An earlier answer without the lines the app put at its head (what was
    read, what was not, the videos read from the transcript alone), for the
    history handed to the engine: left in, the engine copied them into later
    answers, once with the earlier question's figures (the probe of
    2026-10-04)."""
    lines = (answer or "").split("\n")
    while lines:
        head = lines[0].strip()
        if not head:
            lines.pop(0)
            continue
        app_line = (
            head.startswith("Read the overviews of ")
            or (head.startswith("Read ") and "narrowed to on the page" in head)
            or head.endswith("read from the transcript alone.")
            or " not read: " in head
        )
        if not app_line:
            break
        lines.pop(0)
    return "\n".join(lines).strip()


# What was read, in words -------------------------------------------------------------


def opening_line(turn) -> str:
    """The answer's first line: what was read, and what was not."""
    selection = turn.selection or {}
    scope = turn.scope or {}
    if turn.route == OVERVIEWS:
        read_whole = selection.get("read_whole", 0)
        pointed = selection.get("pointed_to", 0)
        said = (
            f"Read the overviews of {selection.get('overviews_read', 0)} "
            f"recordings, then {read_whole} whole"
        )
        if pointed > read_whole:
            said += (
                f"; read {read_whole} of the {pointed} they pointed to, "
                "so narrow the question for the rest"
            )
        said += "."
        missing = selection.get("no_summary", 0)
        if missing:
            said += (
                f" {missing} recording{'' if missing == 1 else 's'} "
                f"{'has' if missing == 1 else 'have'} no summary yet and "
                f"{'was' if missing == 1 else 'were'} not read; the case page "
                "offers to write the missing summaries tonight."
            )
        return said
    if turn.route == NARROWED:
        count = len(scope.get("recordings") or [])
        read = len(turn.readings or [])
        word = "recording" if count == 1 else "recordings"
        if read and read < count:
            # Some of the narrowed recordings had no transcript to read.
            return f"Read {read} of the {count} {word} narrowed to on the page."
        return f"Read the {count} {word} narrowed to on the page."
    return ""


def read_words(turn) -> str:
    """One line for the page and the export under a question: what it read."""
    selection = turn.selection or {}
    scope = turn.scope or {}
    if turn.route == OVERVIEWS:
        return (
            f"Asked over the overviews of {selection.get('overviews_read', 0)} "
            f"recordings, then {selection.get('read_whole', 0)} read whole."
        )
    if turn.route == NARROWED:
        count = len(scope.get("recordings") or [])
        where = {
            "filter": "the recordings list",
            "search": "a search's hits",
            "notes": "the Notes page",
        }.get(scope.get("kind", ""), "the page")
        return f"Asked of the {count} recordings narrowed to on {where}."
    if turn.route in (WHOLE, DIGEST):
        return "Asked of every recording in the case."
    return ""


def head_line(hours: float, allowed: int, summarised: int) -> str:
    """The drawer's head before a question, for a whole-case scope."""
    if hours <= allowed:
        return "This case"
    if summarised:
        return "Reads the overviews first, then the recordings they point to"
    return "Over the ceiling, and no recording has a summary yet"
