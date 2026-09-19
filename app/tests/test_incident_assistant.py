"""v1.61.0: the assistant on the Incident (Phase 6, chapter 3).

The rules checked here: the Case Chat is told each synced camera's start by
the incident clock, and nothing when the switch is off; the incident
record merges the cameras' Digests onto the clock, reads a camera with no
Digest from its words with numbered labels dropped and names kept, and is
never stored; Propose events runs one call per camera, keeps only the
proposals that pass the checks, replaces the pending ones and offers a
dismissed one again never; Accept makes an Event with source assistant and
its row, Dismiss puts one away; the memo is written on the chronology with
its citations and its event marks, says what it was written from, says when
the chronology changed since, exports to Word with the Chronology, and
counts nowhere until written; a numbered label does not show under a tile;
and the settings, the templates and the documents exist.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from core import (
    assistant,
    chronology,
    engine,
    incident_assistant,
    incidents,
    prompts,
    settings_store,
    tasks,
)
from core.assistant import DigestPart, PromptTemplate
from core.audit import Row
from core.cases import Case
from core.chronology import Event
from core.jobs import Segment, Transcript
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording
from tests.test_prepare import engine_answering

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
    settings_store.set_to("moments_available", True)
    settings_store.set_to("digests_available", True)


@pytest.fixture(autouse=True)
def no_tasks(monkeypatch):
    monkeypatch.setattr(tasks.propose_incident_events, "defer", lambda **f: None)
    monkeypatch.setattr(tasks.write_incident_memo, "defer", lambda **f: None)


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


def digest(recording, text: str) -> None:
    DigestPart.objects.create(
        transcript=recording.transcript, number=1, text=text, made_at=None
    )


@pytest.fixture
def incident(person, a_case):
    # The first camera's clock reads 21:56:19 two seconds in, so the incident's
    # zero is 21:56:17; the second starts 281 s later.
    first = video(
        person,
        a_case,
        "first",
        stamp=stamp("21:56:19", "BWC2-1"),
        lines=(
            (10.0, "Speaker 1", "Step out of the vehicle for me."),
            (30.0, "Officer Hale", "Hands where I can see them."),
        ),
    )
    second = video(
        person,
        a_case,
        "second",
        stamp=stamp("22:01:00", "BWC2-2"),
        lines=((5.0, "Speaker 4", "Stay in the car, please."),),
    )
    digest(
        first,
        '1. [00:00:10]-[00:00:14] (said) Speaker 1 said "Step out of the vehicle '
        'for me."\n2. [00:00:30]-[00:00:34] (both) Officer Hale asked for hands '
        "in view; the camera showed a grey jacket.",
    )
    return incidents.make(a_case, "Stop", [first, second], by=person)


def cameras_of(incident) -> dict:
    return {one.camera_id(): one for one in incident.cameras.all()}


# The Case Chat is told the placements ------------------------------------------------


def test_the_case_chat_is_told_each_synced_camera_s_start(incident, a_case):
    settings_store.set_to("incidents_case_chat", True)
    read = list(a_case.recordings.order_by("title"))
    block = incident_assistant.placements_block(a_case, read)
    assert block.startswith(
        "Incident Stop, 2 cameras on one clock, the time of day on 06/07/2025."
    )
    assert "Recording 1 (BWC2-1) starts at 21:56:17 and runs to 22:06:17." in block
    assert "Recording 2 (BWC2-2) starts at 22:00:58 and runs to 22:10:58." in block
    assert "the incident's clock is right" in block
    # A camera the question does not read is not in the block; the switch
    # off gives nothing.
    assert "Recording 2" not in incident_assistant.placements_block(a_case, read[:1])
    settings_store.set_to("incidents_case_chat", False)
    assert incident_assistant.placements_block(a_case, read) == ""
    settings_store.set_to("incidents_case_chat", True)
    # The Case chat template carries the time-of-day sentences, and the
    # shipped wording's history knows the new text.
    assert "time of day by the cameras' clock" in prompts.CASE_CHAT
    assert (
        prompts.text_hash(prompts.CASE_CHAT)
        in prompts.SHIPPED_HISTORY["prompt:case_chat"]
    )


# The incident record -----------------------------------------------------------------


def test_the_record_merges_the_cameras_onto_the_clock_and_drops_numbered_labels(
    incident,
):
    record = incident_assistant.record_of(incident)
    lines = [line for _, _, line in record["rows"]]
    names = [name for _, name, _ in record["rows"]]
    # The Digest's lines, rewritten to the clock, their numbers dropped; the
    # second camera read from its words, the label Speaker 4 dropped.
    assert lines[0].startswith("[21:56:27]-[21:56:31] (said)")
    assert names == ["BWC2-1", "BWC2-1", "BWC2-2"]
    assert lines[2] == "[22:01:03] Stay in the car, please."
    assert record["used"] == ["BWC2-1"] and record["transcript_only"] == ["BWC2-2"]
    # A name a person set stays when a camera is read from its words.
    DigestPart.objects.all().delete()
    record = incident_assistant.record_of(incident)
    lines = [line for _, _, line in record["rows"]]
    assert lines[0] == "[21:56:27] Step out of the vehicle for me."
    assert lines[1] == "[21:56:47] Officer Hale: Hands where I can see them."
    assert record["transcript_only"] == ["BWC2-1", "BWC2-2"]
    # Nothing of it is stored.
    assert not hasattr(incident, "record")


def test_the_record_counts_from_the_first_camera_without_a_clock(person, a_case):
    first = video(person, a_case, "one", lines=((10.0, "Speaker 1", "Hello."),))
    made = incidents.make(a_case, "No clock", [first], by=person)
    camera = made.cameras.get()
    incidents.place_by_hand(camera, 0.0, by=person)
    record = incident_assistant.record_of(made)
    assert [line for _, _, line in record["rows"]] == ["[00:00:10] Hello."]
    block = incident_assistant.placements_block(a_case, [first])
    assert "no camera has a clock" in block and "starts at 00:00:00" in block


# Proposed events --------------------------------------------------------------------


def proposals(*items):
    return json.dumps(
        {
            "events": [
                {"time": time, "end": end, "text": text, "rests_on": rests}
                for time, end, text, rests in items
            ]
        }
    )


def test_proposals_are_checked_kept_replaced_and_never_offered_again_once_dismissed(
    incident, person, monkeypatch
):
    settings_store.set_to("incidents_propose", True)
    # One look per camera and no watch phrases here; the windows, the second
    # look and the search have tests of their own (Phase 7 chapter 2).
    settings_store.set_to("incidents_second_look", False)
    settings_store.set_to("incidents_watch_phrases", "")
    cams = cameras_of(incident)
    # An Event already stands at the first camera's 00:00:10.
    chronology.add(
        incident,
        {"at": "10", "text": "Asked out of the car", "camera": str(cams["BWC2-1"].pk)},
        by=person,
    )
    asked = engine_answering(
        monkeypatch,
        [
            proposals(
                # Kept: inside the camera, rests on a real line.
                (
                    "00:00:30",
                    "",
                    "Hands asked into view",
                    "Officer Hale asked for hands",
                ),
                # Dropped: within five seconds of the standing Event.
                ("00:00:12", "", "Out of the car", "Step out of the vehicle"),
                # Dropped: outside the camera.
                ("00:20:00", "", "Too late", "Officer Hale asked for hands"),
                # Dropped: rests on nothing the camera was given.
                ("00:00:31", "", "Made up", "the dog barked at the moon"),
            ),
            proposals(
                ("00:00:05", "00:00:09", "Passenger told to stay", "Stay in the car")
            ),
        ],
    )
    assert incident_assistant.ask_for_proposals(incident, by=person)
    incident_assistant.propose(incident.pk)
    incident.refresh_from_db()
    assert incident.proposals_state == "done"
    assert incident.proposals_found == 2 and incident.proposals_cameras == 2
    # One call per camera, the schema and no thinking, with the standing
    # Event named so it is not proposed again.
    assert len(asked) == 2
    assert asked[0]["schema"]["properties"]["events"]["items"]["required"] == [
        "time",
        "end",
        "text",
        "why",
        "rests_on",
    ]
    assert asked[0]["thinking"] is False
    user = asked[0]["messages"][-1]["content"]
    assert "Camera BWC2-1 starts 21:56:17 by the cameras' clock" in user
    assert "21:56:27 Asked out of the car" in user
    # The second camera is told the first camera's proposal as well.
    assert "21:56:47 Hands asked into view" in asked[1]["messages"][-1]["content"]
    pending = list(incident.events.filter(proposed=True, dismissed=False))
    assert [one.text for one in pending] == [
        "Hands asked into view",
        "Passenger told to stay",
    ]
    assert pending[0].source == "assistant" and pending[0].camera == cams["BWC2-1"]
    assert (
        pending[0].at == 30.0 and pending[0].rests_on == "Officer Hale asked for hands"
    )
    assert pending[1].until == cams["BWC2-2"].starts_at + 9.0
    words = incident_assistant.proposals_json(incident)
    assert words["pending"] == 2 and words["words"].startswith("Proposed 2 events at ")
    # The state carries them as proposed, with the words each rests on; the
    # exports and the counts leave them out.
    rows = chronology.events_json(incident)
    assert [one["proposed"] for one in rows] == [False, True, True]
    assert rows[1]["source_words"] == "Proposed from BWC2-1"
    assert rows[1]["rests_on"] == "Officer Hale asked for hands"
    assert len(chronology._rows(incident)) == 1
    assert incidents.strip_rows(incident.case)[0]["events"] == 1
    # Dismiss one; Accept the other: an Event with source assistant, its row,
    # and the person who accepted it.
    incident_assistant.dismiss(pending[1], by=person)
    incident_assistant.accept(pending[0], by=person)
    kept = incident.events.filter(proposed=False).order_by("at")
    assert [one.text for one in kept] == [
        "Asked out of the car",
        "Hands asked into view",
    ]
    assert kept[1].source == "assistant" and kept[1].added_by == person
    assert chronology.events_json(incident)[1]["source_words"] == "Assistant, BWC2-1"
    assert chronology._rows(incident)[1]["assistant"]
    events = list(Row.objects.filter(category="cases").values_list("event", flat=True))
    assert "events proposed" in events and "event dismissed" in events
    added = Row.objects.filter(event="event added").order_by("-at").first()
    assert added.details.get("source") == "assistant"
    assert Row.objects.filter(
        event="AI assistant call", details__feature="incident_events"
    ).exists()
    for row in Row.objects.all():
        assert "Hands" not in json.dumps(row.details) and "Stay" not in json.dumps(
            row.details
        )
    # A dismissed proposal is off the page and a second run offers nothing
    # within five seconds of it on that camera.
    assert all(not one["proposed"] for one in chronology.events_json(incident))
    engine_answering(
        monkeypatch,
        [
            proposals(),
            proposals(
                ("00:00:07", "", "Passenger told to stay, again", "Stay in the car")
            ),
        ],
    )
    incident.proposals_state = ""
    incident.save()
    assert incident_assistant.ask_for_proposals(incident, by=person)
    incident_assistant.propose(incident.pk)
    assert not incident.events.filter(proposed=True, dismissed=False).exists()
    assert incident.events.filter(proposed=True, dismissed=True).count() == 1


def test_proposals_need_the_switch_and_a_synced_camera_with_words(
    incident, person, a_case
):
    settings_store.set_to("incidents_propose", False)
    # With the assistant off, the watch phrases alone keep the button (Phase
    # 7 chapter 2); with none listed, nothing offers it.
    assert incident_assistant.proposals_possible(incident)
    assert incident_assistant.proposer_offered()
    settings_store.set_to("incidents_watch_phrases", "")
    assert not incident_assistant.proposals_possible(incident)
    assert not incident_assistant.proposer_offered()
    assert not incident_assistant.ask_for_proposals(incident, by=person)
    settings_store.set_to("incidents_propose", True)
    silent = video(person, a_case, "silent", stamp=stamp("21:30:00", "BWC2-9"))
    alone = incidents.make(a_case, "Silent", [silent], by=person)
    assert not incident_assistant.proposals_possible(alone)
    assert incident_assistant.proposals_json(alone)["possible"] is False


def test_the_watch_phrases_are_searched_by_the_app_itself(person, a_case):
    # The floor (Phase 7 chapter 2): with the assistant off, the run is the
    # search alone; whole words, any case, the plural, a phrase heard again
    # within the join window joining its first hit, and "begun" never "gun".
    settings_store.set_to("incidents_propose", False)
    settings_store.set_to(
        "incidents_watch_phrases", "gun\n\nGun\nstep out of the vehicle\n"
    )
    assert settings_store.watch_phrases() == ["gun", "step out of the vehicle"]
    assert incident_assistant.phrase_pattern("gun").search("two guns down")
    assert not incident_assistant.phrase_pattern("gun").search("we had begun")
    # The run folds the line first: case, curly apostrophes, spacing.
    assert incident_assistant.phrase_pattern("I can't breathe").search(
        incident_assistant._plain("He said I can\u2019t  BREATHE")
    )
    cam = video(
        person,
        a_case,
        "one",
        lines=(
            (10.0, "Speaker 1", "Step out of the vehicle, please."),
            (270.0, "Speaker 4", "I got, I got gun, I got gun."),
            (285.0, "Speaker 4", "Guns down."),
            (400.0, "Speaker 1", "We had begun the search."),
        ),
    )
    made = incidents.make(a_case, "Search", [cam], by=person)
    camera = made.cameras.get()
    incidents.place_by_hand(camera, 0.0, by=person)
    assert incident_assistant.proposals_possible(made)
    assert incident_assistant.ask_for_proposals(made, by=person)
    incident_assistant.propose(made.pk)
    made.refresh_from_db()
    assert made.proposals_state == "done"
    pending = list(made.events.filter(proposed=True).order_by("at"))
    assert [(one.at, one.source) for one in pending] == [
        (10.0, "watch"),
        (270.0, "watch"),
    ]
    assert (
        pending[0].text
        == 'Watch phrase "step out of the vehicle": Step out of the vehicle, please.'
    )
    assert (
        pending[1].text
        == 'Watch phrase "gun": I got, I got gun, I got gun. (said 2 times)'
    )
    assert pending[1].why == 'The office watches for "gun".'
    assert pending[1].rests_on == "I got, I got gun, I got gun."
    assert made.proposals_watch == 2 and made.proposals_found == 2
    words = incident_assistant.proposals_json(made)
    assert words["on"] and "2 from the watch phrases" in words["words"]
    names = {str(camera.pk): camera.camera_id()}
    assert (
        chronology.source_words(pending[1], names)
        == f"Watch phrase, {camera.camera_id()}"
    )
    # No engine call, so no AI assistant call row; the run's own row counts the hits.
    assert not Row.objects.filter(event="AI assistant call").exists()
    proposed = Row.objects.filter(event="events proposed").order_by("-at").first()
    assert (
        proposed.details.get("watch_hits") == 2 and proposed.details.get("windows") == 0
    )
    for row in Row.objects.all():
        assert "gun" not in json.dumps(row.details)
    # Accepted, the Event keeps its source and its why, and Edit keeps the source.
    incident_assistant.accept(pending[1], by=person)
    pending[1].refresh_from_db()
    chronology.change(pending[1], {"at": "270", "text": "Gun found"}, by=person)
    pending[1].refresh_from_db()
    assert pending[1].source == "watch" and pending[1].why.startswith("The office")
    rows = chronology._rows(made)
    assert rows[0]["why"] == 'The office watches for "gun".'
    assert "Why it matters" in chronology.spreadsheet(made).decode("utf-8-sig")


def test_the_run_reads_in_windows_with_a_second_look_and_says_why(
    person, a_case, monkeypatch
):
    settings_store.set_to("incidents_propose", True)
    settings_store.set_to("incidents_watch_phrases", "")
    settings_store.set_to("incidents_events_context", "A public defender's office.")
    cam = video(
        person,
        a_case,
        "long",
        seconds=1500.0,
        lines=(
            (10.0, "Speaker 1", "Step out of the vehicle, please."),
            (700.0, "Speaker 4", "I got, I got gun, I got gun."),
            (1300.0, "Speaker 1", "We had begun the search."),
        ),
    )
    made = incidents.make(a_case, "Long", [cam], by=person)
    camera = made.cameras.get()
    incidents.place_by_hand(camera, 0.0, by=person)
    monkeypatch.setattr(engine, "is_reachable", lambda: True)
    monkeypatch.setattr(engine, "address", lambda: "http://gideon-generator:8000/v1")
    asked = []

    def complete(messages, **options):
        asked.append(messages[-1]["content"])
        user = messages[-1]["content"]
        # The second window's first look finds the gun; its second look adds
        # a why-bearing item; one answer is cut short.
        if "I got gun" in user and "You proposed" not in user:
            text = json.dumps(
                {
                    "events": [
                        {
                            "time": "00:11:40",
                            "end": "",
                            "text": "An officer said he had found a gun.",
                            "why": "A weapon changes the stop.",
                            "rests_on": "I got, I got gun",
                        }
                    ]
                }
            )
            return {
                "text": text,
                "finish_reason": "length",
                "input_tokens": 1,
                "output_tokens": 1,
                "model": "m",
            }
        return {
            "text": json.dumps({"events": []}),
            "finish_reason": "stop",
            "input_tokens": 1,
            "output_tokens": 1,
            "model": "m",
        }

    monkeypatch.setattr(engine, "complete", complete)
    assert incident_assistant.ask_for_proposals(
        made, by=person, look_for="anything about the gun"
    )
    made.refresh_from_db()
    assert made.proposals_look_for == "anything about the gun"
    incident_assistant.propose(made.pk)
    made.refresh_from_db()
    # Three windows of ten minutes, two looks each.
    assert len(asked) == 6
    assert sum("You proposed" in one for one in asked) == 3
    assert all(
        "About the office and its cases: A public defender's office." in one
        for one in asked
    )
    assert all("look for: anything about the gun" in one for one in asked)
    assert "one stretch of" in asked[0]
    # The second look is told what the first proposed.
    second = [one for one in asked if "You proposed" in one and "I got gun" in one][0]
    assert "00:11:40 An officer said he had found a gun." in second
    assert made.proposals_look_for == "" and made.proposals_cut == 1
    pending = list(made.events.filter(proposed=True))
    assert len(pending) == 1 and pending[0].why == "A weapon changes the stop."
    assert pending[0].at == 700.0 and pending[0].source == "assistant"
    words = incident_assistant.proposals_json(made)["words"]
    assert words.startswith("Proposed 1 event at ") and "1 answer cut short" in words
    row = chronology.events_json(made)[0]
    assert row["why"] == "A weapon changes the stop." and row["proposed"]
    call = Row.objects.filter(event="AI assistant call").order_by("-at").first()
    assert call.details.get("windows") == 3 and call.details.get("second_looks") == 3
    assert call.details.get("look_for") is True and call.details.get("cut_short") == 1
    assert "anything about the gun" not in json.dumps(call.details)
    # With the second look off, one look a window.
    settings_store.set_to("incidents_second_look", False)
    asked.clear()
    made.proposals_state = ""
    made.save()
    assert incident_assistant.ask_for_proposals(made, by=person)
    incident_assistant.propose(made.pk)
    assert len(asked) == 3 and not any("You proposed" in one for one in asked)


def test_the_windows_split_a_record_by_its_times():
    lines = ["[00:00:05] a", "[00:09:59] b", "no time", "[00:10:00] c", "[00:31:00] d"]
    assert incident_assistant._windows(lines, 600) == [
        ["[00:00:05] a", "[00:09:59] b", "no time"],
        ["[00:10:00] c"],
        ["[00:31:00] d"],
    ]


# The Incident memo ------------------------------------------------------------------


MEMO = (
    "Summary:\n"
    "At about 21:56 on 6 July 2025 a driver was asked out of the car [21:56:27] "
    "(Event 1) and told to keep hands in view [21:56:47] (Event 2).\n\n"
    "The cameras:\n"
    "BWC2-1 ran from [21:56:17] to [22:06:17]; BWC2-2 from [22:00:58].\n\n"
    "What happened:\n"
    "The passenger was told to stay in the car on BWC2-2 [22:01:03]. Nothing "
    "was seen at [23:59:00].\n\n"
    "Unclear parts:\n"
    "None.\n"
)


def test_the_memo_is_written_on_the_chronology_with_citations_and_marks(
    incident, person, monkeypatch, client
):
    settings_store.set_to("incidents_memo", True)
    cams = cameras_of(incident)
    first = chronology.add(
        incident, {"at": "10", "text": "Asked out of the car"}, by=person
    )
    second = chronology.add(
        incident,
        {
            "at": "30",
            "text": "Hands where I can see them.",
            "source": "words",
            "camera": str(cams["BWC2-1"].pk),
        },
        by=person,
    )
    asked = engine_answering(monkeypatch, [MEMO])
    memo = incident_assistant.ask_for_memo(incident, by=person)
    assert memo is not None and memo.state == "queued"
    incident_assistant.write_memo(memo.pk)
    memo.refresh_from_db()
    assert memo.state == "done" and memo.text == MEMO.strip()
    # What the memo was given: the cameras, the chronology numbered, the
    # record on the clock, the fixed rules with the templates.
    system = asked[0]["messages"][0]["content"]
    user = asked[0]["messages"][-1]["content"]
    assert prompts.INCIDENT_RULES in system and prompts.NARRATIVE_RULES in system
    assert prompts.INCIDENT_MEMO in system
    assert (
        "Event 1, 21:56:27, Asked out of the car; seen on BWC2-1; added by a person."
        in user
    )
    assert (
        "Event 2, 21:56:47, Hands where I can see them.; seen on BWC2-1; "
        "from the words on BWC2-1." in user
    )
    assert "BWC2-2: [22:01:03] Stay in the car, please." in user
    assert "BWC2-1, 21:56:17 to 22:06:17, from its clock, checked" in user
    assert asked[0]["max_completion_tokens"] == 4000
    # The citations inside the span, the marks by the numbering at writing.
    assert memo.citations == {
        "[21:56:27]": 10.0,
        "[21:56:47]": 30.0,
        "[21:56:17]": 0.0,
        "[22:06:17]": 600.0,
        "[22:00:58]": 281.0,
        "[22:01:03]": 286.0,
    }
    assert memo.event_numbers == {"1": str(first.pk), "2": str(second.pk)}
    assert memo.cameras_used == ["BWC2-1"]
    assert memo.cameras_transcript_only == ["BWC2-2"]
    assert memo.events_count == 2 and memo.record_lines == 3
    words = incident_assistant.written_words(memo)
    assert words.startswith("Written ")
    assert (
        "the transcripts and the vision of 1 camera and the words alone of 1" in words
    )
    assert "on the chronology's 2 events." in words
    assert incident_assistant.stale_words(memo, incident) == ""
    assert incident_assistant.memo_line(incident).startswith("memo written ")
    state = incident_assistant.memo_json(incident)
    assert state["state"] == "done" and state["event_numbers"]["2"] == str(second.pk)
    assert state["notice"] and state["busy"] is False
    # The row: metadata only.
    row = Row.objects.get(event="AI assistant call", details__feature="incident_memo")
    assert row.details["events"] == 2 and "Asked" not in json.dumps(row.details)
    # The chronology changes: the tab says so, and so does the case page.
    chronology.add(incident, {"at": "40", "text": "Tow truck"}, by=person)
    assert incident_assistant.stale_words(memo, incident) == (
        "The chronology has changed since this memo was written: 1 event added. "
        "Regenerate to write it on them."
    )
    assert incident_assistant.memo_line(incident).endswith(", 1 event newer")
    chronology.change(first, {"at": "11", "text": "Asked out"}, by=person)
    chronology.remove(Event.objects.get(text="Tow truck"), by=person)
    assert "an event changed" in incident_assistant.stale_words(memo, incident)
    incidents.place_by_hand(cams["BWC2-2"], 290.0, by=person)
    assert "a camera was synced or joined" in incident_assistant.stale_words(
        memo, incident
    )
    # The Word export carries the memo and the Chronology, and writes its row.
    signed_in(client, person)
    answer = client.post(
        f"/case/{incident.case_id}/incident/{incident.pk}/export/memo", {}
    )
    assert answer.status_code == 200
    assert answer["Content-Disposition"].endswith('"Incident memo - Stop.docx"')
    assert answer.content[:2] == b"PK"
    assert Row.objects.filter(event="incident memo exported").exists()

    # Regenerate resets the one row; a failed engine says so.
    def failing(messages, **options):
        from core import engine

        raise engine.Problem(engine.TIMEOUT, "took too long")

    monkeypatch.setattr("core.engine.complete", failing)
    again = incident_assistant.ask_for_memo(incident, by=person)
    assert again.pk == memo.pk and again.state == "queued" and again.text == ""
    incident_assistant.write_memo(again.pk)
    again.refresh_from_db()
    assert again.state == "failed" and again.reason_class == "llm_timeout"
    assert incident_assistant.memo_json(incident)["reason_words"]
    assert incident_assistant.memo_line(incident) == "no memo yet"


def test_the_memo_needs_a_synced_camera_and_drops_a_long_transcript_first(
    incident, person, monkeypatch
):
    settings_store.set_to("incidents_memo", True)
    possible, why = incident_assistant.memo_possible(incident)
    assert possible and why == ""
    # The second camera has many lines and no Digest: when the whole does not
    # fit the window it drops to a line and the memo says so; when even that
    # does not fit, the memo fails as too long.
    second = cameras_of(incident)["BWC2-2"].recording.transcript
    for n in range(60):
        Segment.objects.create(
            transcript=second,
            start=20.0 + n * 5,
            end=24.0 + n * 5,
            text=f"Line number {n} of the passenger's talk about the evening.",
            speaker="Speaker 4",
            speaker_label="SPEAKER_4",
        )
    asked = engine_answering(monkeypatch, [MEMO, MEMO])
    system_cost = prompts.tokens(
        prompts.system_message(
            PromptTemplate.named(PromptTemplate.GROUND_RULES).text,
            PromptTemplate.named(PromptTemplate.INCIDENT_MEMO).text,
            prompts.INCIDENT_MEMO_FORMAT
            + "\n\n"
            + prompts.NARRATIVE_RULES
            + "\n\n"
            + prompts.INCIDENT_RULES,
        )
    )
    record = incident_assistant.record_of(incident)
    event_lines, _ = incident_assistant._chronology_lines(incident)
    dropped_cost = prompts.tokens(
        prompts.incident_memo_input(
            incident_assistant._cameras_line(incident),
            event_lines,
            incident_assistant._record_text(incident, record, {"BWC2-2"}),
        )
    )
    settings_store.set_to("engine_window_tokens", 4096)
    settings_store.set_to(
        "incidents_memo_answer_tokens", 4096 - system_cost - dropped_cost - 5
    )
    memo = incident_assistant.ask_for_memo(incident, by=person)
    incident_assistant.write_memo(memo.pk)
    memo.refresh_from_db()
    assert memo.state == "done"
    assert memo.cameras_not_read == ["BWC2-2"]
    assert "its words were not read" in asked[0]["messages"][-1]["content"]
    assert "could not be read in full" in incident_assistant.written_words(memo)
    settings_store.set_to("incidents_memo_answer_tokens", 4096 - system_cost - 5)
    memo = incident_assistant.ask_for_memo(incident, by=person)
    incident_assistant.write_memo(memo.pk)
    memo.refresh_from_db()
    assert memo.state == "failed" and memo.reason_class == "llm_too_long"
    # No synced camera: no memo.
    settings_store.set_to("engine_window_tokens", 131072)
    for camera in incident.cameras.all():
        camera.placed = incidents.GUESS
        camera.save()
    possible, why = incident_assistant.memo_possible(incident)
    assert not possible and why.startswith("No camera is synced yet")
    assert incident_assistant.ask_for_memo(incident, by=person) is None
    settings_store.set_to("incidents_memo", False)
    state = incident_assistant.memo_json(incident)
    assert state["on"] is False and state["state"] == ""


# The page ---------------------------------------------------------------------------


def test_the_page_and_the_act_endpoint_carry_chapter_3(incident, person, client):
    settings_store.set_to("incidents_memo", True)
    settings_store.set_to("incidents_propose", True)
    signed_in(client, person)
    url = f"/case/{incident.case_id}/incident/{incident.pk}"
    page = client.get(url).content.decode()
    assert 'data-panel="memo">' in page and " Memo</button>" in page
    assert 'id="export-memo"' in page
    assert "exportMemo:" in page
    state = client.get(url + "/state").json()
    assert state["memo"]["on"] and state["memo"]["state"] == ""
    assert state["memo"]["before"] == "2 cameras synced, 0 events on the chronology."
    assert state["proposals"]["on"] and state["proposals"]["possible"]
    # Propose events and Write the memo queue their runs and say so.
    got = client.post(url + "/act", {"action": "propose"}).json()
    assert got["ok"] and got["state"]["proposals"]["busy"]
    got = client.post(url + "/act", {"action": "memo"}).json()
    assert got["ok"] and got["state"]["memo"]["busy"]
    got = client.post(url + "/act", {"action": "memo_cancel"}).json()
    assert got["ok"] and got["state"]["memo"]["state"] == ""
    # Accept and Dismiss from the page, and Accept all.
    cams = cameras_of(incident)
    for text in ("One", "Two", "Three"):
        Event.objects.create(
            incident=incident,
            at=20.0,
            text=text,
            source="assistant",
            camera=cams["BWC2-1"],
            proposed=True,
            rests_on="a line",
        )
    one, two, three = Event.objects.filter(proposed=True).order_by("added")
    # While the run is going nothing is accepted or dismissed: the proposals
    # are still arriving, and one accepted now would be proposed again by
    # the cameras read after it (v1.63.2). The buttons show greyed.
    type(incident).objects.filter(pk=incident.pk).update(proposals_state="running")
    for held in (
        {"action": "event_accept", "event": str(one.pk)},
        {"action": "event_dismiss", "event": str(one.pk)},
        {"action": "event_accept_all"},
    ):
        answer = client.post(url + "/act", held)
        assert answer.status_code == 409
        assert answer.json()["error"] == (
            "The assistant is still proposing. Wait for it to finish."
        )
    assert Event.objects.filter(proposed=True).count() == 3
    type(incident).objects.filter(pk=incident.pk).update(proposals_state="done")
    got = client.post(
        url + "/act", {"action": "event_accept", "event": str(one.pk)}
    ).json()
    assert {e["text"]: e["proposed"] for e in got["state"]["events"]} == {
        "One": False,
        "Two": True,
        "Three": True,
    }
    got = client.post(
        url + "/act", {"action": "event_dismiss", "event": str(two.pk)}
    ).json()
    assert sorted(e["text"] for e in got["state"]["events"]) == ["One", "Three"]
    got = client.post(url + "/act", {"action": "event_accept_all"}).json()
    assert got["said"] == "1 event added."
    assert all(not e["proposed"] for e in got["state"]["events"])
    # An Event that is not a proposal cannot be accepted.
    assert (
        client.post(
            url + "/act", {"action": "event_accept", "event": str(one.pk)}
        ).status_code
        == 404
    )
    # With the memo off the tab is gone; with proposals off, the button.
    settings_store.set_to("incidents_memo", False)
    settings_store.set_to("incidents_propose", False)
    # The watch phrases alone would keep the button (Phase 7 chapter 2).
    settings_store.set_to("incidents_watch_phrases", "")
    page = client.get(url).content.decode()
    assert 'data-panel="memo"' not in page
    state = client.get(url + "/state").json()
    assert state["proposals"]["on"] is False and state["memo"]["on"] is False
    assert client.post(url + "/act", {"action": "propose"}).status_code == 400
    assert client.post(url + "/act", {"action": "memo"}).status_code == 400
    assert client.post(url + "/export/memo").status_code == 404
    # The case page says whether an incident has a memo.
    settings_store.set_to("incidents_memo", True)
    case_page = client.get(f"/case/{incident.case_id}?tab=incidents").content.decode()
    assert "no memo yet" in case_page


def test_a_numbered_label_does_not_show_under_a_tile(incident, person, client):
    signed_in(client, person)
    cams = cameras_of(incident)
    got = client.get(f"/incident-camera/{cams['BWC2-1'].pk}/lines").json()
    assert [one["speaker"] for one in got["segments"]] == ["", "Officer Hale"]
    assert got["segments"][0]["text"] == "Step out of the vehicle for me."


# The settings, the templates, the documents ----------------------------------------


def test_the_settings_templates_and_documents_exist(db, client):
    for key in (
        "incidents_case_chat",
        "incidents_propose",
        "incidents_events_answer_tokens",
        "incidents_events_time_seconds",
        "incidents_memo",
        "incidents_memo_answer_tokens",
        "incidents_memo_time_seconds",
    ):
        assert settings_store.definition(key).page == "incidents"
        assert settings_store.definition(key).group == "The assistant"
    assert settings_store.time_limit_seconds("incident_events") == 180
    assert settings_store.time_limit_seconds("incident_memo") == 600
    assert settings_store.incident_events_answer_cap() == 2000
    assert settings_store.incident_memo_answer_cap() == 4000
    for key, text, name in (
        (PromptTemplate.INCIDENT_EVENTS, prompts.INCIDENT_EVENTS, "Proposed events"),
        (PromptTemplate.INCIDENT_MEMO, prompts.INCIDENT_MEMO, "Incident memo"),
    ):
        row = PromptTemplate.named(key)
        assert row.text == text and not row.behind and row.name == name
        assert prompts.text_hash(text) in prompts.SHIPPED_HISTORY[f"prompt:{key}"]
    admin = User.objects.create_local_admin("adm", PASSWORD)
    signed_in(client, admin)
    templates = client.get("/panel/templates").content.decode()
    assert "Proposed events" in templates and "Incident memo" in templates
    panel = client.get("/panel/settings/incidents").content.decode()
    for name in (
        "Case chat knows the incidents",
        "Assistant proposes events",
        "Incident memo answer cap",
    ):
        assert name in panel
    glossary = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    assert "**Incident memo**" in glossary
    guide = (ROOT / "docs" / "user-guide.md").read_text(encoding="utf-8")
    assert "Propose events" in guide and "Memo to Word" in guide
    assert "Speaker labels on an incident" in guide
    admin_guide = (ROOT / "docs" / "admin-guide.md").read_text(encoding="utf-8")
    assert "Case chat knows the incidents" in admin_guide
    catalogue = (ROOT / "docs" / "spec" / "ADMIN-SETTINGS-CATALOGUE.md").read_text(
        encoding="utf-8"
    )
    assert "Proposed events time limit" in catalogue and "v1.61.0" in catalogue
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## v1.61.0" in changelog
    assert assistant.PromptTemplate.DEFAULTS[PromptTemplate.INCIDENT_MEMO][0] == (
        "Incident memo"
    )
