"""v1.45.0: the recording page's first layout slice.

The rules checked here: the left rail is gone and what it held is where it is
used (the search box in the header with its count, the exports in an Export
menu, the housekeeping in a More menu with Delete last, the speakers a strip
at the head of the transcript); the pop-out control sits on the picture and
only on a video; the shared scripts still find Process again and Delete by
their classes; nothing office-specific, and no em dash, in the page.
"""

from __future__ import annotations

import pytest
from core import settings_store
from core.jobs import Segment, Transcript
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording

PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("asker", PASSWORD)


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def a_recording(person, video=True, with_transcript=True):
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        title="Stop",
        original_filename="bodycam.mp4" if video else "call.m4a",
        media_state=MediaState.READY,
        duration_seconds=900.0,
        diarize=True,
        playback_ready=True,
    )
    recording.folder.mkdir(parents=True, exist_ok=True)
    (recording.folder / ("playback.mp4" if video else "playback.m4a")).write_bytes(
        b"not really media"
    )
    if with_transcript:
        transcript = Transcript.objects.create(recording=recording, language="en")
        for start, speaker, text in (
            (0.0, "Speaker 1", "This is Officer Ruiz."),
            (12.4, "Speaker 2", "Look at that, right there."),
        ):
            Segment.objects.create(
                transcript=transcript,
                start=start,
                end=start + 5,
                text=text,
                speaker=speaker,
                speaker_label=speaker.upper().replace(" ", "_"),
            )
    return recording


@pytest.mark.django_db
def test_the_rail_is_gone_and_its_tools_are_where_they_are_used(person, client):
    settings_store.set_to("clips_available", True)
    recording = a_recording(person)
    signed_in(client, person)
    page = client.get(f"/recording/{recording.pk}").content.decode()

    assert 'class="side"' not in page and 'class="foot"' not in page
    assert "No word timing" not in page
    # The search box in the header, with its count beside it.
    assert 'class="search-box"' in page and 'id="search"' in page
    assert 'id="matches"' in page
    # The exports in a menu, the housekeeping in another, Delete last.
    assert 'id="export-menu"' in page and "Export to Word" in page
    assert 'id="more-menu"' in page and 'id="open-shortcuts"' in page
    assert page.index('class="process-again"') < page.index('class="danger delete"')
    assert page.index('class="danger delete"') > page.index('class="sep"')
    assert page.count("Delete this recording") == 1
    # The speakers as a strip at the head of the transcript, hide at its end.
    assert 'id="cast"' in page and 'id="speakers"' in page
    assert 'id="speakers-toggle"' in page
    assert page.index('id="cast"') < page.index('id="transcript"')
    assert page.index('id="speakers"') < page.index('id="speakers-toggle"')
    # The pop-out control on the picture, after the video element.
    assert 'id="pop-out"' in page and 'class="tiny pip"' in page
    assert page.index('id="player"') < page.index('id="pop-out"')
    assert page.index('id="pop-out"') < page.index('id="thumb-grip"')
    # The new clip button is the header's one coloured button.
    assert 'class="primary small" id="new-clip"' in page
    assert chr(0x2014) not in page


@pytest.mark.django_db
def test_sound_alone_has_no_pop_out_and_no_transcript_no_cast(person, client):
    signed_in(client, person)
    audio = a_recording(person, video=False)
    page = client.get(f"/recording/{audio.pk}").content.decode()
    assert 'id="pop-out"' not in page
    assert 'id="cast"' in page and 'id="export-menu"' in page

    waiting = a_recording(person, with_transcript=False)
    page = client.get(f"/recording/{waiting.pk}").content.decode()
    assert 'id="cast"' not in page and 'id="export-menu"' not in page
    # The search box and the More menu are there before the transcript is.
    assert 'id="search"' in page and 'id="more-menu"' in page
    assert 'class="danger delete"' in page and 'class="process-again"' not in page
