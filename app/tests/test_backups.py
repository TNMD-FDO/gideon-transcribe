"""Backup and restore: the app's five commands and what the pages read.

The store, restic and the host timers are the script's; what runs here is the
preflight, the manifest, the two records and their audit rows, the Status
line's colours, the hourly overdue tests, the after-restore step, and the
drill's checks against a manifest.
"""

from __future__ import annotations

import json
from datetime import timedelta
from io import StringIO

import pytest
from core import backups, settings_store
from core.audit import Row
from core.backups import BackupStatus
from core.cases import Case, OffSpell
from core.jobs import Job, JobState, Segment, Transcript
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording
from django.core.management import call_command
from django.utils import timezone

PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"
    return tmp_path


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setenv("BACKUP_TARGET", "sftp:backup@store:/gideon-backup")
    monkeypatch.setenv("BACKUP_TIME", "02:00")
    monkeypatch.setenv("RELEASE_TAG", "v1.19.0")


@pytest.fixture
def owner(db):
    return User.objects.create_local_admin("case-owner", PASSWORD)


def test_off_when_the_target_is_empty(monkeypatch):
    monkeypatch.delenv("BACKUP_TARGET", raising=False)
    assert not backups.is_on()
    ok, why = backups.preflight()
    assert not ok and "off" in why
    line = backups.status_for_the_panel()
    assert line["colour"] == "red" and "off" in line["says"]


@pytest.mark.django_db
def test_preflight_passes_with_room_and_fails_under_the_floor(on, monkeypatch):
    # The runner's disk is whatever it is; the floor is what is under test.
    monkeypatch.setattr(settings_store, "minimum_free_disk_bytes", lambda: 0)
    ok, why = backups.preflight()
    assert ok and why == "ok"
    monkeypatch.setattr(settings_store, "minimum_free_disk_bytes", lambda: 10**18)
    ok, why = backups.preflight()
    assert not ok and why == "disk_full"


@pytest.mark.django_db
def test_the_manifest_counts_rows_and_hashes_the_cases_files(on, owner, tmp_path):
    case = Case.objects.create(owner=owner, name="Ramirez")
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=owner),
        user=owner,
        case=case,
        title="Call",
        original_filename="call.m4a",
        media_state=MediaState.READY,
    )
    recording.folder.mkdir(parents=True)
    (recording.folder / "original.m4a").write_bytes(b"sound")
    (tmp_path / "backup").mkdir()
    (tmp_path / "backup" / "nightly-2026-09-05.dump").write_bytes(b"x" * 10)

    out = StringIO()
    call_command("write_manifest", stdout=out)
    assert "manifest written" in out.getvalue()
    manifest = json.loads((tmp_path / "backup" / "manifest.json").read_text())
    assert manifest["release"] == "v1.19.0"
    assert manifest["migration"].startswith("00")
    assert manifest["dump"] == "nightly-2026-09-05.dump" and manifest["dump_size"] == 10
    assert manifest["tables"]["core_case"] == 1
    import hashlib

    path = f"{case.pk}/{recording.pk}/original.m4a"
    assert manifest["files"][path] == hashlib.sha256(b"sound").hexdigest()
    assert len(manifest["files"]) == 1


@pytest.mark.django_db
def test_a_run_is_recorded_on_the_status_row_and_in_the_audit_log(on, tmp_path):
    call_command(
        "record_backup",
        "ok",
        "--duration",
        "41.2",
        "--dump-bytes",
        "1000",
        "--snapshot-bytes",
        "5000",
        "--held",
        "3",
    )
    status = BackupStatus.the_one()
    assert status.last_snapshot_ok and status.snapshots_held == 3
    row = Row.objects.get(category="system", event="Backup ran")
    assert row.details["snapshots_held"] == 3 and row.details["dump_bytes"] == 1000
    line = backups.status_for_the_panel()
    assert line["colour"] == "plain" and "3 held" in line["says"]
    assert "next run" in line["says"]
    last = json.loads((tmp_path / "backup" / "last-run.json").read_text())
    assert last["ok"] is True

    call_command(
        "record_backup", "failed", "--step", "snapshot", "--reason", "snapshot_failed"
    )
    status.refresh_from_db()
    assert not status.last_snapshot_ok and status.last_good_snapshot_at is not None
    row = Row.objects.get(category="system", event="Backup failed")
    assert row.reason_class == "snapshot_failed" and row.details["step"] == "snapshot"
    line = backups.status_for_the_panel()
    assert line["colour"] == "red" and "snapshot_failed" in line["says"]
    assert "failed at" in backups._last_run_words()


@pytest.mark.django_db
def test_an_old_snapshot_and_a_late_drill_turn_the_line_red_and_amber(on):
    status = BackupStatus.the_one()
    status.last_snapshot_at = status.last_good_snapshot_at = timezone.now() - timedelta(
        hours=30
    )
    status.last_snapshot_ok = True
    status.save()
    line = backups.status_for_the_panel()
    assert line["colour"] == "red" and "no successful Snapshot since" in line["says"]
    said = backups.watch()
    assert said == ["snapshot"]
    assert Row.objects.filter(event="Backup overdue").count() == 1
    # Once a day, not once an hour.
    assert backups.watch() == []

    status.last_snapshot_at = status.last_good_snapshot_at = timezone.now()
    status.last_drill_at = timezone.now() - timedelta(days=40)
    status.last_drill_ok = True
    status.overdue_said_on = None
    status.save()
    line = backups.status_for_the_panel()
    assert line["colour"] == "amber" and "overdue" in line["drill"]
    assert backups.watch() == ["drill"]
    assert Row.objects.filter(event="Restore drill overdue").count() == 1


@pytest.mark.django_db
def test_a_drill_is_recorded_either_way(on):
    call_command("record_drill", "ok", "--duration", "300")
    assert BackupStatus.the_one().last_drill_ok
    assert "passed" in backups.status_for_the_panel()["drill"]
    call_command(
        "record_drill", "failed", "--step", "table core_case: 3 rows, manifest says 4"
    )
    row = Row.objects.filter(category="system", event="Restore drill ran").latest("at")
    assert row.reason_class == "drill_failed" and "core_case" in row.details["step"]
    assert backups.status_for_the_panel()["colour"] == "red"


@pytest.mark.django_db
def test_after_restore_ends_sessions_fails_jobs_and_records_the_outage(
    on, owner, client
):
    client.force_login(owner)
    LoginSession.objects.create(user=owner, session_key=client.session.session_key)
    settings_store.set_to("folder_management", True)
    case = Case.objects.create(owner=owner, name="Ramirez")
    batch = Batch.objects.create(user=owner)
    in_case = Recording.objects.create(
        batch=batch, user=owner, case=case, title="Call", original_filename="c.m4a"
    )
    running = Job.objects.create(recording=in_case, batch=batch, state=JobState.RUNNING)
    workspace = Recording.objects.create(
        batch=batch, user=owner, title="Mine", original_filename="m.m4a"
    )
    Job.objects.create(recording=workspace, batch=batch, state=JobState.QUEUED)
    when = timezone.now() - timedelta(days=2)

    out = StringIO()
    call_command("after_restore", "abc123", when.isoformat(), stdout=out)
    report = out.getvalue()
    assert "sessions_ended: 1" in report
    assert "jobs_failed_as_restored: 1" in report
    running.refresh_from_db()
    assert running.state == JobState.FAILED and running.failure_class == "restored"
    assert LoginSession.objects.filter(ended__isnull=True).count() == 0
    spell = OffSpell.objects.get(cause=OffSpell.RESTORE)
    assert spell.started == when and spell.ended is not None
    row = Row.objects.get(category="system", event="Restore completed")
    assert row.details["snapshot"] == "abc123" and row.details["cases"] == 1
    assert row.details["integrity_unbroken"] is True


@pytest.mark.django_db
def test_the_drill_check_names_what_differs(on, owner, tmp_path):
    case = Case.objects.create(owner=owner, name="Ramirez")
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=owner),
        user=owner,
        case=case,
        title="Call",
        original_filename="call.m4a",
        media_state=MediaState.READY,
    )
    transcript = Transcript.objects.create(recording=recording, language="en")
    Segment.objects.create(
        transcript=transcript, start=0, end=1, text="Hi", speaker="A"
    )
    recording.folder.mkdir(parents=True)
    (recording.folder / "original.m4a").write_bytes(b"sound")
    manifest = backups.write_manifest()
    assert backups.drill_check(manifest, tmp_path / "cases") == []

    (recording.folder / "original.m4a").write_bytes(b"changed")
    manifest["tables"]["core_case"] = 2
    failures = backups.drill_check(manifest, tmp_path / "cases")
    assert any("core_case" in one for one in failures)
    assert any("original.m4a" in one and "differs" in one for one in failures)

    # Nothing restored is a failure, not a vacuous pass.
    assert backups.drill_check({}, tmp_path / "cases") != []
    with pytest.raises(SystemExit):
        call_command(
            "drill_check", str(tmp_path / "absent.json"), str(tmp_path / "cases")
        )

    manifest_file = tmp_path / "m.json"
    manifest_file.write_text(json.dumps(manifest))
    out = StringIO()
    with pytest.raises(SystemExit):
        call_command(
            "drill_check", str(manifest_file), str(tmp_path / "cases"), stdout=out
        )


@pytest.mark.django_db
def test_the_installation_rows_never_carry_a_secret(on):
    rows = dict(backups.installation_rows())
    assert rows["Backup target"] == "sftp:backup@store:/gideon-backup"
    assert "30 nightly" in rows["Backup keep rule"]
    assert rows["Backup last run"] == "none recorded yet"
    assert "Operator address" in rows


def test_the_preflight_command_exits_one_when_off(monkeypatch):
    monkeypatch.delenv("BACKUP_TARGET", raising=False)
    out = StringIO()
    with pytest.raises(SystemExit):
        call_command("backup_preflight", stdout=out)
    assert "off" in out.getvalue()
