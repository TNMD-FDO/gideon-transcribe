"""What the service can tell about an uploaded file before it runs anything.

Two questions are asked at submit, and both are answered by ffprobe: is there
any audio in here that can be decoded, and how long is it. A file that fails
either is refused straight away rather than after it has waited in the line.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from service import errors

PROBE_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class Audio:
    """What was received, as received. Echoed in the result."""

    duration_seconds: float
    sample_rate: int | None
    channels: int | None

    def as_json(self) -> dict[str, float | int | None]:
        return {
            "duration_seconds": round(self.duration_seconds, 3),
            "sample_rate": self.sample_rate,
            "channels": self.channels,
        }


def probe(path: Path) -> Audio:
    """Read the file's first audio stream, or refuse the file.

    Anything ffmpeg can decode is accepted, whatever its container or its
    extension: recordings arrive under extensions that mean nothing, so what
    is inside the file is the only thing worth trusting.
    """
    try:
        finished = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=sample_rate,channels,codec_name:format=duration",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise errors.bad_input("the file could not be read") from None

    if finished.returncode != 0:
        raise errors.bad_input("no decodable audio stream")

    try:
        probed = json.loads(finished.stdout or "{}")
    except json.JSONDecodeError:
        raise errors.bad_input("no decodable audio stream") from None

    streams = probed.get("streams") or []
    if not streams:
        raise errors.bad_input("no decodable audio stream")

    stream = streams[0]
    duration = probed.get("format", {}).get("duration")
    if duration is None:
        raise errors.bad_input("the audio has no length that could be read")

    try:
        seconds = float(duration)
    except (TypeError, ValueError):
        raise errors.bad_input("the audio has no length that could be read") from None

    if seconds <= 0:
        raise errors.bad_input("the audio is empty")

    return Audio(
        duration_seconds=seconds,
        sample_rate=_whole(stream.get("sample_rate")),
        channels=_whole(stream.get("channels")),
    )


def _whole(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
