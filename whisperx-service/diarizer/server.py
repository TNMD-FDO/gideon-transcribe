"""The diarizer container (Phase 5 chapter 4, ADR 0014; the voices, ADR 0021).

Two models, loaded once from the shared model cache and served on the
WhisperX service's private network. Nemotron 3 Diarization: `POST
/v1/diarize` takes a prepared WAV (16 kHz, mono, 16-bit PCM) in the request
body and answers with the spans, `speaker_0` and on in order of arrival.
TitaNet-large, the voices (the voice plan's second release): `POST
/v1/voices` takes the prepared WAV and a list of stretches, and answers with
one vector per stretch and one per label, nothing stored. `GET /healthz`
says what is loaded. The WhisperX service is the only caller; it attributes
words to the spans itself, so both diarizers attribute words the same way.
Nothing here reads the network: the weights were fetched by the service's
`pull` and `HF_HUB_OFFLINE` is on.

The offline chunking values are the model card's, read from the environment
so an office can change them in the service's `.env` without a rebuild.
"""

from __future__ import annotations

import json
import logging
import os
import struct
import tempfile
import threading
import time
import wave
from pathlib import Path

import centroids
import numpy as np
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

# The voices (ADR 0021): TitaNet-large, pinned by revision like Nemotron,
# fetched by the same pull into the same folder. Optional: a folder without
# it still diarizes, and /v1/voices answers 503.
VOICES_MODEL = os.environ.get(
    "VOICES_MODEL", "nvidia/speakerverification_en_titanet_large"
)
VOICES_REVISION = os.environ.get("VOICES_REVISION", "")
VOICES_FILE = os.environ.get("VOICES_FILE", "speakerverification_en_titanet_large.nemo")
VOICES_BATCH = int(os.environ.get("VOICES_BATCH", "16"))
# The most stretches one request may carry: a transcript of a day's talk.
VOICES_MOST_STRETCHES = int(os.environ.get("VOICES_MOST_STRETCHES", "20000"))
RATE = 16000

app = FastAPI(title="Gideon Transcribe diarizer", docs_url=None, redoc_url=None)
_lock = threading.Lock()
_model = None
_voices = None
_loaded: dict = {}


def _snapshot_file(repository: str, revision: str, filename: str) -> str:
    """The file inside the offline cache at its pinned revision."""
    from huggingface_hub import hf_hub_download

    if revision:
        return hf_hub_download(repository, filename, revision=revision)
    return hf_hub_download(repository, filename)


def load() -> None:
    """Load the models once, from the offline cache, onto the card."""
    global _model, _voices
    from nemo.collections.asr.models import SortformerEncLabelModel

    began = time.monotonic()
    if REVISION:
        path = _snapshot_file(MODEL, REVISION, MODEL_FILE)
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
    _load_voices()


def _load_voices() -> None:
    """TitaNet beside Nemotron, when its file is in the folder."""
    global _voices
    began = time.monotonic()
    try:
        from nemo.collections.asr.models import EncDecSpeakerLabelModel

        path = _snapshot_file(VOICES_MODEL, VOICES_REVISION, VOICES_FILE)
        _voices = EncDecSpeakerLabelModel.restore_from(path, map_location="cuda")
        _voices = _voices.to("cuda").eval()
        _loaded["voices"] = {
            "model": VOICES_MODEL,
            "revision": VOICES_REVISION,
            "loaded": True,
            "load_seconds": round(time.monotonic() - began, 1),
        }
        log.info("loaded %s in %.1f s", VOICES_MODEL, _loaded["voices"]["load_seconds"])
    except Exception as error:  # noqa: BLE001 - the voices are optional
        _voices = None
        _loaded["voices"] = {
            "model": VOICES_MODEL,
            "revision": VOICES_REVISION,
            "loaded": False,
            "reason": str(error)[:200],
        }
        log.warning("the voices model is not loaded: %s", str(error)[:200])


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


# The voices --------------------------------------------------------------------
#
# The body is framed, since the standard library on the service's side sends
# no multipart: four bytes, big-endian, the length of a JSON part; the JSON;
# then the WAV. The JSON is {"stretches": [{"id", "label", "spans": [[start,
# end], ...]}], "sure_seconds": 2.0}.


def _unframe(body: bytes) -> tuple[dict, bytes]:
    if len(body) < 4:
        raise HTTPException(status_code=400, detail="the body is not framed")
    (length,) = struct.unpack(">I", body[:4])
    if length <= 0 or 4 + length > len(body):
        raise HTTPException(status_code=400, detail="the body's frame is wrong")
    try:
        request = json.loads(body[4 : 4 + length].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HTTPException(
            status_code=400, detail="the request part is not JSON"
        ) from None
    return request, body[4 + length :]


def _read_wav(data: bytes, folder: Path) -> np.ndarray:
    path = folder / "audio.wav"
    path.write_bytes(data)
    try:
        with wave.open(str(path), "rb") as handle:
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


def _embed(clips: list[np.ndarray]) -> list[np.ndarray]:
    """TitaNet's vectors for the clips, longest first in batches, in the
    clips' own order on the way out."""
    order = sorted(range(len(clips)), key=lambda i: -len(clips[i]))
    out: list[np.ndarray | None] = [None] * len(clips)
    with torch.inference_mode():
        for at in range(0, len(order), VOICES_BATCH):
            group = order[at : at + VOICES_BATCH]
            longest = max(len(clips[i]) for i in group)
            batch = torch.zeros(len(group), longest)
            lengths = torch.zeros(len(group), dtype=torch.long)
            for row, i in enumerate(group):
                batch[row, : len(clips[i])] = torch.from_numpy(clips[i])
                lengths[row] = len(clips[i])
            _, embs = _voices.forward(
                input_signal=batch.cuda(), input_signal_length=lengths.cuda()
            )
            got = embs.float().cpu().numpy()
            for row, i in enumerate(group):
                out[i] = centroids.unit(got[row].reshape(-1))
    return out  # type: ignore[return-value]


@app.post("/v1/voices")
async def voices(request: Request) -> JSONResponse:
    """The prepared WAV and the stretches in; one vector per stretch and one
    per label out. Nothing is kept."""
    if _voices is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "the voices model is not loaded; run the service's pull and "
                "restart the diarizer"
            ),
        )
    length = int(request.headers.get("content-length") or 0)
    if length > MOST_BYTES:
        raise HTTPException(status_code=413, detail="the audio is too large")
    body = await request.body()
    asked, wav_bytes = _unframe(body)
    stretches = asked.get("stretches")
    if not isinstance(stretches, list) or not stretches:
        raise HTTPException(status_code=400, detail="no stretches in the request")
    if len(stretches) > VOICES_MOST_STRETCHES:
        raise HTTPException(status_code=413, detail="too many stretches in one request")
    sure = float(asked.get("sure_seconds") or 2.0)
    began = time.monotonic()
    torch.cuda.reset_peak_memory_stats()
    with tempfile.TemporaryDirectory() as folder:
        audio = _read_wav(wav_bytes, Path(folder))
    rows: list[dict] = []
    clips: list[np.ndarray] = []
    which: list[int] = []
    for index, one in enumerate(stretches):
        spans = one.get("spans") or []
        if not spans and "start" in one and "end" in one:
            spans = [[one["start"], one["end"]]]
        samples = centroids.cut(audio, spans)
        row = {
            "id": str(one.get("id", index)),
            "label": str(one.get("label", "")),
            "net_seconds": centroids.net_seconds(samples),
            "rms_dbfs": centroids.rms_dbfs(samples),
            "vector": None,
        }
        rows.append(row)
        if row["net_seconds"] >= centroids.LEAST_SECONDS:
            clips.append(samples)
            which.append(index)
    with _lock:
        vectors = _embed(clips) if clips else []
    for index, vector in zip(which, vectors, strict=True):
        rows[index]["vector"] = [round(float(x), 6) for x in vector]
    labels = centroids.labels_from(rows, sure)
    return JSONResponse(
        {
            "stretches": rows,
            "labels": labels,
            "sure_seconds": sure,
            "model": {
                "name": VOICES_MODEL,
                "revision": VOICES_REVISION,
                "nemo": _loaded.get("nemo", "?"),
            },
            "seconds": round(time.monotonic() - began, 2),
            "card_peak_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2)
            if torch.cuda.is_available()
            else None,
        }
    )
