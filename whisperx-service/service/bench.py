"""The benchmark gate: measure this service on this office's own recordings.

The Phase 1 gate is a by-hand step on the office's own server, against its own
corpus, and its numbers are what fix the batch size, the video memory figure in
the README, the default model, and whether the voice-activity settings ship as
they stand. This is the harness that produces them.

It never writes into the repository. The report lands under the service's own
state folder, because it is made of the office's own recordings: their names,
their lengths, and their text. What comes back into the repository is a handful
of product figures, and a person carries those over by hand.

    docker compose run --rm -v <corpus>:/corpus:ro whisperx bench /corpus

Batch size and the voice-activity thresholds are service settings, not
per-request ones, so sweeping them means running this more than once with a
different .env and comparing the reports. Each report records the settings the
service actually used, which the service echoes in every result.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from service.settings import Settings
from service.tokens import parse_file

SERVICE_URL = os.environ.get("WHISPERX_URL", "http://whisperx:8000")

# How often the card is asked what it is holding, while a job runs.
WATCH_SECONDS = 1.0

# What the service expects: the format whisperx's own loader produces, so the
# audio passes through it untouched.
SAMPLE_RATE = "16000"

# The Standard preparation, as the Media handling chapter fixes it: remove the
# DC offset, resample, and normalise loudness in two passes so the change is a
# pure volume scale. Off is the same without the loudness pass.
HIGH_PASS = "highpass=f=20"
LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=20"

PROFILES = ("standard", "off")


@dataclass
class Run:
    """One file through the service, once."""

    recording: str
    profile: str
    model: str
    diarize: bool
    task: str = "transcribe"
    job_id: str | None = None
    audio_seconds: float = 0.0
    wall_seconds: float = 0.0
    peak_vram_gb: float = 0.0
    result: dict[str, Any] = field(default_factory=dict)
    failure: str | None = None

    @property
    def speed(self) -> float | None:
        """Audio minutes finished per wall-clock minute."""
        if self.wall_seconds <= 0:
            return None
        return round(self.audio_seconds / self.wall_seconds, 2)


def _say(message: str = "") -> None:
    print(message, flush=True)


def _token(settings: Settings) -> str:
    """A token to call the service with, from the file the container holds."""
    consumers = parse_file(settings.tokens_file.read_text(encoding="utf-8"))
    if not consumers:
        raise SystemExit(
            "There is no Consumer token. Run make-token and add the line to "
            "the tokens file first."
        )
    return consumers[0].token


def _call(
    method: str,
    path: str,
    token: str,
    body: bytes | None = None,
    content_type: str | None = None,
) -> tuple[int, Any]:
    request = urllib.request.Request(f"{SERVICE_URL}{path}", data=body, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    if content_type:
        request.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(request, timeout=120) as answer:
            raw = answer.read()
            return answer.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            return error.code, json.loads(raw) if raw else None
        except json.JSONDecodeError:
            return error.code, {"error": raw.decode("utf-8", "replace")[:200]}


# Preparing the audio ---------------------------------------------------------


def _forced_decoder(source: Path) -> list[str]:
    """G.729 inside a WAV container needs the decoder naming when it is not read.

    A recent ffmpeg identifies it on its own. This is the fallback the app uses
    too, and it costs nothing when it is not needed.
    """
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_name",
            "-of",
            "csv=p=0",
            str(source),
        ],
        capture_output=True,
        text=True,
    )
    codec = (probe.stdout or "").strip()
    return [] if codec and codec != "none" else ["-c:a", "g729"]


def _measure_loudness(source: Path, decoder: list[str]) -> dict[str, str] | None:
    """The first loudness pass, whose figures the second pass carries."""
    finished = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "info",
            *decoder,
            "-i",
            str(source),
            "-af",
            f"{HIGH_PASS},{LOUDNORM}:print_format=json",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    text = finished.stderr
    start = text.rfind("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def prepare(source: Path, into: Path, profile: str) -> Path | None:
    """One recording, as the service expects it: 16 kHz, mono, 16-bit PCM.

    The app's media worker will do this with its own pinned ffmpeg. Here it is
    the service image's, and the report records which, because a preprocessing
    comparison is only as good as the tool that did the preparing.
    """
    into.mkdir(parents=True, exist_ok=True)
    target = into / f"{source.stem}.{profile}.wav"
    if target.exists():
        return target

    decoder = _forced_decoder(source)
    filters = HIGH_PASS

    if profile == "standard":
        measured = _measure_loudness(source, decoder)
        if measured:
            filters = (
                f"{HIGH_PASS},{LOUDNORM}:linear=true"
                f":measured_I={measured['input_i']}"
                f":measured_TP={measured['input_tp']}"
                f":measured_LRA={measured['input_lra']}"
                f":measured_thresh={measured['input_thresh']}"
                f":offset={measured['target_offset']}"
            )
        else:
            filters = f"{HIGH_PASS},{LOUDNORM}"

    finished = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-y",
            "-v",
            "error",
            *decoder,
            "-i",
            str(source),
            "-af",
            filters,
            "-ar",
            SAMPLE_RATE,
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(target),
        ],
        capture_output=True,
        text=True,
    )
    if finished.returncode != 0 or not target.exists():
        _say(f"  {source.name}: could not be prepared")
        _say(f"    {finished.stderr.strip().splitlines()[-1:]}")
        return None
    return target


# Running one job -------------------------------------------------------------


def _multipart(audio: Path, request: dict[str, Any]) -> tuple[bytes, str]:
    boundary = "----whisperxbench"
    parts: list[bytes] = []
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="request"\r\n'
        f"Content-Type: application/json\r\n\r\n{json.dumps(request)}\r\n".encode()
    )
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="audio"; '
        f'filename="{audio.name}"\r\nContent-Type: audio/wav\r\n\r\n'.encode()
    )
    parts.append(audio.read_bytes())
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def run_one(audio: Path, run: Run, token: str) -> Run:
    body, content_type = _multipart(
        audio,
        {
            "model": run.model,
            "diarize": run.diarize,
            "task": run.task,
            "client_reference": (
                f"bench-{audio.stem}-{run.model}-{run.diarize}-{run.task}"
            ),
        },
    )
    status, answer = _call("POST", "/v1/jobs", token, body, content_type)
    if status not in (200, 202):
        run.failure = f"submit answered {status}: {answer}"
        return run

    run.job_id = answer["id"]
    started = time.monotonic()

    while True:
        time.sleep(WATCH_SECONDS)
        _, health = _call("GET", "/v1/status", token)
        if health and health.get("gpu", {}).get("vram_used_gb"):
            run.peak_vram_gb = max(run.peak_vram_gb, health["gpu"]["vram_used_gb"])

        _, state = _call("GET", f"/v1/jobs/{run.job_id}", token)
        if state is None:
            continue
        if state["state"] == "done":
            run.wall_seconds = round(time.monotonic() - started, 2)
            break
        if state["state"] in ("failed", "cancelled"):
            run.failure = json.dumps(state.get("failure"))
            return run

    _, result = _call("GET", f"/v1/jobs/{run.job_id}/result", token)
    run.result = result or {}
    run.audio_seconds = run.result.get("audio", {}).get("duration_seconds", 0.0)
    _call("DELETE", f"/v1/jobs/{run.job_id}", token)
    return run


# The report ------------------------------------------------------------------


def _summary(run: Run) -> dict[str, Any]:
    result = run.result
    segments = result.get("segments", [])
    words = sum(len(segment.get("words") or []) for segment in segments)
    speech = sum(
        (segment.get("end") or 0) - (segment.get("start") or 0) for segment in segments
    )
    return {
        "recording": run.recording,
        "profile": run.profile,
        "model": run.model,
        "diarize": run.diarize,
        "task": run.task,
        "task_run": result.get("settings_used", {}).get("task_run"),
        "task_reason": result.get("settings_used", {}).get("task_reason"),
        "word_timestamps": result.get("word_timestamps", {}),
        "audio_seconds": run.audio_seconds,
        "wall_seconds": run.wall_seconds,
        "audio_minutes_per_wall_minute": run.speed,
        "peak_vram_gb": run.peak_vram_gb,
        "segments": len(segments),
        "words": words,
        "speech_seconds": round(speech, 1),
        "speech_share": (
            round(speech / run.audio_seconds, 3) if run.audio_seconds else None
        ),
        "speakers": result.get("speakers", {}).get("labels", []),
        "language": result.get("language", {}).get("detected"),
        "settings_used": result.get("settings_used", {}),
        "timings_seconds": result.get("timings_seconds", {}),
        "failure": run.failure,
    }


def _ffmpeg_version() -> str:
    finished = subprocess.run(
        ["ffmpeg", "-hide_banner", "-version"], capture_output=True, text=True
    )
    return (finished.stdout or "").splitlines()[0] if finished.stdout else "unknown"


def compare(first: str, second: str) -> int:
    """Put two reports side by side: what one heard that the other did not.

    This is what the dropped-speech leg of the gate reads. A voice-activity
    decision is the only way the service can leave speech out, so the way to
    see whether the shipped thresholds are losing quiet speech is to run the
    same recordings again with lower ones and look at what changed. Speech
    seconds and words both matter: a few more words in the same seconds is
    ordinary variation, while a jump in both is speech that was being missed.
    """
    settings = Settings.from_environment()
    folder = settings.state_dir / "bench"

    reports = []
    for label in (first, second):
        path = folder / f"report-{label}.json"
        if not path.exists():
            _say(f"There is no report called {label}. Looked in {folder}.")
            return 66
        reports.append(json.loads(path.read_text(encoding="utf-8")))

    left, right = reports
    _say(f"{first} against {second}")
    _say()
    _say(
        f"{'recording':34} {'model':16} "
        f"{'speech s':>10} {'speech s':>10} {'words':>8} {'words':>8}"
    )
    _say(
        f"{'':34} {'':16} {first[:10]:>10} {second[:10]:>10} "
        f"{first[:8]:>8} {second[:8]:>8}"
    )

    def key(run):
        return (run["recording"], run["model"], run["diarize"], run.get("task"))

    right_runs = {key(run): run for run in right["runs"]}
    for run in left["runs"]:
        other = right_runs.get(key(run))
        if other is None:
            continue
        _say(
            f"{run['recording'][:33]:34} {run['model'][:15]:16} "
            f"{run['speech_seconds']:>10} {other['speech_seconds']:>10} "
            f"{run['words']:>8} {other['words']:>8}"
        )

    _say()
    _say("More speech and more words in the second run means the first was")
    _say("leaving speech out. The recordings themselves say whether it was")
    _say("speech worth keeping: listen to the spans that only one run found.")
    return 0


def bench(argv: list[str]) -> int:
    """Run the gate over a folder of recordings."""
    if not argv:
        _say(
            "Usage: bench FOLDER [--models=a,b] [--profiles=standard,off] "
            "[--diarize=off,on] [--tasks=transcribe,translate] [--only=name] "
            "[--label=name]"
        )
        _say("       bench compare LABEL LABEL")
        return 64

    if argv[0] == "compare":
        if len(argv) != 3:
            _say("Usage: bench compare LABEL LABEL")
            return 64
        return compare(argv[1], argv[2])

    corpus = Path(argv[0])
    if not corpus.is_dir():
        _say(f"{corpus} is not a folder this container can see.")
        return 66

    options = dict(
        pair.split("=", 1) for pair in argv[1:] if pair.startswith("--") and "=" in pair
    )
    models = options.get("--models", "large-v3,large-v3-turbo").split(",")
    profiles = options.get("--profiles", "standard").split(",")
    # "off,on" by default, because the gate needs the speed of both.
    diarizations = [
        word.strip() == "on" for word in options.get("--diarize", "off,on").split(",")
    ]
    # The three tasks a Consumer may ask for. Plain transcription is what the
    # speed and memory legs measure; the other two are here so that the task
    # table is proved against the engine and not only in the unit tests, and
    # for the translation leg once an office has non-English samples.
    tasks = options.get("--tasks", "transcribe").split(",")
    # A way to run one recording while something is being got working, without
    # waiting for a whole corpus.
    only = [piece for piece in options.get("--only", "").split(",") if piece.strip()]
    label = options.get("--label", time.strftime("%Y-%m-%d-%H%M"))

    settings = Settings.from_environment()
    token = _token(settings)
    into = settings.state_dir / "bench"
    prepared_dir = into / "prepared"

    recordings = sorted(
        path
        for path in corpus.iterdir()
        if path.is_file()
        and path.suffix.lower() not in (".txt", ".json")
        and (not only or any(piece in path.name for piece in only))
    )
    if not recordings:
        _say(f"There is nothing to run in {corpus}.")
        return 66

    _say(f"{len(recordings)} recordings, models {', '.join(models)}")
    _say(f"ffmpeg: {_ffmpeg_version()}")
    _say()

    runs: list[Run] = []
    for source in recordings:
        for profile in profiles:
            _say(f"preparing {source.name} ({profile})")
            audio = prepare(source, prepared_dir, profile)
            if audio is None:
                continue
            for model in models:
                for diarize in diarizations:
                    for task in tasks:
                        run = Run(source.name, profile, model, diarize, task)
                        _say(
                            f"  {model}, diarize {'on' if diarize else 'off'}"
                            f"{'' if task == 'transcribe' else ', ' + task}: running"
                        )
                        run = run_one(audio, run, token)
                        if run.failure:
                            _say(f"    failed: {run.failure}")
                        else:
                            used = run.result.get("settings_used", {})
                            timing = run.result.get("word_timestamps", {})
                            _say(
                                f"    {run.wall_seconds}s, {run.speed}x real "
                                f"time, {run.peak_vram_gb} GB peak, ran "
                                f"{used.get('task_run')} "
                                f"({used.get('task_reason')}), word timing "
                                f"{timing.get('present')}"
                                + (
                                    f" because {timing.get('reason')}"
                                    if timing.get("reason")
                                    else ""
                                )
                            )
                        runs.append(run)

    report = {
        "label": label,
        "made": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ffmpeg": _ffmpeg_version(),
        "service_url": SERVICE_URL,
        "runs": [_summary(run) for run in runs],
    }
    into.mkdir(parents=True, exist_ok=True)
    report_file = into / f"report-{label}.json"
    report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    _say()
    _say(f"The report is at {report_file} inside the container, which is the")
    _say("bench folder of the service's state folder on the server.")
    _say("Nothing from it belongs in the repository except the product figures.")
    return 0
