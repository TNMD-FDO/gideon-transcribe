"""v1.207.0: the Incidents tab and the incident page tidied (Phase 12,
chapter 9 amended; the drawing phase-12-incidents-tidy.html).

The rules checked here: the ruler fits the cameras and folds a long gap,
a span set by hand zooms it and reads as Your span, the Reader keeps its
column, the incidents built are a menu in the lead, a clockless video is
ticked in from its row; on the page a note is a row like any other with a
quiet source line, the event says how far into the camera's video it
falls, the marks sit on the camera's lane, and notes on an unsynced camera
wait in a line with Sync it. The pill's words are gone from the rows, the
Word export and the timeline report.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from core import chronology, incident_pages, incidents, settings_store
from core.cases import Case
from core.chronology import NOTE, Event
from core.models import User
from core.notes import MomentNote
from core.recordings import Batch, MediaState, Recording
from tests.helpers import stamp

APP = Path(__file__).resolve().parent.parent
ROOT = APP.parent
PASSWORD = "a-long-enough-password"


def static(name: str) -> str:
    return (APP / "static" / name).read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def incidents_on(db):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("incidents", True)


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("asker", PASSWORD)


@pytest.fixture
def a_case(person):
    return Case.objects.create(owner=person, name="Harbour Street stop")


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


# The page: a note is a row like any other ------------------------------------------


def test_the_quiet_line_says_who_which_camera_and_where_from(person, a_case):
    first = video(person, a_case, "first", stamp=stamp("21:56:19", "BWC2-1"))
    second = video(person, a_case, "second", stamp=stamp("22:01:00", "BWC2-2"))
    incident = incidents.make(a_case, "Stop", [first, second], by=person)
    cam_first, cam_second = incident.cameras.order_by("starts_at")
    chronology.add(
        incident,
        {"at": "134", "text": "Step out", "camera": str(cam_first.pk)},
        by=person,
    )
    note = MomentNote.objects.create(
        recording=first,
        at=200.0,
        note="All units at the corner",
        note_by=person,
        note_from={"kind": "map", "words": "from the map, on 4 cameras", "group": "g1"},
    )
    Event.objects.create(
        incident=incident,
        moment_note=note,
        at=200.0,
        text=note.note,
        source=NOTE,
        camera=cam_first,
        cameras=[str(cam_first.pk)],
        added_by=person,
    )
    rows = chronology.events_json(incident)
    typed, noted = rows[0], rows[1]
    # A person's own event: who added it. A note: who, which camera, where
    # from; never the pill's words.
    assert typed["source_line"] == "added by asker"
    assert noted["source_line"] == "asker · BWC2-1 · from the map, on 4 cameras"
    assert noted["group"] == "g1" and typed["group"] == ""
    # How far into the camera's video the moment falls, in words, and the
    # viewer's door at that second; a note's door opens its note.
    assert typed["video_at"] == pytest.approx(134.0)
    assert typed["video_words"] == "2 min 14 s"
    assert typed["video_url"].endswith("?t=134.0")
    assert typed["camera_name"] == "BWC2-1"
    assert noted["video_words"] == "3 min 20 s"
    assert noted["video_url"].endswith("&note=1")
    assert chronology.video_words(40) == "40 s"
    assert chronology.video_words(3723) == "1 h 2 min 3 s"
    assert chronology.video_words(0) == "0 s" and chronology.video_words(None) == ""
    # The Word export's Source column carries the same line.
    exported = chronology._rows(incident)
    assert [one["source"] for one in exported] == [
        "added by asker",
        "asker · BWC2-1 · from the map, on 4 cameras",
    ]


def test_notes_on_a_camera_not_yet_synced_wait_in_a_line(person, a_case):
    first = video(person, a_case, "first", stamp=stamp("21:56:19", "BWC2-1"))
    loose = video(person, a_case, "loose")
    incident = incidents.make(a_case, "Stop", [first, loose], by=person)
    camera = incident.cameras.get(recording=loose)
    # The app's guess puts it on the wall, but a guess is not a sync, and a
    # note on it becomes no event until it is.
    assert not camera.is_synced()
    MomentNote.objects.create(recording=loose, at=5.0, note="Here", note_by=person)
    MomentNote.objects.create(recording=loose, at=9.0, note="And here", note_by=person)
    state = incident_pages.state_json(incident, person)["incident"]
    assert state["waiting_notes"] == [
        {"camera": str(camera.pk), "name": camera.camera_id(), "count": 2}
    ]
    # A camera with no notes is not in the line; a synced camera never is.
    MomentNote.objects.filter(recording=loose).delete()
    MomentNote.objects.create(recording=first, at=5.0, note="Synced", note_by=person)
    state = incident_pages.state_json(incident, person)["incident"]
    assert state["waiting_notes"] == []


def test_the_page_draws_rows_without_pills_and_marks_on_the_lanes():
    script = static("incident.js")
    for wanted in (
        "function decorateEvents(",
        "function groupedEvents(",
        "function sourceLineHtml(",
        "function eventHeadHtml(",
        "function markHtml(",
        "function laneMarks(",
        "class='inc-waiting",
        "data-sync-camera=",
        "Open the recording",
        "ev.video_words",
    ):
        assert wanted in script, wanted
    # The grey pill is gone from the rows and the timeline; the row's time
    # says the video's own time on hover.
    assert "pillClass(" not in script
    card = static("event-card.js")
    assert "ev.video_words" in card and "ev.source_line" in card
    assert "group_words" in card
    css = static("app.css")
    for wanted in (
        ".inc-events .src-line,",
        ".inc-events .ev-dot {",
        ".inc-events .ev-note,",
        ".inc-waiting {",
        ".inc-strip .lane .track .mk-ev",
    ):
        assert wanted in css, wanted


# The tab: the ruler fits, the span is set by hand, the Reader stays ----------------


def test_the_strip_fits_the_cameras_folds_a_gap_and_zooms_to_a_span():
    strip = static("chronology.js")
    for wanted in (
        "var FOLD_AFTER = 3600, FOLD_SHARE = 3.2;",
        "function scaleOf(d)",
        "function setSpan(low, high)",
        "function clearSpan()",
        "function spanBox(d)",
        "function wireSpanBox()",
        "function wireSpanTrack(d)",
        "function spanHtml(d)",
        "function incidentsMenu(",
        "function helpHtml(",
        "data-act='unfold'",
        "data-win",
        "data-act='tick-many'",
        "data-act='clear-span'",
        "data-act='add-ticked'",
        "var UNCLOCKED_SHOWN = 6;",
        "Tick all",
        "Clear the span",
        "Your span",
    ):
        assert wanted in strip, wanted
    # The span the person set holds over the ticks' own span, and the ruler
    # draws from the scale, never the whole day, in strip mode.
    assert "state.setSpan" in strip.split("function spanOf(d)")[1].split("\n  }")[0]
    assert "percentOf(" in strip and "secondsOf(" in strip
    # No surety word on the tab: a bar wide enough carries its span alone.
    piece = strip.split("function barPiece(")[1].split("\n  }")[0]
    assert "!stripMode && b.surety" in piece
    assert 'hm(b.from) + " to " + hm(b.to)' in piece
    assert 'id="incidents-built"' in (APP / "templates" / "case.html").read_text(
        encoding="utf-8"
    )
    page = (APP / "templates" / "case.html").read_text(encoding="utf-8")
    for wanted in (
        'id="incidents-list"',
        'id="span-from"',
        'id="span-to"',
        'id="span-set"',
        'id="span-clear"',
        'id="desk-yours"',
        'id="desk-built"',
        'id="unclocked-host"',
    ):
        assert wanted in page, wanted
    css = static("app.css")
    # The desk (v1.212.0): two columns by fractions, no breakpoint.
    assert ".builder {" in css and ".builder-left, .builder-right {" in css
    for wanted in (
        ".span-box {",
        ".inc-list {",
        ".chron .ruler .fold {",
        ".chron .dayline {",
        ".chron .col.build.set {",
        ".chron .track.strip",
        ".unclocked-row .uc",
        ".desk-panel .cam-row input.tk",
    ):
        assert wanted in css, wanted


def test_the_words_are_in_the_glossary_the_guide_and_the_changelog():
    glossary = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    assert "**Your span**" in glossary and "**Your incident**" in glossary
    guide = (ROOT / "docs" / "user-guide.md").read_text(encoding="utf-8")
    assert "**Your span**" in guide and "Tick all" in guide
    assert "Open the recording" in guide and "Sync it" in guide
    spec = (ROOT / "docs" / "spec" / "SPEC-PHASE-12.md").read_text(encoding="utf-8")
    assert "tidied" in spec and "phase-12-incidents-tidy.html" in spec
    log = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## v1.207.0" in log and "Your span" in log
