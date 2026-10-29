# 28. The pipeline is a service of its own, and the app is its first client

## Status

Accepted, 2026-10-29. The stages of `docs/spec/SPEC-PHASE-11.md` chapter 4
say when each part is built; none is built yet.

## Context

Another front end is being built for the office (the CSC 4610 Team 8
repository `gideon-frontend`, one front end for GIDEON and Gideon
Transcribe), in a language not yet chosen, on the shared server at first and
possibly on a machine of its own later, handling the same privileged
material, and wanting everything Transcribe does.

The three engines (the WhisperX service, the diarizer, the recogniser) are
already independent containers with a documented HTTP contract
(`docs/whisperx-api.md`) and a token per Consumer. What a file needs to
become a Transcript beyond them lives inside the Django app: preparing the
sound (`core/media.py`), the line and the hand-over and the merge
(`core/queue.py`), the English to follow (`core/translation.py`) and the
clock reading (`core/clock_check.py`). A second front end that calls the
engines alone would have to rebuild all of that, and two merges would drift.

A Python library alone would not serve a front end in another language or
on another machine.

## Decision

The pipeline becomes a service of its own, `pipeline`, beside the three
engines: one container, one small API (submit a file with options, poll,
fetch the Result, cancel, process again, a callback when the state changes),
a bearer token per Client, its own small line database, holding no titles,
names or people, deleting audio when a job ends.

It is built as a library first, `pipeline/`, with no Django in it, extracted
from the app's own code rather than written again; the app is rewired onto
the library and the suite proves nothing changed; then the HTTP shell over
it, and the app becomes its first client over HTTP. The Result is one
versioned JSON shape that the app reads into its own Segments, so the
Provenance, the exports and the clock verdict read what they read today.

The WhisperX service's contract does not change; the pipeline service is
its Consumer as the app was.

## Consequences

- One pipeline, one merge, one Result shape, whatever the front end. A bug
  fixed in the merge is fixed for every client.
- Moving the GPU work to a machine of its own moves the pipeline service and
  the engines together; the product changes one address and one token.
- The product keeps what is the product's: the Speaker check, the Summaries,
  the Vision run, the vocabulary, the Case, the Incident, the notes.
- One more container, image, version and README to keep pinned and
  released; one more token in `secrets/`; a ledger entry for the engines'
  network and the GPU's reserve before it runs on the shared box.
- The stages are the risk control: nothing moves without its contract
  written, and each stage is used by Transcribe's own pages before the
  next starts.

## Sources

- `docs/whisperx-api.md`, the engines' contract and the Consumer idea.
- `docs/adr/0013` (the diarizer in a container of its own) and
  `docs/adr/0025` (the recogniser as a choice in a container of its own),
  the pattern this follows.
- The maintainer's answers of 2026-10-29: the front end's repository, that
  it wants everything, that it shares the box and may move, and that it
  handles the same material.
