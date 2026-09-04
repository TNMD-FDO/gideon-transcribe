"""The daily tidy, at half past three.

Three things that should never be on the disk and occasionally are: upload
pieces nobody finished, a folder under `scratch/` whose Recording row is gone,
and a Recording left marked Discarding because something stopped half way
through a Discard. None of them is an emergency, which is why this runs once a
night rather than every minute, and all three are counted in one audit row so
that a growing number is visible.
"""

from __future__ import annotations

import logging
import shutil
import uuid
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from core import audit
from core.recordings import Recording

log = logging.getLogger("transcribe.sweeping")

# An upload piece is nobody's after a day. The ten-minute rule drops the
# Recording that was waiting on it; this is for the bytes themselves, which
# tusd can leave behind if it stops at the wrong moment.
PIECES_KEPT = timedelta(hours=24)

# A Recording still marked Discarding an hour later was interrupted.
DISCARDING_TOO_LONG = timedelta(hours=1)


def sweep() -> dict:
    """Run all three, count what went, and write the row."""
    counts = {
        "upload_pieces": old_upload_pieces(),
        "orphan_folders": folders_without_a_recording(),
        "unfinished_discards": unfinished_discards(),
    }
    audit.write(
        audit.Category.SYSTEM,
        "daily sweeper ran",
        system="sweeper",
        **counts,
    )
    log.info("the daily sweeper ran: %s", counts)
    return counts


def old_upload_pieces() -> int:
    """Upload pieces older than a day, which belong to nothing."""
    folder = Path(settings.UPLOADS_DIR)
    if not folder.is_dir():
        return 0

    too_old = (timezone.now() - PIECES_KEPT).timestamp()
    gone = 0
    for path in folder.iterdir():
        try:
            if path.stat().st_mtime < too_old:
                path.unlink()
                gone += 1
        except OSError:
            log.warning("could not remove the upload piece %s", path.name)
    return gone


def folders_without_a_recording() -> int:
    """A folder under scratch/ or cases/ whose Recording row has gone.

    Ids only, never names, so nothing about what is inside is read to decide
    this: a folder is kept if a Recording with that id exists and removed if
    one does not. cases/ is treated exactly as scratch/ is, and the toggle
    makes no difference: this runs whether Folder management is on or off,
    because it removes only what no row claims.
    """
    gone = 0
    for above in (Path(settings.SCRATCH_DIR), Path(settings.DATA_DIR) / "cases"):
        if above.is_dir():
            gone += _under(above)
    return gone


def _under(above: Path) -> int:
    """One level of holders, each holding Recording folders by id.

    Under scratch/ a holder is a person; under cases/ it is a Case. Both are
    named by an id, and both go once the last Recording folder in them has.
    """
    gone = 0
    for holder in above.iterdir():
        if not holder.is_dir():
            continue
        for folder in holder.iterdir():
            if not folder.is_dir():
                continue
            if not _is_a_recording_id(folder.name):
                continue
            if not Recording.objects.filter(pk=folder.name).exists():
                shutil.rmtree(folder, ignore_errors=True)
                gone += 1
        if not any(holder.iterdir()):
            shutil.rmtree(holder, ignore_errors=True)
    return gone


def _is_a_recording_id(name: str) -> bool:
    """A folder the app made, rather than something a person left there.

    Every Recording folder is named by a uuid. Anything else is left where it
    is: the sweeper removes what the app is responsible for, not what it
    cannot account for.
    """
    try:
        uuid.UUID(name)
    except ValueError:
        return False
    return True


def unfinished_discards() -> int:
    """Recordings marked Discarding for more than an hour, finished off."""
    from core import lifecycle

    stuck = Recording.objects.filter(
        discarding_since__lt=timezone.now() - DISCARDING_TOO_LONG
    )
    gone = 0
    for recording in list(stuck):
        lifecycle.remove_recording(recording, cause="discard")
        gone += 1
    return gone
