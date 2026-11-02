"""The street map behind the paths (Phase 12 chapter 1): one file the office
holds, served from its own server.

The Admin cuts a region of the free OpenStreetMap-based builds into one
`.pmtiles` file on a workstation that has the internet, and `./transcribe
basemap <file>` puts it at `<data>/maps/basemap.pmtiles`. Caddy serves that
one file to a signed-in browser with byte ranges, and the browser draws the
streets from it. Nothing on the Map tab reaches outside the office; without
the file the tab draws its paths on plain ground.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from django.conf import settings
from django.utils import timezone

BASEMAP_NAME = "basemap.pmtiles"
URL = "/maps/" + BASEMAP_NAME
ATTRIBUTION = "© OpenStreetMap contributors · Protomaps"
MAGIC = b"PMTiles"


def maps_dir() -> Path:
    return Path(settings.DATA_DIR) / "maps"


def basemap_file() -> Path:
    return maps_dir() / BASEMAP_NAME


def basemap_present() -> bool:
    try:
        return basemap_file().is_file() and basemap_file().stat().st_size > 0
    except OSError:
        return False


def basemap_json() -> dict:
    """What the Map tab is told: whether the street map is there, and where."""
    present = basemap_present()
    return {
        "present": present,
        "url": URL if present else "",
        "attribution": ATTRIBUTION,
    }


def basemap_state() -> dict:
    """The Status page's line: present with its size and date, or none."""
    try:
        stat = basemap_file().stat()
    except OSError:
        return {"present": False, "words": "none; see the admin guide, Maps"}
    placed = timezone.localtime(dt.datetime.fromtimestamp(stat.st_mtime, tz=dt.UTC))
    size = stat.st_size / (1024 * 1024)
    size_words = f"{size / 1024:.1f} GB" if size >= 1024 else f"{size:.0f} MB"
    return {
        "present": True,
        "size_bytes": stat.st_size,
        "words": f"installed, {size_words}, placed {placed:%d %b %Y}",
    }
