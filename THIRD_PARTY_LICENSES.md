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
| psycopg | LGPL-3.0 | the app's PostgreSQL driver, used as a library and unmodified |
| gunicorn | MIT | |
| whitenoise | MIT | |
| python-docx | MIT | |
| lxml | BSD-3-Clause | python-docx's own dependency |
| python-ldap | Python-style (its own permissive licence) | directory sign-in; see ADR 0010 |
| Markdown (Python-Markdown) | BSD-3-Clause | renders the two guides at build time; see ADR 0012 |
| audiowaveform | GPL-3.0-or-later | in the app image, fetched as a `.deb` by version and hash and called as a separate program; source at `github.com/bbc/audiowaveform`; see note 1 |
| Caddy | Apache-2.0 | upstream image |
| PostgreSQL | the PostgreSQL Licence | upstream image |
| tusd | MIT | upstream image |
| vLLM | Apache-2.0 | the Local engine's upstream image, behind the `llm` Compose profile, off by default; pulled by digest only when an office turns the profile on |
| Qwen3.5-4B weights (`Qwen/Qwen3.5-4B`) | Apache-2.0 | the Local engine's default model, not gated; downloaded by the Local engine itself on its first start, never shipped in an image; an office that names another model in `LLM_LOCAL_MODEL` takes on that model's licence |
| restic | BSD-2-Clause | the Backup chapter's upstream image; not yet shipped |
| `nvidia/cuda` base image | NVIDIA Deep Learning Container Licence (proprietary) | the WhisperX service's base; see note 2 |
| ffmpeg as Debian and Ubuntu build it, with its codec packages | GPL v2 or later | see note 1 |

## 1. ffmpeg and the GPL

The ffmpeg in both images is a GPL build, because it links libx264 (with
libx265 and libxvid), which the app needs for the H.264 Playback copies and
Clips. Calling ffmpeg as a separate program leaves the app's own terms
untouched: running a program through pipes and command-line arguments does not
combine the two works. The same is true of audiowaveform, which draws the
waveform under the player and is GPL-3.0-or-later: the app runs it as a
program and reads the file it writes.

The two images take it from different distributions, because they are built on
different bases: the app image from Debian 13, and the WhisperX service image
from Ubuntu 24.04, which is what its CUDA base image is built on. Both are
recorded below.

Publishing an image that contains that ffmpeg is another matter: whoever
distributes GPL binaries must make the complete corresponding source
available for as long as the binaries are distributed. So **each Release
records the exact ffmpeg and codec package versions it ships in the table
below, with a pointer to Debian's source packages for them.**

| Release | Image | ffmpeg package | codec packages | Source |
|---|---|---|---|---|
| v0.2.0, v0.3.0, v0.4.0, v1.0.0, v1.1.0, v1.2.0, v1.2.1, v1.2.2, v1.2.3, v1.3.0, v1.4.0, v1.5.0, v1.6.0, v1.7.0, v1.8.0, v1.9.0, v1.10.0 | app | `7:7.1.5-0+deb13u1` | `libavcodec61 7:7.1.5-0+deb13u1`, `libx264-164 2:0.164.3108+git31e19f9-2+b1`, `libx265-215 4.1-2`, `libxvidcore4 2:1.3.7-1+b2` | Debian 13 (trixie) source packages |
| v0.2.0, v0.3.0, v0.4.0, v1.0.0, v1.1.0, v1.2.0, v1.2.1, v1.2.2, v1.2.3, v1.3.0, v1.4.0, v1.5.0, v1.6.0, v1.7.0, v1.8.0, v1.9.0, v1.10.0 | whisperx | `7:6.1.1-3ubuntu5` | `libavcodec60 7:6.1.1-3ubuntu5`, `libx264-164 2:0.164.3108+git31e19f9-1`, `libx265-199 3.5-2build1`, `libxvidcore4 2:1.3.7-1build1` | Ubuntu 24.04 (noble) source packages |

The seventeen Releases from v0.2.0 to v1.10.0 share a row each because their
images are the same builds: the base image digest is pinned in both Dockerfiles, and
nothing in either image's package list changed between the tags. The versions
were read from the running images with `dpkg-query` on that day. A later
Release adds a row of its own when a version changes, and repeats the row
when none does. The same rule covers audiowaveform in the app image, whose
version and hash are fixed in the Dockerfile itself (`1.10.2`).

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
