---
status: accepted
date: 2026-09-01
---
# Build a fresh, pinned, ASR-only WhisperX service and reuse nothing from the old apps

An earlier engine wrapper, kept only as a saved container image, was the one engine proven on the office's GPU generation (RTX PRO 6000 Blackwell), but it was built from unpinned nightly PyTorch, so it cannot be rebuilt reproducibly, and it bundles a UI, its own auth, cases, prompts, and a docker.sock mount. The server was being rebuilt from scratch, and the decision for this effort is that nothing is reused from any existing app: not a saved image, not earlier transcription code, not an earlier engine wrapper, not Speakr, and not the office's other Django apps (which may be read for facts about the directory only). The WhisperX service is built fresh from pinned, free components as an independent ASR-only container that other apps can consume.

## Consequences

Compatibility of the pinned stack with that GPU generation must be re-verified (a research ticket), and a benchmark on real hardware is a build-time gate. Any earlier package stays as an archive and a source of facts (for example its pip freeze), never of code.
