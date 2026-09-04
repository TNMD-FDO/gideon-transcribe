"""How long until a Job starts, said in words a person can plan around.

The service never states a wait. It publishes its measured speed, audio
minutes finished per wall-clock minute, and the app multiplies that by the
audio ahead of the Job: only the app knows what it wants to tell its users,
and only the service knows how fast the card actually is.

Until the service has ten completed Jobs of a shape it says nothing about that
shape's speed, and the figures below stand in. Those are research reference
points, not measurements of this office's card, so what the page says then is
"roughly" rather than "about". The word is the whole difference between a
figure somebody can rely on and one they cannot.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone

log = logging.getLogger("transcribe.waiting")

# What the research found, used only until this service has measured itself.
# Transcription at about seventy times real time, and Diarization adding about
# half a minute per hour of audio.
REFERENCE_SPEED = 70.0
REFERENCE_DIARIZATION_MINUTES_PER_HOUR = 0.5

# Every Run ahead costs a moment of its own beyond its audio: the model loads,
# the result is fetched, the next one is handed over.
SECONDS_PER_RUN = 15

# Over this, a person wants a time of day rather than a count of minutes.
SHOW_A_CLOCK_OVER_MINUTES = 10


def reference_speed(diarize: bool) -> float:
    """The stand-in speed, in audio minutes per wall-clock minute."""
    if not diarize:
        return REFERENCE_SPEED
    # Diarization's half a minute per hour of audio, folded into one figure so
    # that the arithmetic below has only one shape.
    minutes_per_audio_minute = (
        1.0 / REFERENCE_SPEED + REFERENCE_DIARIZATION_MINUTES_PER_HOUR / 60.0
    )
    return 1.0 / minutes_per_audio_minute


def speed_from(service_speed: dict | None, model: str, diarize: bool) -> tuple:
    """The speed to use for one shape of Job, and whether it was measured.

    The service answers None for a shape it has not run ten of yet.
    """
    figures = (service_speed or {}).get(model) or {}
    measured = figures.get("with_diarization" if diarize else "without_diarization")
    if measured:
        return float(measured), True
    return reference_speed(diarize), False


def minutes_for(
    audio_minutes_ahead: float,
    runs_ahead: int,
    service_speed: dict | None,
    model: str,
    diarize: bool,
) -> tuple:
    """How many minutes until this Job starts, and whether it was measured.

    Anything ahead that is not the app's own Job is counted at the slower
    figure, the one with Diarization on: the app cannot see another Consumer's
    settings, and a wait that turns out shorter than promised is the kind of
    surprise nobody minds.
    """
    speed, measured = speed_from(service_speed, model, diarize)
    if speed <= 0:
        return 0.0, measured

    minutes = (audio_minutes_ahead or 0) / speed
    minutes += (runs_ahead or 0) * SECONDS_PER_RUN / 60.0
    return minutes, measured


def in_words(minutes: float, measured: bool, now=None) -> str:
    """The wait as a person reads it.

    Rounded up, because a wait that runs over is worse than one that ends
    early. Over ten minutes it carries a time of day as well, since nobody
    holds "thirty-five minutes" against the clock in their head.
    """
    if minutes <= 0:
        return "starting now"

    whole = int(minutes) if minutes == int(minutes) else int(minutes) + 1
    about = "about" if measured else "roughly"

    if whole < 1:
        return "less than a minute"

    said = f"{about} {whole} minute{'' if whole == 1 else 's'}"
    if whole > SHOW_A_CLOCK_OVER_MINUTES:
        when = (now or timezone.localtime()) + timedelta(minutes=whole)
        said += f", around {on_the_clock(when)}"
    return said


def on_the_clock(when) -> str:
    """A time of day as an office reads it: 3:40 pm, not 15:40.

    Written out rather than left to strftime, whose no-padding flag differs
    between the server and a workstation and is not there at all on Windows.
    """
    hour = when.hour % 12 or 12
    return f"{hour}:{when.minute:02d} {'am' if when.hour < 12 else 'pm'}"


def for_run(run, service_speed: dict | None, runs_ahead: int = 0) -> str | None:
    """The wait for one Run of the app's own, or nothing when it is running."""
    if run is None or run.audio_minutes_ahead is None:
        return None
    if run.state not in ("pending", "queued"):
        return None

    recording = run.job.recording
    minutes, measured = minutes_for(
        run.audio_minutes_ahead,
        runs_ahead if runs_ahead else (run.position or 1) - 1,
        service_speed,
        recording.model or "large-v3-turbo",
        recording.diarize,
    )
    return in_words(minutes, measured)


def ordinal(number: int) -> str:
    """1st, 2nd, 3rd, 4th. The teens are the exception every time."""
    if 11 <= number % 100 <= 13:
        return f"{number}th"
    ending = ["th", "st", "nd", "rd"][number % 10] if number % 10 < 4 else "th"
    return f"{number}{ending}"


def ahead_of(run, live_runs, user) -> str:
    """Who is directly ahead, in the three shapes the specification fixes.

    A person sees the sign-in name of whoever is directly ahead and nothing
    else of theirs: never a title, never a file name. When the line ahead is
    their own work it is counted rather than named, and when the app cannot
    see what is ahead at all, it belongs to another Consumer of the same
    service and is called that.
    """
    if not run.position or run.position <= 1:
        return ""

    by_position = {one.position: one for one in live_runs if one.position}
    directly = by_position.get(run.position - 1)
    if directly is None:
        return "behind another system"

    if directly.job.recording.user_id == user.pk:
        # How many of their own sit directly ahead, so that somebody waiting
        # on their own batch is told that rather than a stranger's name.
        theirs = 0
        at = run.position - 1
        while at >= 1:
            one = by_position.get(at)
            if one is None or one.job.recording.user_id != user.pk:
                break
            theirs += 1
            at -= 1
        return f"behind {theirs} of your own recording{'' if theirs == 1 else 's'}"

    return f"behind {directly.job.recording.user.username}"


def queued_line(run, live_runs, user, service_speed) -> str | None:
    """The whole sentence a waiting person reads.

    4th in line, behind jsmith. About 35 minutes.
    4th in line, behind 2 of your own recordings.
    4th in line, behind another system.
    """
    if run is None or run.state not in ("pending", "queued"):
        return None

    place = (
        "Next in line"
        if (run.position or 1) <= 1
        else f"{ordinal(run.position)} in line"
    )
    behind = ahead_of(run, live_runs, user)
    wait = for_run(run, service_speed)

    said = place + (f", {behind}" if behind else "")
    if wait:
        said += f". {wait[0].upper()}{wait[1:]}"
    return said + "."


def everything_done_by(recordings, service_speed: dict | None, now=None) -> str | None:
    """The Batch page's one overall line.

    The last Recording's own wait, plus its own audio at the measured speed:
    the point at which the whole Batch is done rather than the point at which
    its last Job starts.
    """
    waits = []
    for one in recordings:
        run = one.get("run")
        if run is None:
            continue
        minutes, measured = minutes_for(
            run.audio_minutes_ahead or 0,
            (run.position or 1) - 1,
            service_speed,
            one["model"],
            one["diarize"],
        )
        speed, _ = speed_from(service_speed, one["model"], one["diarize"])
        # Its own audio still has to be worked through after it starts.
        own = (one["minutes"] or 0) / speed if speed > 0 else 0
        waits.append((minutes + own, measured))

    if not waits:
        return None

    longest, measured = max(waits, key=lambda pair: pair[0])
    if longest <= 0:
        return None

    when = (now or timezone.localtime()) + timedelta(minutes=int(longest) + 1)
    about = "about" if measured else "roughly"
    return f"Everything done by {about} {on_the_clock(when)}"
