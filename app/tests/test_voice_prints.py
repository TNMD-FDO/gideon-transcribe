"""Voice prints (Phase 5 chapter 2 in force; ADR 0021 decision 6; the voice
plan's V4, v1.144.0): a print learnt from a name, the matches rated by the
weakest link, a conflict, Accept and Not them on the card, Unlearn, the
Admin's switch going off, the Case tab's Voice column, and nothing of a
voice leaving the building."""

import json
from pathlib import Path

import numpy as np
import pytest
from core import settings_store, speaker_check, voice_prints
from core.assistant import SpeakerCheck, VoiceMatch
from core.people import Person
from tests.helpers import signed_in
from tests.test_people import a_case as _a_case  # noqa: F401
from tests.test_people import a_recording
from tests.test_people import owner as _owner  # noqa: F401

HERE = Path(__file__).resolve().parents[1]


def vec(seed: int, dims: int = 192) -> list[float]:
    arr = np.random.default_rng(seed).normal(size=dims)
    return [round(float(x), 5) for x in arr / np.linalg.norm(arr)]


def mixed(a: int, b: int, weight: float = 0.7) -> list[float]:
    arr = weight * np.asarray(vec(a)) + (1 - weight) * np.asarray(vec(b))
    return [round(float(x), 5) for x in arr / np.linalg.norm(arr)]


def label_print(seed: int, seconds: float = 20.0) -> dict:
    return {"vector": vec(seed), "lines": 5, "seconds": seconds}


def a_check(recording, prints: dict, midpoint=None) -> SpeakerCheck:
    look = {"calibration": {"midpoint": midpoint}} if midpoint else {}
    return SpeakerCheck.objects.create(
        transcript=recording.transcript, state="done", prints=prints, second_look=look
    )


def part(seed: int, how: str = voice_prints.HAND, label: str = "Speaker 1") -> dict:
    return {
        "vector": vec(seed),
        "label": label,
        "lines": 5,
        "seconds": 20.0,
        "how": how,
        "by": "pat",
        "at": "2026-10-20T10:00:00",
    }


def a_print(*parts) -> dict:
    kept = {"vector": None, "parts": dict(parts), "scope": "case"}
    vectors = [np.asarray(one["vector"]) for one in kept["parts"].values()]
    mean = np.stack(vectors).mean(axis=0)
    kept["vector"] = [round(float(x), 5) for x in mean / np.linalg.norm(mean)]
    return kept


@pytest.fixture
def owner(_owner):  # noqa: F811
    return _owner


@pytest.fixture
def a_case(_a_case):  # noqa: F811
    return _a_case


@pytest.fixture
def remembering(db):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("remember_voices", True)
    yield
    settings_store.set_to("remember_voices", False)


# Learning ----------------------------------------------------------------------------


def test_a_name_teaches_the_print_from_the_runs_kept_label(
    owner,
    a_case,
    remembering,
):
    recording = a_recording(owner, a_case)
    a_check(recording, {"Speaker 1": label_print(1)})
    dana = Person.objects.create(case=a_case, name="Dana Reyes", added_by=owner)
    assert voice_prints.learn_on_name(recording, "Speaker 1", "Dana Reyes", by=owner)
    dana.refresh_from_db()
    kept = dana.voice_print
    assert len(kept["vector"]) == 192 and kept["scope"] == "case"
    one = kept["parts"][str(recording.pk)]
    assert one["how"] == voice_prints.HAND and one["by"] == owner.username
    assert one["label"] == "Speaker 1"
    # A second recording refines it: two parts, the mean of both.
    other = a_recording(owner, a_case, title="a second call")
    a_check(other, {"Speaker 2": label_print(1)})
    assert voice_prints.learn_on_name(other, "Speaker 2", "Dana Reyes", by=owner)
    dana.refresh_from_db()
    assert len(dana.voice_print["parts"]) == 2
    # Undo of a name: the print forgets that recording.
    assert voice_prints.forget_recording(other, "Dana Reyes")
    dana.refresh_from_db()
    assert list(dana.voice_print["parts"]) == [str(recording.pk)]


def test_nothing_is_learnt_with_the_switch_off_or_outside_a_case(owner, a_case):
    settings_store.set_to("folder_management", True)
    recording = a_recording(owner, a_case)
    a_check(recording, {"Speaker 1": label_print(1)})
    Person.objects.create(case=a_case, name="Dana Reyes", added_by=owner)
    assert not voice_prints.learn_on_name(
        recording, "Speaker 1", "Dana Reyes", by=owner
    )
    assert Person.objects.get(name="Dana Reyes").voice_print is None
    assert not voice_prints.on()


def test_a_run_keeps_one_vector_per_label_only_while_remembering(
    owner,
    a_case,
    remembering,
):
    class FakeJudge:
        centroids = {
            (1, "Speaker 1"): np.asarray(vec(1)),
            (1, "Call system"): np.asarray(vec(3)),
        }
        members = {(1, "Speaker 1"): ["1", "2", "3"], (1, "Call system"): ["4"]}
        stretches = {
            "1": {"net": 4.0},
            "2": {"net": 3.0},
            "3": {"net": 5.5},
            "4": {"net": 9.0},
        }

    recording = a_recording(owner, a_case)
    check = a_check(recording, {})
    voice_prints.keep_prints(check, FakeJudge())
    assert list(check.prints) == ["Speaker 1"]
    assert check.prints["Speaker 1"]["lines"] == 3
    assert check.prints["Speaker 1"]["seconds"] == 12.5
    settings_store.set_to("remember_voices", False)
    voice_prints.keep_prints(check, FakeJudge())
    assert check.prints == {}


# Matching ----------------------------------------------------------------------------


def test_matches_are_rated_by_the_weakest_link_and_two_people_are_a_conflict(
    owner,
    a_case,
    remembering,
):
    first = a_recording(
        owner, a_case, title="Call 1", speakers=("Dana Reyes", "Tom Hale")
    )
    second = a_recording(
        owner, a_case, title="Call 2", speakers=("Dana Reyes", "Speaker 2")
    )
    dana = Person.objects.create(
        case=a_case,
        name="Dana Reyes",
        role="Client",
        voice_print=a_print(
            (str(first.pk), part(1)), (str(second.pk), part(1, voice_prints.VOICE))
        ),
    )
    tom = Person.objects.create(
        case=a_case, name="Tom Hale", voice_print=a_print((str(first.pk), part(2)))
    )
    recording = a_recording(
        owner, a_case, title="Call 3", speakers=("Speaker 1", "Speaker 2")
    )
    check = a_check(
        recording,
        {
            "Speaker 1": label_print(1),  # Dana's voice, heard long: high
            "Speaker 2": {
                "vector": mixed(1, 2, 0.6),
                "lines": 4,
                "seconds": 20.0,
            },  # both
            "Speaker 3": label_print(2, seconds=6.0),  # Tom's voice, heard briefly
            "Speaker 4": label_print(9),  # nobody
        },
    )
    made = voice_prints.match(check)
    rows = {
        (one.speaker, one.person.name): one
        for one in VoiceMatch.objects.filter(transcript=recording.transcript)
    }
    assert made == len(rows) >= 4
    assert rows[("Speaker 1", "Dana Reyes")].rating == voice_prints.HIGH
    # A print from one recording rates medium at best, whatever the score.
    assert rows[("Speaker 3", "Tom Hale")].rating == voice_prints.MEDIUM
    assert ("Speaker 4", "Dana Reyes") not in rows and (
        "Speaker 4",
        "Tom Hale",
    ) not in rows
    shown = voice_prints.rows_for(recording.transcript)
    kinds = {one["speaker"]: one["kind"] for one in shown["matches"]}
    assert kinds["Speaker 1"] == "match" and kinds["Speaker 2"] == "conflict"
    conflict = next(one for one in shown["matches"] if one["speaker"] == "Speaker 2")
    assert {one["name"] for one in conflict["people"]} == {"Dana Reyes", "Tom Hale"}
    # Where the voice can be heard: the recordings that taught the print.
    heard = next(one for one in shown["matches"] if one["speaker"] == "Speaker 1")
    assert {one["title"] for one in heard["people"][0]["heard"]} == {"Call 1", "Call 2"}
    assert heard["people"][0]["recordings"] == 2
    # Only a single match feeds the picker's pill.
    assert voice_prints.suggested_names(recording.transcript) == {
        "Speaker 1": "Dana Reyes",
        "Speaker 3": "Tom Hale",
    }
    # A second run replaces the waiting rows.
    voice_prints.match(check)
    assert VoiceMatch.objects.filter(
        transcript=recording.transcript, state=VoiceMatch.PENDING
    ).count() == len(rows)
    assert dana.pk and tom.pk


def test_accept_names_the_speaker_and_teaches_the_print_and_a_conflict_settles(
    owner,
    a_case,
    remembering,
    client,
):
    first = a_recording(
        owner, a_case, title="Call 1", speakers=("Dana Reyes", "Tom Hale")
    )
    dana = Person.objects.create(
        case=a_case, name="Dana Reyes", voice_print=a_print((str(first.pk), part(1)))
    )
    tom = Person.objects.create(
        case=a_case, name="Tom Hale", voice_print=a_print((str(first.pk), part(2)))
    )
    recording = a_recording(
        owner, a_case, title="Call 3", speakers=("Speaker 1", "Speaker 2")
    )
    check = a_check(
        recording,
        {"Speaker 1": {"vector": mixed(1, 2, 0.6), "lines": 4, "seconds": 20.0}},
    )
    voice_prints.match(check)
    rows = {
        one.person.name: one
        for one in VoiceMatch.objects.filter(transcript=recording.transcript)
    }
    assert set(rows) == {"Dana Reyes", "Tom Hale"}
    signed_in(client, owner)
    answer = client.post(f"/voice-match/{rows['Dana Reyes'].pk}/accept").json()
    assert answer["ok"] and answer["made"] == "Dana Reyes" and answer["changed"] == 2
    assert not recording.transcript.segments.filter(speaker="Speaker 1").exists()
    assert recording.transcript.segments.filter(speaker="Dana Reyes").count() == 2
    dana.refresh_from_db()
    tom.refresh_from_db()
    taught = dana.voice_print["parts"][str(recording.pk)]
    assert taught["how"] == voice_prints.VOICE and taught["label"] == "Speaker 1"
    assert str(recording.pk) not in tom.voice_print["parts"]
    rows["Dana Reyes"].refresh_from_db()
    rows["Tom Hale"].refresh_from_db()
    assert rows["Dana Reyes"].state == VoiceMatch.ACCEPTED
    assert rows["Tom Hale"].state == VoiceMatch.WITHDRAWN
    # Undo is the viewer's: the change is on the transcript's list.
    recording.transcript.refresh_from_db()
    last = recording.transcript.speaker_changes[-1]
    assert last["from"] == "Speaker 1" and last["to"] == "Dana Reyes"
    assert last["voice_match"] == rows["Dana Reyes"].pk
    # Not them: a dismissal teaches nothing and counts towards the call-out.
    again = a_check(recording, {"Speaker 2": label_print(2)})
    voice_prints.match(again)
    row = VoiceMatch.objects.get(
        transcript=recording.transcript, state=VoiceMatch.PENDING
    )
    assert client.post(f"/voice-match/{row.pk}/dismiss").json()["ok"]
    tom.refresh_from_db()
    assert str(recording.pk) not in tom.voice_print["parts"]
    assert voice_prints.dismissed_lately(tom) == 1
    # The state the page reads carries the matches and the switch.
    state = speaker_check.state_json(recording.transcript)
    assert state["remember_voices"] is True and state["voice_matches"]["matches"] == []


# Unlearn -----------------------------------------------------------------------------


def test_unlearn_returns_the_voice_named_speakers_marks_them_and_keeps_the_hand_named(
    owner,
    a_case,
    remembering,
    client,
):
    by_hand = a_recording(
        owner, a_case, title="Call 1", speakers=("Dana Reyes", "Speaker 2")
    )
    by_voice = a_recording(
        owner, a_case, title="Call 2", speakers=("Dana Reyes", "Speaker 2")
    )
    waiting = a_recording(
        owner, a_case, title="Call 3", speakers=("Speaker 1", "Speaker 2")
    )
    dana = Person.objects.create(
        case=a_case,
        name="Dana Reyes",
        voice_print=a_print(
            (str(by_hand.pk), part(1)),
            (str(by_voice.pk), part(1, voice_prints.VOICE, label="Speaker 1")),
        ),
    )
    VoiceMatch.objects.create(
        transcript=waiting.transcript, speaker="Speaker 1", person=dana, rating="high"
    )
    preview = voice_prints.unlearn_preview(dana)
    assert preview == {"returned": ["Call 2"], "kept": ["Call 1"], "waiting": 1}
    signed_in(client, owner)
    answer = client.post(f"/person/{dana.pk}", {"action": "unlearn"})
    assert answer.status_code == 302
    dana.refresh_from_db()
    assert dana.voice_print is None and dana.voice_unlearnt_at is not None
    assert dana.voice_unlearnt_by == owner.username
    # By voice: back to its label and marked; by hand: stays.
    assert not by_voice.transcript.segments.filter(speaker="Dana Reyes").exists()
    assert by_hand.transcript.segments.filter(speaker="Dana Reyes").count() == 2
    mark = VoiceMatch.objects.get(
        transcript=by_voice.transcript, state=VoiceMatch.UNLEARNT
    )
    assert mark.speaker.startswith("Speaker") and mark.person_id == dana.pk
    assert voice_prints.rows_for(by_voice.transcript)["unlearnt"] == [
        {"speaker": mark.speaker, "person": "Dana Reyes"}
    ]
    assert (
        VoiceMatch.objects.get(transcript=waiting.transcript, rating="high").state
        == VoiceMatch.WITHDRAWN
    )
    body = client.get(f"/case/{a_case.pk}?tab=speakers").content.decode()
    assert "voice is unlearnt" in body and "voice unlearnt" in body


def test_the_switch_off_forgets_every_print_and_stamps_the_case(
    owner,
    a_case,
    remembering,
):
    first = a_recording(
        owner, a_case, title="Call 1", speakers=("Dana Reyes", "Speaker 2")
    )
    dana = Person.objects.create(
        case=a_case, name="Dana Reyes", voice_print=a_print((str(first.pk), part(1)))
    )
    check = a_check(first, {"Speaker 2": label_print(2)})
    VoiceMatch.objects.create(
        transcript=first.transcript, speaker="Speaker 2", person=dana, run=check
    )
    settings_store.set_to("remember_voices", False)
    dana.refresh_from_db()
    check.refresh_from_db()
    a_case.refresh_from_db()
    assert dana.voice_print is None and check.prints == {}
    assert a_case.voices_forgotten_at is not None
    assert VoiceMatch.objects.get(speaker="Speaker 2").state == VoiceMatch.WITHDRAWN
    assert not voice_prints.on()
    # Learnt again, the stamp goes.
    settings_store.set_to("remember_voices", True)
    a_check(first, {"Speaker 2": label_print(2)})
    Person.objects.create(case=a_case, name="Tom Hale")
    assert voice_prints.learn_on_name(first, "Speaker 2", "Tom Hale", by=owner)
    a_case.refresh_from_db()
    assert a_case.voices_forgotten_at is None


# The tab and the words ----------------------------------------------------------------


def test_the_case_tab_shows_the_voice_column_the_chain_and_the_counts(
    owner,
    a_case,
    remembering,
    client,
):
    first = a_recording(
        owner, a_case, title="Call 1", speakers=("Dana Reyes", "Speaker 2")
    )
    second = a_recording(
        owner, a_case, title="Call 2", speakers=("Dana Reyes", "Speaker 2")
    )
    waiting = a_recording(
        owner, a_case, title="Call 3", speakers=("Speaker 1", "Speaker 2")
    )
    dana = Person.objects.create(
        case=a_case,
        name="Dana Reyes",
        role="Client",
        voice_print=a_print(
            (str(first.pk), part(1)), (str(second.pk), part(1, voice_prints.VOICE))
        ),
    )
    Person.objects.create(case=a_case, name="Lee Ortiz")
    VoiceMatch.objects.create(
        transcript=waiting.transcript, speaker="Speaker 1", person=dana, rating="high"
    )
    signed_in(client, owner)
    body = client.get(f"/case/{a_case.pk}?tab=speakers").content.decode()
    # The tab as cards (v1.151.0): a card per person, the voice line on it,
    # the needs strip pointing at the call where the match is decided.
    assert 'class="person-card' in body and 'class="needs"' in body
    assert "1 sounds like" in body and "Something waiting 1" in body
    assert "print from 2 recordings" in body and "hear them" in body
    assert 'data-preview-person="Dana Reyes"' in body
    assert "Named by hand on Call 1" in body and "Matched by voice on Call 2" in body
    assert "1 call sounds like them, waiting" in body
    assert f"/recording/{waiting.pk}/speakers?pick=Speaker%201" in body
    assert "Unlearn their voice" in body and "Unlearn Dana Reyes's voice?" in body
    assert "no print yet" in body
    assert "Decided so far in this case" in body and "Sounds like, per person" in body
    assert "Voices are remembered for this case: 1 person has a voice print" in body
    # The tab never carries Accept, and nothing of a voice leaves: no vector.
    assert "match-accept" not in body and '"vector"' not in body
    for number in dana.voice_print["vector"][:3]:
        assert str(number) not in body
    # Nor through the picker's answer or the page's state.
    offer = client.get(f"/recording/{waiting.pk}/picker").content.decode()
    state = client.get(f"/recording/{waiting.pk}/assistant").content.decode()
    for text in (offer, state):
        assert "vector" not in text
    assert "Sounds like" not in offer


def test_the_pages_carry_sounds_like():
    page = (HERE / "static" / "speakers-page.js").read_text(encoding="utf-8")
    assert "function drawVoiceMatches" in page and "Sounds like two people" in page
    assert "match-accept" in page and "side-not" in page
    assert "the print forgets this call" in page
    template = (HERE / "templates" / "speakers-page.html").read_text(encoding="utf-8")
    assert 'class="sounds-box" hidden' in template
    case = (HERE / "templates" / "case.html").read_text(encoding="utf-8")
    assert "Unlearn their voice" in case and "voices_forgotten_at" not in case
    assert "data-preview-recording" in case and "Decided so far in this case" in case
    strip = (HERE / "static" / "assistant.js").read_text(encoding="utf-8")
    assert "sound like someone" in strip
    css = (HERE / "static" / "app.css").read_text(encoding="utf-8")
    assert ".sp-card .sounds.alarm" in css and ".tbl td .voice" in css
    tray = (HERE / "templates" / "panel" / "base.html").read_text(encoding="utf-8")
    assert "row.note" in tray


def test_the_setting_is_in_the_catalogue_and_the_tray_says_what_off_deletes(
    owner,
    a_case,
    db,
):
    from core import panel

    known = settings_store.definition("remember_voices")
    assert known.default is False and known.needs == "folder_management"
    catalogue = (
        HERE.parent / "docs" / "spec" / "ADMIN-SETTINGS-CATALOGUE.md"
    ).read_text(encoding="utf-8")
    assert "| Remember voices across a case |" in catalogue and "v1.144.0" in catalogue
    settings_store.set_to("folder_management", True)
    first = a_recording(
        owner, a_case, title="Call 1", speakers=("Dana Reyes", "Speaker 2")
    )
    Person.objects.create(
        case=a_case, name="Dana Reyes", voice_print=a_print((str(first.pk), part(1)))
    )
    rows = panel.tray_rows({"remember_voices": False})
    assert rows[0]["note"].startswith(
        "Off deletes every voice print the office holds: 1 person across 1 case."
    )
    assert panel.tray_rows({"remember_voices": True})[0]["note"] == ""


def test_the_state_answer_has_no_vector(owner, a_case, remembering, client):
    recording = a_recording(owner, a_case)
    a_check(recording, {"Speaker 1": label_print(1)})
    signed_in(client, owner)
    text = json.dumps(speaker_check.state_json(recording.transcript))
    assert "vector" not in text and "prints" not in text


def test_a_match_across_kinds_rates_medium_at_most_and_says_so(
    owner, a_case, remembering
):
    """v1.150.0: a print taught on body-camera recordings matched on a jail
    call is medium at most, carries the kinds it was taught on and one
    sentence of caution; on an untyped recording, or from untyped
    recordings, nothing is called out and the rating stands."""
    first = a_recording(owner, a_case, title="Cam 1", speakers=("Dana Reyes", "Tom"))
    second = a_recording(owner, a_case, title="Cam 2", speakers=("Dana Reyes", "X"))
    for one in (first, second):
        one.recording_type = "Body camera"
        one.save(update_fields=["recording_type"])
    dana = Person.objects.create(
        case=a_case,
        name="Dana Reyes",
        role="Officer",
        voice_print=a_print((str(first.pk), part(1)), (str(second.pk), part(1))),
    )
    assert voice_prints.kinds_taught(dana) == ["Body camera"]
    call = a_recording(owner, a_case, title="Call 3", speakers=("Speaker 1", "Y"))
    call.recording_type = "Jail call"
    call.save(update_fields=["recording_type"])
    assert voice_prints.cross_kind(["Body camera"], call)
    assert not voice_prints.cross_kind([], call)
    voice_prints.match(a_check(call, {"Speaker 1": label_print(1)}))
    row = VoiceMatch.objects.get(transcript=call.transcript, speaker="Speaker 1")
    assert row.rating == voice_prints.MEDIUM  # the voice itself scores high
    shown = voice_prints.rows_for(call.transcript)["matches"][0]["people"][0]
    assert shown["cross_kind"] and shown["kinds"] == ["Body camera"]
    assert shown["rating"] == "medium"
    assert "taught on a Body camera; this is a Jail call" in shown["caution"]
    assert "medium at most" in shown["caution"]
    # Untyped recording: not judged, the rating stands.
    untyped = a_recording(owner, a_case, title="Call 4", speakers=("Speaker 1", "Z"))
    voice_prints.match(a_check(untyped, {"Speaker 1": label_print(1)}))
    row = VoiceMatch.objects.get(transcript=untyped.transcript, speaker="Speaker 1")
    assert row.rating == voice_prints.HIGH
    shown = voice_prints.rows_for(untyped.transcript)["matches"][0]["people"][0]
    assert not shown["cross_kind"] and shown["caution"] == ""
    # Same kind: the rating stands.
    same = a_recording(owner, a_case, title="Cam 3", speakers=("Speaker 1", "Q"))
    same.recording_type = "body camera"
    same.save(update_fields=["recording_type"])
    assert not voice_prints.cross_kind(["Body camera"], same)
    # A row rated high before this release shows medium when it crosses.
    row = VoiceMatch.objects.get(transcript=call.transcript, speaker="Speaker 1")
    row.rating = voice_prints.HIGH
    row.save(update_fields=["rating"])
    shown = voice_prints.rows_for(call.transcript)["matches"][0]["people"][0]
    assert shown["rating"] == "medium"
    # Both pages carry the caution and the guided page folds weak conflicts.
    guided = (HERE / "static" / "speakers-guided.js").read_text(encoding="utf-8")
    assert "person.caution" in guided and "weak matches in conflict" in guided
    assert "sg-weak" in guided and "function choiceRow(" in guided
    assert '(one.kind === "case" && !one.weak) || one.kind === "book"' in guided
    classic = (HERE / "static" / "speakers-page.js").read_text(encoding="utf-8")
    assert "function cautionOf(" in classic and "person.cross_kind" in classic
    css = (HERE / "static" / "app.css").read_text(encoding="utf-8")
    assert ".sg-weak summary" in css
