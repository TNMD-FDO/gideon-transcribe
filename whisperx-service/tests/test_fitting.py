"""The words fitted over the whole file (service 0.7.0): the request field,
its two refusals, what the model process hands the fitter, and the
settings the result reports."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from service import fitting
from service.api import create_app
from service.audio import Audio
from service.tokens import Consumer, format_line
from tests.test_api import (  # noqa: F401 - the fixtures ride along
    APP_TOKEN,
    CachedModels,
    Model,
    Tokens,
    headers,
    runner,
    settings,
    store,
    submit,
)

HERE = Path(__file__).resolve().parents[1]


def test_one_segment_over_the_whole_file():
    segments = [
        {"start": 0.0, "end": 3.1, "text": " Is it cold down there? "},
        {"start": 3.1, "end": 7.0, "text": ""},
        {"start": 7.2, "end": 9.9, "text": "Hey man."},
    ]
    assert fitting.one_segment_over(segments, 11.5) == [
        {"start": 0.0, "end": 11.5, "text": "Is it cold down there? Hey man."}
    ]
    assert fitting.one_segment_over([], 11.5) == []
    assert fitting.one_segment_over([{"text": "  "}], 4.0) == []


def a_client(settings, store, runner, seconds):  # noqa: F811
    settings.tokens_file.write_text(format_line(Consumer("transcribe", APP_TOKEN)))
    models = CachedModels(
        [Model("large-v3", "Systran/x", "edaa852", "MIT", True)],
        Model("diarization", "pyannote/x", "3533c8c", "CC"),
    )
    app = create_app(
        settings,
        store,
        Tokens(settings.tokens_file),
        models,
        runner,
        probe_audio=lambda path: Audio(seconds, 16000, 1),
    )
    return TestClient(app)


def test_accepted_on_a_short_file_and_kept(settings, store, runner):  # noqa: F811
    client = a_client(settings, store, runner, 11.5)
    answer = submit(client, fit_words_over_whole=True)
    assert answer.status_code == 202, answer.text
    job_id = answer.json()["id"]
    kept = client.get(f"/v1/jobs/{job_id}", headers=headers()).json()
    assert kept["state"] == "queued"
    # The stored request carries the field, so the model process reads it.
    stored = json.loads(json.dumps(store.job(job_id).request))
    assert stored["fit_words_over_whole"] is True
    # Left out, it is false.
    other = submit(client, client_reference="plain").json()["id"]
    assert store.job(other).request["fit_words_over_whole"] is False


def test_refused_long_or_with_diarize(settings, store, runner):  # noqa: F811
    client = a_client(settings, store, runner, 600.0)
    answer = submit(client, fit_words_over_whole=True)
    assert answer.status_code == 400
    assert "short file" in answer.json()["error"]
    assert list(settings.audio_dir.iterdir()) == []
    short = a_client(settings, store, runner, 20.0)
    answer = submit(short, task="diarize", fit_words_over_whole=True)
    assert answer.status_code == 400
    assert "no words to fit" in answer.json()["error"]
    # Not a boolean: refused like any other field.
    answer = submit(short, fit_words_over_whole="yes")
    assert answer.status_code == 400


def test_the_model_process_fits_over_the_whole_file_when_asked():
    source = (HERE / "service" / "model_process.py").read_text(encoding="utf-8")
    align = source.split('stage("aligning")')[1].split('timings["align"]')[0]
    assert 'request.get("fit_words_over_whole")' in align
    assert "fitting.one_segment_over(segments, duration)" in align
    assert "whisperx.align(\n                segments," in align
    assert '"fit_words_over_whole": bool(request.get("fit_words_over_whole"))' in source
