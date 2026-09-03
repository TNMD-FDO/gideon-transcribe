"""The API under /v1/, and the unauthenticated liveness check beside it.

Async throughout, because an hour-long job outlasts any proxy's patience:
submit returns at once with a place in the line, the Consumer polls, fetches
the result, and deletes the job.

Nothing in this module imports torch or whisperx. The engine lives behind the
runner, which is a separate process, so the API can be tested without a card.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from service import errors, pins
from service.audio import Audio, probe
from service.auth import Tokens, bearer
from service.models_file import Models
from service.settings import Settings
from service.store import DONE, Job, Store
from service.submission import read as read_submission
from service.tokens import Consumer
from service.version import API_VERSION, SERVICE_VERSION

# How much of an upload is read at a time.
CHUNK = 1024 * 1024


class Runner(Protocol):
    """What the API needs from whatever is actually running jobs."""

    def alive(self) -> bool: ...

    def loaded_model(self) -> dict[str, Any] | None: ...

    def gpu(self) -> dict[str, Any]: ...

    def cancel(self, job_id: str) -> None: ...


async def _receive(audio: UploadFile, path: Path, limit: int) -> int:
    written = 0
    try:
        with path.open("wb") as handle:
            while True:
                block = await audio.read(CHUNK)
                if not block:
                    break
                written += len(block)
                if written > limit:
                    raise errors.too_large(
                        f"the body is over the limit of {limit / 1024**3:.0f} GB"
                    )
                handle.write(block)
    except errors.ServiceError:
        path.unlink(missing_ok=True)
        raise
    except OSError:
        path.unlink(missing_ok=True)
        raise errors.ServiceError(500, "the upload could not be stored") from None

    if written == 0:
        path.unlink(missing_ok=True)
        raise errors.bad_input("the audio part is empty")
    return written


def status_body(store: Store, job: Job) -> dict[str, Any]:
    """The status of one job, as every polling Consumer reads it."""
    position, minutes_ahead = store.ahead_of(job)
    body: dict[str, Any] = {
        "id": job.id,
        "client_reference": job.client_reference,
        "consumer": job.consumer,
        "state": job.state,
        "stage": job.stage,
        "percent": job.percent,
        "position": position,
        "audio_minutes_ahead": round(minutes_ahead, 2),
        "created": job.created,
        "started": job.started,
        "finished": job.finished,
        "attempt": job.attempt,
    }
    if job.failure_class:
        body["failure"] = {
            "reason_class": job.failure_class,
            "message": job.failure_message,
        }
    return body


def create_app(
    settings: Settings,
    store: Store,
    tokens: Tokens,
    models: Models,
    runner: Runner,
    probe_audio: Callable[[Path], Audio] = probe,
) -> FastAPI:
    """Build the app.

    `probe_audio` is passed in so that the tests can run anywhere. Everything
    else here is plain Python, and reading a file's length is the one thing
    that needs a program on the server.
    """
    app = FastAPI(
        title="WhisperX service",
        version=SERVICE_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    started_at = time.monotonic()

    @app.exception_handler(errors.ServiceError)
    async def _refused(request: Request, error: errors.ServiceError) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content=error.body())

    def caller(request: Request) -> Consumer:
        consumer = tokens.consumer_for(bearer(request.headers.get("authorization")))
        if consumer is None:
            raise errors.unauthorised()
        return consumer

    # Submit ------------------------------------------------------------------

    @app.post("/v1/jobs", status_code=202)
    async def submit(
        request: Request,
        audio: UploadFile = File(...),
        payload: str = Form(alias="request"),
    ) -> JSONResponse:
        consumer = caller(request)

        try:
            body = json.loads(payload)
        except json.JSONDecodeError:
            raise errors.invalid("the request part is not JSON") from None

        submission = read_submission(body, models.names)

        model = models.named(submission.model)
        if model is None or not models.is_cached(model):
            raise errors.model_unavailable(
                f"the model {submission.model} is not in the model folder. "
                "Run the pull command"
            )
        # A job that asks for speakers must find the diarization model here and
        # not after an hour of transcription.
        if submission.diarize and not models.is_cached(models.diarization):
            raise errors.model_unavailable(
                "the diarization model is not in the model folder. Run the pull "
                "command, which needs the HuggingFace token and the accepted "
                "licence together"
            )

        waiting = store.duplicate_of(consumer.name, submission.client_reference)
        if waiting is not None:
            # The same reference twice is a Consumer retrying, not a second
            # recording. It gets the job it already has.
            return JSONResponse(status_code=200, content=status_body(store, waiting))

        path = settings.audio_dir / f"{consumer.name}-{time.time_ns()}"
        await _receive(audio, path, settings.max_upload_bytes)

        try:
            facts = probe_audio(path)
            if facts.duration_seconds > settings.max_audio_seconds:
                hours = settings.max_audio_seconds / 3600
                raise errors.too_long(
                    f"the audio is {facts.duration_seconds / 3600:.1f} hours "
                    f"long, and the most is {hours:.0f}"
                )
        except errors.ServiceError:
            path.unlink(missing_ok=True)
            raise

        job = store.add(
            consumer.name, submission.as_json(), path, facts.duration_seconds
        )
        position, minutes_ahead = store.ahead_of(job)
        return JSONResponse(
            status_code=202,
            content={
                "id": job.id,
                "position": position,
                "audio_minutes_ahead": round(minutes_ahead, 2),
            },
        )

    # Poll, fetch, delete, list ----------------------------------------------

    @app.get("/v1/jobs")
    async def jobs(request: Request) -> dict[str, Any]:
        consumer = caller(request)
        found = store.jobs_for(consumer.name, consumer.admin)
        return {"jobs": [status_body(store, job) for job in found]}

    @app.get("/v1/jobs/{job_id}")
    async def job_status(request: Request, job_id: str) -> dict[str, Any]:
        consumer = caller(request)
        job = store.job_for(job_id, consumer.name, consumer.admin)
        return status_body(store, job)

    @app.get("/v1/jobs/{job_id}/result")
    async def job_result(request: Request, job_id: str) -> Response:
        consumer = caller(request)
        job = store.job_for(job_id, consumer.name, consumer.admin)

        if job.state != DONE:
            return JSONResponse(status_code=409, content=status_body(store, job))
        if job.result_deleted or not job.result_path:
            raise errors.gone()

        try:
            body = Path(job.result_path).read_text(encoding="utf-8")
        except OSError:
            raise errors.gone() from None
        return Response(content=body, media_type="application/json")

    @app.delete("/v1/jobs/{job_id}", status_code=204)
    async def delete_job(request: Request, job_id: str) -> Response:
        consumer = caller(request)
        job = store.job_for(job_id, consumer.name, consumer.admin)

        if not job.ended:
            # Killing the model process is the only way to stop work that has
            # started: nothing in the engine can be interrupted. The card is
            # free within seconds and the next job pays for one model load.
            runner.cancel(job.id)
            store.cancel(job.id)
        else:
            store.remove(job.id)
        return Response(status_code=204)

    # What the service is and what it is doing --------------------------------

    @app.get("/v1/models")
    async def model_list(request: Request) -> dict[str, Any]:
        caller(request)
        loaded = runner.loaded_model() or {}
        return {
            "models": [
                {
                    "name": model.name,
                    "cached": models.is_cached(model),
                    "loaded": loaded.get("model") == model.name,
                }
                for model in models.models
            ]
        }

    @app.get("/v1/status")
    async def status(request: Request) -> dict[str, Any]:
        consumer = caller(request)
        length, minutes = store.queue_length()
        running = store.running()

        current: dict[str, Any] | None = None
        if running is not None:
            if consumer.admin or running.consumer == consumer.name:
                current = {
                    "id": running.id,
                    "consumer": running.consumer,
                    "stage": running.stage,
                }
            else:
                # Another Consumer's job. That something is running, and what
                # stage it is at, is what a Consumer needs to judge its own
                # wait; whose job it is, is not.
                current = {"id": None, "consumer": None, "stage": running.stage}

        failure = store.last_failure()
        return {
            "model_loaded": runner.loaded_model(),
            "gpu": runner.gpu(),
            "queue": {"length": length, "audio_minutes": round(minutes, 2)},
            "current_job": current,
            "speed": {
                model.name: {
                    "with_diarization": store.speed(model.name, True),
                    "without_diarization": store.speed(model.name, False),
                }
                for model in models.models
            },
            "versions": {
                "service": SERVICE_VERSION,
                "api": API_VERSION,
                "pins": pins.versions(),
            },
            "uptime_seconds": round(time.monotonic() - started_at),
            "last_failure": (
                {"reason_class": failure[0], "time": failure[1]} if failure else None
            ),
            "tokens": tokens.names(),
        }

    @app.get("/healthz")
    async def healthz() -> Response:
        """Unauthenticated, because a health check is not a secret.

        It says the API is up and the model process is alive or loading, and
        nothing else: not what is running, not who is waiting.
        """
        if not runner.alive():
            return Response(content="the model process is not running", status_code=503)
        return Response(content="ok", media_type="text/plain")

    return app
