"""The WhisperX service's side of the recogniser container (ADR 0025,
service 0.8.0): Qwen3-ASR and its forced aligner, one piece at a time.

Two calls on the service's private network, nothing else: is the container
up; here is one piece as a prepared WAV and the context line, give me the
words with their times and the language heard. The standard library alone,
as the diarizer's client is, so the API process and the model process can
both use it without another dependency. An empty RECOGNISER_URL means this
copy of the service has no recogniser container (the Fast lane), and every
job under `qwen3-asr` is refused there.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from service.diarizer_client import frame

DEFAULT_URL = "http://recogniser:8200"
HEALTH_TIMEOUT = 3.0


def url() -> str:
    return os.environ.get("RECOGNISER_URL", DEFAULT_URL).rstrip("/")


def configured() -> bool:
    return bool(url())


def health() -> dict[str, Any] | None:
    """The container's /healthz body when it answers, else None. The models
    load on the first piece, so `loaded` may be false while it is up."""
    if not configured():
        return None
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


def recognise(
    wav: bytes, context: str, timeout: float, language: str | None = None
) -> dict[str, Any]:
    """POST one piece; the text, the language and the timed words back.
    Raises on any failure: the model process turns that into the job's
    failure with its reason."""
    asked: dict[str, Any] = {"context": context or ""}
    if language:
        asked["language"] = language
    body = frame(asked, wav)
    request = urllib.request.Request(
        f"{url()}/v1/recognise",
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/octet-stream",
            "Content-Length": str(len(body)),
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as answer:
        return json.loads(answer.read().decode("utf-8"))
