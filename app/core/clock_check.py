"""The clock verdict (ADR 0022, v1.151.0) and the clock re-read (ADR 0023,
v1.152.0): the transcript's clock against the audio's own energy, and the
audio placing a squeezed block again.

The recogniser cuts the audio by voice activity, writes the words of each
chunk, and the aligner places every word inside its chunk's window. When it
writes words for only part of a chunk, which phone audio and long holds
invite, the words land at the window's start: a block of lines sits early
and a hole appears after it where the speech really is. The recogniser
reports no doubt about this; only the audio does. Measured on one of the
office's calls (2026-10-22): a block sixteen seconds early, and the same
shape nine times across the call. Read against the audio the next day: a
line early in the block was eight seconds early and a line late in it
sixteen, thirty-three seconds of talk squeezed into seventeen.

So as a Transcript lands, after the Call system's pass and before the
Speaker check, the audio's pauses are measured once (ffmpeg's silence
detection on the prepared audio the recogniser itself was sent) and held
against the lines:

- rule 1, a hole the audio fills: eight seconds or more with no line,
  where the audio has sound for over seven tenths of it;
- rule 2, a line over a pause: a line of two seconds or more whose words
  are said to run across over a second of quiet inside it;
- rule 3, the bound: the squeezed part of a block of lines (the run
  between two long gaps) that has a line over a pause and a sound-filled
  hole after it is marked "the clock here may be off by up to N seconds",
  N the hole's length; the squeezed part is the lines within the
  recogniser's window before the hole's end (v1.152.0), the line over a
  pause among them.

The mark is kept on each marked line (`Segment.clock`), and every place
that plays a moment reads it: the transcript, the samples, the guided
page's line screen, the Preview. While a line is unsure it plays a wider
window, to the end of the hole; the voice step gives it no vector; it is
never a Sample.

Then the re-read (v1.152.0): the window of prepared audio, from a second
before the first marked line to half a second after the hole's end, goes
to the WhisperX service as a small job of its own, outside the Queue, and
when the reading comes back each line whose words it finds takes its
clock from where those words were heard. The old clock and the shift stay
in the mark ("retimed"); a line the reading cannot find keeps its clock
and its pill ("unplaced"). A re-timed line is a sure line again. The pass
lives in the Transcript's provenance under clock_check.reread and is
polled by core.tasks.poll_reread.

The thresholds are the build's constants, from the shape measured on the
office's call; they move only if the ear says so on a local sheet.
"""

from __future__ import annotations

import contextlib
import logging
import math
import re
import subprocess
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

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
# Rule 3 (v1.152.0): the squeezed part of a block is the lines within this
# many seconds before the hole's end, the recogniser's window and a half.
SQUEEZE_SECONDS = 45.0
# The audio's pauses: quieter than this, for the pause's length.
NOISE_DB = -32
# Play reaches this far either side of a line, marked or not.
EDGE = 0.5
# ffmpeg's time on a long recording.
MEASURE_TIMEOUT = 900

# The re-read (ADR 0023): the cut reaches this far before the first marked
# line and after the hole's end; a line is placed when this share of its
# words is found; the pass is polled this often and given up after this.
LEAD = 1.0
TAIL = 0.5
MATCH_SHARE = 0.5
REREAD_POLL_SECONDS = 10
REREAD_GIVE_UP_SECONDS = 1800
REREAD_PRIORITY = 90
CUT_TIMEOUT = 120


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
        # The squeeze (v1.152.0): only the lines inside the recogniser's
        # window before the hole's end, and the line over a pause among them.
        squeezed = [row for row in block if row.start >= gap_end - SQUEEZE_SECONDS]
        if not squeezed or not any(spans_a_pause(row, quiet) for row in squeezed):
            continue
        marked_blocks += 1
        head = squeezed[0].pk
        for row in squeezed:
            marks[row.pk] = {
                "bound": round(length, 1),
                "to": round(gap_end, 2),
                "hole": [round(gap_start, 2), round(gap_end, 2)],
                "block": head,
            }
    return {"marks": marks, "holes": holes, "blocks": marked_blocks}


def unsure(clock) -> bool:
    """Whether a line's mark still means doubt: marked and not re-timed."""
    return bool(clock) and not clock.get("retimed")


def mark(transcript) -> dict:
    """Measure and mark one Transcript; every line's verdict is written,
    the clear ones as None. Returns the counts, or {"measured": False}
    when the prepared audio is not on disk or cannot be measured. When any
    block is marked the re-read is asked for (ADR 0023)."""
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
    if marks:
        _ask_later(transcript)
    return counts


def _ask_later(transcript) -> None:
    """The re-read, once the marks are committed; a failure to ask never
    fails the marking."""
    try:
        from core import tasks
        from core.deferring import after_commit

        pk = str(transcript.pk)
        after_commit(lambda: tasks.reread_clock.defer(transcript_id=pk))
    except Exception:  # noqa: BLE001
        log.exception("the clock re-read could not be asked for")


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
    a line still unsure to the end of the hole beside it."""
    verdict = getattr(segment, "clock", None) or {}
    end = float(verdict.get("to") or segment.end) if unsure(verdict) else segment.end
    return max(0.0, float(segment.start) - EDGE), float(end) + EDGE


def verdict_json(segment) -> dict | None:
    """The line's verdict as the pages read it, or None when the clock is
    sure: the bound, where the sound is, the clock the audio suggests,
    whether this line heads its block, and from v1.152.0 whether it was
    re-timed (with the clock it had) or left unplaced by the re-read."""
    verdict = getattr(segment, "clock", None)
    if not verdict:
        return None
    start = float(segment.start)
    end = float(segment.end)
    if verdict.get("retimed"):
        was = verdict.get("was") or [start, end]
        return {
            "retimed": True,
            "unplaced": False,
            "was": float(was[0]),
            "shift": float(verdict.get("shift") or 0),
            "bound": 0.0,
            "to": end,
            "hole": [],
            "about": start,
            "head": verdict.get("block") == segment.pk,
            "play_from": max(0.0, start - EDGE),
            "play_to": end + EDGE,
        }
    bound = float(verdict.get("bound") or 0)
    return {
        "retimed": False,
        "unplaced": bool(verdict.get("unplaced")),
        "bound": bound,
        "to": float(verdict.get("to") or end),
        "hole": verdict.get("hole") or [],
        "about": round(start + bound, 1),
        "head": verdict.get("block") == segment.pk,
        "play_from": max(0.0, start - EDGE),
        "play_to": float(verdict.get("to") or end) + EDGE,
    }


# The re-read (ADR 0023) -----------------------------------------------------


def windows_of(transcript) -> list[dict]:
    """The marked blocks still unsure, one window each: the head's pk, the
    Side, and the cut's bounds."""
    heads: dict[int, dict] = {}
    # (A missing key is not "not true" to the database, so the re-timed and
    # the unplaced are set aside here, not in the query.)
    for segment in transcript.segments.filter(
        same_as_other_side=False, clock__isnull=False
    ).order_by("start", "id"):
        clock = segment.clock or {}
        head = clock.get("block")
        if head is None or clock.get("retimed") or clock.get("unplaced"):
            continue
        one = heads.setdefault(
            head,
            {
                "head": head,
                "side": segment.side_id,
                "from": max(0.0, float(segment.start) - LEAD),
                "to": float(clock.get("to") or segment.end) + TAIL,
            },
        )
        one["from"] = min(one["from"], max(0.0, float(segment.start) - LEAD))
        one["to"] = max(one["to"], float(clock.get("to") or segment.end) + TAIL)
    return list(heads.values())


def _cut(source: Path, target: Path, start: float, end: float) -> bool:
    """One window of the prepared audio, copied out as it is."""
    try:
        done = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{start:.3f}",
                "-to",
                f"{end:.3f}",
                "-i",
                str(source),
                "-c",
                "copy",
                str(target),
            ],
            capture_output=True,
            text=True,
            timeout=CUT_TIMEOUT,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        log.warning("the clock window could not be cut: %s", error)
        return False
    if done.returncode != 0 or not target.exists():
        log.warning("the clock window could not be cut: %s", done.stderr.strip()[:200])
        return False
    return True


def reread_request(recording, transcript, head: int) -> dict:
    """What the service is asked for one window: the recording's own task,
    model and language, the same vocabulary, no speakers."""
    from core import queue, settings_store

    return {
        "task": "translate_if_needed" if recording.translate else "transcribe",
        "language": transcript.language or recording.spoken_language or "",
        "model": recording.model or settings_store.get("model"),
        "diarize": False,
        "vocabulary": queue._office_vocabulary()
        + queue._case_vocabulary(recording)
        + list(recording.vocabulary or []),
        "context": recording.context or "",
        "return_speaker_embeddings": False,
        "diarizer": settings_store.diarizer(),
        "client_reference": f"clock-{transcript.pk}-{head}-{int(time.time())}",
        "priority": REREAD_PRIORITY,
    }


def _reread_state(transcript) -> dict:
    counts = (transcript.provenance or {}).get("clock_check") or {}
    return dict(counts.get("reread") or {})


def _write_reread(transcript, state: dict) -> None:
    provenance = dict(transcript.provenance or {})
    counts = dict(provenance.get("clock_check") or {})
    counts["reread"] = state
    provenance["clock_check"] = counts
    transcript.provenance = provenance
    transcript.save(update_fields=["provenance"])


def ask(transcript) -> dict:
    """Send every marked block's window to the service and write the pass's
    state. Returns that state: waiting while any job is out, failed when
    none could be sent, done when there was nothing to send."""
    from core import whisperx

    recording = transcript.recording
    blocks = windows_of(transcript)
    if not blocks:
        state = {"state": "done", "jobs": {}, "retimed": 0, "unplaced": 0}
        _write_reread(transcript, state)
        return state
    sides = {side.pk: side for side in recording.sides.all()}
    only_side = next(iter(sides.values())) if len(sides) == 1 else None
    folder = recording.folder / "clock"
    lane = whisperx.lane_for(recording)
    jobs: dict[str, dict] = {}
    for block in blocks:
        side = sides.get(block["side"]) or only_side
        if side is None or not side.asr_path.exists():
            continue
        folder.mkdir(parents=True, exist_ok=True)
        cut = folder / f"{block['head']}.wav"
        if not _cut(side.asr_path, cut, block["from"], block["to"]):
            continue
        try:
            submitted = whisperx.submit(
                cut, reread_request(recording, transcript, block["head"]), lane
            )
        except Exception as problem:  # noqa: BLE001 - one window's failure
            log.warning("the clock window could not be sent: %s", problem)
            continue
        jobs[str(block["head"])] = {
            "id": submitted.id,
            "lane": lane,
            "from": round(block["from"], 3),
            "state": "waiting",
        }
    state = {
        "state": "waiting" if jobs else "failed",
        "jobs": jobs,
        "asked": timezone.now().isoformat(timespec="seconds"),
        "retimed": 0,
        "unplaced": 0,
    }
    _write_reread(transcript, state)
    log.info(
        "clock re-read: %d window(s) sent for recording %s", len(jobs), recording.pk
    )
    return state


def poll(transcript) -> dict:
    """Ask the service about the windows still out, land the readings that
    are done, and write the state. Returns it; "waiting" means ask again."""
    from core import whisperx

    state = _reread_state(transcript)
    jobs = state.get("jobs") or {}
    if state.get("state") != "waiting":
        return state
    asked = state.get("asked") or ""
    for head, job in jobs.items():
        if job.get("state") != "waiting":
            continue
        try:
            told = whisperx.status_of(job["id"], job.get("lane", ""))
        except Exception as problem:  # noqa: BLE001 - the service, this time
            log.warning("the clock re-read could not be asked about: %s", problem)
            continue
        if told is None or told.get("state") in ("failed", "cancelled"):
            job["state"] = "failed"
            continue
        if told.get("state") != "done":
            continue
        try:
            result = whisperx.result(job["id"], job.get("lane", ""))
        except Exception as problem:  # noqa: BLE001
            log.warning("the clock re-read's result could not be read: %s", problem)
            job["state"] = "failed"
            continue
        try:
            counts = retime(transcript, int(head), result, float(job.get("from") or 0))
        except Exception:  # noqa: BLE001 - one window's reading
            log.exception("the clock re-read of block %s could not be applied", head)
            job["state"] = "failed"
            continue
        job["state"] = "done"
        state["retimed"] = int(state.get("retimed") or 0) + counts["retimed"]
        state["unplaced"] = int(state.get("unplaced") or 0) + counts["unplaced"]
        with contextlib.suppress(Exception):
            whisperx.delete(job["id"], job.get("lane", ""))
        _remove_cut(transcript.recording, head)
    waiting = [one for one in jobs.values() if one.get("state") == "waiting"]
    if waiting:
        started = None
        with contextlib.suppress(ValueError):
            started = timezone.datetime.fromisoformat(asked)
        if started is not None and (
            (timezone.now() - started).total_seconds() > REREAD_GIVE_UP_SECONDS
        ):
            for one in waiting:
                one["state"] = "failed"
                with contextlib.suppress(Exception):
                    whisperx.delete(one["id"], one.get("lane", ""))
            waiting = []
    if waiting:
        state["state"] = "waiting"
        _write_reread(transcript, state)
        return state
    state["state"] = (
        "done" if any(one.get("state") == "done" for one in jobs.values()) else "failed"
    )
    state["finished"] = timezone.now().isoformat(timespec="seconds")
    _write_reread(transcript, state)
    for head in jobs:
        _remove_cut(transcript.recording, head)
    _note(transcript, state)
    return state


def _remove_cut(recording, head) -> None:
    try:
        cut = recording.folder / "clock" / f"{head}.wav"
        if cut.exists():
            cut.unlink()
        folder = recording.folder / "clock"
        if folder.exists() and not any(folder.iterdir()):
            folder.rmdir()
    except OSError:
        pass


def _note(transcript, state: dict) -> None:
    """One audit row per re-read: the lines moved and the lines left; no
    word, no time, no name."""
    from core import audit

    recording = transcript.recording
    audit.write(
        audit.Category.JOBS,
        "Clock re-read",
        system="worker",
        outcome=audit.Outcome.SUCCESS
        if state.get("state") == "done"
        else audit.Outcome.FAILURE,
        affected_user=recording.user,
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
        lines_changed=int(state.get("retimed") or 0),
        lines_left=int(state.get("unplaced") or 0),
        windows=len(state.get("jobs") or {}),
    )
    log.info(
        "clock re-read for %s: %d line(s) re-timed, %d left",
        recording.pk,
        int(state.get("retimed") or 0),
        int(state.get("unplaced") or 0),
    )


# The matching -----------------------------------------------------------------

_WORD = re.compile(r"[\W_]+", re.UNICODE)


def tokens(text: str) -> list[str]:
    """A line's words for matching: lower case, punctuation set aside."""
    pieces = (_WORD.sub("", piece.lower()) for piece in (text or "").split())
    return [one for one in pieces if one]


def heard_words(result: dict, offset: float) -> list[tuple[str, float, float]]:
    """The reading's words with their times, offset into the recording's
    clock: the aligner's own times where every word has them, else each
    segment's span shared evenly among its words."""
    out: list[tuple[str, float, float]] = []
    for segment in result.get("segments") or []:
        words = [one for one in (segment.get("words") or []) if isinstance(one, dict)]
        timed = [
            one
            for one in words
            if one.get("start") is not None and one.get("end") is not None
        ]
        if words and len(timed) == len(words):
            for one in words:
                for token in tokens(str(one.get("word", ""))):
                    out.append(
                        (
                            token,
                            offset + float(one["start"]),
                            offset + float(one["end"]),
                        )
                    )
            continue
        found = tokens(str(segment.get("text", "")))
        if not found:
            continue
        start = float(segment.get("start") or 0.0)
        end = float(segment.get("end") or start)
        span = max(0.0, end - start)
        for i, token in enumerate(found):
            out.append(
                (
                    token,
                    offset + start + span * i / len(found),
                    offset + start + span * (i + 1) / len(found),
                )
            )
    return out


Placed = dict[int, tuple[float, float] | None]


def place(lines: list[Row], texts: dict[int, str], heard: list) -> Placed:
    """Each line's new clock from where its words were heard, or None when
    under MATCH_SHARE of them were found. Pure, for the tests. The order
    of the lines is kept: no line starts before the one above it ends."""
    old: list[str] = []
    owner: list[int] = []
    for row in lines:
        for token in tokens(texts.get(row.pk, "")):
            old.append(token)
            owner.append(row.pk)
    new = [one[0] for one in heard]
    matched: dict[int, list[int]] = {}
    if old and new:
        matcher = SequenceMatcher(None, old, new, autojunk=False)
        for block in matcher.get_matching_blocks():
            for k in range(block.size):
                matched.setdefault(owner[block.a + k], []).append(block.b + k)
    placed: Placed = {}
    counts = {}
    for pk in owner:
        counts[pk] = counts.get(pk, 0) + 1
    floor = 0.0
    for row in lines:
        found = matched.get(row.pk) or []
        need = max(1, math.ceil(counts.get(row.pk, 0) * MATCH_SHARE))
        if len(found) < need:
            placed[row.pk] = None
            continue
        start = min(heard[i][1] for i in found)
        end = max(heard[i][2] for i in found)
        if start < floor:
            start = floor
        if end <= start:
            end = start + max(0.3, row.end - row.start)
        placed[row.pk] = (round(start, 2), round(end, 2))
        floor = end
    return placed


def retime(transcript, head: int, result: dict, offset: float) -> dict:
    """Land one window's reading on its block: every line whose words were
    found takes its clock from them, the old clock and the shift kept in
    the mark; the rest are marked unplaced. Returns the counts."""
    from core.jobs import Segment

    # Every line of the block takes part in the matching, so the words of a
    # line already re-timed are claimed by it; only the lines not yet
    # re-timed are written.
    block = list(transcript.segments.filter(clock__block=head).order_by("start", "id"))
    segments = [one for one in block if not (one.clock or {}).get("retimed")]
    if not segments:
        return {"retimed": 0, "unplaced": 0}
    rows = [Row(one.pk, float(one.start), float(one.end)) for one in block]
    texts = {one.pk: one.text for one in block}
    placed = place(rows, texts, heard_words(result, offset))
    retimed = unplaced = 0
    for segment in segments:
        got = placed.get(segment.pk)
        clock = dict(segment.clock or {})
        if got is None:
            clock["unplaced"] = True
            segment.clock = clock
            unplaced += 1
            continue
        was_start, was_end = float(segment.start), float(segment.end)
        start, end = got
        shift = start - was_start
        words = []
        for word in segment.words or []:
            if (
                isinstance(word, dict)
                and word.get("start") is not None
                and word.get("end") is not None
            ):
                word = dict(word)
                word["start"] = round(
                    min(max(float(word["start"]) + shift, start), end), 3
                )
                word["end"] = round(min(max(float(word["end"]) + shift, start), end), 3)
            words.append(word)
        segment.start = start
        segment.end = end
        segment.words = words
        clock.pop("unplaced", None)
        clock.update(
            {"was": [was_start, was_end], "shift": round(shift, 1), "retimed": True}
        )
        segment.clock = clock
        retimed += 1
    Segment.objects.bulk_update(
        segments, ["start", "end", "words", "clock"], batch_size=200
    )
    return {"retimed": retimed, "unplaced": unplaced}
