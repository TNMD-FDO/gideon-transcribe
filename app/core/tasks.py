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
    else:
        # A Recording that failed here has ended, and may have been the last
        # thing its Batch was waiting on.
        from core import mail

        mail.note_batch_progress(recording)


@app.task(queue="media", name="prepare_audio_again")
def prepare_audio_again(recording_id: str) -> None:
    """Remake a Recording's prepared audio, then put it in the line.

    Process again's first step. It runs on the media queue because it is
    ffmpeg work, and the Job is made only once the audio is there, so the
    service is never handed a file that is being rewritten under it.
    """
    from core import pipeline, queue
    from core.recordings import MediaState, Recording

    recording = Recording.objects.filter(pk=recording_id).first()
    if recording is None:
        log.info("recording %s is gone; nothing to process again", recording_id)
        return

    recording = pipeline.prepare_audio_again(recording)
    if recording.media_state != MediaState.READY:
        # The audio could not be prepared, so the Recording is Failed and says
        # why. There is nothing to hand the service.
        log.warning("recording %s could not be prepared again", recording_id)
        return

    job = queue.make_job(recording)
    hand_over_job.defer(job_id=str(job.pk))


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
        if whisperx.fast_lane_configured():
            # The lane's jobs too, in the same answer. A lane that does not
            # answer leaves its Runs where they were this time round; the
            # batch service's silence is what gives up on everything.
            try:
                states.update({one["id"]: one for one in whisperx.jobs(whisperx.FAST)})
            except whisperx.ServiceError:
                log.warning("the fast lane did not answer the poll")
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
    from core import queue, uploads

    dropped = uploads.drop_abandoned()
    if dropped:
        log.info("%d abandoned upload(s) were dropped", dropped)

    for recording in queue.ready_without_a_job():
        job = queue.make_job(recording)
        hand_over_job.defer(job_id=str(job.pk))

    if queue.live_jobs().exists():
        _poll_again(1)


@app.periodic(cron="* * * * *")
@app.task(queue="default", name="mind_the_workspaces")
def mind_the_workspaces(timestamp: int) -> None:
    """Every minute: end sessions that have sat idle, and run the Discards.

    This is what makes the standing line on every page true. A Workspace that
    is neither Open, nor Busy, nor inside its grace period is removed within
    the minute, and there is no undo: what somebody wanted to keep, they
    exported before they left.
    """
    from core import lifecycle

    ended = lifecycle.end_idle_sessions()
    if ended:
        log.info("%d login session(s) ended after sitting idle", ended)

    for user in lifecycle.workspaces_to_discard():
        lifecycle.discard(user)


@app.periodic(cron="* * * * *")
@app.task(queue="llm", name="check_the_engine")
def check_the_engine(timestamp: int) -> None:
    """Does the engine answer? Asked once a minute, from the one container that can.

    Only llm-worker is on the engine's network, so the check lives on its
    queue. What it finds goes on the status row, which is all the viewer and
    the Status page read: neither ever touches that network. Quiet while no
    engine is configured.
    """
    from core import engine

    engine.check()


@app.task(queue="llm", name="test_the_engine")
def test_the_engine() -> None:
    """The panel's Test connection, run where the engine can be reached."""
    from core import engine

    engine.test_connection()


# The AI assistant's three features, each one task on the llm queue, run by
# llm-worker with concurrency 4: four calls in flight, the rest waiting in
# order. None of them ever holds a Job in Running.


@app.task(queue="llm", name="answer_case_turn")
def answer_case_turn(turn_id: str) -> None:
    """One Case Chat question: its Readings and, when in parts, the combining call."""
    from core import case_chat

    case_chat.answer_case_turn(turn_id)


@app.task(queue="llm", name="write_summary")
def write_summary(summary_id: str) -> None:
    from core import assistant

    assistant.write_summary(summary_id)


@app.task(queue="llm", name="answer_turn")
def answer_turn(turn_id: str) -> None:
    from core import assistant

    assistant.answer_turn(turn_id)


@app.task(queue="llm", name="suggest_names")
def suggest_names(run_id: str) -> None:
    from core import assistant

    assistant.suggest_names(run_id)


@app.periodic(cron="30 3 * * *")
@app.task(queue="default", name="retention_sweep")
def retention_sweep(timestamp: int) -> None:
    """The Retention policy's nightly pass, at half past three.

    Marks the warning, moves due Cases to the Recycle bin, wipes what has sat
    there past the bin period, and writes one row with the counts. Nothing at
    all while Folder management is off. The chapter puts it before the disk
    sweeper and the audit sweep; here they share the minute, and the order does
    not matter, because a binned Case keeps every row and the disk sweeper
    removes only what no row claims.
    """
    from core import dictation, retention

    retention.sweep()
    # The Dictations' own pass, whatever Folder management says.
    dictation.sweep()


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


@app.periodic(cron="30 3 * * *")
@app.task(queue="media", name="sweep_the_disk")
def sweep_the_disk(timestamp: int) -> None:
    """The daily tidy, at the same quiet hour as the audit sweep.

    Three things that should never be there and occasionally are: upload
    pieces nobody finished, a folder under scratch/ whose Recording is gone,
    and a Recording left marked Discarding by a crash.
    """
    from core import sweeping

    sweeping.sweep()


@app.periodic(cron="0 * * * *")
@app.task(queue="default", name="check_the_directory")
def check_the_directory(timestamp: int) -> None:
    """Compare the accounts against the directory, at the hour the panel sets.

    Procrastinate's schedule is fixed when the worker starts and the hour is
    an admin setting, so this wakes every hour and does its work only at the
    hour that is set. Changing the setting therefore takes effect the same
    night, without a restart.
    """
    from datetime import datetime

    from core import directory, settings_store

    if datetime.now().hour != settings_store.get("directory_check_hour"):
        return
    directory.check_accounts()


@app.periodic(cron="30 * * * *")
@app.task(queue="default", name="watch_the_backups")
def watch_the_backups(timestamp: int) -> None:
    """The two overdue tests, once an hour: no Snapshot in 26 hours, a drill
    more than three days late. Each writes one audit row a day while it holds,
    so the log shows the gap without filling with it, and each sends the
    Operator one message a day."""
    from core import backups

    backups.watch()


@app.task(queue="default", name="send_email")
def send_email(**fields) -> None:
    """One message to the relay: three tries within thirty minutes, then dropped.

    The first try is at once; the second 5 minutes on; the third 25 minutes
    on. Each try is its own task, so a relay that is down does not hold the
    worker, and the third failure writes the "Email failed" row.
    """
    from core import mail

    wait = mail.attempt(**fields)
    if wait is not None:
        fields["tries"] = fields.get("tries", 1) + 1
        send_email.configure(schedule_in={"minutes": wait}).defer(**fields)


@app.task(queue="media", name="render_clip")
def render_clip(clip_id: str) -> None:
    """Cut one Clip from the Playback copy.

    On the media queue, so a Clip render never waits behind a transcription
    and never holds one up. It is not a Job: it does not keep a Workspace
    alive and it takes no place in the line.
    """
    from core import clip_work
    from core.clips import Clip

    clip = Clip.objects.filter(pk=clip_id).select_related("recording").first()
    if clip is None:
        # The Recording went while this waited its turn, and the half-made
        # file went with its folder. There is nothing to do.
        log.info("clip %s is gone; nothing to render", clip_id)
        return

    clip_work.render(clip)


@app.periodic(cron="*/10 * * * *")
@app.task(
    queue="default",
    name="retry_stalled_jobs",
    queueing_lock="retry_stalled_jobs",
)
async def retry_stalled_jobs(timestamp: int) -> None:
    """Give back the background work of a worker that died holding it.

    Not the transcription queue: that is the service's line, and a Run lost
    there fails with its own reason class and offers Retry. This is the app's
    own background jobs, the media work and the polls and the schedules. A
    worker writes a heartbeat every ten seconds, and one whose heartbeat is
    over thirty seconds old is considered stalled; its jobs are still marked
    as being done and would sit there for ever.

    The queueing lock means two workers cannot both be putting the same jobs
    back at once.
    """
    stalled = await app.job_manager.get_stalled_jobs()
    for job in stalled:
        log.warning("job %s was left by a worker that stopped; queued again", job.id)
        await app.job_manager.retry_job(job)
