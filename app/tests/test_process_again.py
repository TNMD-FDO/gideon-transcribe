"""Process again remakes the audio the model hears.

It used to hand the file prepared at upload straight back to the service, so a
Recording could never be improved by a change to how audio is prepared: a fix
reached new uploads and nothing already on the disk. The only way to mend a
Recording was to delete it and put it up again, which for a Recording in a
Case would mean losing it.
"""

import pytest
from core import pipeline, tasks, whisperx
from core.jobs import Job, Transcript
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording

PASSWORD = "a-long-enough-password"


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("again", PASSWORD)


@pytest.fixture
def done(person, tmp_path, settings):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    batch = Batch.objects.create(user=person)
    recording = Recording.objects.create(
        batch=batch,
        user=person,
        title="06 camera unknown",
        original_filename="06-camera-unknown.mp4",
        media_state=MediaState.READY,
        duration_seconds=1496.0,
    )
    Transcript.objects.create(recording=recording, language="en")
    return recording


def signed_in(client, person):
    client.force_login(person)
    LoginSession.objects.create(user=person, session_key=client.session.session_key)
    return client


def test_it_prepares_the_audio_again_before_making_a_job(
    done, person, client, monkeypatch
):
    asked = {}
    monkeypatch.setattr(whisperx, "is_alive", lambda: True)
    monkeypatch.setattr(
        tasks.prepare_audio_again, "defer", lambda **fields: asked.update(fields)
    )

    signed_in(client, person)
    answer = client.post(
        f"/recording/{done.pk}/process-again", "{}", "application/json"
    )

    assert answer.status_code == 200
    # The audio comes first, and the Job is made only once it is there: the
    # service must never be handed a file that is being rewritten under it.
    assert asked == {"recording_id": str(done.pk)}
    assert not Job.objects.filter(recording=done).exists()

    done.refresh_from_db()
    assert done.media_state == MediaState.PREPARING
    assert done.batch.is_reprocessing


def test_the_audio_is_made_from_the_uploaded_bytes(done, monkeypatch):
    from core import media
    from core.recordings import Side

    Side.objects.create(recording=done, number=1, kind=Side.WHOLE)
    made = []

    monkeypatch.setattr(
        media,
        "probe",
        lambda path: media.Probe(raw={}, duration_seconds=1496.0, tracks=()),
    )
    monkeypatch.setattr(
        media,
        "make_asr_audio",
        lambda source, target, track, **rest: made.append((source, target)),
    )

    pipeline.prepare_audio_again(done)

    assert len(made) == 1
    source, target = made[0]
    # From the uploaded bytes, which is what they are kept for, and not from
    # the file prepared last time.
    assert source == done.original_path
    assert target.name == "asr-side1.wav"

    done.refresh_from_db()
    assert done.media_state == MediaState.READY


def test_a_recording_that_will_not_prepare_is_failed_and_gets_no_job(done, monkeypatch):
    from core import media
    from core.recordings import Side

    Side.objects.create(recording=done, number=1, kind=Side.WHOLE)

    def refuses(*arguments, **rest):
        raise media.MediaError("no", "media_failed")

    monkeypatch.setattr(
        media,
        "probe",
        lambda path: media.Probe(raw={}, duration_seconds=1496.0, tracks=()),
    )
    monkeypatch.setattr(media, "make_asr_audio", refuses)

    pipeline.prepare_audio_again(done)

    done.refresh_from_db()
    assert done.media_state == MediaState.FAILED
    assert not Job.objects.filter(recording=done).exists()
