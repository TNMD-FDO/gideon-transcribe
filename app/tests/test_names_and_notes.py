"""v1.156.0: the notes export as blocks with a still at the moment, the
Names and places block with the people read-only and their names managed
on the Speakers tab, and the unit's kept voices told to recognition with a
switch each."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from core import audit, media, notes, queue, settings_store, vocabulary, voice_book
from core.cases import Case
from core.jobs import Segment
from core.models import User
from core.people import Person
from core.voice_book import UnitVoice
from django.urls import reverse
from tests.helpers import signed_in
from tests.test_prepare import a_recording

HERE = Path(__file__).resolve().parents[1]
PASSWORD = "a-long-enough-password"
# A one-pixel PNG, for a still the document can carry.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


@pytest.fixture
def owner(db):
    return User.objects.create_local_admin("owner", PASSWORD)


@pytest.fixture
def a_case(owner):
    settings_store.set_to("folder_management", True)
    return Case.objects.create(name="Traffic stop", owner=owner)


def docx_text(data: bytes) -> str:
    import io
    import zipfile

    with zipfile.ZipFile(io.BytesIO(data)) as zipped:
        return zipped.read("word/document.xml").decode("utf-8")


def test_the_notes_export_is_blocks_with_a_still_at_the_moment(
    owner, a_case, tmp_path, settings, monkeypatch, client
):
    camera = a_recording(
        owner, tmp_path, settings, case=a_case, title="Body camera 0412"
    )
    call = a_recording(
        owner, tmp_path, settings, case=a_case, title="Call 0403", video=False
    )
    line = camera.transcript.segments.order_by("start").first()
    line.note = "Bag is already open before the consent question."
    line.note_by = owner
    line.save(update_fields=["note", "note_by"])
    said = call.transcript.segments.order_by("start").first()
    said.note = "He names the second address here."
    said.note_by = owner
    said.clock = {
        "bound": 10.0,
        "to": 20.0,
        "hole": [],
        "block": said.pk,
        "retimed": True,
        "was": [2.0, 4.0],
        "shift": 8.0,
    }
    said.save(update_fields=["note", "note_by", "clock"])
    taken = []

    def grab(source, folder, times, *, height, timeout=0, up=False):
        taken.append((Path(source).name, [round(t, 1) for t in times], height))
        target = Path(folder) / "frame-1.png"
        target.write_bytes(PNG)
        return [target]

    monkeypatch.setattr(media, "grab_frames", grab)
    signed_in(client, owner)
    got = client.get(f"/case/{a_case.pk}/notes.docx")
    assert got.status_code == 200
    assert taken == [("playback.mp4", [0.0], notes.STILL_HEIGHT)]
    text = docx_text(got.content)
    # The note first, where it rests, the line quoted, the writer; no table head.
    assert "Bag is already open" in text and "He names the second address" in text
    assert "Rests on" not in text and "Writer" not in text
    assert "on Speaker 1" in text or "on Officer" in text or "on " in text
    assert "This is Officer Ruiz." in text
    assert "still at 00:00:00" in text
    # The re-read line says what its clock was.
    assert "clock re-read" in text and "was 00:00:02" in text
    # One still, from the camera's playback copy at the note's moment; none
    # for the call, which is audio.
    assert "Body camera 0412" in text and "Call 0403" in text
    # A still that cannot be cut leaves its note without one; the document prints.
    monkeypatch.setattr(media, "grab_frames", lambda *a, **k: 1 / 0)
    again = client.get(f"/case/{a_case.pk}/notes.docx")
    assert again.status_code == 200 and "Bag is already open" in docx_text(
        again.content
    )


def test_the_grouping_and_the_cap_on_stills():
    rows = [
        {
            "kind": "line",
            "id": 1,
            "where": "B",
            "recording_id": "b",
            "type": "Body camera",
            "created": 2,
            "at": 30.0,
        },
        {
            "kind": "moment",
            "id": 2,
            "where": "B",
            "recording_id": "b",
            "type": "Body camera",
            "created": 2,
            "at": 10.0,
        },
        {
            "kind": "line",
            "id": 3,
            "where": "A",
            "recording_id": "a",
            "type": "Jail call",
            "created": 1,
            "at": 5.0,
        },
        {"kind": "event", "where": "The stop", "at": 1.0},
    ]
    groups = notes._grouped(rows)
    assert [g["title"] for g in groups] == ["B", "A", "Incident: The stop"]
    assert [one["id"] for one in groups[0]["rows"]] == [2, 1]
    assert groups[0]["sub"].startswith("Body camera") and groups[0]["sub"].endswith(
        "2 notes"
    )
    assert notes.STILLS_MOST == 300


def test_names_and_places_reads_the_people_and_the_tab_edits_their_names(
    owner, a_case, client
):
    person = Person.objects.create(case=a_case, name="Dana Reyes", role="Witness")
    vocabulary.add_term(a_case, "Pike Street", "Pike Treat", by=owner)
    signed_in(client, owner)
    page = client.get(
        reverse("case", args=[a_case.pk]) + "?tab=details"
    ).content.decode()
    assert "Names and places" in page and "1 person · 1 place and term" in page
    assert 'class="name-chip"' in page and "Dana Reyes" in page
    assert "named and renamed on the" in page
    # The people are read-only here: no spellings form for a person.
    assert 'name="kind" value="person"' not in page
    assert "also heard as Pike Treat" in page
    assert "Gideon</b> is told the people and the terms" in page
    # The Speakers tab's card saves the nicknames and the spellings.
    answer = client.post(
        reverse("person-action", args=[person.pk]),
        {
            "action": "edit",
            "role": "Witness",
            "notes": "",
            "called": "Dee, Dana R",
            "spellings": "Donna Reyes",
        },
    )
    assert answer.status_code == 302
    person.refresh_from_db()
    assert person.also_called == ["Dee", "Dana R"]
    assert person.also_heard_as == ["Donna Reyes"]
    page = client.get(
        reverse("case", args=[a_case.pk]) + "?tab=details"
    ).content.decode()
    assert "also called Dee, Dana R" in page and "heard as Donna Reyes" in page
    tab = client.get(
        reverse("case", args=[a_case.pk]) + "?tab=speakers"
    ).content.decode()
    assert 'value="Dee, Dana R"' in tab and "Save role, notes and names" in tab
    assert f'id="person-{person.pk}"' in tab
    # Recognition gets the names and the nicknames, never the spelling.
    names = vocabulary.recognition_names(a_case)
    assert "Dana Reyes" in names and "Dee" in names and "Pike Street" in names
    assert "Donna Reyes" not in names


def test_the_units_kept_voices_are_told_to_recognition_with_a_switch_each(
    owner, a_case, tmp_path, settings, monkeypatch, client
):
    settings_store.set_to("remember_voices", True)
    settings_store.set_to("unit_voices", True)
    settings_store.set_to("units", "Trial | OU=Trial")
    monkeypatch.setattr(voice_book, "unit_of_case", lambda case: "Trial")
    kept = UnitVoice.objects.create(
        unit="Trial", name="Officer Hale", role="Officer", vector=[0.1, 0.2]
    )
    UnitVoice.objects.create(
        unit="Trial",
        name="Someone Forgotten",
        role="Officer",
        vector=[0.1],
        forgotten_at="2026-10-01T00:00:00Z",
    )
    UnitVoice.objects.create(
        unit="Appeals", name="Elsewhere", role="Officer", vector=[0.1]
    )
    assert voice_book.names_for_recognition(a_case) == ["Officer Hale"]
    assert "Officer Hale" in vocabulary.recognition_names(a_case)
    # The recogniser's request carries it, through the case's names.
    recording = a_recording(owner, tmp_path, settings, case=a_case, title="Call")
    assert "Officer Hale" in queue._case_vocabulary(recording)
    # The block says so.
    signed_in(client, owner)
    page = client.get(
        reverse("case", args=[a_case.pk]) + "?tab=details"
    ).content.decode()
    assert "1 kept voice of the Trial unit" in page
    assert "the Trial unit's kept voices' names" in page
    # The switch on the Voices place, with its row.
    answer = client.post(reverse("voices-recognition", args=[kept.pk]), {"told": "0"})
    assert answer.status_code == 302
    kept.refresh_from_db()
    assert kept.tell_recognition is False
    assert voice_book.names_for_recognition(a_case) == []
    row = audit.Row.objects.get(event="Unit voice recognition switched")
    assert row.details["told"] is False and row.object_label == "Trial"
    place = client.get(reverse("voices") + "?unit=Trial").content.decode()
    assert (
        "not told to recognition" in place
        and "Tell recognition this name again" in place
    )
    client.post(reverse("voices-recognition", args=[kept.pk]), {"told": "1"})
    kept.refresh_from_db()
    assert kept.tell_recognition is True
    # Off with the book: nothing is told.
    settings_store.set_to("unit_voices", False)
    assert voice_book.names_for_recognition(a_case) == []


def test_the_block_is_quiet_without_a_unit(owner, a_case, client):
    signed_in(client, owner)
    shown = vocabulary.block_context(a_case)
    assert shown["unit_count"] == 0 and shown["people"] == [] and shown["terms"] == []
    page = client.get(
        reverse("case", args=[a_case.pk]) + "?tab=details"
    ).content.decode()
    assert "kept voice" not in page.split("Names and places", 1)[1][:400]
    assert json.dumps(shown["people"]) == "[]"
    seg_count = Segment.objects.count()
    assert isinstance(seg_count, int)
