"""The recogniser container (Phase 1 chapter 7, ADR 0025): Qwen3-ASR-1.7B
and Qwen3-ForcedAligner-0.6B, loaded from the shared model folder and served
on the WhisperX service's private network.

One call: `POST /v1/recognise` takes one piece of prepared audio (16 kHz,
mono, 16-bit PCM) with the context line, framed as the diarizer's voices
request is (four bytes of JSON length, the JSON, the WAV), and answers with
the text, the language heard and every word with its time. The WhisperX
service is the only caller: it cuts the audio into pieces, builds the lines
from the words and diarizes, so the result shape is one whichever recogniser
ran. Nothing here reads the network: the weights were fetched by the
service's `pull` and `HF_HUB_OFFLINE` is on.

The models load on the first piece, not at start, so an office that keeps
the Whisper recogniser pays nothing on the card for this container.
"""

from __future__ import annotations

import json
import logging
import os
import struct
import threading
import time
import wave
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version

import numpy as np
import torch
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

log = logging.getLogger("recogniser")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

MODEL = os.environ.get("RECOGNISER_MODEL", "Qwen/Qwen3-ASR-1.7B")
REVISION = os.environ.get("RECOGNISER_REVISION", "")
ALIGNER = os.environ.get("RECOGNISER_ALIGNER", "Qwen/Qwen3-ForcedAligner-0.6B")
ALIGNER_REVISION = os.environ.get("RECOGNISER_ALIGNER_REVISION", "")
# flash_attention_2 is what the trial ran and what the package's attention
# window needs; sdpa is the fallback for a card the wheel does not cover.
ATTENTION = os.environ.get("RECOGNISER_ATTENTION", "flash_attention_2")
# The decoder's cap per piece: a 45-second piece of fast speech is under
# 300 tokens, so this is room, not a limit that cuts.
MAX_NEW_TOKENS = int(os.environ.get("RECOGNISER_MAX_NEW_TOKENS", "1024"))
# A piece over this is refused: the aligner's own cap is 180 seconds, and
# the service cuts at about 45.
MOST_SECONDS = float(os.environ.get("RECOGNISER_MOST_SECONDS", "180"))
RATE = 16000

app = FastAPI(title="Gideon Transcribe recogniser", docs_url=None, redoc_url=None)
_lock = threading.Lock()
_model = None
_loaded: dict = {}


def _version(name: str) -> str | None:
    try:
        return package_version(name)
    except PackageNotFoundError:
        return None


def _snapshot(repository: str, revision: str) -> str:
    """The model's folder inside the offline cache at its pinned revision:
    a lookup by name would read the hub's note of where a branch points,
    which a fetch of one revision never writes."""
    from huggingface_hub import snapshot_download

    if revision:
        return snapshot_download(repository, revision=revision)
    return snapshot_download(repository)


def load() -> None:
    """Load both models once, from the offline cache, onto the card."""
    global _model
    from qwen_asr import Qwen3ASRModel

    began = time.monotonic()
    kwargs = {"dtype": torch.bfloat16, "device_map": "cuda:0"}
    if ATTENTION != "default":
        kwargs["attn_implementation"] = ATTENTION
    _model = Qwen3ASRModel.from_pretrained(
        _snapshot(MODEL, REVISION),
        forced_aligner=_snapshot(ALIGNER, ALIGNER_REVISION),
        forced_aligner_kwargs=dict(kwargs),
        max_inference_batch_size=1,
        max_new_tokens=MAX_NEW_TOKENS,
        **kwargs,
    )
    _loaded.update(
        {
            "loaded": True,
            "load_seconds": round(time.monotonic() - began, 1),
            "card_gb_after_load": round(torch.cuda.memory_allocated() / 1e9, 2)
            if torch.cuda.is_available()
            else None,
        }
    )
    log.info("loaded %s and %s in %.1f s", MODEL, ALIGNER, _loaded["load_seconds"])


def _ensure_loaded() -> None:
    if _model is None:
        with _lock:
            if _model is None:
                load()


def _facts() -> dict:
    return {
        "model": MODEL,
        "revision": REVISION,
        "aligner": ALIGNER,
        "aligner_revision": ALIGNER_REVISION,
        "attention": ATTENTION,
        "versions": {
            "qwen-asr": _version("qwen-asr"),
            "transformers": _version("transformers"),
            "torch": torch.__version__,
            "flash-attn": _version("flash-attn"),
        },
        "loaded": bool(_loaded.get("loaded")),
        **{key: value for key, value in _loaded.items() if key != "loaded"},
    }


@app.get("/healthz")
def healthz() -> JSONResponse:
    """Up as soon as the process answers; `loaded` says whether the models
    are on the card yet."""
    return JSONResponse({"ok": True, **_facts()})


def _unframe(body: bytes) -> tuple[dict, bytes]:
    if len(body) < 4:
        raise HTTPException(status_code=400, detail="the body is not framed")
    (length,) = struct.unpack(">I", body[:4])
    if length <= 0 or 4 + length > len(body):
        raise HTTPException(status_code=400, detail="the body's frame is wrong")
    try:
        asked = json.loads(body[4 : 4 + length].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(
            status_code=400, detail="the request part is not JSON"
        ) from None
    return asked, body[4 + length :]


def _read_wav(data: bytes) -> np.ndarray:
    import io

    try:
        with wave.open(io.BytesIO(data), "rb") as handle:
            if (
                handle.getnchannels() != 1
                or handle.getsampwidth() != 2
                or handle.getframerate() != RATE
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "the audio must be 16 kHz, mono, 16-bit PCM, as the "
                        "service prepares it"
                    ),
                )
            frames = handle.readframes(handle.getnframes())
    except wave.Error:
        raise HTTPException(
            status_code=400, detail="the audio is not a WAV file"
        ) from None
    return np.frombuffer(frames, dtype="<i2").astype("float32") / 32768.0


def _items(stamps) -> list[dict]:
    if stamps is None:
        return []
    items = getattr(stamps, "items", None)
    if items is None:
        items = stamps if isinstance(stamps, list) else []
    out = []
    for item in items:
        if isinstance(item, dict):
            text = item.get("text")
            start = item.get("start_time")
            end = item.get("end_time")
        else:
            text = getattr(item, "text", None)
            start = getattr(item, "start_time", None)
            end = getattr(item, "end_time", None)
        out.append(
            {
                "text": text,
                "start": None if start is None else float(start),
                "end": None if end is None else float(end),
            }
        )
    return out


@app.post("/v1/recognise")
async def recognise(request: Request) -> JSONResponse:
    """One piece in; the text, the language and the timed words out. One at
    a time, as the WhisperX service itself runs one job at a time."""
    body = await request.body()
    asked, wav_bytes = _unframe(body)
    context = str(asked.get("context") or "")
    language = asked.get("language") or None
    audio = _read_wav(wav_bytes)
    seconds = len(audio) / RATE
    if seconds > MOST_SECONDS:
        raise HTTPException(
            status_code=413,
            detail=(
                f"the piece is {seconds:.0f} seconds long, and the most is "
                f"{MOST_SECONDS:.0f}"
            ),
        )
    if len(audio) == 0:
        raise HTTPException(status_code=400, detail="no audio in the piece")
    _ensure_loaded()
    began = time.monotonic()
    with _lock:
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
        with torch.inference_mode():
            results = _model.transcribe(
                audio=(audio, RATE),
                context=context,
                language=language,
                return_time_stamps=True,
            )
    result = results[0]
    return JSONResponse(
        {
            "text": result.text or "",
            "language": getattr(result, "language", "") or "",
            "words": _items(getattr(result, "time_stamps", None)),
            "seconds": round(time.monotonic() - began, 2),
            "audio_seconds": round(seconds, 3),
            "card_peak_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2)
            if torch.cuda.is_available()
            else None,
            "model": {
                "name": MODEL,
                "revision": REVISION,
                "aligner": ALIGNER,
                "aligner_revision": ALIGNER_REVISION,
            },
        }
    )
