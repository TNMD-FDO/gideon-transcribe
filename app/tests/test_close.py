"""v1.97.0: close matches and what was seen, in the three boxes.

The rules checked here: a word's close forms are its other forms and its
near spellings, and only ones written in what is searched; a short word has
no near spelling and a phrase in quotes no forms at all; the exact hits
come first and a line is never both; what the cameras showed is found with
its time; the recording page's box is answered the close lines and the
picture's; and nothing of a search is written to the audit log.
"""

from __future__ import annotations

import json

import pytest
from core import case_search, close, incidents, settings_store
from core.assistant import Moment
from core.audit import Row
from core.cases import Case
from core.jobs import Segment, Transcript
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording

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


def video(person, case, title, *, lines=(), seen=()):
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        case=case,
        title=title,
        original_filename=f"{title}.mp4",
        media_state=MediaState.READY,
        duration_seconds=600.0,
        playback_ready=True,
        stamp={
            "date": "06/07/2025",
            "time": "21:56:19",
            "camera": title,
            "at": 2.0,
            "checked": True,
        },
        probe={},
    )
    recording.folder.mkdir(parents=True, exist_ok=True)
    (recording.folder / "playback.mp4").write_bytes(b"not really media")
    transcript = Transcript.objects.create(recording=recording, language="en")
    for start, text in lines:
        Segment.objects.create(
            transcript=transcript,
            start=start,
            end=start + 4,
            text=text,
            speaker="Speaker 1",
            speaker_label="SPEAKER_1",
        )
    for at, text in seen:
        Moment.objects.create(
            transcript=transcript,
            at=at,
            span_start=at,
            span_end=at + 20,
            source=Moment.INTERVAL,
            state="done",
            text=text,
        )
    return recording


@pytest.fixture
def camera(person, a_case):
    return video(
        person,
        a_case,
        "BWC2-1",
        lines=(
            (10.0, "He had a pill in his hand."),
            (20.0, "There were pills on the seat."),
            (30.0, "Hand me the pillow."),
            (40.0, "They searched the car."),
            (50.0, "Nothing else to say."),
        ),
        seen=(
            (15.0, "A man with dreadlocks stands by the car."),
            (45.0, "An officer holds two bottles."),
        ),
    )


def lines_of(recording):
    return Segment.objects.filter(transcript=recording.transcript)


def test_a_words_close_forms_are_its_other_forms_and_near_spellings(camera):
    lines = lines_of(camera)
    seen = Moment.objects.filter(transcript=camera.transcript)
    # Another form of the word; never the pillow, which only looks alike.
    assert close.forms(["pill"], [(lines, "text")]) == {"pill": ["pills"]}
    assert close.forms(["search"], [(lines, "text")]) == {"search": ["searched"]}
    # A near spelling, from what the camera showed.
    assert close.forms(["dredlocks"], [(seen, "text")]) == {"dredlocks": ["dreadlocks"]}
    # Only forms that are written in what is searched.
    assert close.forms(["bottle"], [(lines, "text")]) == {}
    assert close.forms(["bottle"], [(seen, "text")]) == {"bottle": ["bottles"]}
    # What the app reads itself counts as written.
    assert close.forms(["bottle"], texts=["Two bottles were found."]) == {
        "bottle": ["bottles"]
    }
    # A word itself is not its own form, a stop word has none, a phrase none.
    assert close.forms(["pills"], [(lines, "text")]) == {"pills": ["pill"]}
    assert close.forms(["the"], [(lines, "text")]) == {}
    assert close.forms(case_search.terms('"a pill"'), [(lines, "text")]) == {}
    assert close.forms([], [(lines, "text")]) == {}
    assert close.every_form({"a": ["x", "y"], "b": ["y", "z"]}) == ["x", "y", "z"]


def test_the_case_search_gives_exact_hits_then_close_ones_and_what_was_seen(
    camera, a_case
):
    got = case_search.search(a_case, "pill")
    assert got["also"] == ["pills"] and got["close"] == 1
    hits = got["groups"][0]["hits"]
    assert [(one["at"], one["close"]) for one in hits] == [(10.0, False), (20.0, True)]
    assert str(hits[1]["text"]) == "There were <mark>pills</mark> on the seat."
    assert {one["key"]: one["count"] for one in got["kinds"]} == {"words": 2}
    # What the cameras showed is its own kind, found exactly and closely.
    got = case_search.search(a_case, "dreadlocks")
    assert {one["key"]: one["count"] for one in got["kinds"]} == {"seen": 1}
    hit = got["groups"][0]["hits"][0]
    assert hit["who"] == "Seen" and hit["when"] == "00:00:15" and not hit["close"]
    assert "<mark>dreadlocks</mark>" in str(hit["text"])
    assert hit["url"].endswith("?t=15.0")
    got = case_search.search(a_case, "bottle", kind="seen")
    assert [one["close"] for one in got["groups"][0]["hits"]] == [True]
    # Every word must be on the line, each as itself or as a close form.
    assert case_search.search(a_case, "pill seat")["close"] == 1
    assert case_search.search(a_case, "pill car")["total"] == 0
    # A phrase in quotes is exact and alone.
    got = case_search.search(a_case, '"a pill"')
    assert got["total"] == 1 and got["close"] == 0 and got["also"] == []


def test_the_case_page_says_which_hits_are_close(camera, a_case, person, client):
    signed_in(client, person)
    page = client.get(f"/case/{a_case.pk}?tab=search&q=pill").content.decode()
    assert 'id="search-also"' in page and "(pills)" in page
    assert '<tr class="close">' in page
    assert "Seen (" not in page
    page = client.get(f"/case/{a_case.pk}?tab=search&q=dreadlocks").content.decode()
    assert "Seen (1)" in page and 'id="search-also"' not in page
    for row in Row.objects.all():
        assert "dreadlocks" not in json.dumps(row.details)


def test_find_on_the_incident_page_reads_what_was_seen(camera, a_case, person):
    incident = incidents.make(a_case, "Stop", [camera], by=person)
    placed = incident.cameras.get()
    incidents.place_by_hand(placed, 100.0, by=person)
    got = case_search.find(incident, "bottle")
    assert got["also"] == ["bottles"]
    assert [(one["kind"], one["at"], one["close"]) for one in got["hits"]] == [
        ("seen", 145.0, True)
    ]
    assert got["hits"][0]["camera"] == str(placed.pk)
    got = case_search.find(incident, "pill")
    assert [(one["at"], one["close"]) for one in got["hits"]] == [
        (110.0, False),
        (120.0, True),
    ]
    assert case_search.find(incident, "p") == {
        "asked": "p",
        "hits": [],
        "skipped": 0,
        "also": [],
    }


def test_the_recording_page_is_answered_the_close_lines_and_the_picture(
    camera, person, client
):
    signed_in(client, person)
    url = f"/recording/{camera.pk}/find"
    got = client.get(url, {"q": "pill"}).json()
    second = lines_of(camera).get(start=20.0)
    assert got["close"] == [
        {"id": second.pk, "html": "There were <mark>pills</mark> on the seat."}
    ]
    assert got["seen"] == [] and got["also"] == ["pills"]
    got = client.get(url, {"q": "dreadlocks"}).json()
    assert got["close"] == []
    assert [(one["at"], one["clock"], one["close"]) for one in got["seen"]] == [
        (15.0, "00:00:15", False)
    ]
    assert client.get(url, {"q": "d"}).json()["seen"] == []
    # Another person's recording is not read.
    other = User.objects.create(username="nobody", display_name="nobody")
    stranger = signed_in(client, other)
    assert stranger.get(url, {"q": "pill"}).status_code == 404
    for row in Row.objects.all():
        assert "pill" not in json.dumps(row.details)


def test_the_words_are_in_the_glossary_and_the_guide():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent.parent
    glossary = (root / "CONTEXT.md").read_text(encoding="utf-8")
    guide = (root / "docs" / "user-guide.md").read_text(encoding="utf-8")
    assert "**Close match**:" in glossary
    assert "come after the exact hits" in guide
    assert "what the cameras showed" in guide
    assert (root / "docs" / "research" / "close-matches.md").exists()
