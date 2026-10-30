"""The Incidents tab as a strip (Phase 10 chapter 5, v1.180.0).

The tab's strip is the case's chronology without the spells: the day's
videos on their clocks, the notes lane, the incidents lane, and under them
a forming lane, a dashed bracket wherever two or more videos overlap with
notes gathering under them. Nothing is made without a press. The day's
reading itself comes from case_chronology.day_of(strip=True); this module
reads every day once for the Date strip's chips and the lead's count, and
picks the day the tab opens on.

The drawing: docs/spec/mockups/phase-10-incidents-tab.html, which stands.
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict

from core import case_chronology, incidents


def days(case) -> list[dict]:
    """Every day with a video on the clock (by its clock, by hand or from
    its file; a recording placed by its day alone has no hour and no bar),
    with its counts: videos, recordings, notes, and the forming brackets
    that earn a card (notes under the overlap, not declined). One pass over
    the case's recordings and notes, in date order."""
    recordings, by_recording = case_chronology._noted(case)
    placements = case_chronology._placements(recordings)
    declined = frozenset(case.declined_offers or [])
    # A video already a camera of an incident forms nothing (chapter 5).
    taken = incidents.taken_ids(case)
    bars: dict = defaultdict(list)
    marks: dict = defaultdict(list)
    for one in recordings:
        key = str(one.pk)
        date, start, how = placements[key]
        if date is None or how == case_chronology.DAY or start is None:
            continue
        for when in (date, date + dt.timedelta(days=1)):
            running = case_chronology._running(one, when, start, date, None)
            if running is None:
                continue
            bars[when].append(
                {
                    "id": key,
                    "from": running[0],
                    "to": running[1],
                    "video": incidents.is_video(one),
                }
            )
        for note in by_recording.get(key, []):
            at = start + note["at"]
            when = date
            if at >= case_chronology.DAY_SECONDS:
                at -= case_chronology.DAY_SECONDS
                when = date + dt.timedelta(days=1)
            marks[when].append(at)
    out = []
    for when in sorted(set(bars) | set(marks)):
        todays = bars.get(when, [])
        forming = 0
        for run in case_chronology._runs([b for b in todays if b["id"] not in taken]):
            notes = sum(
                1 for at in marks.get(when, []) if run["from"] <= at <= run["to"]
            )
            if notes and incidents.offer_key(sorted(run["ids"])) not in declined:
                forming += 1
        out.append(
            {
                "date": when.isoformat(),
                "words": case_chronology.day_words(when),
                "month": when.strftime("%b %Y"),
                "videos": sum(1 for b in todays if b["video"]),
                "recordings": len(todays),
                "notes": len(marks.get(when, [])),
                "forming": forming,
            }
        )
    return out


def forming_count(case) -> int:
    """The lead's figure: forming brackets with a card, over every day."""
    return sum(day["forming"] for day in days(case))


def pick_day(strip_days: list[dict]) -> dt.date | None:
    """The day the tab opens on: the one with the most forming, then the
    most notes, then the latest."""
    if not strip_days:
        return None
    best = max(strip_days, key=lambda day: (day["forming"], day["notes"], day["date"]))
    return dt.date.fromisoformat(best["date"])
