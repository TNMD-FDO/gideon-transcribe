"""The WhisperX service's side of the diarizer container (Phase 5 chapter 4;
the voices, ADR 0021).

Three calls on the service's private network, nothing else: is the container
up with its model loaded; here is a prepared WAV, give me the spans; here is
a prepared WAV and a list of stretches, give me their voices. The standard
library alone, so the API process and the model process can both use it
without another dependency.
"""

from __future__ import annotations

import json
import os
import struct
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_URL = "http://diarizer:8100"
HEALTH_TIMEOUT = 3.0


def url() -> str:
    return os.environ.get("DIARIZER_URL", DEFAULT_URL).rstrip("/")


def health() -> dict[str, Any] | None:
    """The container's /healthz body when it is up and loaded, else None."""
    try:
        target = f"{url()}/healthz"
        with urllib.request.urlopen(target, timeout=HEALTH_TIMEOUT) as answer:
            if answer.status != 200:
                return None
            return json.loads(answer.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None


def is_up() -> bool:
    return health() is not None


def voices_up() -> bool:
    """Whether the container has the voices model loaded beside Nemotron."""
    body = health()
    return bool(body and (body.get("voices") or {}).get("loaded"))


def diarize(wav: Path, timeout: float) -> dict[str, Any]:
    """POST the prepared WAV; the spans back. Raises on any failure: the
    model process turns that into the job's failure with its reason."""
    body = wav.read_bytes()
    request = urllib.request.Request(
        f"{url()}/v1/diarize",
        data=body,
        method="POST",
        headers={"Content-Type": "audio/wav", "Content-Length": str(len(body))},
    )
    with urllib.request.urlopen(request, timeout=timeout) as answer:
        return json.loads(answer.read().decode("utf-8"))


def frame(asked: dict[str, Any], wav: bytes) -> bytes:
    """The voices request's body: four bytes of JSON length, the JSON, the WAV.
    No multipart, since this side is the standard library."""
    part = json.dumps(asked).encode("utf-8")
    return struct.pack(">I", len(part)) + part + wav


def voices(wav: Path, asked: dict[str, Any], timeout: float) -> dict[str, Any]:
    """POST the prepared WAV with the stretches; the vectors back. Raises on
    any failure, as `diarize` does; a 503 from the container means the voices
    model is not in the folder."""
    body = frame(asked, wav.read_bytes())
    request = urllib.request.Request(
        f"{url()}/v1/voices",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/octet-stream",
            "Content-Length": str(len(body)),
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as answer:
        return json.loads(answer.read().decode("utf-8"))
