"""The case's chronology (Phase 10 chapter 1, ADR 0027): the Case's notes on
one clock without an Incident.

A note's time of day is its Recording's clock plus the note's moment. The
clock is kept on the Recording: read from the camera's stamp ("clock"),
placed by a person on this page by a drag or a typed time ("hand"), by the
day alone ("day"), or from the time the file carries ("file", unchecked); a
stamp read later takes over. Nothing here invents a time.

The page is one day at a time under the Date strip. Each day: the unplaced
rail (recordings with notes and no clock), the ruler fitted to the day's
notes, the band in one of three shapes the day's recordings choose (lanes in
colour, packed lanes, the Coverage lane), the Notes lane's marks, the hints
where videos overlap under a cluster of marks, and the Spells of entries.
Everything is read once, in a handful of queries, from the same reading the
Notes page keeps (notes_page.note_rows_of), with the clock added per
recording. The exports are the incident's two, a Word document with a still
per entry and a spreadsheet.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path

from django.utils import timezone

from core import audit, exports, incidents, prompts, settings_store
from core.chronology import FIGURE_COLOURS, spells

CLOCK, HAND, DAY, FILE = "clock", "hand", "day", "file"
HOW_WORDS = {CLOCK: "clock", HAND: "by hand", DAY: "by the day", FILE: "from the file"}
# The band's shapes, chosen by the day's recordings (never the person).
LANES, PACKED, COVERAGE = "lanes", "packed", "coverage"
# Up to this many overlapping, lanes in colour; more overlapping, the
# Coverage lane; more recordings but spread, packed lanes up to this many.
LANES_MOST = 6
# Bars under the Coverage lane: the most noted (the maintainer, 2026-10-28).
BARS_MOST = 8
# The spells of a day open folded past this many notes.
FOLD_NOTES = 40
# Chips on the rail before "and N more".
RAIL_MOST = 5
DAY_SECONDS = 86400.0
# The Coverage lane's samples across the span in view.
COVERAGE_SAMPLES = 240
# Entries, bars and stills the exports print at most.
STILL_WIDTH_INCHES = 2.4
MOST_WORDS = 6
MUTED = (0x5B, 0x66, 0x73)


# The Recording's clock -----------------------------------------------------------


def stamp_date(recording) -> dt.date | None:
    text = ((recording.stamp or {}).get("date") or "").strip()
    for form in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"):
        try:
            return dt.datetime.strptime(text, form).date()
        except ValueError:
            continue
    return None


def clock_of(recording) -> tuple[dt.date | None, float | None, str]:
    """The Recording's clock as the page reads it: the stamp first (it wins),
    else what a person placed. (date, the second of the day, how); the second
    is None for a day placed alone, and the how is "" for no clock at all."""
    zero = incidents.clock_zero_of(recording)
    if zero is not None:
        date = stamp_date(recording)
        if date is not None:
            return date, float(zero), CLOCK
    if recording.clock_date is not None and recording.clock_how in (HAND, DAY, FILE):
        return recording.clock_date, recording.clock_start, recording.clock_how
    return None, None, ""


def placed_words(recording) -> str:
    """The pill: "clock", "clock, unchecked", "by hand, D. Meehan", ..."""
    _date, _start, how = clock_of(recording)
    if how == CLOCK:
        return "clock" if incidents.stamp_checked(recording) else "clock, unchecked"
    if not how:
        return ""
    who = recording.clock_by.shown_name if recording.clock_by_id else ""
    return HOW_WORDS[how] + (f", {who}" if who else "")


def file_suggestion(recording) -> dict | None:
    """The time the file carries, offered in the place box as a start the
    person may take ("file", unchecked); the incident's own offer."""
    words, seconds = incidents.file_time_of(recording)
    if seconds is None:
        return None
    return {"words": words, "seconds": seconds}


def place(
    recording, date: dt.date, start: float | None, *, by, request=None, how: str = ""
):
    """A person's placement: by hand (a time), by the day alone, or from the
    file's time. Refused when the stamp already gives the clock."""
    if incidents.clock_zero_of(recording) is not None and stamp_date(recording):
        raise ValueError("the camera's clock was read from the picture and stands")
    if how not in (HAND, DAY, FILE):
        how = DAY if start is None else HAND
    if how == DAY:
        start = None
    recording.clock_date = date
    recording.clock_start = None if start is None else float(start) % DAY_SECONDS
    recording.clock_how = how
    recording.clock_by = by
    recording.clock_at = timezone.now()
    recording.save(
        update_fields=["clock_date", "clock_start", "clock_how", "clock_by", "clock_at"]
    )
    audit.write(
        audit.Category.RECORDINGS,
        "recording placed on the clock",
        actor=by,
        request=request,
        affected_user=recording.user,
        object_type="recording",
        object_id=str(recording.pk),
        object_label=recording.title,
        how=how,
        case=str(recording.case_id) if recording.case_id else "",
    )


def unplace(recording, *, by, request=None) -> bool:
    if not recording.clock_how:
        return False
    recording.clock_date = None
    recording.clock_start = None
    recording.clock_how = ""
    recording.clock_by = None
    recording.clock_at = None
    recording.save(
        update_fields=["clock_date", "clock_start", "clock_how", "clock_by", "clock_at"]
    )
    audit.write(
        audit.Category.RECORDINGS,
        "recording taken off the clock",
        actor=by,
        request=request,
        affected_user=recording.user,
        object_type="recording",
        object_id=str(recording.pk),
        object_label=recording.title,
        case=str(recording.case_id) if recording.case_id else "",
    )
    return True


# The reading ----------------------------------------------------------------------


def hms(seconds: float) -> str:
    seconds = int(round(seconds)) % int(DAY_SECONDS)
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def hm(seconds: float) -> str:
    return hms(seconds)[:5]


def day_words(date: dt.date) -> str:
    return date.strftime("%d %b %Y").lstrip("0")


def _noted(case, rows: list[dict] | None = None):
    """The case's recordings and every note on them, once; or the rows given
    in the notes' shape (the proposals, chapter 4), laid out the same way."""
    from core.notes_page import note_rows_of

    recordings = list(
        case.recordings.select_related("clock_by").order_by("created", "title")
    )
    if rows is None:
        rows = note_rows_of(case, recordings)
    by_recording: dict = defaultdict(list)
    for row in rows:
        by_recording[row["recording"]].append(row)
    return recordings, by_recording


def _placements(recordings) -> dict:
    """Each recording's clock, read once."""
    return {str(one.pk): clock_of(one) for one in recordings}


def days_of(case, rows: list[dict] | None = None) -> list[dict]:
    """The Date strip: each day that has notes on a placed recording, with
    its counts; a recording that runs past midnight counts on both days."""
    recordings, by_recording = _noted(case, rows)
    placements = _placements(recordings)
    counts: dict = defaultdict(lambda: {"notes": 0, "recordings": set()})
    for one in recordings:
        key = str(one.pk)
        date, start, how = placements[key]
        if date is None or not by_recording.get(key):
            continue
        for note in by_recording[key]:
            when = date
            if start is not None and start + note["at"] >= DAY_SECONDS:
                when = date + dt.timedelta(days=1)
            counts[when]["notes"] += 1
            counts[when]["recordings"].add(key)
    return [
        {
            "date": when.isoformat(),
            "words": day_words(when),
            "month": when.strftime("%b %Y"),
            "notes": here["notes"],
            "recordings": len(here["recordings"]),
        }
        for when, here in sorted(counts.items())
    ]


def rail_of(case, rows: list[dict] | None = None) -> dict:
    """The rail on its own (v1.170.1): every recording with a note (or a row
    given, chapter 4) and no clock, so the first placing can happen before
    any day exists. The same rows the day's reading puts on its rail."""
    recordings, by_recording = _noted(case, rows)
    placements = _placements(recordings)
    rail = []
    for one in recordings:
        key = str(one.pk)
        if placements[key][0] is not None or not by_recording.get(key):
            continue
        rail.append(
            {
                "id": key,
                "title": exports.title_of(one),
                "notes": len(by_recording[key]),
                "file": file_suggestion(one),
                "video": incidents.is_video(one),
            }
        )
    return {
        "rail": rail[:RAIL_MOST],
        "rail_more": max(0, len(rail) - RAIL_MOST),
        "rail_all": rail,
    }


def _running(one, date, start, placements_date, span) -> tuple[float, float] | None:
    """The seconds of `date` a placed recording runs across, clipped to the
    day; None when it does not touch the day."""
    length = float(one.duration_seconds or 0.0)
    if start is None:
        return None
    if placements_date == date:
        a, b = start, min(start + length, DAY_SECONDS)
    elif (
        placements_date == date - dt.timedelta(days=1) and start + length > DAY_SECONDS
    ):
        a, b = 0.0, start + length - DAY_SECONDS
    else:
        return None
    if span is not None:
        a, b = max(a, span[0]), min(b, span[1])
        if b <= a:
            return None
    return a, b


def day_of(
    case,
    date: dt.date,
    span: tuple[float, float] | None = None,
    rows: list[dict] | None = None,
) -> dict:
    """Everything the page draws for one day (and a span of it): the rail,
    the ruler, the band in its shape, the marks, the hints and the spells.
    Given rows in the notes' shape, it lays those out instead (chapter 4)."""
    recordings, by_recording = _noted(case, rows)
    placements = _placements(recordings)
    colours: dict = {}
    bars: list[dict] = []
    entries: list[dict] = []
    unknown: list[dict] = []
    rail: list[dict] = []
    for one in recordings:
        key = str(one.pk)
        p_date, p_start, how = placements[key]
        its_notes = by_recording.get(key, [])
        if p_date is None:
            if its_notes:
                rail.append(
                    {
                        "id": key,
                        "title": exports.title_of(one),
                        "notes": len(its_notes),
                        "file": file_suggestion(one),
                        "video": incidents.is_video(one),
                    }
                )
            continue
        if how == DAY:
            if p_date == date and its_notes and span is None:
                for note in its_notes:
                    unknown.append(_entry(note, one, None, "", how))
            continue
        running = _running(one, date, p_start, p_date, span)
        if running is None:
            continue
        colour = colours.setdefault(
            key, FIGURE_COLOURS[len(colours) % len(FIGURE_COLOURS)]
        )
        count = 0
        for note in its_notes:
            when = p_start + note["at"]
            if p_date == date - dt.timedelta(days=1):
                when -= DAY_SECONDS
            if when < 0 or when >= DAY_SECONDS:
                continue
            if span is not None and not (span[0] <= when <= span[1]):
                continue
            entries.append(_entry(note, one, when, colour, how))
            count += 1
        bars.append(
            {
                "id": key,
                "title": exports.title_of(one),
                # The camera's id from its stamp, the bar's short name
                # (v1.164.1); empty for a recording with none.
                "camera": str((one.stamp or {}).get("camera") or "")[:24],
                "from": round(running[0], 1),
                "to": round(running[1], 1),
                "notes": count,
                "colour": colour,
                "placed": placed_words(one),
                "how": how,
                "video": incidents.is_video(one),
                "movable": how in (HAND, FILE),
            }
        )
    entries.sort(key=lambda row: (row["seconds"], row["recording"]))
    for number, row in enumerate(entries, start=1):
        row["number"] = number
    for number, row in enumerate(unknown, start=len(entries) + 1):
        row["number"] = number
    first = min((row["seconds"] for row in entries), default=None)
    last = max((row["seconds"] for row in entries), default=None)
    if span is not None:
        ruler = {"from": span[0], "to": span[1]}
    elif first is not None:
        pad = max(300.0, (last - first) * 0.05)
        ruler = {"from": max(0.0, first - pad), "to": min(DAY_SECONDS, last + pad)}
    elif bars:
        ruler = {"from": min(b["from"] for b in bars), "to": max(b["to"] for b in bars)}
    else:
        ruler = {"from": 0.0, "to": DAY_SECONDS}
    if ruler["to"] - ruler["from"] < 600:
        ruler["to"] = min(DAY_SECONDS, ruler["from"] + 600)
    shape, lanes, folded, coverage = _band(bars, ruler)
    hints = _hints(bars, entries)
    # The case's incidents on the day (chapter 2), and each entry's place
    # against them: an event of one, or inside one on a camera not in it.
    on_day = _incidents_on_day(case, date, span, placements)
    for row in entries:
        _place_in_incidents(row, on_day)
    groups = spells(entries)
    return {
        "date": date.isoformat(),
        "words": day_words(date),
        "span": span is not None,
        "ruler": ruler,
        "rail": rail[:RAIL_MOST],
        "rail_more": max(0, len(rail) - RAIL_MOST),
        "rail_all": rail,
        "shape": shape,
        "lanes": lanes,
        "bars": bars,
        "folded": folded,
        "coverage": coverage,
        "marks": [
            {"n": row["number"], "seconds": row["seconds"], "colour": row["colour"]}
            for row in entries
        ],
        "hints": hints,
        "incidents": on_day,
        "incidents_on": incidents.on(),
        "spells": [
            {
                "from": group[0]["time"],
                "to": group[-1]["time"],
                "notes": len(group),
                "recordings": len({row["recording"] for row in group}),
                "entries": group,
            }
            for group in groups
        ],
        "fold": len(entries) > FOLD_NOTES,
        "unknown": unknown,
        "count": len(entries) + len(unknown),
        "recordings": len({row["recording"] for row in entries}),
    }


def _entry(note: dict, recording, when: float | None, colour: str, how: str) -> dict:
    return {
        "key": note["key"],
        "kind": note["kind"],
        "id": note["id"],
        "recording": str(recording.pk),
        "title": exports.title_of(recording),
        "video": incidents.is_video(recording),
        "at": note["at"],
        "seconds": when if when is not None else -1.0,
        "time": hms(when) if when is not None else "",
        "text": note["text"],
        "said": note.get("said", ""),
        "who": prompts.plain_speaker(note.get("who", "")) if note.get("who") else "",
        "by": note.get("by", ""),
        "by_id": note.get("by_id"),
        "when": note.get("when", ""),
        "colour": colour,
        "how": how,
        "to_check": bool(note.get("to_check")),
        "event_time": note.get("event_time", ""),
        # A proposal's own fields (chapter 4), carried as given.
        **{
            key: note[key]
            for key in (
                "why",
                "source",
                "source_words",
                "state",
                "became",
                "note_url",
                "for_incident",
            )
            if key in note
        },
    }


# The Proposed events tab (chapter 4, the second release, v1.169.0) ---------------


def proposed_day_of(case, date: dt.date | None, span=None) -> dict:
    """The tab's reading: the proposals of the case laid out as the notes
    are, the day's notes as a second lane of marks, and the proposals on
    recordings not yet placed, listed under Not yet placed by their own
    times. With no day given, the latest day that has one."""
    from core import proposals

    rows = proposals.day_rows(case)
    days = days_of(case, rows)
    if date is None and days:
        date = dt.date.fromisoformat(days[-1]["date"])
    day = day_of(case, date, span, rows=rows) if date is not None else None
    if day is not None:
        notes_day = day_of(case, date, span)
        day["notes_marks"] = notes_day["marks"]
        day["hints"] = []
        day["rail"] = []
        day["rail_more"] = 0
        day["rail_all"] = []
    recordings, by_recording = _noted(case, rows)
    placements = _placements(recordings)
    unplaced = []
    for one in recordings:
        key = str(one.pk)
        if placements[key][0] is not None:
            continue
        for row in sorted(by_recording.get(key, []), key=lambda r: r["at"]):
            unplaced.append(_entry(row, one, None, "", "none"))
    for number, row in enumerate(unplaced, start=1):
        row["number"] = number
        row["time"] = hms(row["at"])
    return {
        "days": days,
        "day": day,
        "unplaced": unplaced,
        "run": proposals.run_json(case),
        # The recordings with proposals and no clock, to place from here
        # (v1.170.1).
        **rail_of(case, rows),
    }


def _band(bars: list[dict], ruler: dict) -> tuple[str, list, list, list]:
    """The band's shape from the recordings running in the span, the lanes
    for the packed shape, the folded bars, and the Coverage lane's samples."""
    if not bars:
        return LANES, [], [], []
    overlap = _most_overlapping(bars)
    if len(bars) <= LANES_MOST:
        for lane, bar in enumerate(bars):
            bar["lane"] = lane
        return LANES, list(range(len(bars))), [], []
    if overlap <= LANES_MOST:
        ends: list[float] = []
        folded: list[dict] = []
        for bar in sorted(bars, key=lambda b: (b["from"], b["to"])):
            lane = next((i for i, end in enumerate(ends) if end <= bar["from"]), None)
            if lane is None:
                if len(ends) >= LANES_MOST:
                    bar["lane"] = None
                    folded.append(bar)
                    continue
                ends.append(bar["to"])
                lane = len(ends) - 1
            else:
                ends[lane] = bar["to"]
            bar["lane"] = lane
        return PACKED, list(range(len(ends))), folded, []
    shown = sorted(bars, key=lambda b: (-b["notes"], b["from"]))
    for bar in bars:
        bar["lane"] = None
    for lane, bar in enumerate(shown[:BARS_MOST]):
        bar["lane"] = lane
    folded = [bar for bar in shown[BARS_MOST:]]
    width = max(1.0, ruler["to"] - ruler["from"])
    samples = []
    for i in range(COVERAGE_SAMPLES + 1):
        at = ruler["from"] + width * i / COVERAGE_SAMPLES
        samples.append(sum(1 for b in bars if b["from"] <= at <= b["to"]))
    return COVERAGE, list(range(min(BARS_MOST, len(shown)))), folded, samples


def _most_overlapping(bars: list[dict]) -> int:
    edges = sorted(
        [(b["from"], 1) for b in bars] + [(b["to"], -1) for b in bars],
        key=lambda e: (e[0], e[1]),
    )
    most = running = 0
    for _at, step in edges:
        running += step
        most = max(most, running)
    return most


def _hints(bars: list[dict], entries: list[dict]) -> list[dict]:
    """Wherever two or more videos overlap with marks under them: the
    bracket's span and counts. Overlapping videos are merged into runs."""
    videos = sorted((b for b in bars if b["video"]), key=lambda b: b["from"])
    runs: list[dict] = []
    for bar in videos:
        if runs and bar["from"] <= runs[-1]["to"]:
            runs[-1]["to"] = max(runs[-1]["to"], bar["to"])
            runs[-1]["ids"].add(bar["id"])
        else:
            runs.append({"from": bar["from"], "to": bar["to"], "ids": {bar["id"]}})
    out = []
    for run in runs:
        if len(run["ids"]) < 2:
            continue
        count = sum(1 for row in entries if run["from"] <= row["seconds"] <= run["to"])
        if not count:
            continue
        out.append(
            {
                "from": run["from"],
                "to": run["to"],
                "cameras": len(run["ids"]),
                "notes": count,
                "words": (
                    f"{len(run['ids'])} cameras, {count} "
                    f"note{'' if count == 1 else 's'}, "
                    f"{hm(run['from'])} to {hm(run['to'])}"
                ),
            }
        )
    return out


# An incident from a span (Phase 10 chapter 2, v1.167.0) ----------------------


def _incidents_on_day(case, date: dt.date, span, placements: dict) -> list[dict]:
    """The case's incidents on this day: each one's span on the day from its
    cameras as the case's clock reads them, so the lane and the bars agree.
    An incident with no camera on the day is not drawn; with a span in hand,
    only the incidents the span touches."""
    if not incidents.on():
        return []
    out = []
    for incident in case.incidents.prefetch_related("cameras__recording"):
        low = high = None
        ids = []
        placed_ids = []
        for camera in incident.cameras.all():
            key = str(camera.recording_id)
            ids.append(key)
            if camera.is_placed():
                placed_ids.append(key)
            p_date, p_start, how = placements.get(key) or clock_of(camera.recording)
            if p_date is None or how == DAY:
                continue
            running = _running(camera.recording, date, p_start, p_date, None)
            if running is None:
                continue
            low = running[0] if low is None else min(low, running[0])
            high = running[1] if high is None else max(high, running[1])
        if low is None:
            continue
        if span is not None and (high < span[0] or low > span[1]):
            continue
        events = incident.events.filter(proposed=False).count()
        out.append(
            {
                "id": str(incident.pk),
                "name": incident.name,
                "url": incident.url(),
                "from": round(low, 1),
                "to": round(high, 1),
                "cameras": len(ids),
                "camera_ids": ids,
                "placed_ids": placed_ids,
                "events": events,
                "words": (
                    f"{incident.name} · {len(ids)} camera{'' if len(ids) == 1 else 's'}"
                    f" · {events} event{'' if events == 1 else 's'}"
                ),
            }
        )
    return out


def _place_in_incidents(row: dict, on_day: list[dict]) -> None:
    """The entry's incident: the one its recording is a camera of (its note
    is an event of it, Phase 8 chapter 11); else, when its moment lies in an
    incident's span on a camera not in it, that incident as `outside`."""
    for one in on_day:
        if row["recording"] in one["camera_ids"]:
            # An event of it once the camera is on the incident's clock.
            row["incident"] = {
                "id": one["id"],
                "name": one["name"],
                "event": row["recording"] in one["placed_ids"],
            }
            return
    for one in on_day:
        if one["from"] <= row["seconds"] <= one["to"]:
            row["outside"] = {
                "id": one["id"],
                "name": one["name"],
                "from": hm(one["from"]),
                "to": hm(one["to"]),
            }
            return


def _span_dict(date: dt.date, span) -> dict:
    return {"date": date.isoformat(), "from": hm(span[0]), "to": hm(span[1])}


def span_words(kept: dict | None) -> str:
    """ "6 Nov 2025, 20:24 to 20:40" from a kept span, or nothing."""
    if not kept:
        return ""
    when = day_words(dt.date.fromisoformat(kept["date"]))
    return f"{when}, {kept['from']} to {kept['to']}"


def span_reading(case, date: dt.date, span) -> dict:
    """What the Make an incident sheet needs for a span: the recordings that
    ran in it with their notes, the eight most noted ticked, the incidents
    the span touches (the one holding more of it first) with which of the
    recordings are already in them and the span each would widen to, the
    cap, and a name to offer."""
    reading = day_of(case, date, span)
    bars = sorted(reading["bars"], key=lambda b: (-b["notes"], b["from"]))
    rows = [
        {
            "id": bar["id"],
            "title": bar["title"],
            "notes": bar["notes"],
            "placed": bar["placed"],
            "how": bar["how"],
            "video": bar["video"],
            "from": hm(bar["from"]),
            "to": hm(bar["to"]),
            "ticked": bar["notes"] > 0 and index < BARS_MOST,
        }
        for index, bar in enumerate(bars)
    ]
    touched = []
    for one in reading["incidents"]:
        # Judged to the minute, as the spans are said and kept: a span that
        # reads the same minutes as the incident's is inside it.
        union = (min(one["from"], span[0]), max(one["to"], span[1]))
        held = min(one["to"], span[1]) - max(one["from"], span[0])
        inside = hm(one["from"]) <= hm(span[0]) and hm(span[1]) <= hm(one["to"])
        widens = (hm(union[0]), hm(union[1])) != (hm(one["from"]), hm(one["to"]))
        touched.append(
            {
                "id": one["id"],
                "name": one["name"],
                "url": one["url"],
                "from": hm(one["from"]),
                "to": hm(one["to"]),
                "cameras": one["cameras"],
                "camera_ids": one["camera_ids"],
                "inside": inside,
                "widens": widens,
                "union_from": hm(union[0]),
                "union_to": hm(union[1]),
                "in_ids": [row["id"] for row in rows if row["id"] in one["camera_ids"]],
                "held": held,
            }
        )
    touched.sort(key=lambda one: -one["held"])
    return {
        "date": date.isoformat(),
        "words": day_words(date),
        "from": hm(span[0]),
        "to": hm(span[1]),
        "rows": rows,
        "incidents": touched,
        "most": incidents.most_cameras(),
        "name": f"{day_words(date)}, {hm(span[0])} to {hm(span[1])}",
    }


def _carry_places(incident, date: dt.date, *, by) -> None:
    """A camera placed by hand or from the file on the case's clock arrives
    on the incident's clock at the same start, under the same person's name
    (one with a read stamp was placed from it by make). With no stamp among
    the cameras, the first carried one sets the incident's clock to the day."""
    for camera in incident.cameras.select_related("recording", "recording__clock_by"):
        p_date, p_start, how = clock_of(camera.recording)
        if how not in (HAND, FILE) or p_start is None or p_date is None:
            continue
        if camera.placed in (incidents.CLOCK, incidents.CLOCK_UNCHECKED):
            continue
        if incident.clock_zero is None:
            incident.clock_zero = float(p_start)
            incident.clock_date = p_date.strftime("%m/%d/%Y")
            incident.clock_checked = True
            incident.save(update_fields=["clock_zero", "clock_date", "clock_checked"])
        starts_at = incidents._wrapped(float(p_start) - incident.clock_zero)
        incidents._placed(
            camera,
            incidents.HAND if how == HAND else incidents.FILE,
            starts_at,
            by=camera.recording.clock_by or by,
            request=None,
            quietly=True,
        )


def make_incident(
    case, date: dt.date, span, name: str, recordings, *, by, request=None
):
    """An incident from the span: made with these recordings, each carried
    onto the incident's clock as the case's clock has it, and told where it
    came from."""
    kept = _span_dict(date, span)
    incident = incidents.make(
        case,
        name,
        recordings,
        by=by,
        how=incidents.FROM_CHRONOLOGY,
        request=request,
        details={"day": kept["date"], "span": f"{kept['from']} to {kept['to']}"},
    )
    _carry_places(incident, date, by=by)
    incident.from_chronology = {"made": kept, "span": dict(kept), "changes": []}
    incident.save(update_fields=["from_chronology"])
    return incident


def add_to_incident(
    incident, date: dt.date, span, recordings, *, by, request=None
) -> int:
    """Recordings of a span added to an incident the span touches, the
    incident widened to cover both; one audit row with the spans and the
    count, never a note's words."""
    added = incidents.add_cameras(incident, recordings, by=by, request=request)
    _carry_places(incident, date, by=by)
    kept = dict(incident.from_chronology or {})
    was = kept.get("span")
    now = _span_dict(date, span)
    if was and was["date"] == now["date"]:
        now = {
            "date": now["date"],
            "from": min(was["from"], now["from"]),
            "to": max(was["to"], now["to"]),
        }
    widened = was is None or now != was
    kept["span"] = now
    kept.setdefault("changes", []).append(
        {
            "by": by.shown_name,
            "at": timezone.now().isoformat(),
            "span": f"{now['from']} to {now['to']}",
            "added": added,
            "widened": widened,
        }
    )
    incident.from_chronology = kept
    incident.save(update_fields=["from_chronology"])
    audit.write(
        incidents.CATEGORY,
        "incident widened from the chronology",
        actor=by,
        affected_user=incident.case.owner,
        object_type="incident",
        object_id=incident.pk,
        object_label=incident.name,
        request=request,
        case=incident.case.name,
        was=f"{was['from']} to {was['to']}" if was else "",
        now=f"{now['from']} to {now['to']}",
        cameras=added,
    )
    return added


def running_at(case, date: dt.date, at: float) -> list[dict]:
    """The recordings running at a moment of the day, the noted ones first:
    the Coverage lane's press."""
    recordings, by_recording = _noted(case)
    placements = _placements(recordings)
    out = []
    for one in recordings:
        key = str(one.pk)
        p_date, p_start, how = placements[key]
        if p_date is None or how == DAY:
            continue
        running = _running(one, date, p_start, p_date, None)
        if running is None or not (running[0] <= at <= running[1]):
            continue
        out.append(
            {
                "id": key,
                "title": exports.title_of(one),
                "notes": len(by_recording.get(key, [])),
                "placed": placed_words(one),
                "into": round(
                    at - (p_start if p_date == date else p_start - DAY_SECONDS), 1
                ),
            }
        )
    out.sort(key=lambda row: (-row["notes"], row["title"]))
    return out


# To check ---------------------------------------------------------------------------


def set_to_check(kind: str, note_id, wanted: bool) -> bool:
    """The mark on a line's note or a moment's note."""
    from core.jobs import Segment
    from core.notes import MomentNote

    model = Segment if kind == "line" else MomentNote if kind == "moment" else None
    if model is None:
        return False
    return bool(model.objects.filter(pk=note_id).update(note_to_check=wanted))


# The exports --------------------------------------------------------------------------


def export_name(case, date: dt.date | None, ending: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in case.name)
    when = f" {date.isoformat()}" if date else ""
    return f"Chronology - {safe.strip() or 'case'}{when}.{ending}"


def _days_for_export(case, date: dt.date | None) -> list[dt.date]:
    if date is not None:
        return [date]
    return [dt.date.fromisoformat(one["date"]) for one in days_of(case)]


def spreadsheet(case, date: dt.date | None) -> bytes:
    holder = io.StringIO()
    writer = csv.writer(holder)
    writer.writerow(
        [
            "Date",
            "Time of day",
            "Recording",
            "Placed",
            "Note",
            "Line",
            "Writer",
            "Written on",
            "To check",
        ]
    )
    for when in _days_for_export(case, date):
        day = day_of(case, when)
        for group in day["spells"]:
            for row in group["entries"]:
                writer.writerow(_sheet_row(when, row))
        for row in day["unknown"]:
            writer.writerow(_sheet_row(when, row))
    return holder.getvalue().encode("utf-8-sig")


def _sheet_row(when: dt.date, row: dict) -> list:
    return [
        when.isoformat(),
        row["time"] or "time unknown",
        row["title"],
        HOW_WORDS.get(row["how"], ""),
        row["text"],
        (f"{row['who']}: " if row["who"] else "") + (row["said"] or ""),
        row["by"],
        row["when"],
        "to check" if row["to_check"] else "",
    ]


def word(case, date: dt.date | None, exported_by: str) -> bytes:
    """Chronology to Word: the Timeline report's shape for the case's
    chronology, a still per entry on a video, the words heard around it."""
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Inches, Pt, RGBColor

    from core import media

    height = int(settings_store.get("incidents_report_still_height") or 360)
    most_stills = int(settings_store.get("incidents_report_stills_most") or 0)
    window = int(settings_store.get("incidents_report_words_seconds") or 0)
    stills_on = (
        bool(settings_store.get("incidents_report_stills"))
        if _has("incidents_report_stills")
        else True
    )
    days = _days_for_export(case, date)
    document = exports._open_record_document()
    exports._office_head(document)
    heading = document.add_paragraph(f"Chronology: {case.name}")
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    heading.runs[0].bold = True
    heading.runs[0].font.size = Pt(20)
    said = document.add_paragraph(
        "The office's notes on the recordings' own clocks"
        + (f", {day_words(days[0])}" if len(days) == 1 else f", {len(days)} days")
    )
    said.alignment = WD_ALIGN_PARAGRAPH.CENTER
    said.runs[0].font.size = Pt(13)
    document.add_paragraph()
    total = 0
    day_readings = [(when, day_of(case, when)) for when in days]
    for _when, day in day_readings:
        total += day["count"]
    exports._facts(
        document,
        [
            ("Case", case.name),
            ("Days", ", ".join(day_words(when) for when in days) if days else "none"),
            ("Notes", str(total)),
            (
                "Made from",
                "the case's chronology as it stood at "
                f"{timezone.localtime():{exports.DAY_AND_TIME}}",
            ),
            (
                "Exported",
                f"{dt.datetime.now():{exports.DAY_AND_TIME}} by {exported_by}",
            ),
        ],
        Inches,
    )
    document.add_paragraph()
    how = document.add_paragraph()
    how_run = how.add_run(
        "Each entry is one note of the case: its number, its time of day on the "
        "recording's clock and the recording it was written on; the still is that "
        "recording's picture at the moment; the words are what was heard around "
        "it. Entries run in time order in spells, a new spell wherever ten minutes "
        "or more pass without one. A recording placed by hand or by the day says so."
    )
    how_run.italic = True
    how_run.font.size = Pt(9)
    how_run.font.color.rgb = RGBColor(*MUTED)
    recordings = {str(one.pk): one for one in case.recordings.all()}
    folder = Path(tempfile.mkdtemp(prefix="case-chronology-"))
    stills_cut = 0
    try:
        for when, day in day_readings:
            document.add_paragraph()
            head = document.add_paragraph(day_words(when))
            head.runs[0].bold = True
            head.runs[0].font.size = Pt(14)
            table = document.add_table(rows=1, cols=4)
            table.style = "Light Grid Accent 1"
            for cell, title in zip(
                table.rows[0].cells,
                ("Recording", "Placed", "Starts", "Ends"),
                strict=True,
            ):
                cell.text = title
            for bar in sorted(day["bars"], key=lambda b: b["from"]):
                cells = table.add_row().cells
                cells[0].text = bar["title"]
                cells[1].text = bar["placed"]
                cells[2].text = hms(bar["from"])
                cells[3].text = hms(bar["to"])
            document.add_paragraph()
            groups = [group["entries"] for group in day["spells"]]
            if day["unknown"]:
                groups.append(day["unknown"])
            for group in groups:
                first, last = group[0], group[-1]
                if first["time"]:
                    title = (
                        f"{first['time']} to {last['time']}"
                        if len(group) > 1
                        else first["time"]
                    )
                else:
                    title = f"Time unknown on {day_words(when)}"
                spell = document.add_paragraph()
                spell_run = spell.add_run(f"{title}   ")
                spell_run.bold = True
                spell_run.font.name = "Consolas"
                count_run = spell.add_run(
                    f"{len(group)} note{'' if len(group) == 1 else 's'}"
                )
                count_run.font.color.rgb = RGBColor(*MUTED)
                for row in group:
                    recording = recordings.get(row["recording"])
                    still = None
                    if (
                        recording is not None
                        and row["video"]
                        and stills_on
                        and stills_cut < most_stills
                    ):
                        still = _still(
                            media, recording, row["at"], folder, height, stills_cut
                        )
                        if still is not None:
                            stills_cut += 1
                    _entry_block(
                        document, row, recording, still, window, Inches, Pt, RGBColor
                    )
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    document.add_paragraph()
    line = document.add_paragraph(
        "A still is one frame of the recording's playback copy at the note's "
        "moment, cut for this document. The words quoted are the transcript's, as "
        "it labels the speakers. Every time is the recording's own clock: read from "
        "the picture, or placed by a person as the entry says."
    )
    line.runs[0].italic = True
    line.runs[0].font.size = Pt(9)
    exports.stamp_pages(document, case.name, "Chronology", case.name)
    holder = io.BytesIO()
    document.save(holder)
    return holder.getvalue()


def _has(key: str) -> bool:
    try:
        settings_store.definition(key)
    except KeyError:
        return False
    return True


def _still(media, recording, at: float, folder: Path, height: int, index: int):
    source = recording.playback_path()
    if source is None or not Path(source).exists() or Path(source).suffix != ".mp4":
        return None
    target = folder / f"still-{index}"
    target.mkdir(parents=True, exist_ok=True)
    try:
        written = media.grab_frames(Path(source), target, [float(at)], height=height)
    except Exception:  # noqa: BLE001 - a still is never worth failing the export
        return None
    return written[0] if written else None


def _words_near(recording, at: float, window: int) -> list[str]:
    if window <= 0 or recording is None:
        return []
    transcript = getattr(recording, "transcript", None)
    if transcript is None:
        return []
    near = []
    for line in prompts.lines_of(transcript):
        if abs(line.start - at) <= window:
            near.append((abs(line.start - at), line.start, line))
    near.sort(key=lambda one: one[0])
    out = []
    for _, _start, line in sorted(near[:MOST_WORDS], key=lambda one: one[1]):
        label = prompts.plain_speaker(line.speaker)
        out.append(
            f"{exports.clock(line.start)}  {label + ': ' if label else ''}{line.text}"
        )
    return out


def _entry_block(document, row, recording, still, window, Inches, Pt, RGBColor) -> None:
    import contextlib

    table = document.add_table(rows=1, cols=2 if still else 1)
    table.autofit = False
    cells = table.rows[0].cells
    if still:
        cells[0].width = Inches(STILL_WIDTH_INCHES + 0.1)
        picture = cells[0].paragraphs[0]
        with contextlib.suppress(Exception):
            picture.add_run().add_picture(str(still), width=Inches(STILL_WIDTH_INCHES))
        caption = cells[0].add_paragraph()
        caption_run = caption.add_run(
            f"{row['title']} at {row['time'] or exports.clock(row['at'])}"
        )
        caption_run.font.size = Pt(8)
        caption_run.font.color.rgb = RGBColor(*MUTED)
        text = cells[1]
        text.width = Inches(6.5 - STILL_WIDTH_INCHES - 0.1)
    else:
        cells[0].width = Inches(6.5)
        text = cells[0]
    head = text.paragraphs[0]
    number = head.add_run(f"{row['number']}  ")
    number.bold = True
    if row["colour"]:
        number.font.color.rgb = RGBColor.from_string(row["colour"].lstrip("#"))
    when = head.add_run(row["time"] or "time unknown")
    when.font.name = "Consolas"
    when.font.size = Pt(10)
    where = head.add_run(
        f"   {row['title']}"
        + (f" · {HOW_WORDS[row['how']]}" if row["how"] in (HAND, DAY, FILE) else "")
    )
    where.font.size = Pt(9)
    where.font.color.rgb = RGBColor(*MUTED)
    line = text.add_paragraph()
    words = line.add_run(row["text"])
    words.bold = True
    if row["said"]:
        said = text.add_paragraph()
        said_run = said.add_run(
            f"{row['who'] + ': ' if row['who'] else ''}{row['said']}"
        )
        said_run.font.size = Pt(9)
        said_run.font.color.rgb = RGBColor(*MUTED)
    for heard in _words_near(recording, row["at"], window):
        if row["said"] and heard.endswith(row["said"]):
            continue
        near = text.add_paragraph()
        near_run = near.add_run(heard)
        near_run.font.size = Pt(9)
        near_run.font.color.rgb = RGBColor(*MUTED)
    foot = text.add_paragraph()
    foot_run = foot.add_run(
        ", ".join(
            part
            for part in (row["by"], row["when"], "to check" if row["to_check"] else "")
            if part
        )
    )
    foot_run.font.size = Pt(8)
    foot_run.font.color.rgb = RGBColor(*MUTED)
    document.add_paragraph()


def record_export(request, case, kind: str, date: dt.date | None) -> None:
    audit.write(
        audit.Category.EXPORTS,
        "chronology exported",
        actor=request.user,
        request=request,
        affected_user=case.owner,
        object_type="case",
        object_id=str(case.pk),
        object_label=case.name,
        kind=kind,
        scope="one day" if date else "every day",
    )
