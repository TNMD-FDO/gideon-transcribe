"""The web tier's size and a page's question to the service (v1.181.0, from
the load test of 2026-10-30).

The Compose file passes the worker and thread settings the start script
reads, and the example environment names them; Home and the Upload page ask
the service at most once every thirty seconds and never wait five, while a
Batch is still gated by the direct check.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from core import whisperx
from core.models import User
from tests.helpers import signed_in

ROOT = Path(__file__).resolve().parent.parent.parent
PASSWORD = "a-long-enough-password"


def test_the_compose_file_passes_the_web_tiers_size_to_the_app():
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    entrypoint = (ROOT / "app" / "entrypoint.sh").read_text(encoding="utf-8")
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    for name in ("GUNICORN_WORKERS", "GUNICORN_THREADS"):
        assert f'{name}: "${{{name}:-4}}"' in compose, name
        assert f"${{{name}:-4}}" in entrypoint, name
        assert re.search(rf"^{name}=4$", example, re.M), name


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("web-tier", PASSWORD)


def test_home_asks_the_service_once_in_thirty_seconds(person, client, monkeypatch):
    asked = []
    monkeypatch.setattr(whisperx, "is_alive", lambda: asked.append("asked") or False)
    whisperx.forget_alive()
    signed_in(client, person)
    page = client.get("/").content.decode()
    assert "Transcription is not available right now" in page
    client.get("/")
    client.get("/upload")
    # Three pages, one question.
    assert asked == ["asked"]
    # Forgetting asks again, and a fresh stand-in is asked afresh.
    whisperx.forget_alive()
    assert whisperx.alive_lately() is False
    monkeypatch.setattr(whisperx, "is_alive", lambda: asked.append("again") or True)
    assert whisperx.alive_lately() is True
    assert asked == ["asked", "asked", "again"]


def test_a_page_waits_two_seconds_and_a_batch_five(monkeypatch):
    waits = []

    class Stalled:
        def __init__(self, request, timeout):
            waits.append(timeout)
            raise OSError("no answer")

    monkeypatch.setattr(whisperx.urllib.request, "urlopen", Stalled)
    whisperx.forget_alive()
    assert whisperx.alive_lately() is False
    assert whisperx.is_alive() is False
    assert waits == [whisperx.PAGE_TIMEOUT, 5]
