"""The Call system (ADR 0021, the voice plan's first release, v1.138.0).

On a jail call the prepaid-call system's recorded voice says its
announcements and prompts: this call is from a correctional facility, to
accept press one, you have one minute remaining. Nobody on the call said
them, and until now they sat under a party's label (or, heard on both
Sides, under "Side 1 and Side 2"). From this release they are the lines of a
Speaker of its own, **Call system**: never a person, never named, never
merged, never seen by the Speaker check or by Suggest names, never made a
Person in a Case, and left alone by the rule that names a Side across a
Case. The memo says "the call system announced".

A line is the Call system's when its words carry one of the phrases on the
Admin's list (the shipped list is a prepaid-call system's wording in generic
form; the office edits it for its vendor), or when both Sides of a
two-channel call heard it. The marking runs as a Transcript lands, on a
Recording whose type is Jail call or that the app found to be a two-channel
call, and only while the Admin's switch is on; switched off, nothing here
runs and every Transcript is as it was.
"""

from __future__ import annotations

import logging

from core import settings_store

log = logging.getLogger(__name__)

# The Speaker's name on every page, in exports and in the memo. Reserved: a
# person may not rename a Speaker to it or rename it away.
NAME = "Call system"

# The Recording type (the Admin's list, as shipped) the marking runs on
# beside the two-channel calls the app finds itself.
JAIL_CALL_TYPE = "jail call"


def is_system(name: str | None) -> bool:
    return (name or "").strip().casefold() == NAME.casefold()


def on() -> bool:
    return bool(settings_store.get("call_system_available"))


def qualifies(recording) -> bool:
    """A jail call by type, or a two-channel call by the app's own finding."""
    if recording.is_two_channel_call:
        return True
    return (recording.recording_type or "").strip().casefold() == JAIL_CALL_TYPE


def plain(text: str) -> str:
    """The words alone, lower case, so punctuation cannot part a phrase from
    the line that carries it ("press one." matches "press one")."""
    kept = [one.lower() if one.isalnum() else " " for one in text or ""]
    return " " + " ".join("".join(kept).split()) + " "


def phrases() -> list[str]:
    """The Admin's list, made plain, blanks dropped."""
    out = []
    for line in settings_store.lines_of("call_system_phrases"):
        made = plain(line)
        if made.strip():
            out.append(made)
    return out


def says_a_phrase(text: str, made_phrases: list[str]) -> bool:
    words = plain(text)
    return any(phrase in words for phrase in made_phrases)


def mark(transcript) -> int:
    """Give the Call system its lines on a Transcript that has just landed.

    Returns how many Segments were marked; the count goes in the Transcript's
    provenance (a fact about the processing, never a word). Nothing is
    deleted and no word changes: the Segment keeps its time, its words and
    the engine's own label, and only the Speaker shown becomes the Call
    system's.
    """
    recording = transcript.recording
    if not on() or not qualifies(recording):
        return 0
    from core.queue import BOTH_SIDES

    made_phrases = phrases()
    marked = []
    for segment in transcript.segments.only("id", "text", "speaker"):
        if is_system(segment.speaker):
            continue
        if segment.speaker == BOTH_SIDES or says_a_phrase(segment.text, made_phrases):
            marked.append(segment.pk)
    if marked:
        transcript.segments.filter(pk__in=marked).update(speaker=NAME)
    provenance = dict(transcript.provenance or {})
    provenance["call_system"] = {"lines": len(marked), "phrases": len(made_phrases)}
    transcript.provenance = provenance
    transcript.save(update_fields=["provenance"])
    return len(marked)


def on_landed(transcript) -> None:
    """As a transcript lands: the Call system's lines, when the office has it on."""
    try:
        count = mark(transcript)
        if count:
            log.info(
                "call system: %d lines on recording %s", count, transcript.recording_id
            )
    except Exception:  # noqa: BLE001 - the marking must never fail a transcript
        log.exception("the call system's lines could not be marked")
