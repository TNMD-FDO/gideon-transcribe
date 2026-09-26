"""Phase 5 chapter 4, The diarizer.

The rules checked here: the Diarizer setting exists on the Transcription
defaults page and starts at nemotron; every job carries the choice; the
speaker-count hint and the stretch embeddings go only with pyannote; the
Upload page greys the hint under Nemotron with its reason; the Details tab
and the exports say which model told the voices apart.
"""

from __future__ import annotations

import pytest
from core import exports, queue, settings_store, uploads, whisperx
from core.jobs import Job, Run
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording, Side
from django.urls import reverse

PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("asker", PASSWORD)


def a_run(person, **fields) -> Run:
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        title="a stop",
        original_filename="a-stop.mp4",
        media_state=MediaState.READY,
        diarize=True,
        **fields,
    )
    side = Side.objects.create(recording=recording, number=1)
    job = Job.objects.create(recording=recording, batch=recording.batch)
    return Run.objects.create(job=job, side=side)


@pytest.mark.django_db
def test_the_setting_starts_at_nemotron_and_every_job_carries_it(person):
    assert settings_store.diarizer() == "nemotron"
    known = settings_store.definition("diarizer")
    assert known.page == settings_store.TRANSCRIPTION
    assert known.choices == ("nemotron", "pyannote")
    run = a_run(person, speakers_exactly=3)
    asked = queue.request_for(run)
    assert asked["diarizer"] == "nemotron"
    # The hint is pyannote's alone: not sent under Nemotron, kept unused.
    assert "speakers" not in asked
    settings_store.set_to("diarizer", "pyannote")
    asked = queue.request_for(run)
    assert asked["diarizer"] == "pyannote"
    assert asked["speakers"] == {"exactly": 3}
    settings_store.set_to("diarizer", "nemotron")


@pytest.mark.django_db
def test_the_upload_page_greys_the_hint_under_nemotron(client, person, monkeypatch):
    monkeypatch.setattr(whisperx, "is_alive", lambda *a, **k: True)
    monkeypatch.setattr(uploads, "free_disk_bytes", lambda: 10**15)
    client.force_login(person)
    LoginSession.objects.create(user=person, session_key=client.session.session_key)
    page = client.get(reverse("upload")).content.decode()
    assert 'id="hint" disabled' in page
    assert "The diarizer counts the speakers itself" in page
    settings_store.set_to("diarizer", "pyannote")
    page = client.get(reverse("upload")).content.decode()
    assert 'id="hint" disabled' not in page
    assert "counts the speakers itself" not in page
    settings_store.set_to("diarizer", "nemotron")


def test_the_words_for_which_diarizer_ran():
    assert exports.diarizer_words({"diarize": False}) == "not diarized"
    assert (
        exports.diarizer_words(
            {
                "diarize": True,
                "diarizer": "nemotron",
                "diarizer_version": "f667ed73aee5",
            }
        )
        == "Nemotron 3 Diarization (f667ed73)"
    )
    # A result from before the choice existed is pyannote's.
    assert exports.diarizer_words({"diarize": True}) == "pyannote community-1"
