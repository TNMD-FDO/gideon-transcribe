"""The Call system (ADR 0021, the voice plan's first release, v1.138.0): the
phone system's recorded voice as a Speaker of its own on a jail call, found
by the Admin's phrase list or by being heard on both Sides; never a person,
never renamed or merged, never seen by the Speaker check or by Suggest
names, never a Person in a Case, left alone by the side rule, grey on the
pages, said for what it is in the exports and the memo. Off by default.
"""

from __future__ import annotations

import json

import pytest
from core import (
    assistant,
    call_system,
    people,
    prompts,
    settings_store,
    speaker_check,
    vocabulary,
)
from core.cases import Case
from core.jobs import Segment
from core.models import User
from core.queue import BOTH_SIDES
from core.recordings import Side
from tests.helpers import signed_in
from tests.test_prepare import a_recording

PASSWORD = "a-long-enough-password"

LINES = (
    (
        0.0,
        "Speaker 1",
        "This call is from a correctional facility and may be monitored and recorded.",
    ),
    (6.0, "Speaker 1", "To accept this call, press one."),
    (12.0, "Speaker 1", "Hello?"),
    (14.0, "Speaker 2", "Hey, it's me. Can you hear me?"),
    (20.0, "Speaker 1", "Yeah. What did she say about Friday?"),
    (880.0, "Speaker 1", "You have one minute remaining."),
)


@pytest.fixture
def admin(db):
    return User.objects.create_local_admin("adm", PASSWORD)


def a_call(
    person, tmp_path, settings, *, kind="Jail call", case=None, two_channel=False
):
    recording = a_recording(
        person, tmp_path, settings, case=case, title="Call", video=False
    )
    recording.recording_type = kind
    recording.is_two_channel_call = two_channel
    recording.save(update_fields=["recording_type", "is_two_channel_call"])
    transcript = recording.transcript
    transcript.segments.all().delete()
    for start, speaker, text in LINES:
        Segment.objects.create(
            transcript=transcript,
            start=start,
            end=start + 4,
            text=text,
            speaker=speaker,
            speaker_label=speaker.upper().replace(" ", "_"),
        )
    return recording


def test_shipped_off_and_the_list_shipped(db):
    assert settings_store.DEFINITIONS["call_system_available"].default is False
    phrases = settings_store.DEFINITIONS["call_system_phrases"]
    assert phrases.needs == "call_system_available"
    assert "to accept this call" in phrases.default
    assert "you have one minute remaining" in phrases.default


def test_off_marks_nothing(admin, tmp_path, settings):
    recording = a_call(admin, tmp_path, settings)
    assert call_system.mark(recording.transcript) == 0
    assert not recording.transcript.segments.filter(speaker=call_system.NAME).exists()


def test_on_a_jail_call_the_phrases_are_the_systems(admin, tmp_path, settings):
    settings_store.set_to("call_system_available", True)
    recording = a_call(admin, tmp_path, settings)
    assert call_system.mark(recording.transcript) == 3
    marked = list(
        recording.transcript.segments.filter(speaker=call_system.NAME)
        .order_by("start")
        .values_list("start", flat=True)
    )
    assert marked == [0.0, 6.0, 880.0]
    # The words, the times and the engine's own label are untouched.
    first = recording.transcript.segments.get(start=0.0)
    assert first.speaker_label == "SPEAKER_1"
    assert first.text.startswith("This call is from")
    # The party's lines keep their Speaker.
    assert recording.transcript.segments.get(start=12.0).speaker == "Speaker 1"
    recording.transcript.refresh_from_db()
    assert recording.transcript.provenance["call_system"]["lines"] == 3


def test_a_recording_that_is_not_a_call_is_left_alone(admin, tmp_path, settings):
    settings_store.set_to("call_system_available", True)
    recording = a_call(admin, tmp_path, settings, kind="Body camera")
    assert call_system.mark(recording.transcript) == 0


def test_a_two_channel_call_qualifies_by_itself_and_the_twin_is_the_systems(
    admin, tmp_path, settings
):
    settings_store.set_to("call_system_available", True)
    recording = a_call(admin, tmp_path, settings, kind="", two_channel=True)
    both = recording.transcript.segments.get(start=12.0)
    both.speaker = BOTH_SIDES
    both.text = "Welcome. Please hold."
    both.save()
    assert call_system.mark(recording.transcript) == 4
    assert recording.transcript.segments.get(start=12.0).speaker == call_system.NAME


def test_the_phrases_are_matched_as_words(admin, tmp_path, settings):
    settings_store.set_to("call_system_available", True)
    settings_store.set_to("call_system_phrases", "Please hold\nYour call is important")
    recording = a_call(admin, tmp_path, settings)
    line = recording.transcript.segments.get(start=14.0)
    line.text = "PLEASE, hold! I'm getting the paper."
    line.save()
    assert call_system.mark(recording.transcript) == 1
    assert recording.transcript.segments.get(start=14.0).speaker == call_system.NAME


def test_the_check_and_the_names_never_see_it(admin, tmp_path, settings):
    settings_store.set_to("call_system_available", True)
    recording = a_call(admin, tmp_path, settings)
    call_system.mark(recording.transcript)
    assert speaker_check.speakers_of(recording.transcript) == ["Speaker 1", "Speaker 2"]
    assert call_system.NAME not in assistant.unnamed_speakers(recording.transcript)
    shown = prompts.lines_of(recording.transcript, without_system=True)
    assert len(shown) == 3
    assert all(not call_system.is_system(line.speaker) for line in shown)
    # The memo and the chat still read every line, the system's among them.
    assert len(prompts.lines_of(recording.transcript)) == 6


def test_never_a_person_and_the_side_rule_names_the_party(admin, tmp_path, settings):
    settings_store.set_to("folder_management", True)
    case = Case.objects.create(name="Calls", owner=admin)
    settings_store.set_to("call_system_available", True)
    recording = a_call(admin, tmp_path, settings, case=case, kind="", two_channel=True)
    side = Side.objects.create(
        recording=recording, number=1, kind=Side.CHANNEL, name="Side 1"
    )
    recording.transcript.segments.update(side=side, speaker="Side 1")
    call_system.mark(recording.transcript)
    assert (
        people.on_named(
            recording, call_system.NAME, by=admin, how="named in the viewer"
        )
        is None
    )
    assert people.moved_in(recording, by=admin) == 0
    person, _ = people.join_or_create(
        case, "Dana Reyes", by=admin, how="typed on the tab"
    )
    vocabulary.set_side_rule(case, 1, person, by=admin)
    assert recording.transcript.segments.filter(speaker="Dana Reyes").count() == 3
    assert recording.transcript.segments.filter(speaker=call_system.NAME).count() == 3


def test_the_viewer_refuses_to_rename_or_merge_it(admin, tmp_path, settings, client):
    settings_store.set_to("call_system_available", True)
    recording = a_call(admin, tmp_path, settings)
    call_system.mark(recording.transcript)
    browser = signed_in(client, admin)
    for was, now in ((call_system.NAME, "Dana"), ("Speaker 2", call_system.NAME)):
        answer = browser.post(
            f"/recording/{recording.pk}/speakers",
            data=json.dumps({"from": was, "to": now}),
            content_type="application/json",
        )
        assert answer.status_code == 409, (was, now, answer.content)
    assert recording.transcript.segments.filter(speaker=call_system.NAME).count() == 3


def test_the_pages_draw_it_grey_and_without_controls(admin, tmp_path, settings, client):
    settings_store.set_to("call_system_available", True)
    recording = a_call(admin, tmp_path, settings)
    call_system.mark(recording.transcript)
    browser = signed_in(client, admin)
    page = browser.get(f"/recording/{recording.pk}/speakers/classic").content.decode()
    assert "not a person" in page
    assert 'class="sp-card system"' in page or "sp-card system" in page
    viewer = browser.get(f"/recording/{recording.pk}").content.decode()
    assert "speakerchip system" in viewer
    assert '"system": true' in viewer


def test_the_rules_say_the_call_system_announced(db):
    for text in (
        prompts.NARRATIVE_RULES,
        prompts.CASE_CHAT,
        prompts.SHIPPED_SUMMARIES["jail_call"],
    ):
        assert "call system announced" in text


def test_landing_marks_when_on(admin, tmp_path, settings, monkeypatch):
    """The hook the queue calls as a Transcript lands, with the switch on and off."""
    settings_store.set_to("call_system_available", True)
    recording = a_call(admin, tmp_path, settings)
    call_system.on_landed(recording.transcript)
    assert recording.transcript.segments.filter(speaker=call_system.NAME).count() == 3
    # A failure inside never fails the landing.
    monkeypatch.setattr(call_system, "mark", lambda transcript: 1 / 0)
    call_system.on_landed(recording.transcript)


def test_the_pass_follows_a_type_set_later_and_a_run(
    admin, tmp_path, settings, client, monkeypatch
):
    """A transcript that landed with no type gets the pass when it is typed a
    jail call (v1.147.2), once; a check's run gives it to one that never had
    it; one that had it is left alone."""
    from core.cases import Case

    settings_store.set_to("folder_management", True)
    settings_store.set_to("call_system_available", True)
    case = Case.objects.create(owner=admin, name="Ramirez")
    recording = a_call(admin, tmp_path, settings, kind="", case=case)
    transcript = recording.transcript
    call_system.on_landed(transcript)
    assert transcript.segments.filter(speaker=call_system.NAME).count() == 0
    transcript.refresh_from_db()
    assert (transcript.provenance or {}).get("call_system") is None
    # Typed later, through the page's endpoint: the pass runs now.
    signed_in(client, admin)
    answer = client.post(
        f"/recording/{recording.pk}/case-details",
        {"recording_type": "Jail call", "description": ""},
    )
    assert answer.status_code == 200 and answer.json()["call_system"] == 3
    assert transcript.segments.filter(speaker=call_system.NAME).count() == 3
    transcript.refresh_from_db()
    assert transcript.provenance["call_system"]["lines"] == 3
    # Once: a second type change, and a run, leave it alone.
    answer = client.post(
        f"/recording/{recording.pk}/case-details",
        {"recording_type": "Jail call", "description": "a note"},
    )
    assert answer.json()["call_system"] == 0
    assert call_system.mark_if_missed(transcript) == 0
    # A transcript that never had the pass gets it from mark_if_missed, which
    # the check's run calls first; a failure inside never raises.
    other = a_call(admin, tmp_path, settings, kind="Jail call", case=case)
    assert call_system.mark_if_missed(other.transcript) == 3
    monkeypatch.setattr(call_system, "mark", lambda transcript: 1 / 0)
    third = a_call(admin, tmp_path, settings, kind="Jail call", case=case)
    assert call_system.mark_if_missed(third.transcript) == 0


def test_the_export_says_what_it_is(admin, tmp_path, settings, client):
    settings_store.set_to("call_system_available", True)
    recording = a_call(admin, tmp_path, settings)
    call_system.mark(recording.transcript)
    browser = signed_in(client, admin)
    answer = browser.get(f"/recording/{recording.pk}/export/text")
    assert answer.status_code == 200
    body = answer.content.decode()
    assert "Call system: You have one minute remaining." in body
    assert "Speaker 1: Hello?" in body
