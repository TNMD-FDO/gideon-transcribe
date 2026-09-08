"""v1.36.0: undo for a speaker change, two speakers on a call, renaming a recording.

The rules checked here: a rename or merge in the viewer is remembered on the
Transcript and Undo puts exactly the Segments it moved back, newest change
first, leaving alone any that were renamed again since; a call recorded in
the app does not separate voices within a side unless asked, a meeting
still does, and the Record page's tick decides; a Recording is renamed by
the people who work in it and not by an Admin looking in, the file name
kept; no audit row carries a name or a title.
"""

from __future__ import annotations

import json

import pytest
from core import live, settings_store, uploads
from core.audit import Row
from core.cases import Case
from core.jobs import Segment, Transcript
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording
from django.urls import reverse

PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings, monkeypatch):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"
    (tmp_path / "uploads").mkdir()
    monkeypatch.setattr(uploads, "free_disk_bytes", lambda: 10**15)
    return tmp_path


@pytest.fixture
def owner(db):
    return User.objects.create_local_admin("owner", PASSWORD)


@pytest.fixture
def somebody_else(db):
    return User.objects.create_local_admin("another-admin", PASSWORD)


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def a_recording(owner, speakers=("Speaker 1", "Speaker 2", "Speaker 3")):
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=owner),
        user=owner,
        title="an interview",
        original_filename="interview.m4a",
        media_state=MediaState.READY,
        duration_seconds=900.0,
        diarize=True,
    )
    transcript = Transcript.objects.create(recording=recording, language="en")
    lines = (
        (0.0, speakers[0], "SPEAKER_00", "This is Detective Ruiz."),
        (12.4, speakers[1], "SPEAKER_01", "Thanks, Maria."),
        (30.0, speakers[2], "SPEAKER_02", "Good morning."),
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


def names_in(recording) -> list[str]:
    return list(
        Segment.objects.filter(transcript__recording=recording)
        .order_by("start")
        .values_list("speaker", flat=True)
    )


def change(client, recording, was, now):
    return client.post(
        f"/recording/{recording.pk}/speakers",
        data=json.dumps({"from": was, "to": now}),
        content_type="application/json",
    )


def undo(client, recording):
    return client.post(f"/recording/{recording.pk}/speakers/undo")


# Undo -------------------------------------------------------------------------------


@pytest.mark.django_db
def test_a_merge_is_remembered_and_undone_exactly(owner, client):
    recording = a_recording(owner)
    signed_in(client, owner)

    answer = change(client, recording, "Speaker 2", "Speaker 1")
    assert answer.status_code == 200
    assert answer.json()["merged"] is True
    assert answer.json()["undo"] == "the merge of Speaker 2 into Speaker 1"
    assert names_in(recording) == ["Speaker 1", "Speaker 1", "Speaker 3", "Speaker 1"]

    transcript = Transcript.objects.get(recording=recording)
    (remembered,) = transcript.speaker_changes
    assert remembered["from"] == "Speaker 2" and remembered["to"] == "Speaker 1"
    assert remembered["merged"] is True and len(remembered["segments"]) == 1

    answer = undo(client, recording)
    assert answer.status_code == 200
    assert answer.json() == {"restored": 1, "undo": ""}
    # Only the line that was moved goes back; Speaker 1's own lines stay.
    assert names_in(recording) == ["Speaker 1", "Speaker 2", "Speaker 3", "Speaker 1"]
    assert Transcript.objects.get(recording=recording).speaker_changes == []

    # Nothing left to undo.
    assert undo(client, recording).status_code == 404

    row = Row.objects.get(event="Speaker change undone")
    assert row.details["was_merge"] is True and row.details["segments_changed"] == 1
    assert "Speaker" not in json.dumps(row.details)


@pytest.mark.django_db
def test_undo_takes_the_changes_back_newest_first(owner, client):
    recording = a_recording(owner)
    signed_in(client, owner)
    change(client, recording, "Speaker 1", "Ruiz")
    change(client, recording, "Speaker 3", "Ruiz")
    assert names_in(recording) == ["Ruiz", "Speaker 2", "Ruiz", "Ruiz"]

    assert undo(client, recording).json()["undo"] == "renaming Speaker 1 to Ruiz"
    assert names_in(recording) == ["Ruiz", "Speaker 2", "Speaker 3", "Ruiz"]
    assert undo(client, recording).json()["undo"] == ""
    assert names_in(recording) == ["Speaker 1", "Speaker 2", "Speaker 3", "Speaker 1"]


@pytest.mark.django_db
def test_undo_leaves_alone_a_line_renamed_again_since(owner, client):
    recording = a_recording(owner)
    signed_in(client, owner)
    change(client, recording, "Speaker 2", "Speaker 1")
    # Everything now called Speaker 1 is renamed, moved line included.
    change(client, recording, "Speaker 1", "Ruiz")
    assert names_in(recording) == ["Ruiz", "Ruiz", "Speaker 3", "Ruiz"]
    # The newest change is undone first, and the merged line comes back as
    # Speaker 1 with the others, so the merge can still be undone after it.
    undo(client, recording)
    assert names_in(recording) == ["Speaker 1", "Speaker 1", "Speaker 3", "Speaker 1"]
    undo(client, recording)
    assert names_in(recording) == ["Speaker 1", "Speaker 2", "Speaker 3", "Speaker 1"]


@pytest.mark.django_db
def test_the_viewer_offers_undo_only_when_there_is_something_to_undo(owner, client):
    recording = a_recording(owner)
    signed_in(client, owner)
    page = client.get(reverse("viewer", args=[recording.pk])).content.decode()
    assert 'id="speakers-undo-line" hidden' in page
    change(client, recording, "Speaker 2", "Speaker 1")
    page = client.get(reverse("viewer", args=[recording.pk])).content.decode()
    assert 'id="speakers-undo-line">' in page
    assert "the merge of Speaker 2 into Speaker 1" in page


@pytest.mark.django_db
def test_only_the_last_twenty_changes_are_kept(owner, client):
    recording = a_recording(owner)
    signed_in(client, owner)
    for n in range(23):
        change(client, recording, f"Name {n}" if n else "Speaker 1", f"Name {n + 1}")
    kept = Transcript.objects.get(recording=recording).speaker_changes
    assert len(kept) == 20
    assert kept[-1]["to"] == "Name 23" and kept[0]["from"] == "Name 3"


# A call has two speakers --------------------------------------------------------------


@pytest.fixture
def recording_on(db):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("live_recording", True)


@pytest.fixture
def a_case(owner):
    return Case.objects.create(owner=owner, name="Ramirez")


@pytest.mark.django_db
def test_a_call_does_not_separate_voices_within_a_side_unless_asked(
    recording_on, owner, a_case
):
    assert live.start(owner, a_case, style="call").diarize is False
    assert live.start(owner, a_case, style="meeting").diarize is True
    assert live.start(owner, a_case, style="dictation").diarize is False
    # The tick under More options decides when it is sent.
    assert live.start(owner, a_case, style="call", diarize=True).diarize is True
    assert live.start(owner, a_case, style="meeting", diarize=False).diarize is False


@pytest.mark.django_db
def test_the_record_page_sends_the_tick(recording_on, owner, a_case, client):
    signed_in(client, owner)
    page = client.get(reverse("record-new") + f"?case={a_case.pk}").content.decode()
    assert 'id="record-diarize"' in page and "Tell the speakers apart" in page

    def started(**wanted):
        answer = client.post(
            reverse("record-start"),
            json.dumps({"case": str(a_case.pk), **wanted}),
            "application/json",
        )
        assert answer.status_code == 200, answer.content
        return Recording.objects.get(pk=answer.json()["id"])

    assert started(style="call").diarize is False
    assert started(style="call", diarize=True).diarize is True
    assert started(style="meeting", diarize=False).diarize is False
    assert started(style="meeting").diarize is True


# Rename ----------------------------------------------------------------------------


def rename(client, recording, title):
    return client.post(
        f"/recording/{recording.pk}/rename",
        data=json.dumps({"title": title}),
        content_type="application/json",
    )


@pytest.mark.django_db
def test_the_owner_renames_and_the_file_keeps_its_name(owner, client):
    recording = a_recording(owner)
    signed_in(client, owner)
    answer = rename(client, recording, "  Ruiz interview, 3 March  ")
    assert answer.status_code == 200
    assert answer.json() == {"title": "Ruiz interview, 3 March"}
    recording.refresh_from_db()
    assert recording.title == "Ruiz interview, 3 March"
    assert recording.original_filename == "interview.m4a"
    row = Row.objects.get(event="Recording renamed")
    assert "Ruiz" not in json.dumps(row.details) and row.object_label == "interview.m4a"

    assert rename(client, recording, "   ").status_code == 400
    page = client.get(reverse("viewer", args=[recording.pk])).content.decode()
    assert 'id="rename-title"' in page


@pytest.mark.django_db
def test_an_admin_looking_in_may_not_rename(owner, somebody_else, client):
    recording = a_recording(owner)
    signed_in(client, somebody_else)
    assert rename(client, recording, "Something else").status_code == 404
    recording.refresh_from_db()
    assert recording.title == "an interview"
    page = client.get(reverse("viewer", args=[recording.pk])).content.decode()
    assert 'id="rename-title"' not in page
    # But an Admin may still undo a speaker change, as they may make one.
    change(client, recording, "Speaker 2", "Speaker 1")
    assert undo(client, recording).status_code == 200


@pytest.mark.django_db
def test_my_recordings_offers_rename_on_own_rows_only(owner, somebody_else, client):
    a_recording(owner)
    signed_in(client, owner)
    page = client.get(reverse("home")).content.decode()
    assert "rename-recording" in page
    signed_in(client, somebody_else)
    page = client.get(f"/panel/users/{owner.username}/workspace").content.decode()
    assert "rename-recording" not in page
