"""v1.59.0: the Chronology (Phase 6, chapter 2).

The rules checked here: an Event is added at a moment with the running
cameras ticked, from a line with its words and camera, and refused without
a time or a text; Edit changes it and Remove takes it away, each with its
audit row and none with a word; the state carries the events with their
source words; an Event whose camera left the incident says so; the three
exports come back in their shapes and write their row; the page opens with
a citation's words ready; and the words are in the glossary and the guide.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from core import chronology, incidents, settings_store
from core.audit import Row
from core.cases import Case
from core.chronology import Event
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording

APP = Path(__file__).resolve().parent.parent
ROOT = APP.parent
PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"


@pytest.fixture(autouse=True)
def incidents_on(db):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("incidents", True)


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("asker", PASSWORD)


@pytest.fixture
def a_case(person):
    return Case.objects.create(owner=person, name="Traffic stop")


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def stamp(time: str, camera: str):
    return {
        "date": "06/07/2025",
        "time": time,
        "camera": camera,
        "at": 2.0,
        "checked": True,
    }


def video(person, case, title, *, seconds=600.0, stamp=None):
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        case=case,
        title=title,
        original_filename=f"{title}.mp4",
        media_state=MediaState.READY,
        duration_seconds=seconds,
        playback_ready=True,
        stamp=stamp,
        probe={},
    )
    recording.folder.mkdir(parents=True, exist_ok=True)
    (recording.folder / "playback.mp4").write_bytes(b"not really media")
    return recording


@pytest.fixture
def incident(person, a_case):
    first = video(person, a_case, "first", stamp=stamp("21:56:19", "BWC2-1"))
    second = video(person, a_case, "second", stamp=stamp("22:01:00", "BWC2-2"))
    return incidents.make(a_case, "Stop", [first, second], by=person)


def test_an_event_is_added_at_a_moment_with_the_running_cameras(person, incident):
    cameras = {one.camera_id(): one for one in incident.cameras.all()}
    # At 30 s only the first camera runs; at 400 s both do.
    event = chronology.add(
        incident, {"at": "30", "text": "  Vehicle  stopped "}, by=person
    )
    assert event.text == "Vehicle stopped" and event.source == "person"
    assert event.cameras == [str(cameras["BWC2-1"].pk)]
    later = chronology.add(
        incident, {"at": "400", "until": "410", "text": "Pat-down"}, by=person
    )
    assert set(later.cameras) == {str(one.pk) for one in cameras.values()}
    assert later.until == 410.0
    # From a line: the words, the camera, and only that camera at first.
    quoted = chronology.add(
        incident,
        {
            "at": "105",
            "text": "Step out of the vehicle for me.",
            "source": "words",
            "camera": str(cameras["BWC2-1"].pk),
            "cameras": [str(cameras["BWC2-1"].pk)],
        },
        by=person,
    )
    assert quoted.source == "words" and quoted.camera == cameras["BWC2-1"]
    rows = chronology.events_json(incident)
    assert [one["text"] for one in rows] == [
        "Vehicle stopped",
        "Step out of the vehicle for me.",
        "Pat-down",
    ]
    assert (
        rows[1]["source_words"] == "Words, BWC2-1"
        and rows[0]["source_words"] == "Added by asker"
    )
    assert rows[2]["seen_on"] == "BWC2-1, BWC2-2"
    # Refused without a time or a text; an end before the start is dropped.
    with pytest.raises(ValueError):
        chronology.add(incident, {"at": "", "text": "x"}, by=person)
    with pytest.raises(ValueError):
        chronology.add(incident, {"at": "5", "text": "   "}, by=person)
    odd = chronology.add(
        incident, {"at": "50", "until": "40", "text": "odd"}, by=person
    )
    assert odd.until is None


def test_an_event_changes_and_goes_with_its_rows(person, incident):
    event = chronology.add(incident, {"at": "30", "text": "Stopped"}, by=person)
    chronology.change(
        event, {"at": "35", "text": "Vehicle stopped", "cameras": []}, by=person
    )
    event.refresh_from_db()
    assert event.at == 35.0 and event.text == "Vehicle stopped" and event.cameras == []
    assert event.changed_by == person and event.changed is not None
    chronology.remove(event, by=person)
    assert Event.objects.count() == 0
    events = list(Row.objects.filter(category="cases").values_list("event", flat=True))
    assert (
        "event added" in events
        and "event changed" in events
        and "event removed" in events
    )
    for row in Row.objects.filter(category="cases"):
        assert "Stopped" not in json.dumps(row.details)


def test_a_camera_that_left_the_incident_is_said_so(person, incident):
    camera = incident.cameras.get(recording__title="second")
    event = chronology.add(
        incident,
        {
            "at": "400",
            "text": "Stay in the car",
            "source": "words",
            "camera": str(camera.pk),
            "cameras": [str(camera.pk)],
        },
        by=person,
    )
    incidents.remove_camera(camera, by=person)
    event.refresh_from_db()
    assert event.camera is None and event.text == "Stay in the car"
    rows = chronology.events_json(incident)
    assert rows[0]["source_words"] == "Words, a camera no longer in the incident"
    assert rows[0]["seen_on"] == ""
    # Deleting the incident takes its events.
    incidents.delete(incident, by=person)
    assert Event.objects.count() == 0


@pytest.mark.django_db
def test_the_page_and_the_act_endpoint_carry_the_events(
    person, a_case, incident, client
):
    signed_in(client, person)
    act = f"{incident.url()}/act"
    said = client.post(
        act, {"action": "event_add", "at": "30", "text": "Vehicle stopped"}
    ).json()
    assert said["ok"] and said["state"]["events"][0]["text"] == "Vehicle stopped"
    event_id = said["state"]["events"][0]["id"]
    refused = client.post(act, {"action": "event_add", "at": "30", "text": ""})
    assert refused.status_code == 400 and "text" in refused.json()["error"]
    said = client.post(
        act,
        {
            "action": "event_change",
            "event": event_id,
            "at": "40",
            "text": "Vehicle stopped on the shoulder",
            "cameras_given": "yes",
        },
    ).json()
    assert said["state"]["events"][0]["at"] == 40.0
    assert said["state"]["events"][0]["cameras"] == []
    page = client.get(incident.url() + "?t=40&event=Step%20out").content.decode()
    assert "Add event here" in page and "Chronology" in page and "Step out" in page
    said = client.post(act, {"action": "event_remove", "event": event_id}).json()
    assert said["state"]["events"] == []


@pytest.mark.django_db
def test_the_three_exports_come_back_in_their_shapes(person, a_case, incident, client):
    signed_in(client, person)
    chronology.add(incident, {"at": "30", "text": "Vehicle stopped"}, by=person)
    chronology.add(
        incident, {"at": "400", "until": "410", "text": "Pat-down"}, by=person
    )
    base = f"{incident.url()}/export"

    sheet = client.get(f"{base}/csv")
    assert sheet.status_code == 200 and sheet["Content-Type"].startswith("text/csv")
    text = sheet.content.decode("utf-8-sig")
    assert text.splitlines()[0].startswith("Number,Time,Seconds into the incident")
    assert "1,21:56:47,30.0,,Vehicle stopped,,Added by asker" in text
    assert "2,22:02:57,400.0,22:03:07,Pat-down" in text

    # The Word document is a plain link (Phase 8 chapter 12): the chronology
    # figure is drawn by the server, so the page posts nothing.
    word = client.get(f"{base}/word")
    assert word.status_code == 200
    assert word["Content-Disposition"].endswith('filename="Chronology - Stop.docx"')
    from docx import Document

    document = Document(io.BytesIO(word.content))
    words = "\n".join(one.text for one in document.paragraphs)
    cells = "\n".join(
        cell.text
        for table in document.tables
        for row in table.rows
        for cell in row.cells
    )
    assert "Chronology: Stop" in words
    # The figure: the band's legend, a spell heading, the entries by number.
    assert "Each bar is one camera's recording on the clock." in words
    assert "21:56:47 to 22:02:57" in words and "2 events" in words
    assert "Vehicle stopped" in cells and "to 22:03:07" in cells
    assert "From its clock, checked" in cells and chronology.QUOTE_LEGEND in words
    assert len(document.inline_shapes) == 1  # the band, nothing else drawn
    # The strip picture is gone.
    assert client.get(f"{base}/picture").status_code == 404
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
    assert (
        client.post(f"{base}/picture", {"picture": io.BytesIO(png)}).status_code == 404
    )
    assert client.get(f"{base}/pdf").status_code == 404

    kinds = list(
        Row.objects.filter(event="chronology exported").values_list(
            "details__kind", flat=True
        )
    )
    assert sorted(kinds) == ["csv", "word"]
    for row in Row.objects.filter(event="chronology exported"):
        assert "Vehicle" not in json.dumps(row.details)


def test_spells_split_at_ten_minutes():
    """Phase 8 chapter 12: a spell is a run of events with no gap of ten
    minutes or more between neighbours; one event alone is a spell headed by
    its time."""
    rows = [
        {"seconds": 0.0, "time": "21:56:17"},
        {"seconds": 300.0, "time": "22:01:17"},
        {"seconds": 899.0, "time": "22:11:16"},
        {"seconds": 1499.0, "time": "22:21:16"},
        {"seconds": 5000.0, "time": "23:19:37"},
    ]
    groups = chronology.spells(rows)
    assert [len(one) for one in groups] == [3, 1, 1]
    assert chronology.spell_words(groups[0]) == "21:56:17 to 22:11:16"
    assert chronology.spell_words(groups[1]) == "22:21:16"
    assert chronology.spells([]) == []
    assert chronology.SPELL_GAP == 600


@pytest.mark.django_db
def test_the_rows_carry_the_spell_and_the_cameras_colour(person, a_case, incident):
    first, second = incident.cameras.order_by("starts_at")
    chronology.add(
        incident,
        {"at": "30", "text": "Vehicle stopped", "camera": str(second.pk)},
        by=person,
    )
    chronology.add(incident, {"at": "45", "text": "Step out"}, by=person)
    chronology.add(incident, {"at": "2000", "text": "Tow truck"}, by=person)
    rows = chronology._rows(incident)
    colours = chronology.camera_colours(incident)
    assert colours[str(first.pk)] == "#1f6fb2" and colours[str(second.pk)] == "#c2410c"
    assert rows[0]["colour"] == "#c2410c"
    # A person's event with no camera takes the first of its seen-on cameras.
    assert rows[1]["colour"] in ("#1f6fb2", "#c2410c", "")
    assert rows[0]["spell"] == rows[1]["spell"] == "21:56:47 to 21:57:02"
    assert rows[2]["spell"] == "22:29:37"
    sheet = chronology.spreadsheet(incident).decode("utf-8-sig")
    assert sheet.splitlines()[0].endswith("Why it matters,Spell")
    assert sheet.splitlines()[1].endswith(",21:56:47 to 21:57:02")


def test_the_page_carries_the_timeline_and_the_focus_rule():
    script = (APP / "static" / "incident.js").read_text(encoding="utf-8")
    for wanted in (
        "function showCameraOf",
        "function drawTimeline",
        "var SPELL_GAP = 600",
        "inc-chronology-view",
        "data-view='timeline'",
        "seek: function (at, ev) { seek(at); if (ev) { showCameraOf(ev); } }",
    ):
        assert wanted in script, wanted
    assert "drawPicture" not in script and "exportPicture" not in script
    card = (APP / "static" / "event-card.js").read_text(encoding="utf-8")
    assert "given.seek(ev.at, ev)" in card
    css = (APP / "static" / "app.css").read_text(encoding="utf-8")
    for wanted in (".inc-timeline {", ".tl-spell {", ".view-toggle {", ".tl-num {"):
        assert wanted in css, wanted
    page = (APP / "templates" / "incident.html").read_text(encoding="utf-8")
    assert 'id="export-picture"' not in page
    assert '<a id="export-word" href=' in page


def test_the_words_are_in_the_glossary_and_the_guide():
    glossary = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    assert "**Chronology**" in glossary and "**Event**" in glossary
    assert "Phase 6 chapter 2, proposed" not in glossary
    guide = (ROOT / "docs" / "user-guide.md").read_text(encoding="utf-8")
    assert "**The chronology.**" in guide and "Add event here" in guide


# The line and the detail (Phase 8 chapter 8) ---------------------------------------


def test_an_events_text_keeps_its_line_breaks_and_reads_as_line_and_detail(
    person, incident
):
    event = chronology.add(
        incident,
        {
            "at": "30",
            "text": (
                "Vehicle stopped.\n\n  The  driver  was told to wait. \n"
                "A second unit arrived."
            ),
        },
        by=person,
    )
    assert event.text == (
        "Vehicle stopped.\nThe driver was told to wait.\nA second unit arrived."
    )
    row = chronology.events_json(incident)[0]
    assert row["line"] == "Vehicle stopped."
    assert row["detail"] == "The driver was told to wait. A second unit arrived."
    sheet = chronology.spreadsheet(incident).decode("utf-8-sig")
    head, first = sheet.splitlines()[:2]
    assert head.split(",")[4:6] == ["Event", "Detail"]
    assert (
        "Vehicle stopped.,The driver was told to wait. A second unit arrived.," in first
    )
    # A long description accepted as it came reads as a line and the rest.
    long = chronology.add(
        incident,
        {
            "at": "40",
            "text": (
                "The camera view shifts to the interior of a moving vehicle at "
                "night. A hand rests on the steering wheel and the dashboard "
                "lights are on while the officer speaks to dispatch."
            ),
        },
        by=person,
    )
    assert long.text.count("\n") == 0
    rows = {one["at"]: one for one in chronology.events_json(incident)}
    assert rows[40.0]["line"] == (
        "The camera view shifts to the interior of a moving vehicle at night."
    )
    assert rows[40.0]["detail"].startswith("A hand rests on the steering wheel")
