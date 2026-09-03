---
status: accepted
date: 2026-09-02
---
# The office-wide one-transcription-at-a-time rule is enforced inside the WhisperX service

The requirement list asks for a queue so that only one transcription runs at a time across the whole office. The natural home for a queue is the app, but the WhisperX service is an independent container that other apps will consume (ADR 0002), and a queue inside this app would not stop a second consumer from transcribing beside it on the same GPU. It was decided at charting (2026-09-01) and confirmed on the contract ticket (2026-09-02) that the service holds the single line: every consumer submits jobs to it, the service runs exactly one job at a time in arrival order across all consumers, keeps the line across its own restarts, and tells each job its position. The app keeps its own Queue for what the service cannot know: Batches, per-user limits, the order of a Recording's Sides, the Workspace keep-alive rule, and what users see.

## Consequences

Two lines exist by design and their units differ: the app's Job is one Recording, the service's job is one Side, which the app calls a Run. The service is the only place the GPU rule is enforced, so no consumer can bypass it, and a future move to parallel transcription (a second worker or a second GPU) is a change to the service that every consumer inherits without code changes of its own. The service therefore needs a durable job store and a status surface (position, audio ahead, measured speed) that a bare transcription engine would not, and the service's serial behaviour is part of its published contract, not an internal detail.
