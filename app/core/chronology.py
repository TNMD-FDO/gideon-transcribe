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
SOURCES = (PERSON, WORDS, CAMERA, ASSISTANT)

TEXT_MOST = 500


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
    source = fields.get("source", PERSON)
    if source not in (PERSON, WORDS, CAMERA):
        source = PERSON
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
    }


def add(incident, fields: dict, *, by, request=None) -> Event:
    cleaned = _cleaned(incident, fields)
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
    return f"Added by {event.added_by.shown_name if event.added_by else 'a person'}"


def events_json(incident) -> list[dict]:
    names = {str(one.pk): one.camera_id() for one in incident.cameras.all()}
    rows = []
    for event in incident.events.filter(dismissed=False).select_related(
        "added_by", "changed_by"
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
                "added_by": event.added_by.shown_name if event.added_by else "",
            }
        )
    return rows


# The exports ----------------------------------------------------------------------


def _rows(incident) -> list[dict]:
    """The table every export prints, numbered in time order."""
    names = {str(one.pk): one.camera_id() for one in incident.cameras.all()}
    rows = []
    for number, event in enumerate(incident.events.filter(proposed=False), 1):
        rows.append(
            {
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
        cells[0].text = str(row["number"])
        cells[1].text = row["time"] + (f" to {row['end']}" if row["end"] else "")
        cells[2].text = row["text"]
        cells[3].text = row["source"]
        cells[4].text = row["seen_on"]
    document.add_paragraph()
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
