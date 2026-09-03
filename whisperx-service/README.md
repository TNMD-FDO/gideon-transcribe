# The WhisperX service

Transcription, translation to English, word timing, and speaker separation, on
one GPU, one job at a time, with nothing leaving the building.

This folder is a product of its own. It has its own image, its own settings,
its own version number, and its own README, and it runs without the app that
normally consumes it. Any application holding a token for it is a Consumer and
uses the same contract, which is written out in `docs/whisperx-api.md` at the
top of this repository.

## What state this is in

The image and its pinned stack are built. The API, the model pull, the token
command, and the benchmark harness arrive in the commits that follow, and this
README grows with them. Until then the useful command is `selftest`.

## Building it

From this folder, on the server that has the card:

```bash
docker compose build
```

The image is built on `nvidia/cuda:12.8.2-base-ubuntu24.04`, pinned by digest,
and everything installed into it is pinned to an exact version. The reasons for
each pin are in `docs/research/whisperx-pinned-stack.md`. Do not raise a
version without reading that file first: this stack was chosen for one
generation of card, and several of the pins hold each other in place.

The build takes a while the first time, because the torch and CUDA wheels are
several gigabytes.

## Settings

Copy `.env.example` to `.env` and fill in the values written in angle brackets.
Every key has a comment above it saying what it does. The three that have no
sensible default are the card's UUID, the account the container runs as, and
the two folders on the server.

On a full installation, `./transcribe install` writes this file for you and you
never edit it by hand.

## Checking the container

```bash
docker compose run --rm whisperx selftest
```

It prints what the container can see: the pinned versions, the card and its
compute capability, the ffmpeg version and whether it can decode G.729, and
whether the mounted folders can be written to. It ends either with "Everything
this container needs is in place" or with a list of what is wrong and what to
look at. Nothing is downloaded and no model is loaded, so it is safe to run at
any time.

## GPU budget

To be filled in by the Phase 1 benchmark gate: the measured peak video memory
at the batch size the gate chooses. That figure is what to check before
anything else is placed on the same card.
