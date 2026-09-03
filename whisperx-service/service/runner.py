"""The supervisor: it keeps one model process, and feeds it the line.

The parent never imports torch. It starts the child, hands it one job at a
time, watches what comes back, and kills it when a job has to stop. That is
what makes a cancel take seconds instead of the rest of an hour, and what
keeps a driver fault from taking the API down with it.
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import queue
import threading
import time
from datetime import datetime
from typing import Any

from service import errors
from service.models_file import Models
from service.settings import Settings
from service.store import Store

log = logging.getLogger("whisperx.runner")

# How long to wait for the child to say it is ready before giving up on it.
READY_SECONDS = 600.0

# How often the loop looks for work when there is none.
IDLE_SECONDS = 0.5


class Runner:
    """One model process, one job at a time, for as long as the service runs."""

    def __init__(self, settings: Settings, store: Store, models: Models) -> None:
        self.settings = settings
        self.store = store
        self.models = models

        self._context = mp.get_context("spawn")
        self._process: mp.process.BaseProcess | None = None
        self._inbox: Any = None
        self._outbox: Any = None

        self._lock = threading.Lock()
        self._card: dict[str, Any] = {"uuid": None, "name": None}
        self._vram = {"vram_used_gb": None, "vram_free_gb": None}
        self._loaded: dict[str, Any] | None = None
        self._cancelling: set[str] = set()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # What the API asks it ----------------------------------------------------

    def alive(self) -> bool:
        process = self._process
        return bool(process and process.is_alive())

    def loaded_model(self) -> dict[str, Any] | None:
        with self._lock:
            return dict(self._loaded) if self._loaded else None

    def gpu(self) -> dict[str, Any]:
        with self._lock:
            return {**self._card, **self._vram}

    def cancel(self, job_id: str) -> None:
        """Stop a running job by killing the process that holds it.

        Nothing inside the engine can be asked to stop, so this is the only
        way. The card is free within seconds, and the next job pays for one
        model load.
        """
        with self._lock:
            self._cancelling.add(job_id)
        running = self.store.running()
        if running and running.id == job_id:
            log.info("cancelling job %s by killing the model process", job_id)
            self._kill()

    # Running -----------------------------------------------------------------

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._kill()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:  # noqa: BLE001 - the loop must not die
                log.exception("the runner loop stumbled")
                time.sleep(IDLE_SECONDS)

    def _tick(self) -> None:
        if not self.alive():
            self._spawn()

        job = self.store.take_next()
        if job is None:
            self._drain(timeout=IDLE_SECONDS)
            return

        log.info(
            "job %s started for %s: %.1f minutes of audio, model %s, diarize %s",
            job.id,
            job.consumer,
            job.audio_seconds / 60,
            job.model,
            job.diarize,
        )
        queued = _seconds_between(job.created, job.started)
        self._inbox.put(
            {
                "job_id": job.id,
                "request": job.request,
                "audio_path": job.audio_path,
                "result_path": str(self.settings.results_dir / f"{job.id}.json"),
                "queued_seconds": queued,
                "audio": {
                    "duration_seconds": round(job.audio_seconds, 3),
                    "sample_rate": None,
                    "channels": None,
                },
            }
        )
        self._watch(job.id, self.settings.timeout_seconds(job.audio_seconds))

    def _watch(self, job_id: str, timeout: float) -> None:
        """Follow one job until it ends, one way or another."""
        deadline = time.monotonic() + timeout
        while not self._stop.is_set():
            if not self.alive():
                # The process went, which means either a cancel or a fault.
                self._after_death(job_id)
                return

            if time.monotonic() > deadline:
                log.warning("job %s ran past its time limit", job_id)
                self.store.fail(
                    job_id,
                    errors.TIMEOUT,
                    "the job ran past the time allowed for its length",
                )
                self._kill()
                return

            message = self._next(timeout=1.0)
            if message is None:
                continue
            if message["type"] == "result":
                self.store.finish(job_id, message["path"], message["wall_seconds"])
                log.info(
                    "job %s done in %.1fs, video memory peaked at %s GB",
                    job_id,
                    message["wall_seconds"],
                    message.get("peak_vram_gb"),
                )
                return
            if message["type"] == "failure":
                self._failed(job_id, message["reason_class"], message["message"])
                return

    def _failed(self, job_id: str, reason_class: str, message: str) -> None:
        if reason_class in errors.RETRIED:
            # A card fault is worth one more attempt, but only with a fresh
            # process: whatever upset the driver is still in this one.
            self._kill()
            if self.store.retry(job_id):
                log.warning(
                    "job %s hit %s and goes back for one more try",
                    job_id,
                    reason_class,
                )
                return
        log.warning("job %s failed: %s (%s)", job_id, reason_class, message)
        self.store.fail(job_id, reason_class, message)

    def _after_death(self, job_id: str) -> None:
        """The process is gone while a job was in it."""
        with self._lock:
            cancelled = job_id in self._cancelling
            self._cancelling.discard(job_id)
        if cancelled:
            # The API has already marked it cancelled.
            return
        self._failed(job_id, errors.GPU_ERROR, "the model process stopped")

    # The child ---------------------------------------------------------------

    def _spawn(self) -> None:
        from service import model_process

        self._inbox = self._context.Queue()
        self._outbox = self._context.Queue()
        self._process = self._context.Process(
            target=model_process.run,
            args=(self._inbox, self._outbox, self._child_settings()),
            daemon=True,
        )
        self._process.start()
        log.info("model process started")

        waited = time.monotonic()
        while time.monotonic() - waited < READY_SECONDS:
            message = self._next(timeout=1.0)
            if message and message["type"] == "ready":
                with self._lock:
                    self._card = message["card"]
                return
            if not self.alive():
                log.error("the model process stopped before it was ready")
                return

    def _child_settings(self) -> dict[str, Any]:
        return {
            "batch_size": self.settings.batch_size,
            "vad_onset": self.settings.vad_onset,
            "vad_offset": self.settings.vad_offset,
            "diarization_model": self.models.diarization.repository,
            "model_revisions": {
                model.name: model.revision for model in self.models.models
            },
        }

    def _kill(self) -> None:
        process = self._process
        if process and process.is_alive():
            process.kill()
            process.join(timeout=30)
        self._process = None
        with self._lock:
            self._loaded = None

    def _next(self, timeout: float) -> dict[str, Any] | None:
        """The next message from the child, handling the ones the loop owns."""
        try:
            message = self._outbox.get(timeout=timeout)
        except (queue.Empty, OSError, ValueError):
            return None

        if message["type"] == "gpu":
            with self._lock:
                self._vram = {
                    "vram_used_gb": message["used_gb"],
                    "vram_free_gb": message["free_gb"],
                }
            return None
        if message["type"] == "loaded":
            with self._lock:
                self._loaded = {
                    "model": message["model"],
                    "revision": message.get("revision"),
                }
            return None
        if message["type"] == "stage":
            self.store.set_stage(
                message["job_id"], message["stage"], message["percent"]
            )
            return None
        return message

    def _drain(self, timeout: float) -> None:
        self._next(timeout=timeout)


def _seconds_between(first: str | None, second: str | None) -> float:
    if not first or not second:
        return 0.0
    waited = datetime.fromisoformat(second) - datetime.fromisoformat(first)
    return round(waited.total_seconds(), 3)
