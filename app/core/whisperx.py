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

import http.client
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


# The reason classes that are trouble of the moment (v1.163.1): the service or
# one of its containers was not answering. A hand-over that meets one is held
# and tried again by the minute sweep rather than failed.
WAITS_FOR = frozenset(
    {"service_unreachable", "recogniser_unavailable", "diarizer_unavailable"}
)


class ServiceError(Exception):
    """The service could not be reached, or refused this app. `wait` says
    the trouble is of the moment: a hand-over is held and tried again rather
    than failed."""

    def __init__(self, message: str, reason_class: str) -> None:
        super().__init__(message)
        self.reason_class = reason_class
        self.wait = reason_class in WAITS_FOR


@dataclass(frozen=True)
class Submitted:
    id: str
    position: int
    audio_minutes_ahead: float


def _request(
    method: str,
    path: str,
    body: bytes | StreamedBody | None = None,
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
    if isinstance(body, StreamedBody):
        # A body read from the file as it is sent needs its length said up
        # front (v1.134.0); urllib works it out for bytes alone.
        request.add_header("Content-Length", str(body.size))

    try:
        with urllib.request.urlopen(request, timeout=timeout) as answer:
            raw = answer.read()
            try:
                return answer.status, (json.loads(raw) if raw else None)
            except json.JSONDecodeError:
                # A 200 whose body is not JSON (a proxy page, a body cut
                # short) is the service failing, not the app (v1.132.0).
                raise ServiceError(
                    "the WhisperX service answered with something that is not JSON",
                    "internal",
                ) from None
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
    except http.client.HTTPException as broken:
        # A connection dropped half-way through a large result (v1.132.0).
        raise ServiceError(
            f"the WhisperX service's answer was cut short: {broken}",
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


# How much of the audio file is read and sent at a time.
SEND_CHUNK = 1024 * 1024


class StreamedBody:
    """A multipart body sent from the file rather than from memory (v1.134.0).

    The body used to be built whole with read_bytes() and b"".join(), so a
    460 MB WAV became about a gigabyte in the worker before a byte was sent.
    urllib takes any iterable of bytes as a request body once its length is
    given, so this yields the head, then the file a megabyte at a time, then
    the tail, and knows its size without reading anything.
    """

    def __init__(self, head: bytes, audio: Path, tail: bytes) -> None:
        self.head = head
        self.audio = audio
        self.tail = tail
        self.size = len(head) + audio.stat().st_size + len(tail)

    def __iter__(self):
        yield self.head
        with self.audio.open("rb") as handle:
            yield from iter(lambda: handle.read(SEND_CHUNK), b"")
        yield self.tail

    def read_all(self) -> bytes:
        """The whole body, for a test or a log; the send never calls this."""
        return b"".join(self)


def _multipart(audio: Path, request: dict[str, Any]) -> tuple[StreamedBody, str]:
    """The submit body: the audio, and the settings beside it.

    Built by hand rather than with a library, because it is two parts and one
    boundary, and a dependency for that is a dependency to keep pinned. The
    audio part is streamed from the file, never held whole.
    """
    boundary = f"----gideon{uuid.uuid4().hex}"
    head = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="request"\r\n'
        f"Content-Type: application/json\r\n\r\n{json.dumps(request)}\r\n"
        f'--{boundary}\r\nContent-Disposition: form-data; name="audio"; '
        f'filename="side.wav"\r\nContent-Type: audio/wav\r\n\r\n'
    ).encode()
    tail = f"\r\n--{boundary}--\r\n".encode()
    return StreamedBody(head, audio, tail), f"multipart/form-data; boundary={boundary}"


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
        # The answer's shape is checked (v1.132.0): one without an id used
        # to raise out of the hand-over and leave the Job queued for ever.
        if not isinstance(answer, dict) or not answer.get("id"):
            raise ServiceError(
                "the WhisperX service accepted the job but gave it no id",
                "internal",
            )
        return Submitted(
            id=str(answer["id"]),
            position=answer.get("position", 0),
            audio_minutes_ahead=answer.get("audio_minutes_ahead", 0.0),
        )

    if status == 401:
        raise ServiceError(
            "the service does not know this app's token", "service_refused"
        )
    if status in (400, 413, 503) and isinstance(answer, dict):
        # The service refused the request itself, and its reason class is the
        # Job's reason class. A 503 (v1.163.1) names the container that was
        # not answering, recogniser_unavailable or diarizer_unavailable, and
        # is trouble of the moment: the hand-over is held, not failed.
        raise ServiceError(
            answer.get("error", "the service refused the request"),
            answer.get("reason_class", "service_refused"),
        )
    if status in (502, 503, 504):
        # The service, or whatever stands in front of it, was not there to
        # answer; nothing the app did was refused.
        raise ServiceError(f"the service answered {status}", "service_unreachable")
    raise ServiceError(f"the service answered {status}", "service_refused")


# The voices (ADR 0021): answered in the request, in seconds; the limit is
# for a long call's upload and read.
VOICES_TIMEOUT = 600


def voices(audio: Path, request: dict[str, Any], lane: str = "") -> dict[str, Any]:
    """The prepared WAV and the stretches to the service's voices request;
    one vector per stretch and one per label back (`docs/whisperx-api.md`).
    Raises ServiceError with the service's reason class when it refuses."""
    body, content_type = _multipart(audio, request)
    status, answer = _request(
        "POST", "/v1/voices", body, content_type, timeout=VOICES_TIMEOUT, lane=lane
    )
    if status == 200 and isinstance(answer, dict):
        return answer
    if status == 401:
        raise ServiceError(
            "the service does not know this app's token", "service_refused"
        )
    if status in (400, 413, 503) and isinstance(answer, dict):
        raise ServiceError(
            answer.get("error", "the service refused the voices request"),
            answer.get("reason_class", "service_refused"),
        )
    raise ServiceError(f"the service answered {status}", "service_refused")


def jobs(lane: str = "") -> list[dict[str, Any]]:
    """Every one of this app's own jobs at one service, in one call.

    The contract's intended use: one request every three seconds gets the
    state of every Run rather than one request per Run.
    """
    status, answer = _request("GET", "/v1/jobs", lane=lane)
    if status == 200 and answer is not None:
        # An empty answer is an empty list, not a refusal (v1.132.0); and an
        # entry without an id or a state is left out rather than killing
        # the poll.
        return [
            one
            for one in ((answer or {}).get("jobs") or [])
            if isinstance(one, dict) and one.get("id") and one.get("state")
        ]
    if status == 401:
        raise ServiceError(
            "the service does not know this app's token", "service_refused"
        )
    raise ServiceError(f"the service answered {status}", "service_refused")


def status_of(job_id: str, lane: str = "") -> dict[str, Any] | None:
    """One job's status body, or None when the service has no such job.

    Asked before a Run absent from the list is counted as missing
    (v1.134.0): the list is complete for queued and running jobs now, but
    one more question for the one Run costs nothing against failing a Job
    the service is still transcribing.
    """
    status, answer = _request("GET", f"/v1/jobs/{job_id}", lane=lane)
    if status == 200 and isinstance(answer, dict) and answer.get("state"):
        return answer
    if status == 404:
        return None
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


def status(lane: str = "", timeout: int | None = None) -> dict[str, Any]:
    """What the service says about itself, for the admin status page. A page
    asks with a short timeout (v1.134.0), never the hand-over's long one."""
    extra = {"timeout": timeout} if timeout else {}
    code, answer = _request("GET", "/v1/status", lane=lane, **extra)
    if code == 200 and answer:
        return answer
    raise ServiceError(f"the service answered {code}", "service_refused")
