"""The robustness pass of 14 October 2026 (v1.132.0): the rules it fixed, kept.

A service answer in the wrong shape is a service error and never a stalled
merge or a Job queued for ever; a lane that did not answer leaves its Runs
alone; a slow answer is given more polls than a refused one; the nightly
sweeps run at half past three in the office's time; a job that stopped its
worker twice is failed; a playback copy that never came is asked for again;
a full disk is named; a complete upload whose finish never came is taken in;
a number from a request is finite; the Status page reads the workers'
heartbeats and says when the engine's check has stopped; a backup timer that
never fires is overdue a day later; the pages keep their rules.
"""

from __future__ import annotations

import errno
import json
import subprocess
from datetime import timedelta
from pathlib import Path

import pytest
from core import (
    backups,
    chronology,
    documents,
    engine,
    media,
    numbers,
    panel_pages,
    pipeline,
    queue,
    settings_store,
    tasks,
    uploads,
    whisperx,
)
from core.cases import Case
from core.jobs import Job, JobState, Reason, Run, Transcript
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording, Side
from django.conf import settings as django_settings
from django.utils import timezone

PASSWORD = "a-long-enough-password"
HERE = Path(__file__).resolve().parent.parent.parent
STATIC = HERE / "app" / "static"


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


def a_recording(person, case=None, *, state=MediaState.READY, **more):
    return Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        case=case,
        title=more.pop("title", "one"),
        original_filename="one.mp4",
        media_state=state,
        **more,
    )


def a_job(recording, *, service_job_id="s1", lane="", state=JobState.QUEUED):
    side = recording.sides.first() or Side.objects.create(
        recording=recording, number=1, kind=Side.WHOLE, name=""
    )
    job = Job.objects.create(recording=recording, batch=recording.batch, state=state)
    Run.objects.create(job=job, side=side, service_job_id=service_job_id, lane=lane)
    return job


class FakeAnswer:
    def __init__(self, body: bytes, status: int = 200):
        self.body = body
        self.status = status

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


# The service client ----------------------------------------------------------


def test_a_200_that_is_not_json_is_a_service_error(monkeypatch):
    monkeypatch.setattr(
        whisperx.urllib.request,
        "urlopen",
        lambda request, timeout=0: FakeAnswer(b"<html>proxy page</html>"),
    )
    with pytest.raises(whisperx.ServiceError) as told:
        whisperx._request("GET", "/v1/jobs")
    assert told.value.reason_class == "internal"


def test_a_submit_answer_without_an_id_is_a_service_error(monkeypatch, tmp_path):
    audio = tmp_path / "side.wav"
    audio.write_bytes(b"RIFF")
    monkeypatch.setattr(whisperx, "_request", lambda *a, **k: (200, {"position": 1}))
    with pytest.raises(whisperx.ServiceError):
        whisperx.submit(audio, {})
    monkeypatch.setattr(
        whisperx, "_request", lambda *a, **k: (200, ["not", "a", "dict"])
    )
    with pytest.raises(whisperx.ServiceError):
        whisperx.submit(audio, {})


def test_an_empty_job_list_is_empty_and_odd_entries_are_left_out(monkeypatch):
    monkeypatch.setattr(whisperx, "_request", lambda *a, **k: (200, {}))
    assert whisperx.jobs() == []
    monkeypatch.setattr(
        whisperx,
        "_request",
        lambda *a, **k: (
            200,
            {
                "jobs": [
                    {"id": "a", "state": "running"},
                    {"id": "b"},
                    "x",
                    {"state": "d"},
                ]
            },
        ),
    )
    assert whisperx.jobs() == [{"id": "a", "state": "running"}]


# The merge, the hand-over and the poll ---------------------------------------


def test_a_fetch_that_fails_in_the_apps_code_fails_the_job(person, a_case, monkeypatch):
    recording = a_recording(person, a_case)
    old = Transcript.objects.create(recording=recording, language="en")
    job = a_job(recording)

    def boom(job_id, lane=""):
        raise RuntimeError("a slip")

    monkeypatch.setattr(whisperx, "result", boom)
    monkeypatch.setattr(whisperx, "delete", lambda job_id, lane="": None)
    told = queue.merge(job)
    assert told.state == JobState.FAILED and told.failure_class == Reason.INTERNAL
    assert Transcript.objects.filter(pk=old.pk).exists()


def test_a_hand_over_that_fails_in_the_apps_code_fails_the_job(
    person, a_case, monkeypatch
):
    recording = a_recording(person, a_case)
    job = a_job(recording, service_job_id="")

    def boom(audio, request, lane=""):
        raise KeyError("id")

    monkeypatch.setattr(whisperx, "submit", boom)
    monkeypatch.setattr(whisperx, "lane_for", lambda recording: "")
    told = queue.hand_over(job)
    assert told.state == JobState.FAILED and told.failure_class == Reason.INTERNAL


def test_a_lane_that_did_not_answer_leaves_its_runs_alone(person, a_case, monkeypatch):
    recording = a_recording(person, a_case)
    job = a_job(recording, service_job_id="fast1", lane="fast")
    monkeypatch.setattr(whisperx, "delete", lambda job_id, lane="": None)
    for _ in range(queue.POLLS_BEFORE_MISSING + 2):
        queue.take_state_from(job, {}, silent_lanes=frozenset({"fast"}))
    job.refresh_from_db()
    assert job.state == JobState.QUEUED
    assert job.runs.get().missing_polls == 0


def test_the_poll_reads_odd_entries_without_dying(person, a_case, monkeypatch):
    recording = a_recording(person, a_case)
    job = a_job(recording, service_job_id="s1")
    monkeypatch.setattr(whisperx, "delete", lambda job_id, lane="": None)
    queue.take_state_from(
        job, {"s1": {"state": "running", "percent": "n/a", "position": None}}
    )
    run = job.runs.get()
    assert run.state == "running" and run.percent is None and run.position is None


def test_a_slow_answer_is_given_more_polls_than_a_refused_one(
    person, a_case, monkeypatch
):
    recording = a_recording(person, a_case)
    job = a_job(recording)
    again = []
    monkeypatch.setattr(
        tasks, "_poll_again", lambda attempt, when=3: again.append(attempt)
    )

    def slow():
        raise whisperx.ServiceError("the request timed out", "service_unreachable")

    monkeypatch.setattr(whisperx, "jobs", slow)
    monkeypatch.setattr(whisperx, "fast_lane_configured", lambda: False)
    monkeypatch.setattr(whisperx, "delete", lambda job_id, lane="": None)
    tasks.poll_service(attempt=queue.POLLS_BEFORE_GIVING_UP)
    job.refresh_from_db()
    assert job.state == JobState.QUEUED and again == [queue.POLLS_BEFORE_GIVING_UP + 1]
    tasks.poll_service(attempt=queue.POLLS_BEFORE_GIVING_UP_ON_A_SLOW_ANSWER)
    job.refresh_from_db()
    assert job.state == JobState.FAILED


# The sweeps at half past three, office time ----------------------------------


def test_the_nightly_sweeps_run_at_three_in_the_offices_time(monkeypatch):
    from core import audit, retention, sweeping

    ran = []
    monkeypatch.setattr(retention, "sweep", lambda: ran.append("retention"))
    monkeypatch.setattr(
        __import__("core.dictation", fromlist=["sweep"]), "sweep", lambda: None
    )
    monkeypatch.setattr(audit, "sweep", lambda months: ran.append("audit"))
    monkeypatch.setattr(sweeping, "sweep", lambda: ran.append("disk"))

    class Clock:
        hour = 22

    monkeypatch.setattr("django.utils.timezone.localtime", lambda *a, **k: Clock())
    tasks.retention_sweep(0)
    tasks.sweep_audit_log(0)
    tasks.sweep_the_disk(0)
    assert ran == []
    Clock.hour = 3
    tasks.retention_sweep(0)
    tasks.sweep_audit_log(0)
    tasks.sweep_the_disk(0)
    assert ran == ["retention", "audit", "disk"]


def test_a_job_that_stopped_its_worker_twice_is_failed():
    import asyncio

    class FakeJob:
        def __init__(self, attempts):
            self.id = 1
            self.task_name = "read_document"
            self.attempts = attempts

    seen = {"retried": [], "failed": []}

    class Manager:
        async def get_stalled_jobs(self):
            return [FakeJob(1), FakeJob(2)]

        async def retry_job(self, job):
            seen["retried"].append(job.attempts)

        async def finish_job(self, job, status, delete_job):
            seen["failed"].append((job.attempts, status.value, delete_job))

    original = tasks.app.job_manager
    tasks.app.job_manager = Manager()
    try:
        asyncio.run(tasks.retry_stalled_jobs.func(0))
    finally:
        tasks.app.job_manager = original
    assert seen == {"retried": [1], "failed": [(2, "failed", False)]}


# The media worker's edges ----------------------------------------------------


def test_a_playback_copy_that_never_came_is_asked_for_again(person, a_case):
    old = timezone.now() - timedelta(hours=1)
    waiting = a_recording(person, a_case, playback_ready=False)
    Recording.objects.filter(pk=waiting.pk).update(created=old)
    given_up = a_recording(person, a_case, playback_ready=False, playback_tries=3)
    Recording.objects.filter(pk=given_up.pk).update(created=old)
    done = a_recording(person, a_case, playback_ready=True)
    Recording.objects.filter(pk=done.pk).update(created=old)
    assert list(queue.without_a_playback_copy()) == [waiting]


def test_a_full_disk_is_named_and_offers_retry(monkeypatch, person, a_case):
    finished = subprocess.CompletedProcess(["ffmpeg"], 1, stdout="", stderr="No space")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: finished)
    monkeypatch.setattr(uploads, "free_disk_bytes", lambda: 0)
    with pytest.raises(media.MediaError) as told:
        media._run(["ffmpeg", "-i", "x"], timeout=1)
    assert told.value.reason_class == "server_disk_full"
    recording = a_recording(person, a_case, state=MediaState.CHECKING)
    failed = pipeline._failed(recording, told.value)
    assert failed.media_state == MediaState.FAILED
    assert "disk is full" in failed.failure_message


def test_a_document_read_on_a_full_disk_says_so_plainly(person, a_case, monkeypatch):
    document = documents.Document.objects.create(
        case=a_case, title="r", original_filename="r.pdf"
    )

    def boom(document):
        raise OSError(errno.ENOSPC, "No space left on device", "/srv/data/x")

    monkeypatch.setattr(documents, "_read", boom)
    documents.read(str(document.pk))
    document.refresh_from_db()
    assert document.error == "The server's disk is full. Tell IT."
    assert "/srv" not in document.error


# Uploads ---------------------------------------------------------------------


def test_a_finish_that_cannot_store_the_file_fails_the_row(person, a_case, tmp_path):
    recording = a_recording(person, a_case, state=MediaState.CHECKING)
    missing = tmp_path / "uploads" / "gone"
    assert not uploads.take_in(recording, missing)
    recording.refresh_from_db()
    assert recording.media_state == MediaState.FAILED
    assert recording.failure_message == "The upload could not be stored. Try again."


def test_a_complete_upload_whose_finish_never_came_is_taken_in(
    person, a_case, tmp_path, monkeypatch
):
    from core.tasks import prepare_recording

    deferred = []
    monkeypatch.setattr(prepare_recording, "defer", lambda **f: deferred.append(f))
    recording = a_recording(person, a_case, state=MediaState.UPLOADING)
    (tmp_path / "uploads" / "whole").write_bytes(b"x" * 500)
    (tmp_path / "uploads" / "whole.info").write_text(
        json.dumps({"Size": 500, "MetaData": {"recording": str(recording.pk)}}),
        encoding="utf-8",
    )
    half = a_recording(person, a_case, state=MediaState.UPLOADING, title="half")
    (tmp_path / "uploads" / "part").write_bytes(b"x" * 100)
    (tmp_path / "uploads" / "part.info").write_text(
        json.dumps({"Size": 500, "MetaData": {"recording": str(half.pk)}}),
        encoding="utf-8",
    )
    assert uploads.finish_the_complete() == 1
    recording.refresh_from_db()
    half.refresh_from_db()
    assert recording.media_state == MediaState.CHECKING
    assert recording.original_path.exists() and len(deferred) == 1
    assert half.media_state == MediaState.UPLOADING


def test_the_sidecar_notes_a_live_uploads_id_itself(person, a_case, client):
    from core import live

    settings_store.set_to("live_recording", True)
    signed_in(client, person)
    recording = live.start(person, a_case)
    body = {
        "Type": "post-create",
        "Event": {
            "Upload": {
                "ID": "abc123",
                "MetaData": {"recording": str(recording.pk), "live": "1"},
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
    client.post(
        "/upload-hook/",
        json.dumps(body),
        "application/json",
        HTTP_HOOK_NAME="post-create",
    )
    recording.refresh_from_db()
    assert recording.live["tus_id"] == "abc123"


# Numbers from a request ------------------------------------------------------


def test_a_number_from_a_request_is_finite_and_in_range():
    assert numbers.finite("12.5") == 12.5
    assert numbers.finite(" -3 ", least=-10) == -3.0
    assert numbers.finite("nan") is None
    assert numbers.finite("inf") is None
    assert numbers.finite("1e400") is None
    assert numbers.finite("", least=0) is None
    assert numbers.finite(None) is None
    assert numbers.finite(True) is None
    assert numbers.finite("5", least=0, most=4) is None
    assert chronology.a_moment("nan") is None and chronology.a_moment("12") == 12.0


def test_a_placement_that_is_not_a_number_is_refused(person, a_case, client):
    from core import incidents

    first = a_recording(person, a_case, title="first", duration_seconds=600.0)
    second = a_recording(person, a_case, title="second", duration_seconds=600.0)
    incident = incidents.make(a_case, "Stop", [first, second], by=person)
    camera = incident.cameras.get(recording=second)
    signed_in(client, person)
    for bad in ("nan", "inf", "-inf", "1e400", ""):
        told = client.post(
            f"{incident.url()}/act",
            {
                "action": "place",
                "camera": str(camera.pk),
                "how": "hand",
                "starts_at": bad,
            },
        )
        assert told.status_code == 400, bad
    state = client.get(f"{incident.url()}/state")
    assert state.status_code == 200
    json.loads(state.content)


def test_odd_values_on_the_audit_log_and_the_preview_are_not_crashes(
    person, a_case, client
):
    signed_in(client, person)
    assert client.get("/panel/audit", {"since": "14/10/2026"}).status_code == 200
    assert client.get("/panel/audit", {"until": "2025-02-29"}).status_code == 200
    assert client.get("/panel/audit", {"page": "last"}).status_code == 200
    recording = a_recording(person, a_case, duration_seconds=60.0)
    Transcript.objects.create(recording=recording, language="en")
    told = client.get(f"/recording/{recording.pk}/around", {"t": "1e400"})
    assert told.status_code == 200


# The Status page -------------------------------------------------------------


def test_the_workers_row_reads_the_heartbeats(db):
    row = panel_pages._workers()
    assert row["name"] == "workers" and row["state"] == "not running"
    assert row["says"].startswith("0 of 3 alive")
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO procrastinate_workers (last_heartbeat) "
            "VALUES (now()), (now()), (now())"
        )
    row = panel_pages._workers()
    assert row["state"] == "healthy" and row["says"].startswith("3 of 3 alive")


def test_the_engines_line_says_when_its_check_has_stopped(db, monkeypatch):
    monkeypatch.setattr(engine, "configured", lambda: True)
    status = engine.EngineStatus.the_one()
    status.record(True, served_models=["m"], window_tokens=1000)
    assert engine.status_for_the_panel()["state"] == "reachable"
    engine.EngineStatus.objects.filter(pk=status.pk).update(
        checked_at=timezone.now() - timedelta(minutes=10)
    )
    told = engine.status_for_the_panel()
    assert told["state"] == "unknown" and "engine worker" in told["says"]


def test_a_backup_timer_that_never_fires_is_overdue_a_day_later(monkeypatch, db):
    from core import mail

    monkeypatch.setattr(backups, "is_on", lambda: True)
    monkeypatch.setattr(mail, "backup_overdue", lambda last: None)
    status = backups.BackupStatus.the_one()
    assert backups.watch() == []
    status.refresh_from_db()
    assert status.watched_since is not None
    backups.BackupStatus.objects.filter(pk=status.pk).update(
        watched_since=timezone.now() - timedelta(hours=30)
    )
    assert backups.watch() == ["snapshot"]


# The pages, the script and the stack -----------------------------------------


def test_the_cookie_reader_matches_a_cookie_that_is_not_first():
    for name in (
        "clearing.js",
        "clips.js",
        "panel-directory.js",
        "panel-queue.js",
        "recordings.js",
    ):
        text = (STATIC / name).read_text(encoding="utf-8")
        assert '"(^|;)\\\\s*" + name + "\\\\s*=\\\\s*([^;]+)"' in text, name


def test_the_pages_keep_their_rules():
    speakers = (STATIC / "speakers-page.js").read_text(encoding="utf-8")
    assert "suggestTimer = window.setTimeout(refreshSuggestions, 6000)" in speakers
    record = (STATIC / "record.js").read_text(encoding="utf-8")
    assert 'addEventListener("ended"' in record and 'endNow("device")' in record
    assert "function sendTheEnd" in record and "function noteTheId" in record
    incident = (STATIC / "incident.js").read_text(encoding="utf-8")
    assert "if (!isFinite(moved)) { return; }" in incident
    assert "aboutBox && !aboutBox.hidden" in incident
    upload = (STATIC / "upload.js").read_text(encoding="utf-8")
    assert "byName[index] = one.id" in upload and "findPreviousUploads" in upload
    viewer = (STATIC / "viewer.js").read_text(encoding="utf-8")
    assert "function buildRow" in viewer and viewer.count("redrawRow(segment);") == 3
    chat = (STATIC / "chat-ui.js").read_text(encoding="utf-8")
    assert "The app did not take the question" in chat


def test_the_script_and_the_stack_keep_their_rules():
    script = (HERE / "transcribe").read_text(encoding="utf-8")
    rollback = script[script.index("cmd_rollback() {") :]
    rollback = rollback[: rollback.index("cmd_restore_dump() {")]
    assert 'set_env RELEASE_TAG "$tag"' in rollback
    assert "compose up -d --remove-orphans" in rollback and "running_jobs" in rollback
    assert "compose run --rm --no-deps app python manage.py migrate" in script
    assert "status = 'doing'" in script
    compose = (HERE / "compose.yaml").read_text(encoding="utf-8")
    assert compose.count("stop_grace_period: 10m") == 3
    assert "pre-create,post-create,post-finish" in compose
    assert "-hooks-http-retry=10" in compose
    entrypoint = (HERE / "app" / "entrypoint.sh").read_text(encoding="utf-8")
    assert entrypoint.count("--shutdown-graceful-timeout 540") == 3
    assert "--worker-class gthread" in entrypoint


def test_a_download_is_streamed_from_a_spool():
    from core import exports

    spool = exports.spool()
    spool.write(b"zip bytes")
    answer = exports.hand_over_file(spool, "a b.zip", "application/zip")
    assert answer.status_code == 200
    assert answer["Content-Disposition"] == "attachment; filename*=UTF-8''a%20b.zip"
    assert b"".join(answer.streaming_content) == b"zip bytes"
