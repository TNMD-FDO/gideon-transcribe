"""Documents beside the cameras, part 1 (Phase 8 chapter 4).

A Document is a PDF kept in a Case as a police report, or a picture of the
Map (Phase 12 chapter 5). At upload, on the media queue, each page's words
are read with their positions (a scan read by OCR and marked so), split into
numbered Paragraphs by the gaps on the page, and the page is drawn to a
picture. The page is the truth; the words are a reading.

From v1.213.0 (Phase 12 chapter 11) a Document belongs to the Case alone and
may say what it is about (an incident or a camera of the case, or nothing);
the about steers what Gideon reads it beside and which record a comparison
offers first, and decides nothing else. Until then the same two fields were
the document's home, which decided which comparison was possible.

Nothing new to install: the PDF reader, the page renderer and the OCR engine
are packages in the app image, on the CPU. No retrieval store, no embeddings.
"""

from __future__ import annotations

import errno
import io
import logging
import re
import shutil
import statistics
import uuid
from pathlib import Path

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from core import audit, incidents, settings_store

log = logging.getLogger("transcribe.documents")

READING = "reading"
READY = "ready"
FAILED = "failed"

# What a Document is (Phase 12 chapter 5): the police report as a PDF, or a
# picture of the Map saved from the page as a PNG, one page, no words to
# read, kept and listed like any other and never compared.
REPORT = "report"
PICTURE = "picture"
# A picture of the map, as the browser draws it: a few megabytes at most.
PICTURE_MOST = 12 * 1024 * 1024
# A timelapse of the map (Phase 12 chapter 6.12, v1.241.0): a GIF of the
# Map over a span of the clock, kept beside the pictures; its one page's
# picture is its first frame, still, and the file itself moves.
TIMELAPSE = "timelapse"
TIMELAPSE_MOST = 60 * 1024 * 1024
# What has no words to read and is never compared.
PICTURES = (PICTURE, TIMELAPSE)

TITLE_MOST = 200
# A page with fewer words of its own than this is read from its picture.
FEW_WORDS = 8
# An OCR'd page with fewer words than this, or a low mean confidence, is
# "poorly read": shown, marked, and not to be trusted.
POOR_WORDS = 20
POOR_CONFIDENCE = 55.0
# The page picture's resolution, at reading size.
PICTURE_DPI = 110
OCR_DPI = 220
# Bumped when the splitter's rules change; every document read with an
# older version is read again by the minute task after the upgrade.
READ_VERSION = 2


class Document(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        "core.Case", on_delete=models.CASCADE, related_name="documents"
    )
    # What it is about (v1.213.0): an incident or a camera of the case, or
    # nothing. Until v1.212.0 the same fields were its home, one of the two
    # and never neither.
    incident = models.ForeignKey(
        "core.Incident",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
    )
    recording = models.ForeignKey(
        "core.Recording",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents",
    )
    title = models.CharField(max_length=TITLE_MOST)
    # A report (a PDF) or a picture of the map (a PNG), Phase 12 chapter 5.
    kind = models.CharField(max_length=10, default=REPORT)
    original_filename = models.CharField(max_length=300)
    size_bytes = models.BigIntegerField(default=0)
    pages = models.IntegerField(default=0)
    ocr_pages = models.IntegerField(default=0)
    poor_pages = models.IntegerField(default=0)
    state = models.CharField(max_length=10, default=READING)
    error = models.CharField(max_length=300, blank=True, default="")
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(null=True, blank=True)
    # Which reading split it (READ_VERSION); an older one is read again.
    read_version = models.IntegerField(default=0)

    class Meta:
        ordering = ["-created"]

    def __str__(self) -> str:
        return self.title

    @property
    def folder(self) -> Path:
        return self.case.folder / "documents" / str(self.id)

    @property
    def original_path(self) -> Path:
        if self.kind == TIMELAPSE:
            return self.folder / "original.gif"
        if self.kind == PICTURE:
            return self.folder / "original.png"
        return self.folder / "original.pdf"

    @property
    def is_picture(self) -> bool:
        """A picture of the map, still or moving: no words, never compared."""
        return self.kind in PICTURES

    @property
    def is_timelapse(self) -> bool:
        return self.kind == TIMELAPSE

    def picture_path(self, number: int) -> Path:
        return self.folder / f"page-{number:03d}.png"

    def url(self) -> str:
        return reverse("document", args=[self.case_id, self.pk])

    def about_name(self) -> str:
        """What the document is about, by name; "" when nothing."""
        names = []
        if self.incident_id:
            names.append(self.incident.name)
        if self.recording_id:
            names.append(self.recording.title)
        return " and ".join(names)

    def about_url(self) -> str:
        if self.incident_id:
            return self.incident.url()
        if self.recording_id:
            return reverse("viewer", args=[self.recording_id])
        return ""

    def about_kind(self) -> str:
        kinds = []
        if self.incident_id:
            kinds.append("incident")
        if self.recording_id:
            kinds.append("recording")
        return " and ".join(kinds)

    def about_words(self) -> str:
        """ "about Harbour car park", or "" when about nothing."""
        name = self.about_name()
        return f"about {name}" if name else ""

    def pages_line(self) -> str:
        """ "42 pages, read by OCR, 3 poorly read" as the tab says it."""
        if self.kind == TIMELAPSE:
            return "A timelapse of the map"
        if self.kind == PICTURE:
            return "A picture of the map"
        if self.state == READING:
            return f"Reading {self.pages} page{'' if self.pages == 1 else 's'}"
        if self.state == FAILED:
            return "Could not be read" + (f": {self.error}" if self.error else "")
        line = f"{self.pages} page{'' if self.pages == 1 else 's'}"
        if self.ocr_pages == self.pages and self.pages:
            line += ", read by OCR"
        elif self.ocr_pages:
            line += f", {self.ocr_pages} read by OCR"
        if self.poor_pages:
            line += f", {self.poor_pages} poorly read"
        return line


class DocumentPage(models.Model):
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="page_rows"
    )
    number = models.IntegerField()
    width = models.FloatField(default=612.0)
    height = models.FloatField(default=792.0)
    text = models.TextField(blank=True, default="")
    # [{"n": 1, "text": "...", "box": [x0, top, x1, bottom]}], in page points.
    paragraphs = models.JSONField(default=list, blank=True)
    ocr = models.BooleanField(default=False)
    poor = models.BooleanField(default=False)

    class Meta:
        ordering = ["document", "number"]
        unique_together = [("document", "number")]

    def __str__(self) -> str:
        return f"page {self.number}"


# The settings -------------------------------------------------------------------------


def on() -> bool:
    return bool(settings_store.get("documents"))


def most_pages() -> int:
    return int(settings_store.get("documents_pages_most"))


def per_case() -> int:
    """Documents per case (v1.213.0; Documents per incident or recording until
    then): the most a case holds, reports and pictures together."""
    return int(settings_store.get("documents_per_case"))


def ocr_on() -> bool:
    return bool(settings_store.get("documents_ocr"))


def ocr_installed() -> bool:
    """Whether the OCR engine is in the image; the setting greys without it."""
    return shutil.which("tesseract") is not None


# Adding -------------------------------------------------------------------------------


class Refused(Exception):
    """Why a file was not added, in words for the page."""


def about_of(case, *, incident=None, recording=None) -> dict:
    """What a document is about: an incident, a recording, both, or nothing
    (v1.213.0), each checked to be the case's. One of another case is
    refused with the reason."""
    about = {}
    if incident is not None:
        if incident.case_id != case.pk:
            raise Refused("That incident is not this case's.")
        about["incident"] = incident
    if recording is not None:
        if recording.case_id != case.pk:
            raise Refused("That recording is not this case's.")
        about["recording"] = recording
    return about


def count_in(case) -> int:
    """How many documents the case already holds, pictures included."""
    return Document.objects.filter(case=case).count()


def _room_or_refused(case) -> None:
    if count_in(case) >= per_case():
        raise Refused(
            f"This case already has {per_case()} documents, the most the Admin allows."
        )


def about_words(about: dict) -> str:
    """ "about Stop", "about Stop and BWC2-1", or "" for nothing."""
    names = [
        one.name if kind == "incident" else one.title for kind, one in about.items()
    ]
    return f"about {' and '.join(names)}" if names else ""


def page_count(data: bytes) -> int:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(io.BytesIO(data))
    try:
        return len(pdf)
    finally:
        pdf.close()


def add(case, *, about: dict, data: bytes, filename: str, title: str, by, request=None):
    """Keep the PDF, count its pages against the ceiling, and queue the reading."""
    if not on():
        raise Refused("Documents are off.")
    if not data.startswith(b"%PDF"):
        raise Refused("Only a PDF can be added; save the file as a PDF first.")
    _room_or_refused(case)
    try:
        pages = page_count(data)
    except Exception:  # noqa: BLE001 - any failure reads as an unusable file
        raise Refused("That file could not be opened as a PDF.") from None
    if pages < 1:
        raise Refused("That PDF has no pages.")
    if pages > most_pages():
        raise Refused(
            f"That PDF has {pages} pages; the most is {most_pages()}. Cut it down "
            "to the report that matters."
        )
    title = " ".join(str(title or "").split())[:TITLE_MOST] or (
        Path(filename).stem[:TITLE_MOST] or "Report"
    )
    document = Document.objects.create(
        case=case,
        title=title,
        original_filename=str(filename)[:300],
        size_bytes=len(data),
        pages=pages,
        added_by=by,
        incident=about.get("incident"),
        recording=about.get("recording"),
    )
    document.folder.mkdir(parents=True, exist_ok=True)
    document.original_path.write_bytes(data)
    audit.write(
        audit.Category.CASES,
        "Document added",
        actor=by,
        request=request,
        affected_user=case.owner if case.owner_id != by.pk else None,
        object_type="document",
        object_id=document.pk,
        object_label=document.title,
        pages=pages,
        about=document.about_kind(),
    )
    from core import cases, tasks

    cases.note_activity(case, by=by)
    tasks.read_document.defer(document_id=str(document.pk))
    return document


def add_picture(
    case, *, about: dict, data: bytes, filename: str, title: str, by, request=None
):
    """Save a picture of the map (Phase 12 chapter 5): one PNG the browser
    drew, kept as a Document of one page, about the incident shown or the
    camera pressed when there is one (v1.213.0: or about nothing), ready at
    once since there are no words to read. Counted against the case's cap;
    never compared."""
    if not on():
        raise Refused("Documents are off.")
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise Refused("Only a picture of the map can be saved here.")
    if len(data) > PICTURE_MOST:
        raise Refused("That picture is too large to keep.")
    _room_or_refused(case)
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as picture:
            picture.verify()
        with Image.open(io.BytesIO(data)) as picture:
            width_px, height_px = picture.size
    except Exception:  # noqa: BLE001 - any failure reads as an unusable file
        raise Refused("That picture could not be opened.") from None
    if width_px < 16 or height_px < 16:
        raise Refused("That picture is too small to be the map.")
    title = " ".join(str(title or "").split())[:TITLE_MOST] or "Map"
    document = Document.objects.create(
        case=case,
        kind=PICTURE,
        title=title,
        original_filename=str(filename or "map.png")[:300],
        size_bytes=len(data),
        pages=1,
        state=READY,
        read_at=timezone.now(),
        read_version=READ_VERSION,
        added_by=by,
        incident=about.get("incident"),
        recording=about.get("recording"),
    )
    document.folder.mkdir(parents=True, exist_ok=True)
    document.original_path.write_bytes(data)
    # The one page's picture is the file itself; its size is kept in the
    # page's points as a PDF page's would be, so the page view scales it.
    shutil.copyfile(document.original_path, document.picture_path(1))
    DocumentPage.objects.create(
        document=document,
        number=1,
        width=width_px * 72.0 / PICTURE_DPI,
        height=height_px * 72.0 / PICTURE_DPI,
        text="",
        paragraphs=[],
        ocr=False,
        poor=False,
    )
    audit.write(
        audit.Category.CASES,
        "Document added",
        actor=by,
        request=request,
        affected_user=case.owner if case.owner_id != by.pk else None,
        object_type="document",
        object_id=document.pk,
        object_label=document.title,
        pages=1,
        kind=PICTURE,
        about=document.about_kind(),
    )
    from core import cases

    cases.note_activity(case, by=by)
    return document


def add_timelapse(
    case,
    *,
    about: dict,
    data: bytes,
    still: bytes,
    size: tuple[int, int],
    title: str,
    by,
    request=None,
    frames: int = 0,
    cameras: int = 0,
    span: float = 0.0,
):
    """Save a timelapse (Phase 12 chapter 6.12, v1.241.0): the GIF ffmpeg
    joined from the frames the browser drew, kept as a Document of one
    page whose picture is the first frame, about the incident shown when
    there is one. Ready at once, counted against the case's cap, never
    compared. The row says how many cameras, how long a span and how
    many frames; never a place."""
    if not on():
        raise Refused("Documents are off.")
    if not data.startswith((b"GIF89a", b"GIF87a")):
        raise Refused("The timelapse could not be made into a GIF.")
    if len(data) > TIMELAPSE_MOST:
        raise Refused("That timelapse is too large to keep. Try a shorter one.")
    _room_or_refused(case)
    width_px, height_px = size
    title = " ".join(str(title or "").split())[:TITLE_MOST] or "Timelapse"
    document = Document.objects.create(
        case=case,
        kind=TIMELAPSE,
        title=title,
        # The title without what a PC refuses in a file's name (the colons).
        original_filename=re.sub(r"[^A-Za-z0-9 ,.-]+", "", title).strip()[:200]
        + ".gif",
        size_bytes=len(data),
        pages=1,
        state=READY,
        read_at=timezone.now(),
        read_version=READ_VERSION,
        added_by=by,
        incident=about.get("incident"),
        recording=about.get("recording"),
    )
    document.folder.mkdir(parents=True, exist_ok=True)
    document.original_path.write_bytes(data)
    document.picture_path(1).write_bytes(still)
    DocumentPage.objects.create(
        document=document,
        number=1,
        width=width_px * 72.0 / PICTURE_DPI,
        height=height_px * 72.0 / PICTURE_DPI,
        text="",
        paragraphs=[],
        ocr=False,
        poor=False,
    )
    audit.write(
        audit.Category.CASES,
        "Document added",
        actor=by,
        request=request,
        affected_user=case.owner if case.owner_id != by.pk else None,
        object_type="document",
        object_id=document.pk,
        object_label=document.title,
        pages=1,
        kind=TIMELAPSE,
        about=document.about_kind(),
        frames=int(frames),
        cameras=int(cameras),
        span_seconds=round(float(span)),
    )
    from core import cases

    cases.note_activity(case, by=by)
    return document


# Reading ------------------------------------------------------------------------------


def _lines_of(words: list[dict]) -> list[dict]:
    """Words into lines by their tops."""
    if not words:
        return []
    heights = [max(1.0, w["bottom"] - w["top"]) for w in words]
    tolerance = statistics.median(heights) * 0.5
    lines: list[dict] = []
    for word in sorted(words, key=lambda w: (round(w["top"], 1), w["x0"])):
        if lines and abs(word["top"] - lines[-1]["top"]) <= tolerance:
            lines[-1]["words"].append(word)
        else:
            lines.append({"top": word["top"], "words": [word]})
    for line in lines:
        line["words"].sort(key=lambda w: w["x0"])
        line["x0"] = min(w["x0"] for w in line["words"])
        line["x1"] = max(w["x1"] for w in line["words"])
        line["bottom"] = max(w["bottom"] for w in line["words"])
        line["text"] = " ".join(w["text"] for w in line["words"])
    return lines


def paragraphs_of(words: list[dict]) -> list[dict]:
    """Lines into numbered paragraphs by the gaps on the page: a gap of more
    than one and a half lines, or a line that starts well to the right of the
    block, starts a new paragraph."""
    lines = _lines_of(words)
    if not lines:
        return []
    heights = [line["bottom"] - line["top"] for line in lines]
    height = max(1.0, statistics.median(heights))
    left = min(line["x0"] for line in lines)
    right = max(line["x1"] for line in lines)
    groups: list[list[dict]] = [[lines[0]]]
    for before, line in zip(lines, lines[1:], strict=False):
        gap = line["top"] - before["bottom"]
        # An indented line starts a paragraph only after a line that ended
        # short of the block's right edge: a bullet's hanging second line
        # follows a full line and stays with it (measured 2026-09-19).
        ended_short = before["x1"] < right - height * 2
        indented = line["x0"] - left > height * 1.2 and ended_short
        if gap > height * 0.9 or indented:
            groups.append([line])
        else:
            groups[-1].append(line)
    out = []
    for number, group in enumerate(groups, start=1):
        text = " ".join(line["text"] for line in group).strip()
        if not text:
            continue
        out.append(
            {
                "n": len(out) + 1,
                "text": text,
                "box": [
                    round(min(line["x0"] for line in group), 1),
                    round(min(line["top"] for line in group), 1),
                    round(max(line["x1"] for line in group), 1),
                    round(max(line["bottom"] for line in group), 1),
                ],
            }
        )
        _ = number
    return out


def _words_by_ocr(page) -> tuple[list[dict], float]:
    """The words of a page's picture, read by OCR, in page points."""
    import pytesseract

    picture = page.to_image(resolution=OCR_DPI).original
    scale = 72.0 / OCR_DPI
    got = pytesseract.image_to_data(
        picture, lang="eng", output_type=pytesseract.Output.DICT
    )
    words = []
    confidences = []
    for text, left, top, width, height, conf in zip(
        got["text"],
        got["left"],
        got["top"],
        got["width"],
        got["height"],
        got["conf"],
        strict=False,
    ):
        text = str(text).strip()
        try:
            confidence = float(conf)
        except (TypeError, ValueError):
            confidence = -1.0
        if not text or confidence < 0:
            continue
        words.append(
            {
                "text": text,
                "x0": left * scale,
                "top": top * scale,
                "x1": (left + width) * scale,
                "bottom": (top + height) * scale,
            }
        )
        confidences.append(confidence)
    mean = statistics.mean(confidences) if confidences else 0.0
    return words, mean


def read(document_id) -> None:
    """The media queue's step: every page read, split and drawn."""
    document = Document.objects.filter(pk=document_id).select_related("case").first()
    if document is None:
        return
    try:
        _read(document)
    except Exception as trouble:  # noqa: BLE001 - the row says why, whatever it was
        log.exception("document %s could not be read", document.pk)
        document.state = FAILED
        # Plain words, never the server's own path (v1.132.0): a full disk is
        # named, anything else is "unreadable" with the detail in the journal.
        if isinstance(trouble, OSError) and trouble.errno == errno.ENOSPC:
            document.error = "The server's disk is full. Tell IT."
        else:
            document.error = "This document could not be read."
        document.save(update_fields=["state", "error"])


def _read(document: Document) -> None:
    import pdfplumber

    if document.kind in PICTURES:
        # A picture has no words to read: it was made ready when it was saved.
        return
    document.page_rows.all().delete()
    ocr_pages = 0
    poor_pages = 0
    with pdfplumber.open(str(document.original_path)) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            own = [
                {
                    "text": w["text"],
                    "x0": float(w["x0"]),
                    "top": float(w["top"]),
                    "x1": float(w["x1"]),
                    "bottom": float(w["bottom"]),
                }
                for w in page.extract_words()
                if str(w.get("text", "")).strip()
            ]
            words = own
            ocr = False
            poor = False
            if len(own) < FEW_WORDS and ocr_on() and ocr_installed():
                words, confidence = _words_by_ocr(page)
                ocr = True
                poor = len(words) < POOR_WORDS or confidence < POOR_CONFIDENCE
            elif len(own) < FEW_WORDS:
                # A scan with OCR off (or absent): kept and shown, its words not read.
                words = own
                poor = True
            paragraphs = paragraphs_of(words)
            page.to_image(resolution=PICTURE_DPI).original.save(
                str(document.picture_path(number)), format="PNG"
            )
            DocumentPage.objects.create(
                document=document,
                number=number,
                width=float(page.width),
                height=float(page.height),
                text="\n".join(one["text"] for one in paragraphs),
                paragraphs=paragraphs,
                ocr=ocr,
                poor=poor,
            )
            ocr_pages += 1 if ocr else 0
            poor_pages += 1 if poor else 0
            document.pages = max(document.pages, number)
    document.ocr_pages = ocr_pages
    document.poor_pages = poor_pages
    document.state = READY
    document.error = ""
    document.read_at = timezone.now()
    document.read_version = READ_VERSION
    document.save(
        update_fields=[
            "pages",
            "ocr_pages",
            "poor_pages",
            "state",
            "error",
            "read_at",
            "read_version",
        ]
    )


def read_again_the_old() -> int:
    """The minute task's step: a document read by an older splitter is put
    back in the line, marked reading so it is queued once."""
    from core import tasks

    old = list(
        Document.objects.filter(
            state=READY, kind=REPORT, read_version__lt=READ_VERSION
        ).values_list("pk", flat=True)
    )
    if old:
        Document.objects.filter(pk__in=old).update(state=READING)
        for pk in old:
            tasks.read_document.defer(document_id=str(pk))
    return len(old)


# The case's documents -----------------------------------------------------------------


def of_case(case) -> list[Document]:
    return list(
        case.documents.select_related("incident", "recording", "added_by").order_by(
            "-created"
        )
    )


def count(case) -> int:
    return case.documents.count()


def for_incident(incident) -> list[Document]:
    """The documents about the incident."""
    return list(incident.documents.order_by("-created"))


def for_recording(recording) -> list[Document]:
    """The documents about the recording."""
    return list(recording.documents.order_by("-created"))


def compared_with(home) -> list[Document]:
    """The reports with a comparison against the incident or recording
    (v1.213.0), the newest comparison first."""
    from core.incidents import Incident

    field = "incident" if isinstance(home, Incident) else "recording"
    seen: dict = {}
    for document in (
        Document.objects.filter(
            **{f"comparisons__{field}": home, "comparisons__parent__isnull": True}
        )
        .select_related("incident", "recording")
        .order_by("-comparisons__created")
    ):
        seen.setdefault(document.pk, document)
    return list(seen.values())


def read_with(home, *, about=None, compared=None) -> list[Document]:
    """What Gideon reads beside an incident or a recording (Phase 12 chapter
    11): the reports about it and the reports compared with it, each once,
    pictures left out since they have no words. A page that has the lists
    already hands them in, so nothing is asked twice."""
    from core.incidents import Incident

    if about is None:
        about = (
            for_incident(home) if isinstance(home, Incident) else for_recording(home)
        )
    if compared is None:
        compared = compared_with(home)
    out: dict = {}
    for document in list(about) + list(compared):
        if document.kind == REPORT:
            out.setdefault(document.pk, document)
    return list(out.values())


def as_json(document: Document) -> dict:
    return {
        "id": str(document.pk),
        "title": document.title,
        "url": document.url(),
        "state": document.state,
        "kind": document.kind,
        "pages_line": document.pages_line(),
        "pages": document.pages,
        "about": document.about_name(),
        "about_url": document.about_url(),
    }


def set_about(document: Document, about: dict, *, by, request=None) -> None:
    """About... on the shelf (v1.213.0; Re-link until then): what the document
    is about, or nothing. The audit row keeps its old name."""
    document.incident = about.get("incident")
    document.recording = about.get("recording")
    document.save(update_fields=["incident", "recording"])
    audit.write(
        audit.Category.CASES,
        "Document re-linked",
        actor=by,
        request=request,
        affected_user=document.case.owner if document.case.owner_id != by.pk else None,
        object_type="document",
        object_id=document.pk,
        object_label=document.title,
        about=document.about_kind(),
    )
    from core import cases

    cases.note_activity(document.case, by=by)


def rename(document: Document, title: str, *, by, request=None) -> None:
    """Rename, from the shelf's More menu (v1.213.0): the title only."""
    title = " ".join(str(title or "").split())[:TITLE_MOST]
    if not title:
        raise Refused("Give the document a title.")
    was = document.title
    document.title = title
    document.save(update_fields=["title"])
    audit.write(
        audit.Category.CASES,
        "Document renamed",
        actor=by,
        request=request,
        affected_user=document.case.owner if document.case.owner_id != by.pk else None,
        object_type="document",
        object_id=document.pk,
        object_label=title,
        was=was,
    )
    from core import cases

    cases.note_activity(document.case, by=by)


def remove(document: Document, *, by, request=None) -> None:
    case = document.case
    folder = document.folder
    title = document.title
    pk = document.pk
    document.delete()
    shutil.rmtree(folder, ignore_errors=True)
    audit.write(
        audit.Category.CASES,
        "Document removed",
        actor=by,
        request=request,
        affected_user=case.owner if case.owner_id != by.pk else None,
        object_type="document",
        object_id=pk,
        object_label=title,
    )
    from core import cases

    cases.note_activity(case, by=by)


def add_url(case, *, incident=None, recording=None) -> str:
    base = reverse("add-document", args=[case.pk])
    if incident is not None:
        return f"{base}?incident={incident.pk}"
    if recording is not None:
        return f"{base}?recording={recording.pk}"
    return base


def abouts_of(case) -> list[dict]:
    """The case's incidents and recordings, for the About pickers."""
    abouts = []
    if incidents.on():
        for incident in case.incidents.order_by("created"):
            abouts.append(
                {"kind": "incident", "id": str(incident.pk), "name": incident.name}
            )
    for recording in case.recordings.order_by("created"):
        abouts.append(
            {"kind": "recording", "id": str(recording.pk), "name": recording.title}
        )
    return abouts


# The shelf (Phase 12 chapter 11) ------------------------------------------------------


def shelf(case) -> dict:
    """The Documents tab as the shelf (v1.213.0): the reports with every
    comparison made of each and the records each could still be read
    against, the pictures of the map, and the chips' counts."""
    from core import comparison

    reports = []
    pictures = []
    stale = compared = not_yet = 0
    for document in of_case(case):
        row = {
            "document": document,
            "about": document.about_name(),
            "about_url": document.about_url(),
            "about_pill": document.about_words(),
            "download": reverse(
                "document-download", args=[document.case_id, document.pk]
            ),
        }
        if document.kind in PICTURES:
            row["map_url"] = picture_map_url(document)
            pictures.append(row)
            continue
        row["comparisons"] = comparison.shelf_rows(document)
        row["targets"] = comparison.targets_of(document)
        row["is_stale"] = any(
            one["stale"] for one in row["comparisons"] if one["state"] == "done"
        )
        if row["comparisons"]:
            compared += 1
        else:
            not_yet += 1
        if row["is_stale"]:
            stale += 1
        reports.append(row)
    return {
        "reports": reports,
        "pictures": pictures,
        "counts": {
            "all": len(reports) + len(pictures),
            "reports": len(reports),
            "pictures": len(pictures),
            "compared": compared,
            "not_yet": not_yet,
            "stale": stale,
        },
        "most": per_case(),
        "room": max(0, per_case() - len(reports) - len(pictures)),
    }


# A timelapse's title opens with its span, and the link goes to its start.
_PICTURE_TITLE = re.compile(
    r"^(?:Map at|Timelapse) (\d{2}):(\d{2}):(\d{2})(?: to \d{2}:\d{2}:\d{2})?, "
    r"(\d{1,2}) ([A-Z][a-z]{2}) (\d{4})"
)
_MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def picture_map_url(document: Document) -> str:
    """On the map (v1.213.0): the Map page at the picture's day and moment,
    read from the title Save a picture gave it; "" when the title is another."""
    found = _PICTURE_TITLE.match(document.title or "")
    if not found or found.group(5) not in _MONTHS:
        return ""
    hour, minute, second, day, month, year = found.groups()
    date = f"{year}-{_MONTHS.index(month) + 1:02d}-{int(day):02d}"
    seconds = int(hour) * 3600 + int(minute) * 60 + int(second)
    base = reverse("case-map-page", args=[document.case_id])
    return f"{base}?day={date}&from={seconds}"


# The document's state (part 2; the Comparison page and the paragraph card) ------------


def state_json(document: Document) -> dict:
    """The document as the Comparison page and the paragraph card draw it:
    every page's picture and words."""
    return {
        **as_json(document),
        "home": document.about_name(),
        "download": reverse("document-download", args=[document.case_id, document.pk]),
        # The comparison (part 3): where the layer asks and runs.
        "comparison": reverse(
            "document-comparison", args=[document.case_id, document.pk]
        ),
        "compare": reverse("document-compare", args=[document.case_id, document.pk]),
        "incident": str(document.incident_id) if document.incident_id else "",
        "recording": str(document.recording_id) if document.recording_id else "",
        "pages_rows": [
            {
                "number": row.number,
                "picture": reverse(
                    "document-picture", args=[document.case_id, document.pk, row.number]
                ),
                "width": row.width,
                "height": row.height,
                "ocr": row.ocr,
                "poor": row.poor,
                "paragraphs": row.paragraphs,
            }
            for row in document.page_rows.order_by("number")
        ],
    }


# Told to Gideon (part 2) -------------------------------------------------------------

RULE = (
    "A report is the officer's account and the cameras are the record: say "
    "which says what, and where they differ say so plainly and cite both. A "
    "description of the picture stays a description. Cite a report as "
    "[<its name>, page N, paragraph M], copied from the line it appears on. "
    "Never state a legal conclusion."
)
CITED = re.compile(r"\[([^\]\n]{1,120}?), page (\d+), paragraph (\d+)\]")


def reading_most() -> int:
    return int(settings_store.get("documents_reading_most"))


def short_names(documents: list[Document]) -> dict[str, Document]:
    """One name per document for its citations: "Report" alone, else the
    titles, made unique."""
    ready = [one for one in documents if one.state == READY]
    if len(ready) == 1:
        return {"Report": ready[0]}
    named: dict[str, Document] = {}
    for one in ready:
        name = " ".join(one.title.split()).replace("[", "(").replace("]", ")")[:80]
        base, n = name, 2
        while name in named:
            name = f"{base} ({n})"
            n += 1
        named[name] = one
    return named


def _paragraph_rows(named: dict[str, Document]) -> list[dict]:
    rows = []
    for name, document in named.items():
        for page in document.page_rows.order_by("number"):
            for one in page.paragraphs:
                rows.append(
                    {
                        "name": name,
                        "document": document,
                        "page": page.number,
                        "n": one["n"],
                        "text": one["text"],
                        "ocr": page.ocr,
                    }
                )
    return rows


def _matching(rows: list[dict], question: str, most: int) -> list[dict]:
    """The paragraphs whose words match the question, the fullest matches
    first, then in document order."""
    # The question's words of three letters or more, punctuation dropped.
    words = sorted(
        {w for w in re.findall(r"[a-z0-9']+", question.lower()) if len(w) >= 3}
    )
    if not words:
        return rows[:most]
    scored = []
    for index, row in enumerate(rows):
        low = row["text"].lower()
        score = sum(1 for w in words if w in low)
        if score:
            scored.append((-score, index, row))
    scored.sort()
    kept = sorted(index for _, index, _ in scored[:most])
    return [rows[i] for i in kept]


def reading_block(
    documents: list[Document], question: str, *, heading: str
) -> tuple[str, str, dict[str, Document]]:
    """The documents as the assistant reads them: whole when they fit the
    reading ceiling, else the paragraphs matching the question, with the
    line that says so. Returns (text, note, names)."""
    named = short_names(documents)
    if not named:
        return "", "", {}
    rows = _paragraph_rows(named)
    most = reading_most()
    note = ""
    if len(rows) > most:
        total = len(rows)
        rows = _matching(rows, question, most)
        note = (
            f"Read {len(rows)} of {total} paragraphs of the "
            f"{'report' if len(named) == 1 else 'reports'}, those matching the "
            "question."
        )
    lines = [heading]
    for name, document in named.items():
        lines.append(
            f"{name}: {document.title}, {document.pages} pages"
            + (", read by OCR" if document.ocr_pages else "")
            + "."
        )
        for row in rows:
            if row["document"].pk != document.pk:
                continue
            lines.append(
                f"[{name}, page {row['page']}, paragraph {row['n']}] {row['text']}"
            )
    return "\n".join(lines), note, named


def citation_json(document: Document, page: int, para: int) -> dict | None:
    """A citation as the chat draws it: the paragraph with its neighbours,
    the page, and where it opens. None when the paragraph does not exist."""
    row = document.page_rows.filter(number=page).first()
    if row is None:
        return None
    texts = {one["n"]: one["text"] for one in row.paragraphs}
    if para not in texts:
        return None
    return {
        "kind": "document",
        "document": str(document.pk),
        "title": document.title,
        "page": page,
        "para": para,
        "href": f"{document.url()}?page={page}&para={para}",
        "text": texts[para],
        "before": texts.get(para - 1, ""),
        "after": texts.get(para + 1, ""),
        "ocr": row.ocr,
    }


def citations_in(text: str, named: dict[str, Document]) -> dict:
    """The [name, page N, paragraph M] references that name a real
    paragraph of a document that was read; the rest stay plain text."""
    found: dict = {}
    for match in CITED.finditer(text or ""):
        name, page, para = (
            match.group(1).strip(),
            int(match.group(2)),
            int(match.group(3)),
        )
        document = named.get(name)
        if document is None and len(named) == 1:
            document = next(iter(named.values()))
        if document is None:
            continue
        cited = citation_json(document, page, para)
        if cited is not None:
            found[match.group(0)] = cited
    return found


def with_note(answer: str, note: str) -> str:
    return answer + (f"\n\n({note})" if note else "")


# Search -------------------------------------------------------------------------------


def sources(case) -> list:
    """The case's document pages, for the close forms of a search (v1.97.0)."""
    return [
        (
            DocumentPage.objects.filter(document__case=case, document__state=READY),
            "text",
        )
    ]


def paragraph_hits(
    case, words: list[str], most: int, also: dict | None = None
) -> list[dict]:
    """One hit per paragraph whose text carries every word, in document
    order; then, with `also`, the paragraphs that carry them only by a close
    form (v1.97.0), each marked close."""
    from core.case_search import _all, is_close, matches

    hits = []
    for near in (False, True) if also else (False,):
        pages = (
            DocumentPage.objects.filter(document__case=case, document__state=READY)
            .filter(_all(["text"], words, also if near else None))
            .select_related("document")
            .order_by("document__created", "number")
        )
        for page in pages:
            for paragraph in page.paragraphs:
                found = (
                    is_close(paragraph["text"], words, also)
                    if near
                    else matches(paragraph["text"], words)
                )
                if found:
                    hits.append(
                        {
                            "document": page.document,
                            "page": page.number,
                            "n": paragraph["n"],
                            "text": paragraph["text"],
                            "ocr": page.ocr,
                            "close": near,
                        }
                    )
                    if len(hits) > most:
                        return hits
    return hits
