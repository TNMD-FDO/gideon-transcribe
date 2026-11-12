"""The street map behind the paths (Phase 12 chapter 1): one file the office
holds, served from its own server.

`./transcribe basemap fetch` (v1.232.0) cuts the whole United States with
its territories, or the states and territories an Admin names, out of the
free OpenStreetMap-based builds into one `.pmtiles` file at
`<data>/maps/basemap.pmtiles`; or the Admin cuts a file on a workstation and
`./transcribe basemap <file>` puts it there. Caddy serves that
one file to a signed-in browser with byte ranges, and the browser draws the
streets from it. Nothing on the Map tab reaches outside the office; without
the file the tab draws its paths on plain ground.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import json
from pathlib import Path

from django.conf import settings
from django.utils import timezone

BASEMAP_NAME = "basemap.pmtiles"
NOTE_NAME = "basemap.json"
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


def basemap_note() -> dict:
    """What `./transcribe basemap fetch` wrote beside the file (v1.232.0):
    the areas it holds, in words, and the day of the build it was cut from.
    Nothing for a file an Admin cut and placed by hand, since the app cannot
    know what such a file covers; nothing for a note it cannot read."""
    try:
        note = json.loads((maps_dir() / NOTE_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(note, dict):
        return {}
    found = {}
    words = note.get("words")
    if isinstance(words, str) and words.strip():
        found["words"] = words.strip()[:200]
    with contextlib.suppress(ValueError):
        found["build"] = dt.date.fromisoformat(str(note.get("build", "")))
    return found


def basemap_state() -> dict:
    """The Status page's line: present with its size and date, or none; and
    for a fetched map, what it holds and the build it came from."""
    try:
        stat = basemap_file().stat()
    except OSError:
        return {"present": False, "words": "none; see the admin guide, Maps"}
    placed = timezone.localtime(dt.datetime.fromtimestamp(stat.st_mtime, tz=dt.UTC))
    size = stat.st_size / (1024 * 1024)
    size_words = f"{size / 1024:.1f} GB" if size >= 1024 else f"{size:.0f} MB"
    words = f"installed, {size_words}"
    note = basemap_note()
    if "words" in note:
        words += f", {note['words']}"
    if "build" in note:
        words += f", build of {note['build']:%d %b %Y}"
    return {
        "present": True,
        "size_bytes": stat.st_size,
        "words": f"{words}, placed {placed:%d %b %Y}",
    }
