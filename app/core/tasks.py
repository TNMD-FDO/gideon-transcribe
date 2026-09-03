"""The background work, and when it runs.

Three queues on one image, as the specification fixes: `media` for ffmpeg and
audiowaveform, `default` for the queue and the schedules, and `llm` for the AI
assistant. Procrastinate runs them on the app's own PostgreSQL, which is why
there is no Redis, no Valkey, and no scheduler container.

Media work is CPU only. No container built from the app image ever sees a GPU.
"""

from __future__ import annotations

import logging

from procrastinate import exceptions
from procrastinate.contrib.django import app

log = logging.getLogger("transcribe.tasks")

# One poll waiting at a time, and three seconds between them, as the
# specification fixes.
POLL_LOCK = "whisperx-poll"
POLL_SECONDS = 3


@app.task(queue="media", name="prepare_recording")
def prepare_recording(recording_id: str) -> None:
    """Take one Recording from arrived to Ready, then start its Playback copy.

    The Playback copy is a job of its own rather than the end of this one, so
    that a Recording joins the transcription queue the moment it is Ready and
    waits for nothing.
    """
    from core import pipeline
    from core.recordings import MediaState, Recording

    recording = Recording.objects.filter(pk=recording_id).first()
    if recording is None:
        # The Recording went while this was waiting its turn: a Workspace
        # ended, or somebody cancelled. There is nothing to do and nothing
        # wrong.
        log.info("recording %s is gone; nothing to prepare", recording_id)
        return

    recording = pipeline.prepare(recording)
    if recording.media_state == MediaState.READY:
        # The line first: a Recording joins it the moment it is Ready, and the
        # Playback copy is made beside the transcription rather than before it.
        from core import queue

        job = queue.make_job(recording)
        hand_over_job.defer(job_id=str(job.pk))
        make_playback_copy.defer(recording_id=str(recording.pk))


@app.task(queue="media", name="make_playback_copy")
def make_playback_copy(recording_id: str) -> None:
    """The copy the browser plays, and the peaks it draws."""
    from core import pipeline
    from core.recordings import Recording

    recording = Recording.objects.filter(pk=recording_id).first()
    if recording is None:
        return
    pipeline.make_playback(recording)


@app.task(queue="default", name="hand_over_job")
def hand_over_job(job_id: str) -> None:
    """Give a Job's Sides to the WhisperX service, and start watching."""
    from core import queue
    from core.jobs import Job, JobState

    job = Job.objects.filter(pk=job_id).select_related("recording").first()
    if job is None:
        return

    job = queue.hand_over(job)
    if job.state in JobState.LIVE:
        _poll_again(1, when=0)


@app.task(queue="default", name="poll_service")
def poll_service(attempt: int = 1) -> None:
    """Ask the service about every Run at once, then ask again in a moment.

    One request every three seconds gets the state of every Run, which is what
    the contract intends. The queueing lock keeps exactly one poll waiting, so
    a slow answer cannot pile requests up behind it.

    Two failures in a row give up on the Jobs that are out there: six seconds,
    so one dropped packet does not fail a two-hour transcription.
    """
    from core import queue, whisperx

    jobs = list(queue.live_jobs())
    if not jobs:
        return

    try:
        states = {one["id"]: one for one in whisperx.jobs()}
    except whisperx.ServiceError as problem:
        if attempt >= queue.POLLS_BEFORE_GIVING_UP:
            log.warning("the service has not answered twice; failing what is out there")
            for job in jobs:
                queue.fail(job, problem.reason_class)
            return
        _poll_again(attempt + 1)
        return

    for job in jobs:
        queue.take_state_from(job, states)

    if queue.live_jobs().exists():
        _poll_again(1)


def _poll_again(attempt: int, when: int = POLL_SECONDS) -> None:
    """Ask for one more poll, unless one is already waiting.

    The queueing lock allows exactly one poll to be waiting, and asking for a
    second raises rather than being ignored. That is the lock doing its work,
    not a fault: whichever poll is already queued will find whatever this one
    would have.
    """
    try:
        poll_service.configure(
            queueing_lock=POLL_LOCK, schedule_in={"seconds": when}
        ).defer(attempt=attempt)
    except exceptions.AlreadyEnqueued:
        log.debug("a poll is already waiting")


@app.periodic(cron="* * * * *")
@app.task(queue="default", name="keep_the_queue_moving")
def keep_the_queue_moving(timestamp: int) -> None:
    """Every minute, make sure nothing is sitting still.

    Two things can leave the queue stopped: a Recording that became Ready
    while nothing was watching, and a poll that was lost with a worker. Both
    are cheap to check and neither should need a person to notice.
    """
    from core import queue

    for recording in queue.ready_without_a_job():
        job = queue.make_job(recording)
        hand_over_job.defer(job_id=str(job.pk))

    if queue.live_jobs().exists():
        _poll_again(1)


@app.periodic(cron="30 3 * * *")
@app.task(queue="default", name="sweep_audit_log")
def sweep_audit_log(timestamp: int) -> None:
    """Remove audit rows past the retention setting, nightly at half past three.

    The same quiet hour as the media sweeper, after the Directory check. It
    runs under the sweep role, which is the only thing in the app that can
    remove an audit row, and it writes its own row saying what it removed.
    """
    from core import audit, settings_store

    audit.sweep(settings_store.audit_retention_months())
