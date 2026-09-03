---
status: accepted
date: 2026-09-02
---
# Gideon Transcribe is a fully separate stack beside the platform project on the server

The server is provisioned and operated by another project of the same office, the platform project, which renders one Compose project, one reverse proxy on port 443 with one hostname, secrets as files and no `.env`, images by digest from a local registry, and a release cadence that placed a "Transcribe" branch after its own 1.0. Gideon Transcribe could have shipped inside that release, or as a sibling Compose project that borrows the platform's ingress. It was decided on 2026-09-02 that it is a fully separate stack: its own repository, release cadence, install script, Compose project, data folder on the data drive, reverse proxy, certificate, LDAP configuration, and backup job. It shares only the box, one GPU (the platform's language-model engine keeps the other), and, as configuration, the address and token of a shared language-model engine.

## Consequences

The "clone, fill in `.env`, compose up" install story stands and the platform project's release rules do not bind this app. The platform's proxy owns port 443, so the app answers on another port or a second address; the deployment-topology decision chose the port. The app's data is outside the platform's backup set and needs its own job. Reaching a shared engine means joining that project's Docker network as an external network with a copied token; that is the one coupling to another project's internals and must be a configuration value, never code. If the office later wants transcription inside the platform project, that is a new effort, not a change to this one.
