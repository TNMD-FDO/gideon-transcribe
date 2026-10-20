"""The vocabulary prompt on the transcription options (v1.141.1): a
dataclass since faster-whisper 1.2, a NamedTuple before it; the self-test
proves the shape."""

import sys
import types
from collections import namedtuple
from dataclasses import dataclass

import pytest
from service import selftest
from service.model_process import with_prompt


@dataclass
class Options:
    beam_size: int = 5
    initial_prompt: str | None = None


Tuple = namedtuple("Tuple", ["beam_size", "initial_prompt"])


def test_the_prompt_is_set_on_either_shape():
    told = with_prompt(Options(), "Dana Reyes, Birch Road")
    assert told.initial_prompt == "Dana Reyes, Birch Road" and told.beam_size == 5
    before = Tuple(5, None)
    assert with_prompt(before, "x").initial_prompt == "x"
    assert before.initial_prompt is None
    with pytest.raises(TypeError):
        with_prompt(object(), "x")


def test_the_selftest_proves_the_shape(monkeypatch, capsys):
    module = types.ModuleType("faster_whisper.transcribe")
    module.TranscriptionOptions = Options
    package = types.ModuleType("faster_whisper")
    monkeypatch.setitem(sys.modules, "faster_whisper", package)
    monkeypatch.setitem(sys.modules, "faster_whisper.transcribe", module)
    assert selftest._options_take_a_prompt() == []
    assert "dataclass" in capsys.readouterr().out
    module.TranscriptionOptions = object
    (problem,) = selftest._options_take_a_prompt()
    assert "cannot set the vocabulary prompt" in problem
