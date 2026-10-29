# Gideon Transcribe, Phase 11: the pipeline as a service, and the product as an API

Written 2026-10-29 and agreed by the maintainer the same day ("They
stand", with the recommendations of chapter 5). Nothing in it is built yet;
the chapters say what is to be built and in what order, and each stage waits
for its own word.

## About this document

Phase 11 answers one ask: another front end is being built (the CSC 4610
Team 8 repository `gideon-frontend`, "one front end for GIDEON and Gideon
Transcribe", at its Iteration 0 on 2026-10-29 with no framework chosen yet),
and the transcription pipeline should be modular enough to plug into it. The
front end will share the office's server at first and may move to a machine
of its own; it wants everything Transcribe does, not the engine alone; and
it handles the same privileged material.

Read it with the same companions as every phase: `CONTEXT.md` (the glossary),
`docs/whisperx-api.md` (the WhisperX service's contract, which this phase
does not change), `docs/box-ledger.md` (the shared server), and the ADR this
phase records, `docs/adr/0028-the-pipeline-is-a-service-and-the-app-its-first-client.md`.

## What Phase 11 adds

- **The pipeline service** (chapter 1): one container with one small API in
  front of the three engines, owning what the app owns today between a file
  and a transcript: preparing the sound, the line, the hand-over and the
  merge, the English to follow, and one documented result shape. Transcribe
  is its first client; the other front end its second; a machine of its own
  later needs nothing rewritten.
- **The product's API** (chapter 2): the records Transcribe keeps, as JSON
  under one address, with the same sign-in, the same audit rows and the same
  rules, so a front end in any language can offer what the pages offer.
- **The front end on the box** (chapter 3): where it is served, how it signs
  in, what the ledger says.

## Contents

1. The pipeline service
2. The product's API
3. The front end on the box
4. The stages, and what the front end team can start on now
5. Choices for the maintainer

Appendix A. Audit rows added in Phase 11
Appendix B. Settings added or changed in Phase 11

## Principles

1. **Contracts before code.** Each stage starts with the written contract
   (the result shape, the API, the OpenAPI document) agreed by both sides,
   and ends with the suite proving Transcribe unchanged on it. Nothing moves
   until its contract is written.
2. **The app is the first client.** Whatever the pipeline service and the
   product API offer, Transcribe's own pages use first. There is one merge,
   one result shape and one set of rules, not two that drift apart.
3. **The rules travel.** Nothing leaves the building; no names, titles or
   people in a request to the pipeline; audio deleted the moment a job ends;
   every hand-over and every read of a record an audit row in a person's
   name; retention, quotas and the one-job-at-a-time line unchanged. A
   second front end gets no second set of rules.
4. **Nothing is rebuilt twice.** The engines keep their contracts; the
   pipeline service is the app's own queue and merge moved out, not a new
   pipeline; the product API is the app's own views answering JSON, not a
   second app.
5. **The shared box is shared.** A new container, port, network or token is
   a ledger change with GIDEON first; the front end that serves both
   projects is a line in both halves of the ledger's log.

## Words

**Pipeline**: what turns a file into a Transcript: preparing the sound, the
line, the engines, the merge, the English to follow. **Pipeline service**:
the container that owns the pipeline, with its API. **Result**: the pipeline
service's answer for one file, in the one documented shape. **Product API**:
Transcribe's records as JSON under `/api/v1/`. **Client**: a program that
calls the pipeline service or the product API (Transcribe's own app, the
front end); the WhisperX service's word Consumer stays its own. **Front
end**: the `gideon-frontend` application. The pages never say microservice,
backend, endpoint (that is the contract's word), REST or SPA.

## 1. The pipeline service

### What it owns

Everything the app does today between a Ready file and a Transcript, moved
out of Django into one container, `pipeline`, with its own image, version,
Compose entry and README, beside the three engines:

- **Preparing the sound** (`core/media.py`): ffprobe, ffmpeg into one or two
  Sides, the loudness and the length. The playback copy stays with the
  product, since it is for the player and not the engine.
- **The line and the hand-over** (`core/queue.py` part 1): a Job per file and
  a Run per Side, the request to the WhisperX service with the recogniser,
  the diarizer and the Vocabulary chosen, polling, giving up on a dead
  answer, holding and failing with the reason classes the app has.
- **The merge** (`core/queue.py` part 2): the Runs' answers into one list of
  Segments, the two-sides stretch logic, the speaker labels across stretches,
  the words with their times.
- **The English to follow** (`core/translation.py`): the windows, the line by
  line check, the signature per window, when a Client asks for it and the
  chat engine is there. It is the pipeline's because it reads the words as
  spoken and writes beside them.
- **The clock reading** (`core/clock_check.py`, the re-read): the verdict on
  each line's time and the marked blocks read again by the service, since it
  is about the words' times and not about the case.

What stays with the product: the Speaker check and the speaker names, the
Summaries, the Digests and the Vision run, the vocabulary, the Case, the
Incident, the notes and everything a person does on a page.

### The API

JSON over HTTP under `/v1/`, a bearer token per Client as the WhisperX
service has it, on the engines' network and never on the office network
except through the product (chapter 3).

| Method and path | What it does |
|---|---|
| `POST /v1/transcriptions` | Submit: a multipart body with the `file` and a `request` JSON (the options below). Returns `202` with the id, the position and the minutes ahead. |
| `GET /v1/transcriptions/{id}` | The state: `preparing`, `queued`, `running` with its stage and percent, `translating`, `done`, `held` or `failed` with the reason class, and the expectation. |
| `GET /v1/transcriptions/{id}/result` | The Result (below) once done; `409` with the state before; `410` after it was deleted. |
| `DELETE /v1/transcriptions/{id}` | Cancel, or delete a finished one and its result. |
| `POST /v1/transcriptions/{id}/again` | Process again with new options; the old result stays until the new one lands. |
| `GET /v1/status` | The line, the speed, the engines' health, the models loaded. |
| `GET /healthz` | Liveness, unauthenticated. |

The options: the language or auto, the recogniser (whisper or qwen3-asr),
the diarizer (nemotron or pyannote) and the speaker count hint, the
Vocabulary (a list of terms, under the same 200-term rule), whether to
translate to English, whether to read the clock, the two-sides flag, a
`client_reference`, and a `callback` address the service posts the state to
when it changes (the webhook; a Client that gives none polls).

### The Result

One JSON document, versioned (`"result_version": 1`), the same whatever
the Client:

```
{
  "result_version": 1,
  "id": "...", "client_reference": "...",
  "audio": {"seconds": 2812.4, "sides": 2, "sample_rate": 16000},
  "language": {"code": "es", "probability": 0.98, "mixed": false, "per_piece": [...]},
  "speakers": [{"label": "SPEAKER_00", "side": 1, "seconds": 1210.2}, ...],
  "segments": [
    {"n": 1, "side": 1, "start": 12.40, "end": 15.92, "speaker": "SPEAKER_00",
     "language": "es", "text": "...", "english": "...",
     "words": [{"w": "...", "start": 12.40, "end": 12.71, "p": 0.93}, ...],
     "clock": {"verdict": "fine", "retimed": false}}
  ],
  "provenance": {"service": "whisperx 0.7.0", "recogniser": "...", "diarizer": "...",
                 "settings_used": {...}, "vocabulary_terms": 14,
                 "translation": {"engine": "...", "windows": 6, "checked": true},
                 "clock": {"marked": 3, "reread": 3}},
  "timing": {"prepared_seconds": 4.1, "queued_seconds": 61.0, "run_seconds": 190.2}
}
```

Transcribe's `_store` (today's `queue._store`) becomes the reading of this
document into its own Segments; the Provenance, the exports and the clock
verdict read the same fields they read today, from the Result.

### What it does not hold

No titles, file names, cases, people or users: a Client sends a file and a
reference of its own. Audio is deleted when the job ends; the Result waits
at most 24 hours, as the WhisperX service's does. The service keeps its own
small database for the line (SQLite on its own volume, as the WhisperX
service does), never the product's.

### Moving to a machine of its own

The service and the three engines move together, with the GPU; the product
reaches them by one address and one token in `.env`, which is how it reaches
the WhisperX service today. Nothing in the product changes but that address.
On the shared box they stay on the engines' network (the ledger's entry for
the engine network applies), and a second Client on the same box gets a
token of its own and the same line.

## 2. The product's API

### What it is

The records Transcribe keeps, as JSON under `/api/v1/` on the app, answered
by the app's own views (many already answer JSON for the pages: the incident's
state, the case's chronology, the proposed events, the comparison, the Notes
page's list and find, the recording page's lines around a moment). This is
those answers made one, named, versioned and documented, and widened to the
records the pages render as HTML today.

### What it covers, in the order the front end team will want it

1. **Sign-in and who I am**: the same office sign-in (the directory, the
   Login session), as a session cookie on the same origin (chapter 3), and
   `GET /api/v1/me` with the person, their role and what they may do.
2. **Cases and recordings**: list, open, add (the upload through tusd as
   today), the recording's facts, its state in the pipeline, Process again.
3. **The transcript**: the Segments with words, speakers, the English, the
   clock verdict; corrections; the speakers' names.
4. **Notes**: on a line, at a moment, To check; the Notes tab's rows; the
   case's chronology by day; placing a recording on the clock.
5. **Summaries, Gideon and the case chat**: the summary, a question and its
   answer with citations, the expectation.
6. **Incidents**: the cameras, the clock, the events, the memo, the
   comparison; the proposed events and Accept.
7. **Documents** and their pages; the exports as files.
8. **The Panel**: settings and the audit log, Admins only.

Each section is one release, each with its OpenAPI document generated from
the views and published under `docs/api/`, and each used by Transcribe's own
pages where a page already fetched the same thing, so there is one answer.

### The rules

Every read of a record is the same use of a Case the page's read is: the
retention clock moves, the Admin's access row is written, the share's rows
are written. Pagination on every list; no answer carries another person's
private Workspace; every error has the reason class the pages have. The
same `Cache-Control: private, no-store`. Nothing leaves the building: the
API is on the office network behind Caddy, like the pages.

## 3. The front end on the box

- **Served by Caddy on the same origin** as the app, under a path (`/app`)
  or a hostname of its own with the same certificate, so the office sign-in's
  cookie serves it and no token sits in a browser. A hostname of its own
  needs a certificate from the office's CA as the app's does.
- **No CDN, no font or script from outside the building**, as the app has
  none; the same `Content-Security-Policy` as the pages.
- **The ledger**: the front end's container, its port and its network are a
  ledger entry agreed with GIDEON before the first deployment, and since it
  serves both projects, a line in both halves of the log. If it moves to a
  machine of its own, the ledger says which half owns the machine.
- **Audit**: a person acting through the front end is the same person acting
  through a page; the rows read the same, with the client named.

## 4. The stages, and what the front end team can start on now

| Stage | What ships | Proven by |
|---|---|---|
| 0 | The contracts: the Result shape and the pipeline API (chapter 1) and the product API's first two sections (chapter 2) as OpenAPI documents under `docs/api/`; a sandbox the team can run, the local walk's seed (`manage.py seed_demo`) behind the app | the team builds against the documents; nothing in the app changes |
| 1 | The pipeline library: preparing, the line, the merge, the English and the clock moved out of Django into `pipeline/` with no Django in it; the app rewired onto it; the Result as the app's own reading | the suite green and unchanged; a recording processed on the server reads the same as before |
| 2 | The pipeline service: the HTTP shell over the library, its container, token and Compose entry; the app its first client over HTTP | the server's upgrade; test_3 processed through the service |
| 3 | The product API, section by section in the order above, each with its document, each used by a page of the app | the suite; the team's front end on the sandbox |
| 4 | The front end behind Caddy on the box, the ledger entry, the audit rows with the client named | the walk, both projects' operators |

**What the team can start on now**, before any stage ships: the user
stories against the pages as they are (every page is the product's own
front end, and what a page does is what the API will offer); the framework
choice with the rules above in hand (no CDN, same origin, nothing leaving
the building); and reading `docs/whisperx-api.md` and `CONTEXT.md`, since
the words there are the words the API will use.

## 5. Choices, answered 2026-10-29

1. **The path or a hostname for the front end** (chapter 3). Answered: a
   path on the app's origin, so the cookie serves it and no new certificate
   is needed; a hostname when the front end moves to its own machine.
2. **Where the clock reading lives.** Answered: the pipeline, since it is
   about the words' times.
3. **The product API's first section.** Answered: sign-in and who I am,
   then cases and recordings, since nothing else is reachable without them.
4. **The sandbox for the team.** Answered: the local walk's seed behind a
   copy of the app on a workstation; nothing on the box until stage 4.

## Appendix A. Audit rows added in Phase 11

| Row | Category | Details kept | Never |
|---|---|---|---|
| Transcription handed to the pipeline | Recordings | the recording, the client, the options, the reference | a title, a word |
| Record read through the API | Cases | the record, the client, the person | the record's words |

## Appendix B. Settings added or changed in Phase 11

| Setting | Default | What it does |
|---|---|---|
| Pipeline address and token | from `.env` | Where the pipeline service is and the product's token for it, as the WhisperX service's are today. |
| API on | On | Off answers every `/api/v1/` address with `404`; the pages are unaffected. |
