---
status: accepted
date: 2026-09-01
---
# Build a new Django app rather than adopt Speakr

Speakr (free, AGPL) already covers most of the requirement list: the WhisperX /asr contract with diarization, a speaker management panel with voice matching, chat and summaries, folders with internal sharing, retention with overrides, DOCX/SRT/VTT export, synced video playback, and a job queue. It does not do three things this office requires, and they are architectural in Speakr: LDAP sign-in (OIDC only, and the hardening plan rules out SSO middleware), translation to English (the connector hard-codes transcribe), and an ephemeral no-retention mode. Retention and sharing are env-only, not admin-panel settings. It is also a single-maintainer project with every release tagged alpha. We build a new Django app in the office's usual stack and use Speakr's documentation only as a reference catalogue of features and settings.

## Consequences

We own the speaker, queue, and sharing features Speakr would have supplied. Feature parity with Speakr is not a goal; the requirement list is.
