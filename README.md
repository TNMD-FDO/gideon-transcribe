# Gideon Transcribe

Local transcription, translation to English, and speaker diarization for an
office that handles privileged material, with an AI assistant, running
entirely on the office's own server. Free tools only, Docker only, no cloud
service and nothing sent outside the building.

## Who it is for

An office like the one that wrote it: a federal defender office, or any
office with the same needs. Attorneys, investigators, paralegals, and
interpreters; thirty users and more; internal only. The material is
privileged and confidential, which is why the app never leaves the office's
network and why every Admin access to another user's material is audited.

It is installed by an IT generalist who is not a programmer. Every guide is
written that way: one command where possible, a checklist to verify, and
plain-language recovery when something fails.

## What it does

- Sign-in with the office directory over LDAPS, gated by a Sign-in group,
  with Admins from an Admin group, a manual flag, or a local admin account.
- Upload one file or many as a Batch, from the browser; every recording is
  inspected, prepared, and given a playback copy.
- Transcription by a pinned WhisperX service on the office's own GPU, one run
  at a time across the whole office, in arrival order, with no priority for
  anyone and a queue everyone can see.
- Translation to English, and speaker diarization, as per-recording choices.
- A viewer with the transcript at reading width, a synced audio and video
  player, a speaker-lane timeline, correction, speaker naming, and clips.
- An AI assistant against a language-model engine the office runs: summaries,
  and a chat that answers only from the transcript and cites every claim.
- Export to Word, text, SRT, and VTT.
- An admin panel: status, queue, users, audit log, and about thirty settings.

**Phase 1** is the Workspace release (`v1.0.0`): nothing a user makes
survives their login session. **Phase 2** adds Cases (`v2.0.0`): named
folders that keep recordings, with sharing, a retention policy, chat across a
whole case, email notifications, and backups.

## The state of this repository

The specification pack is here; the code is not written yet. This repository
starts with what the build answers to:

| Path | What it is |
|---|---|
| `docs/spec/SPEC-PHASE-1.md` | the Phase 1 build specification |
| `docs/spec/SPEC-PHASE-2.md` | the Phase 2 build specification |
| `docs/spec/ADMIN-SETTINGS-CATALOGUE.md` | every admin setting of both phases |
| `docs/whisperx-api.md` | the WhisperX service's API and operating contract, for any consumer |
| `CONTEXT.md` | the vocabulary the app, its pages, and its documents use |
| `docs/adr/` | the decisions that are hard to reverse, and why |
| `docs/research/` | the facts the pins and the designs rest on, with sources |

## Installing (the short version)

The full guide will be `docs/install.md`, written for an IT generalist. In
outline, on a server with an NVIDIA GPU, Ubuntu Server 24.04 or newer, the
NVIDIA driver, the container toolkit with CDI, and Docker with the Compose
plugin:

1. **Before you start.** In the directory: a sign-in group, an optional admin
   group, a read-only service account, and the CA root as PEM. On the server:
   a hostname and a certificate from the office's own CA. On Hugging Face: an
   account that has accepted the diarization model's terms, and a read token.
2. **Prepare the server.** One `sudo` session creates the `transcribe` system
   user (no login, not in the docker group), the app's data folder tree on the
   data drive, and an empty install home.
3. **Clone a Release tag** into that install home, then put `cert.pem`,
   `key.pem`, and the CA root into `tls/` and `ca/`.
4. **`./transcribe install`.** It asks the office facts in plain words, writes
   both `.env` files, generates the secrets, and reports anything missing.
5. **Pull the models**, `docker compose up -d`, create the local admin, and
   run `./transcribe check`, which prints a plain report of every check.
6. **Smoke test.** Sign in, see the status page green, upload one recording
   and watch it through to a transcript.

Upgrading is `./transcribe upgrade <tag>`; each Release's notes open with two
fixed lines, whether the models changed and whether the database migrates.
Nothing on the server ever phones home: to hear about a Release, use GitHub's
Watch, Custom, Releases.

## Licence

The app's own work is in the public domain. It is written by employees of a
United States federal defender office in the course of their duties, so under
17 U.S.C. § 105 it carries no copyright in the United States, and a licence
such as MIT or Apache-2.0 would purport to grant rights the office does not
hold. For the rest of the world, where the statute does not reach, the office
waives whatever rights may attach through the CC0 1.0 Universal public domain
dedication. `LICENSE` carries both, in that order.

So: any office may clone this, change it, run it, and pass it on, without
asking anyone. Contributions are accepted only under the same dedication, for
the reason `CONTRIBUTING.md` explains. CC0 is not OSI-approved, which has no
practical effect here. Everything shipped beside the app's own code keeps its
own licence, listed in `THIRD_PARTY_LICENSES.md`, and the models are
downloaded by each office under their own terms, never redistributed here.

## Support

**The app is provided as is, with no support promised.** Reports are welcome
in this repository's Issues: what went wrong, what you expected, and the
Release you were running. Security problems go through `SECURITY.md`, never
an Issue.
