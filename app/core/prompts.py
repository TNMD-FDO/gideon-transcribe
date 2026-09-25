"""What the AI assistant is told, built the way the chapter fixes.

Every request is the same shape. The system message is the Ground rules, then
the feature's prompt template, then what the app adds (the answer format). The
user message is the Transcript-nature line, the rendered Transcript, then the
feature's own input. Nothing here talks to the engine; core/assistant.py does
that. Nothing here is logged anywhere.
"""

from __future__ import annotations

import hashlib
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
    "Write this summary as a memo a member of staff hands to an attorney: what "
    "the recording is, who took part, what happened, and what was said that "
    "matters, so the reader knows the situation without listening to it. "
    "Third person, past tense, plain words. Group what happened by subject, "
    "never minute by minute, and never retell the recording line by line. "
    "Give a time as [hh:mm:ss] only where a reader would want to check the "
    "recording, after the sentence it supports. These parts, in this order, "
    "using these headings.\n"
    "Summary: one paragraph a reader in a hurry could stop at: what kind of "
    "recording this is, who took part, what it was about, what happened, and "
    "how it ended.\n"
    "People: each person who speaks or is spoken of, one line each, with how "
    "the recording identifies them and where: a name only as the words give "
    "it, a role only as the words give it, and otherwise the transcript's own "
    "label for the speaker. Never infer a name or a role from what someone "
    "does.\n"
    "What happened: the substance in a few paragraphs, each on one subject: "
    "what was done and what was said, in your own words, quoting only where "
    "the words themselves matter.\n"
    "Statements that matter: exact quotes that carry weight, each with the "
    "speaker as the transcript labels them and the time. Quote exactly; never "
    "paraphrase inside quotation marks.\n"
    "Names, places, and dates: every person, place, organisation, date, and "
    "time of day mentioned, each with the time of its first mention.\n"
    "Unclear parts: stretches where the transcript is garbled, cut off, "
    'overlapping, or hard to follow, with their times. Write "None noticed" '
    "if there are none."
)


def text_hash(text: str) -> str:
    """The short hash a stored template keeps of the shipped wording it took,
    so an upgrade can tell an unedited copy from an office's own words."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# Every shipped wording each template has carried, by its hash, so a copy
# stored before the hash was kept can still be told unedited (v1.53.0). A
# hash is added here whenever a shipped text changes; nothing is removed.
SHIPPED_HISTORY = {
    "standard": ("77493e20d40da8c2", "f76d2d1e0c15c0de"),
    "video": ("2e247929fe7a40eb", "29aa0cb5855e3303", "4ed91dd19571870e"),
    "jail_call": ("05d6764a931302ea",),
    "body_camera": (
        "c7815e388b0aa161",
        "4f92a41fd993cfd1",
        "aa5c4e55f36ddebb",
        "e420ebc4c6b26842",
    ),
    "interview": ("8b9b3615694561bb",),
    "phone_call": ("c139726a47bb696e",),
    "hearing": ("3d40afd97acf18f4",),
    "dictation": ("8f9d3f1bc76a9956",),
    "meeting": ("f6b5d89ac94a5842",),
    "prompt:ground_rules": ("7a65498ab25fbf63",),
    "prompt:chat": ("0db99390974f3bef", "a31c1f00877b1dce"),
    "prompt:suggestions": ("122c6e749064c4d6",),
    # Re-shipped in v1.87.1: the record of what the camera showed is named.
    "prompt:case_chat": ("0003b7162b10fbfd", "6ad6dc860e5113fb", "235d9d531fff0035"),
    "prompt:moment": ("e995c610e187a63d", "e9c80701c0ab577f"),
    "prompt:digest": ("c19b8288923ed5e9", "09bca7a6668b3994"),
    "prompt:speaker_check": ("c53a7a37eb2a8f1f",),
    # Re-shipped in v1.64.0 (Phase 7 chapter 2): the investigator's ask with
    # the why line, and the memo in an investigator's voice.
    "prompt:incident_events": ("6414affa68b3ecb0", "548dcd1608ba79ea"),
    "prompt:incident_memo": ("bd737802d03d8bd6", "49543deef4508ef9"),
    "prompt:incident_chat": ("1e49dfacd7a8a160",),
}


# The Summary templates the app ships for the Recording types it ships, each
# a memo to the attorney in the Standard summary's shape: named parts, in
# order, grouped by subject, a time only where a reader would check, quotes
# exact. Editable and resettable on the Templates page, like the Standard
# summary; an office reviews them there. Keyed by the template key.
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
        "Write this summary of a body camera recording as a memo a member of "
        "staff hands to an attorney, from what was said and what the camera "
        "showed together: what the encounter was, who took part, what happened, "
        "and what was said and seen that matters, so the reader knows the "
        "situation without watching it. Third person, past tense, plain words, "
        "one account, never saying which sentence came from the words and which "
        "from the picture. Group what happened by subject, never minute by "
        "minute, and never retell the recording line by line. Give a time as "
        "[hh:mm:ss] only where a reader would want to check the recording, "
        "after the sentence it supports. These parts, in this order, using "
        "these headings.\n"
        "Summary: one paragraph a reader in a hurry could stop at: what the "
        "encounter was, where it was as far as the recording says, who took "
        "part, what happened, and how it ended.\n"
        "People: each person who speaks, is spoken of, or is in view, one line "
        "each, with how the recording identifies them and where: a name only "
        "as the words give it, a role such as officer only as the words give "
        "it, and otherwise the transcript's own label for the speaker; a person "
        "seen only in the picture is described by clothing, position, or what "
        "they did, never named. Never infer a name or a role from what someone "
        "does or wears.\n"
        "What happened: the encounter in a few paragraphs, each on one subject: "
        "how it began, what the officers did and said, what the person "
        "contacted did and said, any search, handcuffing, use of force, or "
        "transport, and how it ended; what was done, said, and in view as one "
        "account, in your own words, quoting only where the words themselves "
        "matter.\n"
        "Commands, warnings, and rights: every command, warning, and advisement "
        "of rights spoken, quoted exactly with the speaker as the transcript "
        "labels them and the time. Never paraphrase inside quotation marks.\n"
        "Statements that matter: exact quotes that carry weight, each with the "
        "speaker as the transcript labels them and the time, and for the person "
        "contacted whether it answered a question or was said unprompted.\n"
        "Names, places, and dates: every person, place, organisation, date, and "
        "time of day mentioned in the words, each with the time of its first "
        "mention.\n"
        "Unclear parts: stretches where the audio is garbled, cut off, "
        "overlapping, or hard to follow, and stretches the camera could not "
        'make out, with their times. Write "None noticed" if there are none.'
    ),
    "video": (
        "Write this summary of a video recording as a memo a member of staff "
        "hands to an attorney, from what was said and what the camera showed "
        "together: what the recording is, who took part, what happened, and "
        "what was said and seen that matters, so the reader knows the situation "
        "without watching it. Third person, past tense, plain words, one "
        "account, never saying which sentence came from the words and which "
        "from the picture. Group what happened by subject, never minute by "
        "minute, and never retell the recording line by line. Give a time as "
        "[hh:mm:ss] only where a reader would want to check the recording, "
        "after the sentence it supports. These parts, in this order, using "
        "these headings.\n"
        "Summary: one paragraph a reader in a hurry could stop at: what kind of "
        "recording this is, where it was as far as the recording says, who took "
        "part, what happened, and how it ended.\n"
        "People: each person who speaks, is spoken of, or is in view, one line "
        "each, with how the recording identifies them and where: a name only "
        "as the words give it, a role only as the words give it, and otherwise "
        "the transcript's own label for the speaker; a person seen only in the "
        "picture is described by clothing, position, or what they did, never "
        "named. Never infer a name or a role from what someone does or wears.\n"
        "What happened: the substance in a few paragraphs, each on one subject: "
        "what was done, said, and in view, as one account in your own words, "
        "quoting only where the words themselves matter.\n"
        "Statements that matter: exact quotes that carry weight, each with the "
        "speaker as the transcript labels them and the time. Quote exactly; "
        "never paraphrase inside quotation marks.\n"
        "Names, places, and dates: every person, place, organisation, date, and "
        "time of day mentioned in the words, each with the time of its first "
        "mention.\n"
        "Unclear parts: stretches where the audio is garbled, cut off, "
        "overlapping, or hard to follow, and stretches the camera could not "
        'make out, with their times. Write "None noticed" if there are none.'
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
    "in this case and, where a recording has one, its record of what the "
    "camera showed. If the answer is not in them, say so in one sentence and "
    "do not guess. Quote the transcripts when it helps. For every statement you "
    "rely on, give the recording and the time as [Recording 3, 00:12:45], "
    "copied from the line it appears on, and never make one up. When several "
    "recordings bear on the question, say which says what. Keep answers short "
    "unless the user asks for detail. If a question asks for legal advice, an "
    "opinion on guilt or credibility, or anything outside these transcripts, "
    "reply: I can only answer from the transcripts in this case. When a "
    "recording is a camera of an incident whose clock you were given and the "
    "question asks when something happened, give the time of day by the "
    "cameras' clock beside the reference; asked what another camera showed at "
    "that moment, read that camera at the same time of day, and say when it "
    "had not started or had stopped."
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

SPEAKER_CHECK = (
    "The speakers of this transcript were told apart by their voices, and some "
    "lines were given to the wrong speaker. Read the lines and find the ones "
    "whose words show they belong to a different speaker than the one they "
    "are labelled with: a question and its answer given to the same speaker, "
    "a person addressed by name answering under the name of the one who "
    "asked, a command given by the person it is labelled as receiving. Move a "
    "line only to a speaker already in the list of speakers. Never invent a "
    "speaker, never merge speakers, never change any words. Suggest a move "
    "only when the words make it clear; when either speaker could have said "
    "the line, leave it. Give a reason of a few words for each move."
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
    "and the time copied from the transcript line it appears on. Every line "
    "of a list carries the reference of the line it rests on, copied from "
    "that line; a list never repeats one reference for several lines."
)
# The combining call, when a Case was read in parts: plumbing, not a template.
COMBINING = (
    "The same question was answered separately over several parts of one "
    "case's recordings, each part reading different recordings. Write one "
    "answer from these part answers, in time order by the cameras' clock "
    "where the parts give one. A difference between parts is what different "
    "recordings covered, not a disagreement: name a disagreement only where "
    "two parts describe the same moment and say different things. Keep every "
    "[Recording n, hh:mm:ss] reference exactly as written and add none. Leave "
    "out a part's report that its recordings do not mention something, unless "
    "no part found an answer; then say the transcripts do not answer it."
)


def part_line(part: int, parts: int, numbers: list[int], total: int) -> str:
    """What one Reading is told when a case is read in parts (v1.87.0): which
    recordings it holds, so it never mistakes its share for the whole case."""
    held = [f"Recording {n}" for n in sorted(numbers)]
    held_words = ", ".join(held[:-1]) + " and " + held[-1] if len(held) > 1 else held[0]
    return (
        f"This is part {part} of {parts} of the case's recordings: it holds "
        f"{held_words} of {total}. The other parts hold the rest and are asked "
        "the same question separately. Answer from these recordings alone, and "
        "never say the case lacks something they do not contain; say instead "
        "that these recordings do not mention it."
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
# The assistant on the Incident (Phase 6 chapter 3). Proposed events: one
# camera at a time, its record or its transcript, and the events that stand.
INCIDENT_EVENTS = (
    "You are an investigator reading one camera of an incident for the office "
    "that defends the accused. You are given the record of what happened on "
    "this camera (a condensation of its words and its picture) or its "
    "transcript, one stretch at a time, with the camera's start by the "
    "incident's clock. Propose the moments in this stretch that could matter "
    "to the case: a thing that happened that a member of staff would put on "
    "the incident's chronology and could point to in the record. Judge "
    'significance yourself: a fragment can matter ("I got, I got gun"), an '
    "answer can matter more than the question, a thing seen once can matter; "
    "and most lines of a record do not matter, so leave them out. To help the "
    "judgement and not to bound it, moments that usually matter include a "
    "person or a vehicle arriving, leaving or being stopped; a command, a "
    "warning or an advisement of rights; a question about consent or a search "
    "and its answer; a search, a restraint, a use of force, a weapon drawn, "
    "shown or mentioned, an injury, an arrest as the words or the picture "
    "describe it and never as a conclusion (say handcuffs were put on, not "
    "that someone was arrested); a statement that carries weight, an "
    "admission, a denial, a threat; a thing handed over, found, seized or "
    "taken; a move to another place; a person or a vehicle identified; the "
    "camera starting, stopping or being muted. Not an event: the picture "
    "changing, the camera moving, a vehicle driving with nothing happening, "
    "weather, scenery, a description of clothing or surroundings on its own, "
    "small talk, radio chatter that changes nothing. At most twelve in a "
    "stretch, the ones that matter most first. For each: the line, one "
    "sentence in your own plain words saying what happened, third person, "
    "past tense, up to 120 characters, never a copy of the record's line and "
    'never beginning "the camera" or "the view" ("An officer said he had '
    'found a gun", not "Speaker 4 said, \'I got gun\'"); why it matters, one '
    "line, up to 160 characters; and the first six to ten words of the "
    "record's line it rests on, copied exactly. A speaker's numbered label "
    "(Speaker 1, Speaker 4) is this camera's alone and means nothing on "
    "another camera: name a person only by a name the words give; otherwise "
    "say what was said, and who said it only as the words make plain (an "
    "officer, the man on the ground). Do not propose anything already on the "
    "list of events given; propose only what this stretch adds."
)
INCIDENT_EVENTS_FORMAT = (
    "Answer with the JSON asked for: a list under events, each item the time "
    "in this recording as hh:mm:ss copied from the line it rests on, an end as "
    "hh:mm:ss when the thing ran a while or an empty string, text (the line in "
    "your own words), why (why it matters), and rests_on (the first six to ten "
    "words of the record's line, copied exactly). An empty list when this "
    "stretch adds nothing."
)
# The second look at a stretch (Phase 7 chapter 2): the same lines again,
# against what the first look proposed.
INCIDENT_EVENTS_SECOND_LOOK = (
    "Read the same stretch again against the events you proposed, listed "
    "below. What did you leave out that an investigator for the defence would "
    "want on the chronology, and why? Propose only what is missing and "
    "matters; the same shape of answer; an empty list when nothing is missing."
)
# The Incident memo: a memo across cameras, written on the chronology.
INCIDENT_MEMO = (
    "Write the memo a seasoned investigator hands to the attorney on the case "
    "about one incident seen across several cameras, from the incident record "
    "and the chronology given. Say what happened, who did what and what was "
    "said, in the order it happened, grouped by subject and never minute by "
    "minute, and point at the evidence for each fact: the time of day, the "
    "camera it comes from and the event's number. Third person, past tense, "
    "plain words, short sentences. Never narrate the footage: do not write "
    "that the camera view shifted, that the footage shows or that the video "
    "captures; describe what a camera showed only where the picture is the "
    "evidence for a fact (a handgun lay on the passenger seat, BWC2-098702 at "
    "the time). The chronology's events are the spine and the office's notes "
    "are the office's reading of them; contradict neither. The parts, in this "
    "order, each heading on its own line followed by a colon. Summary: one "
    "paragraph a reader in a hurry could stop at, with the date and the times "
    "of day the incident ran. The cameras: one line each, what the camera is, "
    "when it starts and ends by the clock, and whose it is only as the words "
    "say. People: each person who speaks, is spoken of, or is in view, with "
    "how the record identifies them and where, and which cameras show them; a "
    "name only as the words give it, a role only as the words give it, a "
    "person seen only in the picture by clothing, position or what they did, "
    "never named. What happened: the substance in a few paragraphs, each on "
    "one subject, the chronology's events in their order, and what each "
    "camera adds where it adds something. Commands, warnings, and rights: "
    "every command, warning and advisement of rights spoken, quoted exactly, "
    "with the speaker as the words name them, the time of day and the camera "
    "it was heard on. Statements that matter: exact quotes that carry weight, "
    "with who said them as the words make plain, the time and the camera, and "
    "whether it answered a question or was said unprompted. Names, places, "
    "and dates. Unclear parts: a stretch no camera showed, a thing the cameras "
    "or the words disagree on, and an event the record does not bear out, "
    "said plainly. No closing section of points for the attorney: the memo "
    "ends at the facts."
)
# Gideon on the incident page (Phase 7 chapter 5): questions answered from
# the incident record and the chronology, in the investigator's voice.
INCIDENT_CHAT = (
    "You answer questions about one incident seen across several cameras, "
    "for the office that defends the accused, from the incident record and "
    "the chronology given and nothing else. Answer as an investigator "
    "reports: what happened, who did what and what was said, pointing at the "
    "evidence for each fact with the time of day on the incident's clock and "
    "the camera it comes from. Cite every time as [hh:mm:ss] exactly as the "
    "record gives it. Name a camera by its id. Never narrate the footage (do "
    "not write that the camera view shifted or the footage shows); describe "
    "what a camera showed only where the picture is the evidence for a fact. "
    "Never a legal conclusion: say handcuffs were put on, not that someone "
    "was arrested. A speaker's numbered label belongs to one camera and "
    "means nothing on another; attribute a line to a person only by a name "
    "the words give or the office set, otherwise to the camera it was heard "
    "on. When the record does not hold the answer, say so plainly and say "
    "what it does hold. Plain words, short sentences, no preamble."
)
# The comparison (Phase 8 chapter 4, part 3): a report's pages against the
# record, one finding per row, both sides cited.
COMPARISON = (
    "You compare a police report with the record of what the cameras "
    "recorded, for the office that defends the accused. The report is the "
    "officer's account; the record is the cameras' words and pictures on one "
    "clock, with the chronology the office wrote. Go through the report's "
    "paragraphs given and, for each claim of fact that the record can speak "
    "to, say whether the record agrees with it, differs from it, or shows "
    "nothing about it. Cite the paragraph the claim is in by its page and "
    "paragraph number, and the moment on the record by its time. A "
    "description of the picture is a description, not a fact; say what was "
    "said and what was seen, and never what it means in law. Where the "
    "report's words may be misread (a scan), say so in the why. Prefer few "
    "findings that matter to many that do not; skip headings, form fields "
    "and boilerplate. Plain words, one short sentence each."
)
COMPARISON_FORMAT = (
    'Answer with JSON only: {"findings": [{"page": 4, "paragraph": 2, '
    '"claim": "the report says what, in a few words", "at": "hh:mm:ss", '
    '"mark": "agrees" or "differs" or "not_on_camera" or "not_in_report", '
    '"why": "one sentence"}]}. The page and paragraph copied from the line '
    "the claim appears on; the time copied from the record or the "
    "chronology, left empty only for not_on_camera. For not_in_report the "
    "claim is the event or moment the report leaves out, with its time, and "
    "page and paragraph empty. No other text."
)
INCIDENT_CHAT_FORMAT = (
    "Answer in plain text. Give every time as [hh:mm:ss] copied from the "
    "record or the chronology. Keep to the question."
)
INCIDENT_MEMO_FORMAT = (
    "Write the memo as plain text with each part's heading on its own line, "
    "followed by a colon. Give every time as [hh:mm:ss] copied from the record "
    "or the chronology. Do not add parts the template does not ask for."
)
# The incident rules, fixed: the clock, the events' marks, the cameras, and
# the labels (a numbered label is one camera's alone).
INCIDENT_RULES = (
    "This memo is written across the cameras of one incident, on one clock. "
    "Every time is the time of day by the incident's clock, written as "
    "[hh:mm:ss] exactly as the record and the chronology give it, never a "
    "recording's own elapsed time. A sentence that rests on one of the "
    "chronology's events carries the event's number after its time, as "
    "(Event 4); the memo never contradicts an event, and where the record "
    "does not bear an event out, Unclear parts says so. What one camera shows "
    "and another does not is said by the camera's name. A camera's "
    "description of the picture stays a description. A speaker's numbered "
    "label (Speaker 1, Speaker 4) belongs to one camera and means nothing on "
    "another: attribute a line to a person only by a name the words give or "
    "the office set, otherwise to the camera it was heard on. Cover every "
    "camera in the record and name none that is not in it. The office's "
    "notes, on the incident and on its events, are the office's own words: "
    "respect them, never contradict or rewrite them, and where an event is "
    "marked to check say that the office has not settled the point."
)
SPEAKER_CHECK_FORMAT = (
    "Answer with the JSON asked for: a list under moves, each item the line's "
    "number as shown in brackets, the speaker the line is labelled with as "
    "shown, the speaker it belongs to from the list of speakers, and a reason "
    "of a few words. An empty list when nothing should move."
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
    "The block headed What the camera showed, and a record line marked (seen) "
    "or (both), is a model's description of the picture at the listed times, "
    "not the transcript. Use it by these rules.\n"
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
# The guardrails a Summary keeps when it is written as one account from the
# Digest (chapter 7): the reader is not told which source each sentence came
# from, so the rules that protect the reader stay and the two-source wording
# goes.
NARRATIVE_RULES = (
    "The record of this recording joins what was said and what the camera "
    "showed; write one account from both and do not label which source a "
    "sentence came from. Keep these rules whatever the account says. Names "
    "and roles: a person is named, or given a role such as officer or "
    "homeowner, only as the words give it, and the memo says where; otherwise "
    "the transcript's label for the speaker is used as it is, and a person "
    "only the camera shows is described by clothing, position, or what they "
    "do, never given a name or a role. Objects: a thing stays what the "
    "description saw (a small bag stays a small bag) and is never called "
    "more. Never state a legal fact such as consent, arrest, search, or force "
    "as a conclusion; say what was done and said. A stretch the camera could "
    "not make out is reported as not visible, not filled in. A time is "
    "[hh:mm:ss] copied from the record, given only where a reader would want "
    "to check."
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
    "from, then what happened in plain words, in the third person and the "
    "past tense. One time per line, the span's, and no other: never a time "
    "after a quotation or inside the line. Quote exactly, inside quotation "
    "marks, only words that carry weight: a statement about the case or the "
    "events behind it, a request, an instruction, a warning, a threat, an "
    "admission, a denial, a promise, or an advisement of rights, with the "
    "speaker as the transcript labels them; report everything else in your "
    "own words. Fold agreement, filler, repetition, and small talk into a "
    "phrase, or leave it out. Keep every name, place, date, and time of day "
    "the words give. Name a person only as the words name them; a person the "
    "camera shows stays described by clothing and position. Use a camera line "
    "only where it adds what the words do not, and a run of camera lines that "
    "say Unchanged is no line at all. Leave nothing out that a careful reader "
    "would want to know; leave out the setting said twice. Never add what "
    "neither source carries, and never a legal conclusion."
)
DIGEST_FORMAT = (
    "Answer in plain text, numbered lines only, no headings and no preamble. "
    "Every time as [hh:mm:ss], copied from the line or the camera line it "
    "comes from."
)
DIGEST_CAP = 1200
DIGEST_WINDOW_TOKENS = 4000
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
ANSWER_CAPS = {"short": 800, "standard": 1600, "detailed": 3500}
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


def speaker_check_schema(speakers: list[str]) -> dict:
    """The Speaker check's answer: a list of moves, each to a Speaker already
    on the Transcript, so the engine cannot answer with a name of its own."""
    return {
        "type": "object",
        "properties": {
            "moves": {
                "type": "array",
                # Room for a whole swapped stretch (v1.56.0); the answer cap
                # is the real ceiling, and a cut-off list is said on the page.
                "maxItems": 400,
                "items": {
                    "type": "object",
                    "properties": {
                        "line": {"type": "integer"},
                        "from": {"type": "string"},
                        "to": {"type": "string", "enum": list(speakers)},
                        "reason": {"type": "string"},
                    },
                    "required": ["line", "from", "to", "reason"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["moves"],
        "additionalProperties": False,
    }


def incident_events_schema() -> dict:
    """The proposals' answer: a list of events, each a time, an end, a line
    and the words it rests on."""
    return {
        "type": "object",
        "properties": {
            "events": {
                "type": "array",
                "maxItems": 12,
                "items": {
                    "type": "object",
                    "properties": {
                        "time": {"type": "string"},
                        "end": {"type": "string"},
                        "text": {"type": "string"},
                        "why": {"type": "string"},
                        "rests_on": {"type": "string"},
                    },
                    "required": ["time", "end", "text", "why", "rests_on"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["events"],
        "additionalProperties": False,
    }


def incident_events_input(
    camera: str,
    starts: str,
    ends: str,
    nature: str,
    known: list[str],
    context: str = "",
    look_for: str = "",
) -> str:
    """One camera as the proposals read it: its place on the clock, the
    events that stand, the office's context and what this run looks for
    (Phase 7 chapter 2), and what follows is one stretch of its record or
    its transcript."""
    listed = "\n".join(known) if known else "none yet"
    parts = [
        f"Camera {camera} starts {starts} and ends {ends}. Times in the lines "
        "below are this recording's own, from its start.",
        f"Events already on the chronology, by the incident's clock:\n{listed}",
    ]
    if context:
        parts.append(f"About the office and its cases: {context}")
    if look_for:
        parts.append(f"For this run the office asks you to look for: {look_for}")
    parts.append(f"What follows is one stretch of {nature}:")
    return "\n\n".join(parts)


def comparison_input(
    head: str, events: list[str], record: str, paragraphs: str, *, first: int, last: int
) -> str:
    """One window of the report against the whole record."""
    listed = "\n".join(events) if events else "none."
    return "\n\n".join(
        [
            head,
            "The chronology, as the office wrote it:\n" + listed,
            "The record (every time is by that clock, and each line names the "
            "camera it comes from):\n" + record,
            f"The report, pages {first} to {last} (each paragraph on its own line, "
            "with its page and paragraph number in front):\n" + paragraphs,
            "Compare these pages of the report with the record: for each claim of "
            "fact, agrees, differs or not_on_camera, with the paragraph and the "
            "moment. Do not report what the report leaves out here.",
        ]
    )


def comparison_left_out_input(head: str, events: list[str], paragraphs: str) -> str:
    """The chronology against the whole report: what the report leaves out."""
    return "\n\n".join(
        [
            head,
            "The chronology, as the office wrote it:\n" + "\n".join(events),
            "The whole report (each paragraph on its own line):\n" + paragraphs,
            "Which events of the chronology does the report not mention at all? "
            "Give each as not_in_report with the event's time as at and its line "
            "as the claim, page and paragraph empty. An event the report mentions "
            "anywhere, in any words, is not a finding. No other marks.",
        ]
    )


def incident_memo_input(
    cameras_line: str, events: list[str], record: str, about: str = ""
) -> str:
    """What the memo is written from: the cameras, the office's About, the
    chronology with its notes, the record."""
    listed = "\n".join(events) if events else "none; write on the record alone."
    return "\n\n".join(
        [
            cameras_line,
            *(
                ["The office's note on the incident:\n" + about]
                if about.strip()
                else []
            ),
            "The chronology, as the office wrote it:\n" + listed,
            "The incident record (the cameras' records merged onto the incident "
            "clock; every time is by that clock, and each line names the camera "
            "it comes from):\n" + record,
            LENGTH_LINES["detailed"],
        ]
    )


def speaker_check_input(lines: list, speakers: list[str]) -> str:
    """One window as the engine reads it: the Speakers it may move a line to,
    then the lines with their numbers, times and labels."""
    return f"Speakers: {', '.join(speakers)}\n\nLines:\n{render(lines)}"


def plain_speaker(label: str) -> str:
    """A line's Speaker as labelled, without the corrected mark a rendered
    line carries."""
    return label.replace(" (corrected)", "").strip()


def keep_corrections(raw: list, lines: list, speakers: list[str]) -> list[dict]:
    """The moves that pass every check: a line of this window, a Speaker on
    the Transcript, the label still what the engine was shown, and a move
    to somebody else. One per line; the rest are dropped without a word."""
    by_number = {line.number: line for line in lines}
    allowed = set(speakers)
    kept: dict = {}
    for one in raw:
        if not isinstance(one, dict):
            continue
        try:
            line = by_number[int(one.get("line"))]
        except (KeyError, TypeError, ValueError):
            continue
        to = str(one.get("to", "")).strip()
        labelled = plain_speaker(line.speaker)
        if to not in allowed or to == labelled:
            continue
        if plain_speaker(str(one.get("from", ""))) != labelled:
            continue
        if line.segment_id in kept:
            continue
        kept[line.segment_id] = {
            "segment_id": line.segment_id,
            "start": line.start,
            "quote": line.text[:300],
            "from": labelled,
            "to": to,
            "reason": str(one.get("reason", "")).strip()[:120],
        }
    return list(kept.values())


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
            "words and the picture is in it. Write one account from it, choose "
            "what matters, and leave the rest out rather than listing it."
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


# A Digest's lines are marked, and until v1.87.1 nothing told the model what
# the marks meant or that the picture belongs in an account of what happened:
# asked for a timeline over twelve cameras, it left the camera out.
RECORD_RULES = (
    "A record's lines are marked: (said) is what the words say; (seen) is what "
    "the camera showed at that time and not the words; (both) is both. A line "
    "marked (seen) or (both) is a camera fact: use it under the camera rules, "
    'written as "the camera shows ..." and cited with its line\'s time. Asked '
    "what happened, for a timeline, or what a stretch shows, give what the "
    "camera showed alongside what was said, in time order; the picture is part "
    "of the record and is never left out because the question said transcript. "
    "In a timeline or a list, a line that rests on the picture begins with "
    "Camera: so a reader can tell a description from a spoken fact."
)


def with_record_rules(answer_format: str) -> str:
    """The answer format, the camera rules and the record's marks after it,
    for a call that reads a Digest (v1.87.1)."""
    return answer_format + "\n\n" + CAMERA_RULES + "\n\n" + RECORD_RULES


def with_narrative_rules(answer_format: str) -> str:
    """The answer format with the one-account guardrails (a Summary from the Digest)."""
    return answer_format + "\n\n" + NARRATIVE_RULES


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
