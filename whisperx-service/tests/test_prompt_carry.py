"""A job's vocabulary prompt is its own: the pipeline is held across jobs,
so a job with no vocabulary must not be read with the last job's names."""

import sys
import types
from dataclasses import dataclass

import pytest
from service import model_process


@dataclass
class Options:
    beam_size: int = 5
    initial_prompt: str | None = None


class Stop(Exception):
    pass


class Pipeline:
    def __init__(self):
        self.options = Options()
        self.heard: list[str | None] = []

    def transcribe(self, audio, **kwargs):
        self.heard.append(self.options.initial_prompt)
        raise Stop


class Engine:
    def __init__(self):
        self.settings = {"model_revisions": {}, "batch_size": 16}
        self.pipeline = Pipeline()

    def pipeline_for(self, model_name):
        return self.pipeline


class Outbox:
    def put(self, message):
        pass


@pytest.fixture
def engine(monkeypatch):
    fake = types.ModuleType("whisperx")
    fake.load_audio = lambda path: [0.0] * model_process.SAMPLE_RATE
    monkeypatch.setitem(sys.modules, "whisperx", fake)
    monkeypatch.setattr(model_process, "_vram", lambda: (0.0, 0.0))
    return Engine()


def _job(job_id, vocabulary):
    request = {
        "task": "transcribe",
        "language": "en",
        "model": "large-v3-turbo",
        "vocabulary": vocabulary,
    }
    return {"job_id": job_id, "request": request, "audio_path": "unused"}


def test_a_job_with_no_vocabulary_is_not_read_with_the_last_jobs_names(engine):
    for job in (_job("first", ["Dana Reyes", "Birch Road"]), _job("second", [])):
        with pytest.raises(Stop):
            model_process._run_one(engine, job, Outbox())
    first, second = engine.pipeline.heard
    assert "Dana Reyes" in first
    assert not second
