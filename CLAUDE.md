# Working in this repository

Gideon Transcribe: local transcription, translation to English, and speaker
diarization for an office that handles privileged material. Django and Docker
on the office's own server, free tools only, nothing leaves the building.

This repository holds the specification pack and, from the build onward, the
code. Its maintainer is an office IT lead, not a programmer: explain choices
in plain words, and never assume familiarity with git, Docker, or Python
idiom.

## The specification decides, not you

- `docs/spec/SPEC-PHASE-1.md` is what the build answers to (the Workspace
  release, `v1.0.0`). `docs/spec/SPEC-PHASE-2.md` is the Cases release
  (`v2.0.0`); Phase 1 carries only the hooks each chapter lists under
  "Carried for Phase 2". `docs/spec/ADMIN-SETTINGS-CATALOGUE.md` defines every
  setting. `docs/whisperx-api.md` is the WhisperX service's contract.
- **Read the chapter you are working in, not the whole document.** Phase 1 is
  over 400 KB. Its contents list is at the top; each chapter ends with its
  sources and the amendments already folded in.
- The specification says what the app does *and why*. If the code and the
  specification disagree, the specification wins until the maintainer says
  otherwise.
- Where a chapter says "left to the build", decide within the rules it gives,
  and write the decision down: an ADR in `docs/adr/` when it is hard to
  reverse, otherwise a line in the pull request or commit message.
- Never quietly change specified behaviour. Say what you think is wrong, then
  do as specified unless the maintainer changes it.

## The words

`CONTEXT.md` is the glossary and it is binding. The capitalised words
(Recording, Transcript, Segment, Side, Batch, Job, Run, Queue, Workspace,
Clip, Summary, Chat, Case, Share, Admin, and the rest) are the names used in
code, in the database, on pages, in exports, and in the guides. Each entry
also names the words to avoid. Add a word to the glossary before using a new
one anywhere.

## Style

- No em dashes anywhere: not in code, comments, pages, guides, or commit
  messages. Hyphens.
- British spelling in documents and on pages (organise, licence as the noun),
  as the glossary uses it.
- Guides and error messages are written for an IT generalist who is not a
  programmer: one command where possible, a checklist to verify, plain
  language when something fails.

## Nothing office-specific, ever

Every office fact (hostnames, addresses, networks, directory names and
groups, service accounts, mail addresses, GPU ids, paths, tokens) is a value
in `.env`, a secrets file, or an admin setting, and `./transcribe install`
asks for it. No office's own values belong in this repository, in code, in
docs, or in a test fixture. The office that wrote the app keeps its values in
its own private planning repository.

## Secrets

- Only `.env.example` files are tracked. `.env`, `secrets/`, `tls/`, and
  `ca/` are ignored by `.gitignore` and stay that way.
- Never commit a key, a certificate, a token, or a password, not even a
  sample that looks real. CI runs a secret scan on every push.
- Code reaches a server only by fetch and checkout at a Release tag inside
  `./transcribe upgrade`. Nothing is ever pushed from a workstation to a
  server or copied over an install folder.

## How the work is organised

- Commits go straight to `main`; `main` is always deployable. Tags mark
  Releases (`vMAJOR.MINOR.PATCH`), and each tag's notes are that version's
  section of `CHANGELOG.md`, whose first two lines are always whether the
  models changed and whether the database migrates.
- Commit at natural checkpoints without being asked, and push. Write commit
  messages that say what changed and why, in plain words.
- CI (`.github/workflows/ci.yml`) runs ruff, the unit tests,
  `docker compose config` against the example environment files, and
  gitleaks. Keep it green.
- Never use a self-hosted runner, including the one the office runs on its
  own server. The GPU benchmark gate is a by-hand step on that server.
- This repository's Issues are for other offices' reports, not for the
  build's own task list.

## The server is shared

The office's server and its GitHub organisation are shared with the office's
other project, GIDEON (`TNMD-FDO/GIDEON`), which provisions the server and
owns its operating-system layer: the graphics driver, Docker, the firewall,
the `/data` layout, the time zone, and the self-hosted runner. This app
consumes that layer and owns only its own install home, data directory,
units, Compose project, networks, and images.

`docs/box-ledger.md` is the record both projects keep. It says who owns each
graphics card, port, data directory, and timer, what each project may do with
the Docker daemon and the hosted-runner minutes, the open items between the
two, and, in its section 12, a log with one subsection per project where each
writes what it changed and lines addressed to the other. An identical copy
lives in GIDEON's repository. Nobody writes into the other repository: fetch
GIDEON's copy with the command in the ledger's section 11 and merge it before
any change to a shared thing (a port, graphics-card memory, a `/data`
directory, a timer, a workflow trigger that moves hosted-minute load, the
engine's network or token) and at every Release. Write only the Gideon
Transcribe subsection of the log: what changed, and an answer by number to
every line addressed to Transcribe. Add a "For GIDEON" line when a change
concerns GIDEON. The rule above against self-hosted runners is recorded in the
ledger's section 9 and changes there first, if it ever does.

## Building and running

- Docker only, free tools only, and everything pinned: images by tag and
  digest, Python packages by version. The WhisperX service's stack is pinned
  for a reason (`docs/research/whisperx-pinned-stack.md`); do not bump it
  casually.
- The app never phones home, checks for updates, or reaches any service
  outside the office at run time.
- Two images are built here (`app`, `whisperx`); everything else is an
  upstream image.

## Where the reasons live

`docs/adr/` holds the decisions that are hard to reverse, and
`docs/research/` the facts behind the pins and the designs, each with the URL
it was read from. Read the relevant one before arguing with a pin or a
design; most surprises in this app were already decided on purpose.
