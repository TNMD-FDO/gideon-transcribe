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

from django.db import IntegrityError, transaction
from django.utils import timezone

from core import (
    assistant,
    audit,
    call_system,
    engine,
    prompts,
    settings_store,
    voice_book,
)
from core.assistant import (
    DONE,
    FAILED,
    QUEUED,
    RUNNING,
    PromptTemplate,
    SpeakerCheck,
    SpeakerCorrection,
    SuggestionRun,
)

log = logging.getLogger(__name__)

LANDS, OVERNIGHT = "lands", "overnight"
FEATURE = "speaker_check"
# The lines a window carries over from the one before it, so a line at the
# edge still has its question or its answer in view.
OVERLAP_LINES = 6
# The most windows' worth of time a whole read is given (v1.134.0).
WHOLE_READ_WINDOWS = 4


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
    from core import call_system

    return sorted(
        transcript.segments.filter(same_as_other_side=False)
        .exclude(speaker="")
        .exclude(speaker=call_system.NAME)
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


def queue_check(
    recording, *, by=None, how: str = "landed", mode: str = ""
) -> SpeakerCheck | None:
    """One check queued for this Recording's Transcript, now or at the night's
    start, if the switch is on and there is something to check. Nothing is
    queued twice."""
    transcript = getattr(recording, "transcript", None)
    if not offered(transcript) or busy(transcript):
        return None
    from core import tasks

    try:
        with transaction.atomic():
            check = SpeakerCheck.objects.create(
                transcript=transcript,
                asked_by=by,
                # Voices first (v1.145.0): the words' run asked for at stage 3.
                second_look={"mode": mode} if mode else {},
            )
    except IntegrityError:
        # Two asks at once: the database keeps one live check (v1.131.0).
        return None
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
    lines = prompts.lines_of(transcript, without_system=True)
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
        # Never thinking (v1.134.0), as the proposals are not: the sketch is
        # a reading of the words, and a small model thinks the cap away.
        answer = engine.complete(
            assistant._messages(system, user),
            max_completion_tokens=cap,
            thinking=False,
            timeout=assistant.time_limit(FEATURE),
            **assistant.SUGGESTION_SAMPLING,
        )
    except engine.Problem as problem:
        log.warning("speaker sketch for %s: %s", transcript.pk, problem.reason)
        return "", cut, {}
    words = " ".join(str(answer.get("text", "") or "").split())
    return words[: 400 * max(1, len(speakers)) + 400], cut, answer


# A line of this many timed words, every one given to its own Speaker by the
# voice step, is one the voice was firm on.
FIRM_WORDS = 12
# The lines before and after a marked line that the second reading sees, the
# lines one call reads, and the readings each line gets. The app keeps a
# move in front of the person only where the readings agree.
# The cards (v1.128.0): a Speaker card appears when this share of a label's
# lines, and at least this many, read as one other Speaker; Merge is the
# primary button only above MERGE_SHARE with the voice step hearing the
# other Speaker on enough of them. A stretch is a run of moves between the
# same two Speakers no further apart than STRETCH_GAP seconds. All set
# by the build and read against the office's recordings by ear.
CARD_SHARE = 0.2
CARD_LEAST = 5
MERGE_SHARE = 0.5
MERGE_VOICE_SHARE = 0.3
MERGE_VOICE_LEAST = 3
STRETCH_GAP = 20.0
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


def _voice_notes(transcript, kept: dict, check=None, doubt: bool = False) -> dict:
    """The voice's word on each proposed line, and its own proposals.

    With the voice on for the Recording's type (ADR 0021, v1.139.0) the
    service reads every line's own words and the voice says agrees, against
    or nothing (cannot tell) of each move the words made, calibrated on the
    recording's own lines; lines far from their own Speaker's print and near
    another's join the proposals as the voice's own, under a cap; a second
    voice under one label is kept as a Hand-over for the run to store. The
    vectors are kept on the run while its proposals are pending. With the
    voice off, or the service unable to answer, the word labels of v1.105.0
    are the one measure, as before, and the summary says so."""
    from core import voices

    summary = {
        "rows": len(kept),
        "voice_agrees": 0,
        "voice_against": 0,
        "silent": 0,
        "voice": "words",
        "voice_proposals": 0,
        "handovers": [],
    }
    recording = transcript.recording
    judge = None
    if voices.on_for(recording):
        try:
            answer = voices.ask(transcript)
            judge = voices.Judge(
                transcript, answer["stretches"], voices.floor_for(recording)
            )
            # The phone system's voice (v1.159.0): taught from the Call
            # system's lines, and the lines its voice gives or would give.
            # A line given moves to the Call system, so the judge is built
            # again without it.
            from core import system_voices

            summary["phone_system"] = system_voices.on_voices(
                transcript, answer["stretches"], judge
            )
            if summary["phone_system"].get("given"):
                judge = voices.Judge(
                    transcript, answer["stretches"], voices.floor_for(recording)
                )
            if check is not None:
                check.voices = voices.dump(answer)
            summary["voice"] = "titanet"
            summary["cost"] = answer["cost"]
            summary.update(voices.counts(judge))
            _write_fits(transcript, judge)
            # One vector per label kept for the Case's prints (v1.144.0).
            from core import voice_prints

            voice_prints.keep_prints(check, judge)
        except voices.Unavailable as why:
            summary["voice"] = "unavailable"
            summary["voice_unavailable"] = str(why)[:120]
            log.warning(
                "speaker check for %s: the voices could not be read: %s",
                transcript.pk,
                why,
            )
    heard = voices_heard(transcript) if judge is None and kept else {}
    for one in kept.values():
        one["second"], one["aside_why"] = "", ""
        one.setdefault("source", SpeakerCorrection.WORDS)
        if judge is not None:
            word, _note = judge.word(one["segment_id"], one["from"], one["to"])
            one["voice"] = "" if word == voices.CANNOT else word
        else:
            one["voice"], _ = voice_of(
                heard.get(one["segment_id"]) or Counter(), one["from"], one["to"]
            )
    if judge is not None and doubt:
        # Voices first (v1.145.0): the lines in doubt, from the voice alone.
        from core import voices_first

        summary["doubt"] = voices_first.doubt_rows(transcript, judge, kept)
        summary["voice_proposals"] = summary["doubt"]["near"]
        summary["handovers"] = judge.handovers()
    elif judge is not None:
        from core.jobs import Segment

        proposals = judge.own_proposals(set(kept), voices.CAP)
        lines = {
            seg.pk: seg
            for seg in Segment.objects.filter(
                pk__in=[p["segment_id"] for p in proposals]
            )
        }
        for one in proposals:
            seg = lines.get(one["segment_id"])
            if seg is None or seg.speaker != one["from"]:
                continue
            kept[one["segment_id"]] = {
                "segment_id": one["segment_id"],
                "start": seg.start,
                "quote": (seg.text or "")[:300],
                "from": one["from"],
                "to": one["to"],
                "reason": f"the voice sounds like {one['to']}",
                "voice": VOICE_AGREES,
                "source": SpeakerCorrection.VOICE,
            }
            summary["voice_proposals"] += 1
        summary["handovers"] = judge.handovers()
    for one in kept.values():
        if one.get("voice") == VOICE_AGREES:
            summary["voice_agrees"] += 1
        elif one.get("voice") == VOICE_AGAINST:
            summary["voice_against"] += 1
        else:
            summary["silent"] += 1
    summary["rows"] = len(kept)
    return summary


def _store_handovers(transcript, check, found: list) -> None:
    """This run's Hand-overs in place of the pending ones (ADR 0021)."""
    from core.assistant import Handover

    with transaction.atomic():
        transcript.handovers.filter(state=Handover.PENDING).delete()
        dismissed = {
            (one.speaker, round(one.at))
            for one in transcript.handovers.filter(state=Handover.DISMISSED)
        }
        for one in found:
            if (one["speaker"], round(one["at"])) in dismissed:
                continue
            Handover.objects.create(
                transcript=transcript,
                run=check,
                speaker=one["speaker"],
                side=one.get("side"),
                at=one["at"],
                lines_after=one["lines_after"],
                voices=one["voices"],
                loudness_gap_db=one["loudness_gap_db"],
                held=one["held"],
            )


def rescore(transcript) -> int:
    """After a move (ADR 0021: accept re-scores the rest): the voice's word
    on every pending correction, from the vectors the last run kept and the
    Speakers as they stand now. Returns how many words changed. When nothing
    is pending any more the vectors are deleted."""
    from core import voices
    from core.assistant import Handover

    settle_moot(transcript)
    last = transcript.speaker_checks.exclude(voices={}).first()
    if last is None:
        return 0
    pending = list(transcript.corrections.filter(state=SpeakerCorrection.PENDING))
    open_handovers = transcript.handovers.filter(
        state=Handover.PENDING, held=False
    ).exists()
    if not pending and not open_handovers:
        last.voices = {}
        last.save(update_fields=["voices"])
        return 0
    try:
        judge = voices.judge_from(transcript, last.voices)
    except Exception:  # noqa: BLE001 - a run's vectors never break a person's move
        log.exception(
            "speaker check for %s: the run's vectors could not be read; "
            "the move stands and the proposals keep their words",
            transcript.pk,
        )
        return 0
    if judge is None:
        return 0
    _write_fits(transcript, judge)
    changed = 0
    for one in pending:
        word, _ = judge.word(one.segment_id, one.speaker_from, one.speaker_to)
        word = "" if word == voices.CANNOT else word
        if word != one.voice:
            one.voice = word
            one.save(update_fields=["voice"])
            changed += 1
    return changed


def _write_fits(transcript, judge) -> int:
    """Each line's closeness to its own speaker's print (v1.142.0), kept on
    the line as a score so the Speakers page's samples are the lines the
    recording itself agrees are that voice. A line the voice could not
    measure is cleared. Returns how many lines got a score."""
    from core.jobs import Segment

    fits: dict[int, float | None] = {}
    for sid in judge.stretches:
        try:
            pk = int(sid)
        except (TypeError, ValueError):
            continue
        own = judge.name_of(sid)
        fits[pk] = judge.cos_to(sid, own) if own else None
    rows = list(transcript.segments.filter(same_as_other_side=False))
    for seg in rows:
        seg.voice_fit = fits.get(seg.pk)
    Segment.objects.bulk_update(rows, ["voice_fit"], batch_size=500)
    return sum(1 for one in fits.values() if one is not None)


def settle_moot(transcript) -> int:
    """A pending correction whose line no longer carries the label the check
    saw (moved by hand, a merge, a swap or a split since) is moot: it is
    closed as dismissed with no decider, so the page's count reads right
    and the run's vectors are let go once nothing waits (v1.140.0; before
    it such rows were left out of the page and stayed pending for good)."""
    stamp = timezone.now()
    closed = 0
    for one in transcript.corrections.filter(
        state=SpeakerCorrection.PENDING
    ).select_related("segment"):
        if one.segment is not None and one.segment.speaker == one.speaker_from:
            continue
        one.state = SpeakerCorrection.DISMISSED
        one.aside_why = "the line moved since the check"
        one.decided_at = stamp
        one.save(update_fields=["state", "aside_why", "decided_at"])
        closed += 1
    return closed


def _names_pass(check) -> None:
    """The one run (ADR 0021; v1.140.0): with Speaker suggestions on, the
    check's job goes on to Suggest names for the same Transcript, so one
    press, or the landing, proposes the moves and the names together. The
    names are a second engine call with their own audit row; what they
    found is counted on the check so the page's line can say so. A problem
    with the names never fails the check."""
    transcript = check.transcript
    try:
        if not assistant.features()["suggestions"]:
            return
        if len(assistant.unnamed_speakers(transcript)) < 2:
            # Suggest names' two-speaker rule; the page says so (v1.141.0).
            check.second_look["names"] = None
            check.second_look["names_state"] = "too_few"
            check.save(update_fields=["second_look"])
            return
        if transcript.suggestion_runs.filter(state__in=(QUEUED, RUNNING)).exists():
            return
        names = SuggestionRun.objects.create(
            transcript=transcript, asked_by=check.asked_by
        )
        assistant.suggest_names(names.pk)
        names.refresh_from_db()
        check.second_look["names"] = names.found if names.state == DONE else None
        check.second_look["names_state"] = names.state
        check.save(update_fields=["second_look"])
    except Exception:  # noqa: BLE001 - the check is done whatever the names did
        log.exception("speaker check for %s: the names pass failed", transcript.pk)


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
    # The Call system's pass, where the transcript never had it (v1.147.2):
    # before the run, so its lines are nobody's to move or to name.
    call_system.mark_if_missed(transcript)
    # The clock verdict a transcript from before v1.151.0 never had: before
    # the voice measures anything, so a marked line gives no vector.
    from core import clock_check

    clock_check.mark_if_missed(transcript)
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
        # Voices first (v1.145.0): where the voice listens, the arrival run
        # is the voice's; the words run for names only, and over the whole
        # call at stage 3. With the voice unreadable the words run as before.
        from core import voices_first

        mode = voices_first.mode_of(check) or (
            voices_first.VOICES
            if voices_first.on_for(recording)
            else voices_first.WORDS
        )
        if mode == voices_first.VOICES and voices_first.arrival(
            check, transcript, recording
        ):
            return
        lines = prompts.lines_of(transcript, without_system=True)
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
        # read out at one window's limit), up to WHOLE_READ_WINDOWS of it
        # (v1.134.0: three hours of windows made a limit of 54 minutes, and
        # a call that has not answered in four windows' time is not coming).
        limit = assistant.time_limit(FEATURE) * (
            min(max(1, len(sliced)), WHOLE_READ_WINDOWS) if whole else 1
        )
        for start, end in spans:
            window = lines[start:end]
            user = prompts.speaker_check_input(window, speakers, sketch)
            if not prompts.fits(
                system, user, answer_cap=answer_cap, window=assistant.window()
            ):
                raise engine.Problem(engine.TOO_LONG, "a window is too long")
            # Never thinking (v1.134.0), as the proposals are not: the answer
            # is a schema's worth of moves, and the cap is the moves' room.
            answer = engine.complete(
                assistant._messages(system, user),
                max_completion_tokens=answer_cap,
                thinking=False,
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
        # The voice's word on each move, its own proposals and the
        # Hand-overs (ADR 0021, v1.139.0); the word labels alone before it.
        check.second_look = _voice_notes(transcript, kept, check)
        _store(transcript, kept)
        _store_handovers(transcript, check, check.second_look.get("handovers") or [])
        check.second_look["handovers"] = len(check.second_look.get("handovers") or [])
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
            voice_agrees=check.second_look.get("voice_agrees", 0),
            voice_against=check.second_look.get("voice_against", 0),
        )
        # The one run (ADR 0021, V3): the names, in the same job.
        _names_pass(check)
        # The Case remembers (V4, v1.144.0): each unnamed voice against the
        # Case's prints; a failure here never fails the run.
        try:
            from core import voice_prints

            voice_prints.match(check)
        except Exception:  # noqa: BLE001 - a match is a proposal, never the run
            log.exception(
                "speaker check for %s: the voice matches failed", transcript.pk
            )
        # Voices first (v1.145.0): the words have run; the page's stage follows.
        voices_first.after_words_run(check)
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
    with transaction.atomic():
        _store_under_the_lock(transcript, kept)


def _store_under_the_lock(transcript, kept: dict) -> None:
    from core.jobs import Transcript

    # The transcript's row is the lock the speaker tools take too (v1.131.0),
    # so a merge following corrections never meets a row this delete took.
    Transcript.objects.select_for_update().get(pk=transcript.pk)
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
            source=one.get("source", SpeakerCorrection.WORDS),
            words=one.get("words", ""),
            split_at=one.get("split_at"),
            split_part=one.get("split_part", ""),
        )


# Hand-overs (ADR 0021) ---------------------------------------------------------------


def accept_handover(handover, *, by, request=None, into: str = "") -> str:
    """A person's Yes: the label is split at the time into a new Speaker, or
    into the speaker or person they picked (v1.142.0), as one change with
    Undo. Returns the Speaker's name, or "" when no line of the label lies
    after the time any more."""
    from core import viewer

    made = viewer.split_speaker(
        handover.transcript,
        handover.speaker,
        handover.at,
        by=by,
        request=request,
        into=into,
    )
    handover.state = handover.ACCEPTED if made else handover.DISMISSED
    handover.made = made or ""
    handover.decided_by = by
    handover.decided_at = timezone.now()
    handover.save(update_fields=["state", "made", "decided_by", "decided_at"])
    rescore(handover.transcript)
    return made or ""


def dismiss_handover(handover, *, by, request=None) -> None:
    handover.state = handover.DISMISSED
    handover.decided_by = by
    handover.decided_at = timezone.now()
    handover.save(update_fields=["state", "decided_by", "decided_at"])
    rescore(handover.transcript)
    recording = handover.transcript.recording
    audit.write(
        audit.Category.EDITS,
        "Hand-over dismissed",
        actor=by,
        request=request,
        affected_user=(
            recording.user if by is not None and recording.user_id != by.pk else None
        ),
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
    )


# What the pages read ----------------------------------------------------------------


def score(transcript) -> dict:
    """The office's own measure: of the corrections a person has decided on
    this Transcript, how many were accepted and how many dismissed."""
    out = {"accepted": 0, "dismissed": 0}
    for state in transcript.corrections.exclude(
        state=SpeakerCorrection.PENDING
    ).values_list("state", flat=True):
        out[state] = out.get(state, 0) + 1
    return out


def follow(transcript, was: str, now: str, by=None) -> dict:
    """The pending corrections follow a rename or a merge of `was` into
    `now` (v1.129.0), so a yes on a Speaker card settles what it should
    and the rest stay in view under the new label:

    - a correction that proposed exactly this (its line was `was`'s and it
      read as `now`'s) is accepted: the merge did what it asked;
    - one that proposed another Speaker for a line of `was` keeps its
      proposal, now from `now`;
    - one that proposed `was` for another Speaker's line now proposes
      `now`, unless that is the line's own label, in which case it is moot
      and dismissed.

    Returns what changed, by id, for Undo to put back."""
    stamp = timezone.now()
    pending = transcript.corrections.filter(state=SpeakerCorrection.PENDING)
    done = {"accepted": [], "from": [], "to": [], "moot": []}
    for one in pending.filter(speaker_from=was):
        if one.speaker_to == now:
            one.state = SpeakerCorrection.ACCEPTED
            one.decided_by = by
            one.decided_at = stamp
            one.save(update_fields=["state", "decided_by", "decided_at"])
            done["accepted"].append(str(one.pk))
        else:
            one.speaker_from = now
            one.save(update_fields=["speaker_from"])
            done["from"].append(str(one.pk))
    for one in pending.filter(speaker_to=was):
        one.speaker_to = now
        if one.speaker_from == now:
            one.state = SpeakerCorrection.DISMISSED
            one.decided_by = by
            one.decided_at = stamp
            one.save(update_fields=["speaker_to", "state", "decided_by", "decided_at"])
            done["moot"].append(str(one.pk))
        else:
            one.save(update_fields=["speaker_to"])
            done["to"].append(str(one.pk))
    return {key: ids for key, ids in done.items() if ids}


def unfollow(transcript, was: str, now: str, followed: dict | None) -> int:
    """Undo of a rename or a merge puts its corrections back as they were
    (v1.129.0): the accepted and the moot are pending again, and the
    labels that followed the change follow it back."""
    if not followed:
        return 0
    rows = transcript.corrections
    count = 0
    for pk in followed.get("accepted", []) + followed.get("moot", []):
        count += rows.filter(pk=pk).update(
            state=SpeakerCorrection.PENDING, decided_by=None, decided_at=None
        )
    for pk in followed.get("moot", []):
        rows.filter(pk=pk).update(speaker_to=was)
    for pk in followed.get("from", []):
        count += rows.filter(pk=pk, speaker_from=now).update(speaker_from=was)
    for pk in followed.get("to", []):
        count += rows.filter(pk=pk, speaker_to=now).update(speaker_to=was)
    return count


def _relabel(text: str, was: str, now: str) -> str:
    """The old label, as a whole word, becomes the new name in a sentence."""
    import re

    if not text or not was:
        return text
    return re.sub(r"(?<![\w-])" + re.escape(was) + r"(?![\w-])", now, text)


def reread_after_name(
    transcript, was: str, now: str, *, by=None, followed: dict | None = None
) -> dict:
    """The re-read after a name (v1.144.1; the drawing
    phase-5-reread-after-a-name.html): once a label has taken a name (a
    rename, a merge, a Sounds like accepted, a suggestion accepted), the
    pending proposals are rewritten with the current names, the name
    suggestions for a label now named are closed, the labels' kept prints
    follow the name and the unnamed voices are matched again against the
    Case's prints (the one just taught among them), and the voice's word is
    re-scored. No engine call. A note of what changed, in counts and ids,
    goes on the newest finished run for the page to show; an undo back to a
    label (`now` is a label) takes the note away."""
    from core import voice_prints
    from core.assistant import Suggestion, VoiceMatch, _is_a_label

    followed = followed or {}
    last = transcript.speaker_checks.filter(state=DONE).first()
    note: dict = {
        "for": now,
        "was": was,
        "at": timezone.now().isoformat(timespec="seconds"),
        "settled": list(followed.get("accepted", [])) + list(followed.get("moot", [])),
        "touched": list(followed.get("from", [])) + list(followed.get("to", [])),
        "closed": [],
        "new_matches": [],
        "reread": 0,
    }
    # The words: every pending proposal's reason, with the current names.
    if was:
        for one in transcript.corrections.filter(state=SpeakerCorrection.PENDING):
            fixed = _relabel(one.reason, was, now)
            if fixed != one.reason:
                one.reason = fixed
                one.save(update_fields=["reason"])
                if str(one.pk) not in note["touched"]:
                    note["touched"].append(str(one.pk))
    # The names: a suggestion for a label that is now named has nothing left
    # to say; it is closed, not rejected, and the card says so once.
    if was and not _is_a_label(now):
        from core import exports

        for one in transcript.suggestions.filter(
            state=Suggestion.PENDING, speaker__in=[was, now]
        ):
            one.state = Suggestion.CLOSED
            one.save(update_fields=["state"])
            note["closed"].append(
                {
                    "name": one.name,
                    "clock": exports.clock(one.start),
                    "start": one.start,
                }
            )
    # The prints kept on the runs follow the name.
    if was:
        for check in transcript.speaker_checks.exclude(prints={}):
            prints = dict(check.prints or {})
            if was in prints:
                mine = prints.pop(was)
                kept = prints.get(now)
                if kept is None or float(mine.get("seconds", 0)) > float(
                    kept.get("seconds", 0)
                ):
                    prints[now] = mine
                check.prints = prints
                check.save(update_fields=["prints"])
    # The voices, matched again against the Case's prints as they stand now.
    with_prints = transcript.speaker_checks.exclude(prints={}).first()
    if with_prints is not None and voice_prints.on():
        try:
            voice_prints.match(with_prints)
            if not _is_a_label(now):
                note["new_matches"] = list(
                    VoiceMatch.objects.filter(
                        transcript=transcript,
                        state=VoiceMatch.PENDING,
                        kind=VoiceMatch.MATCH,
                        person__name=now,
                    ).values_list("pk", flat=True)
                )
        except Exception:  # noqa: BLE001 - a match is a proposal, never the name
            log.exception("re-read for %s: the voice matches failed", transcript.pk)
    rescore(transcript)
    note["reread"] = transcript.corrections.filter(
        state=SpeakerCorrection.PENDING
    ).count()
    if last is not None:
        look = dict(last.second_look or {})
        if _is_a_label(now):
            look.pop("reread", None)
        else:
            look["reread"] = note
        last.second_look = look
        last.save(update_fields=["second_look"])
    return note


def live_rows(transcript) -> list:
    """The pending corrections whose line still carries the label the check
    saw; one moved since (by hand, a merge, a swap) is left out."""
    return [
        one
        for one in transcript.corrections.filter(state=SpeakerCorrection.PENDING)
        .select_related("segment")
        .order_by("start")
        if one.segment is not None and one.segment.speaker == one.speaker_from
    ]


def speaker_cards(transcript, rows: list) -> list[dict]:
    """The big thing first (v1.128.0): for each label whose lines often read
    as one other Speaker's, one card: the share, what the voice step heard,
    three moments to hear and one of the label's own, and whether the card
    clears the bar for Merge to be the primary button."""
    from core import exports

    lines_of = Counter(
        transcript.segments.filter(same_as_other_side=False).values_list(
            "speaker", flat=True
        )
    )
    by_from: dict = {}
    for one in rows:
        by_from.setdefault(one.speaker_from, []).append(one)
    cards = []
    for from_, moves in by_from.items():
        total = lines_of.get(from_, 0)
        if not total:
            continue
        into = Counter(one.speaker_to for one in moves)
        top, count = into.most_common(1)[0]
        if count < CARD_LEAST or count < CARD_SHARE * total:
            continue
        tops = sorted(
            (one for one in moves if one.speaker_to == top), key=lambda one: one.start
        )
        both = sum(1 for one in tops if one.voice == VOICE_AGREES)
        against = sum(1 for one in tops if one.voice == VOICE_AGAINST)
        voice_floor = max(MERGE_VOICE_LEAST, MERGE_VOICE_SHARE * count)
        clears = count >= MERGE_SHARE * total and both >= voice_floor
        # The pill carries the count, so one agreeing line is enough to say
        # so; "against" only when the voice argued and never agreed.
        if both:
            voice = "agrees"
        elif against >= voice_floor:
            voice = "against"
        else:
            voice = "silent"
        picks = [tops[i] for i in sorted({0, len(tops) // 2, len(tops) - 1})]
        proposed = {one.segment_id for one in moves}
        own = list(
            transcript.segments.filter(speaker=from_, same_as_other_side=False)
            .exclude(pk__in=proposed)
            .order_by("start")
            .values_list("start", flat=True)
        )
        own_at = own[len(own) // 2] if own else None
        cards.append(
            {
                "from": from_,
                "lines": total,
                "to": top,
                "count": count,
                "share": round(count / total, 2),
                "others": [
                    {"to": other, "count": n}
                    for other, n in into.most_common()
                    if other != top
                ],
                "voice": voice,
                "voice_both": both,
                "voice_against": against,
                "clears": clears,
                "hear": [
                    {"start": one.start, "clock": exports.clock(one.start)}
                    for one in picks
                ],
                "own": (
                    {"start": own_at, "clock": exports.clock(own_at)}
                    if own_at is not None
                    else None
                ),
                "ids": [str(one.pk) for one in tops],
            }
        )
    cards.sort(key=lambda card: (not card["clears"], -card["count"]))
    return cards


def stretches(rows: list, cards: list[dict]) -> list[dict]:
    """Then the stretches (v1.128.0): runs of moves between the same two
    Speakers close together, one card each, the voice-backed first. A
    stretch inside a pair a Speaker card names is marked covered, and the
    page folds those under the cards."""
    from core import exports

    covered = {(card["from"], card["to"]) for card in cards}
    out: list[dict] = []
    for one in sorted(rows, key=lambda row: row.start):
        key = (one.speaker_from, one.speaker_to)
        last = out[-1] if out else None
        if last and last["key"] == key and one.start - last["end"] <= STRETCH_GAP:
            last["ids"].append(str(one.pk))
            last["count"] += 1
            last["end"] = one.start
            last["voices"].append(one.voice)
        else:
            out.append(
                {
                    "key": key,
                    "from": key[0],
                    "to": key[1],
                    "ids": [str(one.pk)],
                    "count": 1,
                    "start": one.start,
                    "end": one.start,
                    "reason": one.reason,
                    "quote": one.quote,
                    "voices": [one.voice],
                    "covered": key in covered,
                }
            )
    order = {"agrees": 0, "silent": 1, "mixed": 2, "against": 3}
    for one in out:
        agrees = sum(1 for voice in one["voices"] if voice == VOICE_AGREES)
        against = sum(1 for voice in one["voices"] if voice == VOICE_AGAINST)
        if agrees and not against:
            one["voice"] = "agrees"
        elif against and not agrees:
            one["voice"] = "against"
        elif agrees and against:
            one["voice"] = "mixed"
        else:
            one["voice"] = "silent"
        one["clock"] = exports.clock(one["start"])
        one["clock_end"] = exports.clock(one["end"])
        del one["key"]
        del one["voices"]
    out.sort(key=lambda one: (order[one["voice"]], one["start"]))
    return out


def state_json(transcript, user=None) -> dict:
    """The corrections pending, as cards, and the last run, for the state answer."""
    from core import exports

    if transcript is None:
        return {
            "offered": False,
            "pending": [],
            "speakers": [],
            "stretches": [],
            "run": None,
        }
    last = transcript.speaker_checks.first()
    rows = live_rows(transcript)
    cards = speaker_cards(transcript, rows)

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
            "voice": one.voice,
            "source": one.source,
            # Voices first (v1.145.0): the words' second reading and a split.
            "words": one.words,
            "words_why": one.words_why,
            "split_at": one.split_at,
            "split_part": one.split_part,
        }

    from core import system_voices, voice_prints, voices_first
    from core.assistant import Handover

    voice_prints.settle(transcript)
    # The rows a name settled since the run (v1.144.1), shown in place.
    done_run = transcript.speaker_checks.filter(state=DONE).first()
    note = ((done_run.second_look or {}).get("reread") or {}) if done_run else {}
    settled_rows = (
        list(transcript.corrections.filter(pk__in=note.get("settled") or []))
        if note
        else []
    )
    stage = voices_first.stage_of(transcript)
    from core import call_system
    from core.assistant import _is_a_label

    cast_names = [
        one for one in speakers_of(transcript) if not call_system.is_system(one)
    ]
    return {
        "offered": offered(transcript),
        # Voices first (v1.145.0): the stage, the mode, the words' reading,
        # the lines in doubt by kind, and the cast's count.
        "stage": stage,
        "mode": voices_first.mode_of(last) if last is not None else "",
        "reading": ((last.second_look or {}).get("reading") or None) if last else None,
        "doubt": voices_first.doubt_counts(transcript) if stage else None,
        "cast": {
            "total": len(cast_names),
            "named": sum(1 for one in cast_names if not _is_a_label(one)),
        },
        "settled": [
            dict(
                row(one),
                state=one.state,
                settled_by={"was": note.get("was", ""), "now": note.get("for", "")},
            )
            for one in settled_rows
        ],
        # Sounds like, the conflicts and the Side alarm (v1.144.0), and the
        # labels Unlearn returned.
        "voice_matches": voice_prints.rows_for(transcript),
        "remember_voices": voice_prints.on(),
        # The unit's voice book (v1.146.0): whether Check is here, per label
        # whether it is lit and why not, and the answers on the cards.
        "voice_book": voice_book.state_for(transcript, user),
        # The phone system's voice (v1.159.0): the lines by words and by
        # voice, the way back, and whether the voice gives or counts.
        "phone_system": system_voices.page_state(transcript),
        "pending": [row(one) for one in rows],
        "speakers": cards,
        "stretches": stretches(rows, cards),
        "score": score(transcript),
        # The Hand-overs waiting (ADR 0021): the held ones are counted, not shown.
        "handovers": [
            {
                "id": one.pk,
                "speaker": one.speaker,
                "at": one.at,
                "clock": exports.clock(one.at),
                "lines_after": one.lines_after,
                "voices": one.voices,
            }
            for one in transcript.handovers.filter(state=Handover.PENDING, held=False)
        ],
        "handovers_held": transcript.handovers.filter(
            state=Handover.PENDING, held=True
        ).count(),
        "voice": (last.second_look or {}).get("voice", "words")
        if last is not None
        else "words",
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
                # What the voice step heard of the proposals (v1.128.0).
                "voice_notes": last.second_look or {},
                # The names the same run suggested (v1.140.0): a count, None
                # when the names pass did not run or failed.
                "names": (last.second_look or {}).get("names"),
                "names_state": (last.second_look or {}).get("names_state", ""),
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
    return transcript.corrections.filter(state=SpeakerCorrection.PENDING).count()


# Deciding ---------------------------------------------------------------------------


def accept(correction: SpeakerCorrection, *, by, request=None) -> int:
    """One correction applied: the line moves as it would by hand. A line
    whose Speaker changed since the check is left where it is and the
    correction dismissed, never applied on a stale label."""
    from core import viewer

    with transaction.atomic():
        return _accept_under_the_lock(correction, by=by, request=request, viewer=viewer)


def _accept_under_the_lock(correction, *, by, request, viewer) -> int:
    from core.jobs import Transcript

    Transcript.objects.select_for_update().get(pk=correction.transcript_id)
    segment = correction.segment
    transcript = correction.transcript
    if segment is None or segment.speaker != correction.speaker_from:
        correction.state = SpeakerCorrection.DISMISSED
        correction.decided_by = by
        correction.decided_at = timezone.now()
        correction.save(update_fields=["state", "decided_by", "decided_at"])
        return 0
    if correction.split_at is not None:
        # A mixed line (v1.145.0): split at the word, that part to the other.
        changed = viewer.split_line(
            transcript,
            segment,
            at=correction.split_at,
            part=correction.split_part or "second",
            to=correction.speaker_to,
            by=by,
            request=request,
        )
    else:
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
    # The moved line joins the other Speaker's print and the rest are
    # scored again (ADR 0021).
    rescore(transcript)
    return changed


def dismiss(correction: SpeakerCorrection, *, by, request=None) -> None:
    correction.state = SpeakerCorrection.DISMISSED
    correction.decided_by = by
    correction.decided_at = timezone.now()
    correction.save(update_fields=["state", "decided_by", "decided_at"])
    rescore(correction.transcript)
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
