"""The app's side of Backup and restore: what the nightly job asks the app.

The nightly job runs on the host (`./transcribe backup`) and uses restic to
push the Backup set to the store. The app's part is five commands the job
calls inside the `app` container: the preflight, the manifest, the record of
the run, the record of a drill, and the after-restore step. This module is
what those commands do, and what the Status and Installation pages read.
Nothing here touches the store: the app never holds the repository password
or the key, and the store is reached only by restic on the host.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import timedelta
from pathlib import Path

from django.conf import settings as django_settings
from django.db import connection, models
from django.utils import timezone

from core import audit, settings_store

# The Status page's colours: a Snapshot is overdue after this long, a drill
# after this many days past its month.
SNAPSHOT_OVERDUE = timedelta(hours=26)
DRILL_OVERDUE_DAYS = 3

REASONS = (
    "disk_full",
    "dump_failed",
    "manifest_failed",
    "target_unreachable",
    "snapshot_failed",
    "prune_failed",
    "check_failed",
    "drill_failed",
)


class BackupStatus(models.Model):
    """One row: the last Snapshot and the last drill, for the Status page."""

    last_snapshot_at = models.DateTimeField(null=True, blank=True)
    last_snapshot_ok = models.BooleanField(default=False)
    last_snapshot_reason = models.CharField(max_length=40, blank=True, default="")
    last_snapshot_step = models.CharField(max_length=40, blank=True, default="")
    last_good_snapshot_at = models.DateTimeField(null=True, blank=True)
    snapshot_size_bytes = models.BigIntegerField(default=0)
    snapshots_held = models.IntegerField(default=0)
    last_drill_at = models.DateTimeField(null=True, blank=True)
    last_drill_ok = models.BooleanField(default=False)
    last_drill_step = models.CharField(max_length=80, blank=True, default="")
    overdue_said_on = models.DateField(null=True, blank=True)

    @classmethod
    def the_one(cls) -> BackupStatus:
        row, _ = cls.objects.get_or_create(pk=1)
        return row


# What .env says -----------------------------------------------------------------------


def target() -> str:
    return os.environ.get("BACKUP_TARGET", "").strip()


def is_on() -> bool:
    return bool(target())


def shown_target() -> str:
    """The account and host, never the key: `sftp:backup@store:/folder`."""
    return target() or "not set (backups are off)"


def keep_days() -> int:
    return int(os.environ.get("BACKUP_KEEP_DAYS", "30") or 30)


def local_dumps() -> int:
    return int(os.environ.get("BACKUP_LOCAL_DUMPS", "7") or 7)


def backup_time() -> str:
    return os.environ.get("BACKUP_TIME", "02:00") or "02:00"


def drill_time() -> str:
    return os.environ.get("DRILL_TIME", "04:00") or "04:00"


def operator_email() -> str:
    return os.environ.get("OPERATOR_EMAIL", "").strip()


def backup_folder() -> Path:
    return Path(django_settings.DATA_DIR) / "backup"


def cases_folder() -> Path:
    return Path(django_settings.DATA_DIR) / "cases"


# The preflight ------------------------------------------------------------------------


def preflight() -> tuple[bool, str]:
    """Free space above the floor and a target named.

    The two backup secrets are the host's to check, in `./transcribe backup`,
    because they are never mounted into any container of the live stack: the
    app has no business holding the repository password or the store's key.
    """
    if not is_on():
        return False, "BACKUP_TARGET is empty, so backups are off"
    usage = shutil.disk_usage(django_settings.DATA_DIR)
    if usage.free < settings_store.minimum_free_disk_bytes():
        return False, "disk_full"
    return True, "ok"


# The manifest -------------------------------------------------------------------------


def row_counts() -> dict[str, int]:
    """A row count per table, for the drill to check the restored dump against."""
    counts: dict[str, int] = {}
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
            "ORDER BY tablename"
        )
        tables = [row[0] for row in cursor.fetchall()]
        for table in tables:
            cursor.execute(f'SELECT count(*) FROM "{table}"')
            counts[table] = cursor.fetchone()[0]
    return counts


def file_hashes(root: Path) -> dict[str, str]:
    """A sha256 per file under cases/, by its path relative to cases/."""
    hashes: dict[str, str] = {}
    if not root.exists():
        return hashes
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        hashes[path.relative_to(root).as_posix()] = digest.hexdigest()
    return hashes


def migration_number() -> str:
    from django.db.migrations.recorder import MigrationRecorder

    latest = (
        MigrationRecorder.Migration.objects.filter(app="core")
        .order_by("-name")
        .values_list("name", flat=True)
        .first()
    )
    return latest or ""


def write_manifest(dump: Path | None = None) -> dict:
    """backup/manifest.json: what the Snapshot holds, for the drill to check."""
    folder = backup_folder()
    folder.mkdir(parents=True, exist_ok=True)
    dump = dump or newest_dump()
    manifest = {
        "release": _checkout_tag(),
        "migration": migration_number(),
        "whisperx_version": _service_version(),
        "written_at": timezone.now().isoformat(),
        "dump": dump.name if dump else "",
        "dump_size": dump.stat().st_size if dump and dump.exists() else 0,
        "tables": row_counts(),
        "files": file_hashes(cases_folder()),
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def _service_version() -> str:
    """The WhisperX service's own version, asked of it; empty when it is down."""
    try:
        from core import whisperx

        return str((whisperx.status().get("versions") or {}).get("service", ""))
    except Exception:  # noqa: BLE001 - a manifest is written whether or not it answers
        return ""


def _checkout_tag() -> str:
    return os.environ.get("RELEASE_TAG", "")


def newest_dump() -> Path | None:
    dumps = sorted(backup_folder().glob("nightly-*.dump"))
    return dumps[-1] if dumps else None


def read_manifest(path: Path | None = None) -> dict:
    path = path or backup_folder() / "manifest.json"
    return json.loads(path.read_text()) if path.exists() else {}


# The records --------------------------------------------------------------------------


def record_backup(
    *,
    ok: bool,
    step: str = "",
    reason: str = "",
    duration: float = 0.0,
    dump_size: int = 0,
    snapshot_size: int = 0,
    held: int = 0,
) -> BackupStatus:
    """The end of a nightly job: the Status line and the System audit row."""
    status = BackupStatus.the_one()
    now = timezone.now()
    status.last_snapshot_at = now
    status.last_snapshot_ok = ok
    status.last_snapshot_reason = "" if ok else (reason or "snapshot_failed")
    status.last_snapshot_step = "" if ok else step
    if ok:
        status.last_good_snapshot_at = now
        status.snapshot_size_bytes = snapshot_size
        status.snapshots_held = held
        status.overdue_said_on = None
    status.save()
    if ok:
        audit.write(
            audit.Category.SYSTEM,
            "Backup ran",
            system="transcribe backup",
            duration_seconds=round(duration, 1),
            dump_bytes=dump_size,
            snapshot_bytes=snapshot_size,
            snapshots_held=held,
        )
    else:
        audit.write(
            audit.Category.SYSTEM,
            "Backup failed",
            system="transcribe backup",
            outcome=audit.Outcome.FAILURE,
            reason_class=status.last_snapshot_reason,
            step=step,
        )
    _write_last_run(
        {
            "at": now.isoformat(),
            "ok": ok,
            "step": step,
            "reason": status.last_snapshot_reason,
            "duration_seconds": round(duration, 1),
            "dump_bytes": dump_size,
            "snapshot_bytes": snapshot_size,
            "snapshots_held": held,
        }
    )
    return status


def record_drill(*, ok: bool, step: str = "", duration: float = 0.0) -> BackupStatus:
    status = BackupStatus.the_one()
    status.last_drill_at = timezone.now()
    status.last_drill_ok = ok
    status.last_drill_step = "" if ok else step
    status.save()
    audit.write(
        audit.Category.SYSTEM,
        "Restore drill ran",
        system="transcribe restore-drill",
        outcome=audit.Outcome.SUCCESS if ok else audit.Outcome.FAILURE,
        reason_class="" if ok else "drill_failed",
        step=step,
        duration_seconds=round(duration, 1),
    )
    return status


def _write_last_run(record: dict) -> None:
    try:
        folder = backup_folder()
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "last-run.json").write_text(json.dumps(record, indent=2))
    except OSError:
        pass


# The Status page's line ---------------------------------------------------------------


def next_run() -> str:
    """When the nightly timer fires next, from BACKUP_TIME, in the office's day."""
    hour, minute = (int(part) for part in backup_time().split(":")[:2])
    now = timezone.localtime()
    when = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if when <= now:
        when += timedelta(days=1)
    return when.strftime("%a %H:%M")


def status_for_the_panel() -> dict:
    """The Backup line: red, amber or plain, with its words."""
    if not is_on():
        return {
            "colour": "red",
            "says": "off: BACKUP_TARGET is empty, so nothing is backed up",
            "drill": "",
        }
    status = BackupStatus.the_one()
    now = timezone.now()
    local = timezone.localtime
    colour = "plain"
    if status.last_snapshot_at is None:
        says = f"no Snapshot yet; the first runs {next_run()}"
        colour = "amber"
    elif not status.last_snapshot_ok:
        says = (
            f"failed {local(status.last_snapshot_at):%a %H:%M} "
            f"({status.last_snapshot_reason}{_at(status.last_snapshot_step)}); "
            f"next run {next_run()}"
        )
        colour = "red"
    else:
        says = (
            f"last Snapshot {local(status.last_snapshot_at):%a %H:%M}, "
            f"{_gb(status.snapshot_size_bytes)} in the repository, "
            f"{status.snapshots_held} held; next run {next_run()}"
        )
    if (
        status.last_good_snapshot_at is not None
        and now - status.last_good_snapshot_at > SNAPSHOT_OVERDUE
    ):
        colour = "red"
        since = local(status.last_good_snapshot_at)
        says += f"; no successful Snapshot since {since:%a %H:%M}"
    if status.last_drill_at is None:
        drill = "no drill yet"
    elif not status.last_drill_ok:
        step = status.last_drill_step or "an unnamed step"
        drill = f"failed {local(status.last_drill_at):%d %b} at {step}"
        colour = "red"
    else:
        drill = f"passed {local(status.last_drill_at):%d %b}"
        if now - status.last_drill_at > timedelta(days=31 + DRILL_OVERDUE_DAYS):
            drill += ", overdue"
            if colour == "plain":
                colour = "amber"
    return {"colour": colour, "says": says, "drill": drill}


def watch() -> list[str]:
    """The hourly overdue tests; the rows they wrote, at most one a day."""
    if not is_on():
        return []
    status = BackupStatus.the_one()
    now = timezone.now()
    today = timezone.localdate()
    said: list[str] = []
    if status.overdue_said_on == today:
        return said
    if (
        status.last_good_snapshot_at is not None
        and now - status.last_good_snapshot_at > SNAPSHOT_OVERDUE
    ) or (status.last_good_snapshot_at is None and status.last_snapshot_at is not None):
        audit.write(
            audit.Category.SYSTEM,
            "Backup overdue",
            system="worker",
            outcome=audit.Outcome.FAILURE,
            reason_class="snapshot_overdue",
            last_good=(
                status.last_good_snapshot_at.isoformat()
                if status.last_good_snapshot_at
                else ""
            ),
        )
        said.append("snapshot")
    if status.last_drill_at is not None and now - status.last_drill_at > timedelta(
        days=31 + DRILL_OVERDUE_DAYS
    ):
        audit.write(
            audit.Category.SYSTEM,
            "Restore drill overdue",
            system="worker",
            outcome=audit.Outcome.FAILURE,
            reason_class="drill_overdue",
            last_drill=status.last_drill_at.isoformat(),
        )
        said.append("drill")
    if said:
        status.overdue_said_on = today
        status.save(update_fields=["overdue_said_on"])
    return said


def _at(step: str) -> str:
    return f", at {step}" if step else ""


def _gb(size: int) -> str:
    return f"{size / (1024**3):.1f} GB"


def installation_rows() -> list[tuple[str, str]]:
    """The read-only rows for the Installation page; never a secret's value."""
    return [
        ("Backup target", shown_target()),
        (
            "Backup schedule",
            f"nightly {backup_time()}; weekly check and monthly drill {drill_time()}",
        ),
        (
            "Backup keep rule",
            f"{keep_days()} nightly Snapshots on the store, "
            f"{local_dumps()} dumps on the box",
        ),
        # The two secrets are never mounted into the stack; the nightly job
        # on the host checks them and the last run's record says what it found.
        ("Backup last run", _last_run_words()),
        ("Operator address", operator_email() or "not set (no Operator mail)"),
    ]


def _last_run_words() -> str:
    try:
        record = json.loads((backup_folder() / "last-run.json").read_text())
    except (OSError, ValueError):
        return "none recorded yet"
    when = record.get("at", "")[:16].replace("T", " ")
    if record.get("ok"):
        return f"ok at {when}"
    reason = record.get("reason") or "unknown"
    step = record.get("step") or "unnamed step"
    return f"failed at {when}: {reason} ({step})"


# The after-restore step ---------------------------------------------------------------


def after_restore(snapshot_id: str, snapshot_at) -> dict:
    """What a restored app does first: the chapter's five acts, in one place.

    Every Login session ends and every Workspace is discarded (their files
    were never copied); every Case-bound Job that was Queued or Running at
    the Snapshot is failed with the reason class `restored`, keeping its
    files and its Retry; the outage is an Off spell with cause `restore`
    unless the toggle spell already covers it; the Integrity check runs; and
    the "Restore completed" row is written with the counts.
    """
    from core import lifecycle
    from core.cases import Case, OffSpell, folder_management_on
    from core.jobs import Job, JobState
    from core.models import LoginSession
    from core.recordings import Recording

    now = timezone.now()
    ended = LoginSession.objects.filter(ended__isnull=True).update(ended=now)
    discarded = 0
    from core.models import User

    for user in User.objects.all():
        removed, _ = lifecycle.discard(user)
        discarded += removed

    failed = 0
    for job in Job.objects.filter(
        state__in=(JobState.QUEUED, JobState.RUNNING),
        recording__case__isnull=False,
    ):
        job.state = JobState.FAILED
        job.failure_class = "restored"
        job.finished = now
        job.save(update_fields=["state", "failure_class", "finished"])
        failed += 1

    spell = None
    if (
        OffSpell.objects.filter(ended__isnull=True).exists()
        and not folder_management_on()
    ):
        spell = "covered by the open toggle spell"
    elif snapshot_at is not None and snapshot_at < now:
        OffSpell.objects.create(started=snapshot_at, ended=now, cause=OffSpell.RESTORE)
        spell = f"{snapshot_at.isoformat()} to {now.isoformat()}"

    integrity = audit.check_integrity()
    manifest = read_manifest()
    cases = Case.objects.filter(deleted_on__isnull=True).count()
    recordings = Recording.objects.filter(case__isnull=False).count()
    total = sum((one.disk_bytes() for one in Case.objects.all()), 0)
    report = {
        "snapshot": snapshot_id,
        "snapshot_at": snapshot_at.isoformat() if snapshot_at else "",
        "sessions_ended": ended,
        "workspaces_discarded": discarded,
        "jobs_failed_as_restored": failed,
        "off_spell": spell or "none",
        "integrity_unbroken": bool(integrity.get("unbroken")),
        "cases": cases,
        "case_recordings": recordings,
        "case_gigabytes": round(total / (1024**3), 1),
        "tables_match_manifest": _tables_match(manifest),
    }
    audit.write(
        audit.Category.SYSTEM,
        "Restore completed",
        system="transcribe restore",
        **{key: value for key, value in report.items() if key != "snapshot_at"},
        snapshot_at=report["snapshot_at"],
    )
    return report


def _tables_match(manifest: dict) -> str:
    wanted = manifest.get("tables") or {}
    if not wanted:
        return "no manifest to compare"
    have = row_counts()
    off = {
        table: (count, have.get(table))
        for table, count in wanted.items()
        if have.get(table) != count
    }
    return "every table" if not off else f"{len(off)} tables differ: {sorted(off)[:5]}"


def drill_check(manifest: dict, cases_root: Path) -> list[str]:
    """The drill's four checks against the manifest; the failures, in words."""
    failures: list[str] = []
    have = row_counts()
    for table, count in (manifest.get("tables") or {}).items():
        if have.get(table) != count:
            failures.append(
                f"table {table}: {have.get(table)} rows, manifest says {count}"
            )
    hashes = file_hashes(cases_root)
    for path, digest in (manifest.get("files") or {}).items():
        if hashes.get(path) != digest:
            failures.append(
                f"file {path}: {'missing' if path not in hashes else 'differs'}"
            )
    from core.recordings import Recording

    for recording in Recording.objects.filter(case__isnull=False):
        folder = cases_root / str(recording.case_id) / str(recording.pk)
        if not folder.exists():
            failures.append(f"recording {recording.pk} has rows and no folder")
    if not audit.check_integrity().get("unbroken"):
        failures.append("the audit log's hash chain is broken")
    return failures
