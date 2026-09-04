# Changelog

Every Release has a section here, newest first, and a Release's notes on
GitHub are its section of this file. Two lines open every section, before
anything else:

```
Models: unchanged
Database: unchanged
```

`Models: changed` means `./transcribe upgrade` has to fetch models again, and
`Database: migrates` means the database changes when the app starts. The
upgrade command reads both lines out before it does anything.

This project follows [Semantic Versioning](https://semver.org): a tag is
`vMAJOR.MINOR.PATCH`, and a Release is the only thing an installer ever
installs or upgrades to.

## Unreleased

```
Models: unchanged
Database: migrates
```

### Added

- **Cases**, the Phase 2 feature that lets a recording outlive the session
  that uploaded it. A case is a named page with one owner; a recording moved
  into one lives under `cases/<case id>/<recording id>/` and the sign-out
  discard leaves it alone. The Cases page, the case page with a search across
  its transcripts, New case, Rename, and a Delete that names what it is taking
  and cannot be undone.
- **Folder management**, the admin toggle that enables cases, default off, on
  a new Cases page of the settings rail with **Recording types** beside it.
  Off hides every case from everyone, Admins included, and deletes nothing;
  the days it is off are recorded as they pass, because the retention policy
  will subtract them and cannot work them out afterwards.
- **Add to case** and **Recording type** on the Upload page, set once per
  batch with a per-file override, and **Move to case** from the recordings
  list, from a case page, and from the sign-out dialog. On disk a move is a
  folder rename, so it is instant whatever the size.
- A **case rail** in the viewer: a recording opened from a case gets a third
  column listing the rest of the case, so somebody working through a matter
  moves between its recordings without going back to the case page. The
  chapter lists the viewer as unchanged when reached from a case; this is
  additive rather than contradictory and the maintainer asked for it. It
  hides on a narrow screen and opens over the page there, the button in the
  head is always present, and the choice is remembered.
- The users list reads "3 in session, 41 in cases", and its **Reassign** and
  **Delete data** actions, greyed since the first release, now act. The status
  page gains a Cases line and, while the toggle is off, the date it went off.
- `./transcribe install` and `./transcribe upgrade` now make `scratch/`,
  `cases/` and `uploads/` under the app data folder with the right owner,
  because Docker creates a missing mount source as root and the app could
  then never write into it. `./transcribe check` says so if one is wrong.

### Fixed

- CI had not run a single check since directory sign-in landed: `python-ldap`
  builds from source and the runner had none of the headers it needs, so the
  install step failed and the lint, the tests, the compose validation and the
  secret scan were all skipped. Four commits went in on a red build.
- Twenty tests had been failing on a missing static files manifest, which hid
  two more: signing out with a GET has shown the confirmation dialog rather
  than signing anybody out since the dialog was built, and nothing noticed.
- The check that proves Caddy asks the app before it serves a byte was not
  looking inside nested routes at all.

Three tabs of the four a case page is meant to have are absent on purpose:
Speakers, Clips, and Chat belong to chapters not yet built.

## v0.1.0, 2026-09-03

```
Models: changed
Database: unchanged
```

The WhisperX service, built first and on its own, so that the app has a
working engine to be written against.

This is a build release, not a public one: `v1.0.0` is the first Release an
office installs. It runs on the office's own server and has been measured
there against the office's own recordings.

### Added

- The WhisperX service in `whisperx-service/`: its image on
  `nvidia/cuda:12.8.2-base-ubuntu24.04` pinned by digest, with every Python
  package pinned to the version `docs/research/whisperx-pinned-stack.md` chose
  for the RTX PRO 6000 Blackwell cards.
- The API under `/v1/`: submit, poll, fetch, delete, list, models, status, and
  an unauthenticated liveness check, with bearer tokens read from a file that
  is re-read whenever it changes.
- The line: one job at a time across every Consumer, in arrival order, kept in
  SQLite so a restart keeps it; position and audio minutes ahead that count
  everyone's jobs; duplicate protection; one retry after an interruption;
  results dropped after a day and job rows after a month; and a measured speed
  figure per model and diarization setting.
- The model process: a process of its own, because nothing in the engine can
  be interrupted, so cancelling a job means killing it. The same path handles
  a job past its time limit and a driver fault.
- Language detection over three windows, the whole task table, speaker
  separation with the three shapes of speaker-count hint, and word timing
  where the language can be aligned.
- Commands in the container: `selftest`, `pull`, `make-token`, `bench`, and
  `serve`.
- `models.yaml`, pinning every model to a revision, and a pull that checks
  what it fetched against those pins.
- The benchmark harness, which measures the service on an office's own
  recordings and writes its report outside the repository.
- ADR 0007: the office's own build server tracks `main` until `v1.0.0`.

### Changed

- The default model is `large-v3-turbo`, decided at the Phase 1 benchmark gate
  on the office's own recordings: about 40 per cent faster than `large-v3`,
  about 4 GB less video memory, within 3 per cent of it on words found in 13
  of 14 recordings, and right about the language on the one recording
  `large-v3` misheard, and confirmed by a reader against both models'
  transcripts of the same recordings. It stays an admin setting that takes
  effect on the next Run.
- `docs/whisperx-api.md` now carries the decisions it had left to the build.
  Nothing specified was changed; what was open is filled in and listed under
  "Settled by the build".
- CI lints and tests the service and validates its compose file on its own.

### Measured

The Phase 1 benchmark gate, run on the office's own recordings on an RTX PRO
6000 Blackwell under driver 595:

- Speed, as the service publishes it: 194 times real time for
  `large-v3-turbo` without speaker separation and 87 with it; 156 and 73 for
  `large-v3`. These replace the research's reference figure of about 70.
- Batch size 16. Above it, video memory grows about a gigabyte for every 8 of
  batch size while transcription gains under 3 per cent.
- A GPU budget of 20 GB, which is in the service README as the figure to check
  before anything else is put on the same card.
- The voice-activity thresholds ship unchanged: lowering them found no more
  speech and no more words on nine narrowband calls.
- The pinned ffmpeg identifies and decodes G.729 inside WAV on its own, and
  the forced decoder still works.

Two legs of the gate could not run and are still owed: the translation checks,
which need non-English and mixed-language samples, and the Phone preprocessing
profile, which ships only if it measurably lowers errors.
