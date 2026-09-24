# ADR 0015: The install is staged, and transcription is a piece behind a Compose profile

Date: 2026-09-24
Status: accepted

## The question

Until v1.82.1 nothing installed without a card: `./transcribe install` stopped when `nvidia-smi` was missing, and the transcription service's Compose file demanded the card's UUID, so the whole stack refused to start without one. Every other part was already optional and added later by its own command (the engine, the fast lane, the directory, mail, the backup), but the guide read as if Active Directory and a certificate from the office's own authority were prerequisites, and the two commands an office needed were a page apart.

The maintainer's ask on 2026-09-24: other offices should find the install as easy as possible, and some will want only parts of the app until they buy hardware. The decisions taken the same day: serve an office with no card yet (cases, incidents, notes, clips, documents and sharing work, and a recording uploaded waits for the card), an office with a card and no engine, and an office with a different or smaller card; offer the Local engine on the office's own card in the walkthrough; offer a self-signed certificate; add every later piece with one command; no CPU-only transcription.

## The decision

- **A piece is the unit.** Transcription, the Fast lane, an Engine, the Directory, Mail and the Backup are the pieces (`CONTEXT.md`). `./transcribe install` asks what the server has and turns on what it can; `./transcribe add <piece>` adds one later; `./transcribe pieces` and the Status page's Pieces card list them from the same facts, with the one command for each. The page runs nothing (ADR 0009).
- **Transcription is the `transcription` Compose profile.** The service and the diarizer carry `profiles: ["transcription"]`; the card's UUID is a default (`:-unset`), never a demand, so the stack starts without it. The install writes the profile when a card is named; `./transcribe upgrade` adds it once to an install from before this release that has a card named, so no office's service stops at the upgrade. `llm-worker` stays without a profile: it costs 2 GB of host memory and is what answers "no engine is configured".
- **A Recording with no Job while the piece is absent is waiting, not failed.** The upload is accepted, the Recording stays Ready with no Job, the pages say "Waiting for the card", and the minute sweep that takes Ready Recordings without a Job hands them over once the piece answers. No column was added: the state is derived. Live recording and Dictation refuse with the piece's words, because they cannot wait.
- **A self-signed certificate is made by the script with openssl, in `tls/`.** A root (ten years) the office trusts once and a certificate for the app's name (two years) signed by it; running again renews under the same root; the office's own certificate replaces it by overwriting the two files. Not Caddy's internal issuer: the Caddyfile runs with automation off, an internal certificate is short-lived and would trip the check's thirty-day line, and its root would live inside a volume. `./transcribe check` notes a self-signed certificate and never fails on it.

## Consequences

- The profile name `transcription` is in every office's `.env` from here on and cannot be renamed without a migration in the script.
- A wrong card UUID now fails when the container starts rather than when Compose reads the file; the self-test before the first start is where it shows.
- `./transcribe check` and the Status page treat a piece that is not installed as a note and a plain pill, never as red; a piece that is installed and does not answer is still red.
- The fast lane is written out in full rather than extending the service: Compose merges an extended service's `profiles` into the child's (proved on the office's server on 2026-09-24), and the lane would otherwise start under the transcription profile alone. CI proves the profile edges: without the profile the service is absent, with it the service and the diarizer are present and the fast lane is not.
- The guides open with what the server has, and each piece has one section under "Add a piece later".
- The memory-fitting rule for a smaller card and the self-test's card check are the next release's (v1.84.0).
