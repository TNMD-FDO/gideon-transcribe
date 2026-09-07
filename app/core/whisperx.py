"""Talking to the WhisperX service, which this app is one Consumer of.

The contract is docs/whisperx-api.md. Nothing here decides anything about
transcription: it submits, asks, fetches, and deletes, and turns what comes
back into either an answer or one of the contract's reason classes.

No title, file name, or user name ever travels to the service. It gets audio,
settings, and the Run's own id as a reference.

There may be two copies of the service: the batch one at WHISPERX_URL, and
the fast lane at WHISPERX_FAST_URL, an office's choice at install, for what
must not wait behind a long job. Every call here names its lane ("" for the
batch service, "fast" for the lane), and a Run remembers which it went to.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.conf import settings

log = logging.getLogger("transcribe.whisperx")

# Long enough for a large prepared file to be sent, short enough that a dead
# service is noticed rather than waited on.
SUBMIT_TIMEOUT = 600
ASK_TIMEOUT = 30


FAST = "fast"


def base_url(lane: str = "") -> str:
    return settings.WHISPERX_FAST_URL if lane == FAST else settings.WHISPERX_URL


def fast_lane_configured() -> bool:
    """Whether the office turned the lane on at install."""
    return bool(settings.WHISPERX_FAST_URL)


def lane_for(recording) -> str:
    """Where this Recording's Runs go: the lane for a Live recording, if it is
    there and answering; the batch service otherwise.

    A lane that is configured but down is not waited for: the Run goes to the
    batch service at the live priority, as it did before there was a lane,
    and the log says so.
    """
    if not recording.is_live or not fast_lane_configured():
        return ""
    if is_alive(FAST):
        return FAST
    log.warning("the fast lane is not answering; the run goes to the batch service")
    return ""


class ServiceError(Exception):
    """The service could not be reached, or refused this app."""

    def __init__(self, message: str, reason_class: str) -> None:
        super().__init__(message)
        self.reason_class = reason_class


@dataclass(frozen=True)
class Submitted:
    id: str
    position: int
    audio_minutes_ahead: float


def _request(
    method: str,
    path: str,
    body: bytes | None = None,
    content_type: str | None = None,
    timeout: int = ASK_TIMEOUT,
    lane: str = "",
) -> tuple[int, Any]:
    request = urllib.request.Request(
        f"{base_url(lane)}{path}", data=body, method=method
    )
    request.add_header("Authorization", f"Bearer {settings.WHISPERX_TOKEN}")
    if content_type:
        request.add_header("Content-Type", content_type)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as answer:
            raw = answer.read()
            return answer.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as refused:
        raw = refused.read()
        try:
            return refused.code, (json.loads(raw) if raw else None)
        except json.JSONDecodeError:
            return refused.code, None
    except (urllib.error.URLError, TimeoutError, OSError) as unreachable:
        raise ServiceError(
            f"the WhisperX service could not be reached: {unreachable}",
            "service_unreachable",
        ) from None


def is_alive(lane: str = "") -> bool:
    """The unauthenticated liveness check, asked before a Batch is made."""
    if lane == FAST and not fast_lane_configured():
        return False
    try:
        request = urllib.request.Request(f"{base_url(lane)}/healthz")
        with urllib.request.urlopen(request, timeout=5) as answer:
            return answer.status == 200
    except Exception:  # noqa: BLE001 - any failure is the same answer
        return False


def _multipart(audio: Path, request: dict[str, Any]) -> tuple[bytes, str]:
    """The submit body: the audio, and the settings beside it.

    Built by hand rather than with a library, because it is two parts and one
    boundary, and a dependency for that is a dependency to keep pinned.
    """
    boundary = f"----gideon{uuid.uuid4().hex}"
    pieces = [
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="request"\r\n'
            f"Content-Type: application/json\r\n\r\n{json.dumps(request)}\r\n"
        ).encode(),
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="audio"; '
            f'filename="side.wav"\r\nContent-Type: audio/wav\r\n\r\n'
        ).encode(),
        audio.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    return b"".join(pieces), f"multipart/form-data; boundary={boundary}"


def submit(audio: Path, request: dict[str, Any], lane: str = "") -> Submitted:
    """Hand one Side to the service and take its place in the line.

    A submission whose reference the service already knows comes back as that
    job rather than a second one, which is what makes handing over safe to
    repeat after a restart.
    """
    body, content_type = _multipart(audio, request)
    status, answer = _request(
        "POST", "/v1/jobs", body, content_type, timeout=SUBMIT_TIMEOUT, lane=lane
    )

    if status in (200, 202) and answer:
        return Submitted(
            id=answer["id"],
            position=answer.get("position", 0),
            audio_minutes_ahead=answer.get("audio_minutes_ahead", 0.0),
        )

    if status == 401:
        raise ServiceError(
            "the service does not know this app's token", "service_refused"
        )
    if status in (400, 413) and answer:
        # The service refused the request itself, and its reason class is the
        # Job's reason class.
        raise ServiceError(
            answer.get("error", "the service refused the request"),
            answer.get("reason_class", "service_refused"),
        )
    raise ServiceError(f"the service answered {status}", "service_refused")


def jobs(lane: str = "") -> list[dict[str, Any]]:
    """Every one of this app's own jobs at one service, in one call.

    The contract's intended use: one request every three seconds gets the
    state of every Run rather than one request per Run.
    """
    status, answer = _request("GET", "/v1/jobs", lane=lane)
    if status == 200 and answer:
        return answer.get("jobs", [])
    if status == 401:
        raise ServiceError(
            "the service does not know this app's token", "service_refused"
        )
    raise ServiceError(f"the service answered {status}", "service_refused")


def result(job_id: str, lane: str = "") -> dict[str, Any]:
    """The finished result, or why there is not one."""
    status, answer = _request(
        "GET", f"/v1/jobs/{job_id}/result", timeout=SUBMIT_TIMEOUT, lane=lane
    )
    if status == 200 and answer is not None:
        return answer
    if status == 410:
        raise ServiceError("the result was already deleted", "result_expired")
    if status == 409:
        raise ServiceError("the result is not ready", "internal")
    if status == 404:
        raise ServiceError("the service has no such job", "result_expired")
    raise ServiceError(f"the service answered {status}", "service_refused")


def delete(job_id: str, lane: str = "") -> None:
    """Give the service its space back, and free the card if it is running.

    A job nobody deletes is run when its turn comes even if its Consumer has
    stopped caring, so abandoning one is not a way to cancel it.
    """
    try:
        _request("DELETE", f"/v1/jobs/{job_id}", lane=lane)
    except ServiceError:
        # Best effort: the service clears its own jobs after a day anyway, and
        # failing to tidy up is not worth failing a Job over.
        log.warning("could not delete service job %s", job_id)


def status(lane: str = "") -> dict[str, Any]:
    """What the service says about itself, for the admin status page."""
    code, answer = _request("GET", "/v1/status", lane=lane)
    if code == 200 and answer:
        return answer
    raise ServiceError(f"the service answered {code}", "service_refused")
