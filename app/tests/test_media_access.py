"""Which path Caddy hands the app, and what the app makes of it.

This file exists because of a real failure: Caddy sorts the directives inside
a route into its own order, ran the strip_prefix before the forward_auth, and
asked the app about a path with the `/media` already gone. The app did not
recognise it and refused every recording in the office, silently, from the day
the route was written.
"""

from core import media_access


class Request:
    """Just enough of a request for the path reader."""

    def __init__(self, forwarded=None, path=""):
        self.headers = {"X-Forwarded-Uri": forwarded} if forwarded else {}
        self.META = {"PATH_INFO": path}


def test_the_path_with_the_media_prefix_is_read():
    asked = media_access._wanted(Request("/media/6/095f0352-63a3-4ef9/playback.mp4"))
    assert asked == ("6", "095f0352-63a3-4ef9", "playback.mp4")


def test_the_path_with_the_prefix_already_stripped_is_read():
    # This is what Caddy actually sends when the strip runs first.
    asked = media_access._wanted(Request("/6/095f0352-63a3-4ef9/playback.mp4"))
    assert asked == ("6", "095f0352-63a3-4ef9", "playback.mp4")


def test_a_clip_keeps_its_folder():
    asked = media_access._wanted(Request("/6/095f0352/clips/c23a9213.mp4"))
    assert asked == ("6", "095f0352", "clips/c23a9213.mp4")
    assert asked[2].startswith(media_access.CLIPS)


def test_a_query_string_and_escapes_are_read_past():
    asked = media_access._wanted(Request("/media/6/095f0352/playback.mp4?t=12"))
    assert asked == ("6", "095f0352", "playback.mp4")


def test_something_that_is_not_a_media_path_is_refused():
    assert media_access._wanted(Request("/6")) is None
    assert media_access._wanted(Request("/media/6")) is None
    assert media_access._wanted(Request("")) is None


def test_only_the_three_files_and_clips_may_be_served():
    # The uploaded bytes and the audio the model heard are never served: what
    # a person keeps, they keep as an export or a clip.
    assert "playback.mp4" in media_access.SERVABLE
    assert "playback.m4a" in media_access.SERVABLE
    assert "waveform.json" in media_access.SERVABLE
    assert "original.mp4" not in media_access.SERVABLE
    assert "asr-side1.wav" not in media_access.SERVABLE


def test_a_case_path_is_read_with_and_without_its_prefix():
    # A Recording in a Case hangs off /case-media/<case>/<recording>/, because
    # Caddy is given cases/ as a second root and never one root over the whole
    # App data folder.
    case = "3f2a1b4c-0000-4000-8000-000000000001"
    with_prefix = media_access._wanted(
        Request(f"/case-media/{case}/rec-1/playback.mp4")
    )
    without = media_access._wanted(Request(f"/{case}/rec-1/playback.mp4"))
    assert with_prefix == (case, "rec-1", "playback.mp4")
    assert without == with_prefix


class Standing:
    """A Recording, as far as the URL builder is concerned."""

    def __init__(self, case_id=None, user_id=6, pk="rec-1"):
        self.case_id = case_id
        self.user_id = user_id
        self.pk = pk


def test_a_workspace_recording_hangs_off_media():
    assert media_access.media_root(Standing()) == "/media/6/rec-1"


def test_a_recording_in_a_case_hangs_off_case_media():
    assert media_access.media_root(Standing(case_id="c-9")) == "/case-media/c-9/rec-1"


def test_the_holder_is_the_case_once_there_is_one():
    assert media_access.holder_of(Standing()) == "6"
    assert media_access.holder_of(Standing(case_id="c-9")) == "c-9"
