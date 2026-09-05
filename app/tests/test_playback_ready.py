"""The viewer plays a copy only once it is whole.

Recognition on the GPU finishes before the playback copy of a long video is
finished on the CPU. For that minute the copy exists on disk but is still
being written, with its index not yet in place, and a browser handed it finds
no index, reads blindly, and stalls. So the copy is written under another name
until it is whole, the viewer decides by the recording's own flag and never by
whether a file exists, and a page that opened too early asks again.
"""

from pathlib import Path

import pytest
from core import media, media_access
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording
from django.urls import reverse

PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"
    return tmp_path


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("viewer", PASSWORD)


def a_video(person, ready: bool) -> Recording:
    """A recording whose playback.mp4 is on disk, ready or not yet."""
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        title="a body-worn camera",
        original_filename="bwc.mp4",
        media_state=MediaState.READY,
        playback_ready=ready,
        # The probe says there is a picture, which is how the overlay knows
        # to say "video" before any copy exists to judge by.
        probe={
            "streams": [{"codec_type": "video", "codec_name": "h264", "height": 720}]
        },
    )
    recording.folder.mkdir(parents=True, exist_ok=True)
    (recording.folder / "playback.mp4").write_bytes(b"half written or whole")
    (recording.folder / "waveform.json").write_text("{}", encoding="utf-8")
    return recording


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


# The name a copy is written under -------------------------------------------------


def test_the_partial_name_keeps_the_extension_and_is_not_the_final_name():
    assert media.partial_name(Path("playback.mp4")) == Path("playback.part.mp4")
    assert media.partial_name(Path("playback.m4a")) == Path("playback.part.m4a")
    assert media.partial_name(Path("waveform.json")) == Path("waveform.part.json")


def test_a_partial_file_is_never_one_caddy_would_serve():
    # The media gate serves exact names only, so a copy still being written is
    # invisible to a browser that guesses the name.
    for name in ("playback.part.mp4", "playback.part.m4a", "waveform.part.json"):
        assert name not in media_access.SERVABLE


def test_the_copy_is_renamed_only_when_ffmpeg_finished(tmp_path, monkeypatch):
    target = tmp_path / "playback.mp4"

    class Finished:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(arguments, **rest):
        # ffmpeg writes to the .part name it was given.
        Path(arguments[-1]).write_bytes(b"whole")
        return Finished()

    monkeypatch.setattr(media, "_run", fake_run)
    monkeypatch.setattr(media, "_measure_loudness", lambda *a, **k: {})
    probed = media.Probe(
        raw={"streams": [], "format": {}}, duration_seconds=1.0, tracks=()
    )

    media.make_playback_copy(tmp_path / "in.mp4", target, probed, "none")

    assert target.read_bytes() == b"whole"
    assert not media.partial_name(target).exists()


def test_a_failed_copy_leaves_no_file_under_either_name(tmp_path, monkeypatch):
    target = tmp_path / "playback.mp4"

    class Failed:
        returncode = 1
        stdout = ""
        stderr = "boom"

    def fake_run(arguments, **rest):
        Path(arguments[-1]).write_bytes(b"partial")
        return Failed()

    monkeypatch.setattr(media, "_run", fake_run)
    monkeypatch.setattr(media, "_measure_loudness", lambda *a, **k: {})
    probed = media.Probe(
        raw={"streams": [], "format": {}}, duration_seconds=1.0, tracks=()
    )

    with pytest.raises(media.MediaError):
        media.make_playback_copy(tmp_path / "in.mp4", target, probed, "none")

    assert not target.exists()
    assert not media.partial_name(target).exists()


# The viewer's decision --------------------------------------------------------------


@pytest.mark.django_db
def test_a_copy_that_is_present_but_not_ready_is_not_offered(person, client):
    recording = a_video(person, ready=False)
    signed_in(client, person)

    page = client.get(reverse("viewer", args=[recording.pk])).content.decode()

    assert "<video" not in page
    assert "Preparing video" in page
    assert "This page notices by itself" in page
    assert "canPlay: false" in page
    assert client.get(reverse("media-state", args=[recording.pk])).json() == {
        "ready": False
    }


@pytest.mark.django_db
def test_a_ready_copy_is_offered_and_the_page_stops_asking(person, client):
    recording = a_video(person, ready=True)
    signed_in(client, person)

    page = client.get(reverse("viewer", args=[recording.pk])).content.decode()

    assert "<video" in page
    assert "canPlay: true" in page
    assert client.get(reverse("media-state", args=[recording.pk])).json() == {
        "ready": True
    }


@pytest.mark.django_db
def test_the_readiness_question_is_nobody_elses(person, client):
    recording = a_video(person, ready=True)
    stranger = User.objects.create_local_admin("stranger", PASSWORD)
    stranger.is_local = False
    stranger.save()
    signed_in(client, stranger)

    assert client.get(reverse("media-state", args=[recording.pk])).status_code == 404
