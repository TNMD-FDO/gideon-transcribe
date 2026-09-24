# The diarizer image (Phase 5 chapter 4, ADR 0014): Nemotron 3 Diarization on
# NeMo, in a container of its own beside the WhisperX service. The stack is
# chosen in docs/research/diarizer-pinned-stack.md: the same base and the same
# torch wheels as the WhisperX image, so the two share one CUDA runtime and the
# package's driver requirement does not rise. Do not bump anything casually.
FROM nvidia/cuda:12.8.2-base-ubuntu24.04@sha256:b382332b575435b081b805b15b3aa1779a350a4e513f4d0449b4d7ad098e94ff

LABEL org.opencontainers.image.title="Gideon Transcribe diarizer"
LABEL org.opencontainers.image.description="Nemotron 3 Diarization, served to the WhisperX service on its private network."
LABEL org.opencontainers.image.source="https://github.com/TNMD-FDO/gideon-transcribe"
LABEL org.opencontainers.image.licenses="CC0-1.0"

# Ubuntu 24.04's Python 3.12, the sound library NeMo reads WAVs with, ffmpeg
# for the same, and the compiler NeMo's build needs for its one source
# install. As in the WhisperX image, the apt packages come from the
# distribution, fixed by the base digest.
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3 \
      python3-venv \
      python3-dev \
      build-essential \
      libsndfile1 \
      ffmpeg \
      ca-certificates \
 && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
RUN python3 -m venv "${VIRTUAL_ENV}"

# torch in a layer of its own (the release workflow's 10 GB layer limit), then
# NeMo from its pinned source archive, checked by sha256 as pip fetches it,
# with every transitive package held by constraints.
COPY requirements-torch.txt /tmp/requirements-torch.txt
RUN pip install --no-cache-dir -r /tmp/requirements-torch.txt

COPY constraints.txt requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
 && pip install --no-cache-dir -c /tmp/constraints.txt "fastapi==0.141.1" "uvicorn[standard]==0.52.4"

# The model must load, not merely install: a NeMo that lacks the model's
# encoder fails here, at build, and not at the first recording. The weights are
# not in the image, so this imports the class alone.
RUN python -c "from nemo.collections.asr.models import SortformerEncLabelModel"

# The container runs as the office's own account (Compose's `user:`), which
# has no entry in the image's passwd file. torch's compile machinery, which
# NeMo imports at start, asks the account's name and its cache folder and
# fails on a bare uid ("getpwuid(): uid not found"), so both are given here.
ENV HOME=/tmp MPLCONFIGDIR=/tmp/matplotlib \
    USER=diarizer LOGNAME=diarizer \
    TORCHINDUCTOR_CACHE_DIR=/tmp/torchinductor

# The same mounted model folder as the WhisperX service: the pull fetches the
# weights there, and this container reads them offline.
ENV HF_HOME=/models/hf \
    TORCH_HOME=/models/torch \
    CUDA_CACHE_PATH=/models/cuda-cache \
    CUDA_CACHE_MAXSIZE=4294967296 \
    HF_HUB_OFFLINE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY server.py /opt/diarizer/server.py
WORKDIR /opt/diarizer
EXPOSE 8100
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8100", "--workers", "1"]
