"""v1.171.1: the smoother page change, pinned.

The stylesheet asks for the crossfade and names the three held elements;
the page declares both colour schemes; the root carries the background;
and nothing in the pages prefetches or prerenders another page.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from core.models import User
from tests.helpers import signed_in

STATIC = Path(__file__).resolve().parent.parent / "static"
TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def test_the_stylesheet_crossfades_and_holds_the_three_elements_still():
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    assert "@view-transition { navigation: auto; }" in css
    assert ".nav { view-transition-name: top-line; }" in css
    assert "nav.rail { view-transition-name: rail; }" in css
    assert "#case-tabs { view-transition-name: case-tabs; }" in css
    assert "html { background: var(--bg); }" in css
    # Less motion asked for: none.
    assert (
        "::view-transition-old(*), ::view-transition-new(*) "
        "{ animation: none !important; }"
    ) in css


@pytest.mark.django_db
def test_the_page_declares_both_schemes_and_prefetches_nothing(client):
    person = User.objects.create_local_admin("asker", "a-long-enough-password")
    signed_in(client, person)
    page = client.get("/").content.decode()
    assert '<meta name="color-scheme" content="light dark">' in page
    for template in TEMPLATES.rglob("*.html"):
        text = template.read_text(encoding="utf-8")
        assert 'rel="prefetch"' not in text and 'rel="prerender"' not in text, template
        assert "speculationrules" not in text, template
