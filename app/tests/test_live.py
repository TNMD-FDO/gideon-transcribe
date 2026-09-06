"""Live recording (Phase 3, step one): the Record page with the microphone.

What would be expensive to get wrong: the page exists only under its
setting; a recording starts as a Recording in its Case with its own Batch
that never holds up uploads; the sidecar takes an upload of unknown length
for it and nothing else; a recording that ends by Stop leaves the pipeline
to the sidecar's finish, and one that ends early takes what arrived; the
service is asked to put it first; the queue line reads in words; the
Provenance says it was recorded live.
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest
from core import live, queue, settings_store, uploads
from core.audit import Row
from core.cases import Case
from core.jobs import Job, JobState, Run, Segment, Transcript
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording, Side
from django.conf import settings as django_settings
from django.urls import reverse
from django.utils import timezone

PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"
    (tmp_path / "uploads").mkdir()
    return tmp_path


@pytest.fixture(autouse=True)
def room(monkeypatch):
    monkeypatch.setattr(uploads, "free_disk_bytes", lambda: 10**15)


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("recorder", PASSWORD)


@pytest.fixture
def on(db):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("live_recording", True)


@pytest.fixture
def a_case(person):
    return Case.objects.create(owner=person, name="Ramirez")


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def rows(event):
    return Row.objects.filter(event=event)


# The setting and the page ------------------------------------------------------------


def test_the_page_exists_only_under_its_setting(person, a_case, client):
    signed_in(client, person)
    assert client.get(reverse("record")).status_code == 404
    settings_store.set_to("folder_management", True)
    assert client.get(reverse("record")).status_code == 404
    told = settings_store.definition("live_recording")
    assert told.needs == "folder_management" and told.default is False
    settings_store.set_to("live_recording", True)
    page = client.get(reverse("record") + f"?case={a_case.pk}").content.decode()
    assert "Ramirez" in page and 'id="start"' in page and "180 minutes" in page
    # Record sits beside Upload on the Cases page and beside Add recordings.
    assert 'href="/record"' in client.get(reverse("cases")).content.decode()
    assert (
        f"/record?case={a_case.pk}"
        in client.get(reverse("case", args=[a_case.pk])).content.decode()
    )


# Starting ------------------------------------------------------------------------


def test_a_recording_starts_in_its_case_with_its_own_batch(on, person, a_case, client):
    signed_in(client, person)
    answer = client.post(
        reverse("record-start"),
        json.dumps(
            {"case": str(a_case.pk), "recording_type": "Interview", "language": "es"}
        ),
        "application/json",
    )
    assert answer.status_code == 200, answer.content
    recording = Recording.objects.get(pk=answer.json()["id"])
    assert recording.case == a_case and recording.is_live
    assert recording.media_state == MediaState.UPLOADING
    assert recording.batch.is_live and recording.recording_type == "Interview"
    assert recording.spoken_language == "es" and recording.title.startswith("Interview")
    assert recording.original_filename.endswith(".webm")
    row = rows("Live recording started").get()
    assert row.details["case"] == "Ramirez" and row.details["language"] == "es"
    # A Live recording never holds up the person's uploads.
    assert Batch.unfinished_for(person) is None
    # And the service is asked to put it first.
    side = Side.objects.create(recording=recording, number=1)
    job = Job.objects.create(recording=recording, batch=recording.batch)
    run = Run.objects.create(job=job, side=side)
    assert queue.request_for(run)["priority"] == 100


def test_starting_is_refused_without_room_or_a_case_of_ones_own(
    on, person, a_case, client
):
    other = User.objects.create_local_admin("other", PASSWORD)
    other.is_local = False
    other.save()
    signed_in(client, other)
    answer = client.post(
        reverse("record-start"),
        json.dumps({"case": str(a_case.pk)}),
        "application/json",
    )
    assert answer.status_code == 400 and "not yours" in answer.json()["why"]
    person.quota_gb = 1
    person.save()
    signed_in(client, person)
    rec = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        case=a_case,
        title="big",
        original_filename="big.m4a",
    )
    rec.folder.mkdir(parents=True)
    (rec.folder / "original.m4a").write_bytes(b"x" * 1024)
    from unittest import mock

    with mock.patch.object(uploads, "used_bytes", return_value=2 * settings_store.GB):
        answer = client.post(
            reverse("record-start"),
            json.dumps({"case": str(a_case.pk)}),
            "application/json",
        )
    assert answer.status_code == 400 and "storage space is full" in answer.json()["why"]


def test_the_computers_sound_makes_a_call_with_named_sides(on, person, a_case, client):
    from core import pipeline

    recording = live.start(person, a_case, with_computer=True)
    assert recording.live["sources"] == ["microphone", "computer"]
    assert rows("Live recording started").get().details["sources"] == [
        "microphone",
        "computer",
    ]
    # The pipeline does not ask whether it looks like a call: it is one.
    from unittest import mock

    from core import media

    probed = mock.Mock(best_track=None)
    with mock.patch.object(media, "probe", return_value=probed):
        pipeline._find_sides(recording)
    recording.refresh_from_db()
    assert recording.is_two_channel_call
    assert [one.name for one in recording.sides.order_by("number")] == [
        "This side",
        "The other side",
    ]
    live.ended(recording, how="stop", seconds=120, computer_ended_at=90.5)
    recording.refresh_from_db()
    told = dict(live.provenance_rows(recording))
    assert told["Recorded live"].startswith(
        "On the Record page, from the microphone and the computer's sound"
    )
    assert told["The computer's sound"].startswith("stopped at 1:30")
    # The page carries the tick and the second meter.
    signed_in(client, person)
    page = client.get(reverse("record")).content.decode()
    assert 'id="record-computer"' in page and 'id="meter-computer"' in page


def test_taps_name_the_speakers_and_marks_are_kept(on, person, a_case, client):
    from core.people import Person

    recording = live.start(person, a_case)
    live.ended(
        recording,
        how="stop",
        seconds=60,
        taps=[
            {"at": 10, "name": "Ana Ruiz"},
            {"at": 20, "name": "Ben Cole"},
            {"at": 40, "name": "Ana Ruiz"},
            {"at": "x", "name": "nobody"},
        ],
        marks=[{"at": 33.3, "word": "the threat"}, {"at": 5, "word": ""}],
    )
    recording.refresh_from_db()
    assert recording.speaker_taps == [
        {"at": 10.0, "name": "Ana Ruiz"},
        {"at": 20.0, "name": "Ben Cole"},
        {"at": 40.0, "name": "Ana Ruiz"},
    ]
    assert recording.marks == [
        {"at": 5.0, "word": ""},
        {"at": 33.3, "word": "the threat"},
    ]
    finished = rows("Live recording finished").get()
    assert finished.details["taps"] == 3 and finished.details["marks"] == 2
    assert "threat" not in str(finished.details)

    # The transcript lands: label A spoke while Ana was tapped, label B while Ben.
    transcript = Transcript.objects.create(recording=recording, language="en")
    for start, label in (
        (2, "SPEAKER_00"),
        (12, "SPEAKER_00"),
        (25, "SPEAKER_01"),
        (45, "SPEAKER_00"),
    ):
        Segment.objects.create(
            transcript=transcript,
            start=start,
            end=start + 6,
            text="words",
            speaker=label.replace("SPEAKER_0", "Speaker "),
            speaker_label=label,
        )
    # A label that spoke before the first tap is covered by nobody and keeps its name.
    Segment.objects.create(
        transcript=transcript,
        start=0,
        end=5,
        text="w",
        speaker="Speaker 3",
        speaker_label="SPEAKER_02",
    )
    assert live.name_from_taps(recording, transcript) == 2
    named = set(transcript.segments.values_list("speaker_label", "speaker"))
    assert ("SPEAKER_00", "Ana Ruiz") in named and ("SPEAKER_01", "Ben Cole") in named
    assert ("SPEAKER_02", "Speaker 3") in named
    assert set(Person.objects.filter(case=a_case).values_list("name", flat=True)) == {
        "Ana Ruiz",
        "Ben Cole",
    }
    row = rows("Speakers named from taps").get()
    assert row.details["labels_named"] == 2 and "Ana" not in str(row.details)
    recording.refresh_from_db()
    told = dict(live.provenance_rows(recording))
    assert (
        told["Speakers named from taps"] == "2 speakers" and told["Marks"] == "2 marks"
    )

    # The viewer's Details carry the Marks as times with their words.
    signed_in(client, person)
    recording.media_state = MediaState.READY
    recording.save()
    told = client.get(reverse("details", args=[recording.pk])).json()
    assert told["marks"] == [
        {"at": 5.0, "clock": "00:00:05", "word": ""},
        {"at": 33.3, "clock": "00:00:33", "word": "the threat"},
    ]


def test_on_a_call_only_the_microphones_side_is_named_from_taps(on, person, a_case):
    recording = live.start(person, a_case, with_computer=True)
    recording.is_two_channel_call = True
    recording.save()
    mine = Side.objects.create(recording=recording, number=1, name="This side")
    theirs = Side.objects.create(recording=recording, number=2, name="The other side")
    live.ended(recording, how="stop", taps=[{"at": 0, "name": "Ana Ruiz"}])
    recording.refresh_from_db()
    transcript = Transcript.objects.create(recording=recording, language="en")
    Segment.objects.create(
        transcript=transcript,
        side=mine,
        start=0,
        end=10,
        text="a",
        speaker="Speaker 1",
        speaker_label="SPEAKER_00",
    )
    Segment.objects.create(
        transcript=transcript,
        side=theirs,
        start=0,
        end=10,
        text="b",
        speaker="Speaker 1",
        speaker_label="SPEAKER_00",
    )
    assert live.name_from_taps(recording, transcript) == 1
    assert transcript.segments.get(side=mine).speaker == "Ana Ruiz"
    assert transcript.segments.get(side=theirs).speaker == "Speaker 1"


def test_the_people_expected_come_from_the_case(on, person, a_case, client):
    from core.people import Person

    Person.objects.create(case=a_case, name="Ana Ruiz", added_by=person)
    signed_in(client, person)
    told = client.get(reverse("record-people") + f"?case={a_case.pk}").json()
    assert told["people"] == ["Ana Ruiz"]
    other = User.objects.create_local_admin("other", PASSWORD)
    other.is_local = False
    other.save()
    signed_in(client, other)
    assert client.get(reverse("record-people") + f"?case={a_case.pk}").json() == {
        "people": []
    }


def test_an_uploaded_recording_has_no_live_facts(person, a_case):
    rec = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        title="t",
        original_filename="t.m4a",
    )
    assert not rec.is_live and live.provenance_rows(rec) == []


# The sidecar ----------------------------------------------------------------------


def hook(client, name, metadata, size=0):
    session_key = client.session.session_key
    body = {
        "Type": name,
        "Event": {
            "Upload": {"ID": "abc123", "Size": size, "MetaData": metadata},
            "HTTPRequest": {
                "Header": {
                    "Cookie": [f"{django_settings.SESSION_COOKIE_NAME}={session_key}"]
                }
            },
        },
    }
    return client.post(
        "/upload-hook/", json.dumps(body), "application/json", HTTP_HOOK_NAME=name
    )


def test_the_sidecar_takes_an_upload_of_unknown_length_for_a_live_recording_only(
    on, person, a_case, client
):
    signed_in(client, person)
    recording = live.start(person, a_case)
    told = hook(
        client, "pre-create", {"recording": str(recording.pk), "live": "1"}
    ).json()
    assert "RejectUpload" not in told
    # Not for a Recording that is not live, and not once it has ended.
    plain = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        title="t",
        original_filename="t.m4a",
    )
    told = hook(client, "pre-create", {"recording": str(plain.pk), "live": "1"}).json()
    assert told.get("RejectUpload") is True
    recording.media_state = MediaState.CHECKING
    recording.save()
    told = hook(
        client, "pre-create", {"recording": str(recording.pk), "live": "1"}
    ).json()
    assert told.get("RejectUpload") is True


def test_stop_leaves_the_finish_to_the_sidecar_and_an_early_end_takes_what_arrived(
    on, person, a_case, client, tmp_path, monkeypatch
):
    from core import tasks

    deferred = []
    monkeypatch.setattr(
        tasks.prepare_recording, "defer", lambda **f: deferred.append(f)
    )
    signed_in(client, person)
    recording = live.start(person, a_case)
    client.post(
        reverse("record-upload", args=[recording.pk]),
        json.dumps({"tus": "abc123"}),
        "application/json",
    )
    (tmp_path / "uploads" / "abc123").write_bytes(b"\x1aE\xdf\xa3" + b"x" * 500)

    # Stop: the facts are written, the pipeline is the sidecar's finish to start.
    answer = client.post(
        reverse("record-ended", args=[recording.pk]),
        json.dumps(
            {"how": "stop", "seconds": 61.5, "pauses": [{"at": 10, "seconds": 5}]}
        ),
        "application/json",
    )
    assert answer.status_code == 200
    recording.refresh_from_db()
    assert recording.live["ended"] == "stop" and recording.live["seconds"] == 61.5
    assert recording.live["pauses"] == [{"at": 10.0, "seconds": 5.0}]
    assert recording.media_state == MediaState.UPLOADING and not deferred
    finished = rows("Live recording finished").get()
    assert finished.details["how"] == "stop" and finished.details["pauses"] == 1
    # The sidecar's finish then moves the file and starts the pipeline.
    hook(client, "post-finish", {"recording": str(recording.pk)})
    recording.refresh_from_db()
    assert recording.media_state == MediaState.CHECKING and len(deferred) == 1
    # And a second finish changes nothing.
    hook(client, "post-finish", {"recording": str(recording.pk)})
    assert len(deferred) == 1

    # The page closing: what arrived is taken at once, as a beacon's form.
    early = live.start(person, a_case)
    live.note_upload(early, "def456")
    (tmp_path / "uploads" / "def456").write_bytes(b"x" * 300)
    (tmp_path / "uploads" / "def456.info").write_text("{}")
    answer = client.post(
        reverse("record-ended", args=[early.pk]),
        {"how": "closed", "seconds": "12.0", "pauses": "[]"},
    )
    assert answer.status_code == 200
    early.refresh_from_db()
    assert early.live["ended"] == "closed"
    assert early.media_state == MediaState.CHECKING and early.size_bytes == 300
    assert (
        early.original_path.exists() and not (tmp_path / "uploads" / "def456").exists()
    )
    assert len(deferred) == 2
    # Ending twice does nothing more.
    client.post(reverse("record-ended", args=[early.pk]), {"how": "closed"})
    assert rows("Live recording finished").count() == 2

    # Nothing arrived at all: failed, and it says why.
    empty = live.start(person, a_case)
    live.ended(empty, how="closed")
    empty.refresh_from_db()
    assert (
        empty.media_state == MediaState.FAILED
        and "before any sound" in empty.failure_message
    )


def test_nobody_else_ends_or_reads_a_recording(on, person, a_case, client):
    recording = live.start(person, a_case)
    other = User.objects.create_local_admin("other", PASSWORD)
    signed_in(client, other)
    assert (
        client.post(
            reverse("record-ended", args=[recording.pk]), {"how": "stop"}
        ).status_code
        == 404
    )
    assert client.get(reverse("record-state", args=[recording.pk])).status_code == 404


# The queue line -----------------------------------------------------------------------


def test_the_queue_line_reads_in_words(on, person, a_case, client, monkeypatch):
    recording = live.start(person, a_case)
    assert live.line_for(recording)["state"] == "recording"
    recording.media_state = MediaState.READY
    recording.duration_seconds = 1800
    recording.save()
    assert live.line_for(recording)["says"] == "Preparing the sound."
    side = Side.objects.create(recording=recording, number=1)
    job = Job.objects.create(
        recording=recording, batch=recording.batch, state=JobState.QUEUED
    )
    Run.objects.create(
        job=job, side=side, state="queued", position=2, audio_minutes_ahead=90
    )
    # Two ahead, 90 minutes of audio plus this one's 30, at the assumed 60x.
    assert live.measured_speed() == live.ASSUMED_SPEED
    assert live.line_for(recording)["says"] == "2 recordings ahead, about 2 minutes."
    Run.objects.filter(job=job).update(position=0, audio_minutes_ahead=0)
    assert live.line_for(recording)["says"] == "Next in line, about 1 minute."
    job.state = JobState.RUNNING
    job.save()
    assert live.line_for(recording)["state"] == "transcribing"
    transcript = Transcript.objects.create(recording=recording, language="en")
    Segment.objects.create(
        transcript=transcript, start=0, end=1, text="Hi", speaker="A"
    )
    signed_in(client, person)
    told = client.get(reverse("record-state", args=[recording.pk])).json()
    assert told["state"] == "ready" and told["viewer"] == f"/recording/{recording.pk}"


def test_the_measured_speed_comes_from_finished_jobs(on, person, a_case):
    for length, took in ((600, 10), (1200, 20)):
        rec = Recording.objects.create(
            batch=Batch.objects.create(user=person),
            user=person,
            title="t",
            original_filename="t.m4a",
            duration_seconds=length,
        )
        job = Job.objects.create(recording=rec, batch=rec.batch, state=JobState.DONE)
        Job.objects.filter(pk=job.pk).update(
            created=timezone.now() - timedelta(seconds=took), finished=timezone.now()
        )
    assert live.measured_speed() == pytest.approx(60.0, rel=0.05)


# The Provenance ----------------------------------------------------------------------


def test_the_provenance_says_recorded_live(on, person, a_case, client):
    recording = live.start(person, a_case, browser="Edge 130")
    live.ended(recording, how="stop", pauses=[{"at": 65, "seconds": 12}], seconds=300)
    recording.refresh_from_db()
    told = dict(live.provenance_rows(recording))
    assert (
        told["Recorded live"]
        == "On the Record page, from the microphone; ended by Stop"
    )
    assert told["Recorded with"] == "Edge 130" and told["Pauses"] == "at 1:05 for 12 s"
    # The case row says where it stands while it is on its way.
    recording.media_state = MediaState.CHECKING
    recording.save()
    signed_in(client, person)
    page = client.get(reverse("case", args=[a_case.pk])).content.decode()
    assert "Preparing the sound." in page
