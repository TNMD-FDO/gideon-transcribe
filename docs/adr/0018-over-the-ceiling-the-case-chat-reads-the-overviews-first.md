# 18. Over the ceiling, the Case Chat reads the overviews first

Date: 2026-10-04. Status: accepted. Release: the Phase 9 release that
builds its chapter 6, after the probe its chapter names.

## Context

Phase 2 chapter 7 grounds the Case Chat in every Transcript in the Case,
packed whole into Readings of about six hours of talk, two at a time, with
one combining call, and refuses over a ceiling of hours (default 120) with
`llm_case_too_large`. It also ruled out an index or embeddings behind the
chat, and left "a picker to narrow a Chat to chosen Recordings" for later.

A Case of 800 jail calls is about 200 hours. The maintainer's rule for it
(2026-10-03): "the context window may not allow it; find smart ways chat
could work so the limitations are implicit and not forced; the app only
does what it can do". A refusal is a forced limit. Thirty Readings a
question is a twenty-minute wait and a load the shared engine should not
carry for a chat.

## Decision

1. **The person's narrowing is the scope.** What is in view on the case
   page or the Notes page (the filter box, a Search's hits, the writer and
   type pills) is what Gideon reads, whole, in Readings as today. No
   picker: the narrowing a person did for their own work is the scope.
2. **Over the ceiling, two passes.** When the recordings to read exceed
   the ceiling and any of them has a Summary, pass one reads one short
   line per recording and its Overview, the Summary's first part cut to a
   budget so that every recording fits one Reading, and names under a
   schema the recordings that bear on the question in order of relevance.
   Pass two reads those recordings whole, as many as fill the allowed
   Readings (one by default), exactly as the Case Chat reads today, so the
   citations are to real lines.
3. **It says what it read.** The drawer's head says the scope before the
   question; the answer's first line says "Read the overviews of 812
   calls, then 11 calls whole" or "read 20 of the 31 it pointed to; narrow
   the question for the rest", and names the recordings without a summary
   with "Write the summaries tonight" one press away.
4. **The ceiling is a size, not a refusal.** The setting becomes "hours of
   talk read whole per question": within it the words are read whole;
   over it the two passes take over. The refusal survives only when no
   recording has a Summary and the Digest fallback cannot help.
5. **No index.** The Overview is the Summary's first part, kept for its
   own sake (ADR 0017); nothing is embedded, ranked or kept between
   questions. The rule against an index stands.

## Consequences

- A whole-case question over 800 calls is two large calls, about 100,000
  tokens in each, three to four minutes expected: lighter than today's
  worst legal question of twenty Readings, and new load where there was a
  refusal. The box ledger's log says the load's shape changed.
- The answer can only reach the recordings the overviews point to. The
  selection is therefore generous (thirty picks by default), the answer
  says how many it read of those pointed to, and the person can narrow and
  ask again.
- Nothing ships untried: the chapter is the last release of the phase and
  is held if the probe from `llm-worker` on the office's largest case
  disappoints. The review loop of chapters 1 to 5 does not depend on it.
- The selection template is on the Templates page with Reset to default,
  like every other wording the engine is given.
