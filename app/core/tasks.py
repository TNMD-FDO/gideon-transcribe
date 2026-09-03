"""The background work, and when it runs.

Three queues on one image, as the specification fixes: `media` for ffmpeg and
audiowaveform, `default` for the queue and the schedules, and `llm` for the AI
assistant. Procrastinate runs them on the app's own PostgreSQL, which is why
there is no Redis, no Valkey, and no scheduler container.

Media work is CPU only. No container built from the app image ever sees a GPU.
"""

from __future__ import annotations

import logging

from procrastinate.contrib.django import app

log = logging.getLogger("transcribe.tasks")


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
