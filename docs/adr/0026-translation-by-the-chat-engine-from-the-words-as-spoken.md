# 26. Translation is written by the chat engine from the words as spoken, which are kept

Date: 2026-10-26. Status: accepted. Release: v1.162.0, 2026-10-27 (Phase 1 chapter 7, "Translation from the words as spoken").

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

## Settled by the build (v1.162.0)

- The signature is per line, not per window: `Segment.english_of` is a
  short hash of the spoken text the English came from, so a Correction
  leaves that one line stale and the next run sends it with its neighbours
  for context and writes only it. Nothing outside the corrected line
  changes, which is what the rule protects, with no window table.
- Three columns on Segment (`language`, `english`, `english_of`) and one
  run row, `Translation`, beside the Speaker check's, with the same one
  live run per Transcript; migration 0092.
- The run waits for the engine where the Speaker check fails at once: a
  queued run the engine cannot take keeps `engine_away` and the minute
  sweep queues it again once the engine answers the minute check; past
  eight hours the pages say the engine was away all night.
- The windows are cut by the Digest's rule under the Digest window tokens
  setting, held under a quarter of the engine's window, with up to three
  lines of context either side marked as such; the answer's room is twice
  the source. A run goes over its lines twice; a line still unwritten is
  counted, said on the pages, and offered to Translate again on the
  Details tab.
- Every reader of a line takes the English when there is one, else the
  words as spoken, through `prompts.lines_of` for the chat engine's readers
  and `translation.reading` elsewhere; a line said in English keeps no
  second text. The English side of a line has no word-by-word highlighting
  during playback: the word times are the spoken words', and mapping them
  across languages would not be honest.
- Two settings and a template: Translation time limit, Translation notice
  by the chat engine, and Translation instructions on the Templates page;
  an Expectation key `translation`; the audit rows "Translation queued"
  (counts) and the engine call's own row.
- Search and Find read both texts and say "in the words as spoken" when
  the hit is there alone; captions and clips carry the English, and a
  clip's captions read as stale once the English lands.
