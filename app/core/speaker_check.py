"""The Speaker check (Phase 5 chapter 3, v1.55.0).

After a Transcript lands with its Speakers told apart, the engine reads it in
windows of a few minutes and names the lines whose words show they belong
to a different Speaker than the one the voice split gave them. Every answer
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


def run(check_id, attempt: int = 1) -> None:
    """The check: one call per window, the answers checked, the corrections
    kept in place of the pending ones. One audit row for the run, metadata
    only."""
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
        for start, end in windows(lines, settings_store.speaker_check_window_seconds()):
            window = lines[start:end]
            user = prompts.speaker_check_input(window, speakers)
            if not prompts.fits(
                system, user, answer_cap=answer_cap, window=assistant.window()
            ):
                raise engine.Problem(engine.TOO_LONG, "a window is too long")
            answer = engine.complete(
                assistant._messages(system, user),
                max_completion_tokens=answer_cap,
                thinking=assistant.thinking(),
                timeout=assistant.time_limit(FEATURE),
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
        )


# What the pages read ----------------------------------------------------------------


def state_json(transcript) -> dict:
    """The corrections pending and the last run, for the state answer."""
    from core import exports

    if transcript is None:
        return {"offered": False, "pending": [], "run": None}
    last = transcript.speaker_checks.first()
    pending = transcript.corrections.filter(state=SpeakerCorrection.PENDING)
    return {
        "offered": offered(transcript),
        "pending": [
            {
                "id": str(one.pk),
                "segment": one.segment_id,
                "start": one.start,
                "clock": exports.clock(one.start),
                "quote": one.quote,
                "from": one.speaker_from,
                "to": one.speaker_to,
                "reason": one.reason,
            }
            for one in pending.order_by("start")
        ],
        "run": (
            {
                "state": last.state,
                "found": last.found,
                "windows": last.windows,
                "cut_short": last.cut_short,
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
