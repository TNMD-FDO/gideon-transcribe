---
status: accepted
date: 2026-09-03
---
# The office's build server tracks `main` until `v1.0.0`

The specification's rule is that code reaches a server only by fetch and checkout at a Release tag. `./transcribe upgrade` refuses any other checkout, `./transcribe check` reports one, and the install guide's clone names a tag. The rule protects an installing office from running code that nobody released, and it is the reason an Upgrade is a checkout and never a copy from a workstation.

Bringing the WhisperX service up on the office's own GPU is a fix-and-retry loop against real hardware: a driver-compiled kernel cache, a gated model download, a card's memory ceiling, and a benchmark that has to run before the batch size and the model default can be written down at all. Under the rule as written, every round of that loop would need its own patch tag, and the tag list would record the build's stumbles rather than its Releases.

So, during the Phase 1 build and only on the office's own build server, the checkout at the Install home may sit on `main`. The rule resumes in full at `v1.0.0`, which is the first Release any office installs.

## Consequences

- The refusal is still written and tested exactly as specified. This is an operating exception for one machine during one period, not a code path, and nothing in the product learns about it.
- The build server is therefore not a reference installation while this holds: it can be running code that no Release names. The install path is first tested for real when a tag is cloned into an empty Install home, and that test is owed before `v1.0.0`.
- Tags are still cut at the checkpoints of each slice, so there is always a named point to go back to.
- The exception ends at `v1.0.0`, and this record is the only place it exists.
