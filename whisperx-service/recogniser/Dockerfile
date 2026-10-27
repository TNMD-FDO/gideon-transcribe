# The recogniser image (Phase 1 chapter 7, ADR 0025): Qwen3-ASR-1.7B and its
# forced aligner, in a container of their own beside the WhisperX service.
# The stack is chosen in docs/research/qwen3-asr.md, part 3: the same base
# and the same torch wheels as the other two GPU images, so the three share
# one CUDA runtime and the package's driver requirement does not rise;
# FlashAttention 2 from the project's own prebuilt wheel, pinned by its
# checksum, because the package's attention window is applied only under
# it. Do not bump anything casually.
FROM nvidia/cuda:12.8.2-base-ubuntu24.04@sha256:b382332b575435b081b805b15b3aa1779a350a4e513f4d0449b4d7ad098e94ff

LABEL org.opencontainers.image.title="Gideon Transcribe recogniser"
LABEL org.opencontainers.image.description="Qwen3-ASR with its forced aligner, served to the WhisperX service on its private network."
LABEL org.opencontainers.image.source="https://github.com/TNMD-FDO/gideon-transcribe"
LABEL org.opencontainers.image.licenses="CC0-1.0"

# Ubuntu 24.04's Python 3.12 and the sound library soundfile reads WAVs
# with. As in the other images, the apt packages come from the distribution,
# fixed by the base digest.
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3 \
      python3-venv \
      libsndfile1 \
      ca-certificates \
 && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
RUN python3 -m venv "${VIRTUAL_ENV}"

# torch in a layer of its own (the release workflow's 10 GB layer limit),
# then the package and its pins.
COPY requirements-torch.txt /tmp/requirements-torch.txt
RUN pip install --no-cache-dir -r /tmp/requirements-torch.txt

# The package's own inference imports first (with the FlashAttention wheel,
# which needs PyPI for einops and so cannot sit in the torch step), under
# the constraints the first server build froze, so a rebuild resolves to the
# same tree; then the package alone (--no-deps): its dependency list carries
# the demo's gradio and flask and would widen the image for code nothing
# here calls.
COPY requirements.txt constraints.txt /tmp/
RUN pip install --no-cache-dir -c /tmp/constraints.txt -r /tmp/requirements.txt \
 && pip install --no-cache-dir --no-deps "qwen-asr==0.0.6"

# The models must import, not merely install, and FlashAttention must load
# against this torch: a wheel built for another torch fails here, at build,
# and not at the first recording. The weights are not in the image.
RUN python -c "import flash_attn; from qwen_asr import Qwen3ASRModel, Qwen3ForcedAligner"

# The container runs as the office's own account (Compose's `user:`), which
# has no entry in the image's passwd file; torch's compile machinery asks
# the account's name and its cache folder, so both are given here.
ENV HOME=/tmp MPLCONFIGDIR=/tmp/matplotlib \
    USER=recogniser LOGNAME=recogniser \
    TORCHINDUCTOR_CACHE_DIR=/tmp/torchinductor

# The same mounted model folder as the WhisperX service: the pull fetches the
# two models there by revision, and this container reads them offline.
ENV HF_HOME=/models/hf \
    TORCH_HOME=/models/torch \
    CUDA_CACHE_PATH=/models/cuda-cache \
    CUDA_CACHE_MAXSIZE=4294967296 \
    HF_HUB_OFFLINE=1 \
    TOKENIZERS_PARALLELISM=false \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY server.py /opt/recogniser/
WORKDIR /opt/recogniser
EXPOSE 8200
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8200", "--workers", "1"]
