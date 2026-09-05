"""What the AI assistant is told, built the way the chapter fixes.

Every request is the same shape. The system message is the Ground rules, then
the feature's prompt template, then what the app adds (the answer format). The
user message is the Transcript-nature line, the rendered Transcript, then the
feature's own input. Nothing here talks to the engine; core/assistant.py does
that. Nothing here is logged anywhere.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from core import exports

# The chapter's default wordings, version 1. They live in the database once an
# Admin has saved them; these are what a fresh install starts from and what
# Reset to default restores.
GROUND_RULES = (
    "You are the AI assistant inside Gideon Transcribe, a transcription tool "
    "used by a public defender office. You work only from the transcript you "
    "are given. Never invent facts, names, or quotes. Whenever you refer to "
    "something said, give the time it was said as [hh:mm:ss], copied from the "
    "line it appears on, and never make up a time. When the transcript is "
    "unclear or a name is uncertain, say so. Report what was said, not what it "
    "proves: no legal advice, no opinions on guilt, credibility, or strategy. "
    "Write in plain English."
)

STANDARD_SUMMARY = (
    "Write a summary of this transcript with these parts, in this order, using "
    "these headings.\n"
    "Overview: one short paragraph. What kind of recording this is, who takes "
    "part, and what it is about.\n"
    "Key points: a bulleted list in the order things happen. Each point ends "
    "with the time it happens.\n"
    "Notable statements: short quotes that matter, each with the speaker and "
    "the time. Quote exactly; never paraphrase inside quotation marks.\n"
    "Names, places, and dates: every person, place, organisation, date, and "
    "time of day mentioned, each with the time of its first mention.\n"
    "Unclear parts: stretches where the transcript is garbled, cut off, "
    'overlapping, or hard to follow, with their times. Write "None noticed" '
    "if there are none."
)

CHAT = (
    "Answer the user's questions using only this transcript. If the answer is "
    "not in the transcript, say so in one sentence and do not guess. Quote the "
    "transcript when it helps. Give the time for every statement you rely on "
    "as [hh:mm:ss]. Keep answers short unless the user asks for detail. If a "
    "question asks for legal advice, an opinion on guilt or credibility, or "
    "anything outside the transcript, reply: I can only answer from this "
    "transcript."
)

SUGGESTIONS = (
    "Some speakers in this transcript have no name yet. For each of them, work "
    "out from what is said who they are: a name, if someone says it or is "
    "addressed by it, or otherwise a role such as Interviewer, Interpreter, "
    "Officer, or Caller. Use the known names below when the talk points to one "
    "of them. Give the one line that best shows how you know, and say how sure "
    "you are. Never suggest the same name for two speakers. If nothing shows "
    "who a speaker is, say unknown."
)

# What the app adds after a feature's template: the answer's shape, which no
# Admin edits. The chapter leaves the exact prose text to the build.
SUMMARY_FORMAT = (
    "Write the summary as plain text with each part's heading on its own line, "
    "followed by a colon. Give every time as [hh:mm:ss], copied from the line "
    "it appears on. Do not add parts the template does not ask for."
)
CHAT_FORMAT = (
    "Answer in plain text. Give every time as [hh:mm:ss], copied from the line "
    "it appears on."
)
SUGGESTIONS_FORMAT = (
    "Answer with the JSON asked for. A speaker's label, such as Speaker 3 or "
    "Side 1 Speaker 2, is not a name and not a role: when nothing said shows who "
    "a speaker is, give the name unknown. A name is what someone is called in "
    "the talk; a role is what they do, such as Officer or Interpreter."
)

LENGTH_LINES = {
    "short": "Keep the whole summary under about 250 words.",
    "standard": "Keep the whole summary to about 600 words.",
    "detailed": "Write up to about 1,500 words; be thorough.",
}
ANSWER_CAPS = {"short": 600, "standard": 1200, "detailed": 2500}
CHAT_CAP = 1500
SUGGESTIONS_CAP = 1000
# The history a Chat carries back to the model, in tokens, oldest dropped first.
HISTORY_TOKENS = 16000

# Four characters a token with a ten percent margin, as the chapter fixes, and
# the smallest window any engine standing in for the Shared one must offer.
CHARS_PER_TOKEN = 4
# The margin as a fraction in whole numbers, so the estimate is exact arithmetic
# and 400 characters is 110 tokens rather than a float a hair over it.
MARGIN_NUMERATOR, MARGIN_DENOMINATOR = 11, 10
ENGINE_WINDOW = 131072

SUGGESTIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "speaker": {"type": "string"},
                    "name": {"type": "string"},
                    "kind": {"type": "string", "enum": ["name", "role", "unknown"]},
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                    "line": {"type": "integer"},
                    "quote": {"type": "string"},
                },
                "required": ["speaker", "name", "kind", "confidence", "line", "quote"],
            },
        }
    },
    "required": ["suggestions"],
}


def tokens(text: str) -> int:
    """The app's own estimate of a text's size, never the engine's count."""
    return math.ceil(
        len(text) * MARGIN_NUMERATOR / (CHARS_PER_TOKEN * MARGIN_DENOMINATOR)
    )


def clock(seconds: float) -> str:
    """[hh:mm:ss], the one shape a time takes in a prompt, an answer, or an export."""
    whole = max(0, int(seconds))
    hours, rest = divmod(whole, 3600)
    minutes, secs = divmod(rest, 60)
    return f"[{hours:02d}:{minutes:02d}:{secs:02d}]"


# The Transcript as the model reads it -----------------------------------------


@dataclass
class Line:
    number: int
    segment_id: object
    start: float
    speaker: str
    text: str


def lines_of(transcript) -> list[Line]:
    """One line per Segment, numbered from 1, the second Side's copies left out."""
    lines = []
    for number, segment in enumerate(
        transcript.segments.filter(same_as_other_side=False).order_by("start", "id"),
        start=1,
    ):
        lines.append(
            Line(
                number=number,
                segment_id=segment.pk,
                start=segment.start,
                speaker=(
                    (segment.speaker or "")
                    + (" (corrected)" if segment.corrected else "")
                ),
                text=segment.text,
            )
        )
    return lines


def render(lines: list[Line]) -> str:
    """`[n] [hh:mm:ss] Speaker: text`, or without the label when there is none."""
    out = []
    for line in lines:
        label = f" {line.speaker}:" if line.speaker.strip() else ""
        out.append(f"[{line.number}] {clock(line.start)}{label} {line.text}".rstrip())
    return "\n".join(out)


def nature_line(recording, transcript) -> str:
    """What the Transcript is, from the Provenance, so the model can say so."""
    duration = exports.length_of(recording)
    if transcript.language_mixed:
        where = f"in which {exports.languages_heard(transcript)} were detected"
    else:
        where = (
            f"in {exports.language_name(transcript.language) or 'an unknown language'}"
        )

    if transcript.task_run == "translate":
        first = (
            f"This is an automatic machine translation to English of a {duration} "
            f"recording {where}. The original-language text is not available. "
            "Translation errors are possible."
        )
    else:
        first = (
            f"This is an automatic machine transcription of a {duration} recording "
            f"{where}. It may contain recognition errors."
        )

    if recording.is_two_channel_call:
        second = "The two sides of a phone call are labelled Side 1 and Side 2."
    elif recording.diarize:
        second = "Speakers were separated automatically and may be mislabelled."
    else:
        second = "Speakers were not separated."

    parts = [first, second]
    probability = transcript.language_probability
    if probability is not None and probability < 0.7:
        parts.append("The language was detected with low confidence.")
    if transcript.segments.filter(corrected=True).exists():
        parts.append("Lines marked (corrected) were corrected by staff.")
    return " ".join(parts)


# Citations -----------------------------------------------------------------------

TIME = re.compile(r"\[(\d{1,2}):(\d{2}):(\d{2})\]")


def citations(text: str, lines: list[Line]) -> dict[str, float]:
    """The times in an answer that match a real Segment's start, and their seconds.

    A time is matched when some Segment starts within the same whole second,
    the expected case since the prompts ask the model to copy the start time
    of the line it cites. A time that matches nothing is not a Citation and is
    left as plain text.
    """
    starts: dict[int, float] = {}
    for line in lines:
        starts.setdefault(int(line.start), line.start)
    found: dict[str, float] = {}
    for match in TIME.finditer(text):
        hours, minutes, seconds = (int(part) for part in match.groups())
        whole = hours * 3600 + minutes * 60 + seconds
        if whole in starts:
            found[match.group(0)] = starts[whole]
    return found


# The messages ---------------------------------------------------------------------


def system_message(ground_rules: str, template: str, answer_format: str) -> str:
    return "\n\n".join(part for part in (ground_rules, template, answer_format) if part)


def summary_input(focus: str, length: str) -> str:
    parts = [LENGTH_LINES.get(length, LENGTH_LINES["standard"])]
    if focus.strip():
        parts.append(
            f"Concentrate on: {focus.strip()}. Keep every part, but weight the "
            "content toward this."
        )
    return "\n".join(parts)


def suggestions_input(unnamed: list[str], known: list[str]) -> str:
    return (
        f"Unnamed speakers: {', '.join(unnamed)}\n"
        f"Known names: {', '.join(known) if known else 'none'}"
    )


def fits(*texts: str, answer_cap: int) -> bool:
    """Whether the prompt and the answer fit the engine's window, by the estimate."""
    return sum(tokens(text) for text in texts) + answer_cap <= ENGINE_WINDOW


def history_that_fits(turns: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """The last question-and-answer pairs within the budget, oldest dropped first."""
    kept: list[tuple[str, str]] = []
    used = 0
    for question, answer in reversed(turns):
        cost = tokens(question) + tokens(answer)
        if used + cost > HISTORY_TOKENS:
            break
        kept.insert(0, (question, answer))
        used += cost
    return kept


# Suggestions the app keeps ---------------------------------------------------------

RANK = {"high": 2, "medium": 1, "low": 0}
LABEL = re.compile(r"^(side\d+)?speaker\d+$|^side\d+$")


def looks_like_a_label(name: str) -> bool:
    """Speaker 3, SPEAKER_02, Side 1 Speaker 2: the app's or the engine's own labels."""
    squashed = re.sub(r"[\s_\-]+", "", name).lower()
    return bool(LABEL.match(squashed))


def keep_suggestions(
    raw: list[dict], unnamed: list[str], taken: set[str], lines: list[Line]
) -> list[dict]:
    """The chapter's five checks, in order, on what the model proposed."""
    by_number = {line.number: line for line in lines}
    kept: dict[str, dict] = {}
    for one in raw:
        speaker = str(one.get("speaker", "")).strip()
        name = str(one.get("name", "")).strip()
        confidence = str(one.get("confidence", "")).strip().lower()
        try:
            number = int(one.get("line"))
        except (TypeError, ValueError):
            continue
        if speaker not in unnamed or number not in by_number:
            continue
        if confidence not in ("high", "medium"):
            continue
        if not name or name.lower() == "unknown" or looks_like_a_label(name):
            continue
        if name.casefold() in {held.casefold() for held in taken}:
            continue
        line = by_number[number]
        candidate = {
            "speaker": speaker,
            "name": name,
            "kind": str(one.get("kind", "name")),
            "confidence": confidence,
            "line": number,
            "segment_id": line.segment_id,
            "start": line.start,
            "quote": str(one.get("quote", "")).strip()[:300] or line.text[:300],
        }
        # One suggestion per Speaker: the first, unless a later one is surer.
        already = kept.get(speaker)
        if already is None or RANK[confidence] > RANK[already["confidence"]]:
            kept[speaker] = candidate

    # The same name is never suggested for two Speakers: the higher wins.
    best_for_name: dict[str, dict] = {}
    for candidate in kept.values():
        key = candidate["name"].casefold()
        rival = best_for_name.get(key)
        if rival is None or RANK[candidate["confidence"]] > RANK[rival["confidence"]]:
            best_for_name[key] = candidate
    return [c for c in kept.values() if best_for_name[c["name"].casefold()] is c]
