"""The Panel's bars float at the top (v1.181.0, at the maintainer's word).

The tray's bar stands above the page's title, one line with Apply and the
changes folded under their count; a settings page carries the edits bar
and its form the id the bar's button names.
"""

from __future__ import annotations

import pytest
from core.models import User
from django.urls import reverse
from tests.helpers import signed_in

PASSWORD = "a-long-enough-password"


@pytest.fixture
def admin(db):
    return User.objects.create_local_admin("bars-admin", PASSWORD)


def test_the_tray_bar_stands_above_the_title_and_folds_its_changes(admin, client):
    signed_in(client, admin)
    page = client.get(reverse("panel-settings", args=["cases"])).content.decode()
    assert 'id="tray-bar"' not in page
    assert 'id="edits-bar"' in page and 'form="settings-form"' in page
    assert 'id="settings-form"' in page
    # A change put in the tray: the bar, above the title, folded.
    client.post(reverse("panel-edit", args=["cases"]), {"folder_management": "on"})
    page = client.get(reverse("panel-settings", args=["cases"])).content.decode()
    assert 'id="tray-bar"' in page
    assert page.index('id="tray-bar"') < page.index("<h1>")
    assert "change waiting in the tray" in page
    assert '<details class="grow">' in page and "Apply</button>" in page
