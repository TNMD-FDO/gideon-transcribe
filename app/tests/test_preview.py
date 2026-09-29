"""v1.98.0: the Preview, a moment played over the page it was cited on.

The rules checked here: the reading around a moment gives the lines and
what the camera showed in that window, the line cited, the description
cited when nothing was said in that second, and the line a note goes on;
it is read by whoever may read the transcript and by nobody else, and
writes nothing; a note written from it is the line's own note and an event
on the chronology of a synced camera; the case chat's citation names the
recording for it; a hit of Search on a line or on something seen plays in
it; and the words are in the glossary and the guide.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from core import case_search, chronology, incidents, settings_store
from core.assistant import Moment
from core.audit import Row
from core.case_chat import CaseChat, CaseChatTurn
from core.cases import Case
from core.jobs import Job, JobState, Segment, Transcript
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording

PASSWORD = "a-long-enough-password"
APP = Path(__file__).resolve().parent.parent
ROOT = APP.parent


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


@pytest.fixture
def camera(person, a_case):
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        case=a_case,
        title="BWC2-1",
        original_filename="BWC2-1.mp4",
        media_state=MediaState.READY,
        duration_seconds=1200.0,
        playback_ready=True,
        stamp={
            "date": "06/07/2025",
            "time": "21:56:19",
            "camera": "BWC2-1",
            "at": 2.0,
            "checked": True,
        },
        probe={},
    )
    recording.folder.mkdir(parents=True, exist_ok=True)
    (recording.folder / "playback.mp4").write_bytes(b"not really media")
    transcript = Transcript.objects.create(recording=recording, language="en")
    for start, text in (
        (100.0, "Far before the moment."),
        (758.0, "Check under the seat."),
        (764.0, "Gun. I have a gun under the seat."),
        (769.0, "That is not mine."),
        (1100.0, "Far after the moment."),
    ):
        Segment.objects.create(
            transcript=transcript,
            start=start,
            end=start + 4,
            text=text,
            speaker="Speaker 1",
            speaker_label="SPEAKER_1",
        )
    Moment.objects.create(
        transcript=transcript,
        at=761.0,
        span_start=755.0,
        span_end=763.5,
        source=Moment.INTERVAL,
        state="done",
        text="An officer lifts a dark handgun from under the seat.",
    )
    return recording


def line(camera, start):
    return Segment.objects.get(transcript=camera.transcript, start=start)


def test_the_reading_gives_the_lines_and_the_picture_around_the_moment(
    camera, person, client
):
    signed_in(client, person)
    before = Row.objects.count()
    got = client.get(f"/recording/{camera.pk}/around", {"t": "764.2"}).json()
    assert [one["start"] for one in got["lines"]] == [758.0, 764.0, 769.0]
    assert [one["clock"] for one in got["lines"]] == [
        "00:12:38",
        "00:12:44",
        "00:12:49",
    ]
    assert [one["at"] for one in got["seen"]] == [761.0]
    assert got["title"] == "BWC2-1" and got["clock"] == "00:12:44"
    assert got["media"].endswith("/playback.mp4") and got["is_video"] is True
    assert got["open"] == f"/recording/{camera.pk}?t=764.2"
    assert got["from"] == pytest.approx(719.2) and got["to"] == pytest.approx(854.2)
    # The line that starts in that second is the line cited, and the note's.
    assert got["cited"] == line(camera, 764.0).pk
    assert got["cited_seen"] is None and got["note_on"] == got["cited"]
    assert got["can_note"] is True and got["why_not"] == ""
    assert got["note_url"] == f"/recording/{camera.pk}/segment/"
    assert got["on_chronology"] is False and got["all"] == ""
    # Nothing is written for a reading, and nothing of it logged.
    assert Row.objects.count() == before


def test_a_thing_only_seen_is_cited_and_its_note_goes_on_the_line_spoken(
    camera, person, client
):
    signed_in(client, person)
    got = client.get(f"/recording/{camera.pk}/around", {"t": "761"}).json()
    assert got["cited"] is None
    assert got["cited_seen"] == str(Moment.objects.get().pk)
    assert got["note_on"] == line(camera, 758.0).pk
    # The chat cites the Digest's time, which may fall outside the span.
    got = client.get(f"/recording/{camera.pk}/around", {"t": "780"}).json()
    assert got["cited"] is None and got["cited_seen"] == str(Moment.objects.get().pk)
    assert got["note_on"] == line(camera, 769.0).pk
    # Far from anything seen, and an odd moment, are answered all the same.
    got = client.get(f"/recording/{camera.pk}/around", {"t": "1102"}).json()
    assert got["cited_seen"] is None and got["note_on"] == line(camera, 1100.0).pk
    got = client.get(f"/recording/{camera.pk}/around", {"t": "soon"}).json()
    assert got["seconds"] == 0.0 and got["lines"] == []


def test_the_reading_is_for_whoever_may_read_the_transcript(camera, person, client):
    other = User.objects.create(username="nobody", display_name="nobody")
    signed_in(client, other)
    assert client.get(f"/recording/{camera.pk}/around", {"t": "764"}).status_code == 404
    client.logout()
    assert client.get(f"/recording/{camera.pk}/around", {"t": "764"}).status_code in (
        302,
        403,
    )


def test_a_note_from_the_preview_is_the_lines_own_note(camera, person, a_case, client):
    """The Preview writes through the recording page's own action, so a note
    on a synced camera's line is still an event on the chronology."""
    incident = incidents.make(a_case, "Stop", [camera], by=person)
    placed = incident.cameras.get()
    incidents.place_by_hand(placed, 50.0, by=person)
    signed_in(client, person)
    got = client.get(f"/recording/{camera.pk}/around", {"t": "764"}).json()
    assert got["on_chronology"] is True
    assert got["all"].startswith(incident.url() + "?t=")
    cited = line(camera, 764.0)
    saved = client.post(
        f"{got['note_url']}{got['note_on']}/note",
        data=json.dumps({"note": "First mention of the gun."}),
        content_type="application/json",
    ).json()
    assert saved["saved"] is True and saved["note"] == "First mention of the gun."
    event = chronology.Event.objects.get(incident=incident, segment=cited)
    assert event.source == "note" and event.at == 814.0
    assert event.text == "First mention of the gun."
    again = client.get(f"/recording/{camera.pk}/around", {"t": "764"}).json()
    noted = [one for one in again["lines"] if one["id"] == cited.pk][0]
    assert noted["note"] == "First mention of the gun." and noted["note_by"]
    for row in Row.objects.all():
        assert "First mention" not in json.dumps(row.details)


def test_no_note_while_the_transcript_is_being_replaced(camera, person, client):
    again = Batch.objects.create(user=person, is_reprocessing=True)
    Job.objects.create(recording=camera, batch=again, state=JobState.RUNNING)
    signed_in(client, person)
    got = client.get(f"/recording/{camera.pk}/around", {"t": "764"}).json()
    assert got["can_note"] is False
    assert got["why_not"].startswith("This transcript is being replaced")


def test_the_case_chats_citation_names_the_recording(camera, person, a_case, client):
    settings_store.set_to("chat_across_cases", True)
    signed_in(client, person)
    chat = CaseChat.objects.create(case=a_case, asked_by=person, name="Gun?")
    CaseChatTurn.objects.create(
        chat=chat,
        number=1,
        question="Gun?",
        answer="Said [Recording 1, 00:12:44].",
        citations={
            "[Recording 1, 00:12:44]": {"recording": str(camera.pk), "seconds": 764.0}
        },
        state="done",
    )
    turn = client.get(f"/case/{a_case.pk}/chat").json()["chats"][0]["turns"][0]
    cited = turn["citations"]["[Recording 1, 00:12:44]"]
    assert cited["recording"] == str(camera.pk)
    assert cited["seconds"] == 764.0 and cited["media"].endswith("/playback.mp4")


def test_the_page_scripts_hand_the_recording_to_the_preview():
    chat = (APP / "static" / "case-chat.js").read_text(encoding="utf-8")
    assert "recording: where.recording" in chat
    assert "seconds: where.seconds" in chat and "media: where.media" in chat
    shared = (APP / "static" / "chat-ui.js").read_text(encoding="utf-8")
    assert "window.Preview.open(" in shared and "data-recording=" in shared
    script = (APP / "static" / "preview.js").read_text(encoding="utf-8")
    assert '"/around?t="' in script and 'told.note_url + one.id + "/note"' in script
    assert "and an event on the incident's chronology." in script
    assert "the line being spoken when this was seen" in script
    assert "—" not in script


def test_a_search_hit_on_a_line_or_on_the_picture_plays_in_the_preview(
    camera, a_case, person, client
):
    got = case_search.search(a_case, "gun")
    hit = got["groups"][0]["hits"][0]
    assert hit["preview"] == {"recording": str(camera.pk), "at": 764.0}
    got = case_search.search(a_case, "handgun")
    assert got["groups"][0]["hits"][0]["preview"] == {
        "recording": str(camera.pk),
        "at": 761.0,
    }
    signed_in(client, person)
    page = client.get(f"/case/{a_case.pk}?tab=search&q=gun").content.decode()
    assert f'data-preview-recording="{camera.pk}"' in page
    assert 'data-preview-at="764.0"' in page
    assert "preview.js" in page
    # A recording with no copy to play has no button.
    Recording.objects.filter(pk=camera.pk).update(playback_ready=False)
    got = case_search.search(a_case, "gun")
    assert got["groups"][0]["hits"][0]["preview"] is None


def test_the_preview_is_in_the_glossary_and_the_guide():
    glossary = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    guide = (ROOT / "docs" / "user-guide.md").read_text(encoding="utf-8")
    assert "**Preview**:" in glossary
    assert "the **Preview** opens over the page" in guide
    assert "plays the moment in the Preview without leaving the search" in guide
