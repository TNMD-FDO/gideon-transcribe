# Graphics cards the transcription stack runs on

Started 2026-09-24 with the staged install (ADR 0015), for the offices that will run this app on a card other than the one it was built on. The pinned stack (`whisperx-pinned-stack.md`, `diarizer-pinned-stack.md`) was chosen for one generation and measured on one card. This note keeps three things apart: what has been **verified** by running the benchmark gate, what is **expected** from the primary sources, and what **offices report**. The self-test (`docker compose run --rm whisperx selftest`) prints the card's generation against the verified list and says whether the service and the diarizer fit at the configured batch size; `./transcribe install` and `./transcribe add transcription` set the batch size by the card's memory from the table at the end.

## Verified

| Card | Memory | Compute capability | Driver | Batch | What was measured | When |
|---|---|---|---|---|---|---|
| NVIDIA RTX PRO 6000 Blackwell | 96 GB | 12.0 | 595 | 16 | The Phase 1 benchmark gate over about six hours of real recordings: 12.3 GB high point for `large-v3-turbo`, 16.6 GB with both models in turn; the diarizer 1.3 GB idle, 3.9 GB on a 50-minute recording, 6.4 GB on a 104-minute one (`whisperx-service/README.md`, GPU budget) | 2026-09-03 and 2026-09-24 |

## Expected

From the sources the pinned stack rests on, not from running it:

- **The floor is compute capability 7.5 (Turing) under a driver of 570 or newer.** The images are `nvidia/cuda:12.8` on torch 2.8.0 with CUDA 12.8; CUDA 12.x runs on any driver at or above 525, and compute capability 12.0 needs CUDA 12.8 and driver 570.26 or newer, so 570 is the floor that serves every generation at once. Torch 2.8's CUDA 12.8 wheels carry kernels from 7.5 up. Below 7.5 the wheels carry nothing, and the self-test says so.
- **CTranslate2 (faster-whisper's engine) ships SASS up to 8.6 plus PTX**, so Ampere and older run compiled kernels, and Ada (8.9), Hopper (9.0) and Blackwell (10.x, 12.0) run from PTX with a first-load JIT that the driver's kernel cache keeps between starts (`CUDA_CACHE_PATH`, a folder the image mounts). The office's own Blackwell card runs this way already.
- **INT8 is off on Blackwell** (`whisperx-pinned-stack.md`, known pitfalls); on Ada and Ampere it is available, and the service does not use it, so nothing changes.
- **The diarizer** (NeMo at the pinned commit, torch 2.8.0 with CUDA 12.8) is documented by NVIDIA for Ampere through Blackwell; Turing is expected to work from PTX and is unverified.
- **Memory, not generation, is the likely limit on a smaller card.** The service holds about 12 GB with the default model loaded and adds about a gigabyte of the card for every 8 of batch size; the diarizer holds 1.3 GB and grows with the recording, about 2.5 GB an hour of audio. A 24 GB card runs recordings up to about two hours at batch 8; a 16 GB card runs short recordings at batch 4 and will run out of memory on a long one; under 16 GB nothing fits and the install refuses. CPU-only transcription is not offered (hours per hour of audio, and a second unpinned stack to keep).

## Reported by offices

Each row is one card an office ran the stack on, as they reported it. Add a row when you have one; the self-test's first lines give the card, the memory, the generation and the driver.

| Card | Memory | Compute capability | Driver | Batch | What happened | Reported |
|---|---|---|---|---|---|---|
| | | | | | | |

## The batch size by the card

What `./transcribe` sets in `whisperx-service/.env` (`WHISPERX_BATCH_SIZE`), from the rule of thumb above; every figure is an estimate until a row above measures it.

| Card memory | Batch size | Expect |
|---|---|---|
| under 16 GB | none: the install refuses | nothing fits beside the diarizer |
| 16 to 23 GB | 4 | short recordings; a recording over an hour may run out of memory |
| 24 to 31 GB | 8 | recordings up to about two hours; a little slower than 16 |
| 32 GB and up | 16 | the measured configuration |

The Local engine, when the card is to hold it too, wants about 20 GB more; `./transcribe` computes its share as 20 divided by the card's memory (0.21 of 96 GB, 0.42 of 48 GB) and offers the Local engine at install only when the card has 24 GB for transcription and 20 GB for the engine, that is 44 GB or more.

## Sources

- `docs/research/whisperx-pinned-stack.md` and its sources S2, S3, S15, S26, S27, S31, S32 (the CUDA and driver floors, the CT2 wheel's kernels, cuDNN's support matrix).
- `docs/research/diarizer-pinned-stack.md` (the diarizer's stack and its measured memory).
- `whisperx-service/README.md`, GPU budget (the measured figures).
