"""The case's chronology (Phase 10 chapter 1, ADR 0027).

The recording's clock: read from the stamp, placed by hand, by the day or
from the file, refused where the stamp stands, taken off, audited. The day's
reading: the Date strip, the rail, the ruler fitted to the notes, the band's
three shapes, the marks, the hints, the spells and the time-unknown band; a
span of the day; the running list. The pages: the day's JSON, placing and
taking off, To check, the exports with their audit rows, the Notes tab's
toggle and the Notes page's panel.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest
from core import case_chronology, settings_store
from core.audit import Row
from core.cases import Case
from core.jobs import Segment, Transcript
from core.models import User
from core.notes import MomentNote
from core.recordings import Batch, MediaState, Recording
from tests.helpers import signed_in

PASSWORD = "a-long-enough-password"
DAY = dt.date(2025, 11, 6)


@pytest.fixture(autouse=True)
def switches(db):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("incidents", True)


@pytest.fixture
def owner(db):
    return User.objects.create_local_admin("chron-owner", PASSWORD)


@pytest.fixture
def a_case(owner):
    return Case.objects.create(owner=owner, name="Harbour Street stop")


def a_recording(owner, case, title, *, seconds=3600.0, video=False, stamp=None):
    return Recording.objects.create(
        batch=Batch.objects.create(user=owner),
        user=owner,
        case=case,
        title=title,
        original_filename=f"{title}.{'mp4' if video else 'm4a'}",
        media_state=MediaState.READY,
        duration_seconds=seconds,
        recording_type="Body camera" if video else "Jail call",
        stamp=stamp,
        probe={"streams": [{"codec_type": "video"}]} if video else {},
    )


def a_note(owner, recording, at, text, *, on_line=False):
    if on_line:
        transcript = getattr(
            recording, "transcript", None
        ) or Transcript.objects.create(recording=recording, language="en")
        return Segment.objects.create(
            transcript=transcript,
            start=at,
            end=at + 4,
            text="the words said",
            speaker="Speaker 1",
            speaker_label="SPEAKER_1",
            note=text,
            note_by=owner,
        )
    return MomentNote.objects.create(
        recording=recording, at=at, note=text, note_by=owner
    )


def stamp(time: str, at: float = 2.0, checked: bool = True) -> dict:
    return {"date": "11/06/2025", "time": time, "at": at, "checked": checked}


# The recording's clock ----------------------------------------------------------------


def test_the_stamp_gives_the_clock_and_wins_over_a_hand_placement(owner, a_case):
    camera = a_recording(owner, a_case, "BWC1-1", video=True, stamp=stamp("20:24:38"))
    date, start, how = case_chronology.clock_of(camera)
    assert (date, start, how) == (DAY, 20 * 3600 + 24 * 60 + 36, case_chronology.CLOCK)
    assert case_chronology.placed_words(camera) == "clock"
    with pytest.raises(ValueError):
        case_chronology.place(camera, DAY, 100.0, by=owner)


def test_a_person_places_by_hand_by_the_day_or_from_the_file(owner, a_case):
    call = a_recording(owner, a_case, "Call_20251106_0915")
    assert case_chronology.clock_of(call) == (None, None, "")
    case_chronology.place(call, DAY, 9 * 3600 + 15 * 60, by=owner)
    call.refresh_from_db()
    assert case_chronology.clock_of(call) == (DAY, 33300.0, case_chronology.HAND)
    assert case_chronology.placed_words(call).startswith("by hand, ")
    row = Row.objects.get(event="recording placed on the clock")
    assert row.details["how"] == "hand" and "time" not in row.details
    # The day alone: a date with no hour.
    case_chronology.place(call, DAY, None, by=owner)
    call.refresh_from_db()
    assert case_chronology.clock_of(call) == (DAY, None, case_chronology.DAY)
    # Taken off.
    assert case_chronology.unplace(call, by=owner)
    call.refresh_from_db()
    assert case_chronology.clock_of(call) == (None, None, "")
    assert Row.objects.filter(event="recording taken off the clock").count() == 1
    assert not case_chronology.unplace(call, by=owner)


# The day's reading --------------------------------------------------------------------


def _three_cameras(owner, a_case):
    one = a_recording(owner, a_case, "BWC1-1", video=True, stamp=stamp("20:24:36"))
    two = a_recording(owner, a_case, "BWC2-1", video=True, stamp=stamp("20:25:02"))
    three = a_recording(
        owner, a_case, "BWC3-1", video=True, stamp=stamp("20:40:00", checked=False)
    )
    a_note(owner, one, 0.0, "First contact.", on_line=True)
    a_note(owner, two, 68.0, "Passenger side: the bag.")
    a_note(owner, one, 250.0, "Consent asked.", on_line=True)
    a_note(owner, three, 2400.0, "Third officer; check the time.")
    return one, two, three


def test_the_days_the_rail_and_the_day_in_lanes(owner, a_case):
    one, two, three = _three_cameras(owner, a_case)
    call = a_recording(owner, a_case, "Call_20251107_0915")
    a_note(owner, call, 30.0, "He says he was never there.")
    quiet = a_recording(owner, a_case, "Call_20251108_1133")  # no note: not on the rail
    assert quiet.pk
    days = case_chronology.days_of(a_case)
    assert [(d["date"], d["notes"], d["recordings"]) for d in days] == [
        ("2025-11-06", 4, 3)
    ]
    day = case_chronology.day_of(a_case, DAY)
    assert day["shape"] == "lanes" and len(day["bars"]) == 3
    assert [b["lane"] for b in day["bars"]] == [0, 1, 2]
    assert day["rail"] == [
        {
            "id": str(call.pk),
            "title": "Call_20251107_0915",
            "notes": 1,
            "file": None,
            "video": False,
        }
    ]
    # The ruler fits the notes: from the first note to the last, padded.
    first = 20 * 3600 + 24 * 60 + 34
    assert (
        day["ruler"]["from"] <= first
        and day["ruler"]["to"] >= 20 * 3600 + 40 * 60 - 2 + 2400
    )
    times = [row["time"] for group in day["spells"] for row in group["entries"]]
    assert times == ["20:24:34", "20:26:08", "20:28:44", "21:19:58"]
    # Two spells: a gap of ten minutes or more parts them.
    assert [group["notes"] for group in day["spells"]] == [3, 1]
    assert day["fold"] is False and day["count"] == 4 and day["recordings"] == 3
    # The entries carry the recording, the line, the writer and the colour.
    entry = day["spells"][0]["entries"][0]
    assert entry["title"] == "BWC1-1" and entry["said"] == "the words said"
    assert entry["who"] == "Speaker 1" and entry["by"] == owner.shown_name
    assert entry["colour"] == day["bars"][0]["colour"]
    # Marks, one per entry; a hint where the three overlap with marks under them.
    assert len(day["marks"]) == 4
    assert day["hints"][0]["cameras"] == 3 and day["hints"][0]["notes"] == 4
    assert day["hints"][0]["words"].startswith("3 cameras, 4 notes, 20:24 to ")
    assert day["bars"][2]["placed"] == "clock, unchecked"


def test_a_span_of_the_day_narrows_everything(owner, a_case):
    _three_cameras(owner, a_case)
    span = (20 * 3600 + 24 * 60, 20 * 3600 + 34 * 60)
    day = case_chronology.day_of(a_case, DAY, span)
    assert day["span"] is True and day["ruler"] == {"from": span[0], "to": span[1]}
    assert day["count"] == 3 and len(day["bars"]) == 2
    assert all(span[0] <= m["seconds"] <= span[1] for m in day["marks"])


def test_the_day_alone_sits_in_the_time_unknown_band(owner, a_case):
    _three_cameras(owner, a_case)
    call = a_recording(owner, a_case, "Call_20251106_2140")
    a_note(owner, call, 192.0, "He says he was never at the stop.")
    case_chronology.place(call, DAY, None, by=owner)
    day = case_chronology.day_of(a_case, DAY)
    assert day["rail"] == []
    assert [row["text"] for row in day["unknown"]] == [
        "He says he was never at the stop."
    ]
    assert day["unknown"][0]["time"] == "" and day["unknown"][0]["how"] == "day"
    assert day["unknown"][0]["number"] == 5


def test_packed_lanes_for_many_calls_spread_over_the_day(owner, a_case):
    for n in range(12):
        call = a_recording(owner, a_case, f"Call_{n:02d}", seconds=600.0)
        a_note(owner, call, 10.0, f"note {n}")
        case_chronology.place(call, DAY, 7 * 3600 + n * 1800, by=owner)
    day = case_chronology.day_of(a_case, DAY)
    # Twelve calls, none overlapping: one lane, nothing folded.
    assert day["shape"] == "packed"
    assert {b["lane"] for b in day["bars"]} == {0} and day["folded"] == []
    assert day["coverage"] == []


def test_the_coverage_lane_when_many_overlap(owner, a_case, monkeypatch):
    monkeypatch.setattr(case_chronology, "FOLD_NOTES", 1000)
    for n in range(12):
        camera = a_recording(
            owner,
            a_case,
            f"BWC{n:02d}",
            video=True,
            seconds=3600.0,
            stamp=stamp("20:00:00"),
        )
        for k in range(n % 4 + 1):
            a_note(owner, camera, 60.0 * (k + 1), f"note {n}.{k}")
    day = case_chronology.day_of(a_case, DAY)
    assert day["shape"] == "coverage"
    assert len(day["coverage"]) == case_chronology.COVERAGE_SAMPLES + 1
    assert max(day["coverage"]) == 12
    with_bar = [b for b in day["bars"] if b["lane"] is not None]
    assert len(with_bar) == case_chronology.BARS_MOST
    # The eight most noted have the bars; the four with one note fold.
    assert min(b["notes"] for b in with_bar) >= max(b["notes"] for b in day["folded"])
    assert len(day["folded"]) == 4
    running = case_chronology.running_at(a_case, DAY, 20 * 3600 + 600)
    assert len(running) == 12 and running[0]["notes"] == 4


def test_a_day_of_many_notes_folds_its_spells(owner, a_case):
    camera = a_recording(owner, a_case, "BWC1-1", video=True, stamp=stamp("20:00:00"))
    for n in range(case_chronology.FOLD_NOTES + 1):
        a_note(owner, camera, 10.0 * n, f"note {n}")
    day = case_chronology.day_of(a_case, DAY)
    assert day["fold"] is True and day["count"] == case_chronology.FOLD_NOTES + 1


def test_a_recording_past_midnight_is_on_both_days(owner, a_case):
    camera = a_recording(
        owner, a_case, "BWC1-1", video=True, seconds=7200.0, stamp=stamp("23:30:00")
    )
    a_note(owner, camera, 600.0, "before midnight")
    a_note(owner, camera, 3600.0, "after midnight")
    days = case_chronology.days_of(a_case)
    assert [(d["date"], d["notes"]) for d in days] == [
        ("2025-11-06", 1),
        ("2025-11-07", 1),
    ]
    after = case_chronology.day_of(a_case, DAY + dt.timedelta(days=1))
    assert after["spells"][0]["entries"][0]["time"] == "00:29:58"
    assert after["bars"][0]["from"] == 0.0


# The pages ----------------------------------------------------------------------------


def test_the_days_json_places_and_takes_off_and_to_check(owner, a_case, client):
    one, _two, _three = _three_cameras(owner, a_case)
    call = a_recording(owner, a_case, "Call_20251107_0915")
    a_note(owner, call, 30.0, "He says he was never there.")
    signed_in(client, owner)
    told = json.loads(client.get(f"/case/{a_case.pk}/chronology.json").content)
    assert told["days"][0]["date"] == "2025-11-06" and told["day"]["count"] == 4
    assert told["bars_most"] == 8 and told["fold_notes"] == 40
    # A span through the address.
    told = json.loads(
        client.get(
            f"/case/{a_case.pk}/chronology.json?day=2025-11-06&from=20:24&to=20:30"
        ).content
    )
    assert told["day"]["span"] is True and told["day"]["count"] == 3
    # Placed by hand from the page; then by the day; then taken off.
    answer = client.post(
        f"/recording/{call.pk}/clock",
        json.dumps({"date": "2025-11-07", "start": "09:15"}),
        content_type="application/json",
    )
    assert answer.status_code == 200 and answer.json()["placed"].startswith("by hand")
    told = json.loads(
        client.get(f"/case/{a_case.pk}/chronology.json?day=2025-11-07").content
    )
    assert told["day"]["spells"][0]["entries"][0]["time"] == "09:15:30"
    answer = client.post(
        f"/recording/{call.pk}/clock",
        json.dumps({"date": "2025-11-07", "day_alone": True}),
        content_type="application/json",
    )
    assert answer.status_code == 200
    told = json.loads(
        client.get(f"/case/{a_case.pk}/chronology.json?day=2025-11-07").content
    )
    assert told["day"]["unknown"][0]["how"] == "day"
    answer = client.post(
        f"/recording/{call.pk}/clock",
        json.dumps({"date": "x"}),
        content_type="application/json",
    )
    assert answer.status_code == 400
    assert client.post(f"/recording/{call.pk}/clock/off").json() == {"ok": True}
    # The stamp stands: a camera cannot be placed by hand.
    answer = client.post(
        f"/recording/{one.pk}/clock",
        json.dumps({"date": "2025-11-06", "start": "10:00"}),
        content_type="application/json",
    )
    assert answer.status_code == 400
    # To check on a line's note, on and off, audited.
    line = one.transcript.segments.order_by("start").first()
    answer = client.post(
        f"/recording/{one.pk}/note/to-check",
        json.dumps({"kind": "line", "id": line.pk, "wanted": True}),
        content_type="application/json",
    )
    assert answer.json() == {"ok": True, "to_check": True}
    line.refresh_from_db()
    assert line.note_to_check
    told = json.loads(client.get(f"/case/{a_case.pk}/chronology.json").content)
    assert told["day"]["spells"][0]["entries"][0]["to_check"] is True
    assert Row.objects.filter(event="note marked to check").count() == 1
    # The running list.
    told = json.loads(
        client.get(
            f"/case/{a_case.pk}/chronology/running?day=2025-11-06&at=20:30"
        ).content
    )
    assert [row["title"] for row in told["rows"]][:2] == ["BWC1-1", "BWC2-1"]


def test_the_exports_and_their_audit_rows(owner, a_case, client):
    _three_cameras(owner, a_case)
    signed_in(client, owner)
    sheet = client.get(f"/case/{a_case.pk}/chronology.csv?day=2025-11-06")
    assert sheet.status_code == 200 and sheet["Content-Type"].startswith("text/csv")
    body = sheet.content.decode("utf-8-sig")
    assert body.splitlines()[0].startswith("Date,Time of day,Recording,Placed,Note")
    assert "2025-11-06,20:24:34,BWC1-1,clock,First contact." in body
    word = client.get(f"/case/{a_case.pk}/chronology.docx")
    assert word.status_code == 200 and word.content[:2] == b"PK"
    assert (
        "Chronology%20-%20Harbour%20Street%20stop.docx" in (word["Content-Disposition"])
    )
    rows = Row.objects.filter(event="chronology exported").order_by("at")
    assert [(r.details["kind"], r.details["scope"]) for r in rows] == [
        ("csv", "one day"),
        ("docx", "every day"),
    ]
    assert not any("First contact" in json.dumps(r.details) for r in rows)


def test_the_notes_tab_and_the_notes_page_carry_the_chronology(owner, a_case, client):
    one, _two, _three = _three_cameras(owner, a_case)
    signed_in(client, owner)
    page = client.get(f"/case/{a_case.pk}?tab=notes").content.decode()
    assert 'id="notes-shape"' in page and 'data-shape="chronology"' in page
    assert 'id="case-chronology"' in page and "chronology.js" in page
    notes_page = client.get(f"/case/{a_case.pk}/notes-page").content.decode()
    assert (
        'data-panel="chronology"' in notes_page
        and 'id="panel-chronology"' in notes_page
    )
    assert 'data-player="notes-page"' in notes_page
    # A case with no note has no toggle and no chronology container.
    empty = Case.objects.create(owner=owner, name="Empty")
    page = client.get(f"/case/{empty.pk}?tab=notes").content.decode()
    assert 'id="notes-shape"' not in page and 'id="case-chronology"' not in page


def test_the_rail_shows_before_any_day_exists_and_the_first_placing_makes_one(
    owner, a_case, client
):
    """v1.170.1: a case whose only note is on a recording with no clock has
    no day; the day address still returns the rail, so the first placing
    can happen from the page, and the placing makes the day."""
    call = a_recording(owner, a_case, "Call_20251107_0915")
    a_note(owner, call, 30.0, "He says he was never there.")
    quiet = a_recording(owner, a_case, "Call_20251108_1133")
    assert quiet.pk
    signed_in(client, owner)
    told = client.get(f"/case/{a_case.pk}/chronology.json").json()
    assert told["days"] == [] and told["day"] is None
    assert [one["title"] for one in told["rail"]] == ["Call_20251107_0915"]
    assert told["rail"][0]["notes"] == 1 and told["rail_more"] == 0
    assert told["rail_all"] == told["rail"]
    # Placed by hand, the day exists and the note is on it.
    case_chronology.place(call, DAY, 9 * 3600 + 15 * 60.0, by=owner, how="hand")
    told = client.get(f"/case/{a_case.pk}/chronology.json").json()
    assert [d["date"] for d in told["days"]] == [DAY.isoformat()]
    assert told["day"]["count"] == 1 and told["rail"] == []
    assert told["day"]["spells"][0]["entries"][0]["time"] == "09:15:30"
