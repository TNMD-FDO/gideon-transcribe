# 20. The transcript goes ahead of the chat history

Date: 2026-10-14. Status: accepted. Release: v1.134.0.

## Context

Every chat in the app (a Recording's Chat, the Case Chat, the incident
page's Gideon) sends the engine one request per question: the system
message (the ground rules, the template, the answer format), then the chat
so far as pairs of question and answer, then the user's turn. Until this
release the user's turn carried everything the call reads, the rendered
transcript, the Digest and the papers, with the question at its end.

The engine is vLLM with prefix caching on, which keeps the KV cache of the
longest prefix two requests share and prefills only what follows it
(`docs/research/llm-handler-capabilities.md`, line 22 of the capability
table, and the long-transcript note at line 45: "a transcript placed
before the chat turns is prefilled once"). With the transcript after the
history, the shared prefix of two questions in the same chat was the
system message alone: the second question's request differed from the
first's from the first history pair on, so the engine read the whole
transcript again for every follow-up, a hundred thousand tokens for a
Reading of six hours. The performance audit of 2026-10-14 rated this its
first finding.

## Decision

The reading goes at the end of the system message, ahead of the history,
and the last user message carries the question alone.

- What moved: the transcript, the Digest, the camera block, the near
  descriptions and the papers of a Recording's Chat; the part line, the
  people line, the transcripts and the papers of a Case Chat Reading; the
  incident record, the chronology and the papers of the incident chat. In
  the Case Chat the part line and the people line stay ahead of the
  transcripts, as they were. The one builder, `assistant._messages`, takes
  the reading as a named argument; `case_chat._messages` delegates to it.
- What did not move: the system message's own parts and their order (the
  ground rules, the template, the format, the rules); the history pairs;
  the fit check, which counts the same texts whichever message holds them;
  the Summary and every single-call feature (the Speaker check, the
  proposals, the comparison, the Digest, the memo), which have no history
  and gain nothing from a different order; the combining call of a Case
  Chat in parts, whose parts are the question's own.
- Not the first user turn: the research note's suggestion (its
  recommendation 2) would put a user message before the first history
  pair, two user messages in a row, which not every chat template renders.
  One system message every template takes.

## Consequences

- A follow-up question in a chat prefills the history and the question,
  not the transcript: the engine's time on the second question of a
  six-hour Reading falls from the whole prefill to a few hundred tokens'
  worth, while the cache holds it.
- The system message is long. Nothing reads it but the engine; the audit
  rows carry counts, never words, as before.
- A test that read the transcript out of the last message reads it out of
  the first; the tests of v1.134.0 pin the new shape.
- The cache is the engine's to keep or drop; the app assumes nothing of it
  beyond the order of its own messages, and a request is correct either
  way.
