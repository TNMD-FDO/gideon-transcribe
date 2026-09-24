"""v1.81.0: a note is an event, and the Event card (Phase 8, chapter 11).

The rules checked here: a note on a line of a synced camera is an event on
that incident's chronology at the line's moment, with the writer, from the
moment the camera is synced, and it moves with the camera; editing or
removing it from either place follows to the other with the note's own audit
rows and never an event row of its own; processing again keeps the row; a
hidden copy takes none and a long note is the text whole; the Notes tab,
Search and Find list it once; the exports and the assistant read it as the
office's own note; the page carries the Event card and the lane's marks
alone; the words are in the glossary, the guide and the spec.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from core import (
    case_search,
    chronology,
    incident_assistant,
    incidents,
    notes,
    settings_store,
    tasks,
)
from core.audit import Row
from core.cases import Case
from core.chronology import Event
from core.jobs import Segment, Transcript
from core.models import User
from tests.test_notes import PASSWORD, gun_line, post_note, signed_in, stamp, video

APP = Path(__file__).resolve().parent.parent
ROOT = APP.parent


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"


@pytest.fixture(autouse=True)
def switched_on(db, monkeypatch):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("incidents", True)
    settings_store.set_to("assistant_available", True)
    monkeypatch.setattr(tasks.answer_incident_turn, "defer", lambda **f: None)


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("asker", PASSWORD)


@pytest.fixture
def a_case(person):
    return Case.objects.create(owner=person, name="Traffic stop")


def camera_of(incident, recording):
    return incident.cameras.get(recording=recording)


def note_event(incident, line):
    return Event.objects.filter(incident=incident, segment=line).first()


@pytest.mark.django_db
def test_a_note_on_a_synced_cameras_line_is_an_event(person, a_case, client):
    first = video(person, a_case, "first", stamp=stamp("21:56:19", "BWC2-1"))
    second = video(person, a_case, "second", stamp=stamp("22:01:00", "BWC2-2"))
    incident = incidents.make(a_case, "Stop", [first, second], by=person)
    signed_in(client, person)
    line = gun_line(first)
    assert post_note(client, first, line, "Check the footage.").status_code == 200
    event = note_event(incident, line)
    assert event is not None and event.is_note()
    assert event.source == "note" and event.text == "Check the footage."
    assert event.at == 30.0 and event.until is None
    assert event.camera == camera_of(incident, first)
    assert event.cameras == [str(camera_of(incident, first).pk)]
    assert event.added_by == person and event.note == "" and not event.proposed
    row = next(
        one for one in chronology.events_json(incident) if one["id"] == str(event.pk)
    )
    assert row["source_words"] == "Note by asker, BWC2-1"
    assert row["note_by"] == "asker" and row["note_on"] and row["note"] == ""
    assert row["segment_id"] == str(line.pk)
    assert row["recording_id"] == str(first.pk) and row["line_start"] == 30.0
    assert row["line_url"] == f"/recording/{first.pk}?t=30.0&note=1"
    assert row["line_words"] == "I got, I got gun, I got gun."
    # A person's event carries the same keys, empty.
    other = chronology.add(incident, {"at": "5", "text": "Hello."}, by=person)
    plain = next(
        one for one in chronology.events_json(incident) if one["id"] == str(other.pk)
    )
    assert (
        plain["segment_id"] == "" and plain["line_url"] == "" and plain["note_by"] == ""
    )
    # The words follow a change, and the row goes with the note.
    post_note(client, first, line, "Check the footage, twice.")
    event.refresh_from_db()
    assert event.text == "Check the footage, twice."
    post_note(client, first, line, "")
    assert note_event(incident, line) is None
    # The note's own rows, and never an event row for the note.
    kinds = [one.event for one in Row.objects.filter(category="edits").order_by("at")]
    assert kinds == ["Note added", "Note changed", "Note removed"]
    # The one "event added" is the typed event's; the note event wrote none.
    assert Row.objects.filter(event="event added").count() == 1
    assert not Row.objects.filter(event="event removed").exists()
    for row in Row.objects.all():
        assert "footage" not in json.dumps(row.details).lower()


@pytest.mark.django_db
def test_a_note_written_before_the_join_appears_when_synced_and_moves(person, a_case):
    first = video(person, a_case, "first", stamp=stamp("21:56:19", "BWC2-1"))
    line = gun_line(first)
    notes.set_note(line, "Before the join.", by=person)
    assert not Event.objects.filter(segment=line).exists()
    incident = incidents.make(a_case, "Stop", [first], by=person)
    event = note_event(incident, line)
    assert event is not None and event.at == 30.0
    # A camera the app has only guessed carries no note event.
    third = video(person, a_case, "third", stamp=None)
    other = gun_line(third)
    notes.set_note(other, "On the third.", by=person)
    incidents.add_cameras(incident, [third], by=person)
    camera = camera_of(incident, third)
    assert not camera.is_synced() and note_event(incident, other) is None
    # Synced by hand: the event appears at the line's moment; re-placed, it
    # moves, the same row with its mark kept.
    incidents.place_by_hand(camera, 120.0, by=person)
    made = note_event(incident, other)
    assert made is not None and made.at == 150.0
    made.to_check = True
    made.save(update_fields=["to_check"])
    incidents.place_by_hand(camera, 200.0, by=person)
    moved = note_event(incident, other)
    assert moved.pk == made.pk and moved.at == 230.0 and moved.to_check
    # The camera removed: its note event goes, the note stays on the line.
    incidents.remove_camera(camera, by=person)
    other.refresh_from_db()
    assert note_event(incident, other) is None and other.note == "On the third."
    # The recording leaving the case: the same.
    incidents.left_the_case(first)
    line.refresh_from_db()
    assert note_event(incident, line) is None and line.note == "Before the join."
    # A recording in two incidents has the note on both chronologies.
    second = incidents.make(a_case, "Second", [third], by=person)
    incidents.place_by_hand(camera_of(second, third), 0.0, by=person)
    third_incident = incidents.make(a_case, "Third", [third], by=person)
    incidents.place_by_hand(camera_of(third_incident, third), 10.0, by=person)
    assert Event.objects.filter(segment=other).count() == 2
    notes.set_note(other, "Changed once.", by=person)
    assert set(Event.objects.filter(segment=other).values_list("text", flat=True)) == {
        "Changed once."
    }


@pytest.mark.django_db
def test_a_note_event_is_edited_and_removed_from_the_chronology(person, a_case):
    first = video(person, a_case, "first", stamp=stamp("21:56:19", "BWC2-1"))
    second = video(person, a_case, "second", stamp=stamp("22:01:00", "BWC2-2"))
    incident = incidents.make(a_case, "Stop", [first, second], by=person)
    line = gun_line(first)
    notes.set_note(line, "Check the footage.", by=person)
    event = note_event(incident, line)
    both = [str(one.pk) for one in incident.cameras.all()]
    changed = chronology.change(
        event,
        {
            "at": "999",
            "until": "1200",
            "text": "New words.",
            "to_check": "yes",
            "cameras": both,
        },
        by=person,
    )
    line.refresh_from_db()
    assert line.note == "New words." and line.note_by == person
    assert changed.at == 30.0 and changed.until is None and changed.source == "note"
    assert changed.to_check and set(changed.cameras) == set(both)
    rows = list(Row.objects.filter(category="edits").order_by("at"))
    assert [one.event for one in rows] == ["Note added", "Note changed"]
    assert rows[-1].details.get("where") == "chronology"
    assert not Row.objects.filter(event="event changed").exists()
    # The marks alone: the event's own row, and no note row.
    chronology.change(
        event, {"at": "1", "text": "New words.", "to_check": ""}, by=person
    )
    event.refresh_from_db()
    assert not event.to_check
    assert Row.objects.filter(event="event changed").count() == 1
    assert Row.objects.filter(category="edits").count() == 2
    # Remove on the chronology removes the note from the line.
    chronology.remove(event, by=person)
    line.refresh_from_db()
    assert line.note == "" and not Event.objects.filter(pk=event.pk).exists()
    assert Row.objects.filter(event="Note removed").count() == 1
    assert not Row.objects.filter(event="event removed").exists()
    # A request saying "note" makes a person's event.
    made = chronology.add(
        incident, {"at": "5", "text": "Typed.", "source": "note"}, by=person
    )
    assert made.source == "person" and not made.is_note()
    # A typed event is still capped at 500; a note event holds a note whole.
    long_note = "word " * 400
    notes.set_note(line, long_note, by=person)
    kept = note_event(incident, line)
    assert len(kept.text) == len(notes.clean(long_note)) > 500
    row = next(
        one for one in chronology.events_json(incident) if one["id"] == str(kept.pk)
    )
    assert row["line"].endswith("…") and row["detail"]
    typed = chronology.add(incident, {"at": "6", "text": "x" * 900}, by=person)
    assert len(typed.text) == 500


@pytest.mark.django_db
def test_processing_again_keeps_the_note_event(person, a_case):
    first = video(person, a_case, "first", stamp=stamp("21:56:19", "BWC2-1"))
    incident = incidents.make(a_case, "Stop", [first], by=person)
    line = gun_line(first)
    notes.set_note(line, "Check the footage.", by=person)
    notes.set_note(first.transcript.segments.get(start=60.0), "Whose?", by=person)
    first_event = note_event(incident, line)
    first_event.to_check = True
    first_event.save(update_fields=["to_check"])
    second_event = Event.objects.get(segment__start=60.0)
    kept = notes.remember(first)
    assert [one["events"] for one in kept] == [
        [str(first_event.pk)],
        [str(second_event.pk)],
    ]
    # Let go of their lines, the rows survive the Transcript's deletion.
    Transcript.objects.filter(recording=first).delete()
    assert Event.objects.filter(pk=first_event.pk, segment__isnull=True).exists()
    made = Transcript.objects.create(recording=first, language="en")
    for start, end, text in (
        (0.0, 10.0, "Hello."),
        (28.0, 35.0, "Gun."),
        (40.0, 50.0, "Bye."),
    ):
        Segment.objects.create(transcript=made, start=start, end=end, text=text)
    assert notes.carry(kept, made) == 2
    first_event.refresh_from_db()
    assert first_event.segment == made.segments.get(start=28.0)
    assert first_event.at == 28.0 and first_event.to_check
    assert Event.objects.filter(segment=made.segments.get(start=40.0)).exists()
    assert Event.objects.filter(incident=incident, source="note").count() == 2
    # Two notes joining one line keep one row; an orphan is swept.
    joined = notes.remember(first)
    Transcript.objects.filter(recording=first).delete()
    again = Transcript.objects.create(recording=first, language="en")
    Segment.objects.create(transcript=again, start=0.0, end=100.0, text="All of it.")
    assert notes.carry(joined, again) == 2
    only = again.segments.get()
    assert only.note == "Check the footage.\nWhose?"
    assert Event.objects.filter(incident=incident, source="note").count() == 1
    assert Event.objects.get(incident=incident, source="note").segment == only
    assert not Event.objects.filter(source="note", segment__isnull=True).exists()


@pytest.mark.django_db
def test_a_hidden_copy_takes_no_event_and_the_lists_say_a_note_once(
    person, a_case, client
):
    first = video(person, a_case, "first", stamp=stamp("21:56:19", "BWC2-1"))
    incident = incidents.make(a_case, "Stop", [first], by=person)
    line = gun_line(first)
    Segment.objects.filter(pk=line.pk).update(same_as_other_side=True)
    line.refresh_from_db()
    notes.set_note(line, "Hidden.", by=person)
    assert note_event(incident, line) is None
    Segment.objects.filter(pk=line.pk).update(same_as_other_side=False)
    line.refresh_from_db()
    notes.set_note(line, "Shown gun.", by=person)
    assert note_event(incident, line) is not None
    # Once: as the line's note.
    assert notes.count(a_case) == 1
    listed = notes.of_case(a_case)
    assert listed["lines"] == 1 and listed["events"] == 0
    counts = {
        one["key"]: one["count"] for one in case_search.search(a_case, "gun")["kinds"]
    }
    assert counts.get("events", 0) == 0 and counts["notes"] == 1
    hits = case_search.find(incident, "gun")
    assert sorted(one["kind"] for one in hits["hits"]) == ["note", "words"]


@pytest.mark.django_db
def test_the_exports_and_the_assistant_read_a_note_event_as_the_offices_own(
    person, a_case
):
    from tests.test_notes import docx_text

    first = video(person, a_case, "first", stamp=stamp("21:56:19", "BWC2-1"))
    incident = incidents.make(a_case, "Stop", [first], by=person)
    chronology.add(incident, {"at": "5", "text": "Typed."}, by=person)
    before = incident_assistant.events_signature(incident)
    text = docx_text(chronology.word(incident, None, "asker"))
    assert chronology.NOTE_LEGEND not in text
    notes.set_note(gun_line(first), "Check the footage.", by=person)
    assert incident_assistant.events_signature(incident) != before
    text = docx_text(chronology.word(incident, None, "asker"))
    assert "Note by asker, BWC2-1" in text and chronology.NOTE_LEGEND in text
    sheet = chronology.spreadsheet(incident).decode("utf-8-sig")
    assert "Note by asker, BWC2-1" in sheet
    lines, numbers = incident_assistant._chronology_lines(incident)
    assert lines[1] == (
        "Event 2, 21:56:47, Check the footage.; seen on BWC2-1; the office's own "
        "note, written by asker on the line at 21:56:47 on BWC2-1."
    )
    assert numbers["2"] == str(note_event(incident, gun_line(first)).pk)
    assert notes.any_on_chronology(incident)


@pytest.mark.django_db
def test_the_page_carries_the_event_card_and_the_marks_alone(person, a_case, client):
    first = video(person, a_case, "first", stamp=stamp("21:56:19", "BWC2-1"))
    incident = incidents.make(a_case, "Stop", [first], by=person)
    signed_in(client, person)
    page = client.get(incident.url()).content.decode()
    assert page.count("event-card.js") == 1
    assert page.count('id="event-title"') == 1 and 'id="event-eyebrow"' in page
    assert "hover it for its line, press it for its card" in page
    viewer_page = client.get(f"/recording/{first.pk}").content.decode()
    assert viewer_page.count("event-card.js") == 1
    static = APP / "static"
    incident_js = (static / "incident.js").read_text(encoding="utf-8")
    assert "data-event-card='" in incident_js and "EVENT_CARD.setup(" in incident_js
    assert "class='lbl" not in incident_js
    assert "tr[data-event='\" + id + \"']" in incident_js
    card_js = (static / "event-card.js").read_text(encoding="utf-8")
    for needed in (
        '"role", "dialog"',
        '"aria-hidden"',
        "(hover: none)",
        '"Escape"',
        "window.EVENT_CARD",
    ):
        assert needed in card_js
    viewer_js = (static / "viewer.js").read_text(encoding="utf-8")
    assert "note-tick" in viewer_js and "data-event-card" not in viewer_js.replace(
        "dataset.eventCard", ""
    )
    css = (static / "app.css").read_text(encoding="utf-8")
    for rule in (
        ".event-card {",
        ".event-card.light {",
        ".pill.src {",
        ".inc-events .line {",
        ".timeline .note-tick {",
    ):
        assert rule in css
    assert ".lane.events .track .lbl" not in css
    glossary = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    assert "**Event card**:" in glossary and "note event" in glossary
    guide = (ROOT / "docs" / "user-guide.md").read_text(encoding="utf-8")
    assert (
        "**event card**" in guide
        and "with its first words; click one to go there" not in guide
    )
    spec = (ROOT / "docs" / "spec" / "SPEC-PHASE-8.md").read_text(encoding="utf-8")
    assert "## 11. A note is an event, and the Event card" in spec
    assert "## 12. Deferred and ruled out" in spec


@pytest.mark.django_db(transaction=True)
def test_the_migration_makes_note_events_over_a_database_with_rows(person, a_case):
    """v1.81.1: the upgrade to v1.81.0 failed at migration 0060 on the office's
    server, "cannot CREATE INDEX because it has pending trigger events":
    PostgreSQL will not build 0060's index while the note events written in
    the same transaction still have their foreign-key checks pending. The
    rows are now made in 0061, a migration of its own. This test migrates a
    database that has a noted line on a synced camera back to 0059 and
    forward again, which the empty test database never exercised."""
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    first = video(person, a_case, "first", stamp=stamp("21:56:19", "BWC2-1"))
    second = video(person, a_case, "second", stamp=stamp("22:01:00", "BWC2-2"))
    incident = incidents.make(a_case, "Stop", [first, second], by=person)
    line = gun_line(first)
    notes.set_note(line, "Check the footage.", by=person)
    made = note_event(incident, line)
    assert made is not None
    executor = MigrationExecutor(connection)
    latest = executor.loader.graph.leaf_nodes("core")
    try:
        executor.migrate([("core", "0059_camera_shares")])
        executor = MigrationExecutor(connection)
        executor.migrate(latest)
    finally:
        MigrationExecutor(connection).migrate(latest)
    event = note_event(incident, line)
    assert event is not None and event.pk != made.pk
    assert event.source == "note" and event.text == "Check the footage."
    assert event.at == 30.0 and event.camera == camera_of(incident, first)
    assert event.cameras == [str(camera_of(incident, first).pk)]
    assert event.added_by == person
    assert Event.objects.filter(incident=incident, source="note").count() == 1
