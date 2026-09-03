# Third-party licences

Gideon Transcribe's own work is public domain (see `LICENSE`). Everything
shipped beside it, in the two images built from this repository and in the
upstream images the compose file pins, keeps its own licence. This file lists
those components.

The sources for the list are `docs/research/github-distribution-facts.md`
(section 6) and `docs/research/whisperx-pinned-stack.md`, both of which ship
in this repository and carry the URL each licence was read from.

Exact versions are not repeated here: the pinned versions live in
`whisperx-service/` (the service's requirements and Dockerfile) and in the
compose files, and each Release records the ones it ships. The one exception
is ffmpeg, whose package versions each Release must record here (see note 1).

| Component | Licence | Note |
|---|---|---|
| whisperx | BSD-2-Clause | |
| faster-whisper | MIT | |
| CTranslate2 | MIT | |
| pyannote.audio (code) | MIT | |
| pyannote/speaker-diarization-community-1 (weights) | CC-BY-4.0 | behind a Hugging Face gate that each office accepts itself; attribution required; never redistributed with the app |
| OpenAI Whisper (code and model weights) | MIT | the Hugging Face mirror `openai/whisper-large-v3` is tagged Apache-2.0 and is not gated |
| PyTorch | BSD-3-Clause | |
| every other component pinned on the WhisperX stack | as pinned | `docs/research/whisperx-pinned-stack.md` is the list |
| Django | BSD-3-Clause | |
| Procrastinate | MIT | the app's background worker, on PostgreSQL; the stack ships no Redis or Valkey, so there is no licence note for either |
| python-docx | MIT | |
| Caddy | Apache-2.0 | upstream image |
| PostgreSQL | the PostgreSQL Licence | upstream image |
| tusd | MIT | upstream image |
| vLLM | Apache-2.0 | upstream image, the Local engine (profile `llm`) |
| Qwen3 weights | Apache-2.0 | the Local engine's model; not gated |
| restic | BSD-2-Clause | upstream image, Phase 2 (profile `backup`) |
| `nvidia/cuda` base image | NVIDIA Deep Learning Container Licence (proprietary) | the WhisperX service's base; see note 2 |
| ffmpeg as Debian builds it, with its codec packages | GPL v2 or later | see note 1 |

## 1. ffmpeg and the GPL

Debian's ffmpeg is a GPL build, because it links libx264 (with libx265 and
libxvid), which the app needs for the H.264 Playback copies and Clips.
Calling ffmpeg as a separate program leaves the app's own terms untouched:
running a program through pipes and command-line arguments does not combine
the two works.

Publishing an image that contains that ffmpeg is another matter: whoever
distributes GPL binaries must make the complete corresponding source
available for as long as the binaries are distributed. So **each Release
records the exact ffmpeg and codec package versions it ships in the table
below, with a pointer to Debian's source packages for them.**

| Release | ffmpeg package | codec packages | Source |
|---|---|---|---|
| *(none published yet)* | — | — | — |

## 2. The WhisperX image

The image built from `whisperx-service/` is a derived container on
`nvidia/cuda`, under the NVIDIA Deep Learning Container Licence. That licence
permits distributing a derived container that adds material functionality,
forbids distributing the base container as a stand-alone product, and
licenses its proprietary parts to run only on systems with NVIDIA GPUs. The
image is proprietary in that respect and is listed as such.

## 3. Models

No model weights ship with the app. The WhisperX service downloads them on
first use: the Whisper model from its public repository, and the diarization
model from behind a Hugging Face gate that each installing office accepts
itself with its own account and token. The diarization model is CC-BY-4.0 and
requires attribution.
