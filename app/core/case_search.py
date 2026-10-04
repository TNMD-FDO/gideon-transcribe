"""Search across a case (Phase 7 chapter 3): one box on the case page's
Search tab over every transcript, event, note, why, memo, summary and clip
title of the case, hits grouped by where they live, every hit a time that
plays or a place that opens. The term is never logged and never stored.

From v1.97.0 the three boxes (Search, Find on the incident page, Find on a
recording's page) also read what the cameras showed, and after the exact
hits give the close matches: a line that carries a word's other form or
near spelling (core/close.py). There is still no score.
"""

from __future__ import annotations

import re
from html import escape

from django.db.models import Q
from django.urls import reverse
from django.utils.safestring import mark_safe

from core import close, documents, exports, incident_assistant, incidents, vocabulary
from core.assistant import DONE, Moment, Summary
from core.chronology import Event
from core.clips import Clip
from core.jobs import Segment, Transcript
from core.notes import MomentNote

# How many hits one kind shows. A person looking for a phrase wants the
# first few; a thousand rows would be a worse answer, not a fuller one.
MOST = 200
SHORTEST = 2

KINDS = (
    ("words", "Words"),
    # What the cameras showed (v1.97.0).
    ("seen", "Seen"),
    ("events", "Events"),
    ("notes", "Notes"),
    ("memos", "Memos"),
    ("summaries", "Summaries"),
    ("clips", "Clips"),
    ("documents", "Documents"),
)


class Phrase(list):
    """The terms of a search typed in quotes: one phrase, matched exactly
    wherever it falls. Plain words are whole words (v1.89.0)."""


def terms(asked: str) -> list[str]:
    """A phrase in quotes as one term, matched exactly; otherwise every word,
    all of which must be present as whole words."""
    asked = " ".join(asked.split())
    if (
        len(asked) >= 2
        and asked[0] == asked[-1]
        and asked[0] in ('"', "\u201c", "\u201d")
    ):
        phrase = asked[1:-1].strip()
        return Phrase([phrase]) if phrase else Phrase()
    if len(asked) >= 2 and asked[0] == "\u201c" and asked[-1] == "\u201d":
        phrase = asked[1:-1].strip()
        return Phrase([phrase]) if phrase else Phrase()
    return [word for word in asked.split() if word]


def _either(word: str, also: dict | None) -> str:
    """A word, or the word and its close forms (v1.97.0), as one group of a
    pattern: whichever of them is on the line."""
    given = [word, *((also or {}).get(word.lower(), []))]
    return "(?:" + "|".join(re.escape(one) for one in given) + ")"


def _word_pattern(words: list[str], also: dict | None = None) -> re.Pattern:
    """The terms as one pattern: a phrase anywhere, a word between word
    boundaries, so "car" no longer lights the middle of "scared"."""
    if isinstance(words, Phrase):
        return re.compile("|".join(re.escape(word) for word in words), re.IGNORECASE)
    return re.compile(
        "|".join(r"(?<!\w)" + _either(word, also) + r"(?!\w)" for word in words),
        re.IGNORECASE,
    )


def _all(fields: list[str], words: list[str], also: dict | None = None) -> Q:
    """Every term found in one of the fields: a phrase as a substring, a word
    as a whole word, between PostgreSQL's word edges. With `also`, a word's
    close forms stand for it too."""
    whole = Q()
    for word in words:
        one = Q()
        for field in fields:
            if isinstance(words, Phrase):
                one |= Q(**{f"{field}__icontains": word})
            else:
                one |= Q(**{f"{field}__iregex": r"\m" + _either(word, also) + r"\M"})
        whole &= one
    return whole


def matches(text: str, words: list[str], also: dict | None = None) -> bool:
    if not words:
        return False
    if isinstance(words, Phrase):
        low = text.lower()
        return all(word.lower() in low for word in words)
    return all(
        re.search(r"(?<!\w)" + _either(word, also) + r"(?!\w)", text, re.IGNORECASE)
        for word in words
    )


def close_only(queryset, fields: list[str], words: list[str], also: dict):
    """The rows that carry every term only when a close form stands for one:
    the close matches, never a row the exact search already found."""
    if not also:
        return queryset.none()
    return queryset.filter(_all(fields, words, also)).exclude(_all(fields, words))


def is_close(text: str, words: list[str], also: dict) -> bool:
    return bool(also) and not matches(text, words) and matches(text, words, also)


def mark(text: str, words: list[str], also: dict | None = None):
    """The text escaped, each term wrapped in a mark."""
    if not words:
        return mark_safe(escape(text))
    pattern = _word_pattern(words, also)
    out: list[str] = []
    last = 0
    for found in pattern.finditer(text):
        out.append(escape(text[last : found.start()]))
        out.append("<mark>" + escape(found.group(0)) + "</mark>")
        last = found.end()
    out.append(escape(text[last:]))
    return mark_safe("".join(out))


def sentence_with(text: str, words: list[str], also: dict | None = None) -> str:
    """The sentences of a text that carry any of the words, joined; the whole
    text when none does or the text is short (v1.75.1, from the walk: a
    memo or report hit showed a whole paragraph)."""
    if not words or len(text) <= 240:
        return text
    pieces = re.split(r"(?<=[.!?])\s+", text)
    pattern = _word_pattern(words, also)
    kept = [one for one in pieces if pattern.search(one)]
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
    close: bool = False,
    preview: dict | None = None,
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
        # A close match (v1.97.0): found by a word's form or near spelling.
        "close": close is True,
        # Found by a spelling the case lists for the name (Phase 9 chapter 2).
        "heard": close == HEARD,
        "rank": 2 if close == HEARD else (1 if close else 0),
        # The Preview (v1.98.0): the recording and the moment, for a hit
        # that plays over the search without leaving it.
        "preview": preview,
    }


def _plays(recording, at: float) -> dict | None:
    """What the Preview plays for a hit: the recording and the moment, when
    the recording has a copy to play."""
    if not recording.playback_ready:
        return None
    return {"recording": str(recording.pk), "at": round(float(at), 2)}


def _seen(transcripts):
    """What the cameras showed (v1.97.0): the descriptions the vision model
    wrote through a recording, each at its time."""
    return (
        Moment.objects.filter(
            transcript__in=transcripts, state=DONE, source=Moment.INTERVAL
        )
        .exclude(text="")
        .select_related("transcript__recording")
    )


HEARD = "heard"


def _any_phrase(fields: list[str], phrases: list[str]) -> Q:
    """Any of the phrases, anywhere in one of the fields."""
    whole = Q()
    for phrase in phrases:
        for field in fields:
            whole |= Q(**{f"{field}__icontains": phrase})
    return whole


def heard_only(queryset, fields: list[str], words, also, heard: list[str]):
    """The rows that carry a listed spelling of the name typed (Phase 9
    chapter 2), and neither the words nor a close form of them."""
    if not heard:
        return queryset.none()
    rows = queryset.filter(_any_phrase(fields, heard)).exclude(_all(fields, words))
    if also:
        rows = rows.exclude(_all(fields, words, also))
    return rows


def is_heard(text: str, words, also, heard: list[str]) -> bool:
    return (
        bool(heard) and not matches(text, words, also) and matches(text, Phrase(heard))
    )


def marked(text: str, words, also, near, heard: list[str] | None = None):
    """The text with its hit lit: the spelling for an also-heard-as hit, the
    words or their close forms for the rest."""
    if near == HEARD and heard:
        return mark(text, Phrase(heard))
    return mark(text, words, also)


def _with_close(queryset, fields, words, also, most=MOST, heard=None):
    """The exact rows, then the close ones, then the ones found by a listed
    spelling (Phase 9 chapter 2), as (row, kind) pairs where kind is False,
    True (close) or "heard"; and whether there were more than are shown."""
    exact = list(queryset.filter(_all(fields, words))[: most + 1])
    near = list(close_only(queryset, fields, words, also)[: most + 1])
    spelt = list(heard_only(queryset, fields, words, also, heard or [])[: most + 1])
    more = len(exact) > most or len(near) > most or len(spelt) > most
    pairs = [(one, False) for one in exact[:most]]
    pairs += [(one, True) for one in near[: max(0, most - len(pairs))]]
    pairs += [(one, HEARD) for one in spelt[: max(0, most - len(pairs))]]
    return pairs, more


def _read(paragraph: str, words, also):
    """Whether a text the app reads itself is a hit, and whether a close one:
    (hit, close)."""
    if matches(paragraph, words):
        return True, False
    if is_close(paragraph, words, also):
        return True, True
    return False, False


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
            "close": 0,
            "also": [],
            "kinds": [],
            "groups": [],
            "more": False,
            "most": MOST,
        }

    lines = Segment.objects.filter(transcript__recording__case=case)
    seen = _seen(Transcript.objects.filter(recording__case=case))
    # The spellings the case lists for a name typed (Phase 9 chapter 2).
    heard = vocabulary.heard_as(case, words)
    # A note event is found once, as its note (on a line, or at a moment).
    events_of = Event.objects.filter(
        incident__case=case,
        proposed=False,
        segment__isnull=True,
        moment_note__isnull=True,
    )
    moment_notes = MomentNote.objects.filter(recording__case=case)
    memos = list(
        incident_assistant.IncidentMemo.objects.filter(
            incident__case=case, state=DONE
        ).select_related("incident")
    )
    summaries = list(
        Summary.objects.filter(recording__case=case, state=DONE)
        .select_related("recording")
        .order_by("recording__created", "-written_at")
    )
    clips_of = Clip.objects.filter(recording__case=case)
    # The close forms (v1.97.0): a word's other forms and near spellings,
    # from what this case holds. A phrase in quotes has none.
    also = close.forms(
        words,
        sources=[
            (lines, "text"),
            (lines.exclude(note=""), "note"),
            (moment_notes, "note"),
            (seen, "text"),
            (events_of, "text"),
            (events_of, "why"),
            (events_of.exclude(note=""), "note"),
            (clips_of, "title"),
            *(documents.sources(case) if documents.on() else []),
        ],
        texts=[one.text for one in memos]
        + [one.text for one in summaries]
        + [one.about for one in case.incidents.all() if one.about],
    )

    # Words: every transcript's lines and speaker names.
    rows, over = _with_close(
        lines.select_related("transcript__recording").order_by(
            "transcript__recording__created", "start"
        ),
        ["text", "speaker"],
        words,
        also,
        heard=heard,
    )
    counts["words"] = len(rows)
    more = more or over
    if wanted("words"):
        for one, near in rows:
            recording = one.transcript.recording
            here = group(
                ("recording", recording.pk),
                recording.title,
                reverse("viewer", args=[recording.pk]),
            )
            here["hits"].append(
                _hit(
                    exports.clock(one.start),
                    marked(one.text, words, also, near, heard),
                    url=f"{reverse('viewer', args=[recording.pk])}?t={one.start:.1f}",
                    who=one.speaker,
                    all_cameras=incidents.all_cameras_url(recording, one.start),
                    at=one.start,
                    close=near,
                    preview=_plays(recording, one.start),
                )
            )

    # Seen (v1.97.0): what the cameras showed, by the vision model's words.
    rows, over = _with_close(
        seen.order_by("transcript__recording__created", "at"),
        ["text"],
        words,
        also,
        heard=heard,
    )
    counts["seen"] = len(rows)
    more = more or over
    if wanted("seen"):
        for one, near in rows:
            recording = one.transcript.recording
            here = group(
                ("recording", recording.pk),
                recording.title,
                reverse("viewer", args=[recording.pk]),
            )
            here["hits"].append(
                _hit(
                    exports.clock(one.at),
                    marked(
                        sentence_with(one.text, words, also), words, also, near, heard
                    ),
                    url=f"{reverse('viewer', args=[recording.pk])}?t={one.at:.1f}",
                    who="Seen",
                    all_cameras=incidents.all_cameras_url(recording, one.at),
                    at=one.at,
                    close=near,
                    preview=_plays(recording, one.at),
                )
            )

    # Documents (Phase 8 chapter 4): one hit per paragraph, opening the page
    # with the paragraph lit.
    if documents.on():
        found_paragraphs = documents.paragraph_hits(case, words, MOST, also)
        counts["documents"] = min(len(found_paragraphs), MOST)
        more = more or len(found_paragraphs) > MOST
        if wanted("documents"):
            for one in found_paragraphs[:MOST]:
                document = one["document"]
                here = group(("document", document.pk), document.title, document.url())
                here["hits"].append(
                    _hit(
                        f"page {one['page']}, paragraph {one['n']}",
                        mark(sentence_with(one["text"], words, also), words, also),
                        url=f"{document.url()}?page={one['page']}&para={one['n']}",
                        who="Document" + (", read by OCR" if one["ocr"] else ""),
                        at=float(one["page"] * 1000 + one["n"]),
                        paragraph={
                            "url": document.url(),
                            "page": one["page"],
                            "n": one["n"],
                            "title": document.title,
                        },
                        close=one["close"],
                    )
                )

    # Notes on lines (Phase 8 chapter 2), found with the notes on events.
    line_notes, over = _with_close(
        lines.filter(same_as_other_side=False)
        .exclude(note="")
        .select_related("transcript__recording", "note_by")
        .order_by("transcript__recording__created", "start"),
        ["note"],
        words,
        also,
        heard=heard,
    )
    counts["notes"] = len(line_notes)
    more = more or over
    if wanted("notes"):
        for one, near in line_notes:
            recording = one.transcript.recording
            here = group(
                ("recording", recording.pk),
                recording.title,
                reverse("viewer", args=[recording.pk]),
            )
            here["hits"].append(
                _hit(
                    exports.clock(one.start),
                    mark(one.text, words, also)
                    if matches(one.text, words, also)
                    else mark_safe(escape(one.text)),
                    url=(
                        f"{reverse('viewer', args=[recording.pk])}"
                        f"?t={one.start:.1f}&note=1"
                    ),
                    who="Note" + (f", {one.note_by.shown_name}" if one.note_by else ""),
                    under=marked(one.note, words, also, near, heard),
                    all_cameras=incidents.all_cameras_url(recording, one.start),
                    at=one.start,
                    close=near,
                    preview=_plays(recording, one.start),
                )
            )

    # Notes at moments where nothing was said (v1.99.0), with the notes on lines.
    rows, over = _with_close(
        moment_notes.select_related("recording", "note_by").order_by(
            "recording__created", "at"
        ),
        ["note"],
        words,
        also,
        heard=heard,
    )
    counts["notes"] = min(counts["notes"] + len(rows), MOST)
    more = more or over
    if wanted("notes"):
        for one, near in rows:
            recording = one.recording
            here = group(
                ("recording", recording.pk),
                recording.title,
                reverse("viewer", args=[recording.pk]),
            )
            here["hits"].append(
                _hit(
                    exports.clock(one.at),
                    # The note itself: it rests on no line (v1.99.1).
                    marked(one.note, words, also, near, heard),
                    url=(
                        f"{reverse('viewer', args=[recording.pk])}"
                        f"?t={one.at:.1f}&note=1"
                    ),
                    who="Note" + (f", {one.note_by.shown_name}" if one.note_by else ""),
                    all_cameras=incidents.all_cameras_url(recording, one.at),
                    at=one.at,
                    close=near,
                    preview=_plays(recording, one.at),
                )
            )

    if incidents.on():
        # Events: the line, the why, and each chronology's About.
        # A note event is found once, as the line's note (chapter 11).
        events, over = _with_close(
            events_of.select_related("incident", "incident__case").order_by(
                "incident__created", "at"
            ),
            ["text", "why"],
            words,
            also,
        )
        abouts = [
            (one, near)
            for one in case.incidents.all()
            for hit, near in [_read(one.about or "", words, also)]
            if hit
        ]
        counts["events"] = len(events) + len(abouts)
        more = more or over
        if wanted("events"):
            names_by_incident: dict = {}
            for event, near in events:
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
                        mark(event.text, words, also),
                        url=f"{incident.url()}?t={event.at:.2f}",
                        who=chronology.source_words(event, names),
                        under=mark(event.why, words, also) if event.why else None,
                        at=event.at,
                        close=near,
                    )
                )
            for incident, near in abouts:
                here = group(("incident", incident.pk), incident.name, incident.url())
                here["hits"].append(
                    _hit(
                        "About",
                        mark(incident.about, words, also),
                        url=incident.url(),
                        who="the chronology",
                        at=-1.0,
                        close=near,
                    )
                )

        # Notes: the office's lines under events.
        notes, over = _with_close(
            events_of.exclude(note="")
            .select_related("incident", "note_by")
            .order_by("incident__created", "at"),
            ["note"],
            words,
            also,
        )
        counts["notes"] = min(counts["notes"] + len(notes), MOST)
        more = more or over
        if wanted("notes"):
            for event, near in notes:
                incident = event.incident
                here = group(("incident", incident.pk), incident.name, incident.url())
                here["hits"].append(
                    _hit(
                        incidents.time_of_day(incident, event.at),
                        mark(event.text, words, also)
                        if matches(event.text, words, also)
                        else mark_safe(escape(event.text)),
                        url=f"{incident.url()}?t={event.at:.2f}",
                        who="Note"
                        + (f", {event.note_by.shown_name}" if event.note_by else ""),
                        under=mark(event.note, words, also),
                        at=event.at,
                        close=near,
                    )
                )

        # Memos, paragraph by paragraph.
        memo_hits = []
        for memo in memos:
            for number, paragraph in enumerate(paragraphs(memo.text)):
                hit, near = _read(paragraph, words, also)
                if hit:
                    memo_hits.append((memo.incident, number, paragraph, near))
        counts["memos"] = min(len(memo_hits), MOST)
        more = more or len(memo_hits) > MOST
        if wanted("memos"):
            for incident, number, paragraph, near in memo_hits[:MOST]:
                here = group(("incident", incident.pk), incident.name, incident.url())
                here["hits"].append(
                    _hit(
                        "Memo",
                        mark(paragraph, words, also),
                        url=f"{incident.url()}?tab=memo&para={number}",
                        who="the assistant",
                        at=10**9 + number,
                        close=near,
                    )
                )

    # Summaries, paragraph by paragraph.
    summary_hits = []
    for summary in summaries:
        for number, paragraph in enumerate(paragraphs(summary.text)):
            hit, near = _read(paragraph, words, also)
            if hit:
                summary_hits.append((summary, number, paragraph, near))
    counts["summaries"] = min(len(summary_hits), MOST)
    more = more or len(summary_hits) > MOST
    if wanted("summaries"):
        for summary, number, paragraph, near in summary_hits[:MOST]:
            recording = summary.recording
            here = group(
                ("recording", recording.pk),
                recording.title,
                reverse("viewer", args=[recording.pk]),
            )
            here["hits"].append(
                _hit(
                    "Summary",
                    mark(paragraph, words, also),
                    url=(
                        f"{reverse('viewer', args=[recording.pk])}"
                        f"?panel=summary&summary={summary.pk}&para={number}"
                    ),
                    who=summary.template_name,
                    at=10**9 + number,
                    close=near,
                )
            )

    # Clips, by title.
    clips, over = _with_close(
        clips_of.select_related("recording", "incident").order_by("created"),
        ["title"],
        words,
        also,
        heard=heard,
    )
    counts["clips"] = len(clips)
    more = more or over
    if wanted("clips"):
        clips_tab = f"{reverse('case', args=[case.pk])}?tab=clips"
        for clip, near in clips:
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
                    marked(clip.title, words, also, near, heard),
                    url=f"{clips_tab}#clip-{clip.pk}",
                    who=clip.span_label,
                    at=10**9 + 10**6,
                    close=near,
                )
            )

    ordered = sorted(groups.values(), key=lambda one: one["order"])
    for one in ordered:
        # The exact hits in time order, then the close ones in theirs: there
        # is no score (Phase 7 chapter 3).
        one["hits"].sort(key=lambda hit: (hit["rank"], hit["at"]))
    return {
        "asked": asked,
        "kind": kind,
        "short": False,
        "total": sum(counts.values()),
        "close": sum(1 for one in ordered for hit in one["hits"] if hit["close"]),
        # Found by a spelling the case lists (Phase 9 chapter 2), and the
        # spellings that were looked for.
        "heard": sum(1 for one in ordered for hit in one["hits"] if hit["heard"]),
        "heard_forms": heard,
        # What else was looked for, said on the page so a close match
        # explains itself.
        "also": close.every_form(also),
        "kinds": [
            {"key": key, "name": name, "count": counts[key]}
            for key, name in KINDS
            if counts[key]
        ],
        "groups": ordered,
        "more": more,
        "most": MOST,
    }


def _hit_of(camera, one, kind, html, text, who, near, at=None):
    start = one.start if at is None else at
    return {
        "at": round(camera.starts_at + start, 2),
        "camera": str(camera.pk),
        "camera_id": camera.camera_id(),
        "kind": kind,
        "html": str(html),
        "text": text,
        "who": who,
        "line_at": start,
        "close": near,
    }


def find(incident, asked: str) -> dict:
    """Find on the incident page: the synced cameras' lines and what they
    showed, the events and the memo's paragraphs, every hit a moment on the
    incident clock; the exact hits first, then the close ones (v1.97.0)."""
    words = terms(asked)
    if len("".join(words)) < SHORTEST:
        return {"asked": asked, "hits": [], "skipped": 0, "also": []}
    hits: list[dict] = []
    skipped = 0
    cameras = []
    for camera in incident.cameras.select_related("recording"):
        if not camera.is_synced() or not hasattr(camera.recording, "transcript"):
            skipped += 1 if not camera.is_synced() else 0
            continue
        cameras.append(camera)
    transcripts = [camera.recording.transcript for camera in cameras]
    lines = Segment.objects.filter(transcript__in=transcripts)
    events_of = incident.events.filter(
        proposed=False, segment__isnull=True, moment_note__isnull=True
    )
    recordings = [camera.recording for camera in cameras]
    moment_notes = MomentNote.objects.filter(recording__in=recordings)
    memo = incident_assistant.memo_of(incident)
    memo_text = memo.text if memo is not None and memo.state == DONE else ""
    also = close.forms(
        words,
        sources=[
            (lines, "text"),
            (lines.exclude(note=""), "note"),
            (moment_notes, "note"),
            (_seen(transcripts), "text"),
            (events_of, "text"),
            (events_of, "why"),
            (events_of.exclude(note=""), "note"),
        ],
        texts=[memo_text] if memo_text else [],
    )
    for camera in cameras:
        transcript = camera.recording.transcript
        mine = Segment.objects.filter(transcript=transcript)
        rows, _ = _with_close(mine.order_by("start"), ["text", "speaker"], words, also)
        for one, near in rows:
            hits.append(
                _hit_of(
                    camera,
                    one,
                    "words",
                    mark(one.text, words, also),
                    one.text,
                    one.speaker,
                    near,
                )
            )
        # What this camera showed (v1.97.0).
        rows, _ = _with_close(_seen([transcript]).order_by("at"), ["text"], words, also)
        for one, near in rows:
            told = sentence_with(one.text, words, also)
            hits.append(
                _hit_of(
                    camera,
                    one,
                    "seen",
                    mark(told, words, also),
                    told,
                    "Seen",
                    near,
                    at=one.at,
                )
            )
        # The office's notes on this camera's lines (Phase 8 chapter 2).
        rows, _ = _with_close(
            mine.filter(same_as_other_side=False)
            .exclude(note="")
            .select_related("note_by")
            .order_by("start"),
            ["note"],
            words,
            also,
        )
        for one, near in rows:
            hits.append(
                _hit_of(
                    camera,
                    one,
                    "note",
                    mark(one.note, words, also),
                    one.note,
                    "Note" + (f", {one.note_by.shown_name}" if one.note_by else ""),
                    near,
                )
            )
    # The notes where nothing was said on these cameras (v1.99.0).
    by_recording = {camera.recording_id: camera for camera in cameras}
    rows, _ = _with_close(
        moment_notes.select_related("note_by").order_by("at"), ["note"], words, also
    )
    for one, near in rows:
        hits.append(
            _hit_of(
                by_recording[one.recording_id],
                one,
                "note",
                mark(one.note, words, also),
                one.note,
                "Note" + (f", {one.note_by.shown_name}" if one.note_by else ""),
                near,
                at=one.at,
            )
        )
    rows, _ = _with_close(events_of, ["text", "why", "note"], words, also)
    for event, near in rows:
        hits.append(
            {
                "at": round(event.at, 2),
                "camera": str(event.camera_id) if event.camera_id else "",
                "camera_id": "",
                "kind": "event",
                "html": str(mark(event.text, words, also)),
                "text": event.text,
                "who": "Event",
                "event": str(event.pk),
                "close": near,
            }
        )
    if memo_text:
        for number, paragraph in enumerate(paragraphs(memo_text)):
            hit, near = _read(paragraph, words, also)
            if not hit:
                continue
            cited = incident_assistant.memo_citations(incident, paragraph)
            first = min(cited.values()) if cited else None
            told = sentence_with(paragraph, words, also)
            hits.append(
                {
                    "at": first,
                    "camera": "",
                    "camera_id": "",
                    "kind": "memo",
                    "html": str(mark(told, words, also)),
                    "text": told,
                    "who": "Memo",
                    "para": number,
                    "close": near,
                }
            )
    hits.sort(key=lambda one: (one["close"], one["at"] is None, one["at"] or 0.0))
    return {
        "asked": asked,
        "hits": hits[: MOST * 2],
        "skipped": skipped,
        "also": close.every_form(also),
    }


def find_in(recording, asked: str) -> dict:
    """Find on a recording's page (v1.97.0): the page itself finds what was
    typed in the lines it holds; this answers what it cannot, the lines that
    carry a close form and what the camera showed."""
    words = terms(asked)
    transcript = getattr(recording, "transcript", None)
    if transcript is None or len("".join(words)) < SHORTEST:
        return {"asked": asked, "close": [], "seen": [], "also": []}
    lines = Segment.objects.filter(transcript=transcript, same_as_other_side=False)
    seen = _seen([transcript])
    also = close.forms(words, sources=[(lines, "text"), (seen, "text")])
    near = close_only(lines.order_by("start"), ["text"], words, also)[:MOST]
    shown, _ = _with_close(seen.order_by("at"), ["text"], words, also)
    return {
        "asked": asked,
        "close": [
            {"id": one.pk, "html": str(mark(one.text, words, also))} for one in near
        ],
        "seen": [
            {
                "at": one.at,
                "clock": exports.clock(one.at),
                "html": str(mark(sentence_with(one.text, words, also), words, also)),
                "close": close_match,
            }
            for one, close_match in shown
        ],
        "also": close.every_form(also),
    }
