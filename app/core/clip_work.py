"""Making a Clip's file, and everything a Clip is downloaded as.

The render runs on the media worker beside Playback copies, within that
worker's own concurrency, never in the serial Queue: ten Clips saved at once
wait their turn showing Rendering, and none of them keeps a Workspace alive.
"""

from __future__ import annotations

import io
import logging
import tempfile
import zipfile
from pathlib import Path

from django.utils import timezone

from core import audit, exports, media
from core.clips import Clip, RenderState, transcript_mark

log = logging.getLogger("transcribe.clips")

# A render fails after the Clip's own length plus five minutes. A one-minute
# clip that has not finished in six is not going to.
EXTRA_SECONDS = 5 * 60


def render(clip: Clip) -> Clip:
    """Cut the file, and say plainly if it could not be cut.

    Burned captions are written to a temporary file and given to ffmpeg; they
    are never stored beside the rendered file, because everything else about a
    Clip is built when it is downloaded.
    """
    source = clip.recording.playback_path()
    if source is None or not source.exists():
        return _failed(clip, "clip_render_failed", "there is no playback copy yet")

    clip.state = RenderState.RENDERING
    clip.save(update_fields=["state"])

    captions = None
    written = None
    try:
        if clip.burn_captions and clip.is_video:
            # ffmpeg reads it by name, so it is written and closed first and
            # taken away in the finally below however this ends.
            handle, name = tempfile.mkstemp(suffix=".srt")
            written = Path(name)
            with open(handle, "w", encoding="utf-8") as into:
                into.write(srt_for(clip))
            captions = written

        media.cut_clip(
            source,
            clip.path,
            clip.start,
            clip.end,
            captions=captions,
            timeout=int(clip.seconds) + EXTRA_SECONDS,
        )
    except media.MediaError as problem:
        return _failed(clip, problem.reason_class, problem.message)
    except Exception:  # noqa: BLE001 - a render failing must not stop the worker
        log.exception("the render of clip %s failed", clip.id)
        return _failed(clip, "clip_render_failed", "the render failed")
    finally:
        if written is not None:
            written.unlink(missing_ok=True)

    clip.state = RenderState.READY
    clip.failure_class = ""
    clip.rendered = timezone.now()
    clip.size_bytes = clip.path.stat().st_size
    clip.captions_of = transcript_mark(clip.recording) if clip.burn_captions else ""
    # The copy somebody already holds is now the wrong one.
    clip.first_downloaded = None
    clip.downloads = 0
    clip.save()

    log.info(
        "clip %s rendered: %.1f s, %d bytes", clip.id, clip.seconds, clip.size_bytes
    )
    return clip


def _failed(clip: Clip, reason: str, why: str) -> Clip:
    log.warning("clip %s failed: %s", clip.id, why)
    clip.state = RenderState.FAILED
    clip.failure_class = reason
    clip.save(update_fields=["state", "failure_class"])
    audit.write(
        audit.Category.CLIPS,
        "Clip render failed",
        system="media worker",
        affected_user=clip.recording.user,
        object_type="clip",
        object_id=clip.pk,
        object_label=f"{clip.start:.1f}-{clip.end:.1f}",
        outcome=audit.Outcome.FAILURE,
        reason_class=reason,
    )
    return clip


# What comes down with a Clip ---------------------------------------------------


def srt_for(clip: Clip) -> str:
    """The cues inside the span, shifted so the file starts at zero."""
    cues = []
    for number, segment in enumerate(clip.segments(), start=1):
        text = f"{segment.speaker}: {segment.text}" if segment.speaker else segment.text
        cues.append(
            f"{number}\r\n"
            f"{exports.srt_time(segment.start - clip.start)} --> "
            f"{exports.srt_time(min(segment.end, clip.end) - clip.start)}\r\n"
            f"{text}\r\n"
        )
    return "\r\n".join(cues)


def excerpt_for(clip: Clip) -> str:
    """The plain-text export's shape, cut to the span, with its own notice.

    The excerpt keeps the Recording's own times rather than starting at zero,
    so that a line found here can be found in the full Transcript.
    """
    recording = clip.recording
    transcript = getattr(recording, "transcript", None)
    if transcript is None:
        return ""

    segments = clip.segments()
    who = exports.appearances(segments)

    head = [
        exports.title_of(recording),
        (
            f"{exports.kind_line(transcript)}. {recording.original_filename}, "
            f"{exports.clock(clip.start)} to {exports.clock(clip.end)}, uploaded "
            f"{recording.created:{exports.DAY}} by {recording.user.username}. "
            f"Processed {transcript.created:{exports.DAY}} with Whisper "
            f"{exports.model_of(transcript)}."
        ),
    ]
    if who:
        head.append(
            "Speakers: "
            + "; ".join(
                f"{one.name} ({one.label})" if one.label else one.name for one in who
            )
        )

    notice = exports.notice_for(transcript)
    if any(segment.corrected for segment in segments):
        notice += " " + exports.CORRECTED_LEGEND_TEXT
    head.append(notice)
    head.append("")

    lines = []
    for segment in segments:
        name = segment.speaker
        if name and segment.corrected:
            name = f"{name} (corrected)"
        elif not name and segment.corrected:
            name = "corrected"
        at = f"[{exports.clock(segment.start)}]"
        lines.append(f"{at} {name}: {segment.text}" if name else f"{at} {segment.text}")

    return "\r\n".join(head + lines) + "\r\n"


def file_name(clip: Clip, ending: str = "") -> str:
    """The Recording's title, the Clip's title, and the span, made safe."""
    stem = (
        f"{exports.safe_name(exports.title_of(clip.recording))} - "
        f"{exports.safe_name(clip.title)} "
        f"{_stamp(clip.start)}-{_stamp(clip.end)}"
    )
    return f"{stem}{ending}"


def _stamp(seconds: float) -> str:
    """A time a file name can carry: no colons."""
    return exports.clock(seconds).replace(":", ".")


def one_clip(clip: Clip) -> tuple[bytes, str, str]:
    """What comes down when somebody downloads one Clip.

    With the excerpt on, a zip of the media file, the text, and the captions.
    With it off, the bare media file.
    """
    body = clip.path.read_bytes()
    if not clip.include_excerpt or not hasattr(clip.recording, "transcript"):
        return (
            body,
            file_name(clip, clip.suffix),
            "video/mp4" if clip.suffix == ".mp4" else "audio/mpeg",
        )

    holder = io.BytesIO()
    with zipfile.ZipFile(holder, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr(file_name(clip, clip.suffix), body)
        bundle.writestr(file_name(clip, ".txt"), excerpt_for(clip).encode("utf-8"))
        bundle.writestr(file_name(clip, ".srt"), srt_for(clip).encode("utf-8"))
    return holder.getvalue(), file_name(clip, ".zip"), "application/zip"


def add_to_zip(bundle: zipfile.ZipFile, clip: Clip, taken: set[str]) -> None:
    """One Ready Clip inside a bigger zip, flat, with its two files beside it."""
    if clip.state != RenderState.READY or not clip.path.exists():
        return
    bundle.writestr(
        exports.without_clashes(taken, file_name(clip, clip.suffix)),
        clip.path.read_bytes(),
    )
    if clip.include_excerpt and hasattr(clip.recording, "transcript"):
        bundle.writestr(
            exports.without_clashes(taken, file_name(clip, ".txt")),
            excerpt_for(clip).encode("utf-8"),
        )
        bundle.writestr(
            exports.without_clashes(taken, file_name(clip, ".srt")),
            srt_for(clip).encode("utf-8"),
        )


def mark_downloaded(clip: Clip, by_the_owner: bool) -> None:
    """The downloaded mark, which only the owner's own download sets.

    An Admin's download is audited and never sets it: the mark is there to
    tell the owner whether they have the file, and an Admin taking a copy
    does not mean they do.
    """
    if not by_the_owner:
        return
    clip.downloads += 1
    if clip.first_downloaded is None:
        clip.first_downloaded = timezone.now()
    clip.save(update_fields=["downloads", "first_downloaded"])
