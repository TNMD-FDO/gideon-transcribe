# Pinned diarizer stack: Nemotron 3 Diarization on NeMo, beside the WhisperX service

Research date: 2026-09-24, the day the diarizer chapter (Phase 5 chapter 4) was built. Target: the same card and driver as the WhisperX service (RTX PRO 6000 Blackwell, driver 595, Ubuntu 24.04 in the container). This is the diarizer image's counterpart of `docs/research/whisperx-pinned-stack.md`: what the image holds, why each pin is what it is, and what a bump has to prove. ADR 0014 is the decision; `docs/research/nemotron-3-diarization.md` is the probe that settled the stack.

## The pin set

| Component | Pin | Why | Source |
|---|---|---|---|
| Base image | `nvidia/cuda:12.8.2-base-ubuntu24.04`, the same digest as the WhisperX image | One CUDA runtime for both containers, so the package's driver requirement does not rise; the torch cu128 wheels carry their own CUDA libraries, so "base" is enough | [S1] |
| Python | 3.12, Ubuntu 24.04's | NeMo needs 3.10 or above; the WhisperX image uses the same | [S2] |
| torch / torchaudio | 2.8.0+cu128 from `download.pytorch.org/whl/cu128` | The WhisperX stack's own wheels. NeMo says "PyTorch 2.7 or above"; the probe's third image ran the model on 2.8.0 with spans byte for byte the same as a torch 2.14 with CUDA 13 run | [S2][S3]; the probe note, part 2 |
| NeMo (`nemo-toolkit[asr]`) | the NeMo Speech repository at commit `cf724ac337d1ebc7d0dda1e23fb80916f52927a5` (2026-09-23), installed from its source archive with the archive's sha256 checked by pip (`a095a36ce9bfd7901eb164552a4c579010473f01c0d9ccd54c9706185acc3c81`) | The released `nemo-toolkit` 3.0.0 on PyPI cannot load the model: its Transformer encoder refuses rotary attention. This commit reports itself as 3.1.0 and loads it. A commit sha names one tree, and the archive's hash catches a changed archive at build | [S2][S4]; the probe note, part 1 |
| The model | `nvidia/Nemotron-3-Diarization`, revision `f667ed73aee57d40cc39428eb768b4fd87a0a29e` | The repository's head when the probe ran and the chapter was built; not gated; OpenMDW-1.1; about 0.45 GB in the cache | [S5] |
| transformers | 5.17.0 | What NeMo at this commit resolved to in the probe; the diarizer image is separate from the WhisperX image, whose transformers is held at 4.57.6 by whisperx, so the two never meet | the probe's freeze |
| lightning / pytorch-lightning | 2.4.0 / 2.6.6 | NeMo's own requirement at this commit | the probe's freeze |
| numpy, scipy, pandas | 2.5.3, 1.18.1, 3.0.6 | The probe's freeze | the probe's freeze |
| hydra-core / omegaconf | 1.3.2 / 2.3.0 | NeMo's configuration stack, pinned by NeMo | the probe's freeze |
| soundfile, librosa | 0.14.0, 1.0.0 | NeMo reads the WAV through soundfile (`libsndfile1` from apt) | the probe's freeze |
| FastAPI / uvicorn | 0.141.1 / 0.52.4 | The container's small HTTP face, the same versions as the WhisperX service's | `whisperx-service/requirements.txt` |
| Cython, packaging | 3.3.0, 24.2 | NeMo's build needs them present before its own install | the probe's freeze |
| everything else | `whisperx-service/diarizer/constraints.txt` | 147 pins, the probe's `pip freeze` on the cu128 image, so a rebuild resolves to the same tree | |

## Why a container of its own

- NeMo is a large toolkit with pins of its own (transformers 5, lightning, hydra). Putting it in the WhisperX image would mean re-verifying that whole stack for a second model's sake, and whisperx 3.8.6 cannot take transformers 5 at all (`huggingface-hub<1.0.0`). Two images, one CUDA runtime.
- The WhisperX service calls the container on the service's private `whisperx` network (`http://diarizer:8100`, no published port) for the spans alone, and attributes words to speakers itself with WhisperX's `assign_word_speakers`, so both diarizers attribute words the same way and the result shape is one.
- The container reserves the same card by the same UUID (`WHISPERX_GPU_UUID`) through CDI, holds the model loaded, and runs one job at a time under a lock, as the service does.

## The run

- Offline chunked inference with the model card's values: speaker cache 264, FIFO 40, chunk 340, right context 40, update period 300, all in frames of 80 ms; read from the service's `.env` (`DIARIZER_*`) so an office can change them without a rebuild.
- Memory: the probe measured 2.3 GB of card memory in use while diarizing (an idle WhisperX's share included) and 5.0 seconds for 25 minutes of audio on torch 2.8.0. The Compose host-memory limit is 4 GB.
- The benchmark gate for the release, run by hand on the server before the tag: time per hour of audio and the card's high point with the WhisperX service beside it. Figures to be written here when the maintainer runs it after `./transcribe upgrade v1.80.0 --build`.

## What a bump has to prove

1. The model loads (the image's build imports the model class; a NeMo without the encoder fails at build, not at the first recording).
2. The spans on a known recording are the same as before the bump, or the difference is explained.
3. torch stays on the WhisperX stack's CUDA (12.8) unless that stack moves first; the driver requirement of the package is the WhisperX note's.
4. When NVIDIA releases a `nemo-toolkit` that loads the model, the pin becomes that version, `requirements.txt` loses the archive line, and ADR 0014 gains a line.

## Sources

- [S1] The base image tags: https://hub.docker.com/r/nvidia/cuda/tags (the digest is in the Dockerfile).
- [S2] NeMo Speech on GitHub, its README's tested versions: https://github.com/NVIDIA-NeMo/Speech
- [S3] The cu128 wheel index: https://download.pytorch.org/whl/cu128
- [S4] nemo-toolkit on PyPI (3.0.0, 2026-08-07): https://pypi.org/project/nemo-toolkit/
- [S5] The model card: https://huggingface.co/nvidia/Nemotron-3-Diarization
- `docs/research/nemotron-3-diarization.md`: the probe, and the stack settled on its third image.
- `docs/research/whisperx-pinned-stack.md`: the WhisperX stack this one sits beside.
- `docs/adr/0014-the-diarizer-is-a-choice-in-its-own-container.md`: the decision.
