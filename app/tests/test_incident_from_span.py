"""An incident from a span of the case's chronology (Phase 10 chapter 2,
v1.167.0), and the three guards against making one twice.

The day's reading carries the case's incidents as spans and says of each
entry whether it is an event of one or sits inside one on a camera not in
it; the span reading ticks the most noted recordings and finds the incidents
the span touches; Make carries every camera's place over; Add widens the
incident and writes its row.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest
from core import case_chronology, incidents, settings_store
from core.audit import Row
from core.cases import Case
from core.chronology import Event
from core.jobs import Segment, Transcript
from core.models import User
from core.notes import MomentNote
from core.recordings import Batch, MediaState, Recording
from django.urls import reverse
from tests.helpers import signed_in

PASSWORD = "a-long-enough-password"
DAY = dt.date(2025, 11, 6)


@pytest.fixture(autouse=True)
def switches(db):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("incidents", True)


@pytest.fixture
def owner(db):
    return User.objects.create_local_admin("span-owner", PASSWORD)


@pytest.fixture
def a_case(owner):
    return Case.objects.create(owner=owner, name="Harbour Street stop")


def stamp(time: str, camera: str = "BWC1-1") -> dict:
    return {
        "date": "11/06/2025",
        "time": time,
        "camera": camera,
        "at": 2.0,
        "checked": True,
    }


def a_video(owner, case, title, *, seconds=1800.0, stamp=None):
    return Recording.objects.create(
        batch=Batch.objects.create(user=owner),
        user=owner,
        case=case,
        title=title,
        original_filename=f"{title}.mp4",
        media_state=MediaState.READY,
        duration_seconds=seconds,
        recording_type="Body camera",
        stamp=stamp,
        probe={"streams": [{"codec_type": "video"}]},
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


def seconds(text: str) -> float:
    hours, minutes = text.split(":")
    return float(int(hours) * 3600 + int(minutes) * 60)


@pytest.fixture
def a_day(owner, a_case):
    """Three cameras on the day: two by their stamps from 20:24 and 20:26, one
    placed by hand at 20:34; a note on each; a fourth video later with a note,
    unrelated."""
    first = a_video(owner, a_case, "BWC1-1", stamp=stamp("20:24:00"))
    second = a_video(owner, a_case, "BWC2-1", stamp=stamp("20:26:00", "BWC2-1"))
    third = a_video(owner, a_case, "BWC3-1")
    case_chronology.place(third, date=DAY, start=seconds("20:34"), how="hand", by=owner)
    later = a_video(owner, a_case, "Dash-4", stamp=stamp("21:40:00", "Dash-4"))
    a_note(owner, first, 36.0, "First contact.", on_line=True)
    a_note(owner, first, 284.0, "Consent asked.", on_line=True)
    a_note(owner, second, 10.0, "The bag on the floor.")
    a_note(owner, third, 60.0, "Third officer arrives.", on_line=True)
    a_note(owner, later, 30.0, "Second car pulls in.")
    return first, second, third, later


def test_the_day_reads_without_incidents_and_the_span_ticks_the_noted(
    owner, a_case, a_day
):
    reading = case_chronology.day_of(a_case, DAY)
    assert reading["incidents"] == [] and reading["incidents_on"] is True
    assert all(
        "incident" not in row and "outside" not in row for row in _entries(reading)
    )
    span = (seconds("20:24"), seconds("20:40"))
    told = case_chronology.span_reading(a_case, DAY, span)
    assert told["incidents"] == []
    assert [row["title"] for row in told["rows"]] == ["BWC1-1", "BWC2-1", "BWC3-1"]
    assert [row["ticked"] for row in told["rows"]] == [True, True, True]
    assert told["rows"][0]["notes"] == 2 and told["rows"][2]["placed"].startswith(
        "by hand"
    )
    assert told["rows"][2]["from"] == "20:34" and told["rows"][2]["to"] == "20:40"
    assert told["name"] == "6 Nov 2025, 20:24 to 20:40"
    assert told["most"] == incidents.most_cameras()


def _entries(reading) -> list[dict]:
    return [row for group in reading["spells"] for row in group["entries"]]


def test_make_carries_every_place_over_and_says_where_it_came_from(
    owner, a_case, a_day, client
):
    first, second, third, later = a_day
    signed_in(client, owner)
    answer = client.post(
        reverse("case-chronology-incident", args=[a_case.pk]),
        json.dumps(
            {
                "day": DAY.isoformat(),
                "from": "20:24",
                "to": "20:40",
                "name": "Traffic stop, 6 Nov",
                "recordings": [str(first.pk), str(second.pk), str(third.pk)],
            }
        ),
        content_type="application/json",
    )
    assert answer.status_code == 200, answer.content
    incident = incidents.Incident.objects.get(case=a_case)
    assert answer.json()["url"] == incident.url()
    assert incident.name == "Traffic stop, 6 Nov" and incident.how == "chronology"
    cameras = {
        one.recording.title: one for one in incident.cameras.select_related("recording")
    }
    assert (
        cameras["BWC1-1"].placed == incidents.CLOCK
        and cameras["BWC1-1"].starts_at == 0.0
    )
    # The stamp's second is where its reading was taken, two seconds in.
    assert incident.clock_zero == seconds("20:24") - 2.0
    assert cameras["BWC2-1"].placed == incidents.CLOCK
    assert cameras["BWC2-1"].starts_at == pytest.approx(120.0)
    # The hand placement arrives Synced by hand at the same start, the same name.
    by_hand = cameras["BWC3-1"]
    assert by_hand.placed == incidents.HAND and by_hand.placed_by == owner
    assert by_hand.starts_at == pytest.approx(seconds("20:34") - incident.clock_zero)
    assert incident.from_chronology["made"] == {
        "date": "2025-11-06",
        "from": "20:24",
        "to": "20:40",
    }
    assert incident.from_chronology["span"] == incident.from_chronology["made"]
    # The notes on the cameras are its events (Phase 8 chapter 11).
    assert Event.objects.filter(incident=incident, proposed=False).count() == 4
    row = Row.objects.get(event="incident made")
    assert (
        row.details["how"] == "chronology" and row.details["span"] == "20:24 to 20:40"
    )
    assert row.details["day"] == "2025-11-06" and "note" not in json.dumps(row.details)
    # The incident's Details carry the line and the link back.
    page = client.get(reverse("incident-state", args=[a_case.pk, incident.pk])).json()
    told = page["incident"]["from_chronology"]
    assert told["made"] == "6 Nov 2025, 20:24 to 20:40" and told["changes"] == []
    assert "shape=chronology&day=2025-11-06&from=20:24&to=20:40" in told["url"]


def test_the_lane_the_pills_and_the_outside_line_then_add_widens(
    owner, a_case, a_day, client
):
    first, second, third, later = a_day
    incident = case_chronology.make_incident(
        a_case,
        DAY,
        (seconds("20:24"), seconds("20:40")),
        "Traffic stop",
        [first, second],
        by=owner,
    )
    # A note written later on a camera outside the incident, inside its span.
    a_note(owner, third, 120.0, "Seen from the third camera.")
    reading = case_chronology.day_of(a_case, DAY)
    lane = reading["incidents"]
    assert (
        len(lane) == 1 and lane[0]["name"] == "Traffic stop" and lane[0]["cameras"] == 2
    )
    assert (
        lane[0]["from"] == seconds("20:24") - 2.0
        and lane[0]["to"] == seconds("20:56") - 2.0
    )
    assert lane[0]["events"] == 3 and lane[0]["url"] == incident.url()
    rows = {row["text"]: row for row in _entries(reading)}
    assert rows["First contact."]["incident"]["name"] == "Traffic stop"
    assert rows["The bag on the floor."]["incident"]["id"] == str(incident.pk)
    outside = rows["Seen from the third camera."]["outside"]
    assert outside["name"] == "Traffic stop" and outside["from"] == "20:23"
    assert "incident" not in rows["Seen from the third camera."]
    # Dash-4 at 21:40 is after the incident: neither.
    assert (
        "incident" not in rows["Second car pulls in."]
        and "outside" not in rows["Second car pulls in."]
    )
    # A span running past the incident: Add first, the union said.
    told = case_chronology.span_reading(
        a_case, DAY, (seconds("20:50"), seconds("22:00"))
    )
    touched = told["incidents"]
    assert (
        len(touched) == 1
        and touched[0]["inside"] is False
        and touched[0]["widens"] is True
    )
    assert touched[0]["union_from"] == "20:23" and touched[0]["union_to"] == "22:00"
    assert set(touched[0]["in_ids"]) == {str(first.pk), str(second.pk)}
    assert set(touched[0]["camera_ids"]) == {str(first.pk), str(second.pk)}
    assert [row["title"] for row in told["rows"]][0] == "Dash-4"
    # Add Dash-4 and widen.
    signed_in(client, owner)
    answer = client.post(
        reverse("incident-add-from-chronology", args=[a_case.pk, incident.pk]),
        json.dumps(
            {
                "day": DAY.isoformat(),
                "from": "20:50",
                "to": "22:00",
                "recordings": [str(later.pk)],
            }
        ),
        content_type="application/json",
    )
    assert answer.status_code == 200, answer.content
    assert answer.json()["added"] == 1
    incident.refresh_from_db()
    assert incident.cameras.count() == 3
    assert incident.from_chronology["span"] == {
        "date": "2025-11-06",
        "from": "20:24",
        "to": "22:00",
    }
    change = incident.from_chronology["changes"][0]
    assert (
        change["added"] == 1
        and change["widened"] is True
        and change["span"] == "20:24 to 22:00"
    )
    row = Row.objects.get(event="incident widened from the chronology")
    assert (
        row.details["was"] == "20:24 to 20:40"
        and row.details["now"] == "20:24 to 22:00"
    )
    assert row.details["cameras"] == 1
    # The outside line's Add: inside the span, nothing widens.
    answer = client.post(
        reverse("incident-add-from-chronology", args=[a_case.pk, incident.pk]),
        json.dumps(
            {
                "day": DAY.isoformat(),
                "from": "20:24",
                "to": "22:00",
                "recordings": [str(third.pk)],
            }
        ),
        content_type="application/json",
    )
    assert answer.status_code == 200
    incident.refresh_from_db()
    assert incident.cameras.count() == 4
    assert incident.from_chronology["changes"][1]["widened"] is False
    # Its note is an event now, and the entry says so.
    reading = case_chronology.day_of(a_case, DAY)
    rows = {row["text"]: row for row in _entries(reading)}
    assert rows["Seen from the third camera."]["incident"]["name"] == "Traffic stop"
    assert "outside" not in rows["Seen from the third camera."]
    assert reading["incidents"][0]["cameras"] == 4
    # The Details list the changes.
    page = client.get(reverse("incident-state", args=[a_case.pk, incident.pk])).json()
    words = [one["words"] for one in page["incident"]["from_chronology"]["changes"]]
    assert words[0].startswith("widened to 20:24 to 22:00, 1 camera, by ")
    assert words[1].startswith("added to, 1 camera, by ")


def test_the_addresses_refuse_without_a_span_or_the_switch(
    owner, a_case, a_day, client
):
    signed_in(client, owner)
    assert (
        client.get(reverse("case-chronology-span", args=[a_case.pk])).status_code == 404
    )
    bad = client.post(
        reverse("case-chronology-incident", args=[a_case.pk]),
        json.dumps(
            {"day": DAY.isoformat(), "from": "20:24", "to": "20:40", "recordings": []}
        ),
        content_type="application/json",
    )
    assert bad.status_code == 400 and "Tick" in bad.json()["error"]
    settings_store.set_to("incidents", False)
    assert (
        client.get(
            reverse("case-chronology-span", args=[a_case.pk])
            + "?day=2025-11-06&from=20:24&to=20:40"
        ).status_code
        == 404
    )
    settings_store.set_to("incidents", True)
    reading = client.get(
        reverse("case-chronology", args=[a_case.pk]) + "?day=2025-11-06"
    ).json()
    assert reading["day"]["incidents_on"] is True and reading["day"]["incidents"] == []


def test_the_page_draws_the_lane_the_sheets_and_the_line():
    from pathlib import Path

    here = Path(__file__).resolve().parents[1]
    script = (here / "static" / "chronology.js").read_text(encoding="utf-8")
    for piece in (
        "function incidentsLane(d)",
        "html += incidentsLane(d);",
        "data-act='make-span'",
        'data-make=\'" + h.from + "," + h.to + "\'',
        "function makeSheet(from, to)",
        "function pickerSheet(told)",
        "function addFirstSheet(told)",
        "Make a new one anyway",
        "function addOutside(e)",
        "data-act='add-outside'",
        'an event of " + esc(e.incident.name)',
        "/chronology/sitting?recordings=",
        "/add-from-chronology",
    ):
        assert piece in script, piece
    css = (here / "static" / "app.css").read_text(encoding="utf-8")
    for rule in (
        ".chron .inc-lane {",
        ".chron .inc-lane .br {",
        ".chron .hint .mk {",
        ".chron .entry .outside {",
        ".chron .sheet .notice {",
        ".chron .sheet .sit.nearly i {",
    ):
        assert rule in css, rule
    incident_js = (here / "static" / "incident.js").read_text(encoding="utf-8")
    assert "from the case's chronology" in incident_js and "F.changes" in incident_js
    spec = (here.parent / "docs" / "spec" / "SPEC-PHASE-10.md").read_text(
        encoding="utf-8"
    )
    assert "phase-10-incident-from-span.html" in spec
    assert "Incident widened from the chronology" in spec
    glossary = (here.parent / "CONTEXT.md").read_text(encoding="utf-8")
    assert "**Incidents lane**:" in glossary
