"""Placing by sound and the panel for what is not on the clock (Phase 10
chapter 5, v1.186.0).

A clockless video is compared on the media worker with the placed videos of
its case, those of its file's day first and near the file's own time, and
the best match is kept with its surety; the panel's rows carry the file's
words, the sound line and the presses; Place it there writes the clock as
by sound with the match's strength and the video it followed, and nothing
is placed by the app itself; Not this sets the suggestion aside; the clock
read and every placing ask the case's clockless videos again; the chips and
the Date strip count what is not on the clock; the bars carry the surety.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from core import (
    audit,
    case_chronology,
    clock_match,
    incident_strip,
    incidents,
    settings_store,
    sound_match,
)
from core.cases import Case
from core.models import User
from core.notes import MomentNote
from core.recordings import Batch, MediaState, Recording, Side
from tests.helpers import signed_in

PASSWORD = "a-long-enough-password"
DAY = dt.date(2025, 11, 6)
HERE = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def switches(db, settings, tmp_path):
    settings.DATA_DIR = tmp_path
    settings_store.set_to("folder_management", True)
    settings_store.set_to("incidents", True)
    settings_store.set_to("incidents_sound_match", True)


@pytest.fixture
def owner(db):
    return User.objects.create_local_admin("sound-owner", PASSWORD)


@pytest.fixture
def a_case(owner):
    return Case.objects.create(owner=owner, name="Harbour Street stop")


@pytest.fixture
def no_worker(monkeypatch):
    """The media worker's task kept from running; what was deferred, counted."""
    from core import tasks

    deferred = []
    monkeypatch.setattr(tasks.match_clock, "defer", lambda **kw: deferred.append(kw))
    # The commit hooks run at once, as they would after the request.
    monkeypatch.setattr(clock_match.transaction, "on_commit", lambda fn, **kw: fn())
    return deferred


def a_video(owner, case, title, *, time=None, file_time=None, seconds=1800.0):
    """A video: on the clock by its stamp when `time` is given, else
    clockless; `file_time` is the file's own UTC creation time."""
    stamp = (
        {"date": "11/06/2025", "time": time, "at": 2.0, "checked": True} if time else {}
    )
    tags = {"creation_time": file_time} if file_time else {}
    one = Recording.objects.create(
        batch=Batch.objects.create(user=owner),
        user=owner,
        case=case,
        title=title,
        original_filename=f"{title}.mp4",
        media_state=MediaState.READY,
        duration_seconds=seconds,
        playback_ready=True,
        recording_type="Body camera",
        stamp=stamp,
        probe={"streams": [{"codec_type": "video"}], "format": {"tags": tags}},
    )
    one.folder.mkdir(parents=True, exist_ok=True)
    Side.objects.create(recording=one, number=1)
    (one.folder / "asr-side1.wav").write_bytes(b"x")
    return one


def test_a_clockless_video_is_matched_near_its_files_time_and_kept_with_its_surety(
    owner, a_case, no_worker, monkeypatch, settings
):
    settings.TIME_ZONE = "UTC"
    # Two placed videos on the day; the clockless one's file says 20:26:04
    # UTC, ninety seconds into the first camera.
    first = a_video(owner, a_case, "BWC1-1", time="20:24:36")
    a_video(owner, a_case, "BWC2-1", time="20:40:00")
    loose = a_video(owner, a_case, "Interview", file_time="2025-11-06T20:26:04Z")
    other_day = a_video(owner, a_case, "Cell-9", time="08:00:00")
    other_day.stamp["date"] = "11/07/2025"
    other_day.save(update_fields=["stamp"])
    # The candidates: the file's day only, the nearest first.
    found = [one.title for one, _date, _start in clock_match.candidates(loose)]
    assert found == ["BWC1-1", "BWC2-1"]
    assert clock_match.ask(loose) and len(no_worker) == 1
    match = clock_match.ClockMatch.objects.get(recording=loose)
    assert match.state == "queued"
    asked = []

    def by_window(a, b, expected=None, window=None):
        asked.append((Path(b).parent.name, round(expected), window))
        # Clear against the first camera, nothing much against the second.
        if a == first.sides.first().asr_path:
            return sound_match.Match(expected + 0.4, 2.5)
        return sound_match.Match(expected + 0.1, 1.0)

    monkeypatch.setattr(sound_match, "lag_between", by_window)
    clock_match.run(str(loose.pk))
    match.refresh_from_db()
    assert match.state == "done" and match.surety == "clear" and match.near_file
    assert match.against_id == first.pk
    assert match.lag == pytest.approx(90.4, abs=0.01)
    # The first search was near the file's time: ninety seconds after the start.
    assert asked[0] == (loose.folder.name, 90, incidents.NEAR_WINDOW)
    at = clock_match.placed_at_of(match)
    assert at[0] == DAY and at[1] == pytest.approx(
        20 * 3600 + 24 * 60 + 34.0 + 90.4, abs=0.01
    )
    assert clock_match.may_place(match)
    # The panel row: the file's words, the sound line, Place it there.
    rows = clock_match.rows_of(a_case)
    assert [row["title"] for row in rows] == ["Interview"]
    row = rows[0]
    assert row["file"]["date"] == "2025-11-06" and row["still"].endswith("still?t=0.0")
    assert row["sound"]["against"] == "BWC1-1" and row["sound"]["may_place"]
    assert row["sound"]["surety"]["word"] == "Clear" and row["rank"] == 0


def test_place_it_there_writes_the_clock_as_by_sound_and_not_this_sets_it_aside(
    owner, a_case, no_worker, monkeypatch, client
):
    first = a_video(owner, a_case, "BWC1-1", time="20:24:36")
    loose = a_video(owner, a_case, "Interview", file_time="2025-11-06T20:26:04Z")
    clock_match.ask(loose)
    monkeypatch.setattr(
        sound_match, "lag_between", lambda a, b, **kw: sound_match.Match(100.0, 2.5)
    )
    clock_match.run(str(loose.pk))
    signed_in(client, owner)
    before = audit.Row.objects.count()
    got = client.post(
        f"/recording/{loose.pk}/clock/by-sound", content_type="application/json"
    )
    assert got.status_code == 200 and got.json()["placed"].startswith("by sound")
    loose.refresh_from_db()
    date, start, how = case_chronology.clock_of(loose)
    assert how == case_chronology.SOUND and date == DAY
    assert start == pytest.approx(20 * 3600 + 24 * 60 + 34.0 + 100.0)
    assert loose.clock_strength == 2.5 and loose.clock_follows_id == first.pk
    assert case_chronology.placed_words(loose) == "by sound, sound-owner"
    assert case_chronology.clock_surety(loose)["word"] == "Clear"
    # One audit row, the how and never a time.
    row = audit.Row.objects.order_by("-pk").first()
    assert audit.Row.objects.count() == before + 1
    assert row.event == "recording placed on the clock"
    assert row.details.get("how") == "sound"
    assert "20:" not in str(row.details)
    # Placed, it leaves the panel; its bar carries the surety word.
    assert clock_match.rows_of(a_case) == []
    day = case_chronology.day_of(a_case, DAY, strip=True)
    sureties = {b["title"]: b["surety"]["word"] for b in day["bars"]}
    assert sureties == {"BWC1-1": "Clear", "Interview": "Clear"}
    # Taken off the clock, it is asked again and is back on the panel.
    no_worker.clear()
    assert client.post(f"/recording/{loose.pk}/clock/off").status_code == 200
    loose.refresh_from_db()
    assert loose.clock_how == "" and loose.clock_follows_id is None
    assert len(no_worker) == 1
    # Not this: the suggestion set aside; the row keeps Type a time and the
    # match is not asked for again.
    assert client.post(f"/recording/{loose.pk}/clock/not-this").status_code == 200
    rows = clock_match.rows_of(a_case)
    assert rows[0]["set_aside"] and rows[0]["sound"] is None
    assert not clock_match.ask(loose)
    # A stranger is told not found.
    stranger = User.objects.create(username="stranger", display_name="stranger")
    signed_in(client, stranger)
    assert client.post(f"/recording/{loose.pk}/clock/by-sound").status_code == 404


def test_an_unclear_match_is_never_placed_by_the_app(
    owner, a_case, no_worker, monkeypatch
):
    a_video(owner, a_case, "BWC1-1", time="20:24:36")
    # No time in its file: the whole range is searched, Unclear whatever
    # the strength.
    loose = a_video(owner, a_case, "Yard-3")
    assert clock_match.ask(loose)
    monkeypatch.setattr(
        sound_match, "lag_between", lambda a, b, **kw: sound_match.Match(100.0, 4.0)
    )
    clock_match.run(str(loose.pk))
    match = clock_match.ClockMatch.objects.get(recording=loose)
    assert match.state == "done" and match.surety == "unclear" and not match.near_file
    assert not clock_match.may_place(match)
    with pytest.raises(ValueError):
        clock_match.place_by_sound(loose, by=owner)
    row = clock_match.rows_of(a_case)[0]
    assert row["sound"]["surety"]["word"] == "Unclear" and not row["sound"]["may_place"]
    assert row["file"] is None and row["rank"] == 2
    # Nothing to compare with: failed, with its reason.
    (loose.folder / "asr-side1.wav").unlink()
    clock_match.ask(loose)
    clock_match.run(str(loose.pk))
    match.refresh_from_db()
    assert match.state == "failed" and match.reason == "no sound to compare"


def test_the_clock_read_and_every_placing_ask_the_cases_clockless_videos(
    owner, a_case, no_worker
):
    placed = a_video(owner, a_case, "BWC1-1", time="20:24:36")
    loose = a_video(owner, a_case, "Interview", file_time="2025-11-06T20:26:04Z")
    # The stamp read found no clock: this one is asked.
    clock_match.after_stamp(loose)
    assert [kw["recording_id"] for kw in no_worker] == [str(loose.pk)]
    # The stamp read found a clock on another video: the clockless ones are
    # asked again.
    no_worker.clear()
    clock_match.after_stamp(placed)
    assert [kw["recording_id"] for kw in no_worker] == [str(loose.pk)]
    # A placing by hand asks again too; the setting off, nothing is asked.
    no_worker.clear()
    other = a_video(owner, a_case, "Van-2")
    case_chronology.place(other, DAY, 15 * 3600.0, by=owner, how="hand")
    assert sorted(kw["recording_id"] for kw in no_worker) == [str(loose.pk)]
    no_worker.clear()
    settings_store.set_to("incidents_sound_match", False)
    assert not clock_match.ask(loose) and no_worker == []
    # Stale rows are asked again by the minute's sweep.
    settings_store.set_to("incidents_sound_match", True)
    clock_match.ask(loose)
    match = clock_match.ClockMatch.objects.get(recording=loose)
    match.asked_at = match.asked_at - dt.timedelta(minutes=20)
    match.save(update_fields=["asked_at"])
    no_worker.clear()
    assert clock_match.requeue_stale() == 1 and len(no_worker) == 1


def test_the_chips_the_date_strip_and_the_strip_json_carry_what_is_not_on_the_clock(
    owner, a_case, no_worker, client, settings
):
    settings.TIME_ZONE = "UTC"
    on_clock = a_video(owner, a_case, "BWC1-1", time="20:24:36")
    MomentNote.objects.create(recording=on_clock, at=10.0, note="a note", note_by=owner)
    a_video(owner, a_case, "Interview", file_time="2025-11-06T20:26:04Z")
    a_video(owner, a_case, "Yard-3")
    days = incident_strip.days(a_case)
    assert len(days) == 1 and days[0]["unclocked"] == 1
    strip = case_chronology.days_of(a_case)
    assert strip[0]["unclocked"] == 1
    signed_in(client, owner)
    told = client.get(f"/case/{a_case.pk}/incidents/strip.json").json()
    assert told["sound_on"] and told["panel_most"] == clock_match.PANEL_MOST
    assert [row["title"] for row in told["unclocked"]] == ["Interview", "Yard-3"]
    assert told["days"][0]["unclocked"] == 1
    assert told["day"]["bars"][0]["surety"]["word"] == "Clear"


def test_the_script_and_the_stylesheet_draw_the_panel():
    script = (HERE / "static" / "chronology.js").read_text(encoding="utf-8")
    for piece in (
        "function panel(d)",
        "function panelRow(r)",
        "/clock/by-sound",
        "/clock/not-this",
        "Place it there",
        "Place by the day",
        "data-rail-sound",
        "Matching the sound; about a minute.",
        "not on the clock",
        '(one.unclocked ? " ring" : "")',
        "stripMode && b.surety ? b.surety.word",
    ):
        assert piece in script, piece
    # The strip draws no rail: the panel is the videos' place.
    assert 'if (stripMode) { return ""; }\n    var rows = d.rail' in script
    css = (HERE / "static" / "app.css").read_text(encoding="utf-8")
    for rule in (
        ".unclocked-panel {",
        ".unclocked-panel .urow {",
        "button.ring::before",
    ):
        assert rule in css, rule
