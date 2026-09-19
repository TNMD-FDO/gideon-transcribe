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
SOURCES = (PERSON, WORDS, CAMERA, ASSISTANT, WATCH)

# The line under a proposal saying why it matters (Phase 7 chapter 2).
WHY_MOST = 300

TEXT_MOST = 500
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
    text = models.CharField(max_length=TEXT_MOST)
    source = models.CharField(max_length=10, default=PERSON)
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

    def __str__(self) -> str:
        return self.text


def running_cameras(incident, at: float) -> list[str]:
    """The placed cameras that cover the moment, as row ids."""
    return [
        str(one.pk)
        for one in incident.cameras.all()
        if one.is_placed() and one.starts_at <= at <= one.ends_at()
    ]


def _cleaned(incident, fields: dict) -> dict:
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
    text = " ".join(str(fields.get("text", "")).split())[:TEXT_MOST]
    if not text:
        raise ValueError("What happened? An event needs a line of text.")
    # Only Accept makes an Event the assistant's (chapter 3); a request that
    # says so is a person's.
    source = fields.get("source", PERSON)
    if source not in (PERSON, WORDS, CAMERA):
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
    return {
        "at": at,
        "until": until,
        "text": text,
        "source": source,
        "camera": camera,
        "cameras": cameras,
        "note": note,
        "to_check": to_check,
    }


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
    cleaned = _cleaned(event.incident, fields)
    # An Event keeps where it came from: Edit changes the words and the
    # cameras, never the source (an accepted proposal stays the assistant's).
    if event.source in (ASSISTANT, WATCH):
        cleaned["source"] = event.source
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


def remove(event: Event, *, by, request=None) -> None:
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
    return f"Added by {event.added_by.shown_name if event.added_by else 'a person'}"


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
    names = {str(one.pk): one.camera_id() for one in incident.cameras.all()}
    clips = clips_per_event(incident)
    rows = []
    for event in incident.events.filter(dismissed=False).select_related(
        "added_by", "changed_by", "note_by"
    ):
        rows.append(
            {
                "id": str(event.pk),
                "at": event.at,
                "until": event.until,
                "text": event.text,
                "source": event.source,
                "source_words": source_words(event, names),
                "camera": str(event.camera_id) if event.camera_id else "",
                "cameras": [one for one in event.cameras if one in names],
                "seen_on": ", ".join(
                    names[one] for one in event.cameras if one in names
                ),
                "proposed": event.proposed,
                "rests_on": event.rests_on if event.proposed else "",
                "why": event.why,
                "added_by": event.added_by.shown_name if event.added_by else "",
                # Phase 7 chapter 1.
                "note": event.note,
                "to_check": event.to_check,
                "note_by": (
                    event.note_by.shown_name if event.note and event.note_by else ""
                ),
                "clips": clips.get(str(event.pk), {}).get("count", 0),
                "clips_rendering": clips.get(str(event.pk), {}).get("rendering", 0),
                "clips_words": clips_words(clips.get(str(event.pk), {})),
            }
        )
    return rows


def to_check_count(incident) -> int:
    return incident.events.filter(proposed=False, to_check=True).count()


# The exports ----------------------------------------------------------------------


def _rows(incident) -> list[dict]:
    """The table every export prints, numbered in time order."""
    names = {str(one.pk): one.camera_id() for one in incident.cameras.all()}
    rows = []
    for number, event in enumerate(incident.events.filter(proposed=False), 1):
        rows.append(
            {
                "id": str(event.pk),
                "number": number,
                "time": incidents.time_of_day(incident, event.at),
                "seconds": event.at,
                "end": incidents.time_of_day(incident, event.until)
                if event.until
                else "",
                "text": event.text,
                "source": source_words(event, names),
                "camera": names.get(str(event.camera_id), ""),
                "seen_on": ", ".join(
                    names[one] for one in event.cameras if one in names
                ),
                "added_by": event.added_by.shown_name if event.added_by else "",
                "added": event.added,
                "assistant": event.source == ASSISTANT,
                "why": event.why,
                "note": event.note,
                "to_check": event.to_check,
            }
        )
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
            "Source",
            "Camera",
            "Seen on",
            "Added by",
            "Added on",
            "Note",
            "To check",
            "Why it matters",
        ]
    )
    for row in _rows(incident):
        writer.writerow(
            [
                row["number"],
                row["time"],
                f"{row['seconds']:.1f}",
                row["end"],
                row["text"],
                row["source"],
                row["camera"],
                row["seen_on"],
                row["added_by"],
                f"{timezone.localtime(row['added']):%Y-%m-%d %H:%M}",
                row["note"],
                "yes" if row["to_check"] else "",
                row["why"],
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


def word(incident, picture: bytes | None, exported_by: str) -> bytes:
    """The Chronology as a Word document, in the app's export shape."""
    from core import exports

    document = exports._open_record_document()
    exports._office_head(document)
    pages(document, incident, picture, exported_by)
    holder = io.BytesIO()
    document.save(holder)
    return holder.getvalue()


def pages(document, incident, picture: bytes | None, exported_by: str) -> None:
    """The Chronology's pages: the head, the cameras, the strip as a picture,
    the events table and the legends. The memo's export (chapter 3) carries
    them as its last pages."""
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
    if picture:
        document.add_paragraph()
        try:
            document.add_picture(io.BytesIO(picture), width=Inches(6.5))
        except Exception:  # noqa: BLE001 - a picture the page could not draw is left out
            note = document.add_paragraph("(The strip could not be drawn.)")
            note.runs[0].italic = True
    document.add_paragraph()
    table = document.add_table(rows=1, cols=5)
    table.style = "Light Grid Accent 1"
    for cell, title in zip(
        table.rows[0].cells, ("#", "Time", "Event", "Source", "Seen on"), strict=True
    ):
        cell.text = title
    for row in rows:
        cells = table.add_row().cells
        cells[0].text = str(row["number"]) + (" (to check)" if row["to_check"] else "")
        cells[1].text = row["time"] + (f" to {row['end']}" if row["end"] else "")
        cells[2].text = row["text"]
        if row["why"]:
            # The assistant's reason, or the watch phrase, under the line and
            # apart from it (Phase 7 chapter 2).
            why = cells[2].add_paragraph()
            run = why.add_run("Why it matters: " + row["why"])
            run.italic = True
        if row["note"]:
            # The office's note under the event, in italics (Phase 7).
            note = cells[2].add_paragraph()
            run = note.add_run("Note: " + row["note"])
            run.italic = True
        cells[3].text = row["source"]
        cells[4].text = row["seen_on"]
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
    for legend in (WORDS_LEGEND, QUOTE_LEGEND):
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
