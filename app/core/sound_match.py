"""Matching two cameras by sound (Phase 6 chapter 1).

Two body cameras within earshot of each other hear the same doors, voices
and sirens a fraction of a second apart. This compares the loudness of the
two recordings over time and finds the shift at which they agree best. It
reads the ASR audio the app already keeps for each recording (16 kHz mono
WAV), never the picture, and nothing goes to the engine.

The method: the sound is cut into 20 ms frames and each frame's loudness
taken in decibels, so a shout and a whisper both count as change; each
frame is compared with the two seconds around it, so only changes count and
the general level of one camera against the other does not; the two rows
of numbers are cross-correlated (with a fast Fourier transform, since a
forty-minute recording is 120,000 frames); the best shift wins. Its
strength is how far the best shift stands above the next best shift more
than three seconds away: a true match is a spike, a false one a plateau.
"""

from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

HOP_SECONDS = 0.02
SMOOTH_SECONDS = 2.0
APART_SECONDS = 3.0
CHUNK_FRAMES = 1 << 20


class NoMatch(Exception):
    """The two cannot be compared: no sound, too short, or unreadable."""


@dataclass(frozen=True)
class Match:
    # The other recording starts `lag` seconds after the reference.
    lag: float
    strength: float


def envelope(path: Path, hop: float = HOP_SECONDS) -> np.ndarray:
    """Loudness per `hop` seconds, in decibels, from a 16-bit mono WAV."""
    try:
        with wave.open(str(path), "rb") as sound:
            rate = sound.getframerate()
            channels = sound.getnchannels()
            width = sound.getsampwidth()
            if width != 2:
                raise NoMatch("the sound is not 16-bit")
            per_frame = max(1, int(rate * hop))
            frames: list[np.ndarray] = []
            carry = np.zeros(0, dtype=np.float32)
            while True:
                raw = sound.readframes(CHUNK_FRAMES)
                if not raw:
                    break
                samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
                if channels > 1:
                    samples = samples.reshape(-1, channels).mean(axis=1)
                samples = np.concatenate([carry, samples])
                whole = (len(samples) // per_frame) * per_frame
                block = samples[:whole].reshape(-1, per_frame)
                frames.append(np.sqrt((block * block).mean(axis=1) + 1e-6))
                carry = samples[whole:]
    except (wave.Error, EOFError, OSError) as why:
        raise NoMatch("the sound could not be read") from why
    if not frames:
        raise NoMatch("the sound is empty")
    rms = np.concatenate(frames)
    return 20.0 * np.log10(rms / 32768.0 + 1e-9)


def _changes(loud: np.ndarray, hop: float) -> np.ndarray:
    """Each frame against the two seconds around it, scaled to unit spread."""
    width = max(1, int(SMOOTH_SECONDS / hop))
    kernel = np.ones(width, dtype=np.float32) / width
    local = np.convolve(loud, kernel, mode="same")
    out = loud - local
    spread = float(out.std())
    if spread < 1e-6:
        raise NoMatch("the sound does not change")
    return (out / spread).astype(np.float32)


def lag_between(
    reference: Path,
    other: Path,
    *,
    expected: float | None = None,
    window: float = 600.0,
    hop: float = HOP_SECONDS,
) -> Match:
    """How many seconds after `reference` the sound of `other` begins.

    `expected`, when the files' own times give one, narrows the search to
    `window` seconds either side of it; otherwise every shift at which the
    two overlap by at least a minute is tried.
    """
    a = _changes(envelope(reference, hop), hop)
    b = _changes(envelope(other, hop), hop)
    if len(a) < int(60 / hop) or len(b) < int(60 / hop):
        raise NoMatch("the sound is too short to compare")
    size = 1 << int(np.ceil(np.log2(len(a) + len(b))))
    spectrum = np.fft.rfft(a, size) * np.conj(np.fft.rfft(b, size))
    correlation = np.fft.irfft(spectrum, size)
    # Index k of the correlation is the shift of `other` against `reference`
    # in frames: positive shifts sit at the front, negative ones wrap to the
    # back. Lay them out on one axis from -len(b) to +len(a).
    lags = np.concatenate([np.arange(0, len(a)), np.arange(-len(b) + 1, 0)])
    values = np.concatenate([correlation[: len(a)], correlation[size - len(b) + 1 :]])
    # The two must overlap by a minute for the shift to mean anything.
    overlap = np.minimum(len(a) - lags, len(b) + lags)
    keep = overlap >= int(60 / hop)
    if expected is not None:
        centre = int(round(expected / hop))
        keep &= np.abs(lags - centre) <= int(window / hop)
    if not keep.any():
        raise NoMatch("the two never overlap")
    # Normalise by the overlap so a long overlap does not win by length alone.
    scores = np.where(keep, values / np.maximum(overlap, 1), -np.inf)
    best = int(np.argmax(scores))
    peak = float(scores[best])
    apart = np.abs(lags - lags[best]) > int(APART_SECONDS / hop)
    rivals = scores[keep & apart]
    second = float(rivals.max()) if rivals.size else 0.0
    if peak <= 0:
        raise NoMatch("the sounds do not line up anywhere")
    strength = peak / second if second > 0 else float("inf")
    return Match(lag=float(lags[best]) * hop, strength=float(min(strength, 99.0)))
