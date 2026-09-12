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

# The Summary templates the app ships for the Recording types it ships, each
# in the Standard summary's shape: named parts, in order, every point with its
# time, quotes exact. Editable and resettable on the Templates page, like the
# Standard summary; an office reviews them there. Keyed by the template key.
SHIPPED_SUMMARIES = {
    "jail_call": (
        "Write a summary of this recorded jail call with these parts, in this "
        "order, using these headings.\n"
        "Overview: one short paragraph. Who is speaking, how they know each "
        "other as far as the call says, and what the call is about.\n"
        "What is discussed: a bulleted list in the order things come up. Each "
        "point ends with the time it happens.\n"
        "Statements about the case: anything said about the charges, the events "
        "behind them, evidence, witnesses, police, lawyers, court dates, or a "
        "plea, quoted exactly with the speaker and the time. Never paraphrase "
        'inside quotation marks. Write "None noticed" if there are none.\n'
        "Requests and instructions: anything one person asks the other to do, "
        "such as contacting someone, moving money, delivering something, or "
        "saying or not saying something, each with the time.\n"
        "Threats, pressure, or guarded talk: any threat, any pressure on the "
        "other person, and any stretch where the speakers seem to talk around "
        'a subject, each with the time. Write "None noticed" if there are none.\n'
        "Names, places, and dates: every person, place, organisation, date, and "
        "time of day mentioned, each with the time of its first mention.\n"
        "Unclear parts: stretches where the recording is garbled, cut off, "
        'overlapping, or hard to follow, with their times. Write "None noticed" '
        "if there are none."
    ),
    "body_camera": (
        "Write a summary of this body camera recording with these parts, in this "
        "order, using these headings.\n"
        "Overview: one short paragraph. What the encounter is, where it takes "
        "place as far as the recording says, and who takes part.\n"
        "Timeline: a bulleted list of what happens in order, each point ending "
        "with its time: arrival, contact, commands, searches, handcuffing, any "
        "use of force, transport, and the end of the recording.\n"
        "Commands, warnings, and rights: every command, warning, and advisement "
        "of rights spoken by an officer, quoted exactly with the time. Never "
        "paraphrase inside quotation marks.\n"
        "What the person stopped says: their statements, quoted exactly with "
        "the time, and for each whether it answers an officer's question or is "
        "said unprompted.\n"
        "What officers say to each other: statements between officers or over "
        "the radio about the person, the scene, or what to do next, with times.\n"
        "Names, places, and dates: every person, place, organisation, date, and "
        "time of day mentioned, each with the time of its first mention.\n"
        "Unclear parts: stretches where the audio is garbled, cut off, "
        'overlapping, or hard to follow, with their times. Write "None noticed" '
        "if there are none."
    ),
    "interview": (
        "Write a summary of this interview with these parts, in this order, "
        "using these headings.\n"
        "Overview: one short paragraph. Who is interviewed, by whom, and what "
        "the interview is about as far as it says.\n"
        "Questions and answers: the main questions in the order asked, each "
        "with the answer in brief and the time.\n"
        "The account given: the interviewee's account of events, in the order "
        "they tell it, each point with its time.\n"
        "Admissions, denials, and changes: any statement that admits, denies, "
        "or changes an earlier statement, quoted exactly with the time. Never "
        'paraphrase inside quotation marks. Write "None noticed" if there are '
        "none.\n"
        "Rights, promises, and pressure: any advisement of rights, any promise "
        "or offer, any threat or pressure, and any leading or repeated question, "
        'each quoted with the time. Write "None noticed" if there are none.\n'
        "Names, places, and dates: every person, place, organisation, date, and "
        "time of day mentioned, each with the time of its first mention.\n"
        "Unclear parts: stretches where the recording is garbled, cut off, "
        'overlapping, or hard to follow, with their times. Write "None noticed" '
        "if there are none."
    ),
    "phone_call": (
        "Write a summary of this phone call with these parts, in this order, "
        "using these headings.\n"
        "Overview: one short paragraph. Who is speaking, how they know each "
        "other as far as the call says, and what the call is about.\n"
        "Key points: a bulleted list in the order things come up. Each point "
        "ends with the time it happens.\n"
        "Notable statements: short quotes that matter, each with the speaker "
        "and the time. Quote exactly; never paraphrase inside quotation marks.\n"
        "Arrangements made: anything agreed, planned, promised, or asked for, "
        'each with the time. Write "None noticed" if there are none.\n'
        "Names, places, and dates: every person, place, organisation, date, and "
        "time of day mentioned, each with the time of its first mention.\n"
        "Unclear parts: stretches where the recording is garbled, cut off, "
        'overlapping, or hard to follow, with their times. Write "None noticed" '
        "if there are none."
    ),
    "meeting": (
        "Write a summary of this meeting with these parts, in this order, using "
        "these headings.\n"
        "Overview: one short paragraph. What the meeting was about, who took "
        "part, and how it ended.\n"
        "What was decided: a bulleted list of every decision, each with who "
        "made it and the time.\n"
        "Who is to do what: a bulleted list of every task or follow-up agreed, "
        "each with the person it fell to, the date if one was set, and the time "
        'it was agreed. Write "None agreed" if there are none.\n'
        "Questions left open: matters raised and not settled, each with the time.\n"
        "What each person said: for each speaker, their main points in brief, "
        "each with the time.\n"
        "Names, places, and dates: every person, place, organisation, date, and "
        "time of day mentioned, each with the time of its first mention.\n"
        "Unclear parts: stretches where the recording is garbled, cut off, "
        'overlapping, or hard to follow, with their times. Write "None noticed" '
        "if there are none."
    ),
    "dictation": (
        "This transcript is one person dictating a document. Write out the "
        "document they dictated, in their words, and do not summarise.\n"
        "Keep every fact, name, date, number, and instruction; add nothing that "
        "was not said.\n"
        "Remove false starts, repeated words, filler, and asides to the typist, "
        'such as "scratch that" or "delete the last sentence", and do what '
        "they ask.\n"
        "Honour spoken punctuation and layout: new paragraph, full stop or "
        "period, comma, colon, question mark, open quote and close quote, "
        "bullet or number one, heading. Where the speaker gives a heading, make "
        "it a heading.\n"
        "Do not shorten, reorder, or add a greeting, sign-off, or date unless "
        "it was dictated.\n"
        'Where a word is unclear in the transcript, keep it and add "[unclear]" '
        "after it. No timestamps."
    ),
    "hearing": (
        "Write a summary of this court hearing with these parts, in this order, "
        "using these headings.\n"
        "Overview: one short paragraph. What kind of hearing it is, which "
        "court, and who appears, as far as the recording says.\n"
        "Rulings, orders, and dates: every ruling, order, deadline, and date "
        "set by the court, quoted exactly where the judge's words matter, each "
        "with the time. Never paraphrase inside quotation marks.\n"
        "Arguments: each side's points in brief, in the order made, each with "
        "the time.\n"
        "Testimony: each witness, and the substance of what they say, in order, "
        'with times. Write "None" if nobody testifies.\n'
        "What the defendant says: any statement by the defendant, quoted "
        'exactly with the time. Write "None" if there are none.\n'
        "Next steps: what is to happen next and when, with the time it is said.\n"
        "Names, places, and dates: every person, place, organisation, date, and "
        "time of day mentioned, each with the time of its first mention.\n"
        "Unclear parts: stretches where the recording is garbled, cut off, "
        'overlapping, or hard to follow, with their times. Write "None noticed" '
        "if there are none."
    ),
}

CHAT = (
    "Answer the user's questions using only this transcript. If the answer is "
    "not in the transcript, say so in one sentence and do not guess. Quote the "
    "transcript when it helps. Give the time for every statement you rely on "
    "as [hh:mm:ss]. Keep answers short unless the user asks for detail. If a "
    "question asks for legal advice, an opinion on guilt or credibility, or "
    "anything outside the transcript, reply: I can only answer from this "
    "transcript."
)

CASE_CHAT = (
    "Answer the user's questions using only the transcripts of the recordings "
    "in this case. If the answer is not in them, say so in one sentence and do "
    "not guess. Quote the transcripts when it helps. For every statement you "
    "rely on, give the recording and the time as [Recording 3, 00:12:45], "
    "copied from the line it appears on, and never make one up. When several "
    "recordings bear on the question, say which says what. Keep answers short "
    "unless the user asks for detail. If a question asks for legal advice, an "
    "opinion on guilt or credibility, or anything outside these transcripts, "
    "reply: I can only answer from the transcripts in this case."
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
CASE_CHAT_FORMAT = (
    'Answer in plain text. Each recording opens with a line "Recording n of '
    'N"; give every reference as [Recording n, hh:mm:ss], the n from that line '
    "and the time copied from the transcript line it appears on."
)
# The combining call, when a Case was read in parts: plumbing, not a template.
COMBINING = (
    "The same question was answered separately over several parts of one "
    "case's recordings. Write one answer from these part answers. Keep every "
    "[Recording n, hh:mm:ss] reference exactly as written and add none. Where "
    "the parts disagree, say so. If no part found an answer, say the "
    "transcripts do not answer it."
)
SUGGESTIONS_FORMAT = (
    "Answer with the JSON asked for. For every unnamed speaker, suggest a name "
    "when somebody says it or addresses them by it; otherwise suggest a role, "
    "what the speaker does or is in this recording, such as Officer, Sergeant, "
    "Dispatcher, Caller, Interviewer, Interpreter, Suspect, Passenger, or "
    "Witness. A role is the expected answer when no name is spoken; say unknown "
    "only when even a role cannot be told. A speaker's label, such as Speaker 3 "
    "or Side 1 Speaker 2, is never a name or a role."
)

# A Moment: what the camera showed at one time (Phase 4). The template is the
# editable part; the format line and the words the app adds are not. Written
# against what the BodyCam-VQA study found vision models get wrong on this
# kind of footage (docs/research/moments-vision-engine.md): guessing at what
# a thing is, and filling in what was not visible.
MOMENT = (
    "You are shown a short clip from a body-worn or fixed camera, and the words "
    "spoken in it. Say what the camera shows, plainly and briefly, leading with "
    "the thing the words point at. Name people by their clothing, position, "
    "and actions, never by name even if a name is spoken; say what is in their "
    "hands, what vehicles and objects are in view, and what is handled, shown, "
    "or pointed at. Concrete nouns and plain verbs; no preamble, no repeating "
    "the setting, no summary of the words. Do not guess at who anyone is, what "
    "they intend, or what a substance or object is: say a small bag, not drugs; "
    "say a dark object in the right hand, not a gun, unless it is plainly one. "
    "When something is unclear, dark, blurred, or out of frame, say not "
    "visible rather than filling it in. Give a second in the clip, as (3 s), "
    "only when it matters which moment you mean."
)

# The two styles the Moment style setting chooses between; the template above
# is the editable part and these are the app's.
MOMENT_FORMAT_BRIEF = (
    "Answer in plain text, one to three short sentences, no headings and no "
    "list. Never give a [hh:mm:ss] time."
)
MOMENT_FORMAT_FULL = (
    "Answer in plain text, two to five sentences, no headings and no list, "
    "the setting first in one clause. Refer to seconds as the clip runs, from "
    "0 at its start. Never give a [hh:mm:ss] time."
)
MOMENT_FORMAT = MOMENT_FORMAT_BRIEF
MOMENT_CAP = 250

# A question about a moment: the same rules, and a fixed shape for the answer,
# so an attorney's "is that a gun?" comes back as what can and cannot be seen.
QUESTION = (
    "You are shown a few frames from a body-worn or fixed camera at one moment, "
    "the words spoken around it, and a question about the picture. Answer only "
    "from what is visible. Say what is visible: the shape, colour, size, "
    "position, and how it is held or placed. Then say what that is consistent "
    "with, naming the likeliest things plainly, and what cannot be told from "
    "these frames and why (too small, too dark, blurred, hidden, out of frame). "
    "Never name a person. Never state as fact what the frames cannot settle."
)
QUESTION_FORMAT = (
    "Answer in plain text in three short parts, each a sentence or two, "
    "labelled exactly: Visible: ... Consistent with: ... Cannot be told: ... "
    "No headings, no list, never a [hh:mm:ss] time."
)

# What the camera showed, as Summary and Chat are told it: a block after the
# transcript, labelled so the model and the reader both know it is a
# description and not the words.
CAMERA_HEADING = "What the camera showed (a model's descriptions, not the transcript):"

LENGTH_LINES = {
    "short": "Keep the whole summary under about 250 words.",
    "standard": "Keep the whole summary to about 600 words.",
    "detailed": "Write up to about 1,500 words; be thorough.",
}
ANSWER_CAPS = {"short": 600, "standard": 1200, "detailed": 2500}
CHAT_CAP = 1500
SUGGESTIONS_CAP = 1500
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
                    "speaker": {"type": "string", "maxLength": 60},
                    "name": {"type": "string", "maxLength": 60},
                    "kind": {"type": "string", "enum": ["name", "role", "unknown"]},
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                    "line": {"type": "integer"},
                    "quote": {"type": "string", "maxLength": 300},
                },
                "required": ["speaker", "name", "kind", "confidence", "line", "quote"],
            },
        }
    },
    "required": ["suggestions"],
}


def suggestions_schema(unnamed: list[str]) -> dict:
    """The schema with the array bounded: one entry per unnamed Speaker at most.

    Under strict output shaping a small model can repeat entries until the
    cap cuts the JSON off; a bound on the array is the cheapest stop to that.
    """
    import copy

    schema = copy.deepcopy(SUGGESTIONS_SCHEMA)
    schema["properties"]["suggestions"]["maxItems"] = max(1, len(unnamed))
    return schema


def salvage_json(text: str) -> str:
    """A suggestions answer cut off at the cap, closed after its last whole entry.

    Only the entries that were finished are kept; a half-written one goes.
    Anything that is not the expected shape comes back unchanged and fails
    the ordinary way.
    """
    start = text.find("[")
    if start < 0:
        return text
    depth, last_whole = 0, -1
    for at in range(start + 1, len(text)):
        if text[at] == "{":
            depth += 1
        elif text[at] == "}":
            depth -= 1
            if depth == 0:
                last_whole = at
    if last_whole < 0:
        return text
    return text[: last_whole + 1] + "]}"


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


def citations(
    text: str, lines: list[Line], moments: list | tuple = ()
) -> dict[str, float]:
    """The times in an answer that match a real Segment's start, and their seconds.

    A time is matched when some Segment starts within the same whole second,
    the expected case since the prompts ask the model to copy the start time
    of the line it cites. A time that matches nothing is not a Citation and is
    left as plain text. A Moment's time counts as well, since the camera lines
    carry it and an answer may cite what was seen.
    """
    starts: dict[int, float] = {}
    for line in lines:
        starts.setdefault(int(line.start), line.start)
    for moment in moments:
        starts.setdefault(int(moment.at), moment.at)
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


def fits(
    *texts: str, answer_cap: int, window: int | None = None, extra: int = 0
) -> bool:
    """Whether the prompt and the answer fit the engine's window, by the estimate.

    The window is the Engine window setting as the caller read it; without
    one, the chapter's starting value. `extra` is what the estimate cannot
    read from text: a Moment's frames, counted by video_tokens().
    """
    if window is None:
        window = ENGINE_WINDOW
    return sum(tokens(text) for text in texts) + extra + answer_cap <= window


# The camera (Phase 4) ----------------------------------------------------------------
#
# The engine reads a clip as frames, each cut into patches of 28 by 28 pixels
# and every two frames taken together, so a frame's cost is its patches and a
# clip's cost is half its frames' worth. Read from the Qwen3-VL report and
# checked against the office's engine, which charged 226 tokens for a three
# second clip of 320 by 180 at two frames a second.
PATCH = 28


def video_tokens(frames: int, height: int, width: int | None = None) -> int:
    """The app's estimate of what a clip costs the engine, never its count."""
    if frames <= 0 or height <= 0:
        return 0
    width = width or round(height * 16 / 9)
    patches = math.ceil(height / PATCH) * math.ceil(width / PATCH)
    return math.ceil(frames / 2) * patches


def moment_input(lines: list[Line], span_start: float, span_end: float) -> str:
    """The words spoken in the clip, as the model is told them, with the span."""
    head = (
        f"This clip runs from {clock(span_start)} to {clock(span_end)} of the "
        "recording."
    )
    if not lines:
        return f"{head} No words were transcribed in this clip."
    return f"{head} The words spoken in this clip were:\n{render(lines)}"


def question_input(
    lines: list[Line], at: float, span_start: float, span_end: float, question: str
) -> str:
    """The frames' time, the words around it, and the question, as the model is told."""
    head = (
        f"The frames are from {clock(at)} of the recording; the words spoken "
        f"from {clock(span_start)} to {clock(span_end)} were:"
    )
    words = render(lines) if lines else "(none transcribed)"
    return f"{head}\n{words}\n\nThe question: {question.strip()}"


def still_tokens(frames: int, height: int, width: int | None = None) -> int:
    """What a few separate frames cost: each its own patches, none paired."""
    if frames <= 0 or height <= 0:
        return 0
    width = width or round(height * 16 / 9)
    return frames * math.ceil(height / PATCH) * math.ceil(width / PATCH)


def lines_in_span(lines: list[Line], span_start: float, span_end: float) -> list[Line]:
    """The lines that start inside the span; the neighbours when none does."""
    inside = [line for line in lines if span_start <= line.start < span_end]
    if inside:
        return inside
    before = [line for line in lines if line.start < span_start]
    after = [line for line in lines if line.start >= span_end]
    return before[-1:] + after[:1]


def camera_line_text(moment) -> str:
    """A Moment's words with its question in front, when it answered one."""
    question = (getattr(moment, "question", "") or "").strip()
    text = (moment.text or "").strip()
    return f'(asked "{question}") {text}' if question else text


def camera_lines(moments) -> str:
    """The Moments as Summary and Chat are told them, or nothing."""
    said = [f"{clock(one.at)} [camera] {camera_line_text(one)}" for one in moments]
    if not said:
        return ""
    return CAMERA_HEADING + "\n" + "\n".join(said)


# The finder (Phase 4, chapter 3) ----------------------------------------------------
#
# A Cue is a line where the picture would tell what the words cannot. A word
# list cannot tell "look at that bag" from "what was that noise", so the
# finder is one read of the whole Transcript by the engine, asked for lines
# worth seeing and why, in a fixed shape the app checks line by line.
FINDER = (
    "You are reading the transcript of a video recording, a body-worn camera "
    "or a fixed camera. Find the lines where seeing the picture at that time "
    "would add a fact the words do not carry: an object named, handled, "
    "shown, or found (a bag, a phone, a weapon, money, keys, a document, a "
    "container); a command that implies an action (hands out of the window, "
    "step out, on the ground); narration of an action (he is reaching down, "
    "she dropped it, they are running); a pointing phrase with something in "
    "view (look at that, there it is); or a sudden change (shouting, a "
    "struggle, a crash, a door). Ordinary talk that happens to use such words "
    "is not a moment: what was that about a sound, on the ground in a story, "
    "look as a filler, a thing merely mentioned. Choose only lines where the "
    "picture at that time is worth a person's look. Give each its line "
    "number, its kind, one short reason in plain words that names the thing "
    "or the action, and how sure you are. Fewer, better lines beat many."
)
FINDER_FORMAT = (
    "Answer with the JSON asked for: the lines most worth seeing first, none "
    "for a line that merely mentions a thing, and never more entries than the "
    "list allows."
)
FINDER_CAP = 1500

CUE_KINDS = ("object", "command", "action", "pointing", "change")
CONFIDENCE = ("high", "medium", "low")

FINDER_SCHEMA = {
    "type": "object",
    "properties": {
        "cues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "line": {"type": "integer"},
                    "kind": {"type": "string", "enum": list(CUE_KINDS)},
                    "reason": {"type": "string", "maxLength": 120},
                    "confidence": {"type": "string", "enum": list(CONFIDENCE)},
                },
                "required": ["line", "kind", "reason", "confidence"],
            },
        }
    },
    "required": ["cues"],
}


def finder_schema(most: int) -> dict:
    """The schema with the array bounded to the office's most-suggestions setting."""
    import copy

    schema = copy.deepcopy(FINDER_SCHEMA)
    schema["properties"]["cues"]["maxItems"] = max(1, int(most))
    return schema


def finder_input(most: int) -> str:
    return (
        f"List at most {int(most)} lines. Refer to a line by the number in "
        "square brackets at its start."
    )


def keep_cues(raw: list, lines: list[Line], least: str, most: int) -> list[dict]:
    """The finder's answer checked line by line: real lines, sure enough, once each.

    Ordered surest first and then by time, and cut to the most allowed.
    """
    rank = {name: n for n, name in enumerate(CONFIDENCE)}
    floor = rank.get(least, rank["medium"])
    by_number = {line.number: line for line in lines}
    kept: list[dict] = []
    seen: set[int] = set()
    for one in raw:
        if not isinstance(one, dict):
            continue
        try:
            number = int(one.get("line"))
        except (TypeError, ValueError):
            continue
        line = by_number.get(number)
        kind = str(one.get("kind", "")).strip().lower()
        confidence = str(one.get("confidence", "")).strip().lower()
        reason = " ".join(str(one.get("reason", "")).split())[:120]
        if (
            line is None
            or number in seen
            or kind not in CUE_KINDS
            or confidence not in rank
            or rank[confidence] > floor
            or not reason
        ):
            continue
        seen.add(number)
        kept.append(
            {
                "segment_id": line.segment_id,
                "start": line.start,
                "line": number,
                "kind": kind,
                "reason": reason,
                "confidence": confidence,
            }
        )
    kept.sort(key=lambda one: (rank[one["confidence"]], one["start"]))
    return kept[: max(1, int(most))]


def history_that_fits(
    turns: list[tuple[str, str]], budget: int | None = None
) -> list[tuple[str, str]]:
    """The last question-and-answer pairs within the budget, oldest dropped first."""
    if budget is None:
        budget = HISTORY_TOKENS
    kept: list[tuple[str, str]] = []
    used = 0
    for question, answer in reversed(turns):
        cost = tokens(question) + tokens(answer)
        if used + cost > budget:
            break
        kept.insert(0, (question, answer))
        used += cost
    return kept


# Evidence, found before the model is asked ------------------------------------------
#
# A name from text has two honest sources: a self-introduction ("This is
# Detective Ruiz", "my name is Maria"), which names the speaker of that line,
# and a form of address at the edge of a turn ("Maria, ...", "..., thanks
# Maria"), which names the other party. The app finds both with plain patterns
# and hands them to the model with their line numbers, so the model reasons
# from evidence rather than from the whole transcript at once, and a suggested
# name is kept only when the text backs it.

INTRODUCES = re.compile(
    r"\b(?i:this is|my name is|i am|i'm|it's|speaking with|you're speaking to)\s+"
    r"((?:[A-Z][\w'.-]+\s?){1,4})",
)
ADDRESSES = re.compile(
    r"(?:^|(?<=[,.!?] ))((?:[A-Z][\w'.-]+\s?){1,3}),\s"
    r"|,\s((?:[A-Z][\w'.-]+\s?){1,3})[.!?]?$"
)
NOT_NAMES = {
    "i",
    "the",
    "a",
    "an",
    "this",
    "that",
    "it",
    "yes",
    "no",
    "okay",
    "ok",
    "sir",
    "ma'am",
    "man",
    "hey",
    "hello",
    "hi",
    "well",
    "so",
    "and",
    "but",
    "officer",
    "detective",
    "sergeant",
    "your",
    "honor",
    "thank",
    "thanks",
    "please",
    "right",
}


def _clean(name: str) -> str:
    words = [
        w for w in name.strip().strip(".,").split() if w.casefold() not in NOT_NAMES
    ]
    return " ".join(words[:3])


def evidence(lines: list[Line]) -> list[dict]:
    """Every self-introduction and form of address, with its line and speaker."""
    found = []
    for line in lines:
        for match in INTRODUCES.finditer(line.text):
            name = _clean(match.group(1))
            if name:
                found.append(
                    {
                        "kind": "introduces",
                        "line": line.number,
                        "speaker": line.speaker.replace(" (corrected)", ""),
                        "name": name,
                    }
                )
        for match in ADDRESSES.finditer(line.text):
            name = _clean(match.group(1) or match.group(2) or "")
            if name:
                found.append(
                    {
                        "kind": "addresses",
                        "line": line.number,
                        "speaker": line.speaker.replace(" (corrected)", ""),
                        "name": name,
                    }
                )
    return found


def evidence_lines(found: list[dict]) -> str:
    """The evidence as the model reads it, or a plain word when there is none."""
    if not found:
        return (
            "Evidence found in the transcript: none. Only roles can be told, if that."
        )
    out = ["Evidence found in the transcript:"]
    for one in found[:60]:
        if one["kind"] == "introduces":
            who = one["speaker"] or "the speaker"
            out.append(
                f"- line {one['line']}: {who} introduces themselves as {one['name']}"
            )
        else:
            who = one["speaker"] or "the speaker"
            out.append(
                f"- line {one['line']}: {who} addresses someone as {one['name']}"
            )
    return "\n".join(out)


def roles_line(roles: list[str]) -> str:
    return (
        f"Roles to choose from: {', '.join(roles)}"
        if roles
        else "Roles to choose from: any plain role word"
    )


def backed_by_evidence(name: str, found: list[dict]) -> bool:
    """Whether some evidence line carries this name, ignoring case and order."""
    wanted = {w.casefold() for w in name.split()}
    for one in found:
        theirs = {w.casefold() for w in one["name"].split()}
        if wanted & theirs:
            return True
    return False


# Suggestions the app keeps ---------------------------------------------------------

RANK = {"high": 2, "medium": 1, "low": 0}
LABEL = re.compile(r"^(side\d+)?speaker\d+$|^side\d+$")


def looks_like_a_label(name: str) -> bool:
    """Speaker 3, SPEAKER_02, Side 1 Speaker 2: the app's or the engine's own labels."""
    squashed = re.sub(r"[\s_\-]+", "", name).lower()
    return bool(LABEL.match(squashed))


def keep_suggestions(
    raw: list[dict],
    unnamed: list[str],
    taken: set[str],
    lines: list[Line],
    found: list[dict] | None = None,
) -> list[dict]:
    """The chapter's five checks, in order, on what the model proposed.

    With `found`, the evidence-first rule as well: a name (not a role) the
    evidence does not back is dropped, since a name from nowhere is a guess.
    """
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
        kind = str(one.get("kind", "name"))
        if found is not None and kind != "role" and not backed_by_evidence(name, found):
            continue
        line = by_number[number]
        candidate = {
            "speaker": speaker,
            "name": name,
            "kind": kind if found is not None else str(one.get("kind", "name")),
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
