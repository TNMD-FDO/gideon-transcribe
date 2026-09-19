"""Documents beside the cameras, part 1 (Phase 8 chapter 4).

A Document is a PDF added to an Incident or a Recording as the police report
about it, kept in the Case. At upload, on the media queue, each page's words
are read with their positions (a scan read by OCR and marked so), split into
numbered Paragraphs by the gaps on the page, and the page is drawn to a
picture. The page is the truth; the words are a reading.

Nothing new to install: the PDF reader, the page renderer and the OCR engine
are packages in the app image, on the CPU. No retrieval store, no embeddings.
"""

from __future__ import annotations

import io
import logging
import shutil
import statistics
import uuid
from pathlib import Path

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from core import audit, settings_store

log = logging.getLogger("transcribe.documents")

READING = "reading"
READY = "ready"
FAILED = "failed"

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


class Document(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        "core.Case", on_delete=models.CASCADE, related_name="documents"
    )
    # Its home: the incident or the recording it is the report about. One of
    # the two, never neither.
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

    class Meta:
        ordering = ["-created"]

    def __str__(self) -> str:
        return self.title

    @property
    def folder(self) -> Path:
        return self.case.folder / "documents" / str(self.id)

    @property
    def original_path(self) -> Path:
        return self.folder / "original.pdf"

    def picture_path(self, number: int) -> Path:
        return self.folder / f"page-{number:03d}.png"

    def url(self) -> str:
        return reverse("document", args=[self.case_id, self.pk])

    def home_name(self) -> str:
        if self.incident_id:
            return self.incident.name
        if self.recording_id:
            return self.recording.title
        return ""

    def home_url(self) -> str:
        if self.incident_id:
            return self.incident.url()
        if self.recording_id:
            return reverse("viewer", args=[self.recording_id])
        return ""

    def home_kind(self) -> str:
        return (
            "incident"
            if self.incident_id
            else ("recording" if self.recording_id else "")
        )

    def pages_line(self) -> str:
        """ "42 pages, read by OCR, 3 poorly read" as the tab says it."""
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


def per_home() -> int:
    return int(settings_store.get("documents_per_home"))


def ocr_on() -> bool:
    return bool(settings_store.get("documents_ocr"))


def ocr_installed() -> bool:
    """Whether the OCR engine is in the image; the setting greys without it."""
    return shutil.which("tesseract") is not None


# Adding -------------------------------------------------------------------------------


class Refused(Exception):
    """Why a file was not added, in words for the page."""


def home_of(case, *, incident=None, recording=None):
    """The incident or recording a document is added to, checked to be the case's."""
    if incident is not None and incident.case_id == case.pk:
        return {"incident": incident}
    if recording is not None and recording.case_id == case.pk:
        return {"recording": recording}
    raise Refused("A document is added to an incident or a recording of the case.")


def count_at(home: dict) -> int:
    return Document.objects.filter(**{k: v for k, v in home.items()}).count()


def page_count(data: bytes) -> int:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(io.BytesIO(data))
    try:
        return len(pdf)
    finally:
        pdf.close()


def add(case, *, home: dict, data: bytes, filename: str, title: str, by, request=None):
    """Keep the PDF, count its pages against the ceiling, and queue the reading."""
    if not on():
        raise Refused("Documents are off.")
    if not data.startswith(b"%PDF"):
        raise Refused("Only a PDF can be added; save the file as a PDF first.")
    if count_at(home) >= per_home():
        raise Refused(
            f"This {'incident' if 'incident' in home else 'recording'} already has "
            f"{per_home()} documents, the most the Admin allows."
        )
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
        **home,
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
        home=document.home_kind(),
    )
    from core import cases, tasks

    cases.note_activity(case, by=by)
    tasks.read_document.defer(document_id=str(document.pk))
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
        document.error = str(trouble)[:300] or "unreadable"
        document.save(update_fields=["state", "error"])


def _read(document: Document) -> None:
    import pdfplumber

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
    document.save(
        update_fields=["pages", "ocr_pages", "poor_pages", "state", "error", "read_at"]
    )


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
    return list(incident.documents.order_by("-created"))


def for_recording(recording) -> list[Document]:
    return list(recording.documents.order_by("-created"))


def as_json(document: Document) -> dict:
    return {
        "id": str(document.pk),
        "title": document.title,
        "url": document.url(),
        "state": document.state,
        "pages_line": document.pages_line(),
        "pages": document.pages,
    }


def relink(document: Document, home: dict, *, by, request=None) -> None:
    if count_at(home) >= per_home():
        raise Refused(
            f"That {'incident' if 'incident' in home else 'recording'} already has "
            f"{per_home()} documents."
        )
    document.incident = home.get("incident")
    document.recording = home.get("recording")
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
        home=document.home_kind(),
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


# Search -------------------------------------------------------------------------------


def paragraph_hits(case, words: list[str], most: int) -> list[dict]:
    """One hit per paragraph whose text carries every word, in document order."""
    from core.case_search import _all, matches

    hits = []
    pages = (
        DocumentPage.objects.filter(document__case=case, document__state=READY)
        .filter(_all(["text"], words))
        .select_related("document")
        .order_by("document__created", "number")
    )
    for page in pages:
        for paragraph in page.paragraphs:
            if matches(paragraph["text"], words):
                hits.append(
                    {
                        "document": page.document,
                        "page": page.number,
                        "n": paragraph["n"],
                        "text": paragraph["text"],
                        "ocr": page.ocr,
                    }
                )
                if len(hits) > most:
                    return hits
    return hits
