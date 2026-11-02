"""v1.186.1: a camera's date in any form it burns it, and a video placed by
the day alone undone from the page.

An aircraft camera printed its date as day, month letters and year with no
separators, which the Recording's clock read as no date and so no clock,
though the time was read and checked; one reader now knows every form, used
by the clock, the strip's incident days and the pages' words. A video placed
by the day alone has no bar to press, so it sits on the Not-on-the-clock
panel with Take off the clock, and the Time unknown head offers Set its time
and Take off the clock.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from core import (
    case_chronology,
    clock_match,
    incident_strip,
    incidents,
    prompts,
    settings_store,
)
from core.cases import Case
from core.models import User
from core.notes import MomentNote
from core.recordings import Batch, MediaState, Recording

PASSWORD = "a-long-enough-password"
HERE = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def switches(db):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("incidents", True)


@pytest.fixture
def owner(db):
    return User.objects.create_local_admin("dates-owner", PASSWORD)


@pytest.fixture
def a_case(owner):
    return Case.objects.create(owner=owner, name="Miller")


def a_video(owner, case, title, *, stamp=None, seconds=900.0):
    return Recording.objects.create(
        batch=Batch.objects.create(user=owner),
        user=owner,
        case=case,
        title=title,
        original_filename=f"{title}.mp4",
        media_state=MediaState.READY,
        duration_seconds=seconds,
        playback_ready=True,
        recording_type="Body camera",
        stamp=stamp if stamp is not None else {},
        probe={"streams": [{"codec_type": "video"}]},
    )


def test_a_printed_date_is_read_in_every_form_a_camera_burns_it():
    want = dt.date(2026, 11, 2)
    for text in (
        "11/02/2026",
        "2026-11-02",
        "11-02-2026",
        "02NOV2026",
        "02nov2026",
        "2 Nov 2026",
        "02-NOV-2026",
        "02/Nov/2026",
        "Nov 02 2026",
        "Nov 2, 2026",
        "02NOV26",
    ):
        assert prompts.stamp_date_of(text) == want, text
    for text in ("", "   ", "yesterday", "02NOV99", "31/31/2026", "2026"):
        assert prompts.stamp_date_of(text) is None, text
    assert incidents.plain_date("02NOV2026") == "02 Nov 2026"
    assert incidents.plain_date("no date") == "no date"


def test_an_aircraft_cameras_stamp_puts_it_on_the_clock(owner, a_case):
    # The stamp as the clock read kept it: a checked time, the date with no
    # separators, the data bar's other words.
    one = a_video(
        owner,
        a_case,
        "AirOne",
        stamp={
            "date": "02NOV2026",
            "time": "14:02:33",
            "camera": "AIR",
            "at": 2.0,
            "checked": True,
            "other": "the data bar",
        },
    )
    date, start, how = case_chronology.clock_of(one)
    assert (date, how) == (dt.date(2026, 11, 2), case_chronology.CLOCK)
    assert start == 14 * 3600 + 2 * 60 + 31.0
    assert case_chronology.clock_surety(one)["word"] == "Clear"
    # Not on the panel, and the strip has its day.
    assert clock_match.rows_of(a_case) == []
    assert [d["date"] for d in incident_strip.days(a_case)] == ["2026-11-02"]
    # An incident's clock date in that form is a day of the strip too.
    incident = incidents.make(a_case, "The stop", [one], by=owner)
    incident.clock_date = "02NOV2026"
    incident.save(update_fields=["clock_date"])
    assert incident_strip._incident_days(a_case) == {dt.date(2026, 11, 2)}


def test_a_video_placed_by_the_day_alone_sits_on_the_panel_with_take_off(owner, a_case):
    day = dt.date(2026, 11, 2)
    placed = a_video(
        owner,
        a_case,
        "BWC1-1",
        stamp={"date": "11/02/2026", "time": "14:00:00", "at": 2.0, "checked": True},
    )
    alone = a_video(owner, a_case, "AirOne")
    loose = a_video(owner, a_case, "Cell-9")
    MomentNote.objects.create(recording=alone, at=10.0, note="a note", note_by=owner)
    case_chronology.place(alone, day, None, by=owner, how=case_chronology.DAY)
    rows = clock_match.rows_of(a_case)
    assert [r["title"] for r in rows] == ["Cell-9", "AirOne"]
    row = rows[1]
    assert row["placed_by_day"] and row["sound"] is None and row["rank"] == 4
    assert row["day_words"] == "2 Nov 2026" and row["placed"].startswith("by the day")
    assert row["notes"] == 1
    assert not rows[0]["placed_by_day"]
    # Never matched by sound: it has a day.
    assert not clock_match._clockless(alone)
    # Counted on its own day, on the chips and the Date strip.
    assert clock_match.unclocked_by_day(a_case) == {day: 1}
    assert incident_strip.days(a_case)[0]["unclocked"] == 1
    assert case_chronology.days_of(a_case)[0]["unclocked"] == 1
    # Its notes sit under Time unknown, and taking it off the clock puts it
    # back among the clockless.
    reading = case_chronology.day_of(a_case, day)
    assert [e["recording"] for e in reading["unknown"]] == [str(alone.pk)]
    assert case_chronology.unplace(alone, by=owner)
    rows = clock_match.rows_of(a_case)
    assert all(not r["placed_by_day"] for r in rows) and len(rows) == 2
    assert placed.pk and loose.pk


def test_the_script_offers_the_presses():
    script = (HERE / "static" / "chronology.js").read_text(encoding="utf-8")
    for piece in (
        "r.placed_by_day",
        "Placed by the day alone, no hour, on ",
        "data-off='",
        "data-set-time='",
        "data-off-day='",
        ">Set its time<",
        ">Take off the clock<",
    ):
        assert piece in script, piece
