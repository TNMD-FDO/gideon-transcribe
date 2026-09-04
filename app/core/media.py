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

# Keep wall-clock time. A body-worn camera drops audio, leaving holes in the
# stream. An mp4 keeps a hole, because it carries a timestamp per frame; a WAV
# cannot, so ffmpeg writes the samples end to end and the file comes out
# shorter than the recording by the length of every hole. The transcript is
# then in one timeline and the player in another, and every word after a hole
# is early by the total of the holes before it.
#
# `async=1` fills each hole with silence instead of closing it, and
# `first_pts=0` pads a stream that starts late so the file starts at zero.
# On a file with no holes it does nothing.
KEEP_THE_CLOCK = "aresample=async=1:first_pts=0"
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
            # The same chain the second pass runs, so the figures describe the
            # signal that is actually written.
            f"{KEEP_THE_CLOCK},{_channel_filter(channel)}{HIGH_PASS}"
            f",{LOUDNORM}:print_format=json",
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
    filters = f"{KEEP_THE_CLOCK},{_channel_filter(channel)}{HIGH_PASS}"

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


# The Playback copy ------------------------------------------------------------
#
# Every Recording gets exactly one, and the player never touches the uploaded
# bytes. Chrome and Edge cannot play PCM inside mp4, G.729, or HEVC without
# hardware support, and they seek badly in variable-bitrate MP3. One
# predictable copy removes all of that, and the faithful file of record stays
# outside the app.

# Video already in this shape is copied rather than re-encoded, which turns a
# 50-minute body-worn camera export into a remux of well under a minute.
PLAYBACK_VIDEO_CODEC = "h264"
PLAYBACK_MAX_HEIGHT = 720

# The Playback copy's audio is pinned to 48 kHz, and pinning it is not a
# detail. The loudness filter resamples to 192 kHz inside itself, and with no
# rate asked for, the AAC encoder settles on 96 kHz: a rate browsers refuse to
# decode in an MP4, which fails the whole file rather than only its sound. The
# source is 48 kHz or below in every recording this app accepts.
PLAYBACK_SAMPLE_RATE = 48000

# What a voice recording needs and no more. Anything above this is spent on
# room noise.
PLAYBACK_BITRATE_MONO = "96k"
PLAYBACK_BITRATE_STEREO = "128k"


@dataclass(frozen=True)
class Video:
    """The video stream, when there is one."""

    codec: str
    height: int


def video_stream(raw: dict) -> Video | None:
    for stream in raw.get("streams", []):
        if stream.get("codec_type") == "video":
            # A cover image inside an audio file is a video stream that is one
            # frame long, and is not video.
            if stream.get("disposition", {}).get("attached_pic"):
                continue
            return Video(
                codec=stream.get("codec_name", ""),
                height=int(stream.get("height") or 0),
            )
    return None


def can_copy_video(video: Video) -> bool:
    """Whether the video can be kept as it is rather than encoded again."""
    return (
        video.codec == PLAYBACK_VIDEO_CODEC and 0 < video.height <= PLAYBACK_MAX_HEIGHT
    )


def make_playback_copy(
    source: Path,
    target: Path,
    probed: Probe,
    profile: str = "standard",
) -> None:
    """One file the browser can play, seek in, and start before it has it all.

    The sound is normalised exactly as the ASR audio is, with the figures
    measured in the first pass, so what the listener hears is what the model
    heard. Channels are kept as recorded, so a two-party call still has one
    side per ear.

    Always with the index at the front: a video plays as it downloads only
    when its index is there, and ffmpeg writes it at the end unless told
    otherwise.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    track = probed.best_track
    video = video_stream(probed.raw)

    # The same first filter the ASR audio gets, so both copies hold a hole the
    # same way and both start at zero. Without it the two are in step only by
    # luck: an mp4 keeps a hole as a jump in its timestamps and a WAV cannot,
    # so they would agree on a clean file and disagree on a body-worn camera's.
    filters = f"{KEEP_THE_CLOCK},{HIGH_PASS}"
    if profile == "standard":
        measured = _measure_loudness(source, track, None)
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
            filters += f",{LOUDNORM}"

    channels = 2 if (track and track.channels >= 2) else 1
    arguments = [
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
        "-c:a",
        "aac",
        "-b:a",
        PLAYBACK_BITRATE_STEREO if channels == 2 else PLAYBACK_BITRATE_MONO,
        "-ac",
        str(channels),
        "-ar",
        str(PLAYBACK_SAMPLE_RATE),
        "-movflags",
        "+faststart",
    ]

    if video is None:
        arguments += ["-vn"]
    elif can_copy_video(video):
        arguments += ["-c:v", "copy"]
    else:
        arguments += [
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            # Down to 720 at most, keeping the shape, and never scaled up.
            # The frame rate is left alone.
            "-vf",
            f"scale=-2:'min({PLAYBACK_MAX_HEIGHT},ih)'",
            "-pix_fmt",
            "yuv420p",
        ]

    arguments.append(str(target))
    finished = _run(arguments, timeout=DECODE_TIMEOUT)
    if finished.returncode != 0 or not target.exists():
        raise MediaError(
            "The playback copy of this recording could not be made", "media_failed"
        )


def playback_suffix(probed: Probe) -> str:
    """mp4 when there is a picture, m4a when there is only sound."""
    return ".mp4" if video_stream(probed.raw) else ".m4a"


# The waveform -----------------------------------------------------------------


def make_waveform(source: Path, target: Path) -> None:
    """The peaks the player draws, from the Playback copy.

    audiowaveform reads MP3, WAV, FLAC, Ogg Vorbis, and Opus, and the Playback
    copy is AAC, which is none of them. So ffmpeg decodes it to WAV on the way
    through rather than a second file being written and deleted.

    Eight bits and 256 samples a pixel is what the viewer draws with: the peaks
    are a picture, and asking for more of them would only make the file bigger.
    """
    target.parent.mkdir(parents=True, exist_ok=True)

    decode = subprocess.Popen(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-i",
            str(source),
            "-f",
            "wav",
            "-",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    peaks = subprocess.run(
        [
            "audiowaveform",
            "-i",
            "-",
            "--input-format",
            "wav",
            "-o",
            str(target),
            "--output-format",
            "json",
            "-z",
            "256",
            "-b",
            "8",
        ],
        stdin=decode.stdout,
        capture_output=True,
        text=True,
        timeout=DECODE_TIMEOUT,
        check=False,
    )
    if decode.stdout:
        decode.stdout.close()
    decode.wait(timeout=DECODE_TIMEOUT)

    if peaks.returncode != 0 or not target.exists():
        raise MediaError(
            "The waveform for this recording could not be made", "media_failed"
        )


# Clips ------------------------------------------------------------------------

# White with a dark outline at the bottom of the picture, one cue per Segment.
# Fixed in code, with no setting: a caption style is a thing to get right once.
CAPTION_STYLE = (
    "FontName=DejaVu Sans,Fontsize=22,PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H80000000,BorderStyle=1,Outline=2,Shadow=0,"
    "Alignment=2,MarginV=28"
)


def cut_clip(
    source: Path,
    target: Path,
    start: float,
    end: float,
    captions: Path | None = None,
    timeout: int = 600,
) -> None:
    """A span of the Playback copy as its own file, cut frame-accurately.

    Seeking is done after the input rather than before it, which is slower and
    exact: a Clip that starts half a second late is no use to somebody playing
    it at a hearing. The picture is re-encoded for the same reason, and
    because captions burned in cannot be copied through.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    video = target.suffix == ".mp4"

    arguments = [
        "ffmpeg",
        "-nostdin",
        "-y",
        "-v",
        "error",
        "-i",
        str(source),
        "-ss",
        f"{max(0.0, start):.3f}",
        "-to",
        f"{max(0.0, end):.3f}",
    ]

    if video:
        if captions is not None:
            # The caption file's times already start at zero, and the trim
            # above makes the output start at zero too, so they line up.
            escaped = str(captions).replace("\\", "/").replace(":", r"\:")
            arguments += ["-vf", f"subtitles='{escaped}':force_style='{CAPTION_STYLE}'"]
        arguments += [
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            PLAYBACK_BITRATE_STEREO,
            "-movflags",
            "+faststart",
        ]
    else:
        arguments += ["-vn", "-c:a", "libmp3lame", "-q:a", "2"]

    arguments.append(str(target))
    finished = _run(arguments, timeout=timeout)
    if finished.returncode != 0 or not target.exists():
        raise MediaError(
            "This clip could not be made from the recording", "clip_render_failed"
        )
