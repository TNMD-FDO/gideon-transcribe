# Contributing to Gideon Transcribe

## The dedication

Gideon Transcribe is a public-domain work: a United States government work
under 17 U.S.C. § 105, dedicated worldwide under CC0 1.0 Universal (see
`LICENSE` and [ADR 0006](docs/adr/0006-us-government-work-cc0-dedication.md)).

**By submitting a contribution to this repository you dedicate that
contribution to the public domain under the CC0 1.0 Universal dedication,
waiving all copyright and related rights you hold in it, worldwide.** This
term exists because not every contributor is a federal employee: Community
Defender Organization staff, for example, are nonprofit employees who *do*
hold copyright in what they write, and the app stays freely distributable
only if every contribution carries the same dedication.

If you cannot, or do not wish to, dedicate your contribution under CC0-1.0,
do not submit it.

The dedication covers the code, the built-in prompt wordings, the guides, and
the specification pack. Nothing in the repository needs a copyright header.
Everything shipped beside the code keeps its own licence and is listed in
`THIRD_PARTY_LICENSES.md`.

## How the work is organised

- The specifications are `docs/spec/SPEC-PHASE-1.md` (the Workspace) and
  `docs/spec/SPEC-PHASE-2.md` (Cases); the settings are catalogued in
  `docs/spec/ADMIN-SETTINGS-CATALOGUE.md`; the WhisperX service's contract is
  `docs/whisperx-api.md`. The vocabulary is `CONTEXT.md`, and every decision
  behind the design is recorded in `docs/adr/`, with the facts they rest on
  in `docs/research/`. Read the specification before changing behaviour: it
  says what the app does and why, and it is the source the code answers to.
- One person, the maintainer, has write access. Commits go straight to
  `main`; tags mark Releases (`vMAJOR.MINOR.PATCH`, semantic versioning), and
  every tag is a GitHub Release whose notes are that version's section of
  `CHANGELOG.md`.
- `main` is always deployable. A server never runs `main`: it clones and
  upgrades at a Release tag.
- CI runs on every push and pull request: ruff, the unit tests,
  `docker compose config` against the example environment files, and a secret
  scan.
- Never commit an environment file, a secret, a certificate, or a key. Only
  `.env.example` files are tracked; `.env`, `secrets/`, `tls/`, and `ca/` are
  ignored by `.gitignore` and must stay that way.

## Reports and questions

This repository's Issues are for other offices' reports: what went wrong,
what you expected, what you saw, and the version you were running. The app is
provided as is, with no support promised. Security problems go through
`SECURITY.md`, not through an Issue.
