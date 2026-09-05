"""The Case Chat: a Chat whose ground is every Transcript in a Case.

A question is answered from the whole Case as it stands when it is asked: every
Recording whose Transcript exists, in upload order, read whole. When the Case
fits one Reading (about six hours of talk) the question is one engine call,
exactly as a Recording's Chat is. When it does not, whole Transcripts are
packed into as few Readings as they fit, every Reading is asked the same
question two at a time, and one combining call writes the answer from the
part answers. Nothing is indexed, embedded, or kept between questions; each
question renders the Case afresh. Nothing asked or answered is ever logged.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from django.db import models
from django.utils import timezone

from core import audit, engine, prompts, settings_store
from core.assistant import (
    DONE,
    FAILED,
    QUEUED,
    RUNNING,
    SAMPLING,
    STATES,
    THOUGHT_AWAY,
    PromptTemplate,
    ThoughtItAway,
    cap,
    thinking,
    thought_it_away,
    time_limit,
)

log = logging.getLogger("transcribe.case_chat")

# One Reading holds up to this much rendered Transcript: the Phase 1 ceiling,
# about six hours of talk, kept at that size rather than filling a larger
# window because models use the middle of a long context badly.
READING_TOKENS = 100_000
# Two Readings run at a time inside the AI assistant's four lanes, so one Case
# never fills them.
READINGS_AT_ONCE = 2
# The whole question, in seconds, on top of each call's own two minutes.
QUESTION_LIMIT = 15 * 60
PART_CAP = 1500
COMBINED_CAP = 2000

CASE_TOO_LARGE = engine.CASE_TOO_LARGE

CITED = re.compile(r"\[Recording (\d{1,3}), (\d{1,2}):(\d{2}):(\d{2})\]")


class CaseChat(models.Model):
    """A Chat that belongs to the Case, open to whoever can open the Case."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        "core.Case", on_delete=models.CASCADE, related_name="chats"
    )
    asked_by = models.ForeignKey(
        "core.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    name = models.CharField(max_length=80, blank=True, default="")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]


class CaseChatTurn(models.Model):
    """One question and its answer, with what the question read.

    `readings` is the list of header lines as numbered for this question, one
    per Recording read: its id, title, type, upload date, length, and the
    Transcript it read. That is how a Citation "[Recording 3, 00:12:45]" still
    opens the right Recording later, and how the export's cover lists what the
    Chat has read. `skipped` names the Recordings not read and why.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chat = models.ForeignKey(CaseChat, on_delete=models.CASCADE, related_name="turns")
    number = models.IntegerField()
    question = models.TextField()
    answer = models.TextField(blank=True, default="")
    # "[Recording 3, 00:12:45]" -> {"recording": id, "seconds": 765.0}
    citations = models.JSONField(default=dict, blank=True)
    readings = models.JSONField(default=list, blank=True)
    skipped = models.JSONField(default=list, blank=True)
    parts = models.IntegerField(default=0)
    state = models.CharField(max_length=10, choices=STATES, default=QUEUED)
    reason_class = models.CharField(max_length=40, blank=True, default="")
    # The failure's own words when the reason needs them: the ceiling's figures,
    # the Recording that would not fit. Never the question or an answer.
    reason_detail = models.CharField(max_length=200, blank=True, default="")
    cut_short = models.BooleanField(default=False)
    model = models.CharField(max_length=120, blank=True, default="")
    asked_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["number"]


# What the pages ask -------------------------------------------------------------------


def available() -> bool:
    """Whether the Chat tab exists: the master switch and its own, and Cases."""
    from core import cases

    return (
        cases.folder_management_on()
        and bool(settings_store.get("assistant_available"))
        and bool(settings_store.get("chat_across_cases"))
    )


def hours_allowed() -> int:
    return int(settings_store.get("case_chat_hours") or 120)


def readable(case) -> tuple[list, list[dict]]:
    """The Recordings a question would read, in upload order, and those skipped."""
    read, skipped = [], []
    for recording in case.recordings.order_by("created"):
        if getattr(recording, "transcript", None) is not None:
            read.append(recording)
            continue
        job = recording.jobs.order_by("-created").first()
        failed = recording.media_state in ("failed", "rejected") or (
            job is not None and job.state == "failed"
        )
        skipped.append(
            {
                "recording": str(recording.pk),
                "title": _title(recording),
                "why": "failed" if failed else "still transcribing",
            }
        )
    return read, skipped


def what_to_say(turn: CaseChatTurn) -> str:
    """The person's line for a failed question."""
    from core import assistant

    if turn.reason_detail:
        return turn.reason_detail
    if turn.reason_class == CASE_TOO_LARGE:
        return "This case is too large for one question."
    return assistant.what_to_say(turn.reason_class)


def not_read_line(skipped: list[dict]) -> str:
    """The answer's opening line about the Recordings it could not read."""
    if not skipped:
        return ""
    parts = []
    for why in ("still transcribing", "failed"):
        count = sum(1 for one in skipped if one["why"] == why)
        if count:
            parts.append(
                f"{count} recording{'' if count == 1 else 's'} "
                f"{'was' if count == 1 else 'were'} not read: {why}"
            )
    return ". ".join(parts) + "."


# The prompt ---------------------------------------------------------------------------


def people_line(case) -> str:
    """The People with their Roles, never their notes; "none yet" when none."""
    if not case.people.exists():
        return "People in this case: none yet"
    shown = [one.shown() for one in case.people.all()]
    return "People in this case: " + ", ".join(shown)


def header_line(number: int, total: int, recording, transcript) -> str:
    """One line per Transcript, carrying what the Transcript-nature line carries."""
    from core import exports

    if transcript.task_run == "translate":
        nature = (
            "machine translation to English from "
            f"{exports.language_name(transcript.language) or 'an unknown language'}"
        )
    else:
        nature = (
            "machine transcription in "
            f"{exports.language_name(transcript.language) or 'an unknown language'}"
        )
    if recording.is_two_channel_call:
        speakers = "the two sides of a phone call labelled Side 1 and Side 2"
    elif recording.diarize:
        speakers = "speakers separated automatically"
    else:
        speakers = "speakers not separated"
    kind = recording.recording_type or "recording"
    return (
        f"Recording {number} of {total}: {_title(recording)}, {kind}, uploaded "
        f"{timezone.localtime(recording.created):%d %B %Y}, "
        f"{exports.length_of(recording)}, {nature}, {speakers}"
    )


def _title(recording) -> str:
    from core import exports

    return exports.title_of(recording)


def reading_of(recording, transcript) -> dict:
    """What a turn remembers about one Recording it read."""
    from core import exports

    return {
        "recording": str(recording.pk),
        "title": _title(recording),
        "type": recording.recording_type or "",
        "uploaded": timezone.localtime(recording.created).strftime("%d %B %Y"),
        "length": exports.length_of(recording),
        "translated": transcript.task_run == "translate",
        "transcript_created": transcript.created.isoformat(),
    }


def pack(rendered: list[tuple[int, str]]) -> list[list[int]]:
    """Whole Transcripts into as few Readings as they fit, in order, never cut.

    Each item is (index, text). A Transcript larger than a Reading is alone in
    its own; the window check for that one is the caller's.
    """
    readings: list[list[int]] = []
    current: list[int] = []
    used = 0
    for index, text in rendered:
        cost = prompts.tokens(text)
        if current and used + cost > READING_TOKENS:
            readings.append(current)
            current, used = [], 0
        current.append(index)
        used += cost
    if current:
        readings.append(current)
    return readings


def citations(text: str, starts_by_number: dict[int, dict]) -> dict:
    """The [Recording n, hh:mm:ss] references that name a real line.

    `starts_by_number` maps a Recording's number in this question to
    {"recording": id, "starts": {whole second: start}}. A reference the app
    cannot match is left as plain text.
    """
    found: dict = {}
    for match in CITED.finditer(text):
        number = int(match.group(1))
        hours, minutes, seconds = (int(part) for part in match.groups()[1:])
        whole = hours * 3600 + minutes * 60 + seconds
        known = starts_by_number.get(number)
        if known and whole in known["starts"]:
            found[match.group(0)] = {
                "recording": known["recording"],
                "seconds": known["starts"][whole],
            }
    return found


# The task ---------------------------------------------------------------------------


def answer_case_turn(turn_id) -> None:
    """One Case Chat question: one Reading, or several and a combining call."""
    turn = (
        CaseChatTurn.objects.filter(pk=turn_id)
        .select_related("chat", "chat__case", "chat__case__owner")
        .first()
    )
    if turn is None:
        return
    chat = turn.chat
    case = chat.case
    started = time.monotonic()
    ground = PromptTemplate.named(PromptTemplate.GROUND_RULES)
    template = PromptTemplate.named(PromptTemplate.CASE_CHAT)
    templates_line = f"ground-rules v{ground.version}; case-chat v{template.version}"
    turn.state = RUNNING
    turn.save(update_fields=["state"])

    usage = {"input_tokens": 0, "output_tokens": 0}
    calls = {"readings": 0, "read": 0, "model": ""}

    def one_call(messages, answer_cap: int) -> dict:
        if time.monotonic() - started > time_limit_for_the_question():
            raise engine.Problem(engine.TIMEOUT, "the question ran out of time")
        answer = engine.complete(
            messages,
            max_completion_tokens=cap(answer_cap),
            thinking=thinking(),
            timeout=time_limit("chat_turn"),
            **SAMPLING,
        )
        usage["input_tokens"] += answer.get("input_tokens", 0) or 0
        usage["output_tokens"] += answer.get("output_tokens", 0) or 0
        calls["model"] = answer.get("model") or calls["model"]
        if thought_it_away(answer):
            raise ThoughtItAway()
        return answer

    try:
        if not engine.is_reachable():
            raise engine.Problem(
                engine.UNREACHABLE, "the engine is failing the minute check"
            )
        read, skipped = readable(case)
        hours = sum((one.duration_seconds or 0) for one in read) / 3600
        if hours > hours_allowed():
            turn.reason_detail = (
                f"This case is too large for one question ({hours:.0f} hours of "
                f"recordings; the limit is {hours_allowed()})."
            )
            raise engine.Problem(CASE_TOO_LARGE, "over the hours ceiling")
        turn.skipped = skipped
        if not read:
            turn.reason_detail = (
                "No recording in this case has a transcript to read yet."
            )
            raise engine.Problem(engine.ERROR, "nothing to read")

        # Render every Transcript once, with its header, and remember what was read.
        total = len(read)
        rendered: list[tuple[int, str]] = []
        starts_by_number: dict[int, dict] = {}
        readings_kept = []
        for number, recording in enumerate(read, start=1):
            transcript = recording.transcript
            lines = prompts.lines_of(transcript)
            text = (
                header_line(number, total, recording, transcript)
                + "\n"
                + (prompts.render(lines))
            )
            rendered.append((number, text))
            starts: dict[int, float] = {}
            for line in lines:
                starts.setdefault(int(line.start), line.start)
            starts_by_number[number] = {
                "recording": str(recording.pk),
                "starts": starts,
            }
            readings_kept.append(reading_of(recording, transcript))
        turn.readings = readings_kept
        calls["read"] = total

        system = prompts.system_message(
            ground.text, template.text, prompts.CASE_CHAT_FORMAT
        )
        people = people_line(case)
        earlier = [
            (one.question, one.answer)
            for one in chat.turns.filter(state=DONE, number__lt=turn.number)
        ]
        history = prompts.history_that_fits(earlier)
        history_text = "\n".join(q + "\n" + a for q, a in history)

        groups = pack(rendered)
        by_number = dict(rendered)
        # A Transcript that would not fit the window even alone names itself.
        for group in groups:
            if len(group) == 1:
                body = by_number[group[0]]
                if not prompts.fits(
                    system,
                    people,
                    body,
                    history_text,
                    turn.question,
                    answer_cap=cap(PART_CAP),
                ):
                    which = read[group[0] - 1]
                    turn.reason_detail = (
                        f"The transcript of {_title(which)} is too long for the "
                        "AI assistant, even on its own."
                    )
                    raise engine.Problem(engine.TOO_LONG, "one transcript too long")
        turn.parts = len(groups) if len(groups) > 1 else 0
        turn.save(update_fields=["skipped", "readings", "parts"])

        def ask_reading(group: list[int], answer_cap: int) -> str:
            user = "\n\n".join(
                [people, *(by_number[number] for number in group), turn.question]
            )
            answer = one_call(_messages(system, user, history), answer_cap)
            calls["readings"] += 1
            if len(groups) == 1:
                turn.cut_short = answer["finish_reason"] == "length"
            return answer["text"].strip()

        if len(groups) == 1:
            text = ask_reading(groups[0], PART_CAP)
        else:
            with ThreadPoolExecutor(max_workers=READINGS_AT_ONCE) as pool:
                parts = list(
                    pool.map(lambda group: ask_reading(group, PART_CAP), groups)
                )
            labelled = "\n\n".join(
                f"Part {n} of {len(parts)}:\n{part}"
                for n, part in enumerate(parts, start=1)
            )
            user = "\n\n".join([prompts.COMBINING, turn.question, labelled])
            answer = one_call(_messages(ground.text, user, history), COMBINED_CAP)
            turn.cut_short = answer["finish_reason"] == "length"
            text = answer["text"].strip()

        opening = not_read_line(skipped)
        turn.answer = f"{opening}\n\n{text}".strip() if opening else text
        # The combined answer's Citations are checked again before display.
        turn.citations = citations(turn.answer, starts_by_number)
        turn.model = calls["model"]
        turn.state = DONE
        turn.reason_class = ""
        turn.answered_at = timezone.now()
        turn.save()
        _record(
            case,
            actor=chat.asked_by,
            templates=templates_line,
            model=turn.model,
            usage=usage,
            calls=calls,
            started=started,
            outcome="ok",
        )
    except engine.Problem as problem:
        turn.state = FAILED
        turn.reason_class = (
            THOUGHT_AWAY if isinstance(problem, ThoughtItAway) else problem.reason
        )
        turn.save(update_fields=["state", "reason_class", "reason_detail"])
        _record(
            case,
            actor=chat.asked_by,
            templates=templates_line,
            model=calls["model"],
            usage=usage,
            calls=calls,
            started=started,
            outcome=problem.reason,
            reason=problem.reason,
        )


def time_limit_for_the_question() -> int:
    return QUESTION_LIMIT * (2 if thinking() else 1)


def _messages(system: str, user: str, history: list[tuple[str, str]]):
    messages = [{"role": "system", "content": system}]
    for question, answer in history:
        messages.append({"role": "user", "content": question})
        messages.append({"role": "assistant", "content": answer})
    messages.append({"role": "user", "content": user})
    return messages


def _record(
    case,
    *,
    actor,
    templates: str,
    model: str,
    usage: dict,
    calls: dict,
    started: float,
    outcome: str,
    reason: str = "",
) -> None:
    """The case_chat_turn row: the Case as the object, metadata only."""
    from urllib.parse import urlparse

    audit.write(
        audit.Category.LLM,
        "AI assistant call",
        actor=actor,
        outcome=audit.Outcome.SUCCESS if outcome == "ok" else audit.Outcome.FAILURE,
        reason_class=reason,
        affected_user=(
            case.owner if actor is not None and case.owner_id != actor.pk else None
        ),
        object_type="case",
        object_id=case.pk,
        object_label=case.name,
        feature="case_chat_turn",
        transcripts_read=calls["read"],
        readings=calls["readings"],
        model=model or engine.model_name(),
        endpoint_host=urlparse(engine.address()).hostname or "",
        templates=templates,
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        duration_seconds=round(time.monotonic() - started, 1),
    )
