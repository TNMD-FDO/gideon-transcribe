"""The API: who may call, what is refused, and what a Consumer reads back.

Nothing here needs a GPU or ffmpeg. The engine sits behind a stub runner and
the file probe is passed in, so these run on any machine.
"""

import json

import pytest
from fastapi.testclient import TestClient
from service.api import create_app
from service.audio import Audio
from service.auth import Tokens
from service.models_file import Model, Models
from service.settings import Settings
from service.store import Store
from service.tokens import Consumer, format_line

APP_TOKEN = "a" * 64
ADMIN_TOKEN = "b" * 64
OTHER_TOKEN = "c" * 64


class StubRunner:
    """A model process that is always up and never actually runs anything."""

    def __init__(self):
        self.cancelled = []
        self.is_alive = True

    def alive(self):
        return self.is_alive

    def loaded_model(self):
        return {"model": "large-v3", "revision": "edaa852"}

    def gpu(self):
        return {
            "uuid": "GPU-0000",
            "name": "a card",
            "vram_used_gb": 4.2,
            "vram_free_gb": 90.0,
        }

    def cancel(self, job_id):
        self.cancelled.append(job_id)


class CachedModels(Models):
    """Every model is in the model folder, because the pull already ran."""

    def is_cached(self, model):
        return True


@pytest.fixture
def settings(tmp_path):
    return Settings(
        state_dir=tmp_path / "state",
        tokens_file=tmp_path / "tokens",
        max_upload_bytes=1024 * 1024,
        max_audio_seconds=8 * 3600,
        timeout_base_minutes=30,
        timeout_per_audio_hour_minutes=60,
        result_hours=24,
        job_history_days=30,
        batch_size=16,
        vad_onset=0.5,
        vad_offset=0.363,
        align_languages=("en", "es"),
        log_level="info",
    )


@pytest.fixture
def store(settings):
    store = Store(settings)
    yield store
    store.close()


@pytest.fixture
def runner():
    return StubRunner()


@pytest.fixture
def client(settings, store, runner):
    settings.tokens_file.write_text(
        "\n".join(
            [
                format_line(Consumer("transcribe", APP_TOKEN)),
                format_line(Consumer("it", ADMIN_TOKEN, admin=True)),
                format_line(Consumer("another-app", OTHER_TOKEN)),
            ]
        )
    )
    models = CachedModels(
        [
            Model(
                "large-v3", "Systran/faster-whisper-large-v3", "edaa852", "MIT", True
            ),
            Model("large-v3-turbo", "mobiuslabsgmbh/x", "0a363e9", "MIT"),
        ],
        Model(
            "diarization", "pyannote/speaker-diarization-community-1", "3533c8c", "CC"
        ),
    )
    app = create_app(
        settings,
        store,
        Tokens(settings.tokens_file),
        models,
        runner,
        probe_audio=lambda path: Audio(600.0, 16000, 1),
    )
    return TestClient(app)


def submit(client, token=APP_TOKEN, audio=b"RIFFfake", **request):
    return client.post(
        "/v1/jobs",
        headers={"Authorization": f"Bearer {token}"},
        files={"audio": ("side.wav", audio, "audio/wav")},
        data={"request": json.dumps(request)},
    )


def headers(token=APP_TOKEN):
    return {"Authorization": f"Bearer {token}"}


# Liveness and tokens ---------------------------------------------------------


def test_healthz_needs_no_token(client):
    answer = client.get("/healthz")
    assert answer.status_code == 200
    assert answer.text == "ok"


def test_healthz_says_so_when_the_model_process_is_down(client, runner):
    runner.is_alive = False
    assert client.get("/healthz").status_code == 503


def test_everything_else_needs_a_token(client):
    assert client.get("/v1/jobs").status_code == 401
    assert client.get("/v1/status").status_code == 401
    assert submit(client, token="not-a-token").status_code == 401


# Submitting ------------------------------------------------------------------


def test_a_submission_is_accepted_and_placed_in_the_line(client):
    answer = submit(client)
    assert answer.status_code == 202
    body = answer.json()
    assert body["position"] == 0
    assert body["audio_minutes_ahead"] == 0
    assert body["id"]


def test_the_second_submission_is_behind_the_first(client):
    submit(client)
    body = submit(client).json()
    assert body["position"] == 1
    assert body["audio_minutes_ahead"] == 10.0


def test_a_higher_priority_goes_ahead_and_the_line_counts_it_so(client):
    first = submit(client).json()
    second = submit(client).json()
    urgent = submit(client, priority=100).json()
    # The urgent one is behind nothing; the earlier two are now behind it.
    assert urgent["position"] == 0 and urgent["audio_minutes_ahead"] == 0
    told = client.get(f"/v1/jobs/{first['id']}", headers=headers()).json()
    assert told["position"] == 1 and told["audio_minutes_ahead"] == 10.0
    told = client.get(f"/v1/jobs/{second['id']}", headers=headers()).json()
    assert told["position"] == 2
    # Out of range, or not a whole number, is refused.
    assert submit(client, priority=101).status_code == 400
    assert submit(client, priority="high").status_code == 400
    assert submit(client, priority=True).status_code == 400


def test_the_same_reference_returns_the_job_already_in_the_line(client):
    first = submit(client, client_reference="run-1").json()
    again = submit(client, client_reference="run-1")
    assert again.status_code == 200
    assert again.json()["id"] == first["id"]


def test_an_unknown_field_is_refused(client):
    answer = submit(client, speed="fast")
    assert answer.status_code == 400
    assert "unknown field" in answer.json()["error"]


def test_a_model_outside_the_allow_list_is_refused(client):
    answer = submit(client, model="distil-large-v3")
    assert answer.status_code == 400


def test_a_speaker_hint_without_diarize_is_refused(client):
    answer = submit(client, speakers={"exactly": 2})
    assert answer.status_code == 400
    assert "without diarize" in answer.json()["error"]


def test_a_hint_whose_least_is_above_its_most_is_refused(client):
    answer = submit(client, diarize=True, speakers={"between": [4, 2]})
    assert answer.status_code == 400


def test_a_hint_is_accepted_with_diarize(client):
    assert submit(client, diarize=True, speakers={"between": [2, 4]}).status_code == 202


def test_too_much_vocabulary_is_refused(client):
    answer = submit(client, vocabulary=[f"term{n}" for n in range(201)])
    assert answer.status_code == 400


def test_too_long_a_context_line_is_refused(client):
    answer = submit(client, context="x" * 501)
    assert answer.status_code == 400


def test_a_language_whisper_does_not_know_is_refused(client):
    answer = submit(client, language="ku")
    assert answer.status_code == 400
    assert "not a language" in answer.json()["error"]


def test_a_body_over_the_size_limit_is_refused(client, settings):
    answer = submit(client, audio=b"x" * (settings.max_upload_bytes + 1))
    assert answer.status_code == 413
    assert answer.json()["reason_class"] == "too_large"


def test_audio_longer_than_the_limit_is_refused(settings, store, runner):
    models = CachedModels(
        [Model("large-v3", "Systran/faster-whisper-large-v3", "edaa852", "MIT", True)],
        Model("diarization", "pyannote/x", "3533c8c", "CC"),
    )
    settings.tokens_file.write_text(format_line(Consumer("transcribe", APP_TOKEN)))
    app = create_app(
        settings,
        store,
        Tokens(settings.tokens_file),
        models,
        runner,
        probe_audio=lambda path: Audio(9 * 3600.0, 16000, 1),
    )
    answer = submit(TestClient(app))
    assert answer.status_code == 400
    assert answer.json()["reason_class"] == "too_long"


def test_a_refused_submission_leaves_no_audio_behind(client, settings):
    submit(client, context="x" * 501)
    assert list(settings.audio_dir.iterdir()) == []


# Polling, fetching, deleting -------------------------------------------------


def test_a_consumer_polls_its_own_job(client):
    job_id = submit(client).json()["id"]
    body = client.get(f"/v1/jobs/{job_id}", headers=headers()).json()
    assert body["state"] == "queued"
    assert body["consumer"] == "transcribe"
    assert body["attempt"] == 1


def test_another_consumer_is_told_the_job_does_not_exist(client):
    job_id = submit(client).json()["id"]
    answer = client.get(f"/v1/jobs/{job_id}", headers=headers(OTHER_TOKEN))
    assert answer.status_code == 404


def test_an_admin_token_may_read_any_job(client):
    job_id = submit(client).json()["id"]
    answer = client.get(f"/v1/jobs/{job_id}", headers=headers(ADMIN_TOKEN))
    assert answer.status_code == 200


def test_a_result_that_is_not_ready_answers_with_the_status(client):
    job_id = submit(client).json()["id"]
    answer = client.get(f"/v1/jobs/{job_id}/result", headers=headers())
    assert answer.status_code == 409
    assert answer.json()["state"] == "queued"


def test_a_finished_job_hands_over_its_result(client, store, settings):
    job_id = submit(client).json()["id"]
    store.take_next()
    result = settings.results_dir / f"{job_id}.json"
    result.write_text(json.dumps({"segments": [{"text": "hello"}]}))
    store.finish(job_id, result, 30.0)

    answer = client.get(f"/v1/jobs/{job_id}/result", headers=headers())
    assert answer.status_code == 200
    assert answer.json()["segments"][0]["text"] == "hello"


def test_a_result_that_was_swept_is_gone(client, store, settings):
    job_id = submit(client).json()["id"]
    store.take_next()
    result = settings.results_dir / f"{job_id}.json"
    result.write_text("{}")
    store.finish(job_id, result, 30.0)
    result.unlink()

    answer = client.get(f"/v1/jobs/{job_id}/result", headers=headers())
    assert answer.status_code == 410


def test_deleting_a_running_job_kills_the_model_process(client, store, runner):
    job_id = submit(client).json()["id"]
    store.take_next()

    assert client.delete(f"/v1/jobs/{job_id}", headers=headers()).status_code == 204
    assert runner.cancelled == [job_id]
    assert store.job(job_id).state == "cancelled"


def test_deleting_a_queued_job_takes_it_out_of_the_line(client, store, runner):
    job_id = submit(client).json()["id"]
    client.delete(f"/v1/jobs/{job_id}", headers=headers())
    assert store.job(job_id).state == "cancelled"


def test_deleting_a_finished_job_removes_it(client, store, settings):
    job_id = submit(client).json()["id"]
    store.take_next()
    result = settings.results_dir / f"{job_id}.json"
    result.write_text("{}")
    store.finish(job_id, result, 30.0)

    client.delete(f"/v1/jobs/{job_id}", headers=headers())
    assert store.job(job_id) is None
    assert not result.exists()


def test_a_consumer_lists_only_its_own_jobs(client):
    submit(client)
    submit(client, token=OTHER_TOKEN)
    mine = client.get("/v1/jobs", headers=headers()).json()["jobs"]
    every = client.get("/v1/jobs", headers=headers(ADMIN_TOKEN)).json()["jobs"]
    assert len(mine) == 1
    assert len(every) == 2


# What the service says about itself ------------------------------------------


def test_the_model_list_says_what_is_cached_and_loaded(client):
    body = client.get("/v1/models", headers=headers()).json()
    names = {model["name"]: model for model in body["models"]}
    assert names["large-v3"]["cached"] is True
    assert names["large-v3"]["loaded"] is True
    assert names["large-v3-turbo"]["loaded"] is False


def test_the_status_page_counts_the_whole_line(client):
    submit(client)
    submit(client, token=OTHER_TOKEN)
    body = client.get("/v1/status", headers=headers()).json()
    assert body["queue"] == {"length": 2, "audio_minutes": 20.0}
    assert body["versions"]["api"] == "v1"
    assert body["tokens"] == ["transcribe", "it", "another-app"]


def test_speed_is_silent_until_enough_jobs_have_run(client):
    body = client.get("/v1/status", headers=headers()).json()
    assert body["speed"]["large-v3"]["with_diarization"] is None


def test_a_consumer_sees_the_stage_of_another_consumers_running_job(client, store):
    submit(client, token=OTHER_TOKEN)
    store.take_next()
    body = client.get("/v1/status", headers=headers()).json()
    assert body["current_job"] == {
        "id": None,
        "consumer": None,
        "stage": "loading model",
    }


def test_an_admin_token_sees_whose_job_is_running(client, store):
    submit(client, token=OTHER_TOKEN)
    store.take_next()
    body = client.get("/v1/status", headers=headers(ADMIN_TOKEN)).json()
    assert body["current_job"]["consumer"] == "another-app"


def test_a_consumer_sees_its_own_running_job_in_full(client, store):
    job_id = submit(client).json()["id"]
    store.take_next()
    body = client.get("/v1/status", headers=headers()).json()
    assert body["current_job"]["id"] == job_id
