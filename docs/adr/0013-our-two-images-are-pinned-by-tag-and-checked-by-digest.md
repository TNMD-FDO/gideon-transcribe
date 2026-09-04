# ADR 0013: Our two images are pinned by tag, and their digests are checked another way

Date: 2026-09-04
Status: accepted

## The question

The rule for this repository is that every image is pinned by tag and by
digest. The upstream images are: Caddy, PostgreSQL, tusd and the CUDA base
each carry an `@sha256:` in the compose files, and a changed upstream image
cannot arrive unnoticed.

The two images this repository builds cannot be pinned the same way, and the
reason is not carelessness. A digest is the hash of the finished image. The
image for `v1.2.0` is built by the release workflow *from* the commit that
`v1.2.0` points at, after the tag is pushed. The compose file inside that
commit would have to name a hash that does not exist until after the commit
is final. The specification's deliverable list asks for both images "pinned
by digest in the compose file", and that is the one thing a tag cannot
carry about itself.

Three ways round it were weighed:

1. **Publish first, then commit the digests and tag again.** Every Release
   becomes two tags, or a tag that moves, and the tag would point at a commit
   other than the one the image was built from. Moving tags is what
   `./transcribe upgrade` exists to make impossible.
2. **Build from a candidate commit, commit the digests, then tag the
   result.** The tag's own workflow would then have to skip building, or
   would build a second image with a different digest from the one pinned.
   Two artefacts for one Release.
3. **Pin by tag, and check the digest at upgrade time against a record the
   workflow publishes beside the Release.**

## The decision

The third. For the two images this repository builds:

- `compose.yaml` names them by tag, and the tag follows `RELEASE_TAG`, which
  `./transcribe upgrade` writes into `.env` before it pulls or builds.
- The workflow never pushes `latest`, and no tag is ever moved or reused,
  so a tag names one build and one build only.
- The workflow records each image's digest in the run's summary at every
  Release.

The digest check that completes the design is **proposed and not yet
built**: the workflow uploads the two digests as an asset of the GitHub
Release, and `./transcribe upgrade`, after `compose pull`, compares what
arrived with what the Release says was built, and refuses to start on a
mismatch. That turns a registry that served the wrong bytes under the right
tag from an invisible failure into a stopped upgrade. It belongs before the
public flip, because after it the registry is reachable by anyone.

## What this departs from

The Phase 1 deliverables (the specification's closing chapter, item 1) say
both images are "pinned by digest in the compose file". For the reason above
that wording cannot be met by any tag about its own image, and this record
is the maintainer's notice of it. The upstream images meet it exactly. The
rule in `CLAUDE.md`, "images by tag and digest", is read as: by digest where
the digest can be known when the file is written, and by tag with a
published digest to check against where it cannot.

## What guards it

- `test_environment.py` fails if either of our images is named with a fixed
  tag instead of `${RELEASE_TAG}`.
- The release workflow is the only thing that pushes to the registry, and it
  runs only on a tag.
- An upgrade that finds nothing in the registry builds from the tag's own
  source on the server, which is the other way of getting exactly the tag's
  bytes.
