"""The helpers every test file used to carry a copy of (v1.133.0).

Before this file, fifty-five test files defined the same signed_in, ten the
same stamp and two the same write_wav; a change to one would have had to be
made fifty-five times. The data-folder fixture that went with them lives in
conftest.py, where it runs for every test.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
from core.models import LoginSession


def signed_in(client, who):
    """A browser with a Login session behind it, which the middleware wants."""
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def stamp(time: str, camera: str, checked: bool = True):
    """A camera clock reading as the clock read stores it."""
    return {
        "date": "06/07/2025",
        "time": time,
        "camera": camera,
        "at": 2.0,
        "checked": checked,
    }


def write_wav(path: Path, samples: np.ndarray, rate: int = 16000) -> None:
    """One channel of 16-bit samples written as a WAV file."""
    with wave.open(str(path), "wb") as sound:
        sound.setnchannels(1)
        sound.setsampwidth(2)
        sound.setframerate(rate)
        sound.writeframes(np.clip(samples, -32767, 32767).astype(np.int16).tobytes())
