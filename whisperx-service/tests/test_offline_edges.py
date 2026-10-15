"""The service's offline edges (service 0.5.0, the dependencies pass of
2026-10-14): no fetch at run time, the ASR models loaded by their pinned
folders, and the aligner's sentence-splitting table built into the image."""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import pytest
from service import pull
from service.model_process import Engine
from service.models_file import Model, Models
from service.runner import Runner

HERE = Path(__file__).resolve().parent.parent


def a_whisperx(monkeypatch, *, align_fails=False):
    """A stand-in whisperx module that records what the loaders were asked."""
    asked: dict[str, list] = {"load_model": [], "load_align_model": []}
    fake = types.ModuleType("whisperx")

    def load_model(source, **kwargs):
        asked["load_model"].append(source)
        return object()

    def load_align_model(language_code, device):
        asked["load_align_model"].append(language_code)
        if align_fails:
            raise OSError("not in the model folder")
        return object(), {"language": language_code}

    fake.load_model = load_model
    fake.load_align_model = load_align_model
    monkeypatch.setitem(sys.modules, "whisperx", fake)
    return asked


def test_the_pipeline_is_loaded_by_its_pinned_folder_when_there_is_one(monkeypatch):
    asked = a_whisperx(monkeypatch)
    engine = Engine(
        {
            "vad_onset": 0.5,
            "vad_offset": 0.3,
            "model_folders": {"large-v3": "/models/hf/hub/x/snapshots/edaa852"},
        }
    )
    engine.pipeline_for("large-v3")
    assert asked["load_model"] == ["/models/hf/hub/x/snapshots/edaa852"]
    # A model the pull has not fetched yet is still asked for by name.
    engine.pipeline_for("large-v3-turbo")
    assert asked["load_model"][-1] == "large-v3-turbo"


def test_the_aligner_never_lifts_the_offline_switch(monkeypatch):
    asked = a_whisperx(monkeypatch, align_fails=True)
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    seen: list[str | None] = []
    original = sys.modules["whisperx"].load_align_model

    def watching(language_code, device):
        seen.append(os.environ.get("HF_HUB_OFFLINE"))
        return original(language_code, device)

    sys.modules["whisperx"].load_align_model = watching
    engine = Engine({"vad_onset": 0.5, "vad_offset": 0.3})
    assert engine.aligner_for("pt") is None
    assert seen == ["1"]
    assert os.environ["HF_HUB_OFFLINE"] == "1"
    # Remembered: a language that could not be loaded is not asked for again.
    assert engine.aligner_for("pt") is None
    assert asked["load_align_model"] == ["pt"]


def test_the_model_process_source_has_no_offline_exception():
    source = (HERE / "service" / "model_process.py").read_text(encoding="utf-8")
    assert 'os.environ["HF_HUB_OFFLINE"] = "0"' not in source
    aligner = source.split("def aligner_for")[1].split("\n    def ")[0]
    assert "os.environ" not in aligner


def test_the_runner_hands_each_fetched_model_s_folder_to_the_process(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("HF_HOME", str(tmp_path))
    snapshot = (
        tmp_path
        / "hub"
        / "models--Systran--faster-whisper-large-v3"
        / "snapshots"
        / "edaa852"
    )
    snapshot.mkdir(parents=True)
    models = Models(
        [
            Model(
                "large-v3", "Systran/faster-whisper-large-v3", "edaa852", "MIT", True
            ),
            Model("large-v3-turbo", "mobiuslabsgmbh/x", "0a363e9", "MIT"),
        ],
        Model("diarization", "pyannote/x", "3533c8c", "CC-BY-4.0"),
    )
    runner = Runner.__new__(Runner)
    runner.models = models
    assert runner._model_folders() == {"large-v3": str(snapshot)}


def test_the_pull_warms_the_kernels_from_the_fetched_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_HOME", str(tmp_path))
    model = {"repository": "Systran/faster-whisper-large-v3", "revision": "edaa852"}
    assert pull._snapshot_folder(model) is None
    snapshot = (
        tmp_path
        / "hub"
        / "models--Systran--faster-whisper-large-v3"
        / "snapshots"
        / "edaa852"
    )
    snapshot.mkdir(parents=True)
    assert pull._snapshot_folder(model) == str(snapshot)
    assert pull._snapshot_folder({"repository": "x/y"}) is None


@pytest.mark.parametrize(
    "line",
    [
        "ENV NLTK_DATA=/opt/venv/nltk_data",
        "nltk.download('punkt_tab', download_dir='/opt/venv/nltk_data', quiet=True)",
        "load('tokenizers/punkt_tab/english.pickle')",
    ],
)
def test_the_image_carries_the_sentence_splitting_table(line):
    dockerfile = (HERE / "Dockerfile").read_text(encoding="utf-8")
    assert line in dockerfile


def test_the_documents_say_no_fetch_at_run_time():
    contract = (HERE.parent / "docs" / "whisperx-api.md").read_text(encoding="utf-8")
    assert "No exception since service 0.5.0" in contract
    assert "single fetch attempt" not in contract.split("## Amendments applied")[0]
    readme = (HERE / "README.md").read_text(encoding="utf-8")
    assert "makes no network call at all." in readme
    models_file = (HERE / "models.yaml").read_text(encoding="utf-8")
    assert "makes one\n# fetch attempt" not in models_file
