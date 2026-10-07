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


def _voice_notes(transcript, kept: dict) -> dict:
    """What the voice step heard on each proposed line (v1.105.0), kept as
    the one measure beside the words (v1.128.0): the blind second reading
    is retired, since on the office's recordings it backed almost nothing
    and overruled the voice. Nothing is dropped; every move is a person's
    to decide, drawn as cards."""
    summary = {"rows": len(kept), "voice_agrees": 0, "voice_against": 0, "silent": 0}
    if not kept:
        return summary
    heard = voices_heard(transcript)
    for one in kept.values():
        one["second"], one["aside_why"] = "", ""
        one["voice"], _ = voice_of(
            heard.get(one["segment_id"]) or Counter(), one["from"], one["to"]
        )
        if one["voice"] == VOICE_AGREES:
            summary["voice_agrees"] += 1
        elif one["voice"] == VOICE_AGAINST:
            summary["voice_against"] += 1
        else:
            summary["silent"] += 1
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
        # The voice step's note on each move (v1.105.0, alone since v1.128.0).
        check.second_look = _voice_notes(transcript, kept)
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
            voice_agrees=check.second_look.get("voice_agrees", 0),
            voice_against=check.second_look.get("voice_against", 0),
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
    """The office's own measure: of the corrections a person has decided on
    this Transcript, how many were accepted and how many dismissed."""
    out = {"accepted": 0, "dismissed": 0}
    for state in transcript.corrections.exclude(
        state=SpeakerCorrection.PENDING
    ).values_list("state", flat=True):
        out[state] = out.get(state, 0) + 1
    return out


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


def state_json(transcript) -> dict:
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
        }

    return {
        "offered": offered(transcript),
        "pending": [row(one) for one in rows],
        "speakers": cards,
        "stretches": stretches(rows, cards),
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
                # What the voice step heard of the proposals (v1.128.0).
                "voice_notes": last.second_look or {},
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
