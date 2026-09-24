# ADR 0014: The diarizer is a choice, Nemotron 3 by default, in a container of its own

Date: 2026-09-24
Status: accepted

## The question

The WhisperX service tells voices apart with `pyannote/speaker-diarization-community-1`, inside a stack pinned on purpose (torch 2.8.0 with CUDA 12.8, pyannote.audio 4.0.7, whisperx 3.8.6; `docs/research/whisperx-pinned-stack.md`). On 2026-09-23 NVIDIA released Nemotron 3 Diarization: open weights under OpenMDW 1.1, not gated, up to eight voices, end to end. Probed on the office's server the next day (`docs/research/nemotron-3-diarization.md`), it was right by ear where the page was wrong on eleven of thirteen disputed stretches of the one recording the office had corrected, and the maintainer chose to make it the diarizer while keeping pyannote reachable.

Three things made the shape a decision rather than a swap:

1. **The model needs NeMo past its last release.** The released `nemo-toolkit` 3.0.0 cannot load it (its encoder has no rotary attention); the NeMo Speech repository at commit `cf724ac3` (2026-09-23) can. So the pin is a source commit, not a PyPI version, until NVIDIA cuts a release.
2. **NeMo is a large toolkit with its own pins.** Installed with no constraint it pulled torch 2.14 with CUDA 13, which needs a newer driver than the WhisperX stack asks for. Installed on torch 2.8.0 with CUDA 12.8 (NeMo says 2.7 or above) it loaded and ran the model with output identical to the CUDA 13 run, on the probe's recording.
3. **The WhisperX image must not move.** Adding NeMo to it would mean re-verifying the whole stack for a second model's sake.

## The decision

- **The diarizer is a Panel setting**, `nemotron` or `pyannote`, default `nemotron`; the service takes it as a request field and returns one result shape whichever runs. pyannote's code, weights and gate stay in the package.
- **Nemotron runs in a third image built here**, `diarizer`: NeMo's ASR extra from a source archive of commit `cf724ac3`, checked by sha256 at build (never a live `git+https` fetch, which cannot be reproduced), on torch 2.8.0 with CUDA 12.8, the same wheels as the WhisperX image, so the package's hardware requirement does not rise. The WhisperX service calls it over the service's private network for the spans and attributes words itself, so both diarizers attribute words the same way.
- **The same rules as the other two images**: tagged with `RELEASE_TAG`, published by the release workflow, its digest recorded and checked at upgrade (ADR 0013), reserved to the same card by UUID as the WhisperX service, weights pinned by revision in `models.yaml` and fetched at install, offline afterwards.
- **When NVIDIA releases a NeMo version that loads the model**, the pin becomes that version and this ADR gains a line; nothing else changes.

## Consequences

- `CLAUDE.md`'s "two images are built here" becomes three; ADR 0013's wording covers three; CI's compose check and the release workflow build and publish three.
- The speaker-count hint and the per-speaker embeddings are pyannote's alone; under Nemotron the hint control greys with its reason and voice prints (Phase 5 chapter 2, deferred) will need an embedding step of their own.
- A new office needs no Hugging Face token for diarization; the token becomes what an office gives to have pyannote as well.
- About 2 GB more of the Transcribe card while a job diarizes, and a third image on the Docker volume: a line in the box ledger at the release.
- The pinned-stack discipline applies to a third stack: a research note records what the diarizer image holds and why, and a bump is a research ticket first.
