"""Fetch every model in models.yaml, check it against its pin, and report.

This is the command an admin runs once at install, again when a Release says
the models changed, and again after a restore. It is the only time the service
reaches the network on purpose: afterwards it runs offline, and a job can use
only what is in the model folder.

It needs two things together, and neither alone is enough: the HuggingFace
token, and the acceptance of the diarization model's licence by the account
that token belongs to.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

# The model folder is what this command fills, so the offline switch has to
# come off before huggingface_hub is imported anywhere.
os.environ["HF_HUB_OFFLINE"] = "0"

# What faster-whisper itself asks for from an ASR repository. Fetching the same
# list keeps the folder to what is used, and skips the duplicate weight formats
# some repositories carry.
ASR_FILES = [
    "config.json",
    "preprocessor_config.json",
    "model.bin",
    "tokenizer.json",
    "vocabulary.*",
]

MODELS_FILE = Path(__file__).resolve().parent.parent / "models.yaml"


def _say(message: str = "") -> None:
    print(message, flush=True)


def _read_token() -> str | None:
    path = os.environ.get("HF_TOKEN_FILE")
    if not path:
        return None
    try:
        token = Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return token or None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _revision_of(snapshot_path: str) -> str:
    """The commit a snapshot folder holds, which is the folder's own name."""
    return Path(snapshot_path).name


def _checkpoint_files() -> dict[Path, int]:
    """Every torch hub checkpoint now on disk, with its size."""
    home = os.environ.get("TORCH_HOME")
    if not home:
        return {}
    folder = Path(home) / "hub" / "checkpoints"
    if not folder.is_dir():
        return {}
    return {path: path.stat().st_size for path in sorted(folder.iterdir())}


def _pull_asr(models: dict[str, Any], token: str | None) -> list[str]:
    from huggingface_hub import snapshot_download

    problems: list[str] = []
    _say("The two models a job may name")
    for name, model in models.items():
        repository = model["repository"]
        pinned = model.get("revision")
        try:
            path = snapshot_download(
                repository,
                revision=pinned,
                allow_patterns=ASR_FILES,
                token=token,
            )
        except Exception as exc:  # noqa: BLE001 - the message is the report
            _say(f"  {name}: COULD NOT BE FETCHED")
            _say(f"    {exc}")
            problems.append(f"the model {name} could not be fetched from {repository}")
            continue

        got = _revision_of(path)
        if pinned and got != pinned:
            _say(f"  {name}: revision {got}, but models.yaml pins {pinned}")
            problems.append(f"the model {name} is not at the revision it is pinned to")
        elif pinned:
            _say(f"  {name}: at its pinned revision {got}")
        else:
            _say(f"  {name}: revision {got}  <- write this into models.yaml")
    return problems


def _pull_diarization(model: dict[str, Any], token: str | None) -> list[str]:
    from huggingface_hub import snapshot_download

    _say("The diarization model")
    repository = model["repository"]
    pinned = model.get("revision")

    if not token:
        _say("  no HuggingFace token was found, so the licence gate cannot open")
        return [
            "there is no HuggingFace token. The service reads it from the file "
            "named by HF_TOKEN_FILE, which the install writes"
        ]

    try:
        path = snapshot_download(repository, revision=pinned, token=token)
    except Exception as exc:  # noqa: BLE001 - the message is the report
        _say("  COULD NOT BE FETCHED")
        _say(f"    {exc}")
        return [
            "the diarization model could not be fetched. Either the token is "
            "wrong, or the account it belongs to has not accepted this model's "
            "conditions on its HuggingFace page. Both are needed"
        ]

    got = _revision_of(path)
    if pinned and got != pinned:
        _say(f"  revision {got}, but models.yaml pins {pinned}")
        return ["the diarization model is not at the revision it is pinned to"]
    _say(f"  at its pinned revision {got}")
    return []


def _pull_alignment(pins: dict[str, Any], languages: list[str]) -> list[str]:
    import whisperx

    problems: list[str] = []
    _say("The alignment models")
    for language in languages:
        before = _checkpoint_files()
        try:
            whisperx.load_align_model(language_code=language, device="cpu")
        except Exception as exc:  # noqa: BLE001 - the message is the report
            _say(f"  {language}: COULD NOT BE FETCHED")
            _say(f"    {exc}")
            problems.append(f"the alignment model for {language} could not be fetched")
            continue

        new = [path for path in _checkpoint_files() if path not in before]
        if not new:
            _say(f"  {language}: already in the model folder")
            continue

        pin = pins.get(language) or {}
        for path in new:
            digest = _sha256(path)
            expected = pin.get("sha256")
            if expected and digest != expected:
                _say(f"  {language}: {path.name} does not match its checksum")
                problems.append(
                    f"the alignment model for {language} does not match the "
                    "checksum in models.yaml"
                )
            elif expected:
                _say(f"  {language}: {path.name}, checksum matches")
            else:
                _say(f"  {language}: {path.name}")
                _say(f"    sha256 {digest}  <- write this into models.yaml")
    return problems


def _warm_the_kernel_cache(default_model: str) -> list[str]:
    """Load the default model once, so the driver's compiled kernels are kept.

    CTranslate2's wheels carry no code for this generation of card, so the
    driver compiles the kernels from PTX the first time a model loads. That
    pause belongs here, at install, and not in front of the first person who
    uploads a recording.
    """
    _say("Loading the default model once, to compile and keep the kernels")
    try:
        import torch
    except ImportError:
        return ["torch could not be imported"]

    if not torch.cuda.is_available():
        _say("  no card is visible, so this step is skipped")
        return []

    try:
        import whisperx

        model = whisperx.load_model(
            default_model,
            device="cuda",
            compute_type="float16",
        )
        del model
    except Exception as exc:  # noqa: BLE001 - the message is the report
        _say(f"  the model would not load: {exc}")
        return [f"the model {default_model} would not load on the card"]

    _say("  loaded and unloaded")
    return []


def pull() -> int:
    """Fetch and check every model. Returns 0 when everything is in place."""
    import yaml

    models = yaml.safe_load(MODELS_FILE.read_text(encoding="utf-8"))
    token = _read_token()
    languages = [
        code.strip()
        for code in os.environ.get("WHISPERX_ALIGN_LANGUAGES", "en,es").split(",")
        if code.strip()
    ]

    folder = os.environ.get("HF_HOME", "the model folder")
    _say(f"Fetching into {folder}")
    _say()

    problems = _pull_asr(models["asr"], token)
    _say()
    problems += _pull_diarization(models["diarization"], token)
    _say()
    problems += _pull_alignment(models.get("alignment") or {}, languages)
    _say()

    default_model = next(
        (name for name, model in models["asr"].items() if model.get("default")),
        "large-v3",
    )
    problems += _warm_the_kernel_cache(default_model)
    _say()

    if not problems:
        _say("Every model is in the model folder and matches its pin.")
        return 0

    _say("Problems found:")
    for problem in problems:
        _say(f"  - {problem}")
    return 1
