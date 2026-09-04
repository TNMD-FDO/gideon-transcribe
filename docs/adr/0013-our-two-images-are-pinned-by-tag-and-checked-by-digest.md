# ADR 0013: Our two images are pinned by tag, and their digests are checked at upgrade

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
- After both images are pushed, the workflow asks the registry what each tag
  resolves to and records it, one line per image as `name:tag@sha256:...`,
  in three places: appended to the Release's notes for a person to read,
  attached to the Release as `digests.txt`, and **as a git note on the
  tagged commit under `refs/notes/digests`**.
- `./transcribe upgrade`, when it has pulled rather than built, fetches that
  note and compares each pulled image's digest with the record. A mismatch
  stops the upgrade before anything is started, names the image, prints
  both digests, and offers `--build` as the way that trusts the source and
  not the registry. A Release with no record is said so and the upgrade
  goes on: a Release has none before its workflow has finished publishing,
  and none from before v1.0.0 has one, and the upgrade cannot tell the two
  apart. An office that wants certainty waits for the Release to appear on
  GitHub, or builds.

## Why a git note and not only the attached file

The record has to reach the server, and the server reaches GitHub in one way:
`git fetch` over SSH with a read-only deploy key. It holds no token. A
private repository hands out its release assets only to a token, so the
attached `digests.txt` is unreachable from the server while the repository
is private, and it is private until the public flip. A git note travels by
the same fetch and the same key as the code, whether the repository is
private or public, so it is the copy the server reads. The attached file and
the notes section are for people.

## What this departs from

The Phase 1 deliverables (the specification's closing chapter, item 1) say
both images are "pinned by digest in the compose file". For the reason above
that wording cannot be met by any tag about its own image, and this record
is the maintainer's notice of it. The upstream images meet it exactly. The
rule in `CLAUDE.md`, "images by tag and digest", is read as: by digest where
the digest can be known when the file is written, and by tag with a
published digest checked at upgrade where it cannot.

## What guards it

- `test_environment.py` fails if either of our images is named with a fixed
  tag instead of `${RELEASE_TAG}`.
- `test_transcribe.py` runs the comparison against a fake docker: a match
  passes, a mismatch stops with both digests printed, a missing image is a
  mismatch and not a pass, and a missing record is said so. It also fails if
  the workflow and the script stop agreeing on the ref the record lives
  under, or on the shape of its lines.
- The release workflow is the only thing that pushes to the registry or
  writes the note, and it runs only on a tag.
- An upgrade that finds nothing in the registry builds from the tag's own
  source on the server, which is the other way of getting exactly the tag's
  bytes.
