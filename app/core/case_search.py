"""Search across a case (Phase 7 chapter 3): one box on the case page's
Search tab over every transcript, event, note, why, memo, summary and clip
title of the case, hits grouped by where they live, every hit a time that
plays or a place that opens. The term is never logged and never stored.
"""

from __future__ import annotations

import re
from html import escape

from django.db.models import Q
from django.urls import reverse
from django.utils.safestring import mark_safe

from core import documents, exports, incident_assistant, incidents
from core.assistant import DONE, Summary
from core.chronology import Event
from core.clips import Clip
from core.jobs import Segment

# How many hits one kind shows. A person looking for a phrase wants the
# first few; a thousand rows would be a worse answer, not a fuller one.
MOST = 200
SHORTEST = 2

KINDS = (
    ("words", "Words"),
    ("events", "Events"),
    ("notes", "Notes"),
    ("memos", "Memos"),
    ("summaries", "Summaries"),
    ("clips", "Clips"),
    ("documents", "Documents"),
)


def terms(asked: str) -> list[str]:
    """A phrase in quotes as one term; otherwise every word, all of which
    must be present."""
    asked = " ".join(asked.split())
    if (
        len(asked) >= 2
        and asked[0] == asked[-1]
        and asked[0] in ('"', "\u201c", "\u201d")
    ):
        phrase = asked[1:-1].strip()
        return [phrase] if phrase else []
    if len(asked) >= 2 and asked[0] == "\u201c" and asked[-1] == "\u201d":
        phrase = asked[1:-1].strip()
        return [phrase] if phrase else []
    return [word for word in asked.split() if word]


def _all(fields: list[str], words: list[str]) -> Q:
    """Every term found in one of the fields."""
    whole = Q()
    for word in words:
        one = Q()
        for field in fields:
            one |= Q(**{f"{field}__icontains": word})
        whole &= one
    return whole


def matches(text: str, words: list[str]) -> bool:
    low = text.lower()
    return bool(words) and all(word.lower() in low for word in words)


def mark(text: str, words: list[str]):
    """The text escaped, each term wrapped in a mark."""
    if not words:
        return mark_safe(escape(text))
    pattern = re.compile("|".join(re.escape(word) for word in words), re.IGNORECASE)
    out: list[str] = []
    last = 0
    for found in pattern.finditer(text):
        out.append(escape(text[last : found.start()]))
        out.append("<mark>" + escape(found.group(0)) + "</mark>")
        last = found.end()
    out.append(escape(text[last:]))
    return mark_safe("".join(out))


def sentence_with(text: str, words: list[str]) -> str:
    """The sentences of a text that carry any of the words, joined; the whole
    text when none does or the text is short (v1.75.1, from the walk: a
    memo or report hit showed a whole paragraph)."""
    if not words or len(text) <= 240:
        return text
    pieces = re.split(r"(?<=[.!?])\s+", text)
    kept = [one for one in pieces if any(word.lower() in one.lower() for word in words)]
    if not kept:
        return text[:240].rsplit(" ", 1)[0] + "..."
    return " ".join(kept[:3])


def paragraphs(text: str) -> list[str]:
    return [one.strip() for one in re.split(r"\n\s*\n|\n", text or "") if one.strip()]


def _hit(
    when: str,
    text,
    *,
    url: str = "",
    who: str = "",
    under=None,
    all_cameras: str = "",
    at: float = 0.0,
    paragraph: dict | None = None,
) -> dict:
    return {
        "when": when,
        "url": url,
        # A document hit (Phase 8 chapter 6): the card's address, page and paragraph.
        "paragraph": paragraph,
        "who": who,
        "text": text,
        "under": under,
        "all_cameras": all_cameras,
        "at": at,
    }


def search(case, asked: str, kind: str = "") -> dict:
    """Everything the box finds, by kind and by where it lives."""
    words = terms(asked)
    short = len("".join(words)) < SHORTEST
    kind = kind if kind in dict(KINDS) else ""
    groups: dict[tuple, dict] = {}
    counts: dict[str, int] = {key: 0 for key, _ in KINDS}
    more = False

    def group(key: tuple, head: str, url: str) -> dict:
        if key not in groups:
            groups[key] = {"head": head, "url": url, "hits": [], "order": len(groups)}
        return groups[key]

    def wanted(key: str) -> bool:
        return not kind or kind == key

    if short:
        return {
            "asked": asked,
            "kind": kind,
            "short": bool(asked),
            "total": 0,
            "kinds": [],
            "groups": [],
            "more": False,
            "most": MOST,
        }

    # Words: every transcript's lines and speaker names.
    found = (
        Segment.objects.filter(transcript__recording__case=case)
        .filter(_all(["text", "speaker"], words))
        .select_related("transcript__recording")
        .order_by("transcript__recording__created", "start")
    )
    rows = list(found[: MOST + 1])
    counts["words"] = len(rows[:MOST])
    more = more or len(rows) > MOST
    if wanted("words"):
        for one in rows[:MOST]:
            recording = one.transcript.recording
            here = group(
                ("recording", recording.pk),
                recording.title,
                reverse("viewer", args=[recording.pk]),
            )
            here["hits"].append(
                _hit(
                    exports.clock(one.start),
                    mark(one.text, words),
                    url=f"{reverse('viewer', args=[recording.pk])}?t={one.start:.1f}",
                    who=one.speaker,
                    all_cameras=incidents.all_cameras_url(recording, one.start),
                    at=one.start,
                )
            )

    # Documents (Phase 8 chapter 4): one hit per paragraph, opening the page
    # with the paragraph lit.
    if documents.on():
        found_paragraphs = documents.paragraph_hits(case, words, MOST)
        counts["documents"] = min(len(found_paragraphs), MOST)
        more = more or len(found_paragraphs) > MOST
        if wanted("documents"):
            for one in found_paragraphs[:MOST]:
                document = one["document"]
                here = group(("document", document.pk), document.title, document.url())
                here["hits"].append(
                    _hit(
                        f"page {one['page']}, paragraph {one['n']}",
                        mark(sentence_with(one["text"], words), words),
                        url=f"{document.url()}?page={one['page']}&para={one['n']}",
                        who="Document" + (", read by OCR" if one["ocr"] else ""),
                        at=float(one["page"] * 1000 + one["n"]),
                        paragraph={
                            "url": document.url(),
                            "page": one["page"],
                            "n": one["n"],
                            "title": document.title,
                        },
                    )
                )

    # Notes on lines (Phase 8 chapter 2), found with the notes on events.
    line_notes = list(
        Segment.objects.filter(
            transcript__recording__case=case, same_as_other_side=False
        )
        .exclude(note="")
        .filter(_all(["note"], words))
        .select_related("transcript__recording", "note_by")
        .order_by("transcript__recording__created", "start")[: MOST + 1]
    )
    counts["notes"] = min(len(line_notes), MOST)
    more = more or len(line_notes) > MOST
    if wanted("notes"):
        for one in line_notes[:MOST]:
            recording = one.transcript.recording
            here = group(
                ("recording", recording.pk),
                recording.title,
                reverse("viewer", args=[recording.pk]),
            )
            here["hits"].append(
                _hit(
                    exports.clock(one.start),
                    mark(one.text, words)
                    if matches(one.text, words)
                    else mark_safe(escape(one.text)),
                    url=(
                        f"{reverse('viewer', args=[recording.pk])}"
                        f"?t={one.start:.1f}&note=1"
                    ),
                    who="Note" + (f", {one.note_by.shown_name}" if one.note_by else ""),
                    under=mark(one.note, words),
                    all_cameras=incidents.all_cameras_url(recording, one.start),
                    at=one.start,
                )
            )

    if incidents.on():
        # Events: the line, the why, and each chronology's About.
        events = list(
            Event.objects.filter(incident__case=case, proposed=False)
            .filter(_all(["text", "why"], words))
            .select_related("incident", "incident__case")
            .order_by("incident__created", "at")[: MOST + 1]
        )
        abouts = [
            one
            for one in case.incidents.all()
            if one.about and matches(one.about, words)
        ]
        counts["events"] = min(len(events), MOST) + len(abouts)
        more = more or len(events) > MOST
        if wanted("events"):
            names_by_incident: dict = {}
            for event in events[:MOST]:
                incident = event.incident
                names = names_by_incident.setdefault(
                    incident.pk,
                    {str(c.pk): c.camera_id() for c in incident.cameras.all()},
                )
                from core import chronology

                here = group(("incident", incident.pk), incident.name, incident.url())
                here["hits"].append(
                    _hit(
                        incidents.time_of_day(incident, event.at),
                        mark(event.text, words),
                        url=f"{incident.url()}?t={event.at:.2f}",
                        who=chronology.source_words(event, names),
                        under=mark(event.why, words) if event.why else None,
                        at=event.at,
                    )
                )
            for incident in abouts:
                here = group(("incident", incident.pk), incident.name, incident.url())
                here["hits"].append(
                    _hit(
                        "About",
                        mark(incident.about, words),
                        url=incident.url(),
                        who="the chronology",
                        at=-1.0,
                    )
                )

        # Notes: the office's lines under events.
        notes = list(
            Event.objects.filter(incident__case=case, proposed=False)
            .exclude(note="")
            .filter(_all(["note"], words))
            .select_related("incident", "note_by")
            .order_by("incident__created", "at")[: MOST + 1]
        )
        counts["notes"] = min(counts["notes"] + len(notes), MOST)
        more = more or len(notes) > MOST
        if wanted("notes"):
            for event in notes[:MOST]:
                incident = event.incident
                here = group(("incident", incident.pk), incident.name, incident.url())
                here["hits"].append(
                    _hit(
                        incidents.time_of_day(incident, event.at),
                        mark(event.text, words)
                        if matches(event.text, words)
                        else mark_safe(escape(event.text)),
                        url=f"{incident.url()}?t={event.at:.2f}",
                        who="Note"
                        + (f", {event.note_by.shown_name}" if event.note_by else ""),
                        under=mark(event.note, words),
                        at=event.at,
                    )
                )

        # Memos, paragraph by paragraph.
        memo_hits = []
        for memo in incident_assistant.IncidentMemo.objects.filter(
            incident__case=case, state=DONE
        ).select_related("incident"):
            for number, paragraph in enumerate(paragraphs(memo.text)):
                if matches(paragraph, words):
                    memo_hits.append((memo.incident, number, paragraph))
        counts["memos"] = min(len(memo_hits), MOST)
        more = more or len(memo_hits) > MOST
        if wanted("memos"):
            for incident, number, paragraph in memo_hits[:MOST]:
                here = group(("incident", incident.pk), incident.name, incident.url())
                here["hits"].append(
                    _hit(
                        "Memo",
                        mark(paragraph, words),
                        url=f"{incident.url()}?tab=memo&para={number}",
                        who="the assistant",
                        at=10**9 + number,
                    )
                )

    # Summaries, paragraph by paragraph.
    summary_hits = []
    for summary in (
        Summary.objects.filter(recording__case=case, state=DONE)
        .select_related("recording")
        .order_by("recording__created", "-written_at")
    ):
        for number, paragraph in enumerate(paragraphs(summary.text)):
            if matches(paragraph, words):
                summary_hits.append((summary, number, paragraph))
    counts["summaries"] = min(len(summary_hits), MOST)
    more = more or len(summary_hits) > MOST
    if wanted("summaries"):
        for summary, number, paragraph in summary_hits[:MOST]:
            recording = summary.recording
            here = group(
                ("recording", recording.pk),
                recording.title,
                reverse("viewer", args=[recording.pk]),
            )
            here["hits"].append(
                _hit(
                    "Summary",
                    mark(paragraph, words),
                    url=(
                        f"{reverse('viewer', args=[recording.pk])}"
                        f"?panel=summary&summary={summary.pk}&para={number}"
                    ),
                    who=summary.template_name,
                    at=10**9 + number,
                )
            )

    # Clips, by title.
    clips = list(
        Clip.objects.filter(recording__case=case)
        .filter(_all(["title"], words))
        .select_related("recording", "incident")
        .order_by("created")[: MOST + 1]
    )
    counts["clips"] = min(len(clips), MOST)
    more = more or len(clips) > MOST
    if wanted("clips"):
        clips_tab = f"{reverse('case', args=[case.pk])}?tab=clips"
        for clip in clips[:MOST]:
            if clip.incident_id and clip.incident is not None:
                here = group(
                    ("incident", clip.incident.pk),
                    clip.incident.name,
                    clip.incident.url(),
                )
            else:
                here = group(
                    ("recording", clip.recording.pk),
                    clip.recording.title,
                    reverse("viewer", args=[clip.recording.pk]),
                )
            here["hits"].append(
                _hit(
                    "Clip",
                    mark(clip.title, words),
                    url=f"{clips_tab}#clip-{clip.pk}",
                    who=clip.span_label,
                    at=10**9 + 10**6,
                )
            )

    ordered = sorted(groups.values(), key=lambda one: one["order"])
    for one in ordered:
        one["hits"].sort(key=lambda hit: hit["at"])
    return {
        "asked": asked,
        "kind": kind,
        "short": False,
        "total": sum(counts.values()),
        "kinds": [
            {"key": key, "name": name, "count": counts[key]}
            for key, name in KINDS
            if counts[key]
        ],
        "groups": ordered,
        "more": more,
        "most": MOST,
    }


def find(incident, asked: str) -> dict:
    """Find on the incident page: the synced cameras' lines, the events and
    the memo's paragraphs, every hit a moment on the incident clock."""
    words = terms(asked)
    if len("".join(words)) < SHORTEST:
        return {"asked": asked, "hits": [], "skipped": 0}
    hits: list[dict] = []
    skipped = 0
    for camera in incident.cameras.select_related("recording"):
        if not camera.is_synced() or not hasattr(camera.recording, "transcript"):
            skipped += 1 if not camera.is_synced() else 0
            continue
        rows = (
            Segment.objects.filter(transcript=camera.recording.transcript)
            .filter(_all(["text", "speaker"], words))
            .order_by("start")[:MOST]
        )
        for one in rows:
            hits.append(
                {
                    "at": round(camera.starts_at + one.start, 2),
                    "camera": str(camera.pk),
                    "camera_id": camera.camera_id(),
                    "kind": "words",
                    "html": str(mark(one.text, words)),
                    "text": one.text,
                    "who": one.speaker,
                    "line_at": one.start,
                }
            )
        # The office's notes on this camera's lines (Phase 8 chapter 2).
        noted = (
            Segment.objects.filter(
                transcript=camera.recording.transcript, same_as_other_side=False
            )
            .exclude(note="")
            .filter(_all(["note"], words))
            .select_related("note_by")
            .order_by("start")[:MOST]
        )
        for one in noted:
            hits.append(
                {
                    "at": round(camera.starts_at + one.start, 2),
                    "camera": str(camera.pk),
                    "camera_id": camera.camera_id(),
                    "kind": "note",
                    "html": str(mark(one.note, words)),
                    "text": one.note,
                    "who": "Note"
                    + (f", {one.note_by.shown_name}" if one.note_by else ""),
                    "line_at": one.start,
                }
            )
    for event in incident.events.filter(proposed=False).filter(
        _all(["text", "why", "note"], words)
    ):
        hits.append(
            {
                "at": round(event.at, 2),
                "camera": str(event.camera_id) if event.camera_id else "",
                "camera_id": "",
                "kind": "event",
                "html": str(mark(event.text, words)),
                "text": event.text,
                "who": "Event",
                "event": str(event.pk),
            }
        )
    memo = incident_assistant.memo_of(incident)
    if memo is not None and memo.state == DONE:
        for number, paragraph in enumerate(paragraphs(memo.text)):
            if not matches(paragraph, words):
                continue
            cited = incident_assistant.memo_citations(incident, paragraph)
            first = min(cited.values()) if cited else None
            hits.append(
                {
                    "at": first,
                    "camera": "",
                    "camera_id": "",
                    "kind": "memo",
                    "html": str(mark(sentence_with(paragraph, words), words)),
                    "text": sentence_with(paragraph, words),
                    "who": "Memo",
                    "para": number,
                }
            )
    hits.sort(key=lambda one: (one["at"] is None, one["at"] or 0.0))
    return {"asked": asked, "hits": hits[: MOST * 2], "skipped": skipped}
