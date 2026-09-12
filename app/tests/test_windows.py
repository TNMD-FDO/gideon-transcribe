"""v1.47.0: a tab in its own window, and the Speakers window.

The rules checked here: a tab of the work area renders alone in a window of
its own, only when the page offers it; the Speakers window (the Speakers page
in a window since v1.50.0) lists the speakers with a key each; one line given
to a Speaker changes that Segment alone, is remembered beside the renames so
Undo puts it back, and writes a row without a name; the recording page
carries the way to both; nothing is offered to somebody who may not open the
recording.
"""

from __future__ import annotations

import json

import pytest
from core import settings_store, viewer
from core.audit import Row
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
            (30.0, "Speaker 3", "That's not mine."),
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
def test_a_tab_renders_alone_in_its_own_window(person, client):
    settings_store.set_to("assistant_available", True)
    settings_store.set_to("moments_available", True)
    settings_store.set_to("clips_available", True)
    recording = a_recording(person)
    signed_in(client, person)

    # The page itself offers the way out, and every tab's panels.
    page = client.get(f"/recording/{recording.pk}").content.decode()
    assert 'id="open-window"' in page and 'id="manage-speakers"' in page
    assert page.count('data-panel="details"') == 3  # the tab and its two panels
    assert 'data-panel="chat"' in page and 'data-panel="clips"' in page

    chat = client.get(f"/recording/{recording.pk}/window/chat")
    assert chat.status_code == 200
    body = chat.content.decode()
    assert 'class="panel chat" data-panel="chat"' in body
    for other in ("summary", "clips", "details"):
        assert f'data-panel="{other}"' not in body, other
    assert 'windowPanel: "chat"' in body and "viewer-window.js" in body
    assert "assistant.js" in body and "chat-ui.js" in body
    assert 'class="winhead"' in body and "Chat" in body
    assert 'class="tabbar"' not in body and 'id="player"' not in body

    clips = client.get(f"/recording/{recording.pk}/window/clips").content.decode()
    assert clips.count('data-panel="clips"') == 2 and "clip-tool.js" in clips
    assert "assistant.js" not in clips

    details = client.get(f"/recording/{recording.pk}/window/details").content.decode()
    assert details.count('data-panel="details"') == 2

    # What the page does not offer, the window does not either.
    assert client.get(f"/recording/{recording.pk}/window/nothing").status_code == 404
    settings_store.set_to("moments_available", False)
    assert client.get(f"/recording/{recording.pk}/window/moments").status_code == 404
    settings_store.set_to("assistant_available", False)
    assert client.get(f"/recording/{recording.pk}/window/chat").status_code == 404
    assert client.get(f"/recording/{recording.pk}/window/details").status_code == 200
    audio = a_recording(person, video=False)
    settings_store.set_to("assistant_available", True)
    settings_store.set_to("moments_available", True)
    assert client.get(f"/recording/{audio.pk}/window/moments").status_code == 404
    assert client.get(f"/recording/{audio.pk}/window/summary").status_code == 200


@pytest.mark.django_db
def test_the_speakers_window_is_the_speakers_page_with_a_key_each(person, client):
    recording = a_recording(person)
    signed_in(client, person)
    body = client.get(f"/recording/{recording.pk}/window/speakers").content.decode()
    assert 'class="viewer speakers-page window"' in body and 'id="cards"' in body
    assert body.count('class="sp-card unnamed"') == 3
    assert '<kbd class="k">1</kbd>' in body and '<kbd class="k">3</kbd>' in body
    assert 'id="now-who"' in body and 'id="speakers-undo"' in body
    assert "inWindow: true" in body and "speakers-page.js" in body
    assert "assistant.js" not in body and "clip-tool.js" not in body
    # The window plays the recording itself: the picture, the lanes, the transport.
    assert '<video id="player"' in body and 'id="play"' in body
    assert 'id="lanes"' in body and body.index('id="lanes"') > body.index('id="play"')
    audio = a_recording(person, video=False)
    sound = client.get(f"/recording/{audio.pk}/window/speakers").content.decode()
    assert '<audio id="player"' in sound and "<video" not in sound
    # A tab's window has no player of its own.
    settings_store.set_to("assistant_available", True)
    chat = client.get(f"/recording/{recording.pk}/window/chat").content.decode()
    assert 'id="player"' not in chat
    # Not before the transcript exists.
    waiting = a_recording(person, with_transcript=False)
    assert client.get(f"/recording/{waiting.pk}/window/speakers").status_code == 404


@pytest.mark.django_db
def test_one_line_given_to_a_speaker_is_remembered_and_undone(
    person, client, monkeypatch
):
    recording = a_recording(person)
    signed_in(client, person)
    line = recording.transcript.segments.get(start=30.0)
    url = f"/recording/{recording.pk}/segment/{line.pk}/speaker"

    answer = client.post(
        url, data=json.dumps({"speaker": "Speaker 2"}), content_type="application/json"
    )
    assert answer.status_code == 200
    assert answer.json() == {
        "changed": 1,
        "undo": "giving one line of Speaker 3 to Speaker 2",
    }
    line.refresh_from_db()
    assert line.speaker == "Speaker 2"
    # The other lines are untouched.
    assert list(
        recording.transcript.segments.order_by("start").values_list(
            "speaker", flat=True
        )
    ) == ["Speaker 1", "Speaker 2", "Speaker 2"]
    recording.transcript.refresh_from_db()
    last = recording.transcript.speaker_changes[-1]
    assert last["line"] is True and last["segments"] == [line.pk]
    assert last["from"] == "Speaker 3" and last["to"] == "Speaker 2"
    row = Row.objects.get(event="Speaker changed on a line")
    assert row.details.get("segments_changed") == 1
    assert "Speaker" not in json.dumps(row.details)

    # The same name again changes nothing; Undo puts the line back.
    again = client.post(
        url, data=json.dumps({"speaker": "Speaker 2"}), content_type="application/json"
    )
    assert again.json()["changed"] == 0
    undone = client.post(f"/recording/{recording.pk}/speakers/undo")
    assert undone.status_code == 200 and undone.json()["restored"] == 1
    line.refresh_from_db()
    assert line.speaker == "Speaker 3"

    # A missing name, a missing line, and a transcript being replaced.
    assert (
        client.post(url, data="{}", content_type="application/json").status_code == 400
    )
    assert (
        client.post(
            f"/recording/{recording.pk}/segment/999999/speaker",
            data=json.dumps({"speaker": "Speaker 1"}),
            content_type="application/json",
        ).status_code
        == 404
    )
    monkeypatch.setattr(viewer, "being_replaced", lambda recording: True)
    assert (
        client.post(
            url,
            data=json.dumps({"speaker": "Speaker 1"}),
            content_type="application/json",
        ).status_code
        == 409
    )
