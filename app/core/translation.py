"""Translation by the chat engine from the words as spoken (ADR 0026, Phase 1
chapter 7 "Translation from the words as spoken", v1.162.0).

Under the Qwen3-ASR recogniser (ADR 0025) a Recording is transcribed in the
language spoken and lands readable at once, each Segment carrying its
language. When Translate to English was asked (or the mixed rule applies),
a run follows: one row like the Speaker check's, one live per Transcript,
queued on commit to the llm queue, waiting while the engine is away as
Summaries tonight does. Only lines not in English are sent, in windows cut
to a token budget with a few lines of context, the lines numbered, one JSON
answer per line, checked line by line; each line keeps a hash of the spoken
text its English came from, so a Correction leaves that one line stale and
the next run writes it again. Both texts are kept: `Segment.text` the words
as spoken, `Segment.english` the engine's rendering. Every reader takes the
English when there is one, else the words as spoken (`reading`).

Nothing here is logged, exported or sent anywhere but the engine; the audit
rows carry counts.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import time

from django.db import IntegrityError, transaction
from django.utils import timezone

from core import assistant, audit, engine, expectation, prompts, settings_store
from core.assistant import DONE, FAILED, QUEUED, RUNNING, PromptTemplate, Translation

log = logging.getLogger(__name__)

FEATURE = "translation"
ENGLISH = "en"
# A queued run's reason while it waits for the engine; never a failure.
ENGINE_AWAY = "engine_away"
# A run done with lines it could not write, said on the page.
LINES_MISSING = "lines_missing"
# Lines sent around a window for the sentence to read whole; never answered.
CONTEXT_LINES = 3
# An English longer than this many times its source is not a translation.
LONGEST_RATIO = 4
# The hash kept on a line: enough to tell a changed text, never the text.
SIGNATURE_CHARS = 16
# "English not written: the engine was away all night" past this wait.
ALL_NIGHT = dt.timedelta(hours=8)
# "English ready" shows for this long after a run, then only the pill.
READY_SHOWS_FOR = dt.timedelta(hours=1)
# The answer's room: twice the source and a floor, under the window.
ANSWER_FLOOR_TOKENS = 600
# A window is cut at this share of the engine's window at most.
WINDOW_SHARE = 4


# What a line reads as -----------------------------------------------------------------


def signature(text: str) -> str:
    return hashlib.sha256((text or "").strip().encode("utf-8")).hexdigest()[
        :SIGNATURE_CHARS
    ]


def is_english(segment) -> bool:
    return (getattr(segment, "language", "") or "").lower().startswith(ENGLISH)


def reading(segment) -> str:
    """The English when the engine wrote one, else the words as spoken. A
    line-shaped object without the column (a test's stand-in, a Clip's
    excerpt row) reads as its words."""
    return getattr(segment, "english", "") or segment.text


def awaits(segment) -> bool:
    """A line said in another language whose English is not written, or is
    stale after a Correction."""
    if is_english(segment) or not (segment.text or "").strip():
        return False
    english = getattr(segment, "english", "")
    return not english or getattr(segment, "english_of", "") != signature(segment.text)


def to_do(transcript) -> list:
    """The lines a run has to write, in order."""
    rows = transcript.segments.filter(same_as_other_side=False).order_by("start", "id")
    return [one for one in rows if awaits(one)]


def awaits_any(transcript) -> bool:
    rows = transcript.segments.filter(same_as_other_side=False)
    return any(awaits(one) for one in rows)


# Whether the English is the engine's --------------------------------------------------


def asked(transcript) -> bool:
    """Whether the Recording asked for English: Translate to English, or
    the mixed rule on a Transcript found mixed."""
    recording = transcript.recording
    if recording.translate:
        return True
    return bool(settings_store.get("translate_mixed")) and bool(
        transcript.language_mixed
    )


def by_engine(transcript) -> bool:
    """A Transcript whose English is the chat engine's from the words as
    spoken: recognised by Qwen3-ASR, and English asked for. The exports, the
    notices and the pills key on this; under Whisper nothing moves."""
    from core import exports

    if transcript is None or exports.recogniser_of(transcript) != "qwen3-asr":
        return False
    return asked(transcript)


def offered() -> bool:
    """The engine is there to write with."""
    return bool(settings_store.get("assistant_available")) and engine.configured()


def wanted(transcript) -> bool:
    """Whether a run has anything to do now."""
    if transcript is None or not by_engine(transcript) or not offered():
        return False
    return bool(to_do(transcript))


# The run row --------------------------------------------------------------------------


def live():
    return Translation.objects.filter(state__in=(QUEUED, RUNNING))


def busy(transcript) -> bool:
    return transcript.translations.filter(state__in=(QUEUED, RUNNING)).exists()


def pending(transcript) -> bool:
    """A live run, or lines still waiting for one: what holds the batch mail."""
    if transcript is None or not by_engine(transcript):
        return False
    return busy(transcript)


def latest(transcript):
    if transcript is None:
        return None
    return transcript.translations.order_by("-created").first()


def queue_run(recording, *, by=None, how: str = "landed") -> Translation | None:
    """One run queued for this Recording's Transcript when there is something
    to write; nothing is queued twice."""
    transcript = getattr(recording, "transcript", None)
    if not wanted(transcript) or busy(transcript):
        return None
    from core import tasks

    lines = to_do(transcript)
    size = sum(prompts.tokens(one.text) for one in lines)
    try:
        with transaction.atomic():
            run_row = Translation.objects.create(
                transcript=transcript,
                asked_by=by,
                how=how,
                lines=len(lines),
                expectation=expectation.note(FEATURE, size),
            )
    except IntegrityError:
        return None

    def send():
        tasks.translate_lines.defer(translation_id=str(run_row.pk))

    transaction.on_commit(send)
    audit.write(
        audit.Category.RECORDINGS,
        "Translation queued",
        actor=by,
        affected_user=(
            recording.user if by is not None and recording.user_id != by.pk else None
        ),
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
        how=how,
        lines=len(lines),
    )
    return run_row


def on_transcript(recording) -> None:
    """The queue's hook, as each Transcript lands."""
    try:
        queue_run(recording)
    except Exception:  # noqa: BLE001 - the transcript is not held up by the run
        log.exception("translation for %s could not be queued", recording.pk)


def on_correction(segment, *, by=None) -> None:
    """A Correction on the words as spoken: the line's English is stale, and
    a run writes it again. The caller has saved the text."""
    transcript = segment.transcript
    if not by_engine(transcript):
        return
    if segment.english or segment.english_of:
        segment.english = ""
        segment.english_of = ""
        segment.save(update_fields=["english", "english_of"])
    try:
        queue_run(transcript.recording, by=by, how="corrected")
    except Exception:  # noqa: BLE001 - the correction stands whatever the run does
        log.exception("translation after a correction on %s", transcript.pk)


def again(recording, *, by=None) -> Translation | None:
    """Translate again, from the Details tab."""
    return queue_run(recording, by=by, how="again")


def queued_without_a_task(older_than_seconds: int = 120):
    """The runs marked queued with no task waiting or at them: what the
    minute sweep queues again, including the ones waiting for the engine."""
    stale = timezone.now() - dt.timedelta(seconds=older_than_seconds)
    return [
        one
        for one in Translation.objects.filter(state=QUEUED, created__lt=stale)
        if not task_waiting_for(one)
    ]


def task_waiting_for(run_row) -> bool:
    try:
        from procrastinate.contrib.django.models import ProcrastinateJob

        return ProcrastinateJob.objects.filter(
            task_name="translate_lines",
            status__in=("todo", "doing"),
            args__translation_id=str(run_row.pk),
        ).exists()
    except Exception:  # noqa: BLE001 - the table is the queue's, not the app's
        return True


# The windows --------------------------------------------------------------------------


def numbered(transcript) -> list[prompts.Line]:
    """Every line of the Transcript with the words as spoken, numbered from
    1, so a window's numbers and its context lines' are one scheme."""
    return prompts.lines_of(transcript, spoken=True)


def windows(lines: list[prompts.Line], asked_ids: set, budget: int) -> list[dict]:
    """The windows over the lines to write, each within the budget, each
    carrying up to CONTEXT_LINES lines either side for the sentence to read
    whole. A window is {"asked": [Line], "context": [Line]}."""
    wanted_lines = [one for one in lines if one.segment_id in asked_ids]
    if not wanted_lines:
        return []
    spans = assistant.digest_windows(wanted_lines, budget)
    by_index = {one.segment_id: index for index, one in enumerate(lines)}
    out = []
    for start, end in spans:
        asked_here = wanted_lines[start:end]
        first = by_index[asked_here[0].segment_id]
        last = by_index[asked_here[-1].segment_id]
        inside = {one.segment_id for one in asked_here}
        before = [
            one
            for one in lines[max(0, first - CONTEXT_LINES) : first]
            if one.segment_id not in inside
        ]
        after = [
            one
            for one in lines[last + 1 : last + 1 + CONTEXT_LINES]
            if one.segment_id not in inside
        ]
        out.append({"asked": asked_here, "context": before + after})
    return out


def window_input(window: dict, language_of: dict) -> str:
    """The user message: the lines in order, each with its language, the
    context lines marked as such."""
    rows = sorted(window["asked"] + window["context"], key=lambda one: one.number)
    inside = {one.segment_id for one in window["asked"]}
    out = []
    for line in rows:
        label = f" {line.speaker}:" if line.speaker.strip() else ""
        code = language_of.get(line.segment_id, "")
        tag = f" ({code})" if code else ""
        mark = "" if line.segment_id in inside else " (context, do not answer)"
        out.append(
            f"[{line.number}]{tag}{mark} {prompts.clock(line.start)}{label} "
            f"{line.text}".rstrip()
        )
    return "\n".join(out)


def keep_lines(raw, window: dict) -> dict:
    """The answer's lines that pass the checks: a number from this window's
    asked lines, an English that is a non-empty string and not absurdly long.
    {segment_id: english}."""
    by_number = {one.number: one for one in window["asked"]}
    kept: dict = {}
    if not isinstance(raw, list):
        return kept
    for one in raw:
        if not isinstance(one, dict):
            continue
        number = one.get("n")
        if not isinstance(number, int) or number not in by_number:
            continue
        english = one.get("english")
        if not isinstance(english, str) or not english.strip():
            continue
        source = by_number[number]
        if len(english) > LONGEST_RATIO * len(source.text) + 40:
            continue
        kept.setdefault(source.segment_id, english.strip())
    return kept


def _write(transcript, kept: dict, sources: dict) -> int:
    """The window's English written under the transcript's row lock, each
    line only while its words are still the ones the English came from."""
    from core.jobs import Segment, Transcript

    written = 0
    with transaction.atomic():
        Transcript.objects.select_for_update().get(pk=transcript.pk)
        for segment_id, english in kept.items():
            source = sources.get(segment_id, "")
            written += Segment.objects.filter(
                pk=segment_id, transcript=transcript, text=source
            ).update(english=english, english_of=signature(source))
    return written


def _budget() -> int:
    """A window's budget in tokens: the Digest's setting, held under a share
    of the engine's window so the answer, about as long again, fits."""
    return max(
        ANSWER_FLOOR_TOKENS,
        min(settings_store.digest_window_tokens(), assistant.window() // WINDOW_SHARE),
    )


# The run ------------------------------------------------------------------------------


def run(translation_id, attempt: int = 1) -> None:
    """One run: the lines to write, in windows, each a call; the English
    written as each window lands. The engine away leaves the row queued for
    the sweep. One audit row for the run, counts only."""
    run_row = (
        Translation.objects.filter(pk=translation_id)
        .select_related("transcript", "transcript__recording")
        .first()
    )
    if run_row is None:
        if attempt == 1:
            from core import tasks

            tasks.translate_lines.configure(
                schedule_in={"seconds": assistant.QUEUE_GRACE_SECONDS}
            ).defer(translation_id=str(translation_id), attempt=attempt + 1)
        return
    if run_row.state not in (QUEUED, RUNNING):
        return
    transcript = run_row.transcript
    recording = transcript.recording
    if not engine.is_reachable():
        # Waits, as Summaries tonight does: the sweep queues it again every
        # minute once the engine answers the minute check.
        if run_row.reason_class != ENGINE_AWAY:
            run_row.reason_class = ENGINE_AWAY
            run_row.save(update_fields=["reason_class"])
        return

    started = time.monotonic()
    ground = PromptTemplate.named(PromptTemplate.GROUND_RULES)
    template = PromptTemplate.named(PromptTemplate.TRANSLATION)
    templates_line = f"ground-rules v{ground.version}; Translation v{template.version}"
    run_row.state = RUNNING
    run_row.reason_class = ""
    run_row.started_at = timezone.now()
    run_row.expectation = expectation.started(run_row.expectation)
    run_row.save(update_fields=["state", "reason_class", "started_at", "expectation"])

    usage = {"input_tokens": 0, "output_tokens": 0}
    model = ""
    calls = 0
    written = 0
    lost = 0
    try:
        if not offered():
            raise engine.Problem(engine.ERROR, "the AI assistant is off")
        system = prompts.system_message(
            ground.text, template.text, prompts.TRANSLATION_FORMAT
        )
        limit = assistant.time_limit(FEATURE)
        budget = _budget()
        # Twice over: the lines to write, then once more for what the first
        # pass left (a missing number, a rejected English, a lost window).
        for round_number in (1, 2):
            todo = to_do(transcript)
            if not todo:
                break
            lines = numbered(transcript)
            language_of = {one.pk: one.language for one in todo}
            sources = {one.pk: one.text for one in todo}
            spans = windows(lines, set(sources), budget)
            if round_number == 1:
                run_row.windows = len(spans)
                run_row.lines = len(todo)
                run_row.save(update_fields=["windows", "lines"])
            for window in spans:
                user = window_input(window, language_of)
                asked_text = "\n".join(one.text for one in window["asked"])
                answer_cap = max(ANSWER_FLOOR_TOKENS, 2 * prompts.tokens(asked_text))
                if not prompts.fits(
                    system, user, answer_cap=answer_cap, window=assistant.window()
                ):
                    raise engine.Problem(engine.TOO_LONG, "a window is too long")
                answer = engine.complete(
                    assistant._messages(system, user),
                    max_completion_tokens=answer_cap,
                    thinking=False,
                    timeout=limit,
                    schema=prompts.translation_schema(),
                    **assistant.SUGGESTION_SAMPLING,
                )
                calls += 1
                model = answer.get("model", "") or model
                usage["input_tokens"] += answer.get("input_tokens", 0)
                usage["output_tokens"] += answer.get("output_tokens", 0)
                try:
                    try:
                        parsed = json.loads(answer["text"])
                    except ValueError:
                        parsed = json.loads(prompts.salvage_json(answer["text"]))
                    raw = parsed.get("lines", [])
                except (ValueError, AttributeError):
                    # One unreadable window is a lost window, not a lost run.
                    lost += 1
                    log.warning(
                        "translation for %s: a window's answer was unreadable",
                        transcript.pk,
                    )
                    raw = []
                kept = keep_lines(raw, window)
                written += _write(transcript, kept, sources)
                if round_number == 1:
                    run_row.windows_done += 1
                    run_row.lines_written = written
                    run_row.save(update_fields=["windows_done", "lines_written"])
        missing = len(to_do(transcript))
        run_row.lines_written = written
        run_row.lines_missing = missing
        run_row.state = DONE
        run_row.reason_class = LINES_MISSING if missing else ""
        run_row.finished_at = timezone.now()
        run_row.save()
        if written:
            # The English changes what a Reading holds (Phase 9 chapter 6,
            # v1.163.0): the share is counted again at the next draw.
            from core import one_reading

            one_reading.changed(transcript)
        assistant._record(
            FEATURE,
            recording,
            actor=run_row.asked_by,
            templates=templates_line,
            model=model,
            usage=usage,
            started=started,
            outcome="ok",
            windows=calls,
            lines=run_row.lines,
            written=written,
            missing=missing,
            lost=lost,
            how=run_row.how,
            **expectation.for_audit(run_row.expectation),
        )
    except engine.Problem as problem:
        run_row.lines_written = written
        run_row.lines_missing = len(to_do(transcript))
        run_row.state = FAILED
        run_row.reason_class = problem.reason
        run_row.finished_at = timezone.now()
        run_row.save()
        assistant._record(
            FEATURE,
            recording,
            actor=run_row.asked_by,
            templates=templates_line,
            model=model,
            usage=usage,
            started=started,
            outcome=problem.reason,
            reason=problem.reason,
            windows=calls,
            lines=run_row.lines,
            written=written,
            missing=run_row.lines_missing,
            lost=lost,
            how=run_row.how,
        )
    finally:
        # The batch mail waited for this (ADR 0026); whatever happened, it
        # may go now.
        try:
            from core import mail

            mail.note_batch_progress(recording)
        except Exception:  # noqa: BLE001 - the mail is never the run's failure
            log.exception("translation for %s: the batch mail", transcript.pk)


# The words on the pages ---------------------------------------------------------------


def words(transcript, brief: bool = False) -> tuple[str, str]:
    """What the head, a row and Home say about the English, in Vision's
    family of words; nothing for a Transcript that is not the engine's to
    translate. `brief` is the row's one or two words."""
    if transcript is None or not by_engine(transcript):
        return "", ""
    run_row = latest(transcript)
    if run_row is None:
        if awaits_any(transcript) and offered():
            return "English to follow", "warn"
        return "", ""
    if run_row.state == QUEUED:
        if (
            run_row.reason_class == ENGINE_AWAY
            and timezone.now() - run_row.created > ALL_NIGHT
        ):
            return (
                "English not written: the engine was away all night",
                "danger",
            )
        return "English to follow", "warn"
    if run_row.state == RUNNING:
        said = f"English, {run_row.windows_done} of {run_row.windows or '?'}"
        if not brief:
            seconds, measured = expectation.expect(
                FEATURE, int((run_row.expectation or {}).get("size_tokens") or 0)
            )
            said += " · " + expectation.words(seconds, measured)
        return said, "warn"
    if run_row.state == DONE:
        if run_row.lines_missing:
            count = run_row.lines_missing
            lines = "line" if count == 1 else "lines"
            said = f"English for {count} {lines} not written"
            return (said if brief else said + " · Translate again"), "danger"
        fresh = run_row.finished_at and (
            timezone.now() - run_row.finished_at < READY_SHOWS_FOR
        )
        if fresh:
            return ("" if brief else "English ready"), "ok"
        return "", ""
    why = assistant.what_to_say(run_row.reason_class)
    return f"English not written: {why}", "danger"


def state_json(transcript) -> dict:
    """What the page polls for: the words and where the run stands."""
    said, tone = words(transcript)
    run_row = latest(transcript)
    return {
        "words": said,
        "tone": tone,
        "state": run_row.state if run_row else "",
        "windows": run_row.windows if run_row else 0,
        "done": run_row.windows_done if run_row else 0,
        "missing": run_row.lines_missing if run_row else 0,
        "pending": pending(transcript),
    }


def mail_line(recordings) -> str:
    """The Batch-finished mail's line about the English, when any Recording
    had it written or waiting."""
    counted = 0
    written = 0
    for one in recordings:
        transcript = getattr(one, "transcript", None)
        if transcript is None or not by_engine(transcript):
            continue
        counted += 1
        if not awaits_any(transcript):
            written += 1
    if not counted:
        return ""
    if written == counted:
        return (
            "The English was written from the words as spoken for "
            f"{'the recording' if counted == 1 else f'all {counted} recordings'}."
        )
    return (
        f"The English was written from the words as spoken for {written} of "
        f"{counted} recordings; the rest read in the language spoken."
    )
