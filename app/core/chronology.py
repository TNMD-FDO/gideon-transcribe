"""The Chronology (Phase 6 chapter 2): an Incident's Events, and their exports.

An Event is something a person says happened, at a time of day the cameras
agree on: a time on the Incident clock, an optional end, a line of text,
its source (a person, the words of one camera, or what one camera showed),
and the cameras that show it. Chapter 3 adds the assistant's proposals;
nothing here makes one. The exports are a Word document with the strip as
a picture the page drew, a spreadsheet, and the picture alone; nothing
image-like is stored.
"""

from __future__ import annotations

import contextlib
import csv
import io
import uuid
from datetime import datetime

from django.db import models
from django.utils import timezone

from core import audit, incidents

PERSON = "person"
WORDS = "words"
CAMERA = "camera"
ASSISTANT = "assistant"
# Phase 7 chapter 2: found by the app's own search for a Watch phrase.
WATCH = "watch"
# Phase 8 chapter 4: made from a comparison's finding, resting on a paragraph.
REPORT = "report"
# Phase 8 chapter 11: the office's note on a line of a synced camera's
# transcript, which is an Event on that Incident's Chronology (a note event).
# Made and unmade by the app as the note and the camera come and go; never
# from a request.
NOTE = "note"
SOURCES = (PERSON, WORDS, CAMERA, ASSISTANT, WATCH, REPORT, NOTE)

# The line under a proposal saying why it matters (Phase 7 chapter 2).
WHY_MOST = 300

TEXT_MOST = 500
# A note event's text is the note itself, up to a note's length (chapter 11);
# the column holds that, and TEXT_MOST stays the cap on a typed event.
NOTE_TEXT_MOST = 2000
# The line and the detail (Phase 8 chapter 8): an Event's text is one field,
# read two ways. The line is the text to its first line break, or its first
# sentence when the text runs past LINE_MOST; a line still longer than
# LINE_CUT is cut at a word, and the detail is then the whole.
LINE_MOST = 120
LINE_CUT = 160
# A full stop after one of these does not end a sentence.
ABBREVIATIONS = frozenset(
    one.lower()
    for one in (
        "Sgt.",
        "Ofc.",
        "Off.",
        "Lt.",
        "Cpl.",
        "Capt.",
        "Det.",
        "Dep.",
        "Tpr.",
        "Ptl.",
        "Insp.",
        "Mr.",
        "Mrs.",
        "Ms.",
        "Dr.",
        "St.",
        "No.",
        "Jr.",
        "Sr.",
        "Ave.",
        "Blvd.",
        "Rd.",
        "Hwy.",
        "approx.",
        "vs.",
        "etc.",
        "a.m.",
        "p.m.",
    )
)
# A person's note under an Event, and the Chronology's About (Phase 7).
NOTE_MOST = 2000


class Event(models.Model):
    """One entry on an Incident's Chronology."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    incident = models.ForeignKey(
        incidents.Incident, on_delete=models.CASCADE, related_name="events"
    )
    # Seconds on the Incident clock; `until` when the Event ran a while.
    at = models.FloatField()
    until = models.FloatField(null=True, blank=True)
    text = models.CharField(max_length=NOTE_TEXT_MOST)
    source = models.CharField(max_length=10, default=PERSON)
    # Chapter 11: the line whose note this Event is, for a note event; null on
    # every other Event. One note event per line per Incident.
    segment = models.ForeignKey(
        "core.Segment",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="events",
    )
    # The camera the words or the description came from, when one did.
    camera = models.ForeignKey(
        incidents.IncidentCamera,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    # The cameras that show it: camera row ids, the person's to change.
    cameras = models.JSONField(default=list, blank=True)
    # Chapter 3's: an Event the assistant proposed and nobody has accepted,
    # the words it rests on, and whether a person put it away (kept so a
    # later run does not offer it again).
    proposed = models.BooleanField(default=False)
    rests_on = models.CharField(max_length=TEXT_MOST, blank=True, default="")
    dismissed = models.BooleanField(default=False)
    # Phase 7 chapter 2: the assistant's reason a proposal matters, or the
    # watch phrase that found it; blank on a person's Event. Shown under the
    # proposal and printed in the exports, never mixed into the line.
    why = models.CharField(max_length=WHY_MOST, blank=True, default="")
    # Phase 7 chapter 1: a person's own line under the event, with who wrote
    # it and when it last changed, and the mark that it needs looking at.
    # The assistant reads them and never writes them.
    note = models.TextField(max_length=NOTE_MOST, blank=True, default="")
    note_by = models.ForeignKey(
        "core.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    note_changed = models.DateTimeField(null=True, blank=True)
    to_check = models.BooleanField(default=False)
    added_by = models.ForeignKey(
        "core.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    added = models.DateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey(
        "core.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    changed = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["at", "added"]
        constraints = [
            models.UniqueConstraint(
                fields=["incident", "segment"],
                condition=models.Q(segment__isnull=False),
                name="one_note_event_per_line",
            )
        ]

    def __str__(self) -> str:
        return self.text

    def is_note(self) -> bool:
        return self.segment_id is not None


def running_cameras(incident, at: float) -> list[str]:
    """The placed cameras that cover the moment, as row ids."""
    return [
        str(one.pk)
        for one in incident.cameras.all()
        if one.is_placed() and one.starts_at <= at <= one.ends_at()
    ]


def _sentence_end(text: str) -> int:
    """Where the first sentence ends, as the index after its stop; 0 if never."""
    import re

    for match in re.finditer(r"[.!?;](?=\s)", text):
        if match.group() == ".":
            word = text[: match.end()].rsplit(None, 1)[-1]
            # "Sgt. Hale", "J. Smith", "No. 12": not an end.
            if word.lower() in ABBREVIATIONS or len(word) == 2 or word[:-1].isdigit():
                continue
        return match.end()
    return 0


def line_and_detail(text: str) -> tuple[str, str]:
    """An Event's text read two ways: the line, and the detail under it."""
    text = (text or "").strip()
    if "\n" in text:
        line, detail = text.split("\n", 1)
        line = " ".join(line.split())
        detail = " ".join(detail.split())
    elif len(text) > LINE_MOST:
        end = _sentence_end(text)
        if end:
            line, detail = text[:end].strip(), text[end:].strip()
        else:
            line, detail = text, ""
    else:
        return text, ""
    if len(line) > LINE_CUT:
        cut = line.rfind(" ", 0, LINE_CUT)
        line = line[: cut if cut > 40 else LINE_CUT].rstrip(" ,;:") + "\u2026"
        detail = " ".join(text.split())
    return line, detail


def _cleaned(incident, fields: dict, *, most: int = TEXT_MOST) -> dict:
    """The fields of an Event from a request, checked."""
    try:
        at = float(fields.get("at", ""))
    except (TypeError, ValueError):
        raise ValueError("When did it happen?") from None
    until = None
    if str(fields.get("until", "")).strip():
        try:
            until = float(fields["until"])
        except (TypeError, ValueError):
            raise ValueError("When did it end?") from None
        if until <= at:
            until = None
    # One line per line typed, the spacing tidied, blank lines dropped: a
    # line break is where the line ends and the detail begins (chapter 8).
    text = "\n".join(
        " ".join(line.split())
        for line in str(fields.get("text", "")).splitlines()
        if line.strip()
    )[:most]
    if not text:
        raise ValueError("What happened? An event needs a line of text.")
    # Only Accept makes an Event the assistant's (chapter 3); a request that
    # says so is a person's.
    source = fields.get("source", PERSON)
    if source not in (PERSON, WORDS, CAMERA, REPORT):
        source = PERSON
    # One line per line typed, the spacing tidied, blank lines dropped.
    note = "\n".join(
        " ".join(line.split())
        for line in str(fields.get("note", "")).splitlines()
        if line.strip()
    )[:NOTE_MOST]
    to_check = str(fields.get("to_check", "")).strip().lower() in (
        "1",
        "yes",
        "true",
        "on",
    )
    known = {str(one.pk) for one in incident.cameras.all()}
    wanted = fields.get("cameras")
    if wanted is None:
        cameras = running_cameras(incident, at)
    else:
        cameras = [one for one in wanted if one in known]
    camera = None
    if fields.get("camera") in known:
        camera = incidents.IncidentCamera.objects.get(pk=fields["camera"])
    cleaned = {
        "at": at,
        "until": until,
        "text": text,
        "source": source,
        "camera": camera,
        "cameras": cameras,
        "note": note,
        "to_check": to_check,
    }
    if source == REPORT:
        # Made from a comparison's finding: the paragraph it rests on and the
        # mark as its why come with it (Phase 8 chapter 4, part 3).
        cleaned["rests_on"] = " ".join(str(fields.get("rests_on", "")).split())[
            :TEXT_MOST
        ]
        cleaned["why"] = " ".join(str(fields.get("why", "")).split())[:WHY_MOST]
    return cleaned


def add(incident, fields: dict, *, by, request=None) -> Event:
    cleaned = _cleaned(incident, fields)
    if cleaned["note"]:
        cleaned["note_by"] = by
        cleaned["note_changed"] = timezone.now()
    event = Event.objects.create(incident=incident, added_by=by, **cleaned)
    audit.write(
        incidents.CATEGORY,
        "event added",
        actor=by,
        affected_user=incident.case.owner,
        object_type="incident",
        object_id=incident.pk,
        object_label=incident.name,
        request=request,
        source=cleaned["source"],
    )
    from core import cases

    cases.note_activity(incident.case, by=by)
    return event


def change(event: Event, fields: dict, *, by, request=None) -> Event:
    if event.is_note():
        return _change_note_event(event, fields, by=by, request=request)
    cleaned = _cleaned(event.incident, fields)
    # An Event keeps where it came from: Edit changes the words and the
    # cameras, never the source (an accepted proposal stays the assistant's).
    if event.source in (ASSISTANT, WATCH, REPORT):
        cleaned["source"] = event.source
        cleaned.pop("rests_on", None)
        cleaned.pop("why", None)
    if cleaned["note"] != event.note:
        # The note's writer is whoever last wrote it, not whoever last
        # touched the event; a cleared note has no writer.
        cleaned["note_by"] = by if cleaned["note"] else None
        cleaned["note_changed"] = timezone.now()
    for key, value in cleaned.items():
        setattr(event, key, value)
    event.changed_by = by
    event.changed = timezone.now()
    event.save()
    audit.write(
        incidents.CATEGORY,
        "event changed",
        actor=by,
        affected_user=event.incident.case.owner,
        object_type="incident",
        object_id=event.incident_id,
        object_label=event.incident.name,
        request=request,
    )
    from core import cases

    cases.note_activity(event.incident.case, by=by)
    return event


def _change_note_event(event: Event, fields: dict, *, by, request=None) -> Event:
    """Edit on a note event (chapter 11): the words are the note's, so a change
    to them goes through the note (one Note changed row, every Incident's row
    follows); the cameras and To check are the Event's own. The time is the
    line's and cannot be moved from here."""
    from core import notes

    cleaned = _cleaned(
        event.incident, {**fields, "at": event.at, "until": ""}, most=NOTE_TEXT_MOST
    )
    words_changed = cleaned["text"] != event.segment.note
    event.cameras = cleaned["cameras"]
    event.to_check = cleaned["to_check"]
    event.changed_by = by
    event.changed = timezone.now()
    event.save(update_fields=["cameras", "to_check", "changed_by", "changed"])
    if words_changed:
        notes.set_note(
            event.segment, cleaned["text"], by=by, request=request, where="chronology"
        )
        event.refresh_from_db()
        return event
    audit.write(
        incidents.CATEGORY,
        "event changed",
        actor=by,
        affected_user=event.incident.case.owner,
        object_type="incident",
        object_id=event.incident_id,
        object_label=event.incident.name,
        request=request,
    )
    from core import cases

    cases.note_activity(event.incident.case, by=by)
    return event


def remove(event: Event, *, by, request=None) -> None:
    if event.is_note():
        # Removing a note event removes the note from its line (chapter 11):
        # one Note removed row, and every Incident's row goes with it.
        from core import notes

        notes.set_note(event.segment, "", by=by, request=request, where="chronology")
        return
    incident = event.incident
    event.delete()
    audit.write(
        incidents.CATEGORY,
        "event removed",
        actor=by,
        affected_user=incident.case.owner,
        object_type="incident",
        object_id=incident.pk,
        object_label=incident.name,
        request=request,
    )
    from core import cases

    cases.note_activity(incident.case, by=by)


def source_words(event: Event, names: dict) -> str:
    """The source pill's words: Added by <name>; Words, <camera>; Camera, <camera>."""
    camera = names.get(str(event.camera_id), "a camera no longer in the incident")
    if event.source == WORDS:
        return f"Words, {camera}"
    if event.source == CAMERA:
        return f"Camera, {camera}"
    if event.source == ASSISTANT:
        return f"Proposed from {camera}" if event.proposed else f"Assistant, {camera}"
    if event.source == WATCH:
        return f"Watch phrase, {camera}"
    if event.source == REPORT:
        return "From the report"
    if event.source == NOTE:
        return f"Note by {note_writer(event)}, {camera}"
    return f"Added by {event.added_by.shown_name if event.added_by else 'a person'}"


def note_writer(event: Event) -> str:
    """A note event's writer: the note's, else whoever the row was made for."""
    segment = event.segment if event.segment_id else None
    if segment is not None and segment.note_by is not None:
        return segment.note_by.shown_name
    return event.added_by.shown_name if event.added_by else "a person"


def clips_per_event(incident) -> dict[str, dict]:
    """The Incident clips cut from each Event, by event id: how many, and how
    many are still rendering or have failed, so the row can say where they
    stand (v1.63.1)."""
    from django.db.models import Count

    from core.clips import Clip

    found: dict[str, dict] = {}
    for row in (
        Clip.objects.filter(event__incident=incident)
        .values("event_id", "state")
        .annotate(n=Count("pk"))
    ):
        one = found.setdefault(
            str(row["event_id"]), {"count": 0, "rendering": 0, "failed": 0}
        )
        one["count"] += row["n"]
        if row["state"] == "rendering":
            one["rendering"] += row["n"]
        elif row["state"] == "failed":
            one["failed"] += row["n"]
    return found


def clips_words(clips: dict) -> str:
    """ "1 clip, rendering", "2 clips ready", "1 clip failed": the row's mark."""
    count = clips.get("count", 0)
    if not count:
        return ""
    head = f"{count} clip{'' if count == 1 else 's'}"
    if clips.get("rendering"):
        return (
            f"{head}, rendering"
            if count == 1
            else f"{head}, {clips['rendering']} rendering"
        )
    if clips.get("failed"):
        return f"{head} failed" if count == 1 else f"{head}, {clips['failed']} failed"
    return f"{head} ready"


def clips_line(incident, numbers: dict) -> str:
    """The line under the export's events table: the clips made from events,
    by the event's number, the clip's title and its length."""
    from core.clips import Clip

    parts = []
    for clip in (
        Clip.objects.filter(incident=incident)
        .select_related("event")
        .order_by("created")
    ):
        number = numbers.get(str(clip.event_id)) if clip.event_id else None
        strip = bool((clip.picture or {}).get("from_strip"))
        where = f"#{number} " if number else ("from the strip: " if strip else "")
        parts.append(f"{where}{clip.title} ({clip.length})")
    if not parts:
        return ""
    return "Clips made from events and the strip: " + "; ".join(parts) + "."


def events_json(incident) -> list[dict]:
    from django.urls import reverse

    from core import notes

    names = {str(one.pk): one.camera_id() for one in incident.cameras.all()}
    clips = clips_per_event(incident)
    rows = []
    for event in incident.events.filter(dismissed=False).select_related(
        "added_by", "changed_by", "note_by", "segment__note_by", "segment__transcript"
    ):
        line, detail = line_and_detail(event.text)
        # Chapter 11: a note event's line, for the card and the row's link.
        segment = event.segment if event.is_note() else None
        line_url = ""
        if segment is not None:
            line_url = (
                reverse("viewer", args=[segment.transcript.recording_id])
                + f"?t={segment.start:.1f}&note=1"
            )
        rows.append(
            {
                "id": str(event.pk),
                "at": event.at,
                "until": event.until,
                "text": event.text,
                "line": line,
                "detail": detail,
                "source": event.source,
                "source_words": source_words(event, names),
                "camera": str(event.camera_id) if event.camera_id else "",
                "cameras": [one for one in event.cameras if one in names],
                "seen_on": ", ".join(
                    names[one] for one in event.cameras if one in names
                ),
                "proposed": event.proposed,
                "rests_on": (
                    event.rests_on if event.proposed or event.source == REPORT else ""
                ),
                "why": event.why,
                "added_by": event.added_by.shown_name if event.added_by else "",
                # Phase 7 chapter 1.
                "note": event.note,
                "to_check": event.to_check,
                "note_by": (
                    note_writer(event)
                    if segment is not None
                    else (
                        event.note_by.shown_name if event.note and event.note_by else ""
                    )
                ),
                "clips": clips.get(str(event.pk), {}).get("count", 0),
                "clips_rendering": clips.get(str(event.pk), {}).get("rendering", 0),
                "clips_words": clips_words(clips.get(str(event.pk), {})),
                # Chapter 11: empty on every Event but a note event.
                "segment_id": str(segment.pk) if segment is not None else "",
                "recording_id": (
                    str(segment.transcript.recording_id) if segment is not None else ""
                ),
                "line_start": segment.start if segment is not None else None,
                "line_url": line_url,
                "line_words": (
                    (segment.text[:140] + ("\u2026" if len(segment.text) > 140 else ""))
                    if segment is not None
                    else ""
                ),
                "note_on": (
                    notes.date_of(segment.note_changed) if segment is not None else ""
                ),
            }
        )
    return rows


def to_check_count(incident) -> int:
    return incident.events.filter(proposed=False, to_check=True).count()


# The exports ----------------------------------------------------------------------


# A spell (Phase 8 chapter 12): a run of events with no gap of this many
# seconds or more between neighbours, headed by its span on the Timeline
# view and in the chronology figure. One number, in one place; the page's
# script carries the same.
SPELL_GAP = 600

# The cameras' colours as the page draws them (its --sp1 to --sp8), in the
# page's order: the placed cameras by their start, then the unplaced.
FIGURE_COLOURS = [
    "#1f6fb2",
    "#c2410c",
    "#2e7d32",
    "#8e24aa",
    "#00838f",
    "#ad1457",
    "#6d4c41",
    "#546e7a",
]


def camera_colours(incident) -> dict:
    """Camera id -> the hex colour the page gives it, by the page's order."""
    cameras = list(incident.cameras.all())
    placed = sorted(
        (one for one in cameras if one.is_placed()),
        key=lambda one: (one.starts_at, one.added),
    )
    unplaced = [one for one in cameras if not one.is_placed()]
    return {
        str(one.pk): FIGURE_COLOURS[index % len(FIGURE_COLOURS)]
        for index, one in enumerate(placed + unplaced)
    }


def spells(rows: list[dict]) -> list[list[dict]]:
    """The rows in time order, split where a gap of SPELL_GAP or more begins."""
    groups: list[list[dict]] = []
    for row in rows:
        if groups and row["seconds"] - groups[-1][-1]["seconds"] < SPELL_GAP:
            groups[-1].append(row)
        else:
            groups.append([row])
    return groups


def spell_words(group: list[dict]) -> str:
    """The heading of a spell: its span, or its one time."""
    if len(group) == 1:
        return group[0]["time"]
    return f"{group[0]['time']} to {group[-1]['time']}"


def _rows(incident) -> list[dict]:
    """The table every export prints, numbered in time order."""
    names = {str(one.pk): one.camera_id() for one in incident.cameras.all()}
    colours = camera_colours(incident)
    rows = []
    for number, event in enumerate(incident.events.filter(proposed=False), 1):
        line, detail = line_and_detail(event.text)
        # The colour the figure prints the number in: the event's camera's,
        # else the first of the cameras it is seen on, else none.
        colour = colours.get(str(event.camera_id), "")
        if not colour:
            colour = next((colours[one] for one in event.cameras if one in colours), "")
        rows.append(
            {
                "id": str(event.pk),
                "number": number,
                "line": line,
                "detail": detail,
                "time": incidents.time_of_day(incident, event.at),
                "seconds": event.at,
                "end": incidents.time_of_day(incident, event.until)
                if event.until
                else "",
                "text": event.text,
                "source": source_words(event, names),
                "camera": names.get(str(event.camera_id), ""),
                "colour": colour,
                "seen_on": ", ".join(
                    names[one] for one in event.cameras if one in names
                ),
                "added_by": event.added_by.shown_name if event.added_by else "",
                "added": event.added,
                "assistant": event.source == ASSISTANT,
                "is_note": event.is_note(),
                "why": event.why,
                "note": event.note,
                "to_check": event.to_check,
                "spell": "",
            }
        )
    for group in spells(rows):
        words = spell_words(group)
        for row in group:
            row["spell"] = words
    return rows


def spreadsheet(incident) -> bytes:
    """One row per Event, UTF-8 with a byte order mark for desktop spreadsheets."""
    holder = io.StringIO()
    writer = csv.writer(holder)
    writer.writerow(
        [
            "Number",
            "Time",
            "Seconds into the incident",
            "End",
            "Event",
            "Detail",
            "Source",
            "Camera",
            "Seen on",
            "Added by",
            "Added on",
            "Note",
            "To check",
            "Why it matters",
            "Spell",
        ]
    )
    for row in _rows(incident):
        writer.writerow(
            [
                row["number"],
                row["time"],
                f"{row['seconds']:.1f}",
                row["end"],
                row["line"],
                row["detail"],
                row["source"],
                row["camera"],
                row["seen_on"],
                row["added_by"],
                f"{timezone.localtime(row['added']):%Y-%m-%d %H:%M}",
                row["note"],
                "yes" if row["to_check"] else "",
                row["why"],
                row["spell"],
            ]
        )
    return holder.getvalue().encode("utf-8-sig")


WORDS_LEGEND = (
    "An event marked Words or Camera was taken from a transcript or from a "
    "model's description of the picture and accepted by a person; a camera's "
    "description is not the transcript."
)
QUOTE_LEGEND = (
    "An event quoting a transcript is a copy as the transcript stood when the "
    "event was added; the transcript may have been corrected since."
)
NOTE_LEGEND = (
    "An event marked Note is the office's own note on a line of that camera's "
    "transcript, printed as written and never the assistant's."
)


def word(incident, picture: bytes | None, exported_by: str) -> bytes:
    """The Chronology as a Word document, in the app's export shape."""
    from core import exports

    document = exports._open_record_document()
    exports._office_head(document)
    pages(document, incident, picture, exported_by)
    exports.stamp_pages(
        document, f"{incident.case.name}, {incident.name}", "Chronology", incident.name
    )
    holder = io.BytesIO()
    document.save(holder)
    return holder.getvalue()


def band_png(incident, width: int = 1300) -> bytes | None:
    """The cameras' spans on the incident clock as a small picture, for the
    figure's head (Phase 8 chapter 12): the ruler's times, one bar per camera
    in its colour. None when there is nothing to draw."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:  # pragma: no cover - Pillow is in the app image
        return None
    low, high = incidents.span_of(incident)
    if low is None or high is None or high <= low:
        return None
    colours = camera_colours(incident)
    cameras = [one for one in incident.cameras.all() if one.is_placed()]
    if not cameras:
        return None
    cameras.sort(key=lambda one: (one.starts_at, one.added))
    left, right, top, lane = 16, 16, 30, 14
    height = top + len(cameras) * lane + 12
    image = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.load_default(size=18)
    except TypeError:  # pragma: no cover - an older Pillow
        font = ImageFont.load_default()

    def x(at: float) -> float:
        return left + ((at - low) / (high - low)) * (width - left - right)

    for i in range(6):
        at = low + (high - low) * i / 5
        words = incidents.time_of_day(incident, at)
        box = draw.textbbox((0, 0), words, font=font)
        text_width = box[2] - box[0]
        tx = x(at) - (0 if i == 0 else text_width if i == 5 else text_width / 2)
        draw.text((tx, 4), words, fill="#5b6673", font=font)
        draw.line([(x(at), top - 4), (x(at), height - 8)], fill="#d3d9e0", width=1)
    for index, camera in enumerate(cameras):
        y = top + index * lane
        start, end = camera.starts_at, camera.starts_at + camera.length()
        draw.rounded_rectangle(
            [(x(start), y + 3), (max(x(end), x(start) + 3), y + lane - 3)],
            radius=3,
            fill=colours.get(str(camera.pk), "#546e7a"),
        )
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def _figure(document, incident, rows: list[dict]) -> None:
    """The chronology figure (Phase 8 chapter 12): the band, then the events
    down the page in spells, each a number in its camera's colour, its time,
    its line, and under it the note, the why and the source in the small
    type. Text and rules, so Word lays it out; nothing overlaps because the
    entries stack."""
    from docx.shared import Inches, Pt, RGBColor

    band = band_png(incident)
    if band:
        # A band that will not embed is left out; the entries still print.
        with contextlib.suppress(Exception):
            document.add_picture(io.BytesIO(band), width=Inches(6.5))
        legend = document.add_paragraph()
        colours = camera_colours(incident)
        cameras = sorted(
            (one for one in incident.cameras.all() if one.is_placed()),
            key=lambda one: (one.starts_at, one.added),
        )
        for index, camera in enumerate(cameras):
            run = legend.add_run(("   " if index else "") + "\u25a0 ")
            run.font.color.rgb = RGBColor.from_string(
                colours[str(camera.pk)].lstrip("#")
            )
            run.font.size = Pt(9)
            legend.add_run(camera.camera_id()).font.size = Pt(9)
        tail = legend.add_run("   Each bar is one camera's recording on the clock.")
        tail.font.size = Pt(8)
        tail.italic = True
    if not rows:
        empty = document.add_paragraph("No events on the chronology yet.")
        empty.runs[0].italic = True
        return
    for group in spells(rows):
        # A real heading (v1.90.0), so Word's navigation pane lists the spells.
        heading = document.add_heading(level=2)
        heading.paragraph_format.space_before = Pt(10)
        heading.paragraph_format.space_after = Pt(2)
        head = heading.add_run(spell_words(group))
        head.bold = True
        head.font.name = "Consolas"
        count = heading.add_run(
            f"   {len(group)} event{'' if len(group) == 1 else 's'}"
        )
        count.font.size = Pt(9)
        count.font.color.rgb = RGBColor(0x5B, 0x66, 0x73)
        table = document.add_table(rows=0, cols=3)
        table.autofit = False
        for row in group:
            cells = table.add_row().cells
            cells[0].width = Inches(0.4)
            cells[1].width = Inches(0.9)
            cells[2].width = Inches(5.2)
            number = cells[0].paragraphs[0].add_run(str(row["number"]))
            number.bold = True
            if row["colour"]:
                number.font.color.rgb = RGBColor.from_string(row["colour"].lstrip("#"))
            time = cells[1].paragraphs[0].add_run(row["time"])
            time.font.name = "Consolas"
            time.font.size = Pt(10)
            if row["end"]:
                until = cells[1].add_paragraph().add_run(f"to {row['end']}")
                until.font.name = "Consolas"
                until.font.size = Pt(9)
                until.font.color.rgb = RGBColor(0x5B, 0x66, 0x73)
            words = cells[2].paragraphs[0]
            words.add_run(row["line"])
            if row["to_check"]:
                mark = words.add_run("  To check")
                mark.font.size = Pt(9)
                mark.font.color.rgb = RGBColor(0x8A, 0x5A, 0x00)
            if row["detail"]:
                detail = cells[2].add_paragraph()
                detail.add_run(row["detail"]).font.size = Pt(9)
            under = []
            if row["note"]:
                under.append("Note: " + row["note"])
            if row["why"]:
                under.append("Why it matters: " + row["why"])
            under.append(
                row["source"]
                + (f"; seen on {row['seen_on']}" if row["seen_on"] else "")
            )
            small = cells[2].add_paragraph()
            run = small.add_run("  ".join(under))
            run.italic = True
            run.font.size = Pt(8)
            run.font.color.rgb = RGBColor(0x5B, 0x66, 0x73)


def pages(document, incident, picture: bytes | None, exported_by: str) -> None:
    """The Chronology's pages: the head, the cameras, the chronology figure
    (the band, the spells and the numbered entries) and the legends. The
    memo's export (chapter 3) carries them as its last pages. `picture` was
    the strip picture the page drew until v1.85.0; it is ignored, and the
    figure is drawn here."""
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Inches, Pt

    from core import exports

    heading = document.add_paragraph(f"Chronology: {incident.name}")
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    heading.runs[0].bold = True
    heading.runs[0].font.size = Pt(20)
    said = document.add_paragraph("The events of an incident, on the cameras' clock")
    said.alignment = WD_ALIGN_PARAGRAPH.CENTER
    said.runs[0].font.size = Pt(13)
    document.add_paragraph()
    cameras = list(incident.cameras.select_related("recording"))
    placed_words, _ = incidents.placed_words(incident)
    rows = _rows(incident)
    exports._facts(
        document,
        [
            ("Case", incident.case.name),
            ("Incident", incident.name),
            (
                "Clock",
                (
                    f"the time of day on {incident.clock_date}, by the cameras' clocks"
                    if incident.has_clock()
                    else "no camera clock; times count from the first camera"
                ),
            ),
            ("Span", incidents.span_words(incident)),
            ("Cameras", f"{len(cameras)}, {placed_words}"),
            ("Events", str(len(rows))),
            ("Exported", f"{datetime.now():{exports.DAY_AND_TIME}} by {exported_by}"),
        ],
        Inches,
    )
    if incident.about:
        # About this chronology (Phase 7 chapter 1), the office's own words.
        document.add_paragraph()
        for line in incident.about.splitlines():
            if line.strip():
                document.add_paragraph(line.strip())
    document.add_paragraph()
    table = document.add_table(rows=1, cols=4)
    table.style = "Light Grid Accent 1"
    for cell, title in zip(
        table.rows[0].cells, ("Camera", "Recording", "Starts at", "Placed"), strict=True
    ):
        cell.text = title
    for camera in sorted(
        cameras, key=lambda one: (one.starts_at is None, one.starts_at or 0.0)
    ):
        cells = table.add_row().cells
        cells[0].text = camera.camera_id()
        cells[1].text = camera.recording.title
        cells[2].text = (
            incidents.time_of_day(incident, camera.starts_at)
            if camera.is_placed()
            else ""
        )
        cells[3].text = incidents.PLACED_WORDS.get(camera.placed, "")
    document.add_paragraph()
    _figure(document, incident, rows)
    document.add_paragraph()
    to_check = sum(1 for row in rows if row["to_check"])
    if to_check:
        line = document.add_paragraph(
            f"{to_check} event{'' if to_check == 1 else 's'} marked to check: "
            "the office has not settled the point."
        )
        line.runs[0].italic = True
    clips = clips_line(incident, {row["id"]: row["number"] for row in rows})
    if clips:
        # The clips cut from events (Phase 7 chapter 1), by number.
        line = document.add_paragraph(clips)
        line.runs[0].italic = True
    legends = [WORDS_LEGEND, QUOTE_LEGEND]
    if any(row["is_note"] for row in rows):
        legends.append(NOTE_LEGEND)
    for legend in legends:
        line = document.add_paragraph(legend)
        line.runs[0].italic = True
    if any(row["assistant"] for row in rows):
        from core import assistant

        notice = assistant.notice("", timezone.now())
        if notice:
            line = document.add_paragraph(notice)
            line.runs[0].italic = True


def export_name(incident, ending: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in incident.name)
    return f"Chronology - {safe.strip() or 'incident'}.{ending}"


def record_export(request, incident, kind: str) -> None:
    audit.write(
        audit.Category.EXPORTS,
        "chronology exported",
        actor=request.user,
        request=request,
        affected_user=incident.case.owner,
        object_type="incident",
        object_id=incident.pk,
        object_label=incident.name,
        kind=kind,
    )
