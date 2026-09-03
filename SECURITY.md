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

## What this app holds

Gideon Transcribe holds recordings, transcripts, and notes that are
privileged and confidential. It is built to run inside one office's network,
signed in against that office's directory, and reachable from nowhere else.
Reports about that boundary, about the audit log, about the Admin-access rule
(see [ADR 0004](docs/adr/0004-admins-see-all-content-every-access-audited.md)),
or about anything that could put transcript text where it does not belong,
are especially welcome.
