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

Found by its phrases (v1.149.0): a Recording with no type at all is a jail
call when three of its lines carry the phrases, whatever the type field
says, so the pass runs on it too and the no-type line offers the type. The
type itself stays a person's word: nothing here writes it, and a Recording
typed something else is left alone however many phrases it carries.
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

# The opening stretch fills in (v1.139.0): a short line, or one that begins
# with "please", between two Call system lines within this many seconds of
# each is the system's too. The recogniser cuts the announcements into
# fragments ("Please...", "Please enter the...") that no phrase list can
# name; a party's "Hello?" after the connection has no system line after it
# within the gap, and a single announcement mid-call has none either side.
FILL_GAP_SECONDS = 15.0
FILL_SHORT_WORDS = 6

# The opening fragment (v1.161.0): a recogniser that cuts lines at pauses
# starts a call's first announcement with a fragment of its own ("This
# call is"), before the first line the phrases find, where the rule above
# has no system line to lean on. A short line, or one that begins with
# "please", within the gap before the first system line is the system's
# too, when that system line opens the call: it starts within this many
# seconds of the call's first line, and every line before it is such a
# fragment, each within the gap of the next. A line that is not (somebody
# spoke first) means the announcement did not open the call, and nothing
# before it is the system's; a mid-call announcement pulls nothing before
# it either, since a party's "Okay" often comes just before one.
OPENING_SECONDS = 60.0

# Found by its phrases (v1.149.0): on a Recording with no type, this many
# lines carrying the phrases make it a jail call for the pass. One line can
# be a party quoting the system or a phrase said in passing; three distinct
# lines of announcements are the system itself. The office's own calls
# carried thirteen and fourteen.
FOUND_BY_PHRASES_MIN = 3


def untyped(recording) -> bool:
    return not (recording.recording_type or "").strip()


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


def fill_in(rows: list, system: set) -> list:
    """The lines between two of the system's lines, close to both, that are
    short or begin with "please": the system's too, applied until nothing
    more changes. `system` grows as lines join."""
    added = []
    changed = True
    while changed:
        changed = False
        for index, segment in enumerate(rows):
            if segment.pk in system:
                continue
            before = next((r for r in reversed(rows[:index]) if r.pk in system), None)
            after = next((r for r in rows[index + 1 :] if r.pk in system), None)
            if before is None or after is None:
                continue
            if segment.start - before.end > FILL_GAP_SECONDS:
                continue
            if after.start - segment.end > FILL_GAP_SECONDS:
                continue
            words = plain(segment.text).split()
            if len(words) <= FILL_SHORT_WORDS or (words and words[0] == "please"):
                system.add(segment.pk)
                added.append(segment.pk)
                changed = True
    return added


def fill_opening(rows: list, system: set) -> list:
    """The fragments before the call's first system line (v1.161.0): every
    line before it is short or begins with "please", each within the gap of
    the line after it, and the system line starts within the opening; then
    they are all the system's, and otherwise none is. `system` grows as
    lines join."""
    if not rows or not system:
        return []
    first = next((i for i, row in enumerate(rows) if row.pk in system), None)
    if first is None or first == 0:
        return []
    if rows[first].start - rows[0].start > OPENING_SECONDS:
        return []
    added = []
    after = rows[first]
    for segment in reversed(rows[:first]):
        if after.start - segment.end > FILL_GAP_SECONDS:
            return []
        words = plain(segment.text).split()
        if not (len(words) <= FILL_SHORT_WORDS or (words and words[0] == "please")):
            # Somebody spoke before the announcement: it does not open the
            # call, and nothing before it is the system's.
            return []
        added.append(segment.pk)
        after = segment
    system.update(added)
    return added


def mark(transcript) -> int:
    """Give the Call system its lines on a Transcript that has just landed.

    Returns how many Segments were marked; the count goes in the Transcript's
    provenance (a fact about the processing, never a word). Nothing is
    deleted and no word changes: the Segment keeps its time, its words and
    the engine's own label, and only the Speaker shown becomes the Call
    system's.
    """
    recording = transcript.recording
    if not on():
        return 0
    by_type = qualifies(recording)
    if not by_type and not untyped(recording):
        # Typed something else: the type is a person's word and wins.
        return 0
    from core.queue import BOTH_SIDES

    made_phrases = phrases()
    rows = list(
        transcript.segments.only("id", "text", "speaker", "start", "end").order_by(
            "start", "id"
        )
    )
    system = {row.pk for row in rows if is_system(row.speaker)}
    marked = []
    heard = 0
    for segment in rows:
        if segment.pk in system:
            continue
        said = says_a_phrase(segment.text, made_phrases)
        heard += 1 if said else 0
        if segment.speaker == BOTH_SIDES or said:
            marked.append(segment.pk)
    if not by_type and heard < FOUND_BY_PHRASES_MIN:
        # Untyped and too few phrases to be sure: no pass, and nothing
        # written, so the pass can still come with a type set later.
        return 0
    system.update(marked)
    marked += fill_in(rows, system)
    opening = fill_opening(rows, system)
    marked += opening
    if marked:
        transcript.segments.filter(pk__in=marked).update(speaker=NAME)
    provenance = dict(transcript.provenance or {})
    provenance["call_system"] = {
        "lines": len(marked),
        "phrases": len(made_phrases),
        "found_by": "type" if by_type else "phrases",
        "heard": heard,
        "opening": len(opening),
    }
    transcript.provenance = provenance
    transcript.save(update_fields=["provenance"])
    return len(marked)


def found_by_phrases(transcript) -> int:
    """How many lines carried the phrases when the pass found an untyped
    Recording to be a jail call by them (v1.149.0); 0 when the pass never
    ran, or ran because of the type. The no-type line reads this."""
    if transcript is None:
        return 0
    given = (transcript.provenance or {}).get("call_system") or {}
    if given.get("found_by") != "phrases":
        return 0
    return int(given.get("heard") or 0)


def mark_if_missed(transcript) -> int:
    """The pass a Transcript never had (v1.147.2): it landed before the
    recording was typed a jail call, or before the switch was on. Given once,
    when the type is set or a check runs; a Transcript that had the pass is
    left alone, and a failure inside never fails the caller. Whether the
    Recording qualifies, by type or by its phrases, is `mark`'s to say."""
    if not on():
        return 0
    if (transcript.provenance or {}).get("call_system") is not None:
        return 0
    try:
        count = mark(transcript)
    except Exception:  # noqa: BLE001 - never fails a type change or a run
        log.exception("the call system's lines could not be marked later")
        return 0
    if count:
        log.info(
            "call system, given later: %d lines on recording %s",
            count,
            transcript.recording_id,
        )
    return count


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
