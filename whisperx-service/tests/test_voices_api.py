"""The voices request on the WhisperX service (ADR 0021, service 0.6.0): what
is refused, what reaches the diarizer container, and what comes back. The
container is a fake; nothing here needs a GPU.
"""

import json
import struct
import urllib.error

import pytest
from fastapi.testclient import TestClient
from service import diarizer_client
from service.api import create_app
from service.audio import Audio
from service.auth import Tokens
from service.models_file import Model, Models
from service.settings import Settings
from service.store import Store
from service.tokens import Consumer, format_line

TOKEN = "a" * 64


class Runner:
    is_alive = True

    def alive(self):
        return True

    def loaded_model(self):
        return {"model": "large-v3", "revision": "edaa852"}

    def gpu(self):
        return {
            "uuid": "GPU-0000",
            "name": "a card",
            "vram_used_gb": 1.0,
            "vram_free_gb": 90.0,
        }

    def cancel(self, job_id):
        pass


class Cached(Models):
    def is_cached(self, model):
        return True


@pytest.fixture
def made(tmp_path):
    settings = Settings(
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
        align_languages=("en",),
        log_level="info",
    )
    settings.tokens_file.write_text(format_line(Consumer("transcribe", TOKEN)))
    store = Store(settings)
    calls = []
    state = {"up": True, "voices": True, "error": None}

    def fake_voices(path, asked, timeout):
        calls.append({"bytes": path.stat().st_size, "asked": asked, "timeout": timeout})
        if state["error"]:
            raise state["error"]
        return {
            "stretches": [
                {
                    "id": s.get("id", str(i)),
                    "label": s["label"],
                    "net_seconds": 2.5,
                    "rms_dbfs": -20.0,
                    "vector": [1.0] + [0.0] * 191,
                }
                for i, s in enumerate(asked["stretches"])
            ],
            "labels": [
                {
                    "label": "A",
                    "vector": [1.0] + [0.0] * 191,
                    "members": 3,
                    "dropped": 0,
                    "sure_stretches": 3,
                }
            ],
            "sure_seconds": asked["sure_seconds"],
            "model": {
                "name": "nvidia/speakerverification_en_titanet_large",
                "revision": "0dc382f4",
                "nemo": "3.1.0",
            },
            "seconds": 0.4,
            "card_peak_gb": 0.3,
        }

    app = create_app(
        settings,
        store,
        Tokens(settings.tokens_file),
        Cached(
            [
                Model(
                    "large-v3",
                    "Systran/faster-whisper-large-v3",
                    "edaa852",
                    "MIT",
                    True,
                )
            ],
            Model(
                "diarization",
                "pyannote/speaker-diarization-community-1",
                "3533c8c",
                "CC-BY-4.0",
            ),
        ),
        Runner(),
        probe_audio=lambda path: Audio(
            duration_seconds=60.0, sample_rate=16000, channels=1
        ),
        diarizer_up=lambda: state["up"],
        voices_up=lambda: state["voices"],
        voices_call=fake_voices,
    )
    client = TestClient(app)
    yield client, calls, state
    store.close()


def ask(client, stretches=None, sure=2.0, token=TOKEN, audio=b"RIFF" + b"\0" * 400):
    asked = {
        "stretches": stretches
        if stretches is not None
        else [{"id": "7-0", "label": "A", "spans": [[1.0, 2.5]]}],
        "sure_seconds": sure,
    }
    return client.post(
        "/v1/voices",
        headers={"Authorization": f"Bearer {token}"},
        files={"audio": ("asr.wav", audio, "audio/wav")},
        data={"request": json.dumps(asked)},
    )


def test_the_voices_come_back_in_the_request(made):
    client, calls, _ = made
    answer = ask(client)
    assert answer.status_code == 200, answer.text
    body = answer.json()
    assert body["stretches"][0]["id"] == "7-0"
    assert len(body["stretches"][0]["vector"]) == 192
    assert body["labels"][0]["members"] == 3
    assert body["service"]["version"].startswith("0.")
    assert calls[0]["asked"]["sure_seconds"] == 2.0 and calls[0]["bytes"] == 404
    assert calls[0]["timeout"] >= 60


def test_it_needs_a_token_and_a_sound_request(made):
    client, calls, _ = made
    assert ask(client, token="b" * 64).status_code == 401
    assert ask(client, stretches=[]).status_code == 400
    assert ask(client, stretches=[{"spans": [[0, 1]]}]).status_code == 400
    assert ask(client, stretches=[{"label": "A"}]).status_code == 400
    assert ask(client, sure=30).status_code == 400
    assert calls == []


def test_the_containers_state_is_said_before_the_upload(made):
    client, calls, state = made
    state["up"] = False
    answer = ask(client)
    assert (
        answer.status_code == 503
        and answer.json()["reason_class"] == "diarizer_unavailable"
    )
    state["up"], state["voices"] = True, False
    answer = ask(client)
    assert answer.json()["reason_class"] == "model_unavailable"
    assert calls == []


def test_the_containers_refusals_are_translated(made):
    client, calls, state = made
    state["error"] = urllib.error.HTTPError("u", 503, "voices not loaded", {}, None)
    assert ask(client).json()["reason_class"] == "model_unavailable"
    state["error"] = urllib.error.HTTPError("u", 400, "bad audio", {}, None)
    assert ask(client).json()["reason_class"] == "bad_input"
    state["error"] = urllib.error.URLError("down")
    assert ask(client).json()["reason_class"] == "diarizer_unavailable"


def test_the_upload_is_removed_after_the_answer(made, tmp_path):
    client, calls, state = made
    ask(client)
    state["error"] = urllib.error.URLError("down")
    ask(client)
    left = [p for p in (tmp_path / "state").rglob("voices-*")]
    assert left == []


def test_the_frame_the_container_reads():
    body = diarizer_client.frame({"stretches": [], "sure_seconds": 2.0}, b"RIFFwav")
    (length,) = struct.unpack(">I", body[:4])
    assert json.loads(body[4 : 4 + length]) == {"stretches": [], "sure_seconds": 2.0}
    assert body[4 + length :] == b"RIFFwav"


def test_the_status_says_whether_the_voices_answer(made):
    client, _, state = made
    body = client.get("/v1/status", headers={"Authorization": f"Bearer {TOKEN}"}).json()
    assert body["diarizers"]["voices"] is True
    state["voices"] = False
    body = client.get("/v1/status", headers={"Authorization": f"Bearer {TOKEN}"}).json()
    assert body["diarizers"]["voices"] is False
