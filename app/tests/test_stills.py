"""The stills on the Incidents tab (Phase 10 chapter 5, v1.185.0).

One frame of a video at a moment, cut on request from the playback copy into
a scratch folder that is gone when the answer has left, sent private and
never kept, to whoever may open the recording and nobody else; each bar of
a day carries where its playback starts on the day's clock, and the
picker's rows carry a still's address at the span's start (their own start
for the same-day rows); the script draws the cards' stills six at most and
the picker's as the rows come into view, eight in flight.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from core import case_chronology, media, settings_store, viewer
from core.cases import Case
from core.models import User
from core.notes import MomentNote
from core.recordings import Batch, MediaState, Recording
from tests.helpers import signed_in
from tests.test_prepare import a_recording

PASSWORD = "a-long-enough-password"
DAY = dt.date(2025, 11, 6)
HERE = Path(__file__).resolve().parents[1]
# The smallest JPEG header, for a frame the stand-in grabber writes.
JPEG = b"\xff\xd8\xff\xdb" + b"\x00" * 16 + b"\xff\xd9"


@pytest.fixture(autouse=True)
def switches(db):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("incidents", True)


@pytest.fixture
def owner(db):
    return User.objects.create_local_admin("still-owner", PASSWORD)


@pytest.fixture
def a_case(owner):
    return Case.objects.create(owner=owner, name="Harbour Street stop")


def a_video(owner, case, title, time, *, seconds=1800.0):
    return Recording.objects.create(
        batch=Batch.objects.create(user=owner),
        user=owner,
        case=case,
        title=title,
        original_filename=f"{title}.mp4",
        media_state=MediaState.READY,
        duration_seconds=seconds,
        recording_type="Body camera",
        stamp={"date": "11/06/2025", "time": time, "at": 2.0, "checked": True},
        probe={"streams": [{"codec_type": "video"}]},
    )


def test_a_still_is_cut_on_request_and_never_kept(
    owner, a_case, tmp_path, settings, monkeypatch, client
):
    camera = a_recording(owner, tmp_path, settings, case=a_case, title="BWC1-1")
    taken = []

    def grab(source, folder, times, *, height, timeout=0, up=False):
        taken.append((Path(source).name, list(times), height, timeout, Path(folder)))
        target = Path(folder) / "frame-1.jpg"
        target.write_bytes(JPEG)
        return [target]

    monkeypatch.setattr(media, "grab_frames", grab)
    signed_in(client, owner)
    got = client.get(f"/recording/{camera.pk}/still?t=12.5")
    assert got.status_code == 200
    assert got["Content-Type"] == "image/jpeg"
    assert got["Cache-Control"] == "private, no-store"
    assert got.content == JPEG
    # The playback copy at the moment asked, at the still's height, with the
    # short cap; the scratch folder is gone once the answer has left.
    name, times, height, timeout, folder = taken[0]
    assert (name, times, height, timeout) == (
        "playback.mp4",
        [12.5],
        viewer.STILL_HEIGHT,
        viewer.STILL_TIMEOUT,
    )
    assert not folder.exists()
    assert str(folder).startswith(str(settings.SCRATCH_DIR))
    # A moment past the end, and a frame that cannot be cut: not found, and
    # nothing is raised to the page.
    assert client.get(f"/recording/{camera.pk}/still?t=5000").status_code == 404
    monkeypatch.setattr(
        media,
        "grab_frames",
        lambda *a, **k: (_ for _ in ()).throw(media.MediaError("no", "media_failed")),
    )
    assert client.get(f"/recording/{camera.pk}/still?t=1").status_code == 404


def test_a_still_is_for_whoever_may_open_the_recording(
    owner, a_case, tmp_path, settings, monkeypatch, client
):
    camera = a_recording(owner, tmp_path, settings, case=a_case, title="BWC1-1")
    call = a_recording(
        owner, tmp_path, settings, case=a_case, title="Call 0403", video=False
    )
    monkeypatch.setattr(media, "grab_frames", lambda *a, **k: 1 / 0)
    # A stranger is told not found, as for the recording itself.
    stranger = User.objects.create(username="stranger", display_name="stranger")
    signed_in(client, stranger)
    assert client.get(f"/recording/{camera.pk}/still?t=1").status_code == 404
    # The owner: an audio recording has no still.
    signed_in(client, owner)
    assert client.get(f"/recording/{call.pk}/still?t=1").status_code == 404


def test_the_bars_carry_their_zero_and_the_picker_rows_a_still(owner, a_case):
    # Two overlapping videos with notes (a forming bracket) and one loose
    # video in the morning (same day, outside the span).
    one = a_video(owner, a_case, "BWC1-1", "20:24:38")
    two = a_video(owner, a_case, "BWC2-1", "20:26:10")
    morning = a_video(owner, a_case, "Cell-5", "08:30:00")
    MomentNote.objects.create(recording=one, at=120.0, note="a note", note_by=owner)
    MomentNote.objects.create(recording=two, at=300.0, note="a note", note_by=owner)
    day = case_chronology.day_of(a_case, DAY, strip=True)
    zero = {b["id"]: b["zero"] for b in day["bars"]}
    # The stamp at 2.0 s: playback starts two seconds before the clock read.
    assert zero[str(one.pk)] == 20 * 3600 + 24 * 60 + 36.0
    assert zero[str(two.pk)] == 20 * 3600 + 26 * 60 + 8.0
    assert zero[str(morning.pk)] == 8 * 3600 + 30 * 60 - 2.0
    # The picker for the forming span: the span's start from the first
    # camera, the second camera's own first moment (it began later), and the
    # same-day row at its own start.
    span = (zero[str(one.pk)], zero[str(one.pk)] + 1800.0)
    told = case_chronology.span_reading(a_case, DAY, span)
    stills = {row["id"]: row["still"] for row in told["rows"]}
    assert stills[str(one.pk)] == f"/recording/{one.pk}/still?t=0.0"
    assert stills[str(two.pk)] == f"/recording/{two.pk}/still?t=0.0"
    assert stills[str(morning.pk)] == f"/recording/{morning.pk}/still?t=0.0"
    # A span that starts a minute in: a minute into the first camera.
    later = case_chronology.span_reading(a_case, DAY, (span[0] + 60.0, span[1]))
    assert {row["id"]: row["still"] for row in later["rows"]}[str(one.pk)] == (
        f"/recording/{one.pk}/still?t=60.0"
    )
    # The address itself, from a bar that crossed midnight (zero before 0).
    bar = {"id": "x", "from": 0.0, "zero": -600.0}
    assert case_chronology.still_address(bar, 0.0) == "/recording/x/still?t=600.0"
    assert case_chronology.still_address(bar, -900.0) == "/recording/x/still?t=0.0"


def test_the_script_and_the_stylesheet_draw_the_stills():
    script = (HERE / "static" / "chronology.js").read_text(encoding="utf-8")
    assert "function stills(root)" in script and "function stillsHtml" in script
    assert "var STILLS_MOST = 6, STILLS_AT_ONCE = 8;" in script
    assert '/still?t=" + Math.max(0, moment - (b.zero || 0)).toFixed(1)' in script
    assert "more in the picker" in script
    assert "IntersectionObserver" in script
    # Both sheets carry the still column, and the minute's read redraws
    # nothing while the day is unchanged.
    assert script.count("<table><tr><th></th><th></th><th>Recording</th>") == 2
    assert "text === state.lastText" in script
    css = (HERE / "static" / "app.css").read_text(encoding="utf-8")
    for rule in (".stills {", ".still {", ".still.sm {", ".still.none::after {"):
        assert rule in css
