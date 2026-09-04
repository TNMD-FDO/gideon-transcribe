"""The Workspace: what it holds, when it ends, and the Discard.

A Workspace is a person's holding area. It belongs to them, not to a browser
tab, and it exists at all times; what changes is whether it holds anything.
Nothing in it outlives their Login session. What somebody wants to keep, they
export or download before they sign out, which is what the standing line on
every page says.

Nothing here is stored: a Workspace's condition is worked out from the
database every time it is asked for, so a restart of the app changes no rule
and loses no state.
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime

from django.conf import settings
from django.utils import timezone

from core import audit, settings_store
from core.jobs import Job, JobState
from core.models import LoginSession, User
from core.recordings import MediaState, Recording

log = logging.getLogger("transcribe.lifecycle")

# While a Recording is at one of these, work is being done to it and the
# Workspace is Busy. Uploading is not among them: an upload that nobody
# finishes is dropped after ten minutes and never made a Workspace live.
BUSY_MEDIA = (MediaState.CHECKING, MediaState.PREPARING)


class Condition:
    """A Workspace's condition, worked out and never stored."""

    OPEN = "Open"
    BUSY = "Busy"
    ENDING = "Ending"
    EMPTY = "Empty"


def is_open(user) -> bool:
    """Whether this person has a Login session."""
    return LoginSession.objects.filter(user=user, ended__isnull=True).exists()


def is_busy(user) -> bool:
    """Whether work is in hand: from an upload finishing to the last Job ending.

    A Recording that is Ready with no Job yet counts, because the queue has
    not picked it up but will within the minute. A Clip render never counts:
    the rule is the last Job, and a Clip is not one.
    """
    if in_the_workspace(user).filter(media_state__in=BUSY_MEDIA).exists():
        return True
    if Job.objects.filter(
        recording__user=user, recording__case__isnull=True, state__in=JobState.LIVE
    ).exists():
        return True
    return (
        in_the_workspace(user)
        .filter(media_state=MediaState.READY, jobs__isnull=True)
        .exists()
    )


def is_empty(user) -> bool:
    return not in_the_workspace(user).exists()


def last_job_ended(user) -> datetime | None:
    """When this person's last Job ended, whether it was done, failed, or cancelled."""
    job = (
        Job.objects.filter(recording__user=user, finished__isnull=False)
        .order_by("-finished")
        .first()
    )
    return job.finished if job else None


def session_ended_at(user) -> datetime | None:
    """When this person's last Login session ended, if it has."""
    session = (
        LoginSession.objects.filter(user=user, ended__isnull=False)
        .order_by("-ended")
        .first()
    )
    return session.ended if session else None


def in_the_workspace(user):
    """This person's Recordings that no Case is keeping.

    A Recording with a Case is not in the Workspace: it is not counted at
    sign-out, it does not hold a session open, and the Discard leaves it
    alone. Phase 1 carried this skip with nothing to skip.
    """
    return Recording.objects.filter(user=user, case__isnull=True)


def discard_due_at(user) -> datetime | None:
    """When this Workspace may be discarded, or None while it may not be.

    Two cases. A Login session that ended with nothing in hand: the Discard
    runs at once. A Login session that ended while the Workspace was Busy: it
    lives until the last Job ends and then for a grace period equal to the
    idle timeout, so a Batch left running finishes and is still there if the
    person signs in again that evening.

    Whether the Workspace was Busy at the end is not stored either: a Job that
    finished after the session ended is the proof.
    """
    if is_open(user) or is_busy(user):
        return None

    ended = session_ended_at(user)
    if ended is None:
        return None

    finished = last_job_ended(user)
    if finished is not None and finished > ended:
        return finished + settings_store.idle_timeout()
    return ended


def condition(user) -> str:
    """The one word the users list shows for a Workspace."""
    if is_empty(user):
        return Condition.EMPTY
    if is_open(user):
        # Busy is independent of Open, and the more useful of the two to see:
        # it is what says whether ending the session would interrupt work.
        return Condition.BUSY if is_busy(user) else Condition.OPEN
    return Condition.ENDING


def counts(user) -> dict:
    """What the sign-out dialog and the Delete confirmations say.

    Summaries and Chats are counted here as zero until the AI assistant is
    built, so that the wording is written once and starts telling the truth on
    the day they arrive.
    """
    from core.clips import Clip

    recordings = in_the_workspace(user)
    done = [one for one in recordings if hasattr(one, "transcript")]
    clips = Clip.objects.filter(recording__user=user)
    return {
        "recordings": recordings.count(),
        "transcripts": len(done),
        "summaries": 0,
        "chats": 0,
        "clips": clips.count(),
        "clips_not_downloaded": clips.filter(
            first_downloaded__isnull=True, state="ready"
        ).count(),
        "running": Job.objects.filter(
            recording__user=user, state__in=JobState.LIVE
        ).count(),
        "gigabytes": round(sum(one.disk_bytes() for one in recordings) / (1024**3), 1),
    }


def sign_out_lines(user) -> list[str]:
    """The dialog's own words, from the counts.

    The specification gives the wording with example counts and leaves how it
    reads at zero to the build. A sentence that would say "removes 0
    recordings" is left out instead, so that a person who has nothing is not
    made to read about it.
    """
    tally = counts(user)
    lines = []

    if tally["recordings"]:
        parts = [_plural(tally["recordings"], "recording")]
        if tally["transcripts"]:
            parts[0] += (
                " and its transcript"
                if tally["recordings"] == 1
                else " and their transcripts"
            )
        if tally["summaries"]:
            parts.append(_plural(tally["summaries"], "summary", "summaries"))
        if tally["chats"]:
            parts.append(_plural(tally["chats"], "chat"))
        lines.append(f"Signing out removes {_list_of(parts)}.")
    else:
        lines.append("There is nothing here to remove.")

    if tally["clips_not_downloaded"]:
        one = tally["clips_not_downloaded"] == 1
        lines.append(
            f"{tally['clips_not_downloaded']} clip{'' if one else 's'} "
            f"{'has' if one else 'have'} not been downloaded."
        )

    if tally["running"]:
        hours = settings_store.get("idle_timeout_minutes") / 60
        one = tally["running"] == 1
        lines.append(
            f"{tally['running']} transcription{'' if one else 's'} "
            f"{'is' if one else 'are'} still running. "
            f"{'It' if one else 'They'} will finish, and everything will be "
            f"removed {hours:g} hours after that unless you sign in again."
        )

    return lines


def _plural(count: int, word: str, many: str | None = None) -> str:
    return f"{count} {word if count == 1 else (many or word + 's')}"


def _list_of(parts: list[str]) -> str:
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + ", and " + parts[-1]


# Removing things --------------------------------------------------------------


def remove_recording(recording: Recording, cause: str, actor=None, request=None) -> int:
    """Take a Recording and everything it made off the disk and the database.

    One way in for all four causes: the owner's Delete, an Admin's, a Cancel,
    and the Discard. The row is written before anything goes, because a row
    naming something that is already gone is the point of it.
    """
    size = recording.disk_bytes()
    audit.write(
        audit.Category.RECORDINGS,
        "Recording deleted",
        actor=actor,
        system="sweeper" if actor is None else None,
        request=request,
        affected_user=(
            recording.user
            if actor is not None and actor.pk != recording.user_id
            else None
        ),
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
        cause=cause,
    )
    folder = recording.folder
    batch = recording.batch
    recording.delete()
    shutil.rmtree(folder, ignore_errors=True)

    # A Batch that has lost every Recording is nothing at all.
    if batch is not None and not batch.recordings.exists():
        batch.delete()

    return size


def clear_out(recordings, actor, request=None) -> tuple[int, int]:
    """Remove Recordings a person says they are finished with.

    The Discard does this when a Login session ends, on the app's own
    initiative. This is the same removal asked for by the person whose
    Recordings they are: somebody who has taken what they wanted from a batch
    and needs the room back before the next one.

    It matters more than tidiness. Every Recording counts against its owner's
    quota until it goes, so an office running large batches would otherwise
    reach the quota by lunchtime with no remedy but signing out or deleting
    sixty things one at a time.
    """
    recordings = [one for one in recordings if one.case_id is None]
    if not recordings:
        return 0, 0

    Recording.objects.filter(pk__in=[one.pk for one in recordings]).update(
        discarding_since=timezone.now()
    )

    gone = 0
    for recording in recordings:
        gone += remove_recording(recording, cause="owner", actor=actor, request=request)

    audit.write(
        audit.Category.RECORDINGS,
        "recordings cleared",
        actor=actor,
        request=request,
        affected_user=actor,
        recordings=len(recordings),
        gigabytes=round(gone / (1024**3), 2),
    )
    log.info(
        "%s cleared %d recording(s), %.1f GB",
        actor.username,
        len(recordings),
        gone / (1024**3),
    )
    return len(recordings), gone


def discard(user) -> tuple[int, int]:
    """Remove everything in one Workspace, and say what went.

    Marked first and removed after, so that a crash half way through leaves
    the mark: the next minute finishes it, and the daily sweeper finishes
    anything that has been marked for more than an hour.
    """
    recordings = list(in_the_workspace(user))
    if not recordings:
        return 0, 0

    in_the_workspace(user).update(discarding_since=timezone.now())

    gone = 0
    for recording in recordings:
        gone += remove_recording(recording, cause="discard")

    audit.write(
        audit.Category.RECORDINGS,
        "Workspace discarded",
        system="sweeper",
        affected_user=user,
        recordings=len(recordings),
        gigabytes=round(gone / (1024**3), 2),
    )
    log.info(
        "discarded %s's workspace: %d recording(s), %.1f GB",
        user.username,
        len(recordings),
        gone / (1024**3),
    )

    # The person's own folder goes too, so that nothing is left standing
    # under scratch/ with their id on it. Named from the setting rather than
    # from a Recording, because a Recording in a Case points elsewhere.
    shutil.rmtree(settings.SCRATCH_DIR / str(user.pk), ignore_errors=True)

    return len(recordings), gone


# The minute's work ------------------------------------------------------------


def end_idle_sessions() -> int:
    """End every Login session that has sat idle longer than the timeout.

    The middleware ends a session when the person comes back to find it gone.
    This is for the person who does not come back, which is the case that
    matters: their Workspace cannot be discarded while their session is
    counted as open.
    """
    too_old = timezone.now() - settings_store.idle_timeout()
    ended = 0
    for session in LoginSession.objects.filter(
        ended__isnull=True, last_request__lt=too_old
    ).select_related("user"):
        session.end(LoginSession.IDLE)
        audit.write(
            audit.Category.SIGN_IN,
            "sign-out",
            system="sweeper",
            affected_user=session.user,
            login_session=session,
            cause=LoginSession.IDLE,
        )
        log.info("%s was signed out after sitting idle", session.user.username)
        ended += 1
    return ended


def workspaces_to_discard() -> list[User]:
    """Everybody whose Workspace is neither Open, nor Busy, nor in its grace."""
    now = timezone.now()
    waiting = []
    for user in User.objects.filter(recordings__isnull=False).distinct():
        due = discard_due_at(user)
        if due is not None and due <= now:
            waiting.append(user)
    return waiting
