"""A camera's Path (Phase 12 chapter 1): where it was, second by second,
from the file beside its video.

Some body-worn and in-car cameras export a small text file beside the video
(a WebVTT file whose cues each hold a JSON reading): the position, the
microphone flag, and for an in-car unit a wall clock, the speed, lights,
siren and brakes. The app keeps that file on the Recording as its Path file,
reads it once into Fixes and marks, and draws the case's cameras on the Map
tab. The file is the camera's record: the app invents no position.

Nothing new to install, and nothing reaches outside the office: the parse is
plain text, the map is drawn in the browser from a street-map file the Admin
places on the server (core/maps.py). Positions are content: never in an audit
row, a log line or a prompt (the chat gets times, distances and words).
"""

from __future__ import annotations

import contextlib
import datetime as dt
import errno
import hashlib
import json
import logging
import math
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from django.conf import settings
from django.db import models
from django.utils import timezone

from core import audit, settings_store

log = logging.getLogger("transcribe.camera_paths")

READY = "ready"
FAILED = "failed"
BODY, CAR = "body", "car"
FILE_NAME = "path.vtt"
MOST_BYTES = 20 * 1024 * 1024
MOST_CUES = 50_000
# No fix for longer than this is a gap: the camera was indoors, or lost the sky.
GAP_SECONDS = 10.0
# The first and last dated cues agree on the recording's start within this.
AGREE_SECONDS = 2.0
# Stood still: no fix moved further than this for longer than this.
STILL_METRES = 15.0
STILL_SECONDS = 120.0
# Together: two cameras within this many metres of each other.
NEAR_METRES = 50.0
# How far the chat's sheet looks for the nearest cameras beyond that, when
# nobody was within it (v1.235.0): past this, a camera is not near at all.
NEAREST_METRES = 2000.0
# A jump (chapter 6.11, v1.211.0): two consecutive fixes further apart than
# this many metres a second is not the camera moving. A fix far from both
# its neighbours is a glitch and is left out; a coordinate that recurs this
# many times while far from the fixes around it is a stale "home" fix the
# camera reports without a lock, and every occurrence is left out; a jump
# between two real stretches is kept but never drawn as a line.
JUMP_METRES_PER_SECOND = 70.0
HOME_FIX_TIMES = 3
FLAGS = ("mic", "low battery", "lights", "siren", "brakes", "crash", "aux", "bookmark")
CAR_KEYS = ("patrolSpeed", "lights", "siren", "brakes")
READ_VERSION = 2
# The file name's twelve digits, which the exporting camera writes as UTC.
NAME_MINUTE = re.compile(r"_(\d{12})_")
TIMING = re.compile(
    r"^(?:(\d+):)?(\d{2}):(\d{2})\.(\d{3})\s+-->\s+(?:(\d+):)?(\d{2}):(\d{2})\.(\d{3})"
)
COORDS = re.compile(r"^\s*([NS])\s*(\d+(?:\.\d+)?)\s+([EW])\s*(\d+(?:\.\d+)?)\s*$")
# The surety words the map gives a camera's clock, in the words Phase 6 and
# Phase 10 use everywhere: (word, why, tone).
SURETY_PATH_CLEAR = (
    "Clear",
    "from its path file, the first and last readings agree",
    "ok",
)
SURETY_PATH_ONCE = ("Likely", "from its path file, read once", "")
SURETY_NAME = (
    "By its name",
    "from the minute in its file name, read as UTC and shown in the office's time",
    "warn",
)
PATH = "path"
NAME = "name"

# The chat's rule, joined to the system message as documents.RULE is.
RULE = (
    "A camera's readings (where it was, its lights, siren and microphone, "
    "when it began and ended) come from its own file beside the video, not "
    "from the picture: say which camera, give the time of day, and cite the "
    "moment as [Recording N, HH:MM:SS] so the person can open it. A body "
    "camera keeps the minute before the officer activates it without sound; "
    "its microphone coming on is the officer activating it."
)
# The case chat's own rule (v1.235.0), beside the sheet `readings_block`
# writes: the reference is given with each reading, and who was near is
# worked out by the app, since a trial on an office's case showed the
# engine writing the time of day as a reference and each part of a question
# reading the pairs its own way.
CASE_RULE = (
    "A camera's readings (its lights, siren and microphone, when it began and "
    "ended, where it stood still, who was near it) come from its own file "
    "beside the video, not from the picture or the words. Say which officer or "
    "unit, give the time of day as the file gives it, and give the reference "
    "that follows the reading, copied exactly: a reference is [Recording N, "
    "HH:MM:SS] into the recording and is never a time of day. Who was near is "
    "worked out from the files and written with the reading: repeat it as "
    "given and do not work it out again. A body camera keeps the minute before "
    "the officer activates it without sound; its microphone coming on is the "
    "officer activating it."
)
SHEET_HEAD = (
    "The cameras' own files, in the office's time of day. After each reading "
    "comes its reference into the recording. Who was near is worked out from "
    "the files' positions; an officer's own cameras are not counted as near "
    "each other."
)
# A case with no path file among what a question reads (v1.235.0): asked
# about what only a camera's file records, the answer says there is none,
# not that "the transcripts do not say".
NO_FILES_RULE = (
    "No camera read for this question has a file of its own readings, so "
    "nothing here records lights, a siren, when a camera was activated or who "
    "was near. Asked about those, say that no camera in this case has a file "
    "that records it, and answer only from what was said or shown."
)


class WaitingPathFile(models.Model):
    """A path file that matched no video of its case when it came in (chapter
    6, third release): kept on the case, read by nothing, until a recording
    of that name lands and it becomes that recording's Path. Its bytes sit
    under the case's folder by id; its name is the only content kept here."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        "core.Case", on_delete=models.CASCADE, related_name="waiting_path_files"
    )
    original_filename = models.CharField(max_length=300)
    stem = models.CharField(max_length=300, db_index=True)
    size_bytes = models.BigIntegerField(default=0)
    # A first look, for the list: body or car, and how many readings.
    source = models.CharField(max_length=8, blank=True, default="")
    cues = models.IntegerField(default=0)
    # Why it was not paired when its video came: the words, and that video.
    flagged = models.CharField(max_length=300, blank=True, default="")
    flagged_recording = models.ForeignKey(
        "core.Recording",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["original_filename", "created"]

    def __str__(self) -> str:
        return self.original_filename

    @property
    def file_path(self) -> Path:
        return self.case.folder / "waiting" / f"{self.id}.vtt"


class Refused(Exception):
    """Why a file was not taken, in words for the page."""


def on() -> bool:
    return bool(settings_store.get("maps"))


class CameraPath(models.Model):
    """One Recording's path file, read once into fixes and marks."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recording = models.OneToOneField(
        "core.Recording", on_delete=models.CASCADE, related_name="camera_path"
    )
    source = models.CharField(max_length=8, default=BODY)
    # What the file says of itself: the wearer, the unit, the department.
    # Content, as the picture is: never in a row.
    wearer = models.CharField(max_length=200, blank=True, default="")
    unit = models.CharField(max_length=80, blank=True, default="")
    department = models.CharField(max_length=200, blank=True, default="")
    # An in-car file's own clock: when its recording began, in the office's
    # zone; null for a body camera, whose file carries none.
    clock_start = models.DateTimeField(null=True, blank=True)
    clock_agrees = models.BooleanField(default=False)
    # [[t, lat, lon], ...], t seconds into the recording, repeats collapsed.
    fixes = models.JSONField(default=list, blank=True)
    # [[t, key, value], ...]: each flag's first value, then every change; and
    # "speed" samples on change for an in-car unit.
    marks = models.JSONField(default=list, blank=True)
    speed_unit = models.CharField(max_length=8, blank=True, default="")
    # [[from, to], ...] stretches with no fix over GAP_SECONDS.
    gaps = models.JSONField(default=list, blank=True)
    cues = models.IntegerField(default=0)
    unread = models.IntegerField(default=0)
    fix_count = models.IntegerField(default=0)
    first_fix = models.FloatField(null=True, blank=True)
    last_fix = models.FloatField(null=True, blank=True)
    length = models.FloatField(default=0.0)
    # [south, west, north, east], or null for a file with no fix.
    bounds = models.JSONField(null=True, blank=True)
    stem_matches = models.BooleanField(default=True)
    state = models.CharField(max_length=10, default=READY)
    error = models.CharField(max_length=300, blank=True, default="")
    original_filename = models.CharField(max_length=300)
    size_bytes = models.BigIntegerField(default=0)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(null=True, blank=True)
    read_version = models.IntegerField(default=0)

    class Meta:
        ordering = ["created"]

    def __str__(self) -> str:
        return self.original_filename

    @property
    def file_path(self) -> Path:
        return self.recording.folder / FILE_NAME

    @property
    def has_fixes(self) -> bool:
        return self.fix_count > 0


# The parser ---------------------------------------------------------------------------


@dataclass
class Parsed:
    source: str = BODY
    wearer: str = ""
    unit: str = ""
    department: str = ""
    clock_start: dt.datetime | None = None
    clock_agrees: bool = False
    fixes: list = field(default_factory=list)
    marks: list = field(default_factory=list)
    speed_unit: str = ""
    gaps: list = field(default_factory=list)
    cues: int = 0
    unread: int = 0
    length: float = 0.0

    @property
    def fix_count(self) -> int:
        return len(self.fixes)

    @property
    def first_fix(self) -> float | None:
        return self.fixes[0][0] if self.fixes else None

    @property
    def last_fix(self) -> float | None:
        return self.fixes[-1][0] if self.fixes else None

    @property
    def bounds(self) -> list | None:
        if not self.fixes:
            return None
        lats = [one[1] for one in self.fixes]
        lons = [one[2] for one in self.fixes]
        return [min(lats), min(lons), max(lats), max(lons)]


def _seconds(h, m, s, ms) -> float:
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def _cues(text: str) -> list[tuple[float, float, str]]:
    """Every cue as (start, end, payload); a cue identifier line before the
    timing is allowed, as WebVTT allows it; NOTE, STYLE and REGION blocks are
    skipped; a zero-length cue is a reading all the same."""
    text = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n")
    if not text.lstrip().startswith("WEBVTT"):
        raise Refused(
            "That is not a WebVTT file: a camera's path file ends in .vtt and "
            "begins with WEBVTT."
        )
    out: list[tuple[float, float, str]] = []
    for block in re.split(r"\n{2,}", text.strip()):
        lines = block.split("\n")
        if lines[0].startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
            continue
        timing = None
        payload = ""
        for index in (0, 1):
            if index < len(lines):
                timing = TIMING.match(lines[index])
                if timing:
                    payload = "\n".join(lines[index + 1 :])
                    break
        if not timing:
            continue
        out.append(
            (_seconds(*timing.groups()[:4]), _seconds(*timing.groups()[4:]), payload)
        )
        if len(out) > MOST_CUES:
            raise Refused(
                f"That file has more than {MOST_CUES:,} cues, more than a path "
                "file can have."
            )
    return out


def _reading(payload: str) -> dict | None:
    try:
        value = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _coordinates(text) -> tuple[float, float] | None:
    """ "N36.123456 W86.123456" as (lat, lon); south and west negative; ""
    or anything out of range is no fix."""
    match = COORDS.match(str(text or ""))
    if not match:
        return None
    lat = float(match.group(2)) * (-1 if match.group(1) == "S" else 1)
    lon = float(match.group(4)) * (-1 if match.group(3) == "W" else 1)
    if abs(lat) > 90 or abs(lon) > 180:
        return None
    return round(lat, 6), round(lon, 6)


def _moment(text) -> dt.datetime | None:
    """An in-car cue's wall clock, "MM/DD/YY HH:MM:SS" in the exporting
    office's local time, made aware in the app's zone."""
    text = str(text or "").strip()
    for shape in ("%m/%d/%y %H:%M:%S", "%m/%d/%Y %H:%M:%S"):
        try:
            naive = dt.datetime.strptime(text, shape)
        except ValueError:
            continue
        return timezone.make_aware(naive, timezone.get_current_timezone())
    return None


def _flag(value) -> int:
    try:
        return int(str(value or 0).strip() or 0)
    except ValueError:
        return 0


def parse(text: str) -> Parsed:
    """The file read into a Parsed: pure, no rows touched. Refuses what is
    not a path file at all; a file with no fix is kept for its readings."""
    cues = _cues(text)
    parsed = Parsed(cues=len(cues))
    last_values: dict = {}
    last_fix = None
    run_start = None
    first_moment = last_moment = None
    seen = False
    for start, end, payload in cues:
        parsed.length = max(parsed.length, end)
        reading = _reading(payload)
        if reading is None:
            parsed.unread += 1
            continue
        if not seen:
            seen = True
            keys = set(reading)
            if keys & set(CAR_KEYS):
                parsed.source = CAR
            elif "low battery" in keys or "gpsCoordinates" in keys:
                parsed.source = BODY
            else:
                raise Refused(
                    "That file is not a camera's path file: its readings carry "
                    "no position and no camera flags."
                )
            parsed.wearer = " ".join(str(reading.get("officer") or "").split())[:200]
            parsed.unit = " ".join(str(reading.get("vehicle") or "").split())[:80]
            parsed.department = " ".join(str(reading.get("department") or "").split())[
                :200
            ]
        t = round(start, 1)
        fix = _coordinates(reading.get("gpsCoordinates"))
        if fix is None:
            if run_start is None:
                run_start = t
        else:
            if run_start is not None and t - run_start > GAP_SECONDS:
                parsed.gaps.append([run_start, t])
            run_start = None
            if fix != last_fix:
                parsed.fixes.append([t, fix[0], fix[1]])
                last_fix = fix
        for key in FLAGS:
            if key in reading:
                value = _flag(reading[key])
                if last_values.get(key) != value:
                    parsed.marks.append([t, key, value])
                    last_values[key] = value
        if "patrolSpeed" in reading:
            speed = str(reading.get("patrolSpeed") or "").strip()
            if speed:
                try:
                    value = float(speed)
                except ValueError:
                    value = None
                if value is not None and last_values.get("speed") != value:
                    parsed.marks.append([t, "speed", value])
                    last_values["speed"] = value
            unit = str(reading.get("speedUnit") or "").strip()
            if unit and not parsed.speed_unit:
                parsed.speed_unit = unit[:8]
        moment = _moment(reading.get("eventDate"))
        if moment is not None:
            if first_moment is None:
                first_moment = (moment, start)
            last_moment = (moment, start)
    if run_start is not None and parsed.length - run_start > GAP_SECONDS:
        parsed.gaps.append([run_start, round(parsed.length, 1)])
    if not seen:
        raise Refused("No cue in that file carries a camera reading.")
    parsed.fixes, jumps = clean_fixes(parsed.fixes)
    parsed.marks.extend(jumps)
    if first_moment is not None:
        parsed.clock_start = first_moment[0] - dt.timedelta(seconds=first_moment[1])
        if last_moment is not None:
            last_start = last_moment[0] - dt.timedelta(seconds=last_moment[1])
            parsed.clock_agrees = (
                abs((last_start - parsed.clock_start).total_seconds()) <= AGREE_SECONDS
            )
    return parsed


def _too_fast(a: list, b: list) -> float | None:
    """The metres between two fixes when the step between them is faster
    than any vehicle, else None."""
    metres = metres_between((a[1], a[2]), (b[1], b[2]))
    seconds = max(1.0, float(b[0]) - float(a[0]))
    return metres if metres / seconds > JUMP_METRES_PER_SECOND else None


def clean_fixes(fixes: list) -> tuple[list, list]:
    """The three jump rules (chapter 6.11, v1.211.0): the fixes kept, and
    the marks that say what was left out or broken.

    A coordinate that recurs HOME_FIX_TIMES times or more while far from
    the fixes around it is left out everywhere ("dropped"); a fix far from
    both its neighbours while they are near each other is left out
    ("dropped"); a jump that remains between two real stretches is marked
    ("jump") so the map breaks the line there. Nothing is invented: the
    marks carry the metres, the readings say so."""
    marks: list = []
    if len(fixes) < 2:
        return list(fixes), marks
    # Rule 3: the repeated far point.
    seen: dict = {}
    for index, one in enumerate(fixes):
        seen.setdefault((one[1], one[2]), []).append(index)
    home: set = set()
    for key, where in seen.items():
        if len(where) < HOME_FIX_TIMES:
            continue
        far = 0
        for index in where:
            before = fixes[index - 1] if index > 0 else None
            after = fixes[index + 1] if index + 1 < len(fixes) else None
            if (before is not None and _too_fast(before, fixes[index]) is not None) or (
                after is not None and _too_fast(fixes[index], after) is not None
            ):
                far += 1
        if far * 3 >= len(where) * 2:
            home.add(key)
    kept: list = []
    for one in fixes:
        if (one[1], one[2]) in home:
            before = kept[-1] if kept else None
            metres = (
                metres_between((before[1], before[2]), (one[1], one[2]))
                if before is not None
                else 0.0
            )
            marks.append([one[0], "dropped", round(metres)])
            continue
        kept.append(one)
    # Rule 2: a spike between two neighbours that agree with each other.
    again = True
    while again and len(kept) >= 3:
        again = False
        for index in range(1, len(kept) - 1):
            a, b, c = kept[index - 1], kept[index], kept[index + 1]
            away = _too_fast(a, b)
            if (
                away is not None
                and _too_fast(b, c) is not None
                and _too_fast(a, c) is None
            ):
                marks.append([b[0], "dropped", round(away)])
                del kept[index]
                again = True
                break
    # Rule 1: a jump kept between two real stretches breaks the line.
    for index in range(1, len(kept)):
        away = _too_fast(kept[index - 1], kept[index])
        if away is not None:
            marks.append([kept[index][0], "jump", round(away)])
    marks.sort(key=lambda m: m[0])
    return kept, marks


def dropped_count(path) -> int:
    """How many of the file's fixes the jump rules left out."""
    return sum(1 for m in path.marks or [] if m[1] == "dropped")


def stem_of(name: str) -> str:
    return Path(str(name or "")).stem.strip().lower()


def name_moment_of(filename: str) -> dt.datetime | None:
    """The file name's twelve digits as a UTC minute, in the office's zone;
    None when the name carries none."""
    match = NAME_MINUTE.search(str(filename or ""))
    if not match:
        return None
    try:
        when = dt.datetime.strptime(match.group(1), "%Y%m%d%H%M")
    except ValueError:
        return None
    return timezone.localtime(when.replace(tzinfo=dt.UTC))


# Adding and removing ------------------------------------------------------------------


def of(recording) -> CameraPath | None:
    return CameraPath.objects.filter(recording=recording).first()


def for_case(case) -> list[CameraPath]:
    return list(
        CameraPath.objects.filter(recording__case=case)
        .select_related("recording")
        .order_by("recording__created")
    )


def count(case) -> int:
    return CameraPath.objects.filter(recording__case=case).count()


def stream_heads(case) -> dict:
    """A vehicle's streams as one camera (Phase 12 chapter 9, v1.205.0): each
    later stream's recording id to its first stream's, as strings, the same
    twins the map draws as one marker; a recording with no twin is absent.
    Known only where both streams carry a path file."""
    if not on():
        return {}
    paths = list(
        CameraPath.objects.filter(recording__case=case).order_by("recording__created")
    )
    return {str(key): str(value) for key, value in _twins(paths).items()}


def names_of(case) -> dict:
    """The officers' names for the Incidents tab's lanes (Phase 12 chapter
    7): by recording id, the wearer or driver as the path file gives them
    and the unit. Empty while Maps is off."""
    if not on():
        return {}
    return {
        str(path.recording_id): {
            "name": " ".join(path.wearer.split()),
            "unit": " ".join((path.unit or "").split()),
        }
        for path in CameraPath.objects.filter(recording__case=case)
    }


def _fill(path: CameraPath, parsed: Parsed) -> None:
    path.source = parsed.source
    path.wearer = parsed.wearer
    path.unit = parsed.unit
    path.department = parsed.department
    path.clock_start = parsed.clock_start
    path.clock_agrees = parsed.clock_agrees
    path.fixes = parsed.fixes
    path.marks = parsed.marks
    path.speed_unit = parsed.speed_unit
    path.gaps = parsed.gaps
    path.cues = parsed.cues
    path.unread = parsed.unread
    path.fix_count = parsed.fix_count
    path.first_fix = parsed.first_fix
    path.last_fix = parsed.last_fix
    path.length = parsed.length
    path.bounds = parsed.bounds
    path.state = READY
    path.error = ""
    path.read_at = timezone.now()
    path.read_version = READ_VERSION


def warnings_for(recording, parsed: Parsed, filename: str) -> list[str]:
    """What is odd but not refused: the names differ, the lengths differ,
    the file's unit is not the camera the picture names, the name's minute
    sits far from the recording's clock."""
    from core import case_chronology

    out = []
    if stem_of(filename) != stem_of(recording.original_filename):
        out.append(
            "Its name does not match the video's; check it is this camera's file."
        )
    length = float(recording.duration_seconds or 0.0)
    if length and parsed.length and abs(parsed.length - length) > length * 0.10:
        out.append(
            f"The path file runs {_minutes(parsed.length)} and the video "
            f"{_minutes(length)}."
        )
    camera = str((recording.stamp or {}).get("camera") or "").strip()
    if camera and parsed.unit and _unit_key(camera) != _unit_key(parsed.unit):
        out.append(
            f"The unit inside it reads {parsed.unit} and the clock read from "
            f"the picture says {camera}."
        )
    named = name_moment_of(filename)
    date, second, how = case_chronology.clock_of(recording)
    if named is not None and date is not None and second is not None:
        clock = timezone.make_aware(
            dt.datetime.combine(date, dt.time()) + dt.timedelta(seconds=second),
            timezone.get_current_timezone(),
        )
        if abs((named - clock).total_seconds()) > 3600:
            out.append(
                "The minute in its name sits over an hour from the recording's clock."
            )
    return out


def _unit_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text or "").lower())


def _minutes(seconds: float) -> str:
    minutes = int(round(seconds / 60))
    return f"{minutes} minute{'' if minutes == 1 else 's'}"


def add(
    recording,
    *,
    data: bytes,
    filename: str,
    by,
    request=None,
    replace: bool = False,
    paired: bool = False,
) -> tuple[CameraPath, list[str]]:
    """Keep the file on the recording and read it, in the request: the
    largest file seen reads in a fraction of a second. Returns the path and
    the warnings; raises Refused with the words. `paired` says the file had
    waited on the case for this video (chapter 6); the row says so."""
    if not on():
        raise Refused("Maps are off.")
    if len(data) > MOST_BYTES:
        raise Refused(
            f"That file is {len(data) // (1024 * 1024)} MB; a path file is a few "
            f"megabytes at most (the limit is {MOST_BYTES // (1024 * 1024)} MB)."
        )
    existing = of(recording)
    if existing is not None and not replace:
        raise Refused("This recording already has a path file; replace it instead.")
    parsed = parse(data.decode("utf-8-sig", errors="replace"))
    warnings = warnings_for(recording, parsed, filename)
    if existing is not None:
        remove(existing, by=by, request=request, replacing=True)
    path = CameraPath(
        recording=recording,
        original_filename=str(filename)[:300],
        size_bytes=len(data),
        added_by=by,
        stem_matches=stem_of(filename) == stem_of(recording.original_filename),
    )
    _fill(path, parsed)
    try:
        # The browser's post can land before the upload's folder is made.
        recording.folder.mkdir(parents=True, exist_ok=True)
        (recording.folder / FILE_NAME).write_bytes(data)
    except OSError as trouble:
        if trouble.errno == errno.ENOSPC:
            raise Refused("The server's disk is full. Tell IT.") from None
        log.exception("path file for %s could not be written", recording.pk)
        raise Refused("That file could not be kept on the server.") from None
    path.save()
    recording.measure_disk()
    place_from_path(path, by=by, request=request)
    from core import cases

    audit.write(
        audit.Category.RECORDINGS,
        "Path file replaced" if existing is not None else "Path file added",
        actor=by,
        request=request,
        affected_user=cases.affected_by(recording, by),
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.title,
        source=path.source,
        fixes=path.fix_count,
        cues=path.cues,
        name_matches=path.stem_matches,
        clock=bool(path.clock_start),
        **({"paired_from_waiting": True} if paired else {}),
    )
    if recording.case_id:
        cases.note_activity(recording.case, by=by)
    return path, warnings


def remove(path: CameraPath, *, by, request=None, replacing: bool = False) -> None:
    recording = path.recording
    # A clock the file gave goes with the file; a replacement places afresh.
    if not replacing:
        from core import case_chronology

        if recording.clock_how == case_chronology.PATH:
            case_chronology.unplace(recording, by=by, request=request)
    path.delete()
    try:
        (recording.folder / FILE_NAME).unlink(missing_ok=True)
    except OSError:
        log.exception("path file for %s could not be removed", recording.pk)
    recording.measure_disk()
    if replacing:
        return
    from core import cases

    audit.write(
        audit.Category.RECORDINGS,
        "Path file removed",
        actor=by,
        request=request,
        affected_user=cases.affected_by(recording, by),
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.title,
    )


def place_from_path(path: CameraPath, *, by, request=None) -> bool:
    """The path file places the recording on the case's clock (Phase 12
    chapter 2, v1.188.0; the order of chapter 6, v1.197.0: vision, then the
    path file, then sound, then the file's name). An in-car file's own clock
    places its camera when nothing a person chose stands: over nothing, over
    a sound match, over a name. A body camera's file carries no clock, so
    the minute in its name places the camera last of all, only when nothing
    at all has, marked "By its name". Never over a stamp, a hand placement,
    a day or the file's time: those are read or chosen, and stand. The
    person who added the file is the placement's name."""
    from core import case_chronology

    recording = path.recording
    _date, _second, how = case_chronology.clock_of(recording)
    if path.clock_start is not None:
        movable = (
            "",
            case_chronology.PATH,
            case_chronology.SOUND,
            case_chronology.NAME,
        )
        if how not in movable:
            return False
        date, second = _day_second(path.clock_start)
        case_chronology.place(
            recording,
            dt.date.fromisoformat(date),
            second,
            by=by,
            request=request,
            how=case_chronology.PATH,
        )
        return True
    named = name_moment_of(path.original_filename or recording.original_filename)
    if named is None or how not in ("", case_chronology.NAME):
        return False
    date, second = _day_second(named)
    case_chronology.place(
        recording,
        dt.date.fromisoformat(date),
        second,
        by=by,
        request=request,
        how=case_chronology.NAME,
    )
    return True


def catch_up_placements() -> int:
    """Once, at the upgrade to v1.197.0: every camera whose path file can
    place it and which nothing has placed (the files added before a path
    file could place anything, v1.188.0, and the body cameras the name's
    minute now places) takes its clock. Nothing a person chose is touched;
    nothing already placed moves. Returns how many were placed."""
    from core import case_chronology

    placed = 0
    for path in CameraPath.objects.select_related("recording").iterator():
        recording = path.recording
        if recording.case_id is None:
            continue
        _date, _second, how = case_chronology.clock_of(recording)
        if how:
            continue
        try:
            if place_from_path(path, by=path.added_by, request=None):
                placed += 1
        except Exception:  # noqa: BLE001 - one odd file is not a reason to stop the rest
            log.exception("catch-up placement of %s failed", recording.pk)
    return placed


def offer_to_chronology(
    recording, *, t: float, words: str, until: float | None, by, request=None
):
    """A reading offered from the Map tab (Phase 12 chapter 3): a Proposed
    event on the recording at the reading's moment, source `path`, in the
    offerer's name, for Accept or Dismiss on the Proposed events tab as any
    proposal. Refused while that tab is off, and offered once."""
    from core import incidents, proposals

    if not proposals.tab_offered():
        raise Refused(
            "The Proposed events tab is off in this office, so an offer would "
            "have nowhere to land."
        )
    words = " ".join(str(words or "").split())[:200]
    if not words:
        raise Refused("The reading has no words.")
    t = max(0.0, float(t))
    kept = proposals.Proposal.objects.filter(
        recording=recording, source="path", text=words, at__gte=t - 0.5, at__lte=t + 0.5
    ).first()
    if kept is not None:
        if kept.state == proposals.DISMISSED:
            raise Refused("That reading was offered before and dismissed.")
        raise Refused("That reading is already on the Proposed events tab.")
    camera = incidents.incident_of(recording)
    proposal = proposals.Proposal.objects.create(
        case=recording.case,
        recording=recording,
        incident=camera.incident if camera is not None else None,
        at=t,
        until=None if until is None else max(t, float(until)),
        text=words,
        why="Read from the camera's own file, not from the picture.",
        rests_on="",
        source="path",
        proposed_by=by,
    )
    from core import cases

    audit.write(
        audit.Category.RECORDINGS,
        "Reading offered to the chronology",
        actor=by,
        request=request,
        affected_user=cases.affected_by(recording, by),
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.title,
        reading=words.split(" ")[0].lower(),
    )
    return proposal


def read_again_the_old() -> int:
    """The minute task's step: a path read by an older parser is read again
    from its file; one row per path, queued once."""
    from core import tasks

    old = list(
        CameraPath.objects.filter(
            state=READY, read_version__lt=READ_VERSION
        ).values_list("pk", flat=True)
    )
    for pk in old:
        tasks.read_camera_path.defer(path_id=str(pk))
    return len(old)


def read(path_id) -> None:
    """The media queue's step for a re-read: the kept file parsed again."""
    path = CameraPath.objects.filter(pk=path_id).select_related("recording").first()
    if path is None:
        return
    try:
        parsed = parse(path.file_path.read_text(encoding="utf-8-sig", errors="replace"))
        _fill(path, parsed)
    except Exception:  # noqa: BLE001 - the row says why, whatever it was
        log.exception("path %s could not be read again", path.pk)
        path.state = FAILED
        path.error = "This path file could not be read."
    path.save()


# Matching files to their recordings ---------------------------------------------------


def match_files(case, uploads: list, *, by, request=None, replace_ids=None) -> dict:
    """Several files at once: each whose name matches one video of the case
    with no path file lands on it; the rest come back to be settled. Each
    upload is (filename, data, recording_id or ""), the id given when a
    person chose the video or said Replace."""
    from core import incidents

    replace_ids = set(str(one) for one in (replace_ids or []))
    videos = [
        one
        for one in incidents.videos_of(case.recordings.order_by("created"))
        if incidents.is_video(one)
    ]
    by_stem: dict[str, list] = {}
    for one in videos:
        by_stem.setdefault(stem_of(one.original_filename), []).append(one)
    by_id = {str(one.pk): one for one in videos}
    landed, leftovers, waiting = [], [], []
    for filename, data, chosen in uploads:
        recording = by_id.get(str(chosen or ""))
        if recording is None:
            matches = by_stem.get(stem_of(filename), [])
            recording = matches[0] if len(matches) == 1 else None
        row = {"file": str(filename)[:300], "recording": "", "title": ""}
        if recording is None:
            # No video of that name: kept waiting on the case (chapter 6,
            # third release), paired when the video lands. Refused files
            # come back with the reason; a file already waiting is not kept twice.
            if len(data) > MOST_BYTES:
                leftovers.append(
                    {**row, "why": "refused", "words": "That file is too large."}
                )
                continue
            if WaitingPathFile.objects.filter(
                case=case, original_filename=str(filename)[:300]
            ).exists():
                waiting.append({**row, "again": True})
                continue
            try:
                keep_waiting(case, data=data, filename=filename, by=by, request=request)
            except Refused as refused:
                leftovers.append({**row, "why": "refused", "words": str(refused)})
                continue
            waiting.append(row)
            continue
        row["recording"] = str(recording.pk)
        row["title"] = recording.title
        wants_replace = str(recording.pk) in replace_ids
        if of(recording) is not None and not wants_replace:
            leftovers.append(
                {
                    **row,
                    "why": "has_one",
                    "words": "This video already has a path file.",
                }
            )
            continue
        try:
            parsed = parse(data.decode("utf-8-sig", errors="replace"))
        except Refused as refused:
            leftovers.append({**row, "why": "refused", "words": str(refused)})
            continue
        flagged = [
            one
            for one in warnings_for(recording, parsed, filename)
            if not one.startswith("Its name")
        ]
        if flagged and not chosen:
            leftovers.append({**row, "why": "flagged", "words": " ".join(flagged)})
            continue
        try:
            path, warnings = add(
                recording,
                data=data,
                filename=filename,
                by=by,
                request=request,
                replace=wants_replace,
            )
        except Refused as refused:
            leftovers.append({**row, "why": "refused", "words": str(refused)})
            continue
        landed.append({**row, "fixes": path.fix_count, "warnings": warnings})
    return {"landed": landed, "leftovers": leftovers, "waiting": waiting}


# Path files that wait for their video (chapter 6, third release) ---------------------


def keep_waiting(
    case, *, data: bytes, filename: str, by, request=None
) -> WaitingPathFile:
    """Keep a file that matched no video on the case, after one look to see
    it is a path file at all (the parse is the same look the take-in does).
    One audit row, never the names inside the file."""
    parsed = parse(data.decode("utf-8-sig", errors="replace"))
    one = WaitingPathFile.objects.create(
        case=case,
        original_filename=str(filename)[:300],
        stem=stem_of(filename)[:300],
        size_bytes=len(data),
        source=parsed.source,
        cues=parsed.cues,
        added_by=by,
    )
    one.file_path.parent.mkdir(parents=True, exist_ok=True)
    one.file_path.write_bytes(data)
    audit.write(
        audit.Category.RECORDINGS,
        "Path file kept waiting",
        actor=by,
        request=request,
        object_type="case",
        object_id=case.pk,
        object_label=case.name[:400],
        source=parsed.source,
        cues=parsed.cues,
    )
    return one


def waiting_of(case) -> list[WaitingPathFile]:
    return list(
        WaitingPathFile.objects.filter(case=case).select_related("flagged_recording")
    )


def waiting_count(case) -> int:
    return WaitingPathFile.objects.filter(case=case).count()


def waiting_rows(case) -> list[dict]:
    """The Map tab's fold: the name, the kind and the count, and why one was
    not paired when its video came."""
    return [
        {
            "id": str(one.pk),
            "file": one.original_filename,
            "kind": "in-car" if one.source == CAR else "body",
            "cues": one.cues,
            "flagged": one.flagged,
            "flagged_title": (
                one.flagged_recording.title if one.flagged_recording is not None else ""
            ),
            "flagged_recording": (
                str(one.flagged_recording_id) if one.flagged_recording_id else ""
            ),
        }
        for one in waiting_of(case)
    ]


def remove_waiting(one: WaitingPathFile, *, by, request=None) -> None:
    case = one.case
    with contextlib.suppress(FileNotFoundError):
        one.file_path.unlink()
    one.delete()
    audit.write(
        audit.Category.RECORDINGS,
        "Waiting path file removed",
        actor=by,
        request=request,
        object_type="case",
        object_id=case.pk,
        object_label=case.name[:400],
    )


def remove_all_waiting(case, *, by, request=None) -> int:
    found = waiting_of(case)
    for one in found:
        with contextlib.suppress(FileNotFoundError):
            one.file_path.unlink()
    WaitingPathFile.objects.filter(case=case).delete()
    if found:
        audit.write(
            audit.Category.RECORDINGS,
            "Waiting path files removed",
            actor=by,
            request=request,
            object_type="case",
            object_id=case.pk,
            object_label=case.name[:400],
            count=len(found),
        )
    return len(found)


def pair_waiting(recording, *, by=None, request=None) -> CameraPath | None:
    """A recording that has just landed in a case: the waiting file of its
    name becomes its Path, by the same stem rule the take-in uses, with the
    usual "Path file added" row. A file that is flagged against this
    recording (the unit inside it is not the camera the picture names, or
    the lengths differ) stays waiting and says why; a second recording of
    the same name takes the next waiting file. None when nothing matched."""
    if not on() or recording.case_id is None or of(recording) is not None:
        return None
    stem = stem_of(recording.original_filename)
    if not stem:
        return None
    for one in WaitingPathFile.objects.filter(case_id=recording.case_id, stem=stem):
        try:
            data = one.file_path.read_bytes()
        except OSError:
            continue
        try:
            parsed = parse(data.decode("utf-8-sig", errors="replace"))
        except Refused:
            continue
        flagged = [
            words
            for words in warnings_for(recording, parsed, one.original_filename)
            if not words.startswith("Its name")
        ]
        if flagged:
            one.flagged = " ".join(flagged)[:300]
            one.flagged_recording = recording
            one.save(update_fields=["flagged", "flagged_recording"])
            continue
        try:
            path, _warnings = add(
                recording,
                data=data,
                filename=one.original_filename,
                by=by or one.added_by,
                request=request,
                paired=True,
            )
        except Refused:
            continue
        with contextlib.suppress(FileNotFoundError):
            one.file_path.unlink()
        one.delete()
        return path
    return None


def pair_anyway(one: WaitingPathFile, *, by, request=None) -> CameraPath:
    """Add anyway, from the fold: the flagged file onto the recording it was
    flagged against, as the take-in's Add anyway does."""
    recording = one.flagged_recording
    if recording is None or recording.case_id != one.case_id:
        raise Refused("That video is no longer in this case.")
    if of(recording) is not None:
        raise Refused("That video has a path file now.")
    data = one.file_path.read_bytes()
    path, _warnings = add(
        recording,
        data=data,
        filename=one.original_filename,
        by=by,
        request=request,
        paired=True,
    )
    with contextlib.suppress(FileNotFoundError):
        one.file_path.unlink()
    one.delete()
    return path


def about_words(parsed: Parsed, filename: str) -> str:
    """A file described in a few words, for the chooser: its kind, its
    length, and the day its name gives."""
    kind = "An in-car camera" if parsed.source == CAR else "A body camera"
    words = f"{kind}, {_minutes(parsed.length)}"
    named = name_moment_of(filename)
    if parsed.clock_start is not None:
        words += f", {timezone.localtime(parsed.clock_start):%d %b %Y} by its own clock"
    elif named is not None:
        words += f", {named:%d %b %Y} by its name"
    return words + ("" if parsed.fix_count else ", no position in it")


# The camera's clock -------------------------------------------------------------------


def _day_second(when: dt.datetime) -> tuple[str, float]:
    local = timezone.localtime(when)
    return local.date().isoformat(), float(
        local.hour * 3600 + local.minute * 60 + local.second + local.microsecond / 1e6
    )


def zero_of(recording, path: CameraPath | None = None) -> dict | None:
    """When the recording began, for the map, in the maintainer's order: the
    path file's own clock, then the clock the app holds for the recording,
    then the file's creation time, then the minute in its name; or None.
    {date, second, how, surety: {word, why, tone}}."""
    from core import case_chronology, incidents

    if path is None:
        path = of(recording)
    if path is not None and path.clock_start is not None:
        date, second = _day_second(path.clock_start)
        word, why, tone = SURETY_PATH_CLEAR if path.clock_agrees else SURETY_PATH_ONCE
        return {
            "date": date,
            "second": second,
            "how": PATH,
            "surety": {"word": word, "why": why, "tone": tone},
        }
    date, second, how = case_chronology.clock_of(recording)
    if date is not None and second is not None:
        return {
            "date": date.isoformat(),
            "second": float(second),
            "how": how,
            "surety": case_chronology.clock_surety(recording),
        }
    if date is not None:
        # A day alone: listed under its day, not on the clock.
        return {"date": date.isoformat(), "second": None, "how": how, "surety": None}
    moment = incidents.file_moment_of(recording)
    if moment is not None:
        date, second = _day_second(moment)
        return {
            "date": date,
            "second": second,
            "how": case_chronology.FILE,
            "surety": {
                "word": "Unchecked",
                "why": "from its file's own time, checked by nobody",
                "tone": "warn",
            },
        }
    named = name_moment_of(recording.original_filename)
    if named is not None:
        date, second = _day_second(named)
        word, why, tone = SURETY_NAME
        return {
            "date": date,
            "second": second,
            "how": NAME,
            "surety": {"word": word, "why": why, "tone": tone},
        }
    return None


# The readings -------------------------------------------------------------------------


def metres_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    """The distance over the ground between two fixes, by the haversine."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 6_371_000.0 * math.asin(math.sqrt(h))


def position_at(path: CameraPath, t: float) -> tuple[float, float] | None:
    """Where the camera was at t seconds in: the last fix at or before t,
    unless t falls in a gap or before the first fix."""
    fixes = path.fixes or []
    if not fixes or t < fixes[0][0]:
        return None
    for start, end in path.gaps or []:
        if start <= t < end:
            return None
    low, high = 0, len(fixes) - 1
    while low < high:
        mid = (low + high + 1) // 2
        if fixes[mid][0] <= t:
            low = mid
        else:
            high = mid - 1
    return fixes[low][1], fixes[low][2]


def still_spells(path: CameraPath) -> list[tuple[float, float]]:
    """Stretches where no fix moved further than STILL_METRES for longer
    than STILL_SECONDS: the vehicle parked, the officer stayed."""
    fixes = path.fixes or []
    out: list[tuple[float, float]] = []
    if not fixes:
        return out
    anchor = fixes[0]
    for one in fixes[1:] + [[path.length, fixes[-1][1], fixes[-1][2]]]:
        if metres_between((anchor[1], anchor[2]), (one[1], one[2])) > STILL_METRES:
            if one[0] - anchor[0] >= STILL_SECONDS:
                out.append((anchor[0], one[0]))
            anchor = one
    if path.length - anchor[0] >= STILL_SECONDS:
        out.append((anchor[0], path.length))
    return out


FLAG_WORDS = {
    "lights": ("Lights on", "Lights off"),
    "siren": ("Siren on", "Siren off"),
    "brakes": ("Brakes", ""),
    "crash": ("Crash sensor", ""),
    "aux": ("Auxiliary on", "Auxiliary off"),
    "bookmark": ("Bookmark pressed", ""),
    "mic": ("Mic on", "Muted"),
    "low battery": ("Low battery", "Battery back"),
}


def _km(metres) -> str:
    metres = float(metres or 0)
    return f"{metres / 1000:.1f} km" if metres >= 1000 else f"{int(round(metres))} m"


def events_of(path: CameraPath) -> list[dict]:
    """The readings that are moments, in order: the camera's start and end,
    each flag turning on and off (an on carries how long until the off),
    stood still, and the top speed reached. {t, kind, value, words, until}."""
    events: list[dict] = []
    length = float(path.length or 0.0)
    events.append(
        {"t": 0.0, "kind": "camera", "value": 1, "words": "Camera on", "until": None}
    )
    open_since: dict = {}
    top_speed = None
    for t, key, value in path.marks or []:
        if key == "speed":
            if top_speed is None or value > top_speed[1]:
                top_speed = (t, value)
            continue
        # The jump rules (chapter 6.11): what was left out, and where the
        # line breaks; each with the metres, so nothing is hidden.
        if key in ("dropped", "jump"):
            events.append(
                {
                    "t": t,
                    "kind": key,
                    "value": value,
                    "words": (
                        f"A fix {_km(value)} away left out"
                        if key == "dropped"
                        else f"Jumped {_km(value)}: the line is not drawn"
                    ),
                    "until": None,
                }
            )
            continue
        on_words, off_words = FLAG_WORDS.get(key, (key, ""))
        if value:
            if key in ("brakes", "bookmark", "crash"):
                events.append(
                    {"t": t, "kind": key, "value": 1, "words": on_words, "until": None}
                )
                continue
            open_since[key] = len(events)
            words = on_words
            if key == "mic" and path.source == BODY and t >= 30:
                words = "Activated"
            # A muted spell ends when the mic comes back (chapter 3).
            muted = open_since.pop("mic:off", None)
            if key == "mic" and muted is not None:
                events[muted]["until"] = t
            events.append(
                {"t": t, "kind": key, "value": 1, "words": words, "until": None}
            )
        else:
            index = open_since.pop(key, None)
            if index is not None:
                events[index]["until"] = t
            if t > 0 and off_words:
                events.append(
                    {"t": t, "kind": key, "value": 0, "words": off_words, "until": None}
                )
                if key == "mic":
                    open_since["mic:off"] = len(events) - 1
    for index in open_since.values():
        events[index]["until"] = length
    for start, end in still_spells(path):
        events.append(
            {
                "t": start,
                "kind": "still",
                "value": 1,
                "words": "Stood still",
                "until": end,
            }
        )
    if top_speed is not None and top_speed[1] > 0:
        unit = (path.speed_unit or "").lower() or "mph"
        events.append(
            {
                "t": top_speed[0],
                "kind": "speed",
                "value": top_speed[1],
                "words": f"Reached {top_speed[1]:g} {unit}",
                "until": None,
            }
        )
    events.append(
        {
            "t": length,
            "kind": "camera",
            "value": 0,
            "words": "Camera off",
            "until": None,
        }
    )
    # The first value of a flag at the start is the state, not an event: a
    # mic that is on from the first cue is not "activated".
    events = [
        one
        for one in events
        if not (
            one["t"] == 0.0 and one["kind"] not in ("camera",) and one["value"] == 0
        )
    ]
    events.sort(key=lambda one: (one["t"], one["kind"]))
    return events


def _spell_words(t: float, until: float | None, zero: dict | None) -> str:
    """ "20:22:08 to 20:31:40" on the clock, or "at 4:08 in" without one."""
    from core import incidents

    if zero is not None and zero.get("second") is not None:
        start = incidents.hms(zero["second"] + t)
        if until is None:
            return start
        return f"{start} to {incidents.hms(zero['second'] + until)}"
    start = f"{incidents.elapsed(t)} in"
    if until is None:
        return start
    return f"{start} to {incidents.elapsed(until)} in"


def readings_words(path: CameraPath, zero: dict | None) -> list[str]:
    """One sentence per reading, in the office's time of day when the
    camera is on the clock, else in minutes into the recording."""
    out = []
    for one in events_of(path):
        if one["kind"] == "camera":
            words = "began" if one["value"] else "ended"
            out.append(f"recording {words} {_spell_words(one['t'], None, zero)}")
        elif one["kind"] == "mic" and one["value"]:
            words = _spell_words(one["t"], None, zero)
            if one["words"] == "Activated":
                out.append(
                    f"activated {words} (the minute before is the camera's buffer, "
                    "without sound)"
                )
            else:
                out.append(f"mic on {words}")
        elif one["kind"] == "mic":
            out.append(f"muted {_spell_words(one['t'], one['until'], zero)}")
        elif one["kind"] in ("lights", "siren", "aux", "low battery") and one["value"]:
            out.append(
                f"{one['words'].lower()} {_spell_words(one['t'], one['until'], zero)}"
            )
        elif one["kind"] == "still":
            minutes = max(1, int(round(((one["until"] or one["t"]) - one["t"]) / 60)))
            out.append(
                f"stood still {_spell_words(one['t'], one['until'], zero)} "
                f"({minutes} minute{'' if minutes == 1 else 's'})"
            )
        elif one["kind"] in ("brakes", "bookmark", "crash", "speed"):
            out.append(f"{one['words'].lower()} {_spell_words(one['t'], None, zero)}")
    for start, end in path.gaps or []:
        out.append(f"no fix {_spell_words(start, end, zero)}")
    left_out = dropped_count(path)
    if left_out:
        out.append(
            f"{left_out} fix{'' if left_out == 1 else 'es'} left out as jumps the "
            "camera could not have made"
        )
    return out


def together(paths: list[CameraPath], zeros: dict) -> list[tuple]:
    """Which cameras were within NEAR_METRES of each other and when, on the
    office's clock: (a, b, from_second, to_second), read at ten-second
    steps from the fixes."""
    clocked = [
        (one, zeros[one.recording_id]["second"])
        for one in paths
        if one.fixes
        and zeros.get(one.recording_id)
        and zeros[one.recording_id].get("second") is not None
    ]
    out = []
    for i, (a, za) in enumerate(clocked):
        for b, zb in clocked[i + 1 :]:
            low = max(za + a.first_fix, zb + b.first_fix)
            # To the recording's end, not the last fix: a camera that never
            # moved has one fix and stood there until it was switched off.
            high = min(za + max(a.length, a.last_fix), zb + max(b.length, b.last_fix))
            spell_start = None
            step = 10.0
            moment = low
            while moment <= high + step:
                near = False
                if moment <= high:
                    pa = position_at(a, moment - za)
                    pb = position_at(b, moment - zb)
                    near = (
                        pa is not None
                        and pb is not None
                        and metres_between(pa, pb) <= NEAR_METRES
                    )
                if near and spell_start is None:
                    spell_start = moment
                if not near and spell_start is not None:
                    if moment - step - spell_start >= 60:
                        out.append((a, b, spell_start, moment - step))
                    spell_start = None
                moment += step
    return out


def who_of(path: CameraPath) -> str:
    """How a camera is named in a sentence about who was near: by its unit
    and officer for an in-car camera, by its officer for a body camera, and
    by its recording's title where the file names neither."""
    wearer = (path.wearer or "").strip()
    unit = (path.unit or "").strip()
    if path.source == CAR and unit:
        return f"unit {unit} (officer {wearer})" if wearer else f"unit {unit}"
    if wearer:
        return f"officer {wearer}"
    return path.recording.title


def same_officer(a: CameraPath, b: CameraPath) -> bool:
    """An officer's own body camera and car camera, or one unit's two
    streams, are not "someone nearby": the same wearer, or the same unit."""
    wearer_a, wearer_b = (a.wearer or "").strip(), (b.wearer or "").strip()
    if wearer_a and wearer_a.casefold() == wearer_b.casefold():
        return True
    unit_a, unit_b = (a.unit or "").strip(), (b.unit or "").strip()
    return bool(unit_a) and unit_a.casefold() == unit_b.casefold()


def near_at(path: CameraPath, t: float, paths: list, zeros: dict) -> dict | None:
    """Who was near this camera at t seconds in, worked out from the files'
    positions (v1.235.0): {"within": [who, ...]} inside NEAR_METRES, and
    {"nearest": [(who, metres), ...]} for the two nearest beyond it and
    inside NEAREST_METRES. None when the camera had no position then or is
    not on the clock. An officer's own other cameras are not counted, and an
    officer with two cameras is said once, at the nearer."""
    zero = zeros.get(path.recording_id)
    here = position_at(path, t)
    if here is None or not zero or zero.get("second") is None:
        return None
    moment = zero["second"] + t
    found: dict[str, float] = {}
    for other in paths:
        if other.recording_id == path.recording_id or not other.fixes:
            continue
        if same_officer(path, other):
            continue
        theirs = zeros.get(other.recording_id)
        if not theirs or theirs.get("second") is None:
            continue
        if theirs.get("date") != zero.get("date"):
            continue
        there = position_at(other, moment - theirs["second"])
        if there is None:
            continue
        metres = metres_between(here, there)
        who = who_of(other)
        if who not in found or metres < found[who]:
            found[who] = metres
    ordered = sorted(found.items(), key=lambda one: one[1])
    return {
        "within": [who for who, metres in ordered if metres <= NEAR_METRES],
        "nearest": [
            (who, metres)
            for who, metres in ordered
            if NEAR_METRES < metres <= NEAREST_METRES
        ][:2],
    }


def near_words(near: dict | None) -> str:
    """ " Within 50 m then: officer Ruiz. Nearest beyond: unit 7, 310 m." """
    if near is None:
        return ""
    within = ", ".join(near["within"]) if near["within"] else "nobody else's camera"
    words = f" Within {int(NEAR_METRES)} m then: {within}."
    if near["nearest"]:
        words += (
            " Nearest beyond: "
            + ", ".join(f"{who} {_km(metres)}" for who, metres in near["nearest"])
            + "."
        )
    return words


def _reference(number: int, t: float, length: float) -> str:
    """[Recording N, HH:MM:SS] into the recording: the reference a reading
    carries, ready to be copied, so nobody has to subtract a clock."""
    whole = int(max(0.0, min(float(t), float(length or t))))
    return (
        f"[Recording {number}, {whole // 3600:02d}:{whole % 3600 // 60:02d}"
        f":{whole % 60:02d}]"
    )


def sheet_lines(path: CameraPath, zero: dict | None, number: int, near) -> list[str]:
    """One line per reading of one camera, each with its reference into the
    recording, and for the lights, the siren, the camera being activated, a
    bookmark and the crash sensor, who was near at that moment (`near` is a
    function of t, or None)."""

    def at(t: float) -> str:
        return f"{_spell_words(t, None, zero)} {_reference(number, t, path.length)}"

    def spell(t: float, until: float | None) -> str:
        return at(t) + (f" to {_spell_words(until, None, zero)}" if until else "")

    def nearby(t: float) -> str:
        return near_words(near(t)) if near is not None else ""

    out = []
    for one in events_of(path):
        kind, t = one["kind"], one["t"]
        if kind == "camera":
            out.append(f"recording {'began' if one['value'] else 'ended'} {at(t)}")
        elif kind == "mic" and one["value"]:
            if one["words"] == "Activated":
                out.append(
                    f"activated {at(t)} (the minute before is the camera's buffer, "
                    f"without sound).{nearby(t)}"
                )
            else:
                out.append(f"mic on {at(t)}")
        elif kind == "mic":
            out.append(f"muted {spell(t, one['until'])}")
        elif kind in ("lights", "siren") and one["value"]:
            out.append(f"{one['words'].lower()} {spell(t, one['until'])}.{nearby(t)}")
        elif kind in ("aux", "low battery") and one["value"]:
            out.append(f"{one['words'].lower()} {spell(t, one['until'])}")
        elif kind == "still":
            minutes = max(1, int(round(((one["until"] or t) - t) / 60)))
            out.append(
                f"stood still {spell(t, one['until'])} "
                f"({minutes} minute{'' if minutes == 1 else 's'})"
            )
        elif kind in ("bookmark", "crash"):
            out.append(f"{one['words'].lower()} {at(t)}.{nearby(t)}")
        elif kind in ("brakes", "speed"):
            out.append(f"{one['words'].lower()} {at(t)}")
    for start, end in path.gaps or []:
        out.append(f"no fix {spell(start, end)}")
    left_out = dropped_count(path)
    if left_out:
        out.append(
            f"{left_out} fix{'' if left_out == 1 else 'es'} left out as jumps the "
            "camera could not have made"
        )
    if not path.fixes:
        out.append("no position in its file")
    return out


def paths_among(case, read: list) -> list[CameraPath]:
    """The path files of the recordings a question may read, or none."""
    if not on():
        return []
    wanted = {recording.pk for recording in read}
    return [one for one in for_case(case) if one.recording_id in wanted]


def readings_block(case, read: list, *, spells: bool = True) -> str:
    """The chat's sheet (Phase 12 chapter 1; rewritten v1.235.0): for each
    camera with a path among the recordings numbered for a question, its
    readings one to a line, each with the reference that opens it, and who
    was near at the moments that matter; then, with `spells`, who was within
    NEAR_METRES of it for a minute or more, and when. Times of day, distances
    and words, never a coordinate. "" when there is nothing to say."""
    paths = paths_among(case, read)
    if not paths:
        return ""
    numbers = {recording.pk: number for number, recording in enumerate(read, 1)}
    zeros = {one.recording_id: zero_of(one.recording, one) for one in paths}
    beside: dict = {}
    if spells:
        for a, b, start, end in together(paths, zeros):
            if same_officer(a, b):
                continue
            for mine, theirs in ((a, b), (b, a)):
                beside.setdefault(mine.recording_id, {}).setdefault(
                    who_of(theirs), []
                ).append((start, end))
    lines = [SHEET_HEAD]
    for path in sorted(paths, key=lambda one: numbers[one.recording_id]):
        recording = path.recording
        number = numbers[recording.pk]
        kind = "an in-car camera" if path.source == CAR else "a body camera"
        who = f"worn by {path.wearer}" if path.wearer and path.source == BODY else ""
        who = who or (f"officer {path.wearer}" if path.wearer else "")
        unit = f"unit {path.unit}" if path.unit else ""
        head = ", ".join(one for one in (kind, unit, who) if one)
        zero = zeros[recording.pk]
        clock = ""
        if zero is None or zero.get("second") is None:
            clock = "not on the clock, so its times are minutes into the recording"
        elif zero["how"] == PATH:
            clock = "clock from its own file"
        elif zero["how"] == NAME:
            clock = "clock from the minute in its file name, to the minute"
        lines.append(
            f"Recording {number} ({recording.title}; {head}"
            + (f"; {clock}" if clock else "")
            + "):"
        )

        def near(t: float, path=path) -> dict | None:
            return near_at(path, t, paths, zeros)

        lines.extend("- " + one for one in sheet_lines(path, zero, number, near))
        if beside.get(recording.pk):
            lines.append(
                f"- within {int(NEAR_METRES)} m of this camera for a minute or more: "
                + "; ".join(
                    f"{who} "
                    + " and ".join(
                        f"{_hms(start)} to {_hms(end)}" for start, end in sorted(spans)
                    )
                    for who, spans in sorted(beside[recording.pk].items())
                )
            )
    return "\n".join(lines)


def paths_signature(incident) -> str:
    """Which path files an incident's cameras have, for a memo or a
    comparison to remember (v1.235.0): one written before a camera's file
    was added, replaced or removed says so. "none" when no camera has one,
    which is not the "" of a row written before this was kept."""
    held = {one.recording_id: one for one in for_case(incident.case)}
    parts = sorted(
        f"{camera.recording_id}:{held[camera.recording_id].pk}"
        f":{held[camera.recording_id].size_bytes}"
        for camera in incident.cameras.all()
        if camera.recording_id in held
    )
    if not parts:
        return "none"
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:16]


def paths_changed_since(incident, signature: str, written_at) -> bool:
    """Whether a camera's path file was added, replaced or removed since a
    memo or a comparison was written. A row from before the signature was
    kept (v1.235.0) is judged by the files' own dates: one added after it
    was written."""
    if not on():
        return False
    if signature:
        return signature != paths_signature(incident)
    if written_at is None:
        return False
    cameras = {camera.recording_id for camera in incident.cameras.all()}
    return any(
        one.recording_id in cameras and one.created > written_at
        for one in for_case(incident.case)
    )


def _hms(second: float) -> str:
    from core import incidents

    return incidents.hms(second)


def readings_block_for_incident(incident) -> str:
    """The incident chat's, the memo's and the comparison's block: the same
    readings, named by the camera ids the incident's record uses, by the
    incident's clock where it has one (the cameras were placed on it) and
    the recording's own otherwise."""
    lines = readings_lines_for_incident(incident)
    if not lines:
        return ""
    return "The cameras' own files, in the time of day:\n" + "\n".join(lines)


def readings_lines_for_incident(incident) -> list[str]:
    """One line per camera of the incident that has a path file, for the
    block above and the timeline report's section (Phase 12 chapter 2)."""
    if not on():
        return []
    cameras = list(incident.cameras.select_related("recording"))
    paths = {one.recording_id: one for one in for_case(incident.case)}
    lines = []
    for camera in cameras:
        path = paths.get(camera.recording_id)
        if path is None:
            continue
        if incident.has_clock() and camera.is_placed():
            zero = {
                "date": _iso_day(incident.clock_date),
                "second": float(incident.clock_zero + camera.starts_at),
                "how": "incident",
                "surety": None,
            }
        else:
            zero = zero_of(camera.recording, path)
        kind = "an in-car camera" if path.source == CAR else "a body camera"
        who = f"worn by {path.wearer}" if path.wearer and path.source == BODY else ""
        who = who or (f"officer {path.wearer}" if path.wearer else "")
        head = ", ".join(one for one in (kind, who) if one)
        words = readings_words(path, zero)
        if not path.fixes:
            words.append("no position in its file")
        lines.append(f"Camera {camera.camera_id()} ({head}): " + "; ".join(words) + ".")
    return lines


# The Map tab's reading ----------------------------------------------------------------


def _colours(case) -> dict:
    """Recording id -> the chronology's colour, by the case's upload order,
    so a camera is one colour on the chronology and the map."""
    from core.chronology import FIGURE_COLOURS

    out = {}
    for index, pk in enumerate(
        case.recordings.order_by("created").values_list("pk", flat=True)
    ):
        out[pk] = FIGURE_COLOURS[index % len(FIGURE_COLOURS)]
    return out


def _twins(paths: list[CameraPath]) -> dict:
    """An in-car unit's several streams carry one file each with the same
    readings: the later ones point at the first, so the map draws one marker."""
    first: dict = {}
    out = {}
    for path in paths:
        key = (path.source, path.unit, path.fix_count, path.first_fix, path.clock_start)
        if path.unit and key in first:
            out[path.recording_id] = first[key]
        else:
            first[key] = path.recording_id
    return out


def _notes_of(recording) -> list[dict]:
    from core.jobs import Segment
    from core.notes import MomentNote

    out = []
    for one in MomentNote.objects.filter(recording=recording).select_related("note_by"):
        out.append(
            {
                "id": f"moment:{one.pk}",
                "t": float(one.at),
                "words": one.note,
                "by": one.note_by.shown_name if one.note_by else "",
                "on": timezone.localtime(one.note_changed).strftime("%d %b %Y")
                if one.note_changed
                else "",
                "to_check": one.note_to_check,
                "from": (one.note_from or {}).get("words", ""),
            }
        )
    for one in (
        Segment.objects.filter(transcript__recording=recording)
        .exclude(note="")
        .filter(same_as_other_side=False)
        .select_related("note_by")
    ):
        out.append(
            {
                "id": f"line:{one.pk}",
                "t": float(one.start),
                "words": one.note,
                "by": one.note_by.shown_name if one.note_by else "",
                "on": timezone.localtime(one.note_changed).strftime("%d %b %Y")
                if one.note_changed
                else "",
                "to_check": bool(getattr(one, "note_to_check", False)),
                "from": (getattr(one, "note_from", None) or {}).get("words", ""),
            }
        )
    out.sort(key=lambda one: one["t"])
    return out


def _clips_of(recording) -> list[dict]:
    from core.clips import Clip

    return [
        {"id": str(one.pk), "title": one.title, "start": one.start, "end": one.end}
        for one in Clip.objects.filter(recording=recording).order_by("start")
    ]


def map_of(case, *, day: str = "", viewer) -> dict:
    """What the Map tab reads once: every video of the case, with its path
    where it has one, its clock and surety, its readings, notes and clips;
    the days; the basemap; who may add."""
    from django.urls import reverse

    from core import incidents, maps, media_access

    videos = [
        one
        for one in incidents.videos_of(case.recordings.order_by("created"))
        if incidents.is_video(one)
    ]
    paths = {one.recording_id: one for one in for_case(case)}
    colours = _colours(case)
    twins = _twins([paths[one.pk] for one in videos if one.pk in paths])
    cameras = []
    days: dict[str, int] = {}
    off_clock = []
    without = []
    zeros: dict = {}
    for recording in videos:
        path = paths.get(recording.pk)
        if path is None:
            without.append({"id": str(recording.pk), "title": recording.title})
            continue
        zero = zero_of(recording, path)
        zeros[recording.pk] = zero
        row = {
            "id": str(recording.pk),
            "title": recording.title,
            "unit": path.unit,
            "wearer": path.wearer,
            "source": path.source,
            "colour": colours.get(recording.pk, ""),
            "zero": (
                {"date": zero["date"], "second": zero["second"]}
                if zero and zero.get("second") is not None
                else None
            ),
            "day_only": zero["date"] if zero and zero.get("second") is None else "",
            "how": zero["how"] if zero else "",
            "surety": (zero or {}).get("surety")
            or {"word": "Not placed", "why": "", "tone": "warn"},
            "length": float(path.length or recording.duration_seconds or 0.0),
            "first_fix": path.first_fix,
            "last_fix": path.last_fix,
            "bounds": path.bounds,
            "fixes": path.fixes,
            "marks": path.marks,
            "dropped": dropped_count(path),
            "gaps": path.gaps,
            "speed_unit": path.speed_unit,
            "events": events_of(path),
            "notes": _notes_of(recording),
            "clips": _clips_of(recording),
            "media": media_access.playback_url(recording),
            "viewer_url": reverse("viewer", args=[recording.pk]),
            "incident": incidents.link_for(recording),
            "stem_matches": path.stem_matches,
            "twin_of": str(twins[recording.pk]) if recording.pk in twins else "",
            "file": path.original_filename,
            "clock_agrees": path.clock_agrees,
        }
        cameras.append(row)
        if row["zero"] is not None:
            days[row["zero"]["date"]] = days.get(row["zero"]["date"], 0) + 1
        else:
            off_clock.append(row["id"])
    day_rows = [
        {"date": date, "cameras": n, "words": _day_words(date)}
        for date, n in sorted(days.items())
    ]
    chosen = day
    if not chosen and day_rows:
        chosen = max(day_rows, key=lambda one: (one["cameras"], one["date"]))["date"]
    may_add = case.role_of(viewer) in ("owner", "collaborator", "admin")
    return {
        "time_zone": settings.TIME_ZONE,
        "basemap": maps.basemap_json(),
        "days": day_rows,
        "day": chosen,
        "cameras": cameras,
        "off_clock": off_clock,
        "videos_without_path": without,
        "add_url": reverse("case-paths-add", args=[case.pk]),
        "may_add": may_add,
        # The path files waiting for their video (chapter 6, third release).
        "waiting": [
            {
                **row,
                "remove_url": reverse(
                    "case-paths-waiting-remove", args=[case.pk, row["id"]]
                ),
                "add_anyway_url": reverse(
                    "case-paths-waiting-add-anyway", args=[case.pk, row["id"]]
                ),
            }
            for row in waiting_rows(case)
        ],
        "waiting_remove_all_url": reverse(
            "case-paths-waiting-remove-all", args=[case.pk]
        ),
        "incidents": _incident_spans(case),
        "note_url": reverse("recording-note-at", args=[uuid.UUID(int=0)]),
        # The forming offer from the map (join 1): cameras that kept close
        # for a while and sit in no incident; made only by a press.
        "offer": offers_of(
            case, [paths[one.pk] for one in videos if one.pk in paths], zeros
        ),
        "new_incident_url": reverse("new-incident", args=[case.pk]),
        # The cap (Phase 12 chapter 9, v1.203.0): the circle's list ticks
        # this many, the longest inside first.
        "most": _most_cameras(),
        "decline_url": reverse("decline-incident-offer", args=[case.pk]),
        # Offer to the chronology (chapter 3): withheld, with the reason,
        # while the Proposed events tab is off.
        "may_offer": _may_offer(),
        "offer_why": "" if _may_offer() else "The Proposed events tab is off.",
    }


def _may_offer() -> bool:
    from core import proposals

    return proposals.tab_offered()


def strip_suggestions(case, date_iso: str) -> list[dict]:
    """The Incidents tab's Suggested row (chapter 6, v1.197.0): the cameras
    that were together by their paths on the day, as the map offers them,
    with the officers' names as the files give them. Empty while Maps is
    off or no path is on the clock that day."""
    from core import incidents

    if not on():
        return []
    declined = set(case.declined_offers or [])
    paths = for_case(case)
    zeros = {}
    for path in paths:
        zero = zero_of(path.recording, path)
        if zero and zero.get("second") is not None:
            zeros[path.recording_id] = zero
    out = []
    for offer in offers_of(case, [p for p in paths if p.recording_id in zeros], zeros):
        if offer["date"] != date_iso or offer["key"] in declined:
            continue
        names = []
        for path in paths:
            if str(path.recording_id) in offer["recordings"]:
                names.append(path.wearer or path.unit or path.recording.title)
        out.append(
            {
                "key": offer["key"],
                "ids": offer["recordings"],
                "from": offer["from"],
                "to": offer["to"],
                "names": names,
                "words": offer["line"],
                "source": "from their paths",
                "together_metres": NEAR_METRES,
            }
        )
    del incidents
    return out


def _day_words(date: str) -> str:
    try:
        when = dt.date.fromisoformat(date)
    except ValueError:
        return date
    return f"{when:%d %b %Y}"


def _iso_day(text) -> str:
    """An incident's day as the chips compare it: the incident keeps its date
    as the camera's stamp wrote it (MM/DD/YYYY); the page speaks ISO."""
    text = str(text or "").strip()
    for shape in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(text, shape).date().isoformat()
        except ValueError:
            continue
    return ""


def _incident_spans(case) -> list[dict]:
    """The case's incidents with their cameras, for the map's scope and the
    day chips' marks; the spans as the chronology has them."""
    out = []
    for incident in case.incidents.all():
        out.append(
            {
                "id": str(incident.pk),
                "name": incident.name,
                "cameras": [str(one.recording_id) for one in incident.cameras.all()],
                "date": _iso_day(incident.clock_date),
                "url": incident.url(),
            }
        )
    return out


OFFER_SECONDS = 300


def offers_of(case, paths: list[CameraPath], zeros: dict) -> list[dict]:
    """The forming offer from the map (Phase 12 chapter 1, join 1): cameras
    that were within NEAR_METRES of each other for over OFFER_SECONDS and
    sit in no incident, one set each, for the Incidents tab's own Make it.
    Nothing is made without a press."""
    from core.incidents import IncidentCamera

    if not paths:
        return []
    placed = set(
        IncidentCamera.objects.filter(recording__case=case).values_list(
            "recording_id", flat=True
        )
    )
    loose = [one for one in paths if one.recording_id not in placed]
    pairs = [one for one in together(loose, zeros) if one[3] - one[2] >= OFFER_SECONDS]
    groups: list[dict] = []
    for a, b, start, end in pairs:
        home = None
        for group in groups:
            if a.recording_id in group["ids"] or b.recording_id in group["ids"]:
                home = group
                break
        if home is None:
            home = {"ids": [], "paths": {}, "from": start, "to": end}
            groups.append(home)
        for one in (a, b):
            if one.recording_id not in home["ids"]:
                home["ids"].append(one.recording_id)
                home["paths"][one.recording_id] = one
        home["from"] = min(home["from"], start)
        home["to"] = max(home["to"], end)
    out = []
    for group in groups:
        names = [
            group["paths"][one].unit or group["paths"][one].recording.title
            for one in group["ids"]
        ]
        minutes = int((group["to"] - group["from"]) // 60)
        first = zeros.get(group["ids"][0]) or {}
        out.append(
            {
                "recordings": [str(one) for one in group["ids"]],
                # The span as seconds of the day and the day (v1.197.0): the
                # strip's Suggested row and the map's circle read them.
                "from": round(group["from"], 1),
                "to": round(group["to"], 1),
                "date": first.get("date", ""),
                "key": "new:" + ",".join(sorted(str(one) for one in group["ids"])),
                "line": (
                    f"{', '.join(names[:-1])} and {names[-1]} were within "
                    f"{NEAR_METRES} m of each other for {minutes} minutes, "
                    f"{_hms(group['from'])} to {_hms(group['to'])}, "
                    "and are in no incident."
                ),
            }
        )
    return out


# The joins (Phase 12 chapter 1, Figure K): On the map from the rest of the case.


def ids_with_path(case) -> set:
    """The recordings of a case that have a path file, in one query, for the
    On the map links on hits, notes and chronology entries."""
    if not on():
        return set()
    return set(
        CameraPath.objects.filter(recording__case=case).values_list(
            "recording_id", flat=True
        )
    )


def map_url(case_id, recording_id, at: float) -> str:
    """The Map tab at a camera's moment, the camera selected."""
    from django.urls import reverse

    return (
        f"{reverse('case', args=[case_id])}?tab=map"
        f"&recording={recording_id}&at={float(at):.1f}"
    )


def map_url_at(with_path: set, recording, at: float) -> str:
    """The link, or "" for a recording without a path file."""
    if recording.pk not in with_path:
        return ""
    return map_url(recording.case_id, recording.pk, at)


def incidents_on_map(case, *, known_on: bool = False) -> set:
    """The incidents of a case with a camera that has a path file, in one
    query; `known_on` when the caller has read the setting already."""
    from core.incidents import IncidentCamera

    if not known_on and not on():
        return set()
    return set(
        IncidentCamera.objects.filter(
            incident__case=case, recording__camera_path__isnull=False
        ).values_list("incident_id", flat=True)
    )


def incident_map_url(incident, on_map: set | None = None) -> str:
    """On the map on an incident's row and page: the Map tab scoped to the
    incident's cameras and span, when any of them has a path file."""
    from django.urls import reverse

    if on_map is None:
        on_map = incidents_on_map(incident.case)
    if incident.pk not in on_map:
        return ""
    return f"{reverse('case', args=[incident.case_id])}?tab=map&incident={incident.pk}"


# Chapter 4: the wearer on the Speakers page, and where a line was said.


def wearers_of(case) -> list[dict]:
    """The names the case's path files give their wearers and drivers, one
    row per name, with the cameras it wore or drove, for the speaker picker:
    "Pat Doe, wore BWC2-1, from its path file". Never a position."""
    if not on():
        return []
    by_name: dict[str, dict] = {}
    for path in for_case(case):
        name = " ".join(path.wearer.split())
        if not name:
            continue
        camera = str((path.recording.stamp or {}).get("camera") or "").strip()
        camera = camera or path.recording.title
        row = by_name.setdefault(
            name.casefold(), {"name": name, "cameras": [], "units": []}
        )
        if path.source == CAR:
            if path.unit and path.unit not in row["units"]:
                row["units"].append(path.unit)
        elif camera not in row["cameras"]:
            row["cameras"].append(camera)
    out = []
    for row in by_name.values():
        words = []
        if row["cameras"]:
            words.append("wore " + ", ".join(row["cameras"]))
        if row["units"]:
            words.append("drove unit " + ", ".join(row["units"]))
        out.append(
            {"name": row["name"], "facts": "; ".join(words) + ", from its path file"}
        )
    out.sort(key=lambda one: one["name"].casefold())
    return out


def where_at(recording, t: float) -> dict:
    """Where this camera was at t seconds in, told without a position: whether
    it had a fix, and which of the case's other cameras with a path were how
    far from it at that moment, by their clocks. The street is the map's to
    say (the browser reads it from the basemap on the Map tab)."""
    from core import incidents

    path = of(recording)
    if path is None or not on():
        return {"has_path": False}
    t = max(0.0, float(t))
    zero = zero_of(recording, path)
    here = position_at(path, t)
    out = {
        "has_path": True,
        "fix": here is not None,
        "before_first": bool(path.fixes) and t < path.fixes[0][0],
        "no_position": not path.fixes,
        "when": (
            incidents.hms(zero["second"] + t)
            if zero and zero.get("second") is not None
            else incidents.elapsed(t) + " in"
        ),
        "near": [],
        "map_url": (
            map_url(recording.case_id, recording.pk, t) if recording.case_id else ""
        ),
    }
    if here is None or not zero or zero.get("second") is None or not recording.case_id:
        return out
    moment = zero["second"] + t
    for other in for_case(recording.case):
        if other.recording_id == recording.pk or not other.fixes:
            continue
        their_zero = zero_of(other.recording, other)
        if not their_zero or their_zero.get("second") is None:
            continue
        if their_zero["date"] != zero["date"]:
            continue
        there = position_at(other, moment - their_zero["second"])
        if there is None:
            continue
        out["near"].append(
            {
                "recording": str(other.recording_id),
                "title": other.recording.title,
                "unit": other.unit,
                "metres": int(round(metres_between(here, there))),
            }
        )
    out["near"].sort(key=lambda one: one["metres"])
    return out


def words(path: CameraPath | None) -> str:
    """The recording's line about its path file, for the Details and the
    Status page: "812 fixes over 38 minutes, in-car, clock from its file"."""
    if path is None:
        return ""
    kind = "in-car" if path.source == CAR else "body camera"
    out = f"{path.fix_count:,} fixes over {_minutes(path.length)}, {kind}"
    left_out = dropped_count(path)
    if left_out:
        out += f" ({left_out} left out as jumps)"
    if path.clock_start is not None:
        out += ", clock from its file"
    return out


def _most_cameras() -> int:
    """The Admin's Most cameras in an incident, read for the map's circle."""
    from core import incidents

    return incidents.most_cameras()
