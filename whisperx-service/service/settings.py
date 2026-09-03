"""The service's settings, read once from the environment.

Every one of these comes from whisperx-service/.env, every one has a comment
there saying what it does, and every one is echoed in a job's result so that a
Consumer's provenance can name what produced a transcript.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Fixed inside the container. The compose file decides which folders on the
# server these are, and nothing in the code needs to know.
STATE_DIR = Path("/srv/state")
TOKENS_FILE = Path("/run/secrets/tokens")

SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
BYTES_PER_GB = 1024**3


def _number(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"{name} is not a number: {raw!r}") from None


def _whole(name: str, default: int) -> int:
    value = _number(name, default)
    if value != int(value):
        raise ValueError(f"{name} is not a whole number: {value}")
    return int(value)


@dataclass(frozen=True)
class Settings:
    """What the service was started with."""

    state_dir: Path
    tokens_file: Path

    max_upload_bytes: int
    max_audio_seconds: float
    timeout_base_minutes: int
    timeout_per_audio_hour_minutes: int
    result_hours: int
    job_history_days: int

    batch_size: int
    vad_onset: float
    vad_offset: float
    align_languages: tuple[str, ...]

    log_level: str

    @classmethod
    def from_environment(cls) -> Settings:
        languages = [
            code.strip()
            for code in os.environ.get("WHISPERX_ALIGN_LANGUAGES", "en,es").split(",")
            if code.strip()
        ]
        return cls(
            state_dir=Path(os.environ.get("WHISPERX_STATE_DIR", STATE_DIR)),
            tokens_file=Path(os.environ.get("WHISPERX_TOKENS_FILE", TOKENS_FILE)),
            max_upload_bytes=int(_number("WHISPERX_MAX_UPLOAD_GB", 2) * BYTES_PER_GB),
            max_audio_seconds=_number("WHISPERX_MAX_AUDIO_HOURS", 8) * SECONDS_PER_HOUR,
            timeout_base_minutes=_whole("WHISPERX_JOB_TIMEOUT_BASE_MINUTES", 30),
            timeout_per_audio_hour_minutes=_whole(
                "WHISPERX_JOB_TIMEOUT_PER_AUDIO_HOUR_MINUTES", 60
            ),
            result_hours=_whole("WHISPERX_RESULT_HOURS", 24),
            job_history_days=_whole("WHISPERX_JOB_HISTORY_DAYS", 30),
            batch_size=_whole("WHISPERX_BATCH_SIZE", 16),
            vad_onset=_number("WHISPERX_VAD_ONSET", 0.50),
            vad_offset=_number("WHISPERX_VAD_OFFSET", 0.363),
            align_languages=tuple(languages),
            log_level=os.environ.get("WHISPERX_LOG_LEVEL", "info").lower(),
        )

    def timeout_seconds(self, audio_seconds: float) -> float:
        """How long this job may run: the base, plus time for its own length.

        Past it the job fails with the reason class `timeout` and the model
        process is restarted, because nothing inside the engine can be asked
        to stop.
        """
        per_hour = self.timeout_per_audio_hour_minutes * SECONDS_PER_MINUTE
        base = self.timeout_base_minutes * SECONDS_PER_MINUTE
        return base + (audio_seconds / SECONDS_PER_HOUR) * per_hour

    @property
    def audio_dir(self) -> Path:
        """Audio in flight. A file here is deleted the moment its job ends."""
        return self.state_dir / "audio"

    @property
    def results_dir(self) -> Path:
        """Results waiting to be collected, and gone within the day."""
        return self.state_dir / "results"

    @property
    def database_file(self) -> Path:
        """The line itself, which is what survives a restart."""
        return self.state_dir / "jobs.sqlite3"
