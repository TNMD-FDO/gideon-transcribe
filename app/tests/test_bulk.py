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


# The download as Word or as text (v1.247.0) -----------------------------------


def test_the_downloads_are_the_menu_of_two(person, client):
    earlier = _recording(person, MediaState.READY, with_transcript=True)
    newest = _recording(person, MediaState.READY, with_transcript=True)
    signed_in(client, person)
    page = client.get(reverse("bulk")).content.decode()
    assert f'data-batch="{newest.pk}"' in page
    # Three menus: the one the page ends as, the one while a batch runs, and
    # the earlier batch's row. The first two get their addresses from the
    # script, which learns the batch as it runs; the row's are written here.
    assert page.count('class="menu transcripts-menu"') == 3
    assert '<span id="bulk-download-done">' in page
    assert '<span id="bulk-download" hidden>' in page
    assert f'href="/batch/{earlier.pk}/download?as=word" data-as="word"' in page
    assert f'href="/batch/{earlier.pk}/download" data-as="text"' in page
    assert "As Word (.docx)" in page and "As text (.txt)" in page
    # No download left on the page that gives text alone.
    assert '<a id="bulk-download' not in page


def test_the_script_points_both_choices_at_the_batch():
    script = (STATIC / "bulk.js").read_text(encoding="utf-8")
    assert "function pointDownload(holder, address, label)" in script
    assert 'word.href = address + "?as=word";' in script
    assert "text.href = address;" in script
    assert "pointDownload(doneLink, download);" in script
    assert "pointDownload(downloadLine, download," in script
    menu = (TEMPLATES / "transcripts-menu.html").read_text(encoding="utf-8")
    assert 'data-as="word"' in menu and 'data-as="text"' in menu
    assert '<span class="menu-label">{{ label }}</span>' in menu


def test_a_finished_batch_keeps_its_download_while_uploading_is_paused(
    person, client, monkeypatch
):
    """The drop is not on the page while the service is down, and the script
    had stopped for want of it, so the page stayed at "Reading the batch"."""
    from core import pieces, whisperx

    monkeypatch.setattr(whisperx, "is_alive", lambda *args, **kwargs: False)
    monkeypatch.setattr(pieces, "transcription_installed", lambda: True)
    batch = _recording(person, MediaState.READY, with_transcript=True)
    signed_in(client, person)
    page = client.get(reverse("bulk")).content.decode()
    assert "Uploading is paused until it is back" in page
    assert 'id="bulk-drop"' not in page
    assert f'data-batch="{batch.pk}"' in page
    assert 'id="bulk-download-done"' in page
    script = (STATIC / "bulk.js").read_text(encoding="utf-8")
    # The script starts on the batch section alone, and only the drop's own
    # listeners wait on the drop.
    assert "if (!section) { return; }" in script
    assert "!picker ||" not in script
    assert "var hasDrop = !!(picker && Card);" in script
    assert 'by("bulk-more").hidden = !hasDrop;' in script
