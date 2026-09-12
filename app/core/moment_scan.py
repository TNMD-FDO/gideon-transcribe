"""The scan of a video's picture and sound for moments worth a look (Phase 4).

No engine here: ffmpeg reads the Playback copy once for sharp changes of
picture and once for seconds far louder than the recording's usual level,
and each becomes a Cue a person may accept. Runs on the media worker, where
the CPU is, and never on a Workspace's clock: it is not a Job.
"""

from __future__ import annotations

import logging
import re
import statistics
import time
from pathlib import Path

from django.utils import timezone

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


def scan_for_moments(run_id) -> None:
    """One scan of the picture and the sound, replacing every pending scanned Cue."""
    from core import assistant
    from core.assistant import Cue, CueRun

    run = (
        CueRun.objects.filter(pk=run_id)
        .select_related("transcript", "transcript__recording")
        .first()
    )
    if run is None:
        return
    transcript = run.transcript
    recording = transcript.recording
    started = time.monotonic()
    run.state = assistant.RUNNING
    run.save(update_fields=["state"])
    scenes: list[float] = []
    loud: list[float] = []
    try:
        if not assistant.playable_video(recording):
            raise media.MediaError("no playback copy with a picture", "media_not_ready")
        source = recording.playback_path()
        gap = settings_store.moment_media_gap_seconds()
        threshold = settings_store.moment_scene_threshold()
        scenes = thin(scene_changes(source, threshold), gap)
        loud = thin(loud_seconds(source, settings_store.moment_loud_db()), gap)
        most = settings_store.moment_finder_most()
        found = [(at, Cue.PICTURE) for at in scenes] + [(at, Cue.SOUND) for at in loud]
        found.sort()
        # The two kinds a gap apart from each other as well, and no more than
        # the most allowed, spread over the recording rather than its start.
        chosen: list[tuple[float, str]] = []
        for at, source_kind in found:
            if not chosen or at - chosen[-1][0] >= gap:
                chosen.append((at, source_kind))
        if len(chosen) > most:
            step = len(chosen) / most
            chosen = [chosen[int(n * step)] for n in range(most)]
        segments = list(
            transcript.segments.filter(same_as_other_side=False).order_by("start", "id")
        )

        def row_for(at: float):
            last = None
            for segment in segments:
                if segment.start <= at:
                    last = segment
                else:
                    break
            return last

        transcript.cues.filter(
            source__in=(Cue.PICTURE, Cue.SOUND), state=Cue.PENDING
        ).delete()
        for at, source_kind in chosen:
            row = row_for(at)
            Cue.objects.create(
                transcript=transcript,
                segment=row,
                at=at,
                line=0,
                kind="change",
                reason=(
                    "The picture changes sharply here"
                    if source_kind == Cue.PICTURE
                    else "Raised voices or a bang here"
                ),
                confidence="medium",
                source=source_kind,
            )
        run.found = len(chosen)
        run.state = assistant.DONE
        run.reason_class = ""
        run.finished_at = timezone.now()
        run.save()
        outcome = audit.Outcome.SUCCESS
        reason = ""
    except media.MediaError as why:
        log.warning("the moment scan failed: %s", why.reason_class)
        run.state = assistant.FAILED
        run.reason_class = why.reason_class
        run.finished_at = timezone.now()
        run.save(update_fields=["state", "reason_class", "finished_at"])
        outcome = audit.Outcome.FAILURE
        reason = why.reason_class
    audit.write(
        audit.Category.RECORDINGS,
        "Picture and sound scanned",
        actor=run.asked_by,
        outcome=outcome,
        reason_class=reason,
        affected_user=(
            recording.user
            if run.asked_by is not None and recording.user_id != run.asked_by.pk
            else None
        ),
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
        picture_changes=len(scenes),
        loud_seconds=len(loud),
        found=run.found,
        duration_seconds=round(time.monotonic() - started, 1),
    )
