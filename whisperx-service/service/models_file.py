"""models.yaml: the allow-list, the pins, and what is in the model folder."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MODELS_FILE = Path(__file__).resolve().parent.parent / "models.yaml"


@dataclass(frozen=True)
class Model:
    name: str
    repository: str
    revision: str | None
    licence: str
    default: bool = False


class Models:
    """What may be asked for, and whether it is already on the server."""

    def __init__(self, models: list[Model], diarization: Model) -> None:
        self.models = models
        self.diarization = diarization

    @classmethod
    def load(cls, path: Path = MODELS_FILE) -> Models:
        import yaml

        raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
        models = [
            Model(
                name=name,
                repository=model["repository"],
                revision=model.get("revision"),
                licence=model.get("licence", ""),
                default=bool(model.get("default")),
            )
            for name, model in raw["asr"].items()
        ]
        diarization = Model(
            name="diarization",
            repository=raw["diarization"]["repository"],
            revision=raw["diarization"].get("revision"),
            licence=raw["diarization"].get("licence", ""),
        )
        return cls(models, diarization)

    @property
    def names(self) -> tuple[str, ...]:
        """The allow-list, with the default first."""
        ordered = sorted(self.models, key=lambda model: not model.default)
        return tuple(model.name for model in ordered)

    def named(self, name: str) -> Model | None:
        for model in self.models:
            if model.name == name:
                return model
        return None

    def snapshot(self, model: Model) -> Path | None:
        """Where the pinned revision of a model actually sits on disk.

        The hub can only resolve a model by name when it has a note of which
        commit a branch points at, and a download of one exact revision writes
        no such note. Handing the loader the folder itself keeps the service
        offline and makes the pin bind at run time as well as at pull time.
        """
        home = os.environ.get("HF_HOME")
        if not home or not model.revision:
            return None
        folder = (
            Path(home)
            / "hub"
            / ("models--" + model.repository.replace("/", "--"))
            / "snapshots"
            / model.revision
        )
        return folder if folder.is_dir() else None

    def is_cached(self, model: Model) -> bool:
        """Whether the model's files are in the model folder already.

        The hub keeps a folder per repository, named after it, so its presence
        with a snapshot inside is what "cached" means here.
        """
        home = os.environ.get("HF_HOME")
        if not home:
            return False
        folder = Path(home) / "hub" / ("models--" + model.repository.replace("/", "--"))
        snapshots = folder / "snapshots"
        return snapshots.is_dir() and any(snapshots.iterdir())
