"""The stage and the work area: the viewer's shape from v1.46.0.

The stylesheet lays the desk out two ways by the width of the window, and the
script asks the same question. These tests hold the pieces together without a
browser: the template's shape, the stylesheet's rules, the script's flag, the
glossary words, and the marking routes that never change the tab.
"""

import re
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
ROOT = APP.parent


def test_the_stage_wraps_the_picture_the_transport_and_the_line_being_spoken():
    page = (APP / "templates" / "viewer.html").read_text(encoding="utf-8")
    stage = page.index('<div class="stage">')
    assert page.index('class="head"') < stage
    assert stage < page.index('id="thumb"') < page.index('class="transport"')
    assert (
        page.index('class="transport"')
        < page.index('id="now"')
        < page.index('id="stage-grip"')
    )
    assert page.index('id="stage-grip"') < page.index('id="timeline"')
    # Nothing about the camera on the stage since v1.52.0.
    assert 'id="describe-now"' not in page
    # Then the marking strip, then the work area with its tabs, Transcript first.
    assert page.index('id="caption"') < page.index('class="tabbar"')
    tabs = re.findall(r'class="tab(?: on)?" data-panel="([a-z]+)"', page)
    assert tabs == ["transcript", "clips", "summary", "chat", "details"]
    assert 'class="tab on" data-panel="transcript"' in page
    assert (
        page.index('class="tabbar"')
        < page.index('id="panels"')
        < page.index('class="panel read" data-panel="transcript"')
    )
    # The follow pill in a holder of no height; the speakers fold away.
    assert 'class="followhold"' in page and 'id="cast-toggle"' in page
    panels = (APP / "templates" / "viewer-panels.html").read_text(encoding="utf-8")
    assert 'id="download-clips"' in panels
    # The marking strip's three controls.
    for control in ("clip-said", "clip-preview-strip", "clip-save-go", "drop-clip"):
        assert f'id="{control}"' in page
    # Nothing of the sheet is left.
    for gone in (
        "sheet-tab",
        'id="sheet"',
        "sheet-grip",
        "expand-sheet",
        "close-sheet",
        "thumb-grip",
        'class="bench"',
        'class="column"',
    ):
        assert gone not in page, gone


def test_the_stylesheet_has_both_shapes():
    css = (APP / "static" / "app.css").read_text(encoding="utf-8")
    assert ".stage { display: contents; }" in css
    narrow = css[
        css.index("/* The desk is one grid")
        if "/* The desk is one grid" in css
        else css.index("/* The desk:") :
    ]
    assert '"thumb head"' in narrow and '"thumb transport"' in narrow
    assert ".desk.sound {" in css
    wide = css[css.index("@media (min-width: 1280px) {\n  .desk:not(.sound)") :]
    assert '"stage body"' in wide and "--stage" in wide
    assert ".desk:not(.sound) .stagegrip {" in wide
    # The Ledger: time, name, words, buttons; names hidden take their column with them.
    assert "grid-template-columns: 5.5em 9em minmax(0, 1fr) auto;" in css
    assert (
        "body.no-speakers .seg { grid-template-columns: 5.5em minmax(0, 1fr) auto; }"
        in css
    )
    assert ".seg.cont .who .name { visibility: hidden; }" in css
    assert "font-size: 16px;" in css[css.index(".read .transcript {") :][:300]
    # The cast is stuck under the tab bar.
    cast = css[css.index(".cast {") :][:200]
    assert "position: sticky;" in cast
    # The line being spoken is styled by its id, never by a bare "now" class:
    # the word being said carries that class too, and took the box's layout
    # (v1.46.0 to v1.50.0), breaking onto a line of its own and vanishing on
    # a sound recording.
    assert ".desk #now {" in css and ".desk.sound #now {" in css
    assert ".desk .now" not in css and ".desk:not(.sound) .now" not in css
    for gone in (
        ".sheetbar",
        ".sheet-tab",
        ".sheetgrip",
        "--column-width",
        "--thumb-width",
        ".thumb.audio",
    ):
        assert gone not in css, gone


def test_the_script_asks_the_same_question_as_the_stylesheet():
    script = (APP / "static" / "viewer.js").read_text(encoding="utf-8")
    assert 'window.matchMedia("(min-width: 1280px)")' in script
    assert "--stage" in script and "stage-width" in script
    assert (
        "function openTab(" in script and "window.VIEWER.openSheet = openTab" in script
    )
    # A citation lands on the Transcript tab; D opens Details.
    shown = script[script.index("window.VIEWER.showSegment = function") :][:200]
    assert 'openTab("transcript")' in shown
    assert 'openTab("details")' in script
    for gone in (
        "hideSheet",
        "settleTheBench",
        "sheet-height",
        "LEAST_ROOM_ABOVE",
        "thumb-grip",
    ):
        assert gone not in script, gone
    # Lost once in the rewrite and not to be lost again: the shortcuts
    # overlay and the pop-out, which the keyboard handler leans on.
    assert 'getElementById("shortcuts")' in script and "function shortcuts(" in script
    assert 'getElementById("open-shortcuts")' in script
    assert "requestPictureInPicture" in script and "enterpictureinpicture" in script
    # Follow scrolls only once the line has left the middle of the column.
    assert "function outOfTheMiddle(" in script
    assert "outOfTheMiddle(now)" in script
    # Marking never changes the tab: the clip tool opens it only for Save,
    # New clip and Adjust.
    tool = (APP / "static" / "clip-tool.js").read_text(encoding="utf-8")
    assert tool.count('window.VIEWER.openTab("clips")') == 2
    assert "openSheet" not in tool
    save = script[
        script.index('var saveGo = document.getElementById("clip-save-go")') :
    ]
    assert 'openTab("clips")' in save[:400]


def test_the_words_are_in_the_glossary():
    glossary = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    assert "**Stage**:" in glossary and "**Work area**:" in glossary
    assert "**Bench**:" not in glossary
