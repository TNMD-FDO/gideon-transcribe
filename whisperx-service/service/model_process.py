"""The model process: the only part of the service that touches the card.

It is a separate process for one reason. Nothing in whisperx, faster-whisper,
or CTranslate2 can be interrupted: there is no callback that stops a batch and
no flag that ends a generation. So the way to stop a running job is to kill the
process that is running it, and the way to survive a driver fault is to start a
fresh one. Everything else in the service stays up while that happens.

It holds one model at a time and runs one job at a time. It talks to the parent
over two queues and writes its result straight to a file, because a transcript
is too big to be worth passing through a pipe.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from service import errors
from service.detection import Window, combine, decide
from service.prompt import build as build_prompt
from service.version import API_VERSION, SERVICE_VERSION

SAMPLE_RATE = 16000

# How often the child tells the parent what the card is doing. The status
# endpoint reports video memory at all times, and this is where the figures
# come from.
HEARTBEAT_SECONDS = 3.0

BYTES_PER_GB = 1024**3


def _message(kind: str, **fields: Any) -> dict[str, Any]:
    return {"type": kind, **fields}


class Engine:
    """whisperx, held across jobs so the model is not reloaded for each one."""

    def __init__(self, settings: dict[str, Any]) -> None:
        self.settings = settings
        self.model_name: str | None = None
        self.pipeline = None
        self.aligners: dict[str, Any] = {}
        self.diarizer = None

    # Loading -----------------------------------------------------------------

    def pipeline_for(self, model_name: str):
        """The transcription pipeline, swapping models only when asked to.

        The last-used model stays loaded and nothing is unloaded when idle: a
        swap costs one reload, and an office that uses one model never pays it.
        """
        import whisperx

        if self.pipeline is not None and self.model_name == model_name:
            return self.pipeline

        self.pipeline = whisperx.load_model(
            model_name,
            device="cuda",
            compute_type="float16",
            vad_options={
                "vad_onset": self.settings["vad_onset"],
                "vad_offset": self.settings["vad_offset"],
            },
        )
        self.model_name = model_name
        return self.pipeline

    def aligner_for(self, language: str):
        """The alignment model for a language, or None when there is not one.

        The service runs offline after the pull, so a language whose model was
        never pulled gets one attempt at fetching it. If that fails the job
        still finishes, with segment timing and a reason saying why.
        """
        if language in self.aligners:
            return self.aligners[language]

        import whisperx

        offline = os.environ.get("HF_HUB_OFFLINE")
        try:
            os.environ["HF_HUB_OFFLINE"] = "0"
            model, metadata = whisperx.load_align_model(
                language_code=language, device="cuda"
            )
            self.aligners[language] = (model, metadata)
        except Exception:  # noqa: BLE001 - any failure here is the same failure
            self.aligners[language] = None
        finally:
            if offline is None:
                os.environ.pop("HF_HUB_OFFLINE", None)
            else:
                os.environ["HF_HUB_OFFLINE"] = offline
        return self.aligners[language]

    def diarization(self):
        if self.diarizer is not None:
            return self.diarizer

        from whisperx.diarize import DiarizationPipeline

        self.diarizer = DiarizationPipeline(
            model_name=self.settings["diarization_model"],
            use_auth_token=_token(),
            device="cuda",
        )
        return self.diarizer

    # Detection ---------------------------------------------------------------

    def detect(self, audio, duration: float) -> list[Window]:
        """One language and one probability per window.

        whisperx's own detect call reads the first 30 seconds and returns only
        the code, so the model is asked directly: a jail call that opens with
        an English announcement would otherwise be heard as an English call.
        """
        from service.detection import WINDOW_SECONDS, window_offsets

        model = self.pipeline.model
        windows: list[Window] = []
        for offset in window_offsets(duration):
            start = int(offset * SAMPLE_RATE)
            end = start + int(WINDOW_SECONDS * SAMPLE_RATE)
            sample = audio[start:end]
            if len(sample) == 0:
                continue
            language, probability, _ = model.detect_language(audio=sample)
            windows.append(Window(round(offset, 3), language, float(probability)))
        return windows


def _token() -> str | None:
    path = os.environ.get("HF_TOKEN_FILE")
    if not path:
        return None
    try:
        return Path(path).read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _vram() -> tuple[float, float]:
    """Video memory used and free, in gigabytes, as the driver sees it.

    The driver's own figure is the one that counts: CTranslate2 allocates
    outside torch's allocator, so torch's accounting would miss most of what
    a transcription actually uses.
    """
    import torch

    if not torch.cuda.is_available():
        return 0.0, 0.0
    free, total = torch.cuda.mem_get_info()
    return (total - free) / BYTES_PER_GB, free / BYTES_PER_GB


def _card() -> dict[str, Any]:
    import torch

    if not torch.cuda.is_available():
        return {"uuid": None, "name": None}
    properties = torch.cuda.get_device_properties(0)
    uuid = getattr(properties, "uuid", None)
    return {
        "uuid": f"GPU-{uuid}" if uuid else None,
        "name": properties.name,
    }


def _heartbeat(outbox, stop: threading.Event) -> None:
    while not stop.wait(HEARTBEAT_SECONDS):
        used, free = _vram()
        outbox.put(_message("gpu", used_gb=round(used, 2), free_gb=round(free, 2)))


def run(inbox, outbox, settings: dict[str, Any]) -> None:
    """The child's whole life: load, then one job at a time until it is killed."""
    engine = Engine(settings)
    stop = threading.Event()
    threading.Thread(target=_heartbeat, args=(outbox, stop), daemon=True).start()

    outbox.put(_message("ready", card=_card()))

    while True:
        job = inbox.get()
        if job is None:
            stop.set()
            return
        try:
            _run_one(engine, job, outbox)
        except Exception as exc:  # noqa: BLE001 - every failure is reported
            outbox.put(
                _message(
                    "failure",
                    job_id=job["job_id"],
                    reason_class=_class_of(exc),
                    message=_safe(exc),
                )
            )


def _class_of(exc: Exception) -> str:
    """Which reason class an engine failure belongs to.

    Only a card fault is worth trying again, and only once, after the process
    has been started fresh.
    """
    text = f"{type(exc).__name__}: {exc}".lower()
    if "cuda" in text or "out of memory" in text or "cublas" in text:
        return errors.GPU_ERROR
    if "ffmpeg" in text or "decode" in text or "no such file" in text:
        return errors.BAD_INPUT
    return errors.INTERNAL


def _safe(exc: Exception) -> str:
    """A short message with nothing in it that could be content."""
    return type(exc).__name__


def _run_one(engine: Engine, job: dict[str, Any], outbox) -> None:
    import whisperx

    job_id = job["job_id"]
    request = job["request"]
    timings: dict[str, float] = {}

    def stage(name: str, percent: float | None = None) -> None:
        outbox.put(_message("stage", job_id=job_id, stage=name, percent=percent))

    started = time.monotonic()
    stage("loading model")
    pipeline = engine.pipeline_for(request["model"])
    outbox.put(
        _message(
            "loaded",
            model=request["model"],
            revision=engine.settings["model_revisions"].get(request["model"]),
        )
    )
    audio = whisperx.load_audio(job["audio_path"])
    duration = len(audio) / SAMPLE_RATE
    peak_used, _ = _vram()

    # What to run -------------------------------------------------------------
    #
    # Detection is counted as part of getting ready rather than as a stage of
    # its own: the contract fixes the six timings a result carries, and this is
    # work done before any transcription starts. What it cost goes to the
    # journal, where the gate can read it.

    detection = None
    if not request.get("language"):
        at = time.monotonic()
        windows = engine.detect(audio, duration)
        detection = combine(windows)
        outbox.put(
            _message(
                "detected",
                job_id=job_id,
                seconds=round(time.monotonic() - at, 3),
                windows=len(windows),
                language=detection.detected,
                mixed=detection.mixed,
            )
        )

    timings["load"] = round(time.monotonic() - started, 3)
    decision = decide(
        request.get("task", "transcribe"),
        request.get("language"),
        bool(request.get("translate_if_mixed")),
        detection,
    )

    prompt = build_prompt(
        request.get("context") or "",
        list(request.get("vocabulary") or []),
        _counter(pipeline),
    )
    if prompt.text:
        pipeline.options = pipeline.options._replace(initial_prompt=prompt.text)

    # Transcribe --------------------------------------------------------------

    stage("transcribing", 0.0)
    at = time.monotonic()
    transcribed = pipeline.transcribe(
        audio,
        batch_size=engine.settings["batch_size"],
        language=decision.language,
        task=decision.task_run,
        progress_callback=lambda percent: stage("transcribing", round(percent, 1)),
    )
    timings["transcribe"] = round(time.monotonic() - at, 3)
    peak_used = max(peak_used, _vram()[0])

    # Align -------------------------------------------------------------------

    word_timestamps = True
    reason = None
    timings["align"] = 0.0

    if decision.task_run == "translate":
        # whisperx disables alignment for translation itself: there is nothing
        # in the English text to line up against the foreign audio.
        word_timestamps = False
        reason = "translation"
    else:
        aligner = engine.aligner_for(decision.language or transcribed["language"])
        if aligner is None:
            word_timestamps = False
            reason = "no_alignment_model"
        else:
            stage("aligning")
            at = time.monotonic()
            model, metadata = aligner
            transcribed = whisperx.align(
                transcribed["segments"],
                model,
                metadata,
                audio,
                "cuda",
                return_char_alignments=False,
            )
            timings["align"] = round(time.monotonic() - at, 3)

    # Diarize -----------------------------------------------------------------

    speakers: dict[str, Any] = {"labels": []}
    timings["diarize"] = 0.0

    if request.get("diarize"):
        stage("diarizing")
        at = time.monotonic()
        hint = request.get("speakers") or {}
        counts: dict[str, Any] = {}
        if "exactly" in hint:
            counts["num_speakers"] = hint["exactly"]
        elif "between" in hint:
            counts["min_speakers"], counts["max_speakers"] = hint["between"]

        wanted = bool(request.get("return_speaker_embeddings"))
        diarized = engine.diarization()(
            {"waveform": _as_tensor(audio), "sample_rate": SAMPLE_RATE},
            return_embeddings=wanted,
            **counts,
        )
        embeddings = None
        if wanted:
            diarized, embeddings = diarized

        transcribed = whisperx.assign_word_speakers(diarized, transcribed)
        timings["diarize"] = round(time.monotonic() - at, 3)
        peak_used = max(peak_used, _vram()[0])

        labels = sorted(
            {
                segment["speaker"]
                for segment in transcribed["segments"]
                if segment.get("speaker")
            }
        )
        speakers = {"labels": labels}
        if wanted and embeddings is not None:
            speakers["embeddings"] = {
                label: [float(value) for value in vector]
                for label, vector in _as_pairs(embeddings, labels)
            }
            first = next(iter(speakers["embeddings"].values()), [])
            speakers["embedding_dimension"] = len(first)

    # The result --------------------------------------------------------------

    stage("finishing")
    timings["queued"] = job.get("queued_seconds", 0.0)
    timings["total"] = round(time.monotonic() - started, 3)

    result = {
        "audio": job["audio"],
        "language": _language_part(request, detection, decision),
        "word_timestamps": {"present": word_timestamps, "reason": reason},
        "segments": _segments(transcribed),
        "speakers": speakers,
        "settings_used": _settings_used(engine, request, decision, prompt),
        "service": _service(),
        "timings_seconds": timings,
        "gpu": _card(),
    }

    path = Path(job["result_path"])
    path.write_text(json.dumps(result), encoding="utf-8")
    outbox.put(
        _message(
            "result",
            job_id=job_id,
            path=str(path),
            wall_seconds=timings["total"],
            peak_vram_gb=round(peak_used, 2),
        )
    )


def _counter(pipeline):
    """Count tokens the way the model does, so the prompt cap is the real one."""

    def count(text: str) -> int:
        try:
            return len(pipeline.tokenizer.encode(text))
        except Exception:  # noqa: BLE001 - a rough count beats no prompt at all
            return len(text.split())

    return count


def _as_tensor(audio):
    import torch

    return torch.from_numpy(audio).unsqueeze(0)


def _as_pairs(embeddings, labels):
    """pyannote hands back one vector per speaker, in the order of its labels."""
    try:
        return zip(labels, embeddings, strict=False)
    except TypeError:
        return []


def _segments(transcribed: dict[str, Any]) -> list[dict[str, Any]]:
    segments = []
    for segment in transcribed.get("segments", []):
        one: dict[str, Any] = {
            "start": segment.get("start"),
            "end": segment.get("end"),
            "text": (segment.get("text") or "").strip(),
        }
        if segment.get("speaker"):
            one["speaker"] = segment["speaker"]
        words = segment.get("words")
        if words:
            one["words"] = [
                {
                    key: word[key]
                    for key in ("word", "start", "end", "score", "speaker")
                    if key in word
                }
                for word in words
            ]
        segments.append(one)
    return segments


def _language_part(request, detection, decision) -> dict[str, Any]:
    part: dict[str, Any] = {
        "requested": request.get("language") or "",
        "detected": decision.language,
        "probability": None,
        "windows": [],
        "combined": {},
        "mixed": False,
    }
    if detection is not None:
        part["detected"] = detection.detected
        part["probability"] = round(detection.probability, 4)
        part["windows"] = [
            {
                "offset_seconds": window.offset_seconds,
                "language": window.language,
                "probability": round(window.probability, 4),
            }
            for window in detection.windows
        ]
        part["combined"] = {
            language: round(total, 4) for language, total in detection.combined.items()
        }
        part["mixed"] = detection.mixed
    return part


def _settings_used(engine, request, decision, prompt) -> dict[str, Any]:
    return {
        "task": request.get("task", "transcribe"),
        "task_run": decision.task_run,
        "task_reason": decision.task_reason,
        "language": decision.language,
        "model": request["model"],
        "model_revision": engine.settings["model_revisions"].get(request["model"]),
        "compute_type": "float16",
        "batch_size": engine.settings["batch_size"],
        "vad": {
            "method": "pyannote",
            "onset": engine.settings["vad_onset"],
            "offset": engine.settings["vad_offset"],
            "chunk_seconds": 30,
        },
        "diarize": bool(request.get("diarize")),
        "speakers": request.get("speakers"),
        "vocabulary_terms_given": len(request.get("vocabulary") or []),
        "vocabulary_terms_used": prompt.vocabulary_terms_used,
        "context_given": bool(request.get("context")),
        "prompt_tokens": prompt.prompt_tokens,
        "return_speaker_embeddings": bool(request.get("return_speaker_embeddings")),
    }


def _service() -> dict[str, Any]:
    from service.pins import versions

    return {
        "version": SERVICE_VERSION,
        "api_version": API_VERSION,
        "pins": versions(),
    }
