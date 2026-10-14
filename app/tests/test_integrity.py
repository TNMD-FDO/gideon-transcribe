"""The data integrity pass of 14 October 2026 (v1.131.0): the rules it fixed, kept.

Four ways a person could lose what they had (a paused live recording, a
dictation at sign-out, a transcript on Retry, a transcript on a failed
Process again), two ways a thing was left stuck for ever (a hung ffmpeg, a
writer failing in the app's own code), the sound match's overlap, the
sidecar's count, events that follow their camera, a deleted recording that
came back, one live Job per recording, a Run the service forgot, the claim
on a finish, the floor with the file counted, a report with no home, a local
admin who owns a case, the asked moment below zero, and the writers' guards.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import wave
from datetime import timedelta
from pathlib import Path

import numpy as np
import pytest
from core import (
    assistant,
    incidents,
    lifecycle,
    media,
    pipeline,
    queue,
    settings_store,
    sound_match,
    tasks,
    uploads,
    whisperx,
)
from core.cases import Case
from core.chronology import Event
from core.documents import Document
from core.incident_pages import _asked_moment
from core.jobs import Job, JobState, Reason, Run, Segment, Transcript
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording, Refusal, Side
from django.conf import settings as django_settings
from django.test import RequestFactory
from django.utils import timezone

PASSWORD = "a-long-enough-password"
HERE = Path(__file__).resolve().parent.parent.parent


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


@pytest.fixture(autouse=True)
def switches(db):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("incidents", True)
    settings_store.set_to("live_recording", True)


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("keeper", PASSWORD)


@pytest.fixture
def a_case(person):
    return Case.objects.create(owner=person, name="Harbour")


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def a_recording(person, case=None, *, state=MediaState.READY, live=None, **more):
    return Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        case=case,
        title=more.pop("title", "one"),
        original_filename="one.mp4",
        media_state=state,
        live=live,
        **more,
    )


def with_lines(recording, texts=("one", "two", "three")):
    transcript = Transcript.objects.create(recording=recording, language="en")
    side = Side.objects.create(recording=recording, number=1, kind=Side.WHOLE, name="")
    for n, text in enumerate(texts):
        Segment.objects.create(
            transcript=transcript,
            side=side,
            start=float(n * 10),
            end=float(n * 10 + 5),
            text=text,
            speaker="Speaker 1",
        )
    return transcript


def write_wav(path: Path, samples: np.ndarray, rate: int = 16000) -> None:
    with wave.open(str(path), "wb") as sound:
        sound.setnchannels(1)
        sound.setsampwidth(2)
        sound.setframerate(rate)
        sound.writeframes(np.clip(samples, -32767, 32767).astype(np.int16).tobytes())


# 1. The live recording the sweep leaves alone --------------------------------


def test_a_paused_live_recording_is_not_dropped_as_abandoned(person, a_case, tmp_path):
    old = timezone.now() - timedelta(hours=1)
    live = a_recording(
        person, a_case, state=MediaState.UPLOADING, live={"started": "x"}
    )
    plain = a_recording(person, a_case, state=MediaState.UPLOADING, title="plain")
    Recording.objects.filter(pk__in=[live.pk, plain.pk]).update(created=old)
    for name, recording in (("aaa", live), ("bbb", plain)):
        (tmp_path / "uploads" / f"{name}.info").write_text(
            json.dumps({"MetaData": {"recording": str(recording.pk)}}), encoding="utf-8"
        )
        pieces = tmp_path / "uploads" / name
        pieces.write_bytes(b"x" * 100)
        stale = time.time() - 11 * 60
        os.utime(pieces, (stale, stale))
    dropped = uploads.drop_abandoned()
    assert dropped == 1
    assert Recording.objects.filter(pk=live.pk).exists()
    assert not Recording.objects.filter(pk=plain.pk).exists()


# 2. The discard leaves a dictation's files -----------------------------------


def test_the_discard_leaves_the_dictations_folder(person, tmp_path):
    kept = a_recording(person, is_dictation=True, live={"dictation": True})
    kept.folder.mkdir(parents=True)
    (kept.folder / "original.webm").write_bytes(b"y" * 10)
    gone = a_recording(person, title="workspace")
    gone.folder.mkdir(parents=True)
    (gone.folder / "original.mp4").write_bytes(b"x" * 10)
    LoginSession.objects.filter(user=person).update(ended=timezone.now())
    lifecycle.discard(person)
    assert not Recording.objects.filter(pk=gone.pk).exists()
    assert (kept.folder / "original.webm").exists()
    assert Recording.objects.filter(pk=kept.pk).exists()


# 3 and 4. A transcript survives a Retry and a failed merge -------------------


def test_the_sides_stay_under_a_transcript(person, a_case, monkeypatch):
    recording = a_recording(person, a_case, state=MediaState.FAILED)
    with_lines(recording)
    recording.folder.mkdir(parents=True)
    recording.original_path.write_bytes(b"x")

    class Probed:
        best_track = 0
        duration_seconds = 30.0

    monkeypatch.setattr(media, "probe", lambda path: Probed())
    pipeline._find_sides(recording)
    assert recording.sides.count() == 1
    assert recording.transcript.segments.count() == 3


def test_a_failed_merge_keeps_the_old_transcript(person, a_case, monkeypatch):
    recording = a_recording(person, a_case)
    old = with_lines(recording)
    job = Job.objects.create(recording=recording, batch=recording.batch)
    Run.objects.create(job=job, side=recording.sides.get(), service_job_id="s1")
    monkeypatch.setattr(whisperx, "result", lambda job_id, lane="": None)
    monkeypatch.setattr(whisperx, "delete", lambda job_id, lane="": None)
    told = queue.merge(job)
    assert told.state == JobState.FAILED and told.failure_class == Reason.MERGE_FAILED
    assert Transcript.objects.filter(pk=old.pk).exists()
    assert old.segments.count() == 3


# 5. A hung ffmpeg is a media failure; the app's own error is Failed with Retry ------


def test_a_timeout_is_a_media_failure(monkeypatch):
    def hang(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=1)

    monkeypatch.setattr(subprocess, "run", hang)
    with pytest.raises(media.MediaError) as told:
        media._run(["ffmpeg", "-i", "x"], timeout=1)
    assert told.value.reason_class == "media_timeout"


def test_an_error_in_the_apps_own_code_fails_the_recording_plainly(
    person, a_case, monkeypatch
):
    recording = a_recording(person, a_case, state=MediaState.CHECKING)

    def boom(recording):
        raise RuntimeError("a slip")

    monkeypatch.setattr(pipeline, "_check", boom)
    told = pipeline.prepare(recording)
    assert told.media_state == MediaState.FAILED
    assert told.refusal_class == Reason.INTERNAL
    from core.pages import _can_retry

    assert _can_retry(told, None)


# 10. A cancelled recording never comes back ----------------------------------


def test_a_recording_that_went_is_not_written_back(person, a_case):
    recording = a_recording(person, a_case, state=MediaState.CHECKING)
    Recording.objects.filter(pk=recording.pk).delete()
    recording.media_state = MediaState.READY
    with pytest.raises(pipeline.Gone):
        pipeline._keep(recording)
    assert not Recording.objects.filter(pk=recording.pk).exists()


# 14. The last resort for a writer --------------------------------------------


def test_a_writer_that_fails_in_the_apps_code_is_marked_failed(person, a_case):
    recording = a_recording(person, a_case)
    summary = assistant.Summary.objects.create(
        recording=recording, template_name="t", state=assistant.RUNNING
    )
    with pytest.raises(RuntimeError), tasks.or_failed(assistant.Summary, summary.pk):
        raise RuntimeError("a slip")
    summary.refresh_from_db()
    assert summary.state == assistant.FAILED and summary.reason_class == "internal"
    # A row already done is left as it is.
    done = assistant.Summary.objects.create(
        recording=recording, template_name="t", state=assistant.DONE
    )
    with pytest.raises(RuntimeError), tasks.or_failed(assistant.Summary, done.pk):
        raise RuntimeError("a slip")
    done.refresh_from_db()
    assert done.state == assistant.DONE


# 22. A writer acts only on a row that waits or runs --------------------------


def test_a_finished_summary_is_not_written_again(person, a_case, monkeypatch):
    recording = a_recording(person, a_case)
    with_lines(recording)
    done = assistant.Summary.objects.create(
        recording=recording, template_name="t", state=assistant.DONE, text="kept"
    )

    def never(*args, **kwargs):
        raise AssertionError("the engine was asked")

    from core import engine

    monkeypatch.setattr(engine, "complete", never)
    assistant.write_summary(done.pk)
    done.refresh_from_db()
    assert done.state == assistant.DONE and done.text == "kept"


# 7. The sound match's overlap ------------------------------------------------


def test_a_short_camera_inside_a_long_one_is_matched_where_it_is(tmp_path):
    rng = np.random.default_rng(7)
    rate = 16000
    # Noise whose loudness changes every half second: the matcher reads
    # loudness, and flat noise has nothing to line up.
    gains = np.repeat(rng.uniform(200, 6000, 600), rate // 2)
    long = rng.normal(0, 1, rate * 300) * gains
    start = rate * 60
    short = long[start : start + rate * 90] + rng.normal(0, 300, rate * 90)
    write_wav(tmp_path / "long.wav", long)
    write_wav(tmp_path / "short.wav", short)
    found = sound_match.lag_between(tmp_path / "long.wav", tmp_path / "short.wav")
    assert found.lag == pytest.approx(60.0, abs=0.05)


# 8. The sidecar's count ------------------------------------------------------


def test_a_full_batch_is_not_refused_at_its_first_byte(person, client):
    signed_in(client, person)
    most = settings_store.files_per_batch()
    batch = Batch.objects.create(user=person)
    rows = [
        Recording.objects.create(
            batch=batch,
            user=person,
            title=f"f{n}",
            original_filename=f"f{n}.mp4",
            media_state=MediaState.UPLOADING,
        )
        for n in range(most)
    ]
    body = {
        "Type": "pre-create",
        "Event": {
            "Upload": {
                "ID": "abc",
                "Size": 1000,
                "MetaData": {"recording": str(rows[0].pk)},
            },
            "HTTPRequest": {
                "Header": {
                    "Cookie": [
                        f"{django_settings.SESSION_COOKIE_NAME}={client.session.session_key}"
                    ]
                }
            },
        },
    }
    told = client.post(
        "/upload-hook/",
        json.dumps(body),
        "application/json",
        HTTP_HOOK_NAME="pre-create",
    ).json()
    assert "RejectUpload" not in told, told


# 17. The floor with the file counted -----------------------------------------


def test_the_floor_counts_the_file_about_to_arrive(person, monkeypatch):
    floor = settings_store.minimum_free_disk_bytes()
    monkeypatch.setattr(uploads, "free_disk_bytes", lambda: floor + 1024**3)
    batch = Batch.objects.create(user=person)
    refusal = uploads.check_before_upload(person, batch, 5 * 1024**3, 1)
    assert refusal is not None and refusal.reason_class == Refusal.DISK_FULL
    assert uploads.check_before_upload(person, batch, 1024**2, 1) is None


# 21. The claim on a finish ---------------------------------------------------


def test_a_finish_is_claimed_once(person, a_case):
    recording = a_recording(person, a_case, state=MediaState.UPLOADING)
    assert uploads.claim(recording)
    assert not uploads.claim(recording)
    recording.refresh_from_db()
    assert recording.media_state == MediaState.CHECKING


# 11 and 13. One live Job; a Run the service forgot; Retry on a cancelled Job ----------


def test_one_live_job_per_recording(person, a_case):
    recording = a_recording(person, a_case)
    Side.objects.create(recording=recording, number=1, kind=Side.WHOLE, name="")
    first = queue.make_job(recording)
    second = queue.make_job(recording)
    assert first.pk == second.pk
    assert recording.jobs.count() == 1


def test_a_run_the_service_no_longer_lists_fails_the_job(person, a_case, monkeypatch):
    recording = a_recording(person, a_case)
    side = Side.objects.create(recording=recording, number=1, kind=Side.WHOLE, name="")
    job = Job.objects.create(recording=recording, batch=recording.batch)
    Run.objects.create(job=job, side=side, service_job_id="lost", state="queued")
    monkeypatch.setattr(whisperx, "delete", lambda job_id, lane="": None)
    for _ in range(queue.POLLS_BEFORE_MISSING - 1):
        queue.take_state_from(job, {})
        job.refresh_from_db()
        assert job.state == JobState.QUEUED
    queue.take_state_from(job, {})
    job.refresh_from_db()
    assert job.state == JobState.FAILED
    assert job.failure_class == Reason.SERVICE_RESTARTED
    # A Run that is listed again is counted from nothing.
    other = Job.objects.create(recording=recording, batch=recording.batch)
    run = Run.objects.create(
        job=other, side=side, service_job_id="here", state="queued"
    )
    queue.take_state_from(other, {})
    queue.take_state_from(other, {"here": {"state": "running"}})
    run.refresh_from_db()
    assert run.missing_polls == 0


def test_a_cancelled_job_is_offered_retry(person, a_case):
    from core.pages import _can_retry

    recording = a_recording(person, a_case)
    job = Job.objects.create(
        recording=recording, batch=recording.batch, state=JobState.CANCELLED
    )
    assert _can_retry(recording, job)


def test_a_lost_hand_over_is_found(person, a_case):
    recording = a_recording(person, a_case)
    side = Side.objects.create(recording=recording, number=1, kind=Side.WHOLE, name="")
    job = Job.objects.create(recording=recording, batch=recording.batch)
    Run.objects.create(job=job, side=side)
    assert list(queue.never_handed_over(older_than_seconds=0)) == [job]
    assert list(queue.never_handed_over(older_than_seconds=600)) == []


# 9. Events follow their camera -----------------------------------------------


def test_a_cameras_events_move_with_it(person, a_case):
    first = a_recording(person, a_case, title="first", duration_seconds=600.0)
    second = a_recording(person, a_case, title="second", duration_seconds=600.0)
    incident = incidents.make(a_case, "Stop", [first, second], by=person)
    camera = incident.cameras.get(recording=second)
    incidents.place_by_hand(camera, 600.0, by=person)
    event = Event.objects.create(
        incident=incident, at=1350.0, until=1360.0, text="Gun found", camera=camera
    )
    other = Event.objects.create(incident=incident, at=100.0, text="Elsewhere")
    incidents.place_by_hand(camera, 660.0, by=person)
    event.refresh_from_db()
    other.refresh_from_db()
    assert event.at == 1410.0 and event.until == 1420.0
    assert other.at == 100.0


# 16. The asked moment, below zero --------------------------------------------


def test_the_asked_moment_may_be_below_zero():
    request = RequestFactory().get("/x", {"t": "-284"})
    state = {"incident": {"span_low": -344.0}}
    assert _asked_moment(request, None, state) == -284.0
    assert (
        _asked_moment(RequestFactory().get("/x", {"t": "-900"}), None, state) == -344.0
    )
    assert _asked_moment(request, None, {"incident": {"span_low": 0.0}}) == 0.0


# 19. A report with no other home goes with its incident ----------------------


def test_a_report_about_the_incident_alone_goes_with_it(person, a_case):
    first = a_recording(person, a_case, title="first", duration_seconds=600.0)
    second = a_recording(person, a_case, title="second", duration_seconds=600.0)
    incident = incidents.make(a_case, "Stop", [first, second], by=person)
    alone = Document.objects.create(
        case=a_case, incident=incident, title="alone", original_filename="a.pdf"
    )
    both = Document.objects.create(
        case=a_case,
        incident=incident,
        recording=first,
        title="both",
        original_filename="b.pdf",
    )
    incidents.delete(incident, by=person)
    assert not Document.objects.filter(pk=alone.pk).exists()
    both.refresh_from_db()
    assert both.incident is None and both.recording == first


# 24. Removing a recording gives up its work at the service -------------------


def test_removing_a_recording_cancels_its_runs_at_the_service(
    person, a_case, monkeypatch
):
    recording = a_recording(person, a_case)
    side = Side.objects.create(recording=recording, number=1, kind=Side.WHOLE, name="")
    job = Job.objects.create(
        recording=recording, batch=recording.batch, state=JobState.RUNNING
    )
    Run.objects.create(job=job, side=side, service_job_id="s9", lane="")
    cancelled = []
    monkeypatch.setattr(
        whisperx, "delete", lambda job_id, lane="": cancelled.append(job_id)
    )
    lifecycle.remove_recording(recording, "case owner", actor=person)
    assert cancelled == ["s9"]


# 18. A local admin who owns anything stays -----------------------------------


def test_a_local_admin_who_owns_a_case_is_not_deleted(person, client):
    other = User.objects.create_local_admin("other", PASSWORD)
    Case.objects.create(owner=other, name="Theirs")
    signed_in(client, person)
    client.post("/panel/users/other", {"action": "delete"})
    assert User.objects.filter(username="other").exists()


# 20. The deferrals that wait for the commit ----------------------------------


def test_the_three_worker_deferrals_wait_for_the_commit():
    core = HERE / "app" / "core"
    assert "after_commit" in (core / "mail.py").read_text(encoding="utf-8")
    assert "after_commit" in (core / "live.py").read_text(encoding="utf-8")
    assert "after_commit" in (core / "assistant.py").read_text(encoding="utf-8")
