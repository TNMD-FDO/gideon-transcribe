"""The voice plan's third release (ADR 0021, v1.140.0): the check and
Suggest names as one run, a Person's Also called list and its name rule,
the moot rows closed, and the pages' parts."""

import json
from pathlib import Path

import pytest
from core import (
    assistant,
    case_chat,
    engine,
    people,
    settings_store,
    speaker_check,
    viewer,
    vocabulary,
)
from core.assistant import SpeakerCheck, SpeakerCorrection, Suggestion, SuggestionRun
from core.audit import Row
from core.jobs import Segment
from core.models import User
from core.people import Person
from tests.helpers import signed_in
from tests.test_people import a_case, owner  # noqa: F401
from tests.test_people import a_recording as a_case_recording
from tests.test_prepare import a_recording, engine_answering
from tests.test_speaker_check import SKETCH, moves, switched_on

PASSWORD = "a-long-enough-password"
HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent


@pytest.fixture
def admin(db):
    return User.objects.create_local_admin("adm", PASSWORD)


def suggestions(*items):
    return json.dumps(
        {
            "suggestions": [
                {
                    "speaker": speaker,
                    "name": name,
                    "confidence": "high",
                    "line": line,
                    "kind": "name",
                    "quote": "",
                }
                for speaker, name, line in items
            ]
        }
    )


# The one run ------------------------------------------------------------------------


def test_the_check_suggests_the_names_in_the_same_run(
    admin, tmp_path, settings, client, monkeypatch
):
    """One job: the sketch, the moves, then the names, each its own engine
    call with its own audit row; the names counted on the check so the
    page's line says so. With Speaker suggestions off the run ends at the
    moves, as before."""
    switched_on()
    settings_store.set_to("suggestions_available", True)
    recording = a_recording(admin, tmp_path, settings)
    transcript = recording.transcript
    asked = engine_answering(
        monkeypatch,
        [
            SKETCH,
            moves((2, "Speaker 2", "Speaker 1", "the officer points")),
            suggestions(("Speaker 1", "Detective Ruiz", 1)),
        ],
    )
    check = SpeakerCheck.objects.create(transcript=transcript, asked_by=admin)
    speaker_check.run(check.pk)
    check.refresh_from_db()
    assert check.state == assistant.DONE and check.found == 1
    assert len(asked) == 3
    names = SuggestionRun.objects.get()
    assert names.state == assistant.DONE and names.asked_by_id == admin.pk
    assert names.found == 1
    assert Suggestion.objects.get().name == "Detective Ruiz"
    assert check.second_look["names"] == 1
    assert check.second_look["names_state"] == "done"
    features = sorted(
        row.details["feature"] for row in Row.objects.filter(event="AI assistant call")
    )
    assert features == ["speaker_check", "speaker_suggestions"]

    signed_in(client, admin)
    state = client.get(f"/recording/{recording.pk}/assistant").json()
    assert state["speaker_check"]["run"]["names"] == 1
    assert state["pending"][0]["form"] == ""

    # The names switched off: the run is the moves alone.
    settings_store.set_to("suggestions_available", False)
    engine_answering(
        monkeypatch, [SKETCH, moves((2, "Speaker 2", "Speaker 1", "again"))]
    )
    again = SpeakerCheck.objects.create(transcript=transcript, asked_by=admin)
    speaker_check.run(again.pk)
    again.refresh_from_db()
    assert again.state == assistant.DONE
    assert SuggestionRun.objects.count() == 1
    assert "names" not in again.second_look


# Also called ------------------------------------------------------------------------


def test_a_name_heard_reaches_the_person_through_also_called(owner, a_case):  # noqa: F811
    dana = Person.objects.create(case=a_case, name="Dana Reyes", also_called=["Mama"])
    recording = a_case_recording(owner, a_case)
    kept = [{"speaker": "Speaker 1", "name": "mama", "basis": "addressed"}]
    (one,) = assistant.through_also_called(kept, recording, set())
    assert (one["name"], one["form"]) == ("Dana Reyes", "mama")
    # The Person already named on this Transcript is not offered under a form.
    assert assistant.through_also_called(kept, recording, {"Dana Reyes"}) == []
    # A form two People share is withheld.
    Person.objects.create(case=a_case, name="Lee Ortiz", also_called=["Mama"])
    assert assistant.through_also_called(kept, recording, set()) == []
    # A name that is no form passes untouched; outside a Case nothing changes.
    plain = [{"speaker": "Speaker 1", "name": "Coach"}]
    assert assistant.through_also_called(plain, recording, set()) == plain
    assert dana.also_called == ["Mama"]


def test_suggest_names_keeps_the_form_as_the_reason(owner, a_case, monkeypatch):  # noqa: F811
    Person.objects.create(case=a_case, name="Dana Reyes", also_called=["Mama"])
    recording = a_case_recording(owner, a_case)
    transcript = recording.transcript
    Segment.objects.create(
        transcript=transcript,
        start=20.0,
        end=22.0,
        text="Thanks, Mama.",
        speaker="Speaker 2",
        speaker_label="SPEAKER_01",
    )
    settings_store.set_to("assistant_available", True)
    settings_store.set_to("suggestions_available", True)
    monkeypatch.setattr(engine, "is_reachable", lambda: True)
    monkeypatch.setattr(engine, "address", lambda: "http://gideon-generator:8000/v1")
    line = [
        one.number
        for one in __import__("core.prompts", fromlist=["lines_of"]).lines_of(
            transcript
        )
        if one.text == "Thanks, Mama."
    ][0]

    def complete(messages, **options):
        return {
            "text": suggestions(("Speaker 1", "Mama", line)),
            "finish_reason": "stop",
            "input_tokens": 1,
            "output_tokens": 1,
            "model": "the-model",
        }

    monkeypatch.setattr(engine, "complete", complete)
    run = SuggestionRun.objects.create(transcript=transcript, asked_by=owner)
    assistant.suggest_names(run.pk)
    found = Suggestion.objects.get()
    assert (found.speaker, found.name, found.form) == (
        "Speaker 1",
        "Dana Reyes",
        "Mama",
    )


def test_also_called_is_kept_and_read_everywhere(owner, a_case, client):  # noqa: F811
    dana = Person.objects.create(case=a_case, name="Dana Reyes", role="Client")
    vocabulary.set_person_spellings(
        dana, "dana rays", by=owner, called="Mama, Coach, dana reyes"
    )
    dana.refresh_from_db()
    # The Person's own name is never a form.
    assert dana.also_called == ["Mama", "Coach"]
    assert dana.also_heard_as == ["dana rays"]
    row = vocabulary.entries(a_case)[0]
    assert row["called"] == ["Mama", "Coach"] and row["shared"] == []
    # A form on two People is said to be shared.
    Person.objects.create(case=a_case, name="Lee Ortiz", also_called=["coach"])
    assert vocabulary.entries(a_case)[0]["shared"] == ["Coach"]
    assert vocabulary.shared_forms(a_case) == {"coach"}
    # To recognition, to Search, to Gideon.
    assert "Mama" in vocabulary.names_in(a_case)
    assert "Dana Reyes" in vocabulary.heard_as(a_case, ["mama"])
    assert "Dana Reyes (Client), also heard as dana rays, also called Mama, Coach" in (
        case_chat.people_line(a_case)
    )
    assert people.by_also_called(a_case)["mama"] == [dana]

    # The page saves both boxes in one change, with one audit row and no name.
    signed_in(client, owner)
    before = Row.objects.filter(event="case vocabulary changed").count()
    answer = client.post(
        f"/case/{a_case.pk}/vocabulary",
        {
            "action": "spellings",
            "kind": "person",
            "id": str(dana.pk),
            "spellings": "dana rays",
            "called": "Mama, Mum",
        },
    )
    assert answer.status_code == 302
    dana.refresh_from_db()
    assert dana.also_called == ["Mama", "Mum"]
    assert Row.objects.filter(event="case vocabulary changed").count() == before + 1
    assert "Mama" not in str(Row.objects.latest("at").details)
    page = client.get(f"/case/{a_case.pk}?tab=details").content.decode()
    assert "also called Mama, Mum" in page
    # Since v1.156.0 the nickname is typed on the Speakers tab's card; the
    # Names and places block reads it.
    tab = client.get(f"/case/{a_case.pk}?tab=speakers").content.decode()
    assert 'name="called"' in tab and "Also called, with commas" in tab


# The moot rows ----------------------------------------------------------------------


def test_a_hand_move_closes_the_proposals_it_made_moot_and_frees_the_vectors(
    admin, tmp_path, settings
):
    """A pending correction whose line changed hands since the run is closed
    as dismissed with no decider; with nothing pending the run's vectors go.
    Before this the row was left out of the page but stayed pending, and the
    vectors with it."""
    switched_on()
    recording = a_recording(admin, tmp_path, settings)
    transcript = recording.transcript
    line = transcript.segments.get(start=12.4)
    check = SpeakerCheck.objects.create(
        transcript=transcript, state=assistant.DONE, voices={"stretches": [1]}
    )
    moot = SpeakerCorrection.objects.create(
        transcript=transcript,
        segment=line,
        start=12.4,
        speaker_from="Speaker 2",
        speaker_to="Speaker 1",
    )
    assert speaker_check.live_rows(transcript) == [moot]
    assert viewer.move_line(transcript, line, "Speaker 3", by=admin) == 1
    moot.refresh_from_db()
    assert moot.state == SpeakerCorrection.DISMISSED
    assert moot.decided_by_id is None and moot.decided_at is not None
    assert moot.aside_why == "the line moved since the check"
    assert speaker_check.live_rows(transcript) == []
    assert speaker_check.score(transcript) == {"accepted": 0, "dismissed": 1}
    check.refresh_from_db()
    assert check.voices == {}


# The pages --------------------------------------------------------------------------


def test_the_pages_carry_the_release():
    template = (HERE / "templates" / "speakers-page.html").read_text(encoding="utf-8")
    # The old button's markup, not the words: "Check against the unit's
    # voices" (v1.146.0) begins with the same letters.
    assert "Run again" in template and ">Check again<" not in template
    assert 'id="sp-foot"' in template and 'class="sp-cast"' in template
    assert "The check also suggests names" in template
    script = (HERE / "static" / "speakers-page.js").read_text(encoding="utf-8")
    # The click fix: a row is found by its line number, never by counting
    # the column's children past the heads above it.
    assert "column.children[" not in script
    assert "function rowAt(index)" in script
    assert "It also suggested" in script
    strip = (HERE / "static" / "assistant.js").read_text(encoding="utf-8")
    assert "changes proposed" in strip and "another voice under" in strip
    assert "checking the speakers..." in strip
    css = (HERE / "static" / "app.css").read_text(encoding="utf-8")
    assert ".sp-cards .sp-cast { display: flex" in css
    assert ".sp-foot { display: flex" in css
    vocab = (HERE / "templates" / "case-vocabulary.html").read_text(encoding="utf-8")
    assert 'name="called"' not in vocab  # read-only there since v1.156.0
    speakers_tab = (HERE / "templates" / "case.html").read_text(encoding="utf-8")
    assert 'name="called"' in speakers_tab
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## v1.140.0" in changelog
    glossary = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    assert "**Also called**" in glossary and "v1.140.0" in glossary
