# Security policy

## Supported versions

The most recent Release is the supported one. Fixes go into a new Release;
there are no backports to older tags.

## Reporting a vulnerability

**Please report privately, and never in an Issue or a pull request.**

Use GitHub's private vulnerability reporting on this repository: the
**Security** tab, then **Report a vulnerability**. It opens a private
advisory that only you and the maintainer can read.

If the button is not there, this repository is still private and you already
have a direct line to the maintainer who gave you access; use that instead.

Please include what you found, how to reproduce it, what an attacker could do
with it, and the Release tag you were running. You will get an
acknowledgement, and a fix or an explanation of why the behaviour is
intended. Nothing is promised on a schedule: this app is maintained by one
office's IT staff.

## Standing alerts on the pinned stack

Dependency scanning reports advisories against two packages the WhisperX
service pins, and both pins are deliberate.

- **transformers 4.57.6.** It cannot move to 5.x: whisperx caps
  `huggingface-hub` below 1.0 and transformers 5 needs 1.5 or later, so the
  two cannot be satisfied together. Moving would mean a new whisperx release
  (see `docs/research/whisperx-pinned-stack.md`).
- **torch 2.8.0+cu128.** It is pinned by whisperx and by the CUDA path this
  generation of card needs.

None of the reported paths is one this service uses. They are
`save_pretrained` with chat-template names, the LightGlue model loader, the
`Trainer` class, and three torch functions (`torch.jit.script`,
`torch.lstm_cell`, `unpack_sequence`). The service loads two pinned local
models, runs inference, and trains nothing. It also runs offline after the
model pull, on an internal Docker network, with no published port.

This is written down so that the answer is on the record rather than worked
out again each time the alerts are looked at. When whisperx releases a version
that frees the pins, the stack moves as a set, which is what
`docs/research/whisperx-pinned-stack.md` exists to make possible.

## What this app holds

Gideon Transcribe holds recordings, transcripts, and notes that are
privileged and confidential. It is built to run inside one office's network,
signed in against that office's directory, and reachable from nowhere else.
Reports about that boundary, about the audit log, about the Admin-access rule
(see [ADR 0004](docs/adr/0004-admins-see-all-content-every-access-audited.md)),
or about anything that could put transcript text where it does not belong,
are especially welcome.
