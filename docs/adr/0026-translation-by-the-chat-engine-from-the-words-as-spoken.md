# 26. Translation is written by the chat engine from the words as spoken, which are kept

Date: 2026-10-26. Status: accepted. Release: not yet built (Phase 1 chapter 7, "Translation from the words as spoken").

## Context

Phase 1 chapter 7 fixed four things about translation: one language per
Run (principle 2); what Whisper produced is the Transcript and no LLM ever
touches the translation path (principle 3, rule 18); the original-language
text is not kept, a user who wants both uploads twice; and chapter 17 ruled
out keeping the original beside the English. The reason given for the
model ban was the second fact: "because the original-language text is not
kept and nothing could check the result".

Two things have changed. Qwen3-ASR (ADR 0025) does not translate, so a
recording recognised by it needs its English from somewhere else; and the
office's chat engine, which already writes the memos, comparisons and
answers, is a Qwen language model that translates Spanish well
(`docs/research/interpreter-languages.md`). The maintainer chose on
2026-10-26 that the engine translates, that the words as spoken are kept
beside the English so a reader can check the English against them, and
that the recording page is not cluttered by it.

Keeping the words as spoken is what answers the old rule's own reason: with
both texts kept, the result can be checked, line by line, by anyone who
reads the language.

## Decision

- **Under Qwen3-ASR a Recording is transcribed in the language spoken
  first**, each Segment carrying its language, and lands readable at once.
- **A translation run follows**, as a Transcript lands with Translate to
  English chosen (or, when the mixed rule applies, found to be mixed): a run
  row like the Speaker check's, one live per Transcript, queued on commit
  to the llm queue, waiting while the engine is away as Summaries tonight
  does. Only lines not in English are sent, in windows cut to a token
  budget, lines numbered, one JSON answer per line, checked line by line;
  each window keeps a signature so a Correction on a spoken line remakes
  only its window's English. The instruction is a Prompt template the
  office can edit; the run has an Expectation key and a time limit; one
  audit row of counts, never a word.
- **Both texts are kept**: `Segment.text` the words as spoken,
  `Segment.english` the engine's rendering (the name the glossary fixes).
  The recording page shows one at a time, the English by default, with one
  switch in the Transcript's head, **English | As spoken**, remembered in
  the browser; nothing is added to a line. The Word export offers "with the
  words as spoken". Search and Find read both texts and say which one a hit
  is in.
- **"English to follow"** is the state while the run waits or works, in
  Vision's family of words ("English, 3 of 12", "English ready"), with one
  Dashboard pill; the batch mail waits for it as it waits for a video's
  prepare.
- **Everything downstream reads the English when it is there** and the
  words as spoken when it is not: Summary, Chat, Case Chat, the Speaker
  check, the exports and their notices.
- **Whisper's own translate stays** as it is for Recordings recognised by
  Whisper; an office with no chat engine keeps Whisper for translation,
  and under Qwen3-ASR Translate to English greys with that reason.

## Consequences

- Phase 1 chapter 7's principles 2 and 3 and rule 18, and chapter 17's
  ruling-out, are reversed for Recordings recognised by Qwen3-ASR; Phase 2's
  copy of the ruling goes with them. For Whisper nothing moves.
- One migration: two columns on Segment and the run's table.
- The engine carries the load: a 30-minute Spanish call is about 4,000
  words read and 4,000 written, a few minutes at the app's pace, inside
  the llm queue's four lanes at `priority` 1, no new shared thing (the box
  ledger's §3 engine terms as they stand).
- The Translation notice is reworded: the English is a machine translation
  by the engine from the words as spoken, which are kept and can be shown.
- The glossary's Translation, Spoken language, Segment, Correction and
  AI assistant entries move; a new word, As spoken, names the second text.
- The faithfulness of the engine's English against Whisper's is the trial's
  open leg: a Spanish call read side by side by the office's reader before
  this ships.
