"""What this container can see: the GPU, the pinned versions, ffmpeg, folders.

This is the first check after the image is built on a server, before any model
has been pulled. It answers the question a person actually has at that moment,
which is whether the card, the driver, the pinned stack, and the mounted
folders line up, and it says plainly which line is the problem when one does
not.
"""

from __future__ import annotations

import os
import subprocess
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version

# The folders the image expects, and what each one holds.
FOLDERS = {
    "HF_HOME": "the ASR, diarization, and alignment models",
    "TORCH_HOME": "the torchaudio alignment bundles",
    "CUDA_CACHE_PATH": "the driver's compiled kernels",
}

# The packages whose versions decide whether this is the stack that was pinned.
PINNED = [
    "whisperx",
    "faster-whisper",
    "ctranslate2",
    "torch",
    "torchaudio",
    "torchcodec",
    "pyannote.audio",
    "transformers",
    "huggingface-hub",
]

STATE_DIR = "/srv/state"


def _line(label: str, value: str) -> None:
    print(f"  {label:<22} {value}")


def _package_versions() -> list[str]:
    problems: list[str] = []
    print("Pinned stack")
    for name in PINNED:
        try:
            _line(name, package_version(name))
        except PackageNotFoundError:
            _line(name, "MISSING")
            problems.append(f"the package {name} is not installed")
    return problems


def _gpu() -> list[str]:
    problems: list[str] = []
    print("GPU")
    try:
        import torch
    except ImportError as exc:  # pragma: no cover - the image always has torch
        _line("torch", f"cannot be imported: {exc}")
        return ["torch cannot be imported, so the image is not built right"]

    _line("CUDA build", torch.version.cuda or "none")
    if not torch.cuda.is_available():
        _line("card", "NOT VISIBLE")
        return [
            "no GPU is visible. Check that the compose file reserves the card "
            "by UUID through CDI and that WHISPERX_GPU_UUID names a card that "
            "nvidia-smi -L lists"
        ]

    for index in range(torch.cuda.device_count()):
        properties = torch.cuda.get_device_properties(index)
        capability = f"{properties.major}.{properties.minor}"
        memory_gb = properties.total_memory / (1024**3)
        _line("card", f"{properties.name} ({memory_gb:.0f} GB)")
        _line("compute capability", capability)
        uuid = getattr(properties, "uuid", None)
        if uuid is not None:
            _line("uuid", f"GPU-{uuid}")
        if capability != "12.0":
            problems.append(
                f"the card reports compute capability {capability}, but the "
                "stack was pinned for 12.0 (Blackwell)"
            )

    if torch.cuda.device_count() != 1:
        problems.append(
            f"{torch.cuda.device_count()} cards are visible. The service is "
            "meant to see exactly the one card it was given by UUID"
        )

    try:
        import ctranslate2

        _line("ctranslate2 sees", f"{ctranslate2.get_cuda_device_count()} card(s)")
    except ImportError:
        problems.append("ctranslate2 cannot be imported")

    return problems


def _ffmpeg() -> list[str]:
    problems: list[str] = []
    print("ffmpeg")
    try:
        version = subprocess.run(
            ["ffmpeg", "-hide_banner", "-version"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()[0]
        _line("version", version)
        decoders = subprocess.run(
            ["ffmpeg", "-hide_banner", "-decoders"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        _line("version", f"cannot be run: {exc}")
        return ["ffmpeg cannot be run, so no audio could be read"]

    has_g729 = any(line.split()[1:2] == ["g729"] for line in decoders.splitlines())
    _line("g729 decoder", "yes" if has_g729 else "NO")
    if not has_g729:
        problems.append("this ffmpeg cannot decode G.729, which phone exports use")
    return problems


def _folders() -> list[str]:
    problems: list[str] = []
    print("Folders")
    for key, holds in FOLDERS.items():
        path = os.environ.get(key)
        if not path:
            _line(key, "NOT SET")
            problems.append(f"{key} is not set, so {holds} would have no home")
            continue
        state = "writable" if _writable(path) else "NOT WRITABLE"
        _line(key, f"{path} ({state})")
        if state != "writable":
            problems.append(
                f"{path} is not writable by this container's user, so {holds} "
                "cannot be stored. Check the owner of the models folder on the "
                "server and the user: line in the compose file"
            )

    state = "writable" if _writable(STATE_DIR) else "NOT WRITABLE"
    _line("state folder", f"{STATE_DIR} ({state})")
    if state != "writable":
        problems.append(
            f"{STATE_DIR} is not writable by this container's user, so the job "
            "database could not be kept"
        )
    return problems


def _writable(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        return False
    return os.access(path, os.W_OK)


def selftest() -> int:
    """Print what the container sees and return 0 when nothing is wrong."""
    print(f"Python {sys.version.split()[0]}\n")

    problems: list[str] = []
    problems += _package_versions()
    print()
    problems += _gpu()
    print()
    problems += _ffmpeg()
    print()
    problems += _folders()
    print()

    if not problems:
        print("Everything this container needs is in place.")
        return 0

    print("Problems found:")
    for problem in problems:
        print(f"  - {problem}")
    return 1
