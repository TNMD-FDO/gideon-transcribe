"""The diarizer container (Phase 5 chapter 4, ADR 0014).

One model, Nemotron 3 Diarization, loaded once from the shared model cache and
served on the WhisperX service's private network: `POST /v1/diarize` takes a
prepared WAV (16 kHz, mono, 16-bit PCM) in the request body and answers with
the spans, `speaker_0` and on in order of arrival; `GET /healthz` says the
model is loaded. The WhisperX service is the only caller; it attributes words
to the spans itself, so both diarizers attribute words the same way. Nothing
here reads the network: the weights were fetched by the service's `pull` and
`HF_HUB_OFFLINE` is on.

The offline chunking values are the model card's, read from the environment
so an office can change them in the service's `.env` without a rebuild.
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
import time
from pathlib import Path

import torch
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

log = logging.getLogger("diarizer")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

MODEL = os.environ.get("DIARIZER_MODEL", "nvidia/Nemotron-3-Diarization")
REVISION = os.environ.get("DIARIZER_REVISION", "")
# The one file in the repository that holds the model. The service's pull
# fetched the snapshot at REVISION; the file is looked up at that revision, so
# the offline cache answers. NeMo's own from_pretrained asks for "main", which
# a snapshot fetched by commit does not record, and offline that is a refusal.
MODEL_FILE = os.environ.get("DIARIZER_MODEL_FILE", "Nemotron-3-Diarization.nemo")
# The model card's offline configuration, in frames of 80 ms.
CHUNKING = {
    "spkcache_len": int(os.environ.get("DIARIZER_SPKCACHE_LEN", "264")),
    "fifo_len": int(os.environ.get("DIARIZER_FIFO_LEN", "40")),
    "chunk_len": int(os.environ.get("DIARIZER_CHUNK_LEN", "340")),
    "chunk_right_context": int(os.environ.get("DIARIZER_RIGHT_CONTEXT", "40")),
    "spkcache_update_period": int(os.environ.get("DIARIZER_UPDATE_PERIOD", "300")),
}
# A WAV over this many bytes is refused before it is read: eight hours of 16
# kHz mono 16-bit audio is about 921 MB, and the WhisperX service refuses over
# eight hours itself.
MOST_BYTES = int(os.environ.get("DIARIZER_MOST_BYTES", str(1024 * 1024 * 1024)))

app = FastAPI(title="Gideon Transcribe diarizer", docs_url=None, redoc_url=None)
_lock = threading.Lock()
_model = None
_loaded: dict = {}


def load() -> None:
    """Load the model once, from the offline cache, onto the card."""
    global _model
    from nemo.collections.asr.models import SortformerEncLabelModel

    began = time.monotonic()
    if REVISION:
        from huggingface_hub import hf_hub_download

        path = hf_hub_download(MODEL, MODEL_FILE, revision=REVISION)
        model = SortformerEncLabelModel.restore_from(path, map_location="cuda")
    else:
        model = SortformerEncLabelModel.from_pretrained(MODEL, map_location="cuda")
    model = model.to("cuda").eval()
    mods = getattr(model, "sortformer_modules", None)
    if mods is not None:
        for key, value in CHUNKING.items():
            if hasattr(mods, key):
                setattr(mods, key, value)
        if hasattr(model, "_check_streaming_parameters"):
            model._check_streaming_parameters()
    _model = model
    _loaded.update(
        {
            "model": MODEL,
            "revision": REVISION,
            "nemo": _nemo_version(),
            "torch": torch.__version__,
            "chunking": CHUNKING,
            "load_seconds": round(time.monotonic() - began, 1),
        }
    )
    log.info("loaded %s in %.1f s", MODEL, _loaded["load_seconds"])


def _nemo_version() -> str:
    try:
        import nemo

        return str(getattr(nemo, "__version__", "?"))
    except Exception:  # noqa: BLE001
        return "?"


@app.on_event("startup")
def _startup() -> None:
    load()


@app.get("/healthz")
def healthz() -> JSONResponse:
    if _model is None:
        return JSONResponse({"ok": False, "reason": "loading"}, status_code=503)
    return JSONResponse({"ok": True, **_loaded})


def _spans_of(prediction) -> list[dict]:
    spans = []
    for one in prediction:
        if isinstance(one, str):
            parts = one.split()
            start, end, who = float(parts[0]), float(parts[1]), parts[2]
        else:
            start, end, who = float(one[0]), float(one[1]), str(one[2])
        if end <= start:
            continue
        spans.append({"start": round(start, 3), "end": round(end, 3), "speaker": who})
    spans.sort(key=lambda one: (one["start"], one["end"]))
    return spans


@app.post("/v1/diarize")
async def diarize(request: Request) -> JSONResponse:
    """The prepared WAV in the body; the spans back. One job at a time, as
    the WhisperX service itself runs one job at a time."""
    if _model is None:
        raise HTTPException(status_code=503, detail="the model is still loading")
    length = int(request.headers.get("content-length") or 0)
    if length > MOST_BYTES:
        raise HTTPException(status_code=413, detail="the audio is too large")
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="no audio in the body")
    began = time.monotonic()
    with tempfile.TemporaryDirectory() as folder:
        wav = Path(folder) / "audio.wav"
        wav.write_bytes(body)
        with _lock, torch.inference_mode():
            predictions = _model.diarize(
                audio=[str(wav)], batch_size=1, include_tensor_outputs=False
            )
    prediction = (
        predictions[0] if isinstance(predictions, (list, tuple)) else predictions
    )
    spans = _spans_of(prediction)
    return JSONResponse(
        {
            "spans": spans,
            "speakers": sorted({one["speaker"] for one in spans}),
            "model": {
                "name": MODEL,
                "revision": REVISION,
                "nemo": _loaded.get("nemo", "?"),
            },
            "seconds": round(time.monotonic() - began, 2),
        }
    )
