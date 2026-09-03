# The WhisperX service image.
#
# The base image, Python, and every pinned package were chosen in
# docs/research/whisperx-pinned-stack.md for the RTX PRO 6000 Blackwell cards
# (compute capability 12.0) under the NVIDIA 595 driver. Nothing here is
# arbitrary, and the risks behind each pin are written down in that file and in
# docs/whisperx-api.md. Do not bump anything casually.
#
# The base is pinned by tag and by digest. The digest is what actually fixes it;
# the tag is there so that a person can read which one it is. CUDA 12.x runs on
# any driver from 525 up, and the torch cu128 wheels bring their own CUDA
# libraries, so the small "base" variant is enough.
FROM nvidia/cuda:12.8.2-base-ubuntu24.04@sha256:b382332b575435b081b805b15b3aa1779a350a4e513f4d0449b4d7ad098e94ff

LABEL org.opencontainers.image.title="Gideon Transcribe WhisperX service"
LABEL org.opencontainers.image.description="Local transcription, alignment, and speaker diarization on one GPU, one job at a time."
LABEL org.opencontainers.image.source="https://github.com/TNMD-FDO/gideon-transcribe"
LABEL org.opencontainers.image.licenses="CC0-1.0"

# Ubuntu 24.04 carries Python 3.12 and ffmpeg 6.1.1. whisperx wants Python 3.10
# to 3.13 and torchcodec wants FFmpeg 4 to 9, so both sit in range.
#
# These apt packages are taken from the distribution rather than pinned to an
# exact version. Ubuntu removes superseded versions from its archive within
# weeks, so an apt pin would make this image unbuildable long before any of the
# pins above went stale, and the base image digest already fixes which Ubuntu
# this is. The exact ffmpeg and codec versions of each Release are recorded in
# THIRD_PARTY_LICENSES.md instead.
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3 \
      python3-venv \
      ffmpeg \
      ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# ffmpeg must be able to decode G.729, which is what a phone system exports
# inside a WAV container. Failing the build here beats failing at the first
# jail call.
RUN ffmpeg -hide_banner -decoders | grep -qw g729

# A virtual environment, because Ubuntu marks its system Python as externally
# managed. pip is whatever the base image's own ensurepip carries, so it is
# fixed by the digest above and is never upgraded here.
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
RUN python3 -m venv "${VIRTUAL_ENV}"

# Two installs, so that torch and the CUDA libraries land in a layer of their
# own. The release workflow builds this image on a hosted runner, where no
# single layer may exceed 10 GB, and these wheels are most of the image.
COPY requirements-torch.txt /tmp/requirements-torch.txt
RUN pip install --no-cache-dir -r /tmp/requirements-torch.txt

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# faster-whisper loads cuBLAS and cuDNN from the wheels torch brought with it,
# and its README says to put those two folders on the library path.
ENV LD_LIBRARY_PATH="/opt/venv/lib/python3.12/site-packages/nvidia/cublas/lib:/opt/venv/lib/python3.12/site-packages/nvidia/cudnn/lib"

# One mounted folder holds every model and the driver's compute cache:
#   HF_HOME          the two ASR models, the diarization model, and any
#                    alignment model fetched from the hub
#   TORCH_HOME       the torchaudio alignment bundles and torch hub
#   CUDA_CACHE_PATH  the driver's compiled kernels. CTranslate2's wheels carry
#                    no sm_120 code, so the driver compiles them from PTX on
#                    first load; keeping the cache on the mounted folder means
#                    that pause is paid once per image and not once per
#                    container start. The size is raised to the 4 GiB maximum.
#
# HF_HUB_OFFLINE is on by default: after the pull, the service makes no network
# call of its own. The pull command lifts it for its own process only.
# pyannote's telemetry is off, or it would report the pipeline class, the file
# duration, and the speaker-count arguments on every call.
ENV HF_HOME=/models/hf \
    TORCH_HOME=/models/torch \
    CUDA_CACHE_PATH=/models/cuda-cache \
    CUDA_CACHE_MAXSIZE=4294967296 \
    HF_HUB_OFFLINE=1 \
    PYANNOTE_METRICS_ENABLED=0 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# The container runs as the app's own system user, set by the compose file, so
# nothing here is owned by root beyond what is read-only anyway.
COPY service/ /opt/service/service/
WORKDIR /opt/service

EXPOSE 8000
ENTRYPOINT ["python", "-m", "service"]
CMD ["serve"]
