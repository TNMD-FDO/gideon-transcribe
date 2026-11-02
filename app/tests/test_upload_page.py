"""The Upload page tightened (v1.182.0, the drawing phase-8-upload-page.html).

The step list is opened once (it had been opened twice since v1.174.0,
which laid the three steps out inside the left half of the page); the
settings card's ticks sit two across with a one-line caption standing and
the longer help behind a question mark or Show the help; the start row
carries the count and the button; the lead carries the line that stood at
the foot; which files is a link on the limits line. Bulk transcription
shares the card and takes the ticks and Show the help with it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from core import settings_store, uploads, whisperx
from core.cases import Case
from core.models import User
from tests.helpers import signed_in

APP = Path(__file__).resolve().parent.parent
PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def switches(db, monkeypatch):
    settings_store.set_to("folder_management", True)
    monkeypatch.setattr(whisperx, "is_alive", lambda *args, **kwargs: True)
    monkeypatch.setattr(uploads, "free_disk_bytes", lambda: 10**13)
    whisperx.forget_alive()


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("upload-page", PASSWORD)


def test_the_step_list_is_opened_once_and_the_page_reads_as_drawn(person, client):
    Case.objects.create(owner=person, name="Harbour Street stop")
    signed_in(client, person)
    page = client.get("/upload").content.decode()
    assert page.count('<ol class="steps">') == 1
    assert "Nothing leaves this building." in page.split('class="asks"')[0]
    assert page.count("Nothing leaves this building") == 1
    assert 'id="which-files"' in page and 'id="formats" hidden' in page
    assert 'class="dialog start-row"' in page and 'id="start-words"' in page
    assert "More options: language, vocabulary, context, audio clean-up" in page
    # The ticks: two across, each with its caption and its help (the email
    # and the summaries ticks show only when the office offers them).
    ticks = page.split('<div class="ticks">')[1].split('id="diarize-warning"')[0]
    for name in ("diarize", "translate"):
        assert f'id="{name}"' in ticks, name
    assert ticks.count('class="tick-block"') >= 2
    assert ticks.count('class="muted small cap"') >= 2
    assert ticks.count('class="muted small help"') >= 2
    assert ticks.count('class="q" data-help') >= 2
    assert 'id="show-help"' in page
    # The old captions are not duplicated outside the blocks.
    assert page.count("Labels each line with who is speaking") == 1


def test_bulk_transcription_shares_the_ticks(person, client):
    signed_in(client, person)
    page = client.get("/bulk").content.decode()
    assert '<div class="ticks">' in page and 'id="show-help"' in page
    assert 'id="diarize"' in page and 'class="q" data-help' in page


def test_the_stylesheet_carries_the_rules():
    css = (APP / "static" / "app.css").read_text(encoding="utf-8")
    assert ".ticks { display: grid; grid-template-columns: repeat(2," in css
    assert ".show-help .tick-block .help { display: block; }" in css
    assert re.search(r"\.start-row\.floating \{ position: fixed; bottom: 0;", css)
    assert "button.link {" in css
