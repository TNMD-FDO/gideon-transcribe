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
