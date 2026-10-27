"""Qwen3-ASR's path through the service (ADR 0025, service 0.8.0): the pieces
the audio is cut into, the words the recogniser container sends back, the
lines built from them, and the languages the pieces were heard in.

Nothing here touches a model or the card, so all of it is tested on its own.
The model process calls it piece by piece, and the recogniser container does
the recognising and the word timing.
"""

from __future__ import annotations

import io
import wave
from dataclasses import dataclass
from typing import Any

SAMPLE_RATE = 16000

# The pieces (the trial of 2026-10-26, docs/research/qwen3-asr.md): on the
# package's 180-second pieces the decoder stops early and leaves minutes
# empty; at 45 seconds it keeps up everywhere. The cut lands on the quietest
# 100 ms within five seconds of the target, the package's own rule, so a
# piece never ends in the middle of a word when there is a pause near by.
PIECE_SECONDS = 45.0
PIECE_SEARCH_SECONDS = 5.0
QUIET_WINDOW_MS = 100.0
# A tail shorter than this is left on the piece before it rather than sent
# as a piece of its own.
SHORTEST_TAIL_SECONDS = 1.0

# The lines: a new one at a pause this long between words, after a sentence
# end, or when the line would run past either cap. Whisper's lines ran to
# about this length; the app's pages and the Speaker check read lines, so
# the shape stays familiar.
PAUSE_SECONDS = 0.7
LONGEST_LINE_SECONDS = 15.0
LONGEST_LINE_WORDS = 40
SENTENCE_ENDS = ".?!"

# A word the aligner gives no length (issue 197: start equal to end, about
# one word in twelve on conversational audio) takes this much, cut short at
# the next word.
UNLENGTHED_SPAN_SECONDS = 0.3

# The names the model answers with, as the two-letter codes the contract and
# the app use (Whisper's codes). A name not listed is passed on lower-cased.
LANGUAGE_CODES = {
    "english": "en",
    "spanish": "es",
    "chinese": "zh",
    "cantonese": "yue",
    "french": "fr",
    "german": "de",
    "italian": "it",
    "portuguese": "pt",
    "russian": "ru",
    "japanese": "ja",
    "korean": "ko",
    "arabic": "ar",
    "vietnamese": "vi",
    "thai": "th",
    "indonesian": "id",
    "malay": "ms",
    "dutch": "nl",
    "turkish": "tr",
    "polish": "pl",
    "hindi": "hi",
    "urdu": "ur",
    "swedish": "sv",
    "danish": "da",
    "norwegian": "no",
    "finnish": "fi",
    "czech": "cs",
    "filipino": "tl",
    "persian": "fa",
    "greek": "el",
    "hungarian": "hu",
    "romanian": "ro",
    "ukrainian": "uk",
    "bulgarian": "bg",
    "hebrew": "he",
    "bengali": "bn",
    "tamil": "ta",
    "telugu": "te",
}


@dataclass(frozen=True)
class Word:
    """One word as the aligner timed it, in the whole file's seconds."""

    text: str
    start: float
    end: float
    piece: int


# The pieces -------------------------------------------------------------------


def cut_points(
    audio,
    rate: int = SAMPLE_RATE,
    piece_seconds: float = PIECE_SECONDS,
    search_seconds: float = PIECE_SEARCH_SECONDS,
    window_ms: float = QUIET_WINDOW_MS,
) -> list[tuple[int, int]]:
    """Where the audio is cut, as sample ranges laid end to end with no gap
    and no overlap: at the quietest short window within `search_seconds` of
    each target, by the sum of absolute amplitudes, then the quietest sample
    inside that window."""
    import numpy as np

    total = len(audio)
    most = int(piece_seconds * rate)
    search = int(search_seconds * rate)
    window = max(4, int(window_ms / 1000.0 * rate))
    tail = int(SHORTEST_TAIL_SECONDS * rate)
    pieces: list[tuple[int, int]] = []
    start = 0
    while total - start > most + tail:
        target = start + most
        low = max(start + 1, target - search)
        high = min(total, target + search)
        boundary = target
        if high - low > window:
            loud = np.abs(audio[low:high])
            sums = np.convolve(loud, np.ones(window, dtype=loud.dtype), mode="valid")
            at = int(np.argmin(sums))
            inside = int(np.argmin(loud[at : at + window]))
            boundary = low + at + inside
        boundary = max(start + 1, min(boundary, total))
        pieces.append((start, boundary))
        start = boundary
    pieces.append((start, total))
    return pieces


def wav_bytes(samples, rate: int = SAMPLE_RATE) -> bytes:
    """One piece as the 16 kHz mono 16-bit WAV the container reads."""
    import numpy as np

    clipped = np.clip(np.asarray(samples, dtype="float32"), -1.0, 1.0)
    pcm = (clipped * 32767.0).astype("<i2").tobytes()
    out = io.BytesIO()
    with wave.open(out, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm)
    return out.getvalue()


# The words --------------------------------------------------------------------


def code_of(name: str | None) -> str:
    """The model's language name as a code; the first of a joined list."""
    first = (name or "").split(",")[0].strip().lower()
    if not first:
        return ""
    return LANGUAGE_CODES.get(first, first)


def name_of(code: str | None) -> str | None:
    """A code the Consumer named as the name the model is told, or None to
    let the model hear the language itself."""
    for name, known in LANGUAGE_CODES.items():
        if known == (code or "").strip().lower():
            return name.capitalize()
    return None


def words_of(items: list[dict[str, Any]], offset: float, piece: int) -> list[Word]:
    """The container's timed words for one piece, moved to the whole file's
    clock. An item with no text is dropped; an item with no time is kept at
    the piece's offset with no length and spanned below."""
    words: list[Word] = []
    for item in items:
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        start = item.get("start")
        end = item.get("end")
        start = offset + float(start if start is not None else 0.0)
        end = offset + float(end if end is not None else 0.0)
        words.append(Word(text, round(start, 3), round(max(end, start), 3), piece))
    return words


def span_unlengthed(
    words: list[Word], span: float = UNLENGTHED_SPAN_SECONDS
) -> tuple[list[Word], int]:
    """Give a word with no length a short span: forward to the next word's
    start when there is room, else back from its own time to the previous
    word's end. Returns the words and how many were spanned."""
    out: list[Word] = []
    count = 0
    for index, word in enumerate(words):
        if word.end > word.start:
            out.append(word)
            continue
        count += 1
        start, end = word.start, word.start + span
        following = words[index + 1] if index + 1 < len(words) else None
        if following is None or following.start > start:
            if following is not None:
                end = min(end, following.start)
        else:
            previous = out[-1] if out else None
            floor = previous.end if previous is not None else 0.0
            start = max(floor, start - span)
            end = word.start
        if end <= start:
            end = start + 0.05
        out.append(Word(word.text, round(start, 3), round(end, 3), word.piece))
    return out, count


# The lines --------------------------------------------------------------------


def lines_of(
    words: list[Word],
    languages: dict[int, str],
    pause: float = PAUSE_SECONDS,
    longest_seconds: float = LONGEST_LINE_SECONDS,
    longest_words: int = LONGEST_LINE_WORDS,
) -> list[dict[str, Any]]:
    """The segments, built from the words: a new one at a pause, after a
    sentence end, where a piece in another language begins, or when the
    line would pass either cap. `languages` maps a piece's index to its
    code; each segment carries the language of the piece its words came
    from."""
    segments: list[dict[str, Any]] = []
    current: list[Word] = []

    def close() -> None:
        if current:
            segments.append(_segment(current, languages.get(current[0].piece, "")))
            current.clear()

    for word in words:
        if current:
            last = current[-1]
            if (
                word.start - last.end >= pause
                or last.text[-1:] in SENTENCE_ENDS
                or languages.get(word.piece, "") != languages.get(last.piece, "")
                or word.end - current[0].start > longest_seconds
                or len(current) >= longest_words
            ):
                close()
        current.append(word)
    close()
    return segments


def _segment(words: list[Word], language: str) -> dict[str, Any]:
    return {
        "start": words[0].start,
        "end": words[-1].end,
        "text": " ".join(word.text for word in words),
        "language": language,
        "words": [
            {"word": word.text, "start": word.start, "end": word.end} for word in words
        ],
    }


def split_at_speakers(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """After the diarizer has given each word its speaker: a line whose words
    belong to two speakers is split where the speaker changes, so a line is
    one voice. A word with no speaker stays with the run it is in."""
    out: list[dict[str, Any]] = []
    for segment in segments:
        words = segment.get("words") or []
        runs: list[list[dict[str, Any]]] = []
        who: str | None = None
        for word in words:
            speaker = word.get("speaker")
            if runs and (speaker is None or speaker == who):
                runs[-1].append(word)
                continue
            runs.append([word])
            who = speaker
        if len(runs) <= 1:
            out.append(segment)
            continue
        for run in runs:
            speaker = next((w.get("speaker") for w in run if w.get("speaker")), None)
            piece = {
                "start": run[0]["start"],
                "end": run[-1]["end"],
                "text": " ".join(w["word"] for w in run),
                "language": segment.get("language", ""),
                "words": run,
            }
            if speaker:
                piece["speaker"] = speaker
            out.append(piece)
    return out


def fill_speakers(segments: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """A line none of whose words fell inside a diarizer span has no speaker
    (service 0.8.1): under lines cut at pauses such a fragment is a line of
    its own, where Whisper's longer utterance carried it under a speaker.
    It takes the speaker of its nearest neighbour in time, the previous
    line when the gaps are equal; a file with no speaker anywhere is left
    as it is. Returns the lines and how many were filled."""
    if not any(segment.get("speaker") for segment in segments):
        return segments, 0
    out: list[dict[str, Any]] = []
    filled = 0
    for index, segment in enumerate(segments):
        if segment.get("speaker"):
            out.append(segment)
            continue
        before = next((s for s in reversed(segments[:index]) if s.get("speaker")), None)
        after = next((s for s in segments[index + 1 :] if s.get("speaker")), None)
        chosen = None
        if before is not None and after is not None:
            gap_before = segment["start"] - before["end"]
            gap_after = after["start"] - segment["end"]
            chosen = before if gap_before <= gap_after else after
        else:
            chosen = before if before is not None else after
        if chosen is None:
            out.append(segment)
            continue
        out.append({**segment, "speaker": chosen["speaker"]})
        filled += 1
    return out, filled


# The languages ----------------------------------------------------------------

# A second language counts as present, and the file as mixed, from this
# much of it: a greeting in the other language does not make a call mixed.
MIXED_LEAST_SECONDS = 10.0
MIXED_LEAST_SHARE = 0.1


def language_part(
    pieces: list[dict[str, Any]], requested: str | None
) -> dict[str, Any]:
    """The result's `language` part from the pieces: the most spoken wins,
    its share of the seconds stands as the probability, and the file is
    mixed when a second language holds enough of it."""
    seconds: dict[str, float] = {}
    for piece in pieces:
        code = piece.get("language") or ""
        if not code:
            continue
        seconds[code] = seconds.get(code, 0.0) + float(piece.get("seconds") or 0.0)
    total = sum(seconds.values())
    combined = {
        code: round(amount / total, 4) if total else 0.0
        for code, amount in sorted(seconds.items())
    }
    detected = (
        max(combined, key=lambda code: (combined[code], code)) if combined else ""
    )
    others = [
        code
        for code, amount in seconds.items()
        if code != detected
        and amount >= MIXED_LEAST_SECONDS
        and total
        and amount / total >= MIXED_LEAST_SHARE
    ]
    return {
        "requested": requested or "",
        "detected": requested or detected,
        "probability": combined.get(detected) if detected else None,
        "windows": [],
        "combined": combined,
        "mixed": bool(others),
        "pieces": [
            {
                "offset_seconds": piece.get("offset_seconds"),
                "seconds": piece.get("seconds"),
                "language": piece.get("language") or "",
            }
            for piece in pieces
        ],
    }


def count_words(text: str) -> int:
    """The prompt rule's counter under this recogniser: the context is a
    system message with no token slot to fit, so words stand for tokens."""
    return len(text.split())
