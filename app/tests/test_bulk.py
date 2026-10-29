"""Bulk transcription (Phase 8 chapter 13, amended v1.173.0), and the brand
mark that came with the same release."""

from __future__ import annotations

from pathlib import Path

import pytest
from core.jobs import Transcript
from core.models import User
from core.recordings import Batch, MediaState, Recording
from core.templatetags.help_links import help_url
from django.urls import reverse
from tests.helpers import signed_in

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
STATIC = Path(__file__).resolve().parent.parent / "static"
PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def the_service_is_up(monkeypatch):
    # The drop is not offered while transcription is down, as the upload page
    # pauses it; the tests have no service, so one is said to be there.
    from core import uploads, whisperx

    monkeypatch.setattr(whisperx, "is_alive", lambda *args, **kwargs: True)
    # And room on the disk: a workstation under the floor would pause it too.
    monkeypatch.setattr(uploads, "free_disk_bytes", lambda: 10**13)


@pytest.fixture
def person(db) -> User:
    one = User.objects.create_local_admin("bulk-person", PASSWORD)
    one.is_local = False
    one.display_name = "Bo Lee"
    one.save()
    return one


def _recording(person, state, with_transcript=False):
    batch = Batch.objects.create(user=person)
    recording = Recording.objects.create(
        batch=batch,
        user=person,
        title="interview_0412",
        original_filename="interview_0412.m4a",
        media_state=state,
        duration_seconds=2480,
    )
    if with_transcript:
        Transcript.objects.create(recording=recording, language="en")
    return batch


def test_the_page_opens_on_the_drop_and_lights_its_place(person, client):
    signed_in(client, person)
    page = client.get(reverse("bulk")).content.decode()
    assert "<h1>Bulk transcription</h1>" in page
    assert 'id="bulk-drop" class="card">' in page
    assert 'id="bulk-batch" class="card" hidden' in page
    assert 'id="translate"' in page and 'id="language"' in page
    # Lit in the rail, with its one line and no pill while nothing runs.
    assert 'href="/bulk" aria-current="page"' in page
    assert "Files in, transcripts out, nothing kept" in page
    assert 'Bulk transcription <span class="pill' not in page
    # The guide's link goes to its own section.
    assert help_url("bulk").endswith("#bulk-transcription")


def test_a_running_batch_takes_the_page_and_the_rail_counts_it(person, client):
    batch = _recording(person, MediaState.PREPARING)
    signed_in(client, person)
    page = client.get(reverse("bulk")).content.decode()
    assert 'id="bulk-drop" class="card" hidden' in page
    assert f'data-batch="{batch.pk}"' in page
    assert 'Bulk transcription <span class="pill small ">0 of 1</span>' in page
    # Every page's rail says the same.
    home = client.get(reverse("home")).content.decode()
    assert "0 of 1</span>" in home


def test_a_finished_batch_is_the_download_and_the_rail_says_ready(person, client):
    batch = _recording(person, MediaState.READY, with_transcript=True)
    signed_in(client, person)
    page = client.get(reverse("bulk")).content.decode()
    assert f'data-batch="{batch.pk}"' in page
    assert 'id="bulk-drop" class="card" hidden' in page
    assert 'Bulk transcription <span class="pill small ok">Ready</span>' in page
    # Home's empty state points at the place only when the session is empty;
    # here it has a recording, so the rows show instead.
    home = client.get(reverse("home")).content.decode()
    assert "Ready to download" in home


def test_home_points_a_newcomer_at_the_place(person, client):
    signed_in(client, person)
    home = client.get(reverse("home")).content.decode()
    assert '<a href="/bulk">Bulk transcription</a> is made for that.' in home


def test_the_brand_mark_is_the_six_bars_everywhere_it_lives(person, client):
    sprite = (TEMPLATES / "icons.html").read_text(encoding="utf-8")
    assert 'id="i-gideon"' in sprite and 'id="i-bulk"' in sprite
    favicon = (STATIC / "favicon.svg").read_text(encoding="utf-8")
    assert favicon.count("v") >= 6 and "<rect" not in favicon
    drawer = (TEMPLATES / "gideon-drawer.html").read_text(encoding="utf-8")
    assert "#i-gideon" in drawer and "#i-chat" not in drawer
    # The top bar: the ring, and the name in two weights.
    signed_in(client, person)
    page = client.get(reverse("home")).content.decode()
    assert '<circle cx="16" cy="16" r="13.25"/>' in page
    assert 'Gideon <span class="second">Transcribe</span>' in page
    # The sign-in card draws the same mark where no office logo is uploaded.
    client.logout()
    gate = client.get(reverse("sign-in")).content.decode()
    assert '<circle cx="16" cy="16" r="13.25"/>' in gate
