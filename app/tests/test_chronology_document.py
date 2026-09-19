"""v1.63.0: the chronology as a document (Phase 7, chapter 1).

The rules checked here: a Note and a To check mark are saved with an Event
and come back in the state with the writer's name; About this chronology
is saved on the Incident with its row; the Word export prints About on
the cover, the note under the event and the to-check count, and the
spreadsheet gains its two columns; the memo and the proposals are told the
notes and About, and the memo's stale signature covers them; an accepted
proposal edited by a person keeps its source; and the words are in the
glossary and the guide.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from core import chronology, incident_assistant, incidents, prompts, settings_store
from core.audit import Row
from core.cases import Case
from core.chronology import Event
from core.jobs import Segment, Transcript
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
def switched_on(db):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("incidents", True)
    settings_store.set_to("assistant_available", True)


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


def video(person, case, title, *, seconds=600.0, stamp=None, lines=()):
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
    if lines:
        transcript = Transcript.objects.create(recording=recording, language="en")
        for start, speaker, text in lines:
            Segment.objects.create(
                transcript=transcript,
                start=start,
                end=start + 4,
                text=text,
                speaker=speaker,
                speaker_label=speaker.upper().replace(" ", "_"),
            )
    return recording


@pytest.fixture
def incident(person, a_case):
    first = video(
        person,
        a_case,
        "first",
        stamp=stamp("21:56:19", "BWC2-1"),
        lines=((10.0, "Officer Hale", "Step out of the vehicle for me."),),
    )
    second = video(person, a_case, "second", stamp=stamp("22:01:00", "BWC2-2"))
    return incidents.make(a_case, "Stop", [first, second], by=person)


def docx_text(body: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(body)) as bundle:
        return bundle.read("word/document.xml").decode("utf-8")


# Notes, marks and About ------------------------------------------------------------


def test_a_note_and_a_mark_are_saved_with_the_event(incident, person):
    event = chronology.add(
        incident,
        {
            "at": "10",
            "text": "Asked out of the car",
            "note": "  Check the  consent question \n\n page 4 of the report ",
            "to_check": "yes",
        },
        by=person,
    )
    assert event.note == "Check the consent question\npage 4 of the report"
    assert event.to_check is True
    rows = chronology.events_json(incident)
    assert rows[0]["note"] == event.note and rows[0]["to_check"] is True
    assert rows[0]["note_by"] == "asker"
    assert chronology.to_check_count(incident) == 1
    # The note's writer stays when somebody else edits the event's text.
    other = User.objects.create_local_admin("other", PASSWORD)
    chronology.change(
        event,
        {
            "at": "10",
            "text": "Asked out of the car, edited",
            "note": event.note,
            "to_check": "yes",
        },
        by=other,
    )
    event.refresh_from_db()
    assert event.note_by == person and event.changed_by == other
    assert chronology.events_json(incident)[0]["note_by"] == "asker"
    # Cleared by a person, never by itself; a note too long is cut.
    chronology.change(
        event,
        {
            "at": "10",
            "text": "Asked out of the car",
            "note": "x" * 2500,
            "to_check": "",
        },
        by=other,
    )
    event.refresh_from_db()
    assert len(event.note) == 2000 and event.to_check is False
    assert chronology.events_json(incident)[0]["note_by"] == "other"
    # No row holds a word of the note.
    for row in Row.objects.filter(category="cases"):
        assert "consent" not in json.dumps(row.details)


def test_about_this_chronology_is_saved_with_its_row(incident, person, client):
    incidents.set_about(
        incident, "  The stop of 7 June.\n\n  Cameras of units 12 and 14. ", by=person
    )
    incident.refresh_from_db()
    assert incident.about == "The stop of 7 June.\nCameras of units 12 and 14."
    row = Row.objects.filter(event="incident changed").order_by("-at").first()
    assert row.details.get("about") is True and "June" not in json.dumps(row.details)
    signed_in(client, person)
    url = f"/case/{incident.case_id}/incident/{incident.pk}"
    got = client.post(url + "/act", {"action": "about", "about": "Rewritten."}).json()
    assert got["ok"] and got["state"]["incident"]["about"] == "Rewritten."
    assert got["state"]["incident"]["to_check"] == 0
    page = client.get(url).content.decode()
    assert 'name="note"' in page and 'name="to_check"' in page


def test_only_accept_makes_an_event_the_assistants(incident, person):
    event = chronology.add(
        incident, {"at": "5", "text": "Typed by hand", "source": "assistant"}, by=person
    )
    assert event.source == "person"


def test_an_accepted_proposal_keeps_its_source_when_edited(incident, person):
    cams = {one.camera_id(): one for one in incident.cameras.all()}
    event = Event.objects.create(
        incident=incident,
        at=20.0,
        text="Proposed line",
        source="assistant",
        camera=cams["BWC2-1"],
        proposed=True,
        rests_on="a line",
    )
    incident_assistant.accept(event, by=person)
    chronology.change(
        event,
        {"at": "20", "text": "Proposed line, edited", "source": "person"},
        by=person,
    )
    event.refresh_from_db()
    assert event.source == "assistant" and event.text == "Proposed line, edited"


# The exports -----------------------------------------------------------------------


def test_the_exports_print_about_the_notes_and_the_marks(incident, person):
    incidents.set_about(incident, "The stop of 7 June.", by=person)
    chronology.add(
        incident,
        {
            "at": "10",
            "text": "Asked out of the car",
            "note": "Cite page 4",
            "to_check": "yes",
        },
        by=person,
    )
    chronology.add(incident, {"at": "40", "text": "Tow truck"}, by=person)
    body = chronology.word(incident, None, "asker")
    text = docx_text(body)
    assert "The stop of 7 June." in text
    assert "Note: Cite page 4" in text
    assert "1 (to check)" in text
    assert "1 event marked to check" in text
    sheet = chronology.spreadsheet(incident).decode("utf-8-sig")
    head, first, second = sheet.strip().splitlines()[:3]
    assert head.endswith("Added on,Note,To check,Why it matters")
    # A person's event has no why (v1.64.0), so the last column is empty.
    assert first.endswith("Cite page 4,yes,")
    assert second.endswith(",,,")


# The memo and the proposals are told --------------------------------------------


def test_the_memo_and_the_proposals_are_told_the_notes(incident, person):
    incidents.set_about(incident, "The stop of 7 June.", by=person)
    first = chronology.add(
        incident,
        {
            "at": "10",
            "text": "Asked out of the car",
            "note": "Cite page 4",
            "to_check": "yes",
        },
        by=person,
    )
    lines, _ = incident_assistant._chronology_lines(incident)
    assert lines[0].endswith(
        "added by a person. To check: the office has not settled this. "
        "The office's note: Cite page 4"
    )
    user = prompts.incident_memo_input("cameras", lines, "record", about=incident.about)
    assert "The office's note on the incident:\nThe stop of 7 June." in user
    assert (
        "The office's notes, on the incident and on its events"
        in prompts.INCIDENT_RULES
    )
    before = incident_assistant.events_signature(incident)
    chronology.change(
        first,
        {"at": "10", "text": "Asked out of the car", "note": "Cite page 5"},
        by=person,
    )
    assert incident_assistant.events_signature(incident) != before
    again = incident_assistant.events_signature(incident)
    incidents.set_about(incident, "Changed.", by=person)
    assert incident_assistant.events_signature(incident) != again


# The documents ---------------------------------------------------------------------


def test_the_words_are_in_the_glossary_and_the_guide():
    glossary = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    for word in ("**Note**:", "**To check**:", "**About**:", "**Incident clip**:"):
        assert word in glossary
    guide = (ROOT / "docs" / "user-guide.md").read_text(encoding="utf-8")
    assert "About this chronology" in guide and "To check" in guide
    spec = (ROOT / "docs" / "spec" / "SPEC-PHASE-7.md").read_text(encoding="utf-8")
    assert "## 1. The chronology as a document" in spec
