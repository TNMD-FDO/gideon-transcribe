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
    assert "1,21:56:47,30.0,,Vehicle stopped,Added by asker" in text
    assert "2,22:02:57,400.0,22:03:07,Pat-down" in text

    # The Word document takes the picture the page drew.
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
    word = client.post(f"{base}/word", {"picture": io.BytesIO(png)})
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
    assert "Chronology: Stop" in words and "The strip could not be drawn." in words
    assert "Vehicle stopped" in cells and "22:02:57 to 22:03:07" in cells
    assert "From its clock, checked" in cells and chronology.QUOTE_LEGEND in words
    assert client.get(f"{base}/word").status_code == 404

    picture = client.post(f"{base}/picture", {"picture": io.BytesIO(png)})
    assert picture.status_code == 200 and picture["Content-Type"] == "image/png"
    assert picture.content == png
    assert client.get(f"{base}/picture").status_code == 404
    assert client.get(f"{base}/pdf").status_code == 404

    kinds = list(
        Row.objects.filter(event="chronology exported").values_list(
            "details__kind", flat=True
        )
    )
    assert sorted(kinds) == ["csv", "picture", "word"]
    for row in Row.objects.filter(event="chronology exported"):
        assert "Vehicle" not in json.dumps(row.details)


def test_the_words_are_in_the_glossary_and_the_guide():
    glossary = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    assert "**Chronology**" in glossary and "**Event**" in glossary
    assert "Phase 6 chapter 2, proposed" not in glossary
    guide = (ROOT / "docs" / "user-guide.md").read_text(encoding="utf-8")
    assert "**The chronology.**" in guide and "Add event here" in guide
