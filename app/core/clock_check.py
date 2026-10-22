"""The clock verdict (ADR 0022, v1.151.0): the transcript's clock against
the audio's own energy.

The recogniser cuts the audio by voice activity, writes the words of each
chunk, and the aligner places every word inside its chunk's window. When it
writes words for only part of a chunk, which phone audio and long holds
invite, the words land at the window's start: a block of lines sits early
and a hole appears after it where the speech really is. The recogniser
reports no doubt about this; only the audio does. Measured on one of the
office's calls (2026-10-22): a block sixteen seconds early, and the same
shape nine times across the call.

So as a Transcript lands, after the Call system's pass and before the
Speaker check, the audio's pauses are measured once (ffmpeg's silence
detection on the prepared audio the recogniser itself was sent) and held
against the lines:

- rule 1, a hole the audio fills: eight seconds or more with no line,
  where the audio has sound for over seven tenths of it;
- rule 2, a line over a pause: a line of two seconds or more whose words
  are said to run across over a second of quiet inside it;
- rule 3, the bound: a block of lines (the run between two long gaps)
  that has a line over a pause and a sound-filled hole after it is marked
  "the clock here may be off by up to N seconds", N the hole's length.

Nothing moves and no word changes: the mark is kept on each line of the
block (`Segment.clock`), and every place that plays a moment reads it: the
transcript, the samples, the guided page's line screen, the Preview. A
marked line plays a wider window, to the end of the hole; the voice step
gives it no vector; it is never a Sample. Sliding the block into the hole
is left for later, with the measurement behind it, as the ADR says.

The thresholds are the build's constants, from the shape measured on the
office's call; they move only if the ear says so on a local sheet.
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass

from django.utils import timezone

log = logging.getLogger(__name__)

# Rule 1: a gap of this many seconds or more with no line is a hole, and a
# hole counts when the audio has sound for over this share of it.
HOLE_SECONDS = 8.0
SOUND_SHARE = 0.7
# Rule 2: a line of this length or more that spans a pause of this length
# or more, the pause sitting inside the line by this inset at both ends.
LINE_SHORTEST = 2.0
PAUSE_SECONDS = 1.2
PAUSE_INSET = 0.3
# The audio's pauses: quieter than this, for the pause's length.
NOISE_DB = -32
# Play reaches this far either side of a line, marked or not.
EDGE = 0.5
# ffmpeg's time on a long recording.
MEASURE_TIMEOUT = 900


@dataclass
class Row:
    pk: int
    start: float
    end: float
    clock: dict | None = None


def silences(path) -> list[tuple[float, float]]:
    """The audio's pauses of PAUSE_SECONDS or more, as (start, end) pairs,
    from ffmpeg's silence detection; empty when it cannot be run."""
    try:
        done = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-nostats",
                "-i",
                str(path),
                "-af",
                f"silencedetect=noise={NOISE_DB}dB:d={PAUSE_SECONDS}",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=MEASURE_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        log.warning("the audio's pauses could not be measured: %s", error)
        return []
    starts = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", done.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", done.stderr)]
    out = []
    for start, end in zip(starts, ends, strict=False):
        if end > start:
            out.append((start, end))
    return out


def _measure(path) -> list[tuple[float, float]] | None:
    """The pauses of one prepared audio file, or None when it is not on disk
    (a transcript from long ago, or a Live recording's stretches). Kept
    apart so a test can stand in for ffmpeg."""
    if path is None or not path.exists():
        return None
    return silences(path)


def sound_in(a: float, b: float, quiet: list[tuple[float, float]]) -> float:
    """Seconds of sound inside [a, b]."""
    silent = 0.0
    for start, end in quiet:
        lo, hi = max(a, start), min(b, end)
        if hi > lo:
            silent += hi - lo
    return max(0.0, (b - a) - silent)


def spans_a_pause(row: Row, quiet: list[tuple[float, float]]) -> bool:
    """Rule 2."""
    if row.end - row.start < LINE_SHORTEST:
        return False
    return any(
        start >= row.start + PAUSE_INSET and end <= row.end - PAUSE_INSET
        for start, end in quiet
    )


def judge(rows: list[Row], quiet: list[tuple[float, float]]) -> dict:
    """The verdicts for one Side's lines, in time order: the marks as
    {segment pk: clock dict}, and the counts. Pure, for the tests."""
    marks: dict[int, dict] = {}
    if not rows:
        return {"marks": marks, "holes": 0, "blocks": 0}
    # The blocks: runs of lines split at every long gap, and whether the gap
    # after each block is a hole the audio fills.
    blocks: list[list[Row]] = [[rows[0]]]
    for before, row in zip(rows, rows[1:], strict=False):
        if row.start - before.end >= HOLE_SECONDS:
            blocks.append([row])
        else:
            blocks[-1].append(row)
    holes = 0
    marked_blocks = 0
    for block, following in zip(blocks, blocks[1:] + [None], strict=False):
        if following is None:
            continue
        gap_start, gap_end = block[-1].end, following[0].start
        length = gap_end - gap_start
        filled = sound_in(gap_start, gap_end, quiet) / length > SOUND_SHARE
        if not filled:
            continue
        holes += 1
        if not any(spans_a_pause(row, quiet) for row in block):
            continue
        marked_blocks += 1
        head = block[0].pk
        for row in block:
            marks[row.pk] = {
                "bound": round(length, 1),
                "to": round(gap_end, 2),
                "hole": [round(gap_start, 2), round(gap_end, 2)],
                "block": head,
            }
    return {"marks": marks, "holes": holes, "blocks": marked_blocks}


def mark(transcript) -> dict:
    """Measure and mark one Transcript; every line's verdict is written,
    the clear ones as None. Returns the counts, or {"measured": False}
    when the prepared audio is not on disk or cannot be measured."""
    from core.jobs import Segment

    recording = transcript.recording
    sides = {side.pk: side for side in recording.sides.all()}
    if not sides:
        return {"measured": False, "why": "no sides"}
    rows_by_side: dict[int, list[Row]] = {}
    segments = list(
        transcript.segments.filter(same_as_other_side=False).order_by("start", "id")
    )
    only_side = next(iter(sides.values())) if len(sides) == 1 else None
    for segment in segments:
        side = sides.get(segment.side_id) or only_side
        if side is None:
            continue
        rows_by_side.setdefault(side.pk, []).append(
            Row(segment.pk, float(segment.start), float(segment.end))
        )
    marks: dict[int, dict] = {}
    holes = blocks = 0
    measured = 0
    for side_pk, rows in rows_by_side.items():
        quiet = _measure(sides[side_pk].asr_path)
        if quiet is None:
            continue
        measured += 1
        verdict = judge(rows, quiet)
        marks.update(verdict["marks"])
        holes += verdict["holes"]
        blocks += verdict["blocks"]
    if not measured:
        return {"measured": False, "why": "the prepared audio is not on disk"}
    for segment in segments:
        segment.clock = marks.get(segment.pk)
    Segment.objects.bulk_update(segments, ["clock"], batch_size=500)
    counts = {
        "measured": True,
        "holes": holes,
        "blocks": blocks,
        "marked": len(marks),
        "at": timezone.now().isoformat(timespec="seconds"),
    }
    provenance = dict(transcript.provenance or {})
    provenance["clock_check"] = counts
    transcript.provenance = provenance
    transcript.save(update_fields=["provenance"])
    return counts


def on_landed(transcript) -> None:
    """As a transcript lands: the clock verdict, never failing the landing."""
    try:
        counts = mark(transcript)
        if counts.get("marked"):
            log.info(
                "clock verdict: %d lines in %d blocks marked on recording %s",
                counts["marked"],
                counts["blocks"],
                transcript.recording_id,
            )
    except Exception:  # noqa: BLE001 - the verdict must never fail a transcript
        log.exception("the clock could not be checked")


def mark_if_missed(transcript) -> dict | None:
    """The verdict a Transcript never had: given once, when a check runs, to
    a transcript from before this release. One that was measured is left
    alone, and a failure never fails the caller."""
    if (transcript.provenance or {}).get("clock_check") is not None:
        return None
    try:
        return mark(transcript)
    except Exception:  # noqa: BLE001
        log.exception("the clock could not be checked later")
        return None


def window(segment) -> tuple[float, float]:
    """Where play reaches for this line: half a second either side, and on
    a marked line to the end of the hole beside it."""
    verdict = getattr(segment, "clock", None) or {}
    end = float(verdict.get("to") or segment.end)
    return max(0.0, float(segment.start) - EDGE), end + EDGE


def verdict_json(segment) -> dict | None:
    """The line's verdict as the pages read it, or None when the clock is
    sure: the bound, where the sound is, the clock the audio suggests, and
    whether this line heads its block."""
    verdict = getattr(segment, "clock", None)
    if not verdict:
        return None
    start = float(segment.start)
    bound = float(verdict.get("bound") or 0)
    return {
        "bound": bound,
        "to": float(verdict.get("to") or segment.end),
        "hole": verdict.get("hole") or [],
        "about": round(start + bound, 1),
        "head": verdict.get("block") == segment.pk,
        "play_from": max(0.0, start - EDGE),
        "play_to": float(verdict.get("to") or segment.end) + EDGE,
    }
