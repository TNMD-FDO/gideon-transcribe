"""The line: one job at a time, in arrival order, across every Consumer.

This is the only place the one-at-a-time rule is enforced, which is why it
lives in the service and not in any application that uses it. A second
Consumer cannot transcribe beside the first, because both stand in this line.

The line is a SQLite database on the service's own folder, so a restart keeps
every queued job and its order. Audio and results are files beside it, because
a database is a poor place for either: the audio goes the moment a job ends,
and a result goes when it is collected or when its day is up.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import closing, suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from service import errors
from service.settings import Settings

QUEUED = "queued"
RUNNING = "running"
DONE = "done"
FAILED = "failed"
CANCELLED = "cancelled"

# The states a job can still leave. Everything else has ended.
LIVE = (QUEUED, RUNNING)

# The stages a running job passes through, in the words the contract fixes. A
# Consumer turns these into whatever its own users read.
STAGES = ("loading model", "transcribing", "aligning", "diarizing", "finishing")

# How many finished jobs the speed figure averages over.
SPEED_WINDOW = 10

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    sequence          INTEGER PRIMARY KEY AUTOINCREMENT,
    id                TEXT    NOT NULL UNIQUE,
    consumer          TEXT    NOT NULL,
    client_reference  TEXT,
    state             TEXT    NOT NULL,
    stage             TEXT,
    percent           REAL,
    attempt           INTEGER NOT NULL DEFAULT 1,
    request           TEXT    NOT NULL,
    audio_path        TEXT,
    audio_seconds     REAL    NOT NULL,
    model             TEXT    NOT NULL,
    diarize           INTEGER NOT NULL,
    created           TEXT    NOT NULL,
    started           TEXT,
    finished          TEXT,
    failure_class     TEXT,
    failure_message   TEXT,
    result_path       TEXT,
    result_deleted    INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS jobs_by_state ON jobs (state, sequence);
CREATE INDEX IF NOT EXISTS jobs_by_consumer ON jobs (consumer, sequence);

CREATE TABLE IF NOT EXISTS completions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    model          TEXT NOT NULL,
    diarize        INTEGER NOT NULL,
    audio_seconds  REAL NOT NULL,
    wall_seconds   REAL NOT NULL,
    finished       TEXT NOT NULL
);
"""


def now() -> str:
    """The time, in UTC, in the one form the API ever shows."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def _age(stamp: str | None) -> timedelta | None:
    if not stamp:
        return None
    return datetime.now(UTC) - datetime.fromisoformat(stamp)


@dataclass(frozen=True)
class Job:
    """One row of the line."""

    sequence: int
    id: str
    consumer: str
    client_reference: str | None
    state: str
    stage: str | None
    percent: float | None
    attempt: int
    request: dict[str, Any]
    audio_path: str | None
    audio_seconds: float
    model: str
    diarize: bool
    created: str
    started: str | None
    finished: str | None
    failure_class: str | None
    failure_message: str | None
    result_path: str | None
    result_deleted: bool

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Job:
        return cls(
            sequence=row["sequence"],
            id=row["id"],
            consumer=row["consumer"],
            client_reference=row["client_reference"],
            state=row["state"],
            stage=row["stage"],
            percent=row["percent"],
            attempt=row["attempt"],
            request=json.loads(row["request"]),
            audio_path=row["audio_path"],
            audio_seconds=row["audio_seconds"],
            model=row["model"],
            diarize=bool(row["diarize"]),
            created=row["created"],
            started=row["started"],
            finished=row["finished"],
            failure_class=row["failure_class"],
            failure_message=row["failure_message"],
            result_path=row["result_path"],
            result_deleted=bool(row["result_deleted"]),
        )

    @property
    def ended(self) -> bool:
        return self.state not in LIVE


class Store:
    """Every read and write of the line goes through here."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        settings.state_dir.mkdir(parents=True, exist_ok=True)
        settings.audio_dir.mkdir(parents=True, exist_ok=True)
        settings.results_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._db = sqlite3.connect(
            settings.database_file,
            check_same_thread=False,
            isolation_level=None,
        )
        self._db.row_factory = sqlite3.Row
        # Write-ahead logging, so a reader is never blocked by the writer, and
        # a full flush on every commit, because losing the line is worse than
        # being slow at it.
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # Reading -----------------------------------------------------------------

    def _one(self, sql: str, parameters: tuple[Any, ...] = ()) -> Job | None:
        with closing(self._db.execute(sql, parameters)) as cursor:
            row = cursor.fetchone()
        return Job.from_row(row) if row else None

    def _many(self, sql: str, parameters: tuple[Any, ...] = ()) -> list[Job]:
        with closing(self._db.execute(sql, parameters)) as cursor:
            return [Job.from_row(row) for row in cursor.fetchall()]

    def job(self, job_id: str) -> Job | None:
        with self._lock:
            return self._one("SELECT * FROM jobs WHERE id = ?", (job_id,))

    def job_for(self, job_id: str, consumer: str, admin: bool) -> Job:
        """A job, or 404.

        A job belongs to the token that made it. Any other regular token is
        told the job does not exist, rather than that it may not have it: a
        Consumer has no business learning that another Consumer's job is
        there.
        """
        job = self.job(job_id)
        if job is None or (not admin and job.consumer != consumer):
            raise errors.not_found()
        return job

    def jobs_for(self, consumer: str, admin: bool, limit: int = 200) -> list[Job]:
        with self._lock:
            if admin:
                return self._many(
                    "SELECT * FROM jobs ORDER BY sequence DESC LIMIT ?", (limit,)
                )
            return self._many(
                "SELECT * FROM jobs WHERE consumer = ? ORDER BY sequence DESC LIMIT ?",
                (consumer, limit),
            )

    def ahead_of(self, job: Job) -> tuple[int, float]:
        """How many jobs are in front of this one, and their audio minutes.

        Both count every Consumer's jobs, not just this one's, because the line
        is shared. The running job counts as one of them: it is in front of
        this job in every sense that matters to somebody waiting.
        """
        if job.ended:
            return 0, 0.0
        with (
            self._lock,
            closing(
                self._db.execute(
                    "SELECT COUNT(*) AS jobs, "
                    "COALESCE(SUM(audio_seconds), 0) AS seconds "
                    "FROM jobs WHERE state IN (?, ?) AND sequence < ?",
                    (QUEUED, RUNNING, job.sequence),
                )
            ) as cursor,
        ):
            row = cursor.fetchone()
        return row["jobs"], row["seconds"] / 60.0

    def queue_length(self) -> tuple[int, float]:
        """Everything waiting or running, and its audio minutes."""
        with (
            self._lock,
            closing(
                self._db.execute(
                    "SELECT COUNT(*) AS jobs, "
                    "COALESCE(SUM(audio_seconds), 0) AS seconds "
                    "FROM jobs WHERE state IN (?, ?)",
                    (QUEUED, RUNNING),
                )
            ) as cursor,
        ):
            row = cursor.fetchone()
        return row["jobs"], row["seconds"] / 60.0

    def running(self) -> Job | None:
        with self._lock:
            return self._one("SELECT * FROM jobs WHERE state = ? LIMIT 1", (RUNNING,))

    def duplicate_of(self, consumer: str, client_reference: str | None) -> Job | None:
        """A job this Consumer already has with the same reference.

        Only a job still in the line counts. A Consumer that submits the same
        reference again gets that job's status instead of a second job, which
        is what makes a retried submission safe.
        """
        if not client_reference:
            return None
        with self._lock:
            return self._one(
                "SELECT * FROM jobs WHERE consumer = ? AND client_reference = ? "
                "AND state IN (?, ?) ORDER BY sequence LIMIT 1",
                (consumer, client_reference, QUEUED, RUNNING),
            )

    # Writing -----------------------------------------------------------------

    def add(
        self,
        consumer: str,
        request: dict[str, Any],
        audio_path: Path,
        audio_seconds: float,
    ) -> Job:
        """Put a job at the end of the line."""
        job_id = uuid.uuid4().hex
        with self._lock:
            self._db.execute(
                "INSERT INTO jobs (id, consumer, client_reference, state, request, "
                "audio_path, audio_seconds, model, diarize, created) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    job_id,
                    consumer,
                    request.get("client_reference"),
                    QUEUED,
                    json.dumps(request),
                    str(audio_path),
                    audio_seconds,
                    request.get("model", "large-v3"),
                    1 if request.get("diarize") else 0,
                    now(),
                ),
            )
            job = self._one("SELECT * FROM jobs WHERE id = ?", (job_id,))
        assert job is not None
        return job

    def take_next(self) -> Job | None:
        """The job whose turn it is, marked as running. None when the line is empty.

        Nothing else may run while one job is running, so this refuses to hand
        out a second.
        """
        with self._lock:
            if self._one("SELECT * FROM jobs WHERE state = ? LIMIT 1", (RUNNING,)):
                return None
            job = self._one(
                "SELECT * FROM jobs WHERE state = ? ORDER BY sequence LIMIT 1",
                (QUEUED,),
            )
            if job is None:
                return None
            self._db.execute(
                "UPDATE jobs SET state = ?, stage = ?, started = ? WHERE id = ?",
                (RUNNING, STAGES[0], now(), job.id),
            )
            return self._one("SELECT * FROM jobs WHERE id = ?", (job.id,))

    def set_stage(self, job_id: str, stage: str, percent: float | None = None) -> None:
        if stage not in STAGES:
            raise ValueError(f"unknown stage {stage!r}")
        with self._lock:
            self._db.execute(
                "UPDATE jobs SET stage = ?, percent = ? WHERE id = ? AND state = ?",
                (stage, percent, job_id, RUNNING),
            )

    def finish(self, job_id: str, result_path: Path, wall_seconds: float) -> None:
        """A job that worked. Its audio goes now; its result waits to be fetched."""
        with self._lock:
            job = self._one("SELECT * FROM jobs WHERE id = ?", (job_id,))
            if job is None:
                return
            self._db.execute(
                "UPDATE jobs SET state = ?, stage = NULL, percent = NULL, "
                "finished = ?, result_path = ?, audio_path = NULL WHERE id = ?",
                (DONE, now(), str(result_path), job_id),
            )
            self._db.execute(
                "INSERT INTO completions (model, diarize, audio_seconds, "
                "wall_seconds, finished) VALUES (?, ?, ?, ?, ?)",
                (
                    job.model,
                    1 if job.diarize else 0,
                    job.audio_seconds,
                    wall_seconds,
                    now(),
                ),
            )
        _remove(job.audio_path)

    def fail(self, job_id: str, reason_class: str, message: str) -> None:
        if reason_class not in errors.REASON_CLASSES:
            raise ValueError(f"unknown reason class {reason_class!r}")
        self._end(job_id, FAILED, reason_class, message)

    def cancel(self, job_id: str) -> None:
        self._end(job_id, CANCELLED, errors.CANCELLED, "cancelled by its Consumer")

    def _end(self, job_id: str, state: str, reason_class: str, message: str) -> None:
        with self._lock:
            job = self._one("SELECT * FROM jobs WHERE id = ?", (job_id,))
            if job is None or job.ended:
                return
            self._db.execute(
                "UPDATE jobs SET state = ?, stage = NULL, percent = NULL, "
                "finished = ?, failure_class = ?, failure_message = ?, "
                "audio_path = NULL WHERE id = ?",
                (state, now(), reason_class, message, job_id),
            )
        _remove(job.audio_path)

    def retry(self, job_id: str) -> bool:
        """Put a job back at the head of the line for its second attempt.

        Used for a CUDA fault, which is worth one more go after the model
        process has been reloaded, and for a job that a service restart
        interrupted. A job that has already had its second attempt is not
        retried again.
        """
        with self._lock:
            job = self._one("SELECT * FROM jobs WHERE id = ?", (job_id,))
            if job is None or job.attempt >= errors.MAX_ATTEMPTS:
                return False
            self._db.execute(
                "UPDATE jobs SET state = ?, stage = NULL, percent = NULL, "
                "started = NULL, attempt = attempt + 1 WHERE id = ?",
                (QUEUED, job_id),
            )
        return True

    def remove(self, job_id: str) -> None:
        """Delete a finished job and everything it left behind."""
        with self._lock:
            job = self._one("SELECT * FROM jobs WHERE id = ?", (job_id,))
            if job is None:
                return
            self._db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        _remove(job.audio_path)
        _remove(job.result_path)

    # Starting up and tidying -------------------------------------------------

    def recover(self) -> list[str]:
        """Put the line back in order after the service stopped.

        A job that was running when the service stopped goes back to the head
        of the line once. A job interrupted a second time fails: something
        about it is stopping the service, and running it again would stop it
        again.
        """
        recovered: list[str] = []
        with self._lock:
            interrupted = self._many(
                "SELECT * FROM jobs WHERE state = ? ORDER BY sequence", (RUNNING,)
            )
        for job in interrupted:
            if self.retry(job.id):
                recovered.append(job.id)
            else:
                self.fail(
                    job.id,
                    errors.SERVICE_RESTARTED,
                    "the service restarted while this job was running",
                )
        return recovered

    def sweep(self) -> tuple[int, int]:
        """Drop results past their hours and rows past their days.

        A result holds transcript text, so it goes first and soon: a day after
        it was made, fetched or not. The row that is left holds no text at all,
        only what an admin needs to work out what happened, and it goes after
        its own month.
        """
        results = 0
        rows = 0
        with self._lock:
            waiting = self._many(
                "SELECT * FROM jobs WHERE result_path IS NOT NULL "
                "AND result_deleted = 0"
            )
        for job in waiting:
            age = _age(job.finished)
            if age and age > timedelta(hours=self.settings.result_hours):
                _remove(job.result_path)
                with self._lock:
                    self._db.execute(
                        "UPDATE jobs SET result_deleted = 1, result_path = NULL "
                        "WHERE id = ?",
                        (job.id,),
                    )
                results += 1

        with self._lock:
            old = self._many(
                "SELECT * FROM jobs WHERE state NOT IN (?, ?) AND finished IS NOT NULL",
                (QUEUED, RUNNING),
            )
        for job in old:
            age = _age(job.finished)
            if age and age > timedelta(days=self.settings.job_history_days):
                self.remove(job.id)
                rows += 1
        return results, rows

    def last_failure(self) -> tuple[str, str] | None:
        """The most recent failure's class and time, for the status page."""
        with (
            self._lock,
            closing(
                self._db.execute(
                    "SELECT failure_class, finished FROM jobs WHERE state = ? "
                    "AND failure_class IS NOT NULL ORDER BY sequence DESC LIMIT 1",
                    (FAILED,),
                )
            ) as cursor,
        ):
            row = cursor.fetchone()
        if row is None:
            return None
        return row["failure_class"], row["finished"]

    # The measured speed ------------------------------------------------------

    def speed(self, model: str, diarize: bool) -> float | None:
        """Audio minutes finished per wall-clock minute, over the last few jobs.

        The service never says how long a wait will be. It publishes this, and
        a Consumer multiplies it by the audio ahead of its own job, because
        only the Consumer knows what it wants to tell its users.

        None means this service has not yet run enough jobs of this shape to
        say anything honest.
        """
        with (
            self._lock,
            closing(
                self._db.execute(
                    "SELECT audio_seconds, wall_seconds FROM completions "
                    "WHERE model = ? AND diarize = ? ORDER BY id DESC LIMIT ?",
                    (model, 1 if diarize else 0, SPEED_WINDOW),
                )
            ) as cursor,
        ):
            rows = cursor.fetchall()

        if len(rows) < SPEED_WINDOW:
            return None
        audio = sum(row["audio_seconds"] for row in rows)
        wall = sum(row["wall_seconds"] for row in rows)
        if wall <= 0:
            return None
        return audio / wall


def _remove(path: str | None) -> None:
    if not path:
        return
    # A file that will not go is a matter for the journal, not for the Consumer
    # waiting on the answer.
    with suppress(OSError):
        Path(path).unlink(missing_ok=True)
