"""The Bench: the viewer's third column on a wide window.

The stylesheet lays the desk out two ways by the width of the window, and the
script asks the same question. These tests hold the pieces together without a
browser: the template's shape, the stylesheet's rule, the script's flag, and
the glossary word.
"""

import re
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
ROOT = APP.parent


def test_the_column_wraps_the_picture_and_the_panels():
    page = (APP / "templates" / "viewer.html").read_text(encoding="utf-8")
    column = page.index('<div class="column">')
    assert page.index('id="thumb"') > column
    assert page.index('<div class="bench">') > column
    assert page.index('id="sheet"') > page.index('<div class="bench">')
    # The dock keeps the title and the transport only.
    dock = page.index('<div class="dockhead">')
    assert dock < page.index('class="head"') < column
    assert 'id="thumb"' not in page[:column]


def test_the_stylesheet_has_both_shapes():
    css = (APP / "static" / "app.css").read_text(encoding="utf-8")
    assert ".column { display: contents; }" in css
    wide = css[css.index("@media (min-width: 1280px)") :]
    assert '"head column"' in wide and '"body column"' in wide
    assert "--column-width" in wide
    # The case rail gives way while the Bench is narrow.
    assert "(min-width: 1280px) and (max-width: 1499px)" in css


def test_the_script_asks_the_same_question_as_the_stylesheet():
    script = (APP / "static" / "viewer.js").read_text(encoding="utf-8")
    assert 'window.matchMedia("(min-width: 1280px)")' in script
    assert "--column-width" in script and "--thumb-width" in script
    # Esc and the tabs never close the Bench.
    body = script[script.index("function hideSheet") :]
    assert re.search(r"if \(onTheBench\(\)\) \{ return; \}", body)


def test_the_word_is_in_the_glossary():
    glossary = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    assert "**Bench**:" in glossary
