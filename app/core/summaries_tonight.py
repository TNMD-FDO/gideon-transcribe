"""Summaries tonight (Phase 9 chapter 5, ADR 0017).

A summary for every recording, written in the overnight window: the Vision
flow's own pattern (the mark on the recording, the minute tick, oldest first,
not reached meaning tonight again), applied to the Summary. Asked for once,
with the tick on the Upload page or the offer on the case page; written at
night with the recording type's template, Standard length and no Focus, the
same Summary a press of New summary gives. Nothing here runs in the daytime.

The window is the Vision page's (Overnight from, Overnight until). Inside it
the night's vision work runs first; a summary is handed to the summary worker
only while no video is being enriched, one at a time by default and two when
the Admin's setting says so, and a recording whose own vision is still to
come waits for its picture, so its summary is written from the words and the
picture together. When the window closes with summaries waiting, each is
marked not reached and tried the next night.
"""

from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from core import assistant, audit, engine, expectation, settings_store, vision
from core.assistant import DONE, QUEUED, RUNNING, TONIGHT, Summary, SummaryTemplate

NOT_REACHED = vision.NOT_REACHED


# Whether it is offered -------------------------------------------------------------


def on() -> bool:
    """The Summary feature is on; the engine need not answer right now."""
    return bool(
        settings_store.get("assistant_available")
        and settings_store.get("summary_available")
    )


def at_once() -> int:
    """How many of the night's summaries may be written at the same time."""
    return max(1, min(2, int(settings_store.get("summaries_at_once_overnight") or 1)))


def tick_default() -> bool:
    return bool(settings_store.get("summaries_tonight_tick_default"))


def tick() -> dict:
    """What the upload page offers under the Vision tick: offered when the
    Summary is On and the batch goes into a case."""
    start, end = settings_store.vision_window()
    return {
        "offered": on(),
        "ticked": tick_default(),
        "caption": (
            f"Written in the overnight window, between {start} and {end}, oldest "
            "first; on Home and the case page you see how many are left. A "
            "session's recordings are gone by night, so this needs a case."
        ),
    }


# The mark ----------------------------------------------------------------------------


def waiting():
    """The summaries marked for tonight, oldest first."""
    return (
        Summary.objects.filter(state=TONIGHT)
        .select_related("recording", "recording__transcript")
        .order_by("created")
    )


def tonight_for(recording):
    return Summary.objects.filter(recording=recording, state=TONIGHT).first()


def has_one(recording) -> bool:
    """Whether the recording has, or is getting, a summary of its current
    transcript: done for this transcript, running, or waiting for tonight."""
    transcript = getattr(recording, "transcript", None)
    if transcript is None:
        return True
    return (
        Summary.objects.filter(recording=recording)
        .filter(
            Q(state=DONE, transcript_created=transcript.created)
            | Q(state=DONE, transcript_created__isnull=True)
            | Q(state__in=(QUEUED, RUNNING, TONIGHT))
        )
        .exists()
    )


def mark(recording, *, by=None) -> Summary | None:
    """One Summary row in the state tonight, the template chosen for the
    recording, Standard length, no Focus. Nothing twice, and nothing for a
    recording without a transcript or outside a case."""
    if recording.case_id is None or getattr(recording, "transcript", None) is None:
        return None
    if has_one(recording):
        return None
    template = SummaryTemplate.chosen_for(recording)
    return Summary.objects.create(
        recording=recording,
        asked_by=by,
        template=template,
        template_name=template.name,
        template_version=template.version,
        focus="",
        length="standard",
        state=TONIGHT,
        overnight=True,
    )


def on_transcript(recording) -> bool:
    """A transcript has landed on a recording whose upload carried the tick:
    its summary waits for tonight."""
    if not recording.summary_wanted or not on():
        return False
    return mark(recording) is not None


# The case page's offer -------------------------------------------------------------


def missing_in(case) -> list:
    """The case's recordings with a transcript and no summary of it, not
    running and not waiting for tonight: what the offer would mark."""
    from core.jobs import Transcript

    transcripts = Transcript.objects.filter(recording__case=case).select_related(
        "recording"
    )
    created_of = {one.recording_id: one.created for one in transcripts}
    if not created_of:
        return []
    covered = set()
    for summary in Summary.objects.filter(
        recording_id__in=created_of, state__in=(DONE, QUEUED, RUNNING, TONIGHT)
    ).values("recording_id", "state", "transcript_created"):
        if summary["state"] != DONE or summary["transcript_created"] in (
            None,
            created_of[summary["recording_id"]],
        ):
            covered.add(summary["recording_id"])
    return [
        one.recording
        for one in sorted(transcripts, key=lambda row: row.recording.created)
        if one.recording_id not in covered
    ]


def count_tonight(case) -> int:
    return waiting().filter(recording__case=case).count()


def schedule_missing(case, *, by, request=None) -> int:
    """Write the missing summaries tonight: one mark per recording without
    one, and one audit row with the count."""
    count = 0
    for recording in missing_in(case):
        recording.summary_wanted = True
        recording.save(update_fields=["summary_wanted"])
        if mark(recording, by=by) is not None:
            count += 1
    if count:
        audit.write(
            audit.Category.LLM,
            "Summaries scheduled",
            actor=by,
            request=request,
            object_type="case",
            object_id=case.pk,
            object_label=case.name,
            count=count,
        )
    return count


def line(case) -> str:
    """The case page's line: how many have no summary, how many are tonight."""
    if not on():
        return ""
    missing = len(missing_in(case))
    tonight = count_tonight(case)
    parts = []
    if missing:
        parts.append(f"{_recordings(missing)} without a summary")
    if tonight:
        start, _ = settings_store.vision_window()
        parts.append(
            f"{tonight} summar{'y' if tonight == 1 else 'ies'} tonight from {start}"
        )
    return "; ".join(parts)


def _recordings(count: int) -> str:
    return f"{count} recording{'' if count == 1 else 's'}"


# The row's words ---------------------------------------------------------------------


def words(summary: Summary | None) -> str:
    """What a case row says about a summary waiting for tonight."""
    if summary is None or summary.state != TONIGHT:
        return ""
    if summary.reason_class == NOT_REACHED:
        return "Summary not reached last night; tonight again"
    return "Summary tonight"


# The night ---------------------------------------------------------------------------


def running_now() -> int:
    """How many of the night's summaries are being written."""
    return Summary.objects.filter(overnight=True, state__in=(QUEUED, RUNNING)).count()


def _waits_for_its_picture(summary: Summary) -> bool:
    """A recording whose vision is tonight, queued or running keeps its
    summary until the picture is there."""
    transcript = getattr(summary.recording, "transcript", None)
    if transcript is None:
        return False
    if not (assistant.record_on() and assistant.has_picture(summary.recording)):
        return False
    return transcript.prepare_state in (
        vision.TONIGHT,
        assistant.QUEUED,
        assistant.PREPARING,
    )


def hand_over(summary: Summary) -> None:
    """The summary's turn: queued to the summary worker as a press of New
    summary would queue it."""
    from core import tasks

    transcript = getattr(summary.recording, "transcript", None)
    summary.state = QUEUED
    summary.reason_class = ""
    summary.expectation = expectation.note(
        "summary", assistant.reading_size(transcript)
    )
    summary.save(update_fields=["state", "reason_class", "expectation"])
    tasks.write_summary.defer(summary_id=str(summary.pk))


def mind_the_night(vision_did: str = "", now=None) -> str:
    """Every minute, after the vision tick: inside the window, while the
    night's vision work is not running, the oldest summary marked tonight is
    handed over, up to the setting's count at once; outside it, as the window
    closes, the ones still waiting are marked not reached. Returns what it
    did, in a word."""
    if not on():
        return "off"
    if not vision.in_window(now):
        if vision.just_closed(now):
            waiting().exclude(reason_class=NOT_REACHED).update(reason_class=NOT_REACHED)
        return "outside"
    if vision_did in ("queued", "busy"):
        # The night's vision work comes first.
        return "vision"
    if running_now() >= at_once():
        return "busy"
    if not engine.is_reachable():
        # The engine is away: nothing fails, everything waits for it.
        return "engine away"
    for summary in waiting():
        if getattr(summary.recording, "transcript", None) is None:
            continue
        if _waits_for_its_picture(summary):
            continue
        hand_over(summary)
        return "queued"
    return "nothing"


# The mail --------------------------------------------------------------------------


def mail_line(recordings) -> str:
    """The Batch-finished mail's one line when summaries are scheduled."""
    ids = [one.pk for one in recordings if one.summary_wanted and one.case_id]
    if not ids:
        return ""
    if not Summary.objects.filter(
        recording_id__in=ids, state__in=(TONIGHT, QUEUED, RUNNING, DONE)
    ).exists():
        return ""
    return "Each recording's summary will be written tonight."


def when_written(summary: Summary) -> str:
    """For the card: when the night's writing is due."""
    start, _ = settings_store.vision_window()
    if summary.reason_class == NOT_REACHED:
        return f"Not reached last night; written tonight from {start}."
    now = timezone.localtime()
    if vision.in_window(now):
        return "Written tonight, in its turn."
    return f"Written tonight from {start}."
