"""The scan of a video's picture and sound: where it changes (Phase 4).

No engine here: ffmpeg reads the Playback copy once for sharp changes of
picture and once for seconds far louder than the recording's usual level.
The seconds found are the change points the picture record is cut by
(chapter 6), kept on the Transcript and made once per Transcript. Until
v1.51.0 each became a Cue a person could accept.
"""

from __future__ import annotations

import logging
import re
import statistics
import time
from pathlib import Path

from core import audit, media, settings_store

log = logging.getLogger("transcribe.moment_scan")

# A long recording decodes at a few hundred frames a second at this size.
SCAN_TIMEOUT = 30 * 60
PTS = re.compile(r"pts_time:\s*([0-9]+(?:\.[0-9]+)?)")
LEVEL = re.compile(r"lavfi\.astats\.Overall\.RMS_level=(-?[0-9]+(?:\.[0-9]+)?|-inf)")


def _ffmpeg_output(arguments: list[str], timeout: int) -> tuple[str, str]:
    """Both streams of one ffmpeg run; a scan reads what ffmpeg prints."""
    finished = media._run(arguments, timeout=timeout)
    if finished.returncode != 0:
        raise media.MediaError("The scan could not read the recording", "media_failed")
    return finished.stdout or "", finished.stderr or ""


def scene_changes(
    source: Path, threshold: float, timeout: int = SCAN_TIMEOUT
) -> list[float]:
    """The seconds at which the picture changes by more than the threshold (0 to 1)."""
    arguments = [
        "ffmpeg",
        "-nostdin",
        "-v",
        "info",
        "-i",
        str(source),
        "-an",
        "-vf",
        f"scale=320:-2,select='gt(scene,{threshold:.2f})',showinfo",
        "-f",
        "null",
        "-",
    ]
    out, err = _ffmpeg_output(arguments, timeout)
    return sorted({round(float(one), 2) for one in PTS.findall(out + err)})


def loud_seconds(
    source: Path, rise_db: float, timeout: int = SCAN_TIMEOUT
) -> list[float]:
    """The seconds whose level is `rise_db` above the recording's median level."""
    arguments = [
        "ffmpeg",
        "-nostdin",
        "-v",
        "error",
        "-i",
        str(source),
        "-vn",
        "-af",
        "aresample=16000,asetnsamples=n=16000,astats=metadata=1:reset=1,"
        "ametadata=mode=print:key=lavfi.astats.Overall.RMS_level:file=-",
        "-f",
        "null",
        "-",
    ]
    out, err = _ffmpeg_output(arguments, timeout)
    return loud_from(out + "\n" + err, rise_db)


def loud_from(printed: str, rise_db: float) -> list[float]:
    """The loud seconds in ffmpeg's printed levels: a second's time, then its level."""
    levels: list[tuple[float, float]] = []
    at = None
    for line in printed.splitlines():
        time_match = PTS.search(line)
        if time_match:
            at = float(time_match.group(1))
            continue
        level_match = LEVEL.search(line)
        if level_match and at is not None:
            value = level_match.group(1)
            if value != "-inf":
                levels.append((at, float(value)))
            at = None
    if len(levels) < 5:
        return []
    usual = statistics.median(level for _, level in levels)
    return [round(at, 2) for at, level in levels if level >= usual + rise_db]


def thin(times: list[float], gap: float) -> list[float]:
    """One time per cluster: the first of each run closer together than the gap."""
    kept: list[float] = []
    for at in sorted(times):
        if not kept or at - kept[-1] >= gap:
            kept.append(at)
    return kept


def change_points_of(transcript, actor=None) -> list[float]:
    """The seconds where the picture or the sound changes sharply, kept on the
    Transcript for the record's cut, thinned to the gap. Raises MediaError."""
    from core import assistant

    recording = transcript.recording
    started = time.monotonic()
    scenes: list[float] = []
    loud: list[float] = []
    points: list[float] = []
    trouble = None
    try:
        if not assistant.playable_video(recording):
            raise media.MediaError("no playback copy with a picture", "media_not_ready")
        source = recording.playback_path()
        gap = settings_store.moment_media_gap_seconds()
        scenes = thin(
            scene_changes(source, settings_store.moment_scene_threshold()), gap
        )
        loud = thin(loud_seconds(source, settings_store.moment_loud_db()), gap)
        points = thin(sorted(set(scenes + loud)), gap)
        transcript.change_points = points
        transcript.save(update_fields=["change_points"])
        outcome = audit.Outcome.SUCCESS
        reason = ""
    except media.MediaError as why:
        log.warning("the scan of the picture and sound failed: %s", why.reason_class)
        trouble = why
        outcome = audit.Outcome.FAILURE
        reason = why.reason_class
    audit.write(
        audit.Category.RECORDINGS,
        "Picture and sound scanned",
        actor=actor,
        outcome=outcome,
        reason_class=reason,
        affected_user=(
            recording.user
            if actor is not None and recording.user_id != actor.pk
            else None
        ),
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
        picture_changes=len(scenes),
        loud_seconds=len(loud),
        found=len(points),
        duration_seconds=round(time.monotonic() - started, 1),
    )
    if trouble is not None:
        raise trouble
    return points
