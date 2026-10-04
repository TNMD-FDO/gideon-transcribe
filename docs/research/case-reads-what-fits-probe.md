# The probe of Gideon reads what fits (Phase 9 chapter 6)

Run on 2026-10-04 from the office server's `llm-worker` against the shared
engine, on one of the office's own test cases: twelve body-camera
recordings of one incident, 5.3 hours of talk, every recording with a
Summary written the same afternoon (Summaries tonight, run by hand). The
case is under the setting's floor of 6 hours, so the probe forced the
ceiling under it inside its own process; the Limits page was not touched.
Five general questions, written by the build, each a question a reviewer
would put to a set of recordings. Counts only are kept here; nothing of the
case is.

## The overviews

| | |
|---|---|
| Recordings | 12, all with an Overview |
| Overview length | 105 to 164 tokens, 154 in the middle (the Body camera and Video summary templates' first part) |
| Transcript length | 1,600 to 47,000 tokens; 10,000 in the middle |
| Pass one's input | about 3,000 to 6,000 tokens: one line per recording and its Overview, the People line, the question |

At 154 tokens an Overview, 812 recordings would be about 125,000 tokens of
overviews, over one Reading of 100,000; the budget rule would cut each to
about 110 tokens and keep pass one to one call. A Jail call summary's
Overview is expected shorter.

## The five questions

| Question | Pointed to | Read whole | Readings | Seconds | Tokens read |
|---|---|---|---|---|---|
| Who are the people, and what part does each play? | 12 | 12 | 1 | 94 | 173,000 |
| Was anyone read their rights, and what was said before and after? | 2 | 2 | 1 | 42 | 94,000 |
| What was searched, and what was found? | 9 | 9 | 1 | 87 | 152,000 |
| Which recordings mention a weapon, and what is said about it? | 5 | 5 | 1 | 95 | 147,000 |
| Where was force used or threatened, and who did what? | 12 | 12 | 1 | 103 | 178,000 |

Pass one took about 40 to 80 seconds a question on the shared engine; pass
two the rest. Every question was answered with citations to real lines (14
to 42 a question), none failed, and the selection answered under its schema
every time, in one call.

## By eye

- **The picks are right in kind.** The narrow questions picked narrowly:
  the rights question named the two recordings whose overviews say rights
  were read, and the answer quoted the warning and what was said before and
  after it from those two. The weapon question named five, three where a
  weapon was found and two where one is spoken of. The broad questions
  (people, force) named all twelve, each with a line of why, which is the
  generous reading the chapter asks for: nothing it leaves out is read.
- **The reasons are readable** and say what in the overview pointed to the
  recording. One reason ended in a stray character from the engine; the
  reasons are shown on the page's record of the question and cut at 160
  characters, so no harm.
- **One fault found, in the app, not the wording.** The chat's earlier
  answers are given to the engine as history, and the app's own opening
  line ("Read the overviews of 12 recordings, then 12 whole" and the
  "read from the transcript alone" line) was copied by the engine into its
  later answers, once with the earlier question's figures. The app must
  strip its own lines from the history it hands over. Fixed in v1.121.3.

## What this does not show

- The case was twelve recordings; pass one at 800 overviews, and the cut to
  a budget, have not been exercised on the engine. The arithmetic is
  tested; the engine's reading of 800 lines is not.
- Jail calls: the probe's recordings were videos, read with their records
  of what the camera showed. A call reads words alone.

## The wording

The selection template's shipped wording is kept as written for
v1.121.0: the picks and the reasons answered the questions as asked, the
"generous" instruction produced the broad selections the chapter wants, and
the note said why when it named everything.
