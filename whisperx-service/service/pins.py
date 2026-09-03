"""The versions of what actually produced a result.

Every result carries these, so that a Consumer's provenance can say which
engine wrote a transcript. A package that is not installed reads as None
rather than raising: the API layer is meant to run without the GPU stack, and
the tests rely on that.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version

PINNED = (
    "whisperx",
    "faster-whisper",
    "ctranslate2",
    "torch",
    "pyannote.audio",
)


def versions() -> dict[str, str | None]:
    found: dict[str, str | None] = {}
    for name in PINNED:
        try:
            found[name] = package_version(name)
        except PackageNotFoundError:
            found[name] = None
    return found
