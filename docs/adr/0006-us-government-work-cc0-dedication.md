---
status: accepted
date: 2026-09-02
---
# Gideon Transcribe's own code is a US government work dedicated under CC0 1.0

The app is written by employees of the Office of the Federal Public Defender for the Middle District of Tennessee in the course of their duties, so under 17 U.S.C. section 105 it carries no US copyright, and a licence such as MIT or Apache-2.0 would be granting rights the office does not hold. The choices considered were MIT, Apache-2.0, and AGPL-3.0; AGPL would also oblige any office that changes the app to publish its changes, a barrier for the IT generalists the app is meant for. It was decided on 2026-09-02 to follow the pattern the same office had already set for another project (confirmed by counsel on 2026-08-28): a `LICENSE` file carrying the US-government-work notice and a worldwide CC0 1.0 Universal dedication for whatever rights attach elsewhere, and a `CONTRIBUTING.md` that accepts contributions only under the same dedication, because Community Defender Organization staff are nonprofit employees who do hold copyright in what they write. The dedication covers the code, the built-in prompt wordings, the guides, and the spec pack.

## Consequences

Any office can clone, change, and run the app without asking anyone, and nothing in the repository needs a copyright header. Everything shipped beside the code keeps its own licence and is listed in `THIRD_PARTY_LICENSES.md`: the Whisper models (MIT), the diarization model (CC-BY-4.0 behind a licence gate that each office accepts itself), the pinned Python and Docker components, and ffmpeg as Debian builds it. A licence on released code cannot be taken back, so this decision holds for every Release once the repository is public; a later effort could only add terms to new versions. If the pending Community Defender Organization reply on that contribution term is ever answered differently, this repository's `CONTRIBUTING.md` follows the answer.
