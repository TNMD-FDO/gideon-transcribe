"""v1.169.0: the Proposed events tab (Phase 10 chapter 4, the second release).

Checked here: the tab is in the case's bar in the order given and hidden
when neither the assistant nor the watch phrases are on; its reading lays
the case's proposals out by day on the recordings' clocks with the why, the
source, the incident pill and what an accepted one became, and lists the
ones on recordings not yet placed; its acts (Accept, Accept and edit,
Dismiss, Accept all, Dismiss all) write notes or put rows away, refuse while
a run is going, and the run itself reads every recording with a transcript,
the watch phrases first, replaces its own waiting rows, keeps clear of the
notes and the dismissed, and says which recordings it has not read yet.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest
from core import case_chronology, incidents, proposals, settings_store, tasks
from core.audit import Row
from core.cases import Case
from core.jobs import Segment, Transcript
from core.models import User
from core.notes import MomentNote
from core.proposals import Proposal, ProposalRun
from core.recordings import Batch, MediaState, Recording
from tests.helpers import signed_in, stamp
from tests.test_prepare import engine_answering

PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def switched_on(db, monkeypatch):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("incidents", True)
    settings_store.set_to("assistant_available", True)
    settings_store.set_to("incidents_propose", True)
    monkeypatch.setattr(tasks.propose_case_events, "defer", lambda **f: None)
    monkeypatch.setattr(tasks.propose_incident_events, "defer", lambda **f: None)


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("asker", PASSWORD)


@pytest.fixture
def a_case(person):
    return Case.objects.create(owner=person, name="Traffic stop")


def video(person, case, title, *, stamp=None, lines=(), seconds=600.0):
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
        for start, text in lines:
            Segment.objects.create(
                transcript=transcript,
                start=start,
                end=start + 4,
                text=text,
                speaker="Speaker 1",
                speaker_label="SPEAKER_1",
            )
    return recording


def proposal(case, recording, **fields):
    given = {
        "at": 30.0,
        "text": "A weapon was mentioned.",
        "why": "A weapon changes the stop.",
        "rests_on": "I got gun",
        "source": "assistant",
    }
    given.update(fields)
    return Proposal.objects.create(case=case, recording=recording, **given)


def test_the_tab_is_in_the_bar_in_order_and_hides_with_the_proposer(
    person, a_case, client
):
    signed_in(client, person)
    page = client.get(f"/case/{a_case.pk}").content.decode()
    # The bar, in the order given: Recordings, Search, Proposed events,
    # Notes, (Documents,) Incidents, Clips, Speakers, Details.
    marks = [
        " Recordings <span",
        " Search</a>",
        " Proposed events <span",
        " Notes <span",
        " Incidents <span",
        " Clips <span",
        " Speakers <span",
        " Details</a>",
    ]
    spots = [page.index(mark) for mark in marks]
    assert spots == sorted(spots)
    assert "tab=proposed" in page
    # Off: neither the assistant's judgement nor a watch phrase.
    settings_store.set_to("incidents_propose", False)
    settings_store.set_to("incidents_watch_phrases", "")
    page = client.get(f"/case/{a_case.pk}").content.decode()
    assert "tab=proposed" not in page
    assert client.get(f"/case/{a_case.pk}?tab=proposed").status_code == 200


def test_the_reading_lays_proposals_out_by_day_with_the_unplaced_apart(
    person, a_case, client
):
    # Two recordings on the clock (the first by its stamp, the second by
    # hand), one with no clock at all.
    first = video(
        person,
        a_case,
        "BWC2-1",
        stamp=stamp("21:56:19", "BWC2-1"),
        lines=((10.0, "Step out."), (30.0, "I got gun.")),
    )
    second = video(person, a_case, "BWC2-2", lines=((5.0, "Stay in the car."),))
    case_chronology.place(
        second, dt.date(2025, 6, 7), 22 * 3600 + 60.0, by=person, how="hand"
    )
    loose = video(person, a_case, "Call", lines=((40.0, "Hello."),))
    made = incidents.make(a_case, "Stop", [first], by=person)
    waiting = proposal(a_case, first, incident=made)
    accepted = proposal(
        a_case, second, at=5.0, text="Passenger told to stay.", source="watch"
    )
    proposals.accept(accepted, by=person)
    proposal(a_case, loose, at=40.0, text="A greeting.")
    gone = proposal(a_case, first, at=200.0, text="Dismissed one.")
    proposals.dismiss(gone, by=person)
    signed_in(client, person)
    told = client.get(f"/case/{a_case.pk}/proposed.json").json()
    assert told["on"] is True and told["run"]["pending"] == 2
    assert [d["date"] for d in told["days"]] == ["2025-06-07"]
    day = told["day"]
    assert day["date"] == "2025-06-07" and day["count"] == 2
    rows = [e for g in day["spells"] for e in g["entries"]]
    assert [(e["kind"], e["state"]) for e in rows] == [
        ("proposal", "waiting"),
        ("proposal", "accepted"),
    ]
    mine = rows[0]
    assert mine["id"] == str(waiting.pk) and mine["why"] == "A weapon changes the stop."
    assert mine["source_words"] == "Proposed by the assistant"
    assert mine["said"] == "I got gun" and mine["for_incident"] == "Stop"
    assert mine["time"] == "21:56:47"
    theirs = rows[1]
    assert theirs["source_words"] == "Watch phrase" and theirs["time"] == "22:01:05"
    assert theirs["became"].startswith(f"a note on BWC2-2 by {person.shown_name}")
    assert theirs["note_url"].endswith("?t=5.0&note=1")
    # The day's notes are a lane of their own: the accepted one is a note now.
    assert len(day["notes_marks"]) == 1 and day["hints"] == [] and day["rail"] == []
    # The incident the camera is in shows on the entry.
    assert mine["incident"]["name"] == "Stop"
    # The recording with no clock: its proposal waits under Not yet placed.
    assert [(e["title"], e["time"]) for e in told["unplaced"]] == [("Call", "00:00:40")]
    # A dismissed one is nowhere.
    assert "Dismissed one." not in json.dumps(told)
    # The day's reading asked for a day with nothing on it is empty but whole.
    told = client.get(f"/case/{a_case.pk}/proposed.json?day=2025-06-08").json()
    assert told["day"]["count"] == 0 and len(told["unplaced"]) == 1


def test_the_acts_write_notes_or_put_away_and_wait_for_the_run(person, a_case, client):
    cam = video(person, a_case, "BWC2-1", lines=((10.0, "Step out."), (30.0, "Gun.")))
    one = proposal(a_case, cam, at=31.0, rests_on="Gun.")
    two = proposal(a_case, cam, at=120.0, text="Second.")
    three = proposal(a_case, cam, at=300.0, text="Third.")
    signed_in(client, person)
    act = f"/case/{a_case.pk}/proposed/act"

    def post(body):
        return client.post(act, json.dumps(body), content_type="application/json")

    got = post({"action": "accept", "id": str(one.pk)}).json()
    assert got["ok"] and got["said"] == "A note is written on BWC2-1."
    assert got["run"]["pending"] == 2
    assert Segment.objects.get(start=30.0).note == "A weapon was mentioned."
    # Accept and edit: the person's words, on the moment where nothing is said.
    got = post(
        {"action": "accept_edit", "id": str(two.pk), "text": "  My own  words. "}
    )
    assert got.status_code == 200
    assert MomentNote.objects.get(at=120.0).note == "My own words."
    assert (
        MomentNote.objects.get(at=120.0).note_from["words"] == "from a proposed event"
    )
    told = post({"action": "accept_edit", "id": str(three.pk), "text": "   "})
    assert told.status_code == 400 and "Write the note" in told.json()["error"]
    got = post({"action": "dismiss", "id": str(three.pk)}).json()
    assert got["run"]["pending"] == 0
    three.refresh_from_db()
    assert three.state == "dismissed"
    assert post({"action": "accept", "id": str(three.pk)}).status_code == 404
    assert post({"action": "nothing"}).status_code == 404
    # All at once, and refused while the run is going.
    proposal(a_case, cam, at=400.0, text="Four.")
    proposal(a_case, cam, at=500.0, text="Five.")
    ProposalRun.objects.create(case=a_case, state="running")
    told = post({"action": "dismiss_all"})
    assert told.status_code == 409 and "still proposing" in told.json()["error"]
    ProposalRun.objects.filter(case=a_case).update(state="done")
    got = post({"action": "accept_all"}).json()
    assert got["said"] == "2 notes written." and got["run"]["pending"] == 0
    assert MomentNote.objects.count() == 3
    got = post({"action": "dismiss_all"}).json()
    assert got["said"] == "0 proposed events dismissed."
    assert Row.objects.filter(event="proposal accepted").count() == 4
    assert Row.objects.filter(event="proposal dismissed").count() == 1
    for row in Row.objects.all():
        assert "weapon" not in json.dumps(row.details).lower()


def test_the_run_reads_every_recording_and_keeps_clear_of_what_stands(
    person, a_case, monkeypatch
):
    settings_store.set_to("incidents_watch_phrases", "gun")
    settings_store.set_to("incidents_second_look", False)
    first = video(
        person,
        a_case,
        "BWC2-1",
        lines=((10.0, "Step out of the vehicle."), (30.0, "I got, I got gun.")),
    )
    second = video(person, a_case, "Call", lines=((5.0, "Stay in the car."),))
    video(person, a_case, "No words")
    # A note on the first recording at 10 s, and a dismissed proposal at 5 s
    # on the second: nothing is proposed within five seconds of either.
    from core import notes

    notes.set_note(Segment.objects.get(start=10.0), "Asked out.", by=person)
    proposals.dismiss(proposal(a_case, second, at=5.0, text="Told to stay."), by=person)
    # A proposal of an earlier case run waits; the new run replaces it.
    proposal(a_case, first, at=200.0, text="Stale.")
    asked = engine_answering(
        monkeypatch,
        [
            json.dumps(
                {
                    "events": [
                        {
                            "time": "00:00:12",
                            "end": "",
                            "text": "Out of the car",
                            "why": "near the note",
                            "rests_on": "Step out of the vehicle",
                        },
                        {
                            "time": "00:00:30",
                            "end": "",
                            "text": "A gun was mentioned",
                            "why": "A weapon changes the stop.",
                            "rests_on": "I got, I got gun",
                        },
                        {
                            "time": "00:00:50",
                            "end": "",
                            "text": "Hands were asked for",
                            "why": "matters",
                            "rests_on": "I got, I got gun",
                        },
                    ]
                }
            ),
            json.dumps(
                {
                    "events": [
                        {
                            "time": "00:00:07",
                            "end": "",
                            "text": "Told to stay, again",
                            "why": "near the dismissed",
                            "rests_on": "Stay in the car",
                        }
                    ]
                }
            ),
        ],
    )
    assert proposals.ask_for_run(a_case, by=person)
    run = ProposalRun.objects.get(case=a_case)
    assert run.state == "queued" and run.expectation["key"] == "case_events"
    assert proposals.ask_for_run(a_case, by=person)  # one run at a time
    proposals.propose_for_case(a_case.pk)
    run.refresh_from_db()
    assert run.state == "done" and run.read == 2 and run.watch == 1
    # One call per recording with words; the head says the recording's own
    # times and what the office noted on it.
    assert len(asked) == 2
    head = asked[0]["messages"][-1]["content"]
    assert "Recording BWC2-1 runs from 00:00:00 to 00:10:00" in head
    assert "00:00:10 the office's note: Asked out." in head
    assert "00:00:30 Watch phrase" in head
    kept = list(
        Proposal.objects.filter(state="waiting").order_by("recording__title", "at")
    )
    assert [(one.recording.title, one.at, one.source) for one in kept] == [
        ("BWC2-1", 30.0, "watch"),
        ("BWC2-1", 50.0, "assistant"),
    ]
    assert all(one.incident_id is None for one in kept)
    assert not Proposal.objects.filter(text="Stale.").exists()
    assert Proposal.objects.filter(state="dismissed").count() == 1
    assert run.found == 2 and run.full_at is not None
    words = proposals.run_json(a_case)
    assert words["words"].startswith("Proposed 2 events at ")
    assert "from 2 recordings, 1 from the watch phrases" in words["words"]
    assert words["never_read"] == 0 and words["pending"] == 2
    rows = list(Row.objects.filter(event="events proposed"))
    assert len(rows) == 1 and rows[0].details["whole_case"] is True
    assert rows[0].details["found"] == 2 and rows[0].details["watch_hits"] == 1
    call = Row.objects.get(event="AI assistant call")
    assert call.details["calls"] == 2 and call.object_type == "case"
    for row in Row.objects.all():
        assert "gun" not in json.dumps(row.details).lower()
    # A recording landed since is not yet read.
    late = video(person, a_case, "Late", lines=((1.0, "Later."),))
    assert proposals.run_json(a_case)["never_read"] == 1
    assert "Not yet read: Late." in proposals.run_json(a_case)["words"]
    assert late.transcript.created > run.full_at
    # With the assistant off the run is the search alone.
    settings_store.set_to("incidents_propose", False)
    run.state = ""
    run.save()
    asked.clear()
    assert proposals.ask_for_run(a_case, by=person)
    proposals.propose_for_case(a_case.pk)
    run.refresh_from_db()
    assert run.state == "done" and not asked and run.read == 3
    assert Proposal.objects.filter(state="waiting", source="watch").count() == 1
