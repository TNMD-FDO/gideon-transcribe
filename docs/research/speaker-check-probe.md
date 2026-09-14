# The Speaker check probe: what the engine proposed on three corrected recordings

Run on 2026-09-14 on the office's server against GIDEON's shared engine
(vLLM, Qwen3.8-27B-FP8), before Phase 5 chapter 3 was written. The probe
was a script run once through `manage.py shell` from the worker that can
reach the engine; nothing of it is in the app. The report with the words
stayed on the server in the maintainer's home folder; only the counts are
recorded here.

## What was asked

For every transcript in one case whose speakers were told apart, the
diarization as the engine gave it was rebuilt from the label each line
keeps beside its name, and sent in windows of about ten minutes of talk,
each starting six lines before the last ended, with the list of speakers
and the rules the chapter now ships: move a line only to a speaker in the
list, never invent or merge a speaker, never change a word, propose only
where the words make it clear, answer with a JSON list of moves. Each move
was then checked: a real line, a speaker on the transcript, the label as
shown, a move to somebody else.

## What came back

| Recording | Lines | Windows sent | Windows readable | Moves kept |
|---|---|---|---|---|
| Body camera, 25 minutes | 496 | 3 | 1 | 19 |
| Body camera, 51 minutes | 916 | 5 | 3 | 14 |
| Interview, 1 h 44 min | 826 | 6 | 3 | 44 |

Two of the case's five transcripts had been made without the speakers told
apart and were skipped. No line moves were on record for the three, only
renames and merges, so the probe could not score itself against hand
corrections; the maintainer read the report and judged the proposals
"very promising".

Half the windows came back unreadable: the answer cap of 1,500 tokens cut
the JSON off mid-list. The chapter's shipped cap is 3,000 tokens, the
window setting lets an office shorten the windows, and an answer cut off at
the cap keeps the moves that were finished.

## What it decided

- The check is worth building as a feature that proposes and never applies,
  with a switch shipped Off and its settings on a page of their own.
- The engine is eager: about eleven moves per readable window. The rules
  say to leave a line either speaker could have said; whether that is
  strict enough is for each office to judge on its own recordings, and the
  template is editable for that reason.
- The first pass from the app container failed every call: only
  `llm-worker` is joined to the engine's network. The task runs there.

## Links

- The Speaker suggestions note, for the earlier evidence on what a small
  engine does with speaker questions: `docs/research/speaker-suggestions.md`.
- vLLM structured outputs, which hold the answer to the list of speakers:
  https://docs.vllm.ai/en/stable/features/structured_outputs/
