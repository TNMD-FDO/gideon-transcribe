"""The voices' arithmetic (ADR 0021, the voice plan's second release): plain
numpy, no torch, so it is tested on any machine. The container's server
imports it beside the model.

A stretch's clip is the samples of its spans laid end to end; its vector is
the model's, made unit length here. A label's vector is the mean of its
stretches of `sure_seconds` or more, outliers dropped (more than two and a
half scaled median deviations below the median cosine to the mean) and the
mean re-taken until it settles; at least three stretches, else no vector.
The rule is the one `docs/research/speaker-verification.md` measured as
rule B.
"""

from __future__ import annotations

import math

import numpy as np

RATE = 16000
MIN_MEMBERS = 3
MAD_SCALE = 1.4826
MAD_CUT = 2.5
KEEP_SHARE = 0.6
ROUNDS = 10
# Under this much speech a stretch gets no vector: the model's output on a
# few hundred milliseconds is noise.
LEAST_SECONDS = 0.5


def unit(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    return vector / norm if norm else vector


def cut(audio: np.ndarray, spans: list, rate: int = RATE) -> np.ndarray:
    """The spans' samples laid end to end, clipped to the audio's length,
    overlapping spans merged first so no sample is heard twice."""
    merged: list[list[float]] = []
    for pair in sorted((float(a), float(b)) for a, b in spans if b > a):
        a, b = max(0.0, pair[0]), min(len(audio) / rate, pair[1])
        if b <= a:
            continue
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    pieces = [audio[int(a * rate) : int(b * rate)] for a, b in merged]
    pieces = [piece for piece in pieces if len(piece)]
    if not pieces:
        return np.zeros(0, dtype=audio.dtype)
    return np.concatenate(pieces)


def net_seconds(samples: np.ndarray, rate: int = RATE) -> float:
    return round(len(samples) / rate, 3)


def rms_dbfs(samples: np.ndarray) -> float | None:
    """Loudness, for the hand-over's guard (a shout is not a second voice)."""
    if not len(samples):
        return None
    x = samples.astype("float64")
    if x.dtype != np.float64:
        x = x.astype("float64")
    if np.abs(x).max() > 1.5:
        x = x / 32768.0
    rms = math.sqrt(float(np.mean(x * x)))
    return round(20 * math.log10(rms), 1) if rms > 0 else None


def centroid(vectors: list[np.ndarray]) -> tuple[np.ndarray | None, int, int]:
    """The label's vector, how many stretches made it, how many were dropped."""
    kept = [unit(np.asarray(v, dtype="float32")) for v in vectors]
    total = len(kept)
    if total < MIN_MEMBERS:
        return None, 0, 0
    for _ in range(ROUNDS):
        matrix = np.stack(kept)
        centre = unit(matrix.mean(axis=0))
        cos = matrix @ centre
        median = float(np.median(cos))
        mad = float(np.median(np.abs(cos - median))) * MAD_SCALE
        cut_at = median - MAD_CUT * max(mad, 0.01)
        keep = [v for v, s in zip(kept, cos, strict=True) if s >= cut_at]
        if len(keep) < max(MIN_MEMBERS, int(KEEP_SHARE * total)) or len(keep) == len(
            kept
        ):
            break
        kept = keep
    matrix = np.stack(kept)
    return unit(matrix.mean(axis=0)), len(kept), total - len(kept)


def labels_from(stretches: list[dict], sure_seconds: float) -> list[dict]:
    """One row per label: its vector from the sure stretches, or none."""
    by_label: dict[str, list[np.ndarray]] = {}
    for one in stretches:
        if one.get("vector") is None or one.get("net_seconds", 0.0) < sure_seconds:
            continue
        by_label.setdefault(one["label"], []).append(
            np.asarray(one["vector"], dtype="float32")
        )
    rows = []
    for label in sorted(by_label):
        vector, members, dropped = centroid(by_label[label])
        rows.append(
            {
                "label": label,
                "vector": None
                if vector is None
                else [round(float(x), 6) for x in vector],
                "members": members,
                "dropped": dropped,
                "sure_stretches": len(by_label[label]),
            }
        )
    return rows
