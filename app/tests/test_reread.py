"""The re-read after a name (v1.144.1; the drawing
phase-5-reread-after-a-name.html): the proposals catch up with a rename, a
merge, a Sounds like accepted and a suggestion accepted, the page is told
in counts, and an undo takes it back."""

import json
from pathlib import Path

import numpy as np
import pytest
from core import settings_store, speaker_check, voice_prints
from core.assistant import SpeakerCheck, SpeakerCorrection, Suggestion, VoiceMatch
from core.people import Person
from tests.helpers import signed_in
from tests.test_people import a_case as _a_case  # noqa: F401
from tests.test_people import a_recording
from tests.test_people import owner as _owner  # noqa: F401

HERE = Path(__file__).resolve().parents[1]


@pytest.fixture
def owner(_owner):  # noqa: F811
    return _owner


@pytest.fixture
def a_case(_a_case):  # noqa: F811
    return _a_case


def vec(seed: int) -> list[float]:
    arr = np.random.default_rng(seed).normal(size=192)
    return [round(float(x), 5) for x in arr / np.linalg.norm(arr)]


def lines_of(recording, speaker):
    return list(recording.transcript.segments.filter(speaker=speaker).order_by("start"))


def propose(recording, segment, from_, to, reason, source=SpeakerCorrection.WORDS):
    return SpeakerCorrection.objects.create(
        transcript=recording.transcript,
        segment=segment,
        start=segment.start,
        quote=segment.text[:120],
        speaker_from=from_,
        speaker_to=to,
        reason=reason,
        source=source,
    )


def test_a_rename_rewrites_the_reasons_closes_the_name_and_leaves_a_note(
    owner, a_case, client
):
    recording = a_recording(owner, a_case, speakers=("Speaker 1", "Speaker 2"))
    run = SpeakerCheck.objects.create(transcript=recording.transcript, state="done")
    two = lines_of(recording, "Speaker 2")[0]
    one = lines_of(recording, "Speaker 1")[0]
    # A proposes a line of Speaker 2 to Speaker 1; B the other way; both wait.
    a = propose(
        recording, two, "Speaker 2", "Speaker 1", "the voice sounds like Speaker 1"
    )
    b = propose(
        recording, one, "Speaker 1", "Speaker 2", "answers Speaker 1's question"
    )
    riley = Suggestion.objects.create(
        transcript=recording.transcript, speaker="Speaker 1", name="Riley", start=0.0
    )
    signed_in(client, owner)
    answer = client.post(
        f"/recording/{recording.pk}/speakers",
        data=json.dumps({"from": "Speaker 1", "to": "Dana Reyes"}),
        content_type="application/json",
    )
    assert answer.status_code == 200
    a.refresh_from_db()
    b.refresh_from_db()
    riley.refresh_from_db()
    assert (
        a.speaker_to == "Dana Reyes" and a.reason == "the voice sounds like Dana Reyes"
    )
    assert (
        b.speaker_from == "Dana Reyes" and b.reason == "answers Dana Reyes's question"
    )
    assert a.state == b.state == SpeakerCorrection.PENDING
    assert riley.state == Suggestion.CLOSED
    run.refresh_from_db()
    note = run.second_look["reread"]
    assert note["for"] == "Dana Reyes" and note["was"] == "Speaker 1"
    assert set(note["touched"]) == {str(a.pk), str(b.pk)} and note["settled"] == []
    assert note["closed"][0]["name"] == "Riley" and note["reread"] == 2
    # The page reads the note on the run and no settled rows.
    state = speaker_check.state_json(recording.transcript)
    assert state["run"]["voice_notes"]["reread"]["for"] == "Dana Reyes"
    assert state["settled"] == []
    # A label is never confused with a word inside another: "Speaker 10".
    assert speaker_check._relabel("Speaker 10 and Speaker 1", "Speaker 1", "Dana") == (
        "Speaker 10 and Dana"
    )


def test_a_merge_settles_the_proposal_it_fulfils_and_the_page_shows_it_in_place(
    owner, a_case, client
):
    recording = a_recording(owner, a_case, speakers=("Speaker 1", "Speaker 3"))
    SpeakerCheck.objects.create(transcript=recording.transcript, state="done")
    three = lines_of(recording, "Speaker 3")[0]
    c = propose(recording, three, "Speaker 3", "Speaker 1", "the same voice")
    signed_in(client, owner)
    # Speaker 1 is named first, then Speaker 3 is merged into the name.
    client.post(
        f"/recording/{recording.pk}/speakers",
        data=json.dumps({"from": "Speaker 1", "to": "Dana Reyes"}),
        content_type="application/json",
    )
    client.post(
        f"/recording/{recording.pk}/speakers",
        data=json.dumps({"from": "Speaker 3", "to": "Dana Reyes"}),
        content_type="application/json",
    )
    c.refresh_from_db()
    assert c.state == SpeakerCorrection.ACCEPTED and c.speaker_to == "Dana Reyes"
    state = speaker_check.state_json(recording.transcript)
    assert [one["id"] for one in state["settled"]] == [str(c.pk)]
    assert state["settled"][0]["settled_by"] == {
        "was": "Speaker 3",
        "now": "Dana Reyes",
    }
    assert state["settled"][0]["state"] == "accepted"
    assert state["pending"] == []
    # Undo of the merge is a name back: the proposal returns, the note goes.
    undo = client.post(f"/recording/{recording.pk}/speakers/undo")
    assert undo.status_code == 200
    c.refresh_from_db()
    assert c.state == SpeakerCorrection.PENDING and c.speaker_from == "Speaker 3"
    state = speaker_check.state_json(recording.transcript)
    assert "reread" not in (state["run"]["voice_notes"] or {})
    assert state["settled"] == []


def test_a_name_from_a_suggestion_now_makes_the_proposals_follow(owner, a_case, client):
    recording = a_recording(owner, a_case, speakers=("Speaker 1", "Speaker 2"))
    SpeakerCheck.objects.create(transcript=recording.transcript, state="done")
    two = lines_of(recording, "Speaker 2")[0]
    a = propose(
        recording, two, "Speaker 2", "Speaker 1", "the voice sounds like Speaker 1"
    )
    riley = Suggestion.objects.create(
        transcript=recording.transcript,
        speaker="Speaker 1",
        name="Riley Park",
        start=0.0,
    )
    signed_in(client, owner)
    assert client.post(f"/suggestion/{riley.pk}/accept").json()["ok"]
    a.refresh_from_db()
    assert (
        a.speaker_to == "Riley Park" and a.reason == "the voice sounds like Riley Park"
    )
    riley.refresh_from_db()
    assert riley.state == Suggestion.ACCEPTED


def test_the_prints_follow_the_name_and_the_new_match_is_marked(owner, a_case, client):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("remember_voices", True)
    try:
        recording = a_recording(owner, a_case, speakers=("Speaker 1", "Speaker 2"))
        run = SpeakerCheck.objects.create(
            transcript=recording.transcript,
            state="done",
            prints={
                "Speaker 1": {"vector": vec(1), "lines": 5, "seconds": 20.0},
                "Speaker 2": {"vector": vec(1), "lines": 5, "seconds": 20.0},
            },
        )
        signed_in(client, owner)
        client.post(
            f"/recording/{recording.pk}/speakers",
            data=json.dumps({"from": "Speaker 1", "to": "Dana Reyes"}),
            content_type="application/json",
        )
        run.refresh_from_db()
        assert set(run.prints) == {"Dana Reyes", "Speaker 2"}
        dana = Person.objects.get(case=a_case, name="Dana Reyes")
        assert dana.voice_print and str(recording.pk) in dana.voice_print["parts"]
        # Speaker 2 has the same voice: a match born of the print just taught.
        rows = list(
            VoiceMatch.objects.filter(transcript=recording.transcript, state="pending")
        )
        assert [one.speaker for one in rows] == ["Speaker 2"] and rows[0].person == dana
        note = run.second_look["reread"]
        assert note["new_matches"] == [rows[0].pk]
        shown = voice_prints.rows_for(recording.transcript)["matches"][0]
        assert shown["people"][0]["new"] is True
        heard = shown["people"][0]["heard"]
        assert heard and heard[-1]["here"] is True
    finally:
        settings_store.set_to("remember_voices", False)


def test_the_page_carries_the_reread():
    page = (HERE / "static" / "speakers-page.js").read_text(encoding="utf-8")
    assert "function drawRereadLine" in page and "function rereadPill" in page
    assert "settled: this line is" in page and "undo-name" in page
    assert "Re-reading " in page and "closed: this speaker is" in page
    assert "new: their print was just taught from this call" in page
    template = (HERE / "templates" / "speakers-page.html").read_text(encoding="utf-8")
    assert 'id="reread-line"' in template
    strip = (HERE / "static" / "assistant.js").read_text(encoding="utf-8")
    assert "re-read for " in strip
    css = (HERE / "static" / "app.css").read_text(encoding="utf-8")
    assert ".sp-corrections .reread" in css and ".sp-read .seg.change.settled" in css


def test_unlearn_takes_the_proposals_back_to_the_label(owner, a_case, client):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("remember_voices", True)
    try:
        by_voice = a_recording(owner, a_case, speakers=("Dana Reyes", "Speaker 2"))
        SpeakerCheck.objects.create(transcript=by_voice.transcript, state="done")
        two = lines_of(by_voice, "Speaker 2")[0]
        a = propose(
            by_voice, two, "Speaker 2", "Dana Reyes", "the voice sounds like Dana Reyes"
        )
        dana = Person.objects.create(
            case=a_case,
            name="Dana Reyes",
            voice_print={
                "vector": vec(1),
                "scope": "case",
                "parts": {
                    str(by_voice.pk): {
                        "vector": vec(1),
                        "label": "Speaker 1",
                        "lines": 2,
                        "seconds": 20.0,
                        "how": voice_prints.VOICE,
                        "by": "pat",
                        "at": "2026-10-20T10:00:00",
                    }
                },
            },
        )
        voice_prints.unlearn(dana, by=owner)
        a.refresh_from_db()
        assert a.state == SpeakerCorrection.PENDING
        assert a.speaker_to.startswith("Speaker") and a.speaker_to != "Speaker 2"
        assert a.reason == "the voice sounds like " + a.speaker_to
    finally:
        settings_store.set_to("remember_voices", False)
