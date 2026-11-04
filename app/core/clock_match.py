"""Placing a video by sound (Phase 10 chapter 5, v1.186.0).

A video with no clock in its picture is compared, on the media worker, with
the placed videos of its case: those of its file's day first, searched near
the file's own time (the probe of 2026-11-02 found that search trustworthy
and the whole-range search not), else every placed video over the whole
range, which is only ever Unclear. The best match is one row of the
Not-on-the-clock panel under the Incidents tab's cards, with its surety
word: Place it there writes the recording's clock as "by sound" (ADR 0027
widened: the match's strength and the video it followed are kept), Not this
sets the suggestion aside. Sound places a video; the notes form the
incident. The app never places a video by itself here.
"""

from __future__ import annotations

import datetime as dt
import logging

from django.db import models, transaction
from django.utils import timezone

from core import exports, incidents
from core.recordings import Recording

log = logging.getLogger("transcribe.clock_match")

QUEUED, RUNNING, DONE, FAILED = "queued", "running", "done", "failed"
# Placed videos compared with one clockless video, at most: the nearest by
# the file's time first. Each comparison is a few seconds on the media worker.
CANDIDATES_MOST = 8
# The panel shows this many rows before "show all".
PANEL_MOST = 5
# A match left queued or running this long is asked for again by the minute
# sweep: a worker that died took it with it.
STALE_AFTER = dt.timedelta(minutes=15)
RANK = {
    incidents.SURETY_CLEAR: 0,
    incidents.SURETY_LIKELY: 1,
    incidents.SURETY_UNCLEAR: 2,
}


class ClockMatch(models.Model):
    """One clockless video's best sound match against the placed videos of
    its case: what it lines up with, by how much, how surely, and whether
    the person set it aside."""

    recording = models.OneToOneField(
        Recording, on_delete=models.CASCADE, related_name="clock_match"
    )
    against = models.ForeignKey(
        Recording, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    state = models.CharField(max_length=10, default=QUEUED)
    lag = models.FloatField(null=True, blank=True)
    strength = models.FloatField(null=True, blank=True)
    surety = models.CharField(max_length=10, blank=True, default="")
    # Searched near the file's own time (true) or over the whole range.
    near_file = models.BooleanField(default=False)
    reason = models.CharField(max_length=60, blank=True, default="")
    set_aside = models.BooleanField(default=False)
    asked_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)


# Asking -------------------------------------------------------------------------


def _clockless(recording) -> bool:
    from core import case_chronology

    return (
        incidents.is_video(recording) and case_chronology.clock_of(recording)[0] is None
    )


def candidates(recording) -> list[tuple]:
    """The placed videos of the case to compare with: (other, date, start),
    those of the file's day first and nearest the file's time first, at most
    CANDIDATES_MOST; every placed video when the file carries no day."""
    from core import case_chronology

    if not recording.case_id:
        return []
    file_date = incidents.file_date_of(recording)
    _, file_seconds = incidents.file_time_of(recording)
    found = []
    for other in recording.case.recordings.exclude(pk=recording.pk):
        if not incidents.is_video(other):
            continue
        date, start, how = case_chronology.clock_of(other)
        if date is None or start is None or how == case_chronology.DAY:
            continue
        if file_date is not None and date != file_date:
            continue
        near = (
            abs(incidents._wrapped(file_seconds - start))
            if file_seconds is not None
            else 0.0
        )
        found.append((near, other, date, start))
    found.sort(key=lambda one: (one[0], one[2], one[3]))
    return [(other, date, start) for _, other, date, start in found[:CANDIDATES_MOST]]


def ask(recording) -> bool:
    """Queue the match for one clockless video; False when there is nothing
    to do: the setting off, a placed video, a suggestion set aside, nobody
    to compare with."""
    if not incidents.sound_match_on() or not _clockless(recording):
        return False
    match = ClockMatch.objects.filter(recording=recording).first()
    if match is not None and match.set_aside:
        return False
    if not candidates(recording):
        return False
    if match is None:
        match = ClockMatch(recording=recording)
    match.state = QUEUED
    match.against = None
    match.lag = None
    match.strength = None
    match.surety = ""
    match.near_file = False
    match.reason = ""
    match.asked_at = timezone.now()
    match.finished_at = None
    match.save()
    from core import tasks

    transaction.on_commit(
        lambda: tasks.match_clock.defer(recording_id=str(recording.pk))
    )
    return True


def ask_for_case(case) -> int:
    """Every clockless video of the case asked again: a video was placed or
    landed, so the comparisons may read differently now."""
    if case is None or not incidents.sound_match_on():
        return 0
    return sum(1 for one in case.recordings.all() if _clockless(one) and ask(one))


def after_stamp(recording) -> None:
    """The clock read ended: a clock found places the video, so the case's
    other clockless videos are asked again; none found, this one is asked."""
    try:
        if _clockless(recording):
            ask(recording)
        elif recording.case_id and incidents.is_video(recording):
            ask_for_case(recording.case)
    except Exception as why:  # noqa: BLE001 - a match problem never fails a read
        log.warning("the clock match after the stamp read failed: %s", why)


def after_placed(recording) -> None:
    """A video was placed or taken off the clock: the case's clockless
    videos (this one among them, when taken off) are asked again."""
    if recording.case_id:
        ask_for_case(recording.case)


def requeue_stale() -> int:
    """Matches left queued or running by a worker that died, asked again."""
    from core import tasks

    cutoff = timezone.now() - STALE_AFTER
    stale = list(
        ClockMatch.objects.filter(state__in=(QUEUED, RUNNING), asked_at__lt=cutoff)[:20]
    )
    for match in stale:
        match.asked_at = timezone.now()
        match.state = QUEUED
        match.save(update_fields=["asked_at", "state"])
        tasks.match_clock.defer(recording_id=str(match.recording_id))
    return len(stale)


# Running ------------------------------------------------------------------------


def run(recording_id) -> None:
    """The worker's side: the best match over the candidates, kept."""
    from core import sound_match

    match = (
        ClockMatch.objects.filter(recording_id=recording_id)
        .select_related("recording", "recording__case")
        .first()
    )
    if match is None or match.state not in (QUEUED, RUNNING):
        return
    recording = match.recording
    match.state = RUNNING
    match.save(update_fields=["state"])
    best = None
    try:
        mine = incidents._first_side_audio(recording)
        _, file_seconds = incidents.file_time_of(recording)
        for other, date, start in candidates(recording):
            try:
                theirs = incidents._first_side_audio(other)
            except sound_match.NoMatch:
                continue
            expected = None
            if file_seconds is not None and incidents.file_date_of(recording) == date:
                expected = incidents._wrapped(file_seconds - start)
            try:
                found, surety = incidents._match_near(theirs, mine, expected)
            except sound_match.NoMatch:
                continue
            key = (RANK.get(surety, 9), -found.strength)
            if best is None or key < best[0]:
                best = (key, other, found, surety, expected is not None)
    except sound_match.NoMatch as why:
        _failed(match, str(why)[:60])
        return
    except Exception as why:  # noqa: BLE001 - the panel says it failed, the log why
        log.warning("the clock match of %s failed: %s", recording_id, why)
        _failed(match, "the match failed")
        return
    if best is None:
        _failed(match, "nothing lined up")
        return
    _, other, found, surety, near = best
    match.state = DONE
    match.against = other
    match.lag = found.lag
    match.strength = found.strength
    match.surety = surety
    match.near_file = near
    match.reason = ""
    match.finished_at = timezone.now()
    match.save()


def _failed(match: ClockMatch, reason: str) -> None:
    match.state = FAILED
    match.reason = reason
    match.finished_at = timezone.now()
    match.save(update_fields=["state", "reason", "finished_at"])


# Placing ------------------------------------------------------------------------


def placed_at_of(match: ClockMatch) -> tuple[dt.date, float] | None:
    """Where the video would sit: the other's clock plus the lag, past
    midnight onto the next day."""
    from core import case_chronology

    if match.state != DONE or match.lag is None or match.against is None:
        return None
    date, start, _ = case_chronology.clock_of(match.against)
    if date is None or start is None:
        return None
    at = start + match.lag
    while at >= case_chronology.DAY_SECONDS:
        at -= case_chronology.DAY_SECONDS
        date = date + dt.timedelta(days=1)
    while at < 0:
        at += case_chronology.DAY_SECONDS
        date = date - dt.timedelta(days=1)
    return date, at


def may_place(match: ClockMatch) -> bool:
    return (
        not match.set_aside
        and match.surety in (incidents.SURETY_CLEAR, incidents.SURETY_LIKELY)
        and placed_at_of(match) is not None
    )


def place_by_sound(recording, *, by, request=None) -> str:
    """Place it there: the recording's clock written as by sound, with the
    match's strength and the video it followed. Raises ValueError when the
    match is not one the app may offer."""
    from core import case_chronology

    match = (
        ClockMatch.objects.filter(recording=recording).select_related("against").first()
    )
    if match is None or not may_place(match):
        raise ValueError("there is no clear sound match to place it by")
    # The path file's clock stands over sound (v1.197.0, Phase 12 chapter 6).
    if case_chronology.clock_of(recording)[2] == case_chronology.PATH:
        raise ValueError("it is placed from its path file, which stands over sound")
    date, start = placed_at_of(match)
    case_chronology.place(
        recording,
        date,
        start,
        by=by,
        request=request,
        how=case_chronology.SOUND,
        strength=match.strength,
        follows=match.against,
    )
    return case_chronology.placed_words(recording)


def set_aside(recording) -> bool:
    """Not this: the suggestion put away; the row keeps Type a time."""
    match = ClockMatch.objects.filter(recording=recording).first()
    if match is None:
        return False
    match.set_aside = True
    match.save(update_fields=["set_aside"])
    return True


# The panel ----------------------------------------------------------------------


def _surety_words(surety: str) -> dict:
    word, why, tone = incidents.SURETY_WORDS.get(
        surety, incidents.SURETY_WORDS[incidents.SURETY_UNCLEAR]
    )
    return {"word": word, "why": why, "tone": tone}


def _path_waiting_words(recording) -> str:
    """ "A path file of its name is waiting: ..." when one sits on the case
    unpaired against this video, else ""."""
    from core import camera_paths

    if recording.case_id is None or not camera_paths.on():
        return ""
    stem = camera_paths.stem_of(recording.original_filename)
    if not stem:
        return ""
    one = camera_paths.WaitingPathFile.objects.filter(
        case_id=recording.case_id, stem=stem
    ).first()
    if one is None:
        return ""
    if one.flagged:
        return f"A path file of its name is waiting on the case: {one.flagged}"
    return "A path file of its name is waiting on the case."


def rows_of(case) -> list[dict]:
    """Every video of the case with no clock, for the panel: its still at
    its start, what its file says, what its sound says, and the presses it
    earns; ordered by what the app can say, a Clear line first, then Likely,
    then a file time, then nothing."""
    from core import case_chronology

    recordings, by_recording = case_chronology._noted(case)
    matches = {
        m.recording_id: m
        for m in ClockMatch.objects.filter(recording__case=case).select_related(
            "against"
        )
    }
    rows = []
    for one in recordings:
        # A video placed by the day alone (v1.186.1) has a day and no hour:
        # it sits here too, with Take off the clock, and is never matched.
        day_alone = None
        if incidents.is_video(one):
            date, start, how = case_chronology.clock_of(one)
            if date is not None and how == case_chronology.DAY:
                day_alone = date
        if day_alone is None and not _clockless(one):
            continue
        words, seconds = incidents.file_time_of(one)
        file_date = incidents.file_date_of(one)
        file = (
            {
                "words": words,
                "seconds": seconds,
                "date": file_date.isoformat() if file_date else "",
            }
            if seconds is not None
            else None
        )
        match = matches.get(one.pk)
        sound = None
        rank = 2 if file else 3
        if day_alone is not None:
            match = None
            rank = 4
        if match is not None and not match.set_aside:
            sound = {"state": match.state, "reason": match.reason}
            if match.state == DONE:
                at = placed_at_of(match)
                sound.update(
                    {
                        "against": exports.title_of(match.against)
                        if match.against
                        else "",
                        "date": at[0].isoformat() if at else "",
                        "at": case_chronology.hms(at[1]) if at else "",
                        "surety": _surety_words(match.surety),
                        "near_file": match.near_file,
                        "may_place": may_place(match),
                    }
                )
                rank = min(rank, RANK.get(match.surety, 9))
        rows.append(
            {
                "id": str(one.pk),
                "title": exports.title_of(one),
                "notes": len(by_recording.get(str(one.pk), [])),
                "still": f"/recording/{one.pk}/still?t=0.0",
                "file": file,
                "sound": sound,
                # A path file of this video's name waiting on the case, and why
                # it did not pair (Phase 12 chapter 6, v1.197.0).
                "path_waiting": _path_waiting_words(one),
                "set_aside": bool(match and match.set_aside),
                "rank": rank,
                "placed_by_day": day_alone is not None,
                "day_words": case_chronology.day_words(day_alone) if day_alone else "",
                "placed": case_chronology.placed_words(one) if day_alone else "",
            }
        )
    rows.sort(key=lambda row: (row["rank"], row["title"]))
    return rows


def unclocked_by_day(case, recordings=None) -> dict:
    """How many clockless videos each day has by its file's date, for the
    day chips and the Date strip's ring. Given the case's recordings already
    loaded, asks the database nothing (the case page's query budget)."""
    from core import case_chronology

    counts: dict = {}
    for one in recordings if recordings is not None else case.recordings.all():
        if not incidents.is_video(one):
            continue
        date, _start, how = case_chronology.clock_of(one)
        if date is not None and how == case_chronology.DAY:
            # Placed by the day alone (v1.186.1): no hour, so not on the clock
            # in the panel's sense, counted on its own day.
            counts[date] = counts.get(date, 0) + 1
            continue
        if date is not None:
            continue
        date = incidents.file_date_of(one)
        if date is not None:
            counts[date] = counts.get(date, 0) + 1
    return counts
