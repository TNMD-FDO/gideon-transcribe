"""Save a timelapse (Phase 12 chapter 6.12, v1.241.0): a GIF of the Map over
a span of the clock, kept as a Document of the case.

The browser draws the frames, since only it has the map as the person
framed it: the ticked cameras' markers, trails and names at each moment,
with a band under them for the clock. It sends them here a few at a time;
ffmpeg, the same one that cuts clips, joins them into one GIF with a
palette of its own, and the GIF is kept as Save a picture's PNG is.

Three steps, one address: begin (a working folder inside the case's own
folder, and a token for it), frames (a batch of JPEGs, each numbered), and
finish (the GIF made and kept, the folder gone). Stop removes the folder.
A folder left behind by a page that was closed is swept when the next
timelapse begins. Nothing here reaches the Queue or the engine.
"""

from __future__ import annotations

import io
import json
import logging
import re
import shutil
import time
import uuid
from pathlib import Path

from core import documents

log = logging.getLogger(__name__)

# Eight frames a second, and the three lengths a person may choose: 480
# frames at most, which a GIF of the map carries in a few megabytes.
FPS = 8
RUNS = (15, 30, 60)
FRAMES_MOST = FPS * max(RUNS)
FRAMES_LEAST = 2
# The widths offered; a frame of another size is refused.
WIDTHS = (960, 640)
HEIGHT_MOST = 1400
# One frame as the browser sends it (a JPEG), and how many a request carries.
FRAME_MOST = 2 * 1024 * 1024
BATCH = 20
# The last frame is held this long before the GIF starts again.
HOLD_SECONDS = 2
# ffmpeg's time for the join; the web tier's own limit is 120 seconds.
ENCODE_TIMEOUT = 90
# A working folder older than this was left by a page that was closed.
STALE_SECONDS = 2 * 3600
WORK = "timelapse-work"
_TOKEN = re.compile(r"[0-9a-f]{32}")
_JPEG = b"\xff\xd8\xff"

Refused = documents.Refused


def _work(case) -> Path:
    return case.folder / WORK


def sweep(case) -> int:
    """Working folders a closed page left behind, removed; how many."""
    gone = 0
    root = _work(case)
    if not root.is_dir():
        return 0
    now = time.time()
    for one in root.iterdir():
        try:
            if one.is_dir() and now - one.stat().st_mtime > STALE_SECONDS:
                shutil.rmtree(one, ignore_errors=True)
                gone += 1
        except OSError:
            continue
    return gone


def _folder(case, token: str, by) -> tuple[Path, dict]:
    """The working folder a token names and what was said when it began;
    refused when the token is not one, is gone, or is somebody else's."""
    if not _TOKEN.fullmatch(str(token or "")):
        raise Refused("That timelapse was not begun here.")
    folder = _work(case) / token
    try:
        meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise Refused(
            "That timelapse is no longer being made. Start it again."
        ) from None
    if meta.get("user") != by.pk:
        raise Refused("That timelapse is somebody else's.")
    return folder, meta


def begin(
    case, *, by, frames: int, width: int, height: int, cameras: int, span: float
) -> str:
    """A working folder for one timelapse, and its token. Everything that
    would refuse the finished GIF is refused here, before a frame is drawn."""
    from core import settings_store, uploads

    if not documents.on():
        raise Refused("Documents are off, so the timelapse has nowhere to go.")
    documents._room_or_refused(case)
    if not FRAMES_LEAST <= frames <= FRAMES_MOST:
        raise Refused(
            f"A timelapse runs {min(RUNS)} to {max(RUNS)} seconds, "
            f"{FRAMES_MOST} frames at most."
        )
    if width not in WIDTHS or not 16 <= height <= HEIGHT_MOST:
        raise Refused("That is not a size a timelapse is made in.")
    if cameras < 1:
        raise Refused("Tick at least one camera in the list first.")
    if uploads.free_disk_bytes() < settings_store.minimum_free_disk_bytes():
        raise Refused("The server's disk is full. Tell IT.")
    sweep(case)
    token = uuid.uuid4().hex
    folder = _work(case) / token
    try:
        folder.mkdir(parents=True, exist_ok=False)
        (folder / "meta.json").write_text(
            json.dumps(
                {
                    "user": by.pk,
                    "frames": int(frames),
                    "width": int(width),
                    "height": int(height),
                    "cameras": int(cameras),
                    "span": round(float(span), 1),
                }
            ),
            encoding="utf-8",
        )
    except OSError:
        log.exception("a timelapse's working folder could not be made")
        raise Refused("The timelapse could not be started on the server.") from None
    return token


def add_frames(case, token: str, *, by, frames: list[tuple[int, bytes]]) -> int:
    """A batch of frames kept by their numbers; how many the folder holds."""
    folder, meta = _folder(case, token, by)
    if len(frames) > BATCH:
        raise Refused("Too many frames arrived at once.")
    for index, data in frames:
        if not 0 <= index < meta["frames"]:
            raise Refused("A frame arrived that this timelapse has no place for.")
        if not data.startswith(_JPEG) or len(data) > FRAME_MOST:
            raise Refused("A frame arrived that is not a picture of the map.")
        try:
            (folder / f"f-{index:05d}.jpg").write_bytes(data)
        except OSError:
            log.exception("a timelapse frame could not be kept")
            raise Refused("A frame could not be kept on the server.") from None
    return len(list(folder.glob("f-*.jpg")))


def stop(case, token: str, *, by) -> None:
    """The person stopped it: the frames go, nothing is kept."""
    try:
        folder, _meta = _folder(case, token, by)
    except Refused:
        return
    shutil.rmtree(folder, ignore_errors=True)


def encode_arguments(folder: Path, target: Path) -> list[str]:
    """ffmpeg's arguments for the join: the frames in order at FPS, the last
    one held, one palette for the whole GIF from what changes between
    frames, an ordered dither (it stays put from frame to frame, so only
    what moved is written), looping for ever."""
    return [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-framerate",
        str(FPS),
        "-start_number",
        "0",
        "-i",
        str(folder / "f-%05d.jpg"),
        "-filter_complex",
        f"[0:v]tpad=stop_mode=clone:stop_duration={HOLD_SECONDS},split[a][b];"
        "[a]palettegen=stats_mode=diff[p];"
        "[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle",
        "-loop",
        "0",
        str(target),
    ]


def _encode(folder: Path, target: Path) -> None:
    """Kept apart so a test can stand in for ffmpeg."""
    from core import media

    try:
        finished = media._run(encode_arguments(folder, target), ENCODE_TIMEOUT)
    except media.MediaError as problem:
        if problem.reason_class == "server_disk_full":
            raise Refused("The server's disk is full. Tell IT.") from None
        raise Refused(
            "The timelapse took too long to join. Try a shorter one."
        ) from None
    if finished.returncode != 0 or not target.exists():
        raise Refused("The frames could not be joined into a GIF.")


def finish(case, token: str, *, by, about: dict, title: str, request=None):
    """The frames joined and the GIF kept as a Document; the folder goes
    whether or not it worked, so a failure leaves nothing behind."""
    folder, meta = _folder(case, token, by)
    try:
        have = sorted(folder.glob("f-*.jpg"))
        if len(have) != meta["frames"]:
            raise Refused(
                f"Only {len(have)} of {meta['frames']} frames arrived. "
                "Make the timelapse again."
            )
        target = folder / "out.gif"
        _encode(folder, target)
        data = target.read_bytes()
        try:
            from PIL import Image

            with Image.open(have[0]) as first:
                width_px, height_px = first.size
                kept = io.BytesIO()
                first.convert("RGB").save(kept, format="PNG")
        except Exception:  # noqa: BLE001 - any failure reads as an unusable frame
            raise Refused("The first frame could not be opened.") from None
        return documents.add_timelapse(
            case,
            about=about,
            data=data,
            still=kept.getvalue(),
            size=(width_px, height_px),
            title=title,
            by=by,
            request=request,
            frames=meta["frames"],
            cameras=meta["cameras"],
            span=meta["span"],
        )
    finally:
        shutil.rmtree(folder, ignore_errors=True)
