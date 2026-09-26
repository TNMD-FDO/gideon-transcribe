"""v1.83.0: the pieces of an installation (ADR 0015).

The rules checked here: the Status page lists the six pieces from the same
facts the script reads; with the transcription piece absent an upload is
accepted rather than refused, no Job is made, the Recording reads "Waiting
for the card", the service's health row is "not installed" and not red; and
once the piece is there the sweep hands the waiting Recording over. A
process not given the profile list at all is read as having the piece, as
every install before this release did.
"""

from __future__ import annotations

import json

import pytest
from core import pieces, tasks, whisperx
from core.jobs import Job
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording
from django.urls import reverse

PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings, monkeypatch):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"
    # The upload page reads the disk; a scratch folder can read as low.
    from core import uploads

    monkeypatch.setattr(uploads, "free_disk_bytes", lambda: 10**13)


@pytest.fixture
def admin(db):
    who = User.objects.create_local_admin("it", PASSWORD)
    who.is_local = True
    who.admin_flag = True
    who.save()
    return who


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def test_a_process_not_given_the_list_has_the_piece(monkeypatch):
    monkeypatch.delenv("COMPOSE_PROFILES", raising=False)
    assert pieces.transcription_installed()
    monkeypatch.setenv("COMPOSE_PROFILES", "")
    assert not pieces.transcription_installed()
    monkeypatch.setenv("COMPOSE_PROFILES", "llm,transcription")
    assert pieces.transcription_installed()
    monkeypatch.setenv("COMPOSE_PROFILES", "llm, fast")
    assert not pieces.transcription_installed()
    assert pieces.profiles() == {"llm", "fast"}


def test_the_six_pieces_in_order():
    assert pieces.PIECES == (
        "transcription",
        "fast-lane",
        "engine",
        "directory",
        "mail",
        "backup",
    )
    assert pieces.command("engine") == "./transcribe add engine"


@pytest.mark.django_db
def test_the_status_page_lists_the_pieces(admin, client, monkeypatch):
    monkeypatch.setenv("COMPOSE_PROFILES", "")
    monkeypatch.setattr(whisperx, "is_alive", lambda lane="": False)
    signed_in(client, admin)
    told = client.get(reverse("panel-status-lines")).json()
    rows = told["pieces"]
    assert [one["name"] for one in rows] == list(pieces.PIECES)
    by_name = {one["name"]: one for one in rows}
    assert by_name["transcription"]["state"] == "not installed"
    assert by_name["transcription"]["command"] == "./transcribe add transcription"
    assert by_name["fast-lane"]["state"] == "not installed"
    assert by_name["engine"]["state"] == "off"
    assert by_name["directory"]["state"] == "off"
    assert by_name["mail"]["state"] == "off"
    assert by_name["backup"]["state"] == "off"
    # The service's own rows: not installed, never "unreachable".
    service = next(one for one in told["services"] if one["name"] == "whisperx")
    assert service["state"] == "not installed"
    assert told["service"] == {"up": False, "installed": False, "says": "not installed"}
    # With the piece, the same rows read as before.
    monkeypatch.setenv("COMPOSE_PROFILES", "transcription")
    told = client.get(reverse("panel-status-lines")).json()
    by_name = {one["name"]: one for one in told["pieces"]}
    assert by_name["transcription"]["state"] == "not answering"
    assert by_name["fast-lane"]["state"] == "off"
    service = next(one for one in told["services"] if one["name"] == "whisperx")
    assert service["state"] == "unreachable"
    monkeypatch.setattr(whisperx, "is_alive", lambda lane="": True)
    by_name = {
        one["name"]: one
        for one in client.get(reverse("panel-status-lines")).json()["pieces"]
    }
    assert by_name["transcription"]["state"] == "on"


@pytest.mark.django_db
def test_an_upload_waits_for_the_card(admin, client, monkeypatch):
    monkeypatch.setenv("COMPOSE_PROFILES", "")
    monkeypatch.setattr(whisperx, "is_alive", lambda lane="": False)
    signed_in(client, admin)
    # The upload page says the piece is not installed, in amber, and the form is there.
    page = client.get(reverse("upload")).content.decode()
    assert "not installed on this server yet" in page
    assert (
        "notice warn" in page and "Transcription is not available right now" not in page
    )
    start = client.get(reverse("home")).content.decode()
    assert "not installed on this server yet" in start
    # Submit is accepted, where the service being down would refuse it.
    answer = client.post(
        reverse("submit"),
        data=json.dumps({"files": [{"name": "call.m4a", "size": 10}]}),
        content_type="application/json",
    )
    assert answer.status_code == 200, answer.content
    recording = Recording.objects.get()
    # Prepared and Ready: no Job is made while the piece is absent.
    recording.media_state = MediaState.READY
    recording.save(update_fields=["media_state"])
    tasks.keep_the_queue_moving(0)
    assert not Job.objects.exists()
    rows = client.get(reverse("recordings")).content.decode()
    assert "Waiting for the card" in rows
    # The piece added: the sweep hands the Recording over.
    monkeypatch.setenv("COMPOSE_PROFILES", "transcription")
    handed = []
    monkeypatch.setattr(tasks.hand_over_job, "defer", lambda **f: handed.append(f))
    tasks.keep_the_queue_moving(0)
    assert Job.objects.filter(batch=recording.batch).count() == 1
    assert len(handed) == 1
    rows = client.get(reverse("recordings")).content.decode()
    assert "Waiting for the card" not in rows


@pytest.mark.django_db
def test_the_service_down_still_refuses_when_the_piece_is_installed(
    admin, client, monkeypatch
):
    monkeypatch.setenv("COMPOSE_PROFILES", "transcription")
    monkeypatch.setattr(whisperx, "is_alive", lambda lane="": False)
    signed_in(client, admin)
    answer = client.post(
        reverse("submit"),
        data=json.dumps({"files": [{"name": "call.m4a", "size": 10}]}),
        content_type="application/json",
    )
    assert answer.status_code == 503
    assert answer.json()["reason_class"] == "service_unreachable"
    assert not Batch.objects.exists()
    page = client.get(reverse("upload")).content.decode()
    assert "Transcription is not available right now" in page


def test_where_a_server_sits_on_the_ladder(monkeypatch):
    """v1.92.0: the card's memory, as the install recorded it, gives the
    words for the Installation page and the Pieces card, and the bar."""
    monkeypatch.delenv("CARD_MEMORY_GB", raising=False)
    assert pieces.card_memory_gb() is None
    none = pieces.fitment(None)
    assert none["words"].startswith("No card:") and "44 GB" in none["next"]
    assert none["segments"] == []
    small = pieces.fitment(12)
    assert "under the 16 GB" in small["words"] and small["batch"] == 0
    card = pieces.fitment(24)
    assert card["batch"] == 8 and "recordings up to about two hours" in card["words"]
    assert card["engine_room"] is False and card["fast_lane_room"] is False
    assert "the Local engine needs 44 GB in all" in card["next"]
    assert [one["name"] for one in card["segments"]] == ["Transcription", "Diarizer"]
    assert sum(one["gb"] for one in card["segments"]) == 24
    big = pieces.fitment(48)
    assert big["engine_room"] is True and big["fast_lane_room"] is False
    assert [one["name"] for one in big["segments"]] == [
        "Transcription",
        "Diarizer",
        "Local engine",
        "Room",
    ]
    assert (
        big["segments"][-1]["gb"] == 4
        and "the fast lane needs 8 GB more" in big["next"]
    )
    whole = pieces.fitment(96)
    assert [one["name"] for one in whole["segments"]][-2:] == ["Fast lane", "Room"]
    assert whole["next"].startswith("Nothing left to open")
    assert abs(sum(one["share"] for one in whole["segments"]) - 100) < 0.5
    # A narrow segment carries no label of its own (v1.92.1): the diarizer's
    # 4 GB of 96 is 4.2 percent; transcription's 20 GB is 20.8 and labelled.
    by_name = {one["name"]: one for one in whole["segments"]}
    assert by_name["Diarizer"]["narrow"] is True
    assert by_name["Fast lane"]["narrow"] is True
    assert by_name["Transcription"]["narrow"] is False
    # An engine on the LAN: no Local engine drawn, the assistant is on.
    lan = pieces.fitment(48, engine_on_lan=True)
    assert "engine on the LAN" in lan["words"] and lan["fast_lane_room"] is True
    monkeypatch.setenv("CARD_MEMORY_GB", "24")
    assert pieces.card_memory_gb() == 24
    monkeypatch.setenv("CARD_MEMORY_GB", "nonsense")
    assert pieces.card_memory_gb() is None


@pytest.mark.django_db
def test_the_installation_page_and_the_pieces_say_what_the_card_opens(
    admin, client, monkeypatch
):
    monkeypatch.setenv("COMPOSE_PROFILES", "transcription")
    monkeypatch.setenv("CARD_MEMORY_GB", "24")
    monkeypatch.setenv("LLM_NETWORK", "transcribe-llm")
    monkeypatch.setattr(whisperx, "is_alive", lambda lane="": True)
    signed_in(client, admin)
    page = client.get(reverse("panel-installation")).content.decode()
    assert "What the card opens" in page and "24 GB" in page
    assert "fit-seg fit-t" in page and "fit-seg fit-d" in page
    # On a 24 GB card every segment is wide enough for its label (v1.92.1).
    assert "fit-narrow" not in page
    assert "the Local engine needs 44 GB in all" in page
    by_name = {
        one["name"]: one
        for one in client.get(reverse("panel-status-lines")).json()["pieces"]
    }
    assert "it needs 8 GB more on the card" in by_name["fast-lane"]["says"]
    assert "the Local engine needs a card of 44 GB" in by_name["engine"]["says"]
    monkeypatch.setenv("CARD_MEMORY_GB", "96")
    by_name = {
        one["name"]: one
        for one in client.get(reverse("panel-status-lines")).json()["pieces"]
    }
    assert "the card has room for it" in by_name["fast-lane"]["says"]
    assert "the card has room for the Local engine" in by_name["engine"]["says"]
    # On a 96 GB card the diarizer's segment is too narrow for a label.
    page = client.get(reverse("panel-installation")).content.decode()
    assert "fit-seg fit-d fit-narrow" in page and "fit-seg fit-t fit-narrow" not in page
    monkeypatch.delenv("CARD_MEMORY_GB")
    page = client.get(reverse("panel-installation")).content.decode()
    assert "no card recorded" in page and "No card:" in page
