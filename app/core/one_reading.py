"""One reading (Phase 9 chapter 6, v1.163.0): how full a case is, and what a
question will do with it.

The incidents have One sitting (core/sitting.py): what the engine holds at
once, with a bar. A case is read differently (core/case_chat.py): whole
Transcripts packed into Readings of about six hours of talk each, two at a
time, under a ceiling of hours; over the ceiling the overviews are read first
(ADR 0018). Nothing here changes that rule. This module says it: one strip on
the case page under the head's pills, the drawer's head line and grounding
line before a question, and what a question read under its answer.

The figures come from what the app already keeps. The hours are the
recordings' lengths, as the ceiling counts them. The Readings are counted from
each Transcript's share of a Reading, kept on the Transcript
(`reading_tokens`, `reading_made_at`) the way a camera keeps its share of the
Sitting: counted at the landing, cleared by a Correction or a translation so
the next draw counts again, and stale once the Digest is newer than the count.
The summarised count is live, since the summaries are written overnight. The
strip reads no transcript to draw once the shares are kept.

Three states: room (the whole case fits one Reading), several (under the
ceiling, more than one Reading: the cost is minutes, not a refusal), over (the
overviews first; the refusal survives only with no summary at all). A new
recording counts as not ready until it lands, as a question would skip it.
"""

from __future__ import annotations

from django.utils import timezone

from core import assistant, case_chat, case_scope, notes, prompts, settings_store

# The bar's nearly-full mark, as a share of the ceiling: the sitting's figure.
NEARLY = 0.85
# Room kept in a Transcript's share for its header line in a Reading.
HEADER_TOKENS = 80
ROOM, SEVERAL, OVER = "room", "several", "over"
FIELDS = ("reading_tokens", "reading_made_at")


def on() -> bool:
    """The strip and the lines show when the Case Chat does."""
    return case_chat.available()


# The share kept on a Transcript -------------------------------------------------------


def size_of(transcript) -> int:
    """This Transcript's share of a Reading, as the Case Chat renders it: the
    header's room, the words (the English where there is one), the Digest
    after them and the office's notes."""
    recording = transcript.recording
    words = prompts.render(prompts.lines_of(transcript))
    digest = assistant.digest_text(transcript) if assistant.digests_on() else ""
    noted = notes.recording_block(recording) or ""
    text = words
    if digest:
        text += "\n\n" + prompts.digest_block(digest)
    if noted:
        text += "\n\n" + noted
    return HEADER_TOKENS + prompts.tokens(text)


def stale(transcript) -> bool:
    """Never counted, cleared, or the Digest is newer than the count."""
    if transcript.reading_made_at is None:
        return True
    made = assistant.digest_made_at(transcript)
    return bool(made and made > transcript.reading_made_at)


def refresh(transcript) -> int:
    transcript.reading_tokens = size_of(transcript)
    transcript.reading_made_at = timezone.now()
    transcript.save(update_fields=list(FIELDS))
    return transcript.reading_tokens


def changed(transcript) -> None:
    """A Correction or a translation changed the words: the share is stale,
    and the next draw counts it again. One cheap update, never a render."""
    if transcript is None:
        return
    type(transcript).objects.filter(pk=transcript.pk).update(reading_made_at=None)


def on_transcript(recording) -> None:
    """At the landing: the share counted while the transcript is in hand."""
    transcript = getattr(recording, "transcript", None)
    if transcript is None or not on():
        return
    refresh(transcript)


# The figures --------------------------------------------------------------------------


def pack_sizes(sizes: list[int], reading_tokens: int) -> list[list[int]]:
    """The Case Chat's packing rule on sizes alone: whole items into as few
    Readings as they fit, in order, never cut; an item larger than a Reading
    is alone in its own. Each group holds the items' positions."""
    groups: list[list[int]] = []
    current: list[int] = []
    used = 0
    for index, cost in enumerate(sizes):
        if current and used + cost > reading_tokens:
            groups.append(current)
            current, used = [], 0
        current.append(index)
        used += cost
    if current:
        groups.append(current)
    return groups


def hours_words(hours: float) -> str:
    """4, 4.5, 38, 150: one decimal under ten hours when it is not whole."""
    if hours < 10 and abs(hours - round(hours)) >= 0.05:
        return f"{hours:.1f}"
    return f"{round(hours)}"


def _count(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def rows_of(case, count: bool = True) -> tuple[list, int]:
    """The Recordings a whole-case question would read, in upload order, with
    their Transcripts in hand, and the count it would skip: flat, whatever
    the case's size, so the strip costs the page a few queries. With `count`
    the stale shares are counted on the way (the case page's draw); without
    it they are read as they stand (the drawer's poll, every few seconds)."""
    from django.db.models import Max

    from core.assistant import DigestPart

    rows = list(case.recordings.select_related("transcript").order_by("created"))
    read = [one for one in rows if getattr(one, "transcript", None) is not None]
    transcripts = [one.transcript for one in read]
    if not count:
        return read, len(rows) - len(read)
    newest = {
        row["transcript_id"]: row["made"]
        for row in DigestPart.objects.filter(transcript__in=transcripts)
        .exclude(made_at=None)
        .values("transcript_id")
        .annotate(made=Max("made_at"))
    }
    for one in transcripts:
        made = newest.get(one.pk)
        if one.reading_made_at is None or (made and made > one.reading_made_at):
            refresh(one)
    return read, len(rows) - len(read)


def figures(case, count: bool = True) -> dict:
    """Everything the strip, the pill and the drawer's lines need."""
    read, not_ready = rows_of(case, count)
    transcripts = [one.transcript for one in read]
    hours = case_scope.hours_of(read)
    allowed = case_chat.hours_allowed()
    groups = (
        pack_sizes(
            [one.reading_tokens for one in transcripts], settings_store.reading_tokens()
        )
        if read
        else []
    )
    readings = len(groups)
    over = hours > allowed
    summarised = no_summary = 0
    if over:
        overviews = assistant.overviews_for(read)
        summarised = sum(1 for one in read if overviews.get(one.pk))
        no_summary = len(read) - summarised
    zone = OVER if over else (SEVERAL if readings > 1 else ROOM)
    # The ticks where the Readings part, as shares of the ceiling.
    cuts: list[float] = []
    done = 0.0
    for group in groups[:-1]:
        done += sum((read[i].duration_seconds or 0) for i in group) / 3600
        if allowed:
            cuts.append(round(100 * done / allowed, 1))
    fill = round(min(100.0, 100 * hours / allowed), 1) if allowed else 0.0
    out = {
        "zone": zone,
        "hours": round(hours, 2),
        "hours_words": hours_words(hours),
        "allowed": allowed,
        "readings": readings,
        "transcripts": len(read),
        "not_ready": not_ready,
        "summarised": summarised,
        "no_summary": no_summary,
        "room_hours": round(max(0.0, allowed - hours), 2),
        "fill": fill,
        "cuts": cuts,
        "nearly": round(100 * NEARLY, 1),
        "at_once": settings_store.readings_at_once(),
    }
    out.update(words(out))
    return out


# The words ----------------------------------------------------------------------------


def words(f: dict) -> dict:
    """The strip's figure, its pill, its two legend halves and its sentence,
    and the drawer's head line, from the figures."""
    hours = f["hours_words"]
    allowed = f["allowed"]
    transcripts = f["transcripts"]
    if f["zone"] == OVER:
        figure = f"Over the ceiling · {hours} of {allowed} hours"
        pill, tone = (
            ("overviews first", "danger")
            if f["summarised"]
            else ("no summary yet", "danger")
        )
        right = f"{f['summarised']} summarised, {f['no_summary']} not yet"
        if f["summarised"]:
            sentence = (
                f"A question reads the overviews of {f['summarised']} recordings "
                "first, then the recordings they point to, whole."
            )
            if f["no_summary"]:
                sentence += (
                    f" {f['no_summary']} {'has' if f['no_summary'] == 1 else 'have'} "
                    "no summary yet and will not be read:"
                )
        else:
            sentence = (
                "No recording has a summary yet, so a question about the whole "
                "case will be refused:"
            )
        head = f"Over the ceiling · {hours} of {allowed} hours · {pill}"
    elif f["zone"] == SEVERAL:
        figure = f"{f['readings']} readings · {hours} of {allowed} hours"
        pill, tone = "several readings", "warn"
        right = f"room for about {hours_words(f['room_hours'])} hours more"
        sentence = (
            f"A question reads every transcript whole, in {f['readings']} readings "
            f"{f['at_once']} at a time, and takes a few minutes. Narrow the list to "
            "ask about fewer."
        )
        head = f"This case · {f['readings']} readings · {hours} of {allowed} hours"
    else:
        figure = f"One reading · {hours} of {allowed} hours"
        pill, tone = "room", "ok"
        right = f"room for about {hours_words(f['room_hours'])} hours more"
        if transcripts:
            sentence = (
                "A question reads every transcript whole at one go, in under a minute."
            )
        else:
            sentence = "No recording in this case has a transcript to read yet."
        head = f"This case · one reading · {hours} of {allowed} hours"
    if transcripts:
        left = _count(transcripts, "transcript") + (
            f", {f['not_ready']} not ready yet" if f["not_ready"] else ", all ready"
        )
    else:
        left = (
            f"{f['not_ready']} not ready yet" if f["not_ready"] else "no transcript yet"
        )
    return {
        "figure": figure,
        "pill": pill,
        "tone": tone,
        "left": left,
        "right": right,
        "sentence": sentence,
        # The sentence ends with a colon when the link "write the summaries
        # tonight" follows it on the page.
        "offer_summaries": sentence.endswith(":"),
        "head": head,
    }


def json_for(case) -> dict | None:
    """The figures for the case page and the drawer, or None when the Case
    Chat is off and nothing is drawn."""
    if not on():
        return None
    return figures(case)


def head_pill(f: dict | None) -> dict | None:
    """The head's pill, only over the ceiling; it opens the strip."""
    if not f or f["zone"] != OVER:
        return None
    return {
        "words": "over the reading ceiling",
        "href": "#one-reading",
        "tone": "danger",
    }


# What a question read -----------------------------------------------------------------


def took_words(turn) -> str:
    if not (turn.asked_at and turn.answered_at):
        return ""
    seconds = int((turn.answered_at - turn.asked_at).total_seconds())
    if seconds < 1:
        return ""
    if seconds < 60:
        return f"{seconds} s"
    minutes, rest = divmod(seconds, 60)
    return f"{minutes} min {rest} s" if rest else f"{minutes} min"


def read_line(turn) -> str:
    """Under an answer: what the question read, in how many Readings, and
    how long it took, so a slow answer explains itself and a fast one shows
    what it skipped. Empty while the question is still being answered."""
    if turn.state != assistant.DONE:
        return ""
    count = len(turn.readings or [])
    parts = turn.parts or (1 if count else 0)
    readings = _count(parts, "reading")
    selection = turn.selection or {}
    if turn.route == case_scope.OVERVIEWS:
        said = (
            f"Read the overviews of {selection.get('overviews_read', 0)}, then "
            f"{_count(selection.get('read_whole', count), 'recording')} whole "
            f"in {readings}"
        )
    elif turn.route == case_scope.NARROWED:
        said = (
            f"Read the {_count(count, 'transcript')} narrowed to, whole, in {readings}"
        )
    elif count:
        said = f"Read {_count(count, 'transcript')} whole in {readings}"
    else:
        return ""
    took = took_words(turn)
    return said + (f", {took}" if took else "")
