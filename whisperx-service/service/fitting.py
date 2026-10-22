"""The words fitted over the whole file (service 0.7.0; the app's ADR 0023).

Whisper writes its own rough stamps for each utterance, and WhisperX fits
the words of an utterance only inside those stamps. When a file opens with
speech Whisper does not write down (noise, a far party, a hold), it stamps
the words it did write at the start of what it was given, and the word
fitting is confined there: a block of lines lands seconds early, however
short the file. A Consumer that re-reads a short window to place its words
asks for `fit_words_over_whole`: before the fitting runs, every segment's
text is joined into one segment spanning the whole file, so the fitter, a
forced alignment of the text against the sound, may place every word
anywhere in it and skips the sound that has no words. Meant for a short
file; the service refuses it over FIT_WHOLE_MAX_SECONDS, because on a long
file the segments are what keep the fitting tractable.
"""

from __future__ import annotations

from typing import Any

FIT_WHOLE_MAX_SECONDS = 60.0


def one_segment_over(
    segments: list[dict[str, Any]], duration: float
) -> list[dict[str, Any]]:
    """Every segment's text as one segment over [0, duration]. Empty text
    gives no segment at all, so the fitter has nothing to place."""
    text = " ".join(
        str(one.get("text", "")).strip()
        for one in segments
        if str(one.get("text", "")).strip()
    )
    if not text:
        return []
    return [{"start": 0.0, "end": round(max(0.0, float(duration)), 3), "text": text}]
