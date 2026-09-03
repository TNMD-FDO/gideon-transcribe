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
Models: changed
Database: unchanged
```

The WhisperX service, built first and on its own, so that the app has a
working engine to be written against.

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
