# Gideon Transcribe

Local transcription, translation to English, and speaker diarization for an
office that handles privileged material, running entirely on the office's
own server. Free tools only, Docker only, no cloud service and nothing sent
outside the building.

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
  with Admins from an Admin group, a manual flag, or a Local admin account.
- Upload one file or many as a Batch, from the browser; every recording is
  inspected, prepared, and given a playback copy. A finished batch offers its
  transcripts as one download and a way to clear the lot and start the next.
- Transcription by a pinned WhisperX service on the office's own GPU, one run
  at a time across the whole office, in arrival order, with no priority for
  anyone and a queue everyone can see.
- Translation to English, and speaker diarization, as per-recording choices.
- A viewer with the transcript at reading width, a synced audio and video
  player, a waveform timeline, correction, speaker naming, search, and
  clips.
- Export to Word, plain text, and SRT captions.
- Cases: named pages of recordings for one matter that outlive the session
  that uploaded them, behind an admin toggle, with a search across each case.
- An admin panel: status, queue, users, audit log with a hash chain and an
  integrity check, an installation page, and about thirty settings that apply
  through a tray with an audit note.
- Three guides: the user guide and the admin guide are rendered into the app
  itself, so nobody needs this repository to read them; the install guide is
  here.

Everything a user does not put in a case is removed when their login
session ends, by design.

Also built: the AI assistant, summaries, a chat over the transcript and
speaker name suggestions, against an office's own vLLM or a small Local
engine the stack runs itself, and the retention policy with its recycle bin.
**Not built yet**, and said so rather than implied: the rest of Cases:
sharing a case with colleagues, the speakers tab, chat across a case, email
notifications, and backups. The
specification for all of it is in `docs/spec/`, and the changelog says
exactly what each Release holds.

## The state of this repository

The app is built and in daily use at the office that wrote it, upgraded
only at Release tags. The `v0.x` Releases are that office's own, marked as
pre-releases; `v1.0.0` is the first Release meant for another office to
install, and the point at which this repository goes public. The Releases
page lists every tag, and each Release's notes are its section of
`CHANGELOG.md`, opening with two fixed lines: whether the models changed and
whether the database migrates.

| Path | What it is |
|---|---|
| `docs/install.md` | the install guide, for the person setting up a server |
| `docs/user-guide.md` | the user guide, served in the app at `/help/` |
| `docs/admin-guide.md` | the admin guide, served in the app's Admin panel |
| `app/` | the Django app, its Dockerfile, and its tests |
| `whisperx-service/` | the transcription service: Dockerfile, compose file, models list, README |
| `transcribe` | the one script an Admin runs on the server: install, check, upgrade, and the rest |
| `compose.yaml` | the whole stack |
| `docs/spec/` | the two build specifications and the settings catalogue, which the code answers to |
| `docs/whisperx-api.md` | the WhisperX service's API and operating contract, for any consumer |
| `CONTEXT.md` | the vocabulary the app, its pages, and its documents use |
| `docs/adr/` | the decisions that are hard to reverse, and why |
| `docs/research/` | the facts the pins and the designs rest on, with sources |

## Installing (the short version)

The full guide is [`docs/install.md`](docs/install.md), written for an IT
generalist. In outline, on a server with an NVIDIA GPU, Ubuntu Server 24.04
or newer, the NVIDIA driver, the container toolkit with CDI, and Docker with
the Compose plugin:

1. **Before you start.** In the directory: a sign-in group, an optional admin
   group, a read-only service account, and the CA root as PEM. On the server:
   a hostname and a certificate from the office's own CA. On Hugging Face: an
   account that has accepted the diarization model's terms, and a read token.
2. **Prepare the server.** One `sudo` session creates the `transcribe` system
   user (no login, not in the docker group), the app's data folder on the
   data drive, and an empty install home.
3. **Clone a Release tag** into that install home, then put `cert.pem`,
   `key.pem`, and the CA root into `tls/` and `ca/`.
4. **`./transcribe install`.** It asks the office facts in plain words, writes
   both `.env` files, generates the secrets, and reports anything missing.
5. **Pull the images and the models**, `docker compose up -d`, create the
   Local admin, and run `./transcribe check`, which prints a plain report of
   every check.
6. **Smoke test.** Sign in, see the status page green, upload one recording
   and watch it through to a transcript.

Upgrading is `./transcribe upgrade <tag>`; each Release's notes open with two
fixed lines, whether the models changed and whether the database migrates.
Nothing on the server ever phones home: to hear about a Release, use GitHub's
Watch, Custom, Releases. Nothing is ever pushed from a workstation to a
server or copied over the install folder.

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
