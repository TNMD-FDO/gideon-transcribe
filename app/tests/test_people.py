"""People: inside a Case a Speaker's name means a person.

The rules checked here: naming a Speaker in a Case makes or joins a Person and
a label never does; rename and merge reach every Recording of the Case and
delete puts the Speakers back to Speaker 1, Speaker 2; the AI assistant's
Suggest names reads the People first and drops a name nothing in the
Transcript backs; the Speakers tab renders, and the Role reaches the viewer's
badges and the Word export. Every audit row is checked never to carry a name.
"""

from __future__ import annotations

import json

import pytest
from core import assistant, people, prompts, queue, settings_store
from core.audit import Row
from core.cases import Case
from core.jobs import Segment, Transcript
from core.models import LoginSession, User
from core.people import Person
from core.recordings import Batch, MediaState, Recording

PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"
    return tmp_path


@pytest.fixture
def owner(db):
    return User.objects.create_local_admin("case-owner", PASSWORD)


@pytest.fixture
def a_case(owner):
    # Cases, and so People, exist only while Folder management is On.
    settings_store.set_to("folder_management", True)
    return Case.objects.create(owner=owner, name="Ramirez")


def a_recording(owner, case, title="an interview", speakers=("Speaker 1", "Speaker 2")):
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=owner),
        user=owner,
        case=case,
        title=title,
        original_filename="interview.m4a",
        media_state=MediaState.READY,
        duration_seconds=900.0,
        diarize=True,
    )
    transcript = Transcript.objects.create(recording=recording, language="en")
    lines = (
        (0.0, speakers[0], "SPEAKER_00", "This is Detective Ruiz."),
        (12.4, speakers[1], "SPEAKER_01", "Thanks, Maria."),
        (724.0, speakers[0], "SPEAKER_00", "Tell me about the car."),
    )
    for start, speaker, label, text in lines:
        Segment.objects.create(
            transcript=transcript,
            start=start,
            end=start + 5,
            text=text,
            speaker=speaker,
            speaker_label=label,
        )
    return recording


def names_in(recording) -> set[str]:
    return set(
        Segment.objects.filter(transcript__recording=recording).values_list(
            "speaker", flat=True
        )
    )


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def no_name_in_the_audit(*names):
    for row in Row.objects.filter(category="cases"):
        text = json.dumps(row.details) + (row.object_label or "")
        for name in names:
            assert name not in text, (row.event, text)


# Naming makes a Person ------------------------------------------------------------


@pytest.mark.django_db
def test_naming_a_speaker_in_a_case_makes_a_person_and_a_label_does_not(owner, a_case):
    recording = a_recording(owner, a_case)
    assert people.on_named(recording, "Speaker 3", by=owner, how="test") is None
    made = people.on_named(recording, "Detective Ruiz", by=owner, how="test")
    assert made is not None and made.case == a_case
    # The same name, in any case of letters, joins rather than doubles.
    again = people.on_named(recording, "detective ruiz", by=owner, how="test")
    assert again.pk == made.pk
    assert Person.objects.filter(case=a_case).count() == 1
    row = Row.objects.get(category="cases", event="Person added")
    assert row.details["how"] == "test"
    no_name_in_the_audit("Ruiz")


@pytest.mark.django_db
def test_a_workspace_recording_makes_no_person(owner):
    recording = a_recording(owner, None)
    assert people.on_named(recording, "Detective Ruiz", by=owner, how="test") is None
    assert Person.objects.count() == 0


@pytest.mark.django_db
def test_a_recording_moved_in_brings_its_named_speakers(owner, a_case):
    recording = a_recording(owner, a_case, speakers=("Detective Ruiz", "Speaker 2"))
    assert people.moved_in(recording, by=owner) == 1
    assert [one.name for one in a_case.people.all()] == ["Detective Ruiz"]


@pytest.mark.django_db
def test_the_viewer_rename_and_an_accepted_suggestion_reach_the_case(
    owner, a_case, client
):
    recording = a_recording(owner, a_case)
    signed_in(client, owner)
    answer = client.post(
        f"/recording/{recording.pk}/speakers",
        data=json.dumps({"from": "Speaker 1", "to": "Detective Ruiz"}),
        content_type="application/json",
    )
    assert answer.status_code == 200
    assert Person.objects.get(case=a_case).name == "Detective Ruiz"


# The tab's acts reach every recording ----------------------------------------------


@pytest.mark.django_db
def test_rename_reaches_every_recording_and_refuses_a_taken_name(owner, a_case):
    first = a_recording(owner, a_case, "first", speakers=("Ruiz", "Speaker 2"))
    second = a_recording(owner, a_case, "second", speakers=("Ruiz", "Maria"))
    ruiz, _ = people.join_or_create(a_case, "Ruiz", by=owner, how="test")
    maria, _ = people.join_or_create(a_case, "Maria", by=owner, how="test")

    assert people.rename(ruiz, "Detective Ruiz", by=owner) == 4
    assert names_in(first) == {"Detective Ruiz", "Speaker 2"}
    assert names_in(second) == {"Detective Ruiz", "Maria"}
    with pytest.raises(ValueError):
        people.rename(ruiz, "maria", by=owner)
    no_name_in_the_audit("Ruiz", "Maria")


@pytest.mark.django_db
def test_merge_renames_the_merged_persons_speakers_and_keeps_the_notes(owner, a_case):
    first = a_recording(owner, a_case, "first", speakers=("Ruiz", "Speaker 2"))
    second = a_recording(owner, a_case, "second", speakers=("D. Ruiz", "Maria"))
    ruiz, _ = people.join_or_create(a_case, "Ruiz", by=owner, how="test", notes="Lead.")
    other, _ = people.join_or_create(
        a_case, "D. Ruiz", by=owner, how="test", notes="Also on the second call."
    )

    changed, recordings = people.merge(other, ruiz, by=owner)
    assert (changed, recordings) == (2, 1)
    assert names_in(first) == {"Ruiz", "Speaker 2"}
    assert names_in(second) == {"Ruiz", "Maria"}
    ruiz.refresh_from_db()
    assert ruiz.notes == "Lead.\n\nD. Ruiz: Also on the second call."
    assert not Person.objects.filter(pk=other.pk).exists()
    no_name_in_the_audit("Ruiz")


@pytest.mark.django_db
def test_delete_puts_the_speakers_back_to_their_labels(owner, a_case):
    recording = a_recording(owner, a_case, speakers=("Detective Ruiz", "Maria"))
    ruiz, _ = people.join_or_create(a_case, "Detective Ruiz", by=owner, how="test")
    assert people.delete(ruiz, by=owner) == 2
    assert names_in(recording) == {"Speaker 1", "Maria"}


@pytest.mark.django_db
def test_unname_works_out_the_labels_per_side_as_at_storage(owner, a_case):
    recording = a_recording(owner, a_case, speakers=("Maria", "Speaker 1"))
    # Maria carries SPEAKER_00, the first label; she goes back to Speaker 1 and
    # the other speaker, whose label is SPEAKER_01, is Speaker 2 again.
    assert queue.unname(recording.transcript, "maria") == 2
    assert names_in(recording) == {"Speaker 1"}
    assert queue.unname(recording.transcript, "Speaker 1") == 3
    assert names_in(recording) == {"Speaker 1", "Speaker 2"}


@pytest.mark.django_db
def test_the_tab_posts_add_rename_edit_merge_and_delete(owner, a_case, client):
    a_recording(owner, a_case, speakers=("Ruiz", "Speaker 2"))
    signed_in(client, owner)
    tab = f"/case/{a_case.pk}?tab=speakers"

    added = client.post(f"/case/{a_case.pk}/people", {"name": "Ruiz", "role": "Agent"})
    assert added.status_code == 302 and added["Location"] == tab
    ruiz = Person.objects.get(case=a_case)
    assert ruiz.role == "Agent"

    # The same name again is refused, and the tab says so once.
    client.post(f"/case/{a_case.pk}/people", {"name": "ruiz"})
    page = client.get(tab)
    assert b"is already in this case" in page.content
    assert b"is already in this case" not in client.get(tab).content
    assert Person.objects.filter(case=a_case).count() == 1

    client.post(f"/person/{ruiz.pk}", {"action": "edit", "role": "", "notes": "Lead."})
    ruiz.refresh_from_db()
    assert (ruiz.role, ruiz.notes) == ("", "Lead.")

    client.post(f"/person/{ruiz.pk}", {"action": "rename", "name": "Detective Ruiz"})
    ruiz.refresh_from_db()
    assert ruiz.name == "Detective Ruiz"

    client.post(f"/case/{a_case.pk}/people", {"name": "D. Ruiz"})
    other = Person.objects.get(case=a_case, name="D. Ruiz")
    client.post(f"/person/{other.pk}", {"action": "merge", "into": str(ruiz.pk)})
    assert not Person.objects.filter(pk=other.pk).exists()

    client.post(f"/person/{ruiz.pk}", {"action": "delete"})
    assert Person.objects.filter(case=a_case).count() == 0


@pytest.mark.django_db
def test_the_tab_renders_the_people_and_the_unnamed(owner, a_case, client):
    recording = a_recording(owner, a_case, speakers=("Detective Ruiz", "Speaker 2"))
    people.join_or_create(
        a_case, "Detective Ruiz", by=owner, how="test", role="Agent", notes="Lead."
    )
    signed_in(client, owner)
    page = client.get(f"/case/{a_case.pk}?tab=speakers")
    assert page.status_code == 200
    text = page.content.decode()
    assert "Speakers (1)" in text
    assert "1 person, 1 recording with unnamed speakers" in text
    assert "Detective Ruiz" in text and "Agent" in text and "Lead." in text
    assert f"/recording/{recording.pk}?t=0.0" in text
    assert "1 unnamed" in text
    # The other tabs count the people too, for the tab's label.
    assert "Speakers (1)" in client.get(f"/case/{a_case.pk}").content.decode()


@pytest.mark.django_db
def test_the_tab_is_gone_while_folder_management_is_off(owner, a_case, client):
    signed_in(client, owner)
    settings_store.set_to("folder_management", False)
    assert client.get(f"/case/{a_case.pk}?tab=speakers").status_code == 404
    assert client.post(f"/case/{a_case.pk}/people", {"name": "Ruiz"}).status_code == 404


# The Role reaches the viewer and the export -------------------------------------------


@pytest.mark.django_db
def test_the_role_shows_in_the_viewer_and_the_rename_box_offers_the_people(
    owner, a_case, client
):
    recording = a_recording(owner, a_case, speakers=("Detective Ruiz", "Speaker 2"))
    people.join_or_create(a_case, "Detective Ruiz", by=owner, how="test", role="Agent")
    signed_in(client, owner)
    text = client.get(f"/recording/{recording.pk}").content.decode()
    assert '<span class="pill role">Agent</span>' in text
    assert 'id="rename-box"' in text and 'id="people-pick"' in text
    # The people are listed in the open, one button each, not in the
    # browser's own suggestion list (which hid them behind the current name).
    assert "datalist" not in text
    assert (
        '<button type="button" class="pick" data-name="Detective Ruiz">'
        'Detective Ruiz <span class="pill role">Agent</span> '
        '<span class="muted">in 1 recording</span></button>'
    ) in text
    assert f"/case/{a_case.pk}?tab=speakers" in text


@pytest.mark.django_db
def test_a_workspace_viewer_has_no_rename_box(owner, client):
    recording = a_recording(owner, None)
    signed_in(client, owner)
    text = client.get(f"/recording/{recording.pk}").content.decode()
    assert 'id="rename-box"' not in text


@pytest.mark.django_db
def test_the_word_export_fills_the_role_column_inside_a_case(owner, a_case):
    from io import BytesIO

    from core import exports
    from docx import Document

    recording = a_recording(owner, a_case, speakers=("Detective Ruiz", "Speaker 2"))
    people.join_or_create(a_case, "Detective Ruiz", by=owner, how="test", role="Agent")
    document = Document(BytesIO(exports.word(recording, "case-owner")))
    cells = [
        cell.text
        for table in document.tables
        for row in table.rows
        for cell in row.cells
    ]
    assert "Agent" in cells


# What Suggest names reads ----------------------------------------------------------


@pytest.mark.django_db
def test_known_names_lists_the_people_first_then_the_vocabularies(owner, a_case):
    recording = a_recording(owner, a_case)
    recording.vocabulary = ["Maria Lopez", "Detective Ruiz"]
    recording.save(update_fields=["vocabulary"])
    settings_store.set_to("office_vocabulary", "Maria Lopez\nRamirez")
    people.join_or_create(a_case, "Detective Ruiz", by=owner, how="test", role="Agent")
    assert people.known_names(recording) == [
        "Detective Ruiz (Agent)",
        "Maria Lopez",
        "Ramirez",
    ]


def test_the_evidence_finds_introductions_and_addresses():
    lines = [
        prompts.Line(1, 1, 0.0, "Speaker 1", "This is Detective Ruiz, good morning."),
        prompts.Line(2, 2, 12.4, "Speaker 2", "Thanks, Maria, I understand."),
        prompts.Line(3, 3, 20.0, "Speaker 1", "Yes sir, I am sure of it."),
    ]
    found = prompts.evidence(lines)
    assert [(one["kind"], one["speaker"], one["name"]) for one in found] == [
        ("introduces", "Speaker 1", "Ruiz"),
        ("addresses", "Speaker 2", "Maria"),
    ]
    assert prompts.backed_by_evidence("Detective Ruiz", found)
    assert prompts.backed_by_evidence("Maria Lopez", found)
    assert not prompts.backed_by_evidence("Carlos", found)


def test_a_name_without_evidence_is_dropped_and_a_role_is_kept():
    lines = [
        prompts.Line(1, 1, 0.0, "Speaker 1", "This is Detective Ruiz."),
        prompts.Line(2, 2, 12.4, "Speaker 2", "Thanks, Maria."),
    ]
    found = prompts.evidence(lines)
    raw = [
        {
            "speaker": "Speaker 1",
            "name": "Detective Ruiz",
            "kind": "name",
            "confidence": "high",
            "line": 1,
            "quote": "This is Detective Ruiz.",
        },
        {
            "speaker": "Speaker 2",
            "name": "Carlos",
            "kind": "name",
            "confidence": "high",
            "line": 2,
            "quote": "Thanks, Maria.",
        },
    ]
    kept = prompts.keep_suggestions(
        raw, ["Speaker 1", "Speaker 2"], set(), lines, found
    )
    assert [one["name"] for one in kept] == ["Detective Ruiz"]
    raw[1]["name"], raw[1]["kind"] = "Interviewer", "role"
    kept = prompts.keep_suggestions(
        raw, ["Speaker 1", "Speaker 2"], set(), lines, found
    )
    assert [one["name"] for one in kept] == ["Detective Ruiz", "Interviewer"]


@pytest.mark.django_db
def test_suggest_names_tells_the_engine_the_people_the_roles_and_the_evidence(
    owner, a_case, monkeypatch
):
    from core import engine
    from core.assistant import SuggestionRun

    recording = a_recording(owner, a_case)
    people.join_or_create(a_case, "Maria Lopez", by=owner, how="test", role="Client")
    settings_store.set_to("assistant_available", True)
    settings_store.set_to("suggestions_available", True)
    monkeypatch.setattr(engine, "is_reachable", lambda: True)
    monkeypatch.setattr(engine, "address", lambda: "http://gideon-generator:8000/v1")
    asked = []

    def complete(messages, **options):
        asked.append(messages)
        return {
            "text": json.dumps({"suggestions": []}),
            "finish_reason": "stop",
            "input_tokens": 1,
            "output_tokens": 1,
            "model": "the-model",
        }

    monkeypatch.setattr(engine, "complete", complete)
    run = SuggestionRun.objects.create(transcript=recording.transcript, asked_by=owner)
    assistant.suggest_names(run.pk)
    user_message = asked[0][-1]["content"]
    assert "Known names: Maria Lopez (Client)" in user_message
    assert "Roles to choose from:" in user_message
    assert "Evidence found in the transcript:" in user_message
    assert "Ruiz" in user_message and "Maria" in user_message


def test_the_suggestion_method_setting_offers_evidence_and_needs_the_feature():
    definition = settings_store.DEFINITIONS["suggestion_method"]
    assert definition.default == "evidence"
    assert definition.choices == ("evidence",)
    assert definition.needs == "suggestions_available"
