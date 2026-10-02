"""The Speaker check (Phase 5 chapter 3, v1.55.0).

After a Transcript lands with its Speakers told apart, the engine first reads
the whole of it once and writes a sketch of who is who (v1.100.0), then
reads it in windows of a few minutes, each given the sketch, and names the
lines whose words show they belong to a different Speaker than the one the
voice split gave them; a Transcript that fits the engine is checked in one
window. A sketch that cannot be written does not stop the check. Every answer
is checked here before it is kept: a real line, a Speaker already in the
Transcript, the label still what the engine was shown. What survives is a
Speaker correction, proposed and never applied: a person accepts it on the
Speakers page, through the same move a line makes by hand, with the same
audit row and the same Undo. The check never adds or merges a Speaker and
never touches a word.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import time
from collections import Counter

from django.db import transaction
from django.utils import timezone

from core import assistant, audit, engine, prompts, settings_store
from core.assistant import (
    DONE,
    FAILED,
    QUEUED,
    RUNNING,
    PromptTemplate,
    SpeakerCheck,
    SpeakerCorrection,
)

log = logging.getLogger(__name__)

LANDS, OVERNIGHT = "lands", "overnight"
FEATURE = "speaker_check"
# The lines a window carries over from the one before it, so a line at the
# edge still has its question or its answer in view.
OVERLAP_LINES = 6


# The switch and the offer -----------------------------------------------------------


def on() -> bool:
    """The check, from the settings alone: never the engine's minute check."""
    return bool(
        settings_store.get("assistant_available")
        and settings_store.get("speaker_check_available")
    )


def speakers_of(transcript) -> list[str]:
    """The Speakers a line may be moved among: every name on the Transcript."""
    # Ordered by the name before distinct, or the Segment's own ordering
    # would make every line its own row.
    return sorted(
        transcript.segments.filter(same_as_other_side=False)
        .exclude(speaker="")
        .order_by("speaker")
        .values_list("speaker", flat=True)
        .distinct()
    )


def possible(transcript) -> bool:
    """Whether there is anything to check: two Speakers or more, told apart."""
    if transcript is None or not transcript.recording.diarize:
        return False
    return len(speakers_of(transcript)) >= 2


def offered(transcript) -> bool:
    return on() and possible(transcript)


def busy(transcript) -> bool:
    return transcript.speaker_checks.filter(state__in=(QUEUED, RUNNING)).exists()


# Queueing ---------------------------------------------------------------------------


def seconds_until_the_night(now=None) -> int:
    """How long a check waits under the overnight position: until the Vision
    window opens, or nothing when it is open now."""
    from core import vision

    if vision.in_window(now):
        return 0
    moment = timezone.localtime(now or timezone.now())
    start, _ = vision.window()
    opens = moment.replace(
        hour=start.hour, minute=start.minute, second=0, microsecond=0
    )
    if opens <= moment:
        opens += dt.timedelta(days=1)
    return int((opens - moment).total_seconds())


def queue_check(recording, *, by=None, how: str = "landed") -> SpeakerCheck | None:
    """One check queued for this Recording's Transcript, now or at the night's
    start, if the switch is on and there is something to check. Nothing is
    queued twice."""
    transcript = getattr(recording, "transcript", None)
    if not offered(transcript) or busy(transcript):
        return None
    from core import tasks

    check = SpeakerCheck.objects.create(transcript=transcript, asked_by=by)
    wait = 0
    if by is None and settings_store.speaker_check_runs() == OVERNIGHT:
        wait = seconds_until_the_night()

    # Queued once the row is committed (v1.56.1): the transcript lands inside
    # a transaction, and a job taken up before the commit found no row and
    # left the check queued for good.
    def send():
        if wait:
            tasks.check_speakers.configure(schedule_in={"seconds": wait}).defer(
                check_id=str(check.pk)
            )
        else:
            tasks.check_speakers.defer(check_id=str(check.pk))

    transaction.on_commit(send)
    audit.write(
        audit.Category.RECORDINGS,
        "Speaker check queued",
        actor=by,
        affected_user=(
            recording.user if by is not None and recording.user_id != by.pk else None
        ),
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
        how=how,
        waits_seconds=wait,
    )
    return check


def on_transcript(recording) -> None:
    """The queue's hook, as each Transcript lands."""
    try:
        queue_check(recording)
    except Exception:  # noqa: BLE001 - the transcript is not held up by the check
        log.exception("speaker check for %s could not be queued", recording.pk)


# The run ----------------------------------------------------------------------------


def windows(lines: list, seconds: int) -> list[tuple[int, int]]:
    """Index spans over the lines, each about `seconds` of talk, each starting
    a few lines before the one before it ended."""
    out = []
    at = 0
    while at < len(lines):
        end = at
        while end < len(lines) and lines[end].start - lines[at].start < seconds:
            end += 1
        if end == at:
            end = at + 1
        out.append((max(0, at - OVERLAP_LINES), end))
        at = end
    return out


def queued_without_a_task(older_than_seconds: int = 120):
    """The checks marked queued with no task waiting or at them: what the
    minute sweep queues again (v1.56.1)."""
    stale = timezone.now() - dt.timedelta(seconds=older_than_seconds)
    return [
        one
        for one in SpeakerCheck.objects.filter(state=QUEUED, created__lt=stale)
        if not task_waiting_for(one)
    ]


def task_waiting_for(check) -> bool:
    """Whether a check_speakers job for this check is waiting or running.
    Read from the queue's own table; when that cannot be read, the answer is
    yes, so nothing is queued twice on a guess."""
    try:
        from procrastinate.contrib.django.models import ProcrastinateJob

        return ProcrastinateJob.objects.filter(
            task_name="check_speakers",
            status__in=("todo", "doing"),
            args__check_id=str(check.pk),
        ).exists()
    except Exception:  # noqa: BLE001 - the table is the queue's, not the app's
        return True


def sketch_of(
    transcript, speakers: list[str], ground_text: str
) -> tuple[str, bool, dict]:
    """The sketch of who is who (v1.100.0): one call over the whole Transcript,
    or as much as fits the engine. (sketch, cut, answer): the words, whether
    the transcript had to be cut to fit, and the engine's answer for the
    run's count of tokens. A problem gives an empty sketch and the check
    goes on without one."""
    lines = prompts.lines_of(transcript)
    system = prompts.system_message(ground_text, prompts.SPEAKER_SKETCH, "")
    cap = prompts.sketch_cap(speakers)
    room = assistant.window()
    kept = list(lines)
    cut = False
    while kept and not prompts.fits(
        system,
        prompts.speaker_sketch_input(kept, speakers, cut),
        answer_cap=cap,
        window=room,
    ):
        # Off the end, a tenth at a time, until it fits.
        kept = kept[: max(1, len(kept) - max(1, len(kept) // 10))]
        cut = True
        if len(kept) == 1:
            break
    if not kept:
        return "", cut, {}
    user = prompts.speaker_sketch_input(kept, speakers, cut)
    try:
        answer = engine.complete(
            assistant._messages(system, user),
            max_completion_tokens=cap,
            thinking=assistant.thinking(),
            timeout=assistant.time_limit(FEATURE),
            **assistant.SUGGESTION_SAMPLING,
        )
    except engine.Problem as problem:
        log.warning("speaker sketch for %s: %s", transcript.pk, problem.reason)
        return "", cut, {}
    words = " ".join(str(answer.get("text", "") or "").split())
    return words[: 400 * max(1, len(speakers)) + 400], cut, answer


# The voice and the second reading (v1.105.0) ----------------------------------------
#
# A line of this many words or fewer is never offered for a move on the
# words alone ("yeah", "okay, sir"): the words cannot settle it.
SHORT_LINE_WORDS = 3
# A line of this many timed words, every one given to its own Speaker by the
# voice step, is one the voice was firm on.
FIRM_WORDS = 12
# The lines before and after a marked line that the second reading sees, the
# lines one call reads, and the readings each line gets. The app keeps a
# move in front of the person only where the readings agree.
AROUND = 4
SECOND_BATCH = 20
SECOND_READINGS = 2
BACKED, ASIDE = SpeakerCorrection.BACKED, SpeakerCorrection.ASIDE
VOICE_AGREES = SpeakerCorrection.VOICE_AGREES
VOICE_AGAINST = SpeakerCorrection.VOICE_AGAINST


def voices_heard(transcript) -> dict:
    """What the voice step heard in each line, word by word: {segment id:
    Counter({Speaker's name: words})}. The service gives every timed word
    the label of the voice it fell under; a line is given to whoever holds
    most of its words, so a line with two voices in it shows here. The
    labels are the engine's own, turned to the names on the page by the
    name most lines of each label carry; a label spread over several names
    (a recording made in stretches) says nothing and is left out."""
    rows = list(
        transcript.segments.filter(same_as_other_side=False).values(
            "id", "side_id", "speaker", "speaker_label", "words"
        )
    )
    carried: dict = {}
    for row in rows:
        if row["speaker_label"] and row["speaker"]:
            carried.setdefault((row["side_id"], row["speaker_label"]), Counter())[
                row["speaker"]
            ] += 1
    name_of = {}
    for key, counts in carried.items():
        name, most = counts.most_common(1)[0]
        if most >= 0.8 * sum(counts.values()):
            name_of[key] = name
    heard = {}
    for row in rows:
        counts: Counter = Counter()
        for word in row["words"] or []:
            label = word.get("speaker") if isinstance(word, dict) else None
            name = name_of.get((row["side_id"], label))
            if name:
                counts[name] += 1
        heard[row["id"]] = counts
    return heard


def voice_of(heard: Counter, from_: str, to: str) -> tuple[str, str]:
    """What the voice step's own labels say of a move, and the note the
    second reading is given. VOICE_AGREES when the voice heard the other
    Speaker within the line; VOICE_AGAINST when the line is long and every
    word of it was given to the Speaker it is labelled with; nothing when
    the line is short or was not timed."""
    total = sum(heard.values())
    if not total:
        return "", ""
    theirs = heard.get(to, 0)
    if theirs >= 2 or (theirs and theirs / total >= 0.2):
        names = sorted(name for name, count in heard.items() if count)
        return (
            VOICE_AGREES,
            f"Voice: the voice step heard {' and '.join(names)} on this line.",
        )
    if total >= FIRM_WORDS and heard.get(from_, 0) == total:
        return (
            VOICE_AGAINST,
            f"Voice: the voice step gave all {total} words of this line to {from_}.",
        )
    return "", ""


def _second_look(
    transcript,
    lines: list,
    speakers: list[str],
    sketch: str,
    kept: dict,
    ground_text: str,
    usage: dict,
) -> dict:
    """Every move the check proposes, read again before a person sees it.
    Each kept move gains `second` (BACKED, ASIDE or nothing when no reading
    could be had), `aside_why` and `voice`. Nothing is dropped: a move set
    aside is still the person's to decide, shown apart. A reading that
    fails leaves the moves as the check made them."""
    summary = {
        "rows": len(kept),
        "backed": 0,
        "aside": 0,
        "short": 0,
        "voice_against": 0,
        "apart": 0,
        "unread": 0,
        "calls": 0,
    }
    if not kept:
        return summary
    heard = voices_heard(transcript)
    where = {line.segment_id: index for index, line in enumerate(lines)}
    notes: dict = {}
    to_read = []
    for one in kept.values():
        one["second"], one["aside_why"] = "", ""
        one["voice"], notes[one["segment_id"]] = voice_of(
            heard.get(one["segment_id"]) or Counter(), one["from"], one["to"]
        )
        if len(one["quote"].split()) <= SHORT_LINE_WORDS:
            one["second"] = ASIDE
            one["aside_why"] = "too short for the words to settle"
            summary["short"] += 1
        elif one["segment_id"] in where:
            to_read.append(one)
    system = prompts.system_message(
        ground_text, prompts.SPEAKER_SECOND, prompts.SPEAKER_SECOND_FORMAT
    )
    cap = settings_store.speaker_check_answer_cap()
    said: dict = {}
    for start in range(0, len(to_read), SECOND_BATCH):
        batch = to_read[start : start + SECOND_BATCH]
        blocks = []
        numbered = {}
        for one in batch:
            index = where[one["segment_id"]]
            numbered[lines[index].number] = one
            blocks.append(
                {
                    "line": lines[index],
                    "around": lines[max(0, index - AROUND) : index + AROUND + 1],
                    "voice": notes[one["segment_id"]],
                }
            )
        user = prompts.speaker_second_input(sketch, speakers, blocks)
        if not prompts.fits(system, user, answer_cap=cap, window=assistant.window()):
            continue
        for _ in range(SECOND_READINGS):
            try:
                answer = engine.complete(
                    assistant._messages(system, user),
                    max_completion_tokens=cap,
                    thinking=assistant.thinking(),
                    timeout=assistant.time_limit(FEATURE),
                    schema=prompts.speaker_second_schema(speakers),
                    # Not the check's own sampling: at zero the two readings
                    # would be one reading asked twice.
                    **assistant.SAMPLING,
                )
            except engine.Problem as problem:
                log.warning(
                    "speaker check for %s: a second reading could not be asked (%s)",
                    transcript.pk,
                    problem.reason,
                )
                continue
            summary["calls"] += 1
            usage["input_tokens"] += answer.get("input_tokens", 0) or 0
            usage["output_tokens"] += answer.get("output_tokens", 0) or 0
            try:
                try:
                    parsed = json.loads(answer["text"])
                except ValueError:
                    parsed = json.loads(prompts.salvage_json(answer["text"]))
                raw = parsed.get("readings", [])
                if not isinstance(raw, list):
                    raise ValueError("not a list")
            except (ValueError, AttributeError, TypeError):
                log.warning(
                    "speaker check for %s: a second reading was unreadable",
                    transcript.pk,
                )
                continue
            seen: set = set()
            for item in raw:
                if not isinstance(item, dict):
                    continue
                try:
                    number = int(item.get("line"))
                except (TypeError, ValueError):
                    continue
                one = numbered.get(number)
                if one is None or number in seen:
                    continue
                seen.add(number)
                said.setdefault(one["segment_id"], []).append(
                    str(item.get("speaker", "")).strip()
                )
    for one in to_read:
        readings = said.get(one["segment_id"], [])
        if len(readings) < SECOND_READINGS:
            summary["unread"] += 1
            continue
        if all(reading == one["to"] for reading in readings):
            if one["voice"] == VOICE_AGAINST:
                one["second"] = ASIDE
                one["aside_why"] = "the voice step was firm on this line"
                summary["voice_against"] += 1
            else:
                one["second"] = BACKED
            continue
        one["second"] = ASIDE
        if len(set(readings)) > 1:
            one["aside_why"] = "the two readings differed"
            summary["apart"] += 1
        elif readings[0] == one["from"]:
            one["aside_why"] = f"the second reading kept it with {one['from']}"[:120]
        elif readings[0] == prompts.CANNOT_TELL:
            one["aside_why"] = "the second reading could not tell"
        else:
            one["aside_why"] = f"the second reading gave it to {readings[0]}"[:120]
    summary["backed"] = sum(1 for one in kept.values() if one["second"] == BACKED)
    summary["aside"] = sum(1 for one in kept.values() if one["second"] == ASIDE)
    return summary


def run(check_id, attempt: int = 1) -> None:
    """The check: the sketch first, then one call per window, each given the
    sketch, the answers checked, the corrections kept in place of the
    pending ones. One audit row for the run, metadata only."""
    check = (
        SpeakerCheck.objects.filter(pk=check_id)
        .select_related("transcript", "transcript__recording")
        .first()
    )
    if check is None:
        # The job may still be taken up before the row is there (v1.56.1):
        # look again in a few seconds rather than take it for nothing.
        if attempt == 1:
            from core import tasks

            tasks.check_speakers.configure(
                schedule_in={"seconds": assistant.QUEUE_GRACE_SECONDS}
            ).defer(check_id=str(check_id), attempt=attempt + 1)
        return
    if check.state not in (QUEUED, RUNNING):
        return
    transcript = check.transcript
    recording = transcript.recording
    started = time.monotonic()
    ground = PromptTemplate.named(PromptTemplate.GROUND_RULES)
    template = PromptTemplate.named(PromptTemplate.SPEAKER_CHECK)
    templates_line = (
        f"ground-rules v{ground.version}; Speaker check v{template.version}"
    )
    check.state = RUNNING
    check.save(update_fields=["state"])

    usage = {"input_tokens": 0, "output_tokens": 0}
    model = ""
    kept: dict = {}
    calls = 0
    cut = 0
    sketch, sketch_cut, whole = "", False, False
    try:
        problem = assistant._unreachable()
        if problem:
            raise problem
        if not on():
            raise engine.Problem(engine.ERROR, "the speaker check is off")
        speakers = speakers_of(transcript)
        if len(speakers) < 2:
            raise engine.Problem(engine.ERROR, "fewer than two speakers")
        lines = prompts.lines_of(transcript)
        system = prompts.system_message(
            ground.text, template.text, prompts.SPEAKER_CHECK_FORMAT
        )
        answer_cap = settings_store.speaker_check_answer_cap()
        # The sketch of who is who (v1.100.0), given to every window.
        sketch, sketch_cut, told = sketch_of(transcript, speakers, ground.text)
        model = told.get("model", "") or model
        usage["input_tokens"] += told.get("input_tokens", 0) or 0
        usage["output_tokens"] += told.get("output_tokens", 0) or 0
        check.sketch = sketch
        check.save(update_fields=["sketch"])
        # The whole Transcript in one window when it fits the engine.
        whole = prompts.fits(
            system,
            prompts.speaker_check_input(lines, speakers, sketch),
            answer_cap=answer_cap,
            window=assistant.window(),
        )
        check.whole = whole
        sliced = windows(lines, settings_store.speaker_check_window_seconds())
        spans = [(0, len(lines))] if whole else sliced
        # Read whole, one call does the work of every window it replaced, so
        # it is given their time (v1.100.1: a busy engine timed the whole
        # read out at one window's limit).
        limit = assistant.time_limit(FEATURE) * (max(1, len(sliced)) if whole else 1)
        for start, end in spans:
            window = lines[start:end]
            user = prompts.speaker_check_input(window, speakers, sketch)
            if not prompts.fits(
                system, user, answer_cap=answer_cap, window=assistant.window()
            ):
                raise engine.Problem(engine.TOO_LONG, "a window is too long")
            answer = engine.complete(
                assistant._messages(system, user),
                max_completion_tokens=answer_cap,
                thinking=assistant.thinking(),
                timeout=limit,
                schema=prompts.speaker_check_schema(speakers),
                **assistant.SUGGESTION_SAMPLING,
            )
            calls += 1
            if answer.get("finish_reason") == "length":
                cut += 1
            model = answer.get("model", "") or model
            usage["input_tokens"] += answer.get("input_tokens", 0)
            usage["output_tokens"] += answer.get("output_tokens", 0)
            try:
                try:
                    parsed = json.loads(answer["text"])
                except ValueError:
                    parsed = json.loads(prompts.salvage_json(answer["text"]))
                raw = parsed.get("moves", [])
                if not isinstance(raw, list):
                    raise ValueError("not a list")
            except (ValueError, AttributeError):
                # One unreadable window is a lost window, not a lost run.
                log.warning(
                    "speaker check for %s: a window's answer was unreadable",
                    transcript.pk,
                )
                continue
            for one in prompts.keep_corrections(raw, window, speakers):
                kept.setdefault(one["segment_id"], one)
        # The second reading and the voice (v1.105.0), before a person sees
        # any of it; it marks the moves and loses none.
        check.second_look = _second_look(
            transcript, lines, speakers, sketch, kept, ground.text, usage
        )
        _store(transcript, kept)
        check.found = len(kept)
        check.windows = calls
        check.cut_short = cut
        check.state = DONE
        check.reason_class = ""
        check.finished_at = timezone.now()
        check.save()
        assistant._record(
            FEATURE,
            recording,
            actor=check.asked_by,
            templates=templates_line,
            model=model,
            usage=usage,
            started=started,
            outcome="ok",
            windows=calls,
            found=len(kept),
            cut_short=cut,
            sketch=bool(sketch),
            sketch_cut=sketch_cut,
            whole=whole,
            backed=check.second_look.get("backed", 0),
            set_aside=check.second_look.get("aside", 0),
            second_calls=check.second_look.get("calls", 0),
        )
    except engine.Problem as problem:
        # What was found before the problem is kept: every one passed the checks.
        if kept:
            _store(transcript, kept)
        check.found = len(kept)
        check.windows = calls
        check.cut_short = cut
        check.state = FAILED
        check.reason_class = problem.reason
        check.finished_at = timezone.now()
        check.save()
        assistant._record(
            FEATURE,
            recording,
            actor=check.asked_by,
            templates=templates_line,
            model=model,
            usage=usage,
            started=started,
            outcome=problem.reason,
            reason=problem.reason,
            windows=calls,
            found=len(kept),
            cut_short=cut,
            sketch=bool(sketch),
            sketch_cut=sketch_cut,
            whole=whole,
        )


def _store(transcript, kept: dict) -> None:
    """The pending corrections replaced by this run's; decided ones stay."""
    transcript.corrections.filter(state=SpeakerCorrection.PENDING).delete()
    dismissed = set(
        transcript.corrections.filter(state=SpeakerCorrection.DISMISSED).values_list(
            "segment_id", flat=True
        )
    )
    for one in kept.values():
        # A line somebody already dismissed a move for is not offered again.
        if one["segment_id"] in dismissed:
            continue
        SpeakerCorrection.objects.create(
            transcript=transcript,
            segment_id=one["segment_id"],
            start=one["start"],
            quote=one["quote"],
            speaker_from=one["from"],
            speaker_to=one["to"],
            reason=one["reason"],
            second=one.get("second", ""),
            aside_why=one.get("aside_why", ""),
            voice=one.get("voice", ""),
        )


# What the pages read ----------------------------------------------------------------


def score(transcript) -> dict:
    """The office's own measure (v1.105.0): of the corrections a person has
    decided on this Transcript, how many were accepted and dismissed among
    those the second reading backed, those it set aside, and those no second
    reading saw. Counts only."""
    out = {
        key: {"accepted": 0, "dismissed": 0} for key in ("backed", "aside", "unread")
    }
    for second, state in transcript.corrections.exclude(
        state=SpeakerCorrection.PENDING
    ).values_list("second", "state"):
        out[second or "unread"][state] = out[second or "unread"].get(state, 0) + 1
    return out


def state_json(transcript) -> dict:
    """The corrections pending and the last run, for the state answer."""
    from core import exports

    if transcript is None:
        return {"offered": False, "pending": [], "aside": [], "run": None}
    last = transcript.speaker_checks.first()
    pending = transcript.corrections.filter(state=SpeakerCorrection.PENDING)

    def row(one) -> dict:
        return {
            "id": str(one.pk),
            "segment": one.segment_id,
            "start": one.start,
            "clock": exports.clock(one.start),
            "quote": one.quote,
            "from": one.speaker_from,
            "to": one.speaker_to,
            "reason": one.reason,
            "second": one.second,
            "why": one.aside_why,
            "voice": one.voice,
        }

    rows = list(pending.order_by("start"))
    return {
        "offered": offered(transcript),
        # In front of the person: what the second reading backed, and what
        # no second reading saw. Set aside (v1.105.0): still theirs to
        # decide, shown apart, left by Accept all.
        "pending": [row(one) for one in rows if one.second != ASIDE],
        "aside": [row(one) for one in rows if one.second == ASIDE],
        "score": score(transcript),
        "run": (
            {
                "state": last.state,
                "found": last.found,
                "windows": last.windows,
                "cut_short": last.cut_short,
                # The sketch of who is who and whether the Transcript was
                # read whole (v1.100.0).
                "sketch": last.sketch,
                "whole": last.whole,
                # What the second reading did with the proposals (v1.105.0).
                "second_look": last.second_look or {},
                "said": assistant.what_to_say(last.reason_class)
                if last.reason_class
                else "",
                "when": timezone.localtime(last.finished_at or last.created).strftime(
                    "%d %b %Y %H:%M"
                ),
            }
            if last is not None
            else None
        ),
    }


def pending_count(transcript) -> int:
    if transcript is None:
        return 0
    # What asks for a person's attention: not the ones set aside (v1.105.0).
    return (
        transcript.corrections.filter(state=SpeakerCorrection.PENDING)
        .exclude(second=ASIDE)
        .count()
    )


# Deciding ---------------------------------------------------------------------------


def accept(correction: SpeakerCorrection, *, by, request=None) -> int:
    """One correction applied: the line moves as it would by hand. A line
    whose Speaker changed since the check is left where it is and the
    correction dismissed, never applied on a stale label."""
    from core import viewer

    segment = correction.segment
    transcript = correction.transcript
    if segment is None or segment.speaker != correction.speaker_from:
        correction.state = SpeakerCorrection.DISMISSED
        correction.decided_by = by
        correction.decided_at = timezone.now()
        correction.save(update_fields=["state", "decided_by", "decided_at"])
        return 0
    changed = viewer.move_line(
        transcript,
        segment,
        correction.speaker_to,
        by=by,
        request=request,
        event="Speaker correction accepted",
        how="check",
    )
    correction.state = SpeakerCorrection.ACCEPTED
    correction.decided_by = by
    correction.decided_at = timezone.now()
    correction.save(update_fields=["state", "decided_by", "decided_at"])
    return changed


def dismiss(correction: SpeakerCorrection, *, by, request=None) -> None:
    correction.state = SpeakerCorrection.DISMISSED
    correction.decided_by = by
    correction.decided_at = timezone.now()
    correction.save(update_fields=["state", "decided_by", "decided_at"])
    recording = correction.transcript.recording
    audit.write(
        audit.Category.EDITS,
        "Speaker correction dismissed",
        actor=by,
        request=request,
        affected_user=(
            recording.user if by is not None and recording.user_id != by.pk else None
        ),
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
    )
