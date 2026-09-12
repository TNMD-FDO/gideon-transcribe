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
        "use of force, transport, and the end of the recording. Where the "
        "camera showed the thing said or done, add it to the same point as "
        '"the camera shows ..." with the camera line\'s time. Leave out camera '
        "lines that only repeat the scene.\n"
        "Commands, warnings, and rights: every command, warning, and advisement "
        "of rights spoken by an officer, quoted exactly with the time. Never "
        "paraphrase inside quotation marks.\n"
        "What the person stopped says: their statements, quoted exactly with "
        "the time, and for each whether it answers an officer's question or is "
        "said unprompted.\n"
        "What officers say to each other: statements between officers or over "
        "the radio about the person, the scene, or what to do next, with times.\n"
        "Seen but not said: what the camera showed that nobody spoke about: an "
        "object, an action, a person in view, a change of place; each as "
        '"the camera shows ..." with its time. Write "None noticed" if there '
        "are none.\n"
        "Names, places, and dates: every person, place, organisation, date, and "
        "time of day mentioned, each with the time of its first mention.\n"
        "Unclear parts: stretches where the audio is garbled, cut off, "
        'overlapping, or hard to follow, with their times. Write "None noticed" '
        "if there are none."
    ),
    "video": (
        "Write a summary of this video recording with these parts, in this "
        "order, using these headings. It has two sources: the transcript, which "
        "is what was said, and, when it is given, the block headed What the "
        "camera showed, which is what a model saw in the picture. Keep them "
        "apart in every sentence.\n"
        "Overview: one short paragraph. What kind of recording this is, where "
        "it is as far as the words or the camera say, who takes part, and what "
        "happens.\n"
        "What happened: a bulleted list in the order things happen, each point "
        "ending with its time. Where the camera showed the thing said or done, "
        'add it to the same point as "the camera shows ..." with the camera '
        "line's time. Leave out camera lines that only repeat the scene.\n"
        "Seen but not said: what the camera showed that nobody spoke about: an "
        "object, an action, a person in view, a change of place; each as "
        '"the camera shows ..." with its time. Write "None noticed" if there '
        "are none.\n"
        "Notable statements: short quotes that matter, each with the speaker "
        "and the time. Quote exactly; never paraphrase inside quotation marks.\n"
        "Names, places, and dates: every person, place, organisation, date, and "
        "time of day mentioned in the words, each with the time of its first "
        "mention. Never a name from the camera.\n"
        "Unclear parts: stretches where the audio is garbled, cut off, "
        "overlapping, or hard to follow, and times the camera could not make "
        'out, with their times. Write "None noticed" if there are none.'
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
    "Answer the user's questions using only this transcript and, when it is "
    "given, the block headed What the camera showed. If the answer is in "
    "neither, say so in one sentence and do not guess. Quote the transcript "
    "when it helps. Give the time for every statement you rely on as "
    '[hh:mm:ss], and write anything from the camera as "the camera shows ..." '
    "with the camera line's time. Asked what was visible at a time, answer "
    "from the camera line nearest it within a minute; when there is none, say "
    "no moment has been described near that time and that one can be asked "
    "for on the Moments tab. Keep answers short unless the user asks for "
    "detail. If a question asks for a legal conclusion, such as whether "
    "someone consented, was under arrest, or was searched lawfully, give what "
    "was said and what the camera showed about it, with times, then say in "
    "one sentence that the conclusion is not something you can answer from a "
    "transcript. If a question asks for legal advice, an opinion on guilt or "
    "credibility, or anything outside the transcript and the camera lines, "
    "reply: I can only answer from this transcript."
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
    "it appears on. Do not add parts the template does not ask for. Where a "
    "part asks for what the camera showed and no block headed What the camera "
    'showed was given, write "No moments were described" under it.'
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
# The legend under the heading: the block's shape, and that the picture was
# looked at only at the listed times.
CAMERA_NOTE = (
    "One line per described moment, in time order. Times not listed were not looked at."
)
# How Summary and Chat use the block (chapter 5): fixed, and put after the
# answer format only when a block is given, so a sound-only Recording pays
# nothing. Two sources kept apart, neither winning, names from the words
# only, nothing inferred from the picture, only the listed times, briefly.
CAMERA_RULES = (
    "The block headed What the camera showed is a model's description of the "
    "picture at the listed times, not the transcript. Use it by these rules.\n"
    "Two sources, kept apart: a fact from the words is cited with its line's "
    'time; a fact from the camera is written as "the camera shows ..." and '
    "cited with the camera line's time. Never put a camera fact and a spoken "
    "fact in one unmarked clause.\n"
    "Precedence: neither wins. The words are the record of what was said; the "
    "camera is the record of what was visible. When they disagree, give both "
    "with their times and say that they differ.\n"
    "Names: a person is named only from the words. The camera's \"a man in a "
    'grey hoodie" stays that even when the words name him; join the two only '
    'side by side, as "the man the officer calls Marcus [00:03:10]; the '
    'camera shows a man in a grey hoodie ... [00:03:12]".\n'
    "Never infer from the camera: not who someone is, not what they intend, "
    "not what an object or substance is beyond what the description says (a "
    "small bag stays a small bag), and not a legal fact such as consent, "
    'arrest, search, or force. "Not visible" is a finding; report it as one.\n'
    "Only listed times: the camera was looked at only at the listed times. Say "
    "nothing about the picture at any other time, and when asked about one, "
    "say no moment was described there.\n"
    "Brevity: a camera fact earns a clause, not a paragraph. Leave out camera "
    "lines that add nothing to the words."
)
# The most the camera block may cost a Summary or a Chat without a Digest,
# past which the app thins it (every asked Moment kept, the record's spread
# evenly). With a Digest the block is not sent at all (chapter 6).
CAMERA_BLOCK_TOKENS = 6000

# The picture record (chapter 6): a span described with the previous span's
# description in hand, so it says what is new and never the room again.
RECORD_NEW = (
    "This clip is one span of a record that covers the whole recording, and "
    "you are told what the clip before it showed. Say only what is new in this "
    "one: what moved, what came into view or left it, what was handled, shown, "
    "or pointed at, and where the camera went. Do not describe the setting "
    "again. If nothing of note changed, answer with one line beginning "
    "Unchanged: and a few words on what is still in view."
)

# The Digest (chapter 6): fixed instructions, never a template. The window's
# words and camera lines come in, a time-ordered record comes out, every line
# saying where it came from, exact quotes kept where a summary will need them.
DIGEST = (
    "You are condensing one window of a recording's transcript, and, when it "
    "is given, the block headed What the camera showed for the same window, "
    "into a record of what happened, in time order. Write one numbered line "
    "per thing that happened, in this shape: the span of time it covers as "
    "[hh:mm:ss]-[hh:mm:ss], then (said), (seen), or (both) for where it comes "
    "from, then what happened in plain words. Keep the exact words inside "
    "quotation marks for any statement about the case or the events behind it, "
    "any request, instruction, threat, or admission, and any name, place, date, "
    "or time of day, each with its line's time. Name a person only as the "
    "words name them; a person the camera shows stays described by clothing "
    "and position. A run of camera lines that say Unchanged is one line. Leave "
    "nothing out that a careful reader would want to know; leave out filler, "
    "repetition, and the setting said twice. Never add what neither source "
    "carries, and never a legal conclusion."
)
DIGEST_FORMAT = (
    "Answer in plain text, numbered lines only, no headings and no preamble. "
    "Every time as [hh:mm:ss], copied from the line or the camera line it "
    "comes from."
)
DIGEST_CAP = 1200
DIGEST_WINDOW_TOKENS = 12000
RECORD_HEADING = (
    "The record of this recording (a model's condensation of the words and the "
    "camera, in time order; every time is the transcript's):"
)
# The camera's stamp (chapter 6): the date, the time and the camera id burned
# into the picture, read from a frame near the start, copied never guessed.
STAMP = (
    "You are shown one frame from a body-worn or fixed camera. Some cameras "
    "burn text into the picture, usually along its top edge: a date, a clock "
    "time, a camera or device id, a badge or a name, a manufacturer. Transcribe "
    "exactly what is burned in, character for character, and nothing else in "
    "the picture. Copy digits as they are printed and never guess a missing or "
    "unclear one: leave the field empty instead. Give the date and the time "
    "exactly as printed, without reordering."
)
STAMP_FORMAT = (
    'Answer with the JSON asked for: {"date": "...", "time": "...", "camera": '
    '"...", "other": "..."}, an empty string for a field the picture does not show.'
)
STAMP_SCHEMA = {
    "type": "object",
    "properties": {
        "date": {"type": "string", "maxLength": 40},
        "time": {"type": "string", "maxLength": 40},
        "camera": {"type": "string", "maxLength": 80},
        "other": {"type": "string", "maxLength": 200},
    },
    "required": ["date", "time", "camera", "other"],
}
STAMP_CAP = 200
CLOCK_TIME = re.compile(r"^(\d{1,2}):(\d{2}):(\d{2})$")


def clock_seconds(text: str) -> int | None:
    """A printed clock time as seconds since midnight, or None when it is not one."""
    match = CLOCK_TIME.match((text or "").strip())
    if not match:
        return None
    hours, minutes, seconds = (int(part) for part in match.groups())
    if hours > 23 or minutes > 59 or seconds > 59:
        return None
    return hours * 3600 + minutes * 60 + seconds


def stamp_line(stamp: dict | None) -> str:
    """The camera's clock as the model is told it, or nothing.

    Never reinterprets the date: the digits go as printed. A time is given
    both as read and as the recording's own zero, so the model can add.
    """
    stamp = stamp or {}
    when = stamp.get("time", "")
    camera = stamp.get("camera", "")
    date = stamp.get("date", "")
    if not (when or camera or date):
        return ""
    parts = ["The camera's own stamp, burned into the picture, read"]
    shown = ", ".join(part for part in (date, when) if part)
    if shown:
        parts.append(
            f"{shown} at {clock(float(stamp.get('at', 0.0)))} of the recording"
        )
    if camera:
        parts.append(f"camera {camera}")
    said = " ".join(parts[:1]) + " " + ", ".join(parts[1:]) + "."
    seconds = clock_seconds(when)
    if seconds is not None:
        zero = (seconds - int(float(stamp.get("at", 0.0)))) % 86400
        hours, rest = divmod(zero, 3600)
        minutes, secs = divmod(rest, 60)
        said += (
            f" So [00:00:00] of the recording was {hours:02d}:{minutes:02d}:{secs:02d} "
            "by the camera's clock, and a time in the recording plus that is the "
            "clock time; give the date as printed, without reordering it."
        )
    if not stamp.get("checked"):
        said += " The stamp was read from one frame and not checked against a second."
    return said


def stamp_row(stamp: dict | None) -> str:
    """The stamp for Details and an export's processing record, or nothing."""
    stamp = stamp or {}
    shown = ", ".join(
        part for part in (stamp.get("date", ""), stamp.get("time", "")) if part
    )
    if not shown and not stamp.get("camera"):
        return ""
    row = shown
    if shown:
        row += f" at {clock(float(stamp.get('at', 0.0)))}"
    if stamp.get("camera"):
        row += (", " if row else "") + f"camera {stamp['camera']}"
    row += (
        " (checked against a second frame)"
        if stamp.get("checked")
        else " (read from one frame)"
    )
    return row


NEAR_HEADING = (
    "What the camera showed at the times asked about (a model's descriptions, "
    "not the transcript):"
)

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


def summary_input(focus: str, length: str, seen: int = 0, digest: bool = False) -> str:
    """The length line, the Focus, and what to make of the picture: the Digest
    when there is one, else the camera block."""
    parts = [LENGTH_LINES.get(length, LENGTH_LINES["standard"])]
    if focus.strip():
        parts.append(
            f"Concentrate on: {focus.strip()}. Keep every part, but weight the "
            "content toward this."
        )
    if digest:
        parts.append(
            "The record of this recording is complete: every stretch of the "
            "words and the picture is in it. Choose what matters for the "
            "summary and leave the rest out rather than listing it; a fact "
            "marked (seen) or (both) is the camera's and is written as the "
            "rules say."
        )
    elif seen > 0:
        lines = "line" if seen == 1 else "lines"
        parts.append(
            f"The camera block has {seen} {lines}; draw on the ones that add "
            "a fact the words do not, and leave the rest out rather than "
            "listing them."
        )
    return "\n".join(parts)


def with_camera_rules(answer_format: str, seen) -> str:
    """The answer format, with the camera rules after it when a block is given."""
    return answer_format + ("\n\n" + CAMERA_RULES if seen else "")


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


def moment_input(
    lines: list[Line], span_start: float, span_end: float, previous: str = ""
) -> str:
    """The words spoken in the clip, as the model is told them, with the span;
    for a record span, what the previous span showed as well."""
    head = (
        f"This clip runs from {clock(span_start)} to {clock(span_end)} of the "
        "recording."
    )
    if not lines:
        said = f"{head} No words were transcribed in this clip."
    else:
        said = f"{head} The words spoken in this clip were:\n{render(lines)}"
    if previous.strip():
        said += f"\n\nThe clip before this one showed: {previous.strip()}"
    return said


def span_of(moment) -> tuple[float, float]:
    """A Moment's span, or its time twice when it has none."""
    start = getattr(moment, "span_start", 0.0) or 0.0
    end = getattr(moment, "span_end", 0.0) or 0.0
    if end > start:
        return start, end
    return moment.at, moment.at


def span_clock(moment) -> str:
    """A Moment's time as the lines print it: its span when it has one."""
    start, end = span_of(moment)
    if end > start:
        return f"{clock(start)}-{clock(end)}"
    return clock(moment.at)


def digest_input(
    number: int, total: int, start: float, end: float, words: str, camera: str
) -> str:
    """One window as the Digest's call is told it."""
    head = (
        f"Window {number} of {total}, from {clock(start)} to {clock(end)} of the "
        "recording. The words spoken in it:"
    )
    parts = [f"{head}\n{words}" if words else f"{head}\n(none transcribed)"]
    if camera:
        parts.append(camera)
    return "\n\n".join(parts)


def digest_block(text: str) -> str:
    """The Digest as Summary, Chat and the Case Chat are told it."""
    if not text.strip():
        return ""
    return RECORD_HEADING + "\n" + text.strip()


TIME_IN_QUESTION = re.compile(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b")


def times_in(question: str, length: float = 0.0) -> list[float]:
    """The times a question names, in seconds: h:mm:ss, or m:ss (read as h:mm
    when that alone fits the recording)."""
    found: list[float] = []
    for match in TIME_IN_QUESTION.finditer(question or ""):
        first, second, third = match.groups()
        if third is not None:
            seconds = int(first) * 3600 + int(second) * 60 + int(third)
        else:
            seconds = int(first) * 60 + int(second)
            if (
                length
                and seconds > length
                and int(first) * 3600 + int(second) * 60 <= length
            ):
                seconds = int(first) * 3600 + int(second) * 60
        if seconds not in found:
            found.append(float(seconds))
    return found


def near_descriptions(moments: list, times: list[float], most: int) -> list:
    """The described Moments whose spans hold the times asked about, else the
    nearest within a minute, at most `most`, in time order."""
    if not times or most <= 0:
        return []
    chosen: dict = {}
    for when in times:
        holding = [
            one
            for one in moments
            if span_of(one)[1] > span_of(one)[0]
            and span_of(one)[0] <= when <= span_of(one)[1]
        ]
        if not holding:
            near = sorted(
                (one for one in moments if abs(one.at - when) <= 60),
                key=lambda one: abs(one.at - when),
            )[:1]
            holding = near
        for one in holding:
            chosen[one.pk] = one
    return sorted(chosen.values(), key=lambda one: one.at)[:most]


def near_block(moments: list) -> str:
    if not moments:
        return ""
    return (
        "\n\n"
        + NEAR_HEADING
        + "\n"
        + "\n".join(
            f"{span_clock(one)} [camera] {camera_line_text(one, mark_edited=True)}"
            for one in moments
        )
    )


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


def camera_line_text(moment, mark_edited: bool = False) -> str:
    """A Moment's words: its question in front when it answered one, and, for
    the model's block, a mark at the end when staff put their own words in,
    so the heading's "a model's descriptions" is honest for every line. The
    exports have their legend and their provenance row for that."""
    question = (getattr(moment, "question", "") or "").strip()
    text = (moment.text or "").strip()
    if question:
        text = f'(asked "{question}") {text}'
    if mark_edited and getattr(moment, "edited", False):
        text = f"{text} (edited by staff)"
    return text


def camera_lines(moments) -> str:
    """The Moments as Summary and Chat are told them, or nothing."""
    said = [
        f"{span_clock(one)} [camera] {camera_line_text(one, mark_edited=True)}"
        for one in moments
    ]
    if not said:
        return ""
    return CAMERA_HEADING + "\n" + CAMERA_NOTE + "\n" + "\n".join(said)


def trim_camera_lines(moments, budget: int = CAMERA_BLOCK_TOKENS) -> list:
    """The Moments whose block fits the budget, in time order.

    Every asked Moment is kept; the record's are spread evenly over the
    recording, fewer each step, until the block fits. Used only without a
    Digest (chapter 6).
    """
    moments = sorted(moments, key=lambda one: one.at)
    if tokens(camera_lines(moments)) <= budget:
        return moments
    kept = [one for one in moments if getattr(one, "source", "") != "interval"]
    intervals = [one for one in moments if getattr(one, "source", "") == "interval"]
    count = len(intervals)
    while count > 0:
        step = len(intervals) / count
        spread = [intervals[int(n * step)] for n in range(count)]
        chosen = sorted(kept + spread, key=lambda one: one.at)
        if tokens(camera_lines(chosen)) <= budget:
            return chosen
        count -= max(1, count // 10)
    return kept


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
