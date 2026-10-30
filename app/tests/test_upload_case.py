"""v1.174.0: the settings card shared by the Upload page and Bulk
transcription, and every batch from the Upload page going into a case."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from core import cases, settings_store
from core.models import User
from django.urls import reverse
from tests.helpers import signed_in

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"
PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def room(monkeypatch):
    from core import uploads, whisperx

    monkeypatch.setattr(whisperx, "is_alive", lambda *args, **kwargs: True)
    monkeypatch.setattr(uploads, "free_disk_bytes", lambda: 10**13)


@pytest.fixture
def person(db) -> User:
    one = User.objects.create_local_admin("case-person", PASSWORD)
    one.is_local = False
    one.display_name = "Cy Dale"
    one.save()
    return one


CARD = (
    'id="diarize"',
    'id="hint"',
    'id="translate"',
    'id="language"',
    'id="vocabulary"',
    'id="context"',
)


def test_the_bulk_page_folds_the_whole_settings_card_under_the_files(person, client):
    signed_in(client, person)
    page = client.get(reverse("bulk")).content.decode()
    assert 'id="bulk-settings" class="settings-fold"' in page
    for control in CARD:
        assert control in page, control
    # The case-bound settings are not there, whatever the office's switches.
    settings_store.set_to("folder_management", True)
    cases.Case.objects.create(owner=person, name="Ramirez")
    page = client.get(reverse("bulk")).content.decode()
    assert 'id="add-to-case"' not in page and 'id="recording-type"' not in page
    assert 'id="summaries-tick"' not in page and "which-case" not in page
    # The More options are plain fields here, a fold on the Upload page.
    assert 'id="more" class="more-plain"' in page
    assert "upload-settings." in page  # the shared script, collected
    # Both pages draw the one include.
    include = (TEMPLATES / "upload-settings.html").read_text(encoding="utf-8")
    for name in ("upload.html", "bulk.html"):
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        assert 'include "upload-settings.html"' in text, name
    assert 'id="the-settings"' in include


def test_the_upload_page_asks_which_case_and_never_this_session(person, client):
    settings_store.set_to("folder_management", True)
    cases.Case.objects.create(owner=person, name="Ramirez")
    signed_in(client, person)
    page = client.get(reverse("upload")).content.decode()
    assert "Into which case?" in page and 'id="which-case"' in page
    assert ">Ramirez</option>" in page
    assert "<b>This session only</b>" not in page and "Where do they go?" not in page
    # A file's own Add to case box lists the cases and no session choice.
    assert 'id="add-to-case"' in page
    box = page.split('id="add-to-case"')[1].split("</select>")[0]
    assert 'option value=""' not in box
    # The fold stays a fold on this page, and the card is the shared one; its
    # attributes may come in any order since a spacing class joined them.
    assert re.search(r'<details[^>]*id="more"', page)
    for control in CARD:
        assert control in page, control


def test_a_person_with_no_case_is_sent_to_make_one_or_to_bulk(person, client):
    settings_store.set_to("folder_management", True)
    signed_in(client, person)
    page = client.get(reverse("upload")).content.decode()
    assert "No case to upload into yet" in page
    assert 'href="/bulk"' in page and "New case" in page
    assert 'id="picker"' not in page  # no steps without a case to go into
    # With cases off there is no case to ask about and the page is as it was.
    settings_store.set_to("folder_management", False)
    page = client.get(reverse("upload")).content.decode()
    assert 'id="picker"' in page and "Into which case?" not in page
