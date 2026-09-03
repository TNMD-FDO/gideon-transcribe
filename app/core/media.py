"""The media pipeline: what happens to a file between arriving and being Ready.

In order: hash it, look inside it, decide whether it can be accepted, work out
its Sides, and make the audio the WhisperX service is sent. The Playback copy
and the waveform come afterwards and never hold recognition up.

All of it runs on the media worker, on CPU only. No container built from the
app image ever sees a GPU.

Everything here shells out to ffmpeg and ffprobe rather than linking anything
into the app: calling a program through pipes and arguments leaves the app's
own terms untouched, and ffmpeg is where thirty years of other people's
knowledge about broken files lives.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("transcribe.media")

# What the WhisperX service expects, and what whisperx's own loader produces,
# so the audio passes through it untouched.
SAMPLE_RATE = 16000

# The acceptance decode: ten seconds is enough to know whether a file can be
# read at all, and short enough that a refused upload is refused quickly.
TEST_DECODE_SECONDS = 10

# ffprobe on a large file is quick; ffmpeg on a long one is not. The caps are
# generous, and exist so that a broken file cannot hold a worker for ever.
PROBE_TIMEOUT = 120
DECODE_TIMEOUT = 60 * 60

# The Standard preparation, as the Media handling chapter fixes it: remove the
# DC offset, resample, and normalise loudness in two linear passes so the
# change is a pure volume scale. Off is the same without the loudness pass.
HIGH_PASS = "highpass=f=20"
LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=20"

# What tells a two-party call from an ordinary stereo recording. Build
# constants rather than admin settings, because an office has no way to judge
# them, and tuned on the office's own two-channel recordings.
#
# The test is the difference signal. Subtract one channel from the other and
# measure what is left, against the quieter of the two channels. On a
# recording where both channels carry the same sound the difference cancels
# and sits below either channel. On a call with one party per channel it does
# not, because the two parties are not talking at the same time.
#
# Measured on the sample corpus on 2026-09-03, as (quieter channel) minus
# (difference), in decibels:
#
#     two-party calls        -13.1, -3.0, -2.6, -2.1
#     ordinary stereo         +1.2, +2.1, +5.0
#
# Zero separates them with room on both sides. A dual-mono recording, where
# the two channels are identical, sits far higher again, because the
# difference cancels almost completely.
DIFFERENCE_MARGIN_DB = 0.0

# A channel this far below the other is silence rather than a party. The
# quietest real call in the corpus had 12.9 dB between its two channels.
SILENT_CHANNEL_DB = 30.0

# Narrowband is what a phone system gives. Nothing wider is tested, because an
# interview recorder and a body-worn camera are stereo without being a call.
NARROWBAND_HZ = 16000


class MediaError(Exception):
    """A media step that could not finish, with words for the person."""

    def __init__(self, message: str, reason_class: str) -> None:
        super().__init__(message)
        self.message = message
        self.reason_class = reason_class


@dataclass(frozen=True)
class Track:
    """One audio stream inside the file."""

    index: int
    codec: str
    channels: int
    sample_rate: int


@dataclass(frozen=True)
class Probe:
    """What ffprobe said, in the shape the pipeline asks questions of."""

    raw: dict
    duration_seconds: float
    tracks: tuple[Track, ...]

    @property
    def has_audio(self) -> bool:
        return bool(self.tracks)

    @property
    def best_track(self) -> Track | None:
        """The track with the most channels, which is whisperx's own rule."""
        return max(self.tracks, key=lambda track: track.channels, default=None)


def _run(arguments: list[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        arguments, capture_output=True, text=True, timeout=timeout, check=False
    )


def hash_file(path: Path) -> str:
    """The SHA-256 of what was uploaded, read once, a megabyte at a time."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def probe(path: Path) -> Probe:
    """Look inside the file. The extension and the declared type are ignored.

    Recordings arrive under extensions that mean nothing, so what is inside
    the file is the only thing worth trusting.
    """
    finished = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(path),
        ],
        timeout=PROBE_TIMEOUT,
    )
    if finished.returncode != 0:
        raise MediaError("The audio in this file could not be decoded", "undecodable")

    try:
        raw = json.loads(finished.stdout or "{}")
    except json.JSONDecodeError:
        raise MediaError(
            "The audio in this file could not be decoded", "undecodable"
        ) from None

    tracks = tuple(
        Track(
            index=stream.get("index", 0),
            codec=stream.get("codec_name", ""),
            channels=int(stream.get("channels") or 0),
            sample_rate=int(stream.get("sample_rate") or 0),
        )
        for stream in raw.get("streams", [])
        if stream.get("codec_type") == "audio"
    )

    duration = raw.get("format", {}).get("duration")
    try:
        seconds = float(duration)
    except (TypeError, ValueError):
        seconds = 0.0

    return Probe(raw=raw, duration_seconds=seconds, tracks=tracks)


def forced_decoder(track: Track | None) -> list[str]:
    """Name the decoder when ffmpeg could not work it out for itself.

    A phone system exports G.729 inside a WAV container. A recent ffmpeg
    identifies it; an older one calls the codec unknown and decodes it only
    when told. Naming it costs nothing when it is not needed.
    """
    if track is None or not track.codec or track.codec == "none":
        return ["-c:a", "g729"]
    return []


def test_decode(path: Path, track: Track | None) -> None:
    """Decode the first few seconds, or refuse the file.

    A file with an audio stream that will not decode is refused here rather
    than at the front of the transcription queue an hour later.
    """
    finished = _run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            *forced_decoder(track),
            "-i",
            str(path),
            "-t",
            str(TEST_DECODE_SECONDS),
            "-f",
            "null",
            "-",
        ],
        timeout=PROBE_TIMEOUT,
    )
    if finished.returncode != 0:
        raise MediaError("The audio in this file could not be decoded", "undecodable")


# Sides -----------------------------------------------------------------------


def _astats(path: Path, track: Track | None, filters: str) -> dict[str, float]:
    """Run one astats pass and read the numbers out of what ffmpeg printed."""
    finished = _run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "info",
            *forced_decoder(track),
            "-i",
            str(path),
            "-af",
            filters,
            "-f",
            "null",
            "-",
        ],
        timeout=DECODE_TIMEOUT,
    )

    return read_levels(finished.stderr)


def read_levels(output: str) -> dict[str, float]:
    """The per-channel levels out of what ffmpeg printed.

    Every line a filter prints carries a prefix naming the filter and its
    address, as `[Parsed_astats_0 @ 0x7f...] Channel: 1`, so the prefix comes
    off before anything is read. Missing that is why this returned nothing at
    all the first time, and a two-party jail call was transcribed as one side.
    """
    found: dict[str, float] = {}
    channel = "overall"
    for raw in output.splitlines():
        line = raw.split("] ", 1)[-1].strip()
        if line.startswith("Channel:"):
            channel = line.split(":", 1)[1].strip()
        elif line.startswith("Overall"):
            channel = "overall"
        elif line.startswith("RMS level dB:"):
            value = line.split(":", 1)[1].strip()
            try:
                found[channel] = float(value)
            except ValueError:
                # A silent channel prints -inf, which is a number to a person
                # and not to Python.
                found[channel] = float("-inf")
    return found


def looks_like_a_call(path: Path, track: Track) -> bool:
    """Whether a two-channel track is one party per channel.

    Three things have to hold. The audio has to be narrowband, because that is
    what a phone system gives and an interview recorder does not. Both channels
    have to carry something, because a silent channel is a fault rather than a
    party. And subtracting one channel from the other has to leave something
    behind: on a recording where both channels carry the same sound, the
    difference cancels to tens of decibels below either channel.
    """
    if track.channels != 2:
        return False
    if track.sample_rate > NARROWBAND_HZ:
        return False

    levels = _astats(path, track, "astats")
    left = levels.get("1", float("-inf"))
    right = levels.get("2", float("-inf"))
    if left == float("-inf") or right == float("-inf"):
        return False
    if abs(left - right) > SILENT_CHANNEL_DB:
        return False

    difference = _astats(path, track, "pan=1c|c0=c0-c1,astats").get("1", float("-inf"))
    if difference == float("-inf"):
        return False

    margin = min(left, right) - difference
    log.info(
        "channels at %.1f and %.1f dB, difference at %.1f dB, margin %.1f dB",
        left,
        right,
        difference,
        margin,
    )
    return margin < DIFFERENCE_MARGIN_DB


# The ASR audio ---------------------------------------------------------------


def _measure_loudness(path: Path, track: Track | None, channel: int | None) -> dict:
    """The first loudness pass, whose figures the second pass carries.

    Two passes in linear mode keep the change a pure volume scale. In dynamic
    mode the filter would push quiet speech up and loud speech down, which
    would change what the model hears from moment to moment.
    """
    finished = _run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "info",
            *forced_decoder(track),
            "-i",
            str(path),
            "-af",
            f"{_channel_filter(channel)}{HIGH_PASS},{LOUDNORM}:print_format=json",
            "-f",
            "null",
            "-",
        ],
        timeout=DECODE_TIMEOUT,
    )
    text = finished.stderr
    start, end = text.rfind("{"), text.rfind("}")
    if start < 0 or end < start:
        return {}
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}


def _channel_filter(channel: int | None) -> str:
    """Take one channel of a two-channel call, or the whole thing."""
    if channel is None:
        return ""
    return f"pan=1c|c0=c{channel},"


def make_asr_audio(
    source: Path,
    target: Path,
    track: Track | None,
    channel: int | None = None,
    profile: str = "standard",
) -> None:
    """One Side, as the service expects it: WAV, 16 kHz, mono, 16-bit PCM.

    This is the format whisperx's own loader produces, so it passes through the
    service untouched. Nothing here trims, removes silence, or drops a track;
    the only thing that can leave speech out is a voice-activity decision, and
    that happens inside the service where it is recorded as a setting.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    filters = f"{_channel_filter(channel)}{HIGH_PASS}"

    if profile == "standard":
        measured = _measure_loudness(source, track, channel)
        if measured:
            filters += (
                f",{LOUDNORM}:linear=true"
                f":measured_I={measured['input_i']}"
                f":measured_TP={measured['input_tp']}"
                f":measured_LRA={measured['input_lra']}"
                f":measured_thresh={measured['input_thresh']}"
                f":offset={measured['target_offset']}"
            )
        else:
            # The measurement failed, so the second pass would fall back to
            # dynamic mode without saying so. One pass at the target is
            # honest, and the Provenance records what happened.
            filters += f",{LOUDNORM}"
            log.warning("loudness could not be measured; normalising in one pass")

    finished = _run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-v",
            "error",
            *forced_decoder(track),
            "-i",
            str(source),
            "-af",
            filters,
            "-ar",
            str(SAMPLE_RATE),
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(target),
        ],
        timeout=DECODE_TIMEOUT,
    )
    if finished.returncode != 0 or not target.exists():
        raise MediaError(
            "The audio in this file could not be prepared for transcription",
            "media_failed",
        )
