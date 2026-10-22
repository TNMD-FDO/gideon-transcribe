"""The Preview in the page (v1.151.0; the drawing phase-5-preview-and-clock.html):
the floating card becomes a panel of the page's own column where the page
offers one, a sheet from the foot elsewhere, and carries the person, their
role, a tab per recording that taught the print, their samples and the
clock verdict. The pages offer the column; the hear buttons carry the
person. And the Speakers tab and the Voices place as cards."""

from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def test_the_preview_script_places_itself_in_the_page_or_as_a_sheet():
    script = (HERE / "static" / "preview.js").read_text(encoding="utf-8")
    for piece in (
        'document.querySelector("[data-preview-host]")',
        "window.innerWidth >= 900",
        '" in-page"',
        '" sheet"',
        "preview-handle",
        "function drawPerson(",
        "clock unsure · heard about",
        "clock sure",
        "data-preview-tab=",
        "data-preview-sample=",
        "told.clock_verdict.play_from",
        "&speaker=",
        "hit.dataset.previewPerson",
        "hit.dataset.previewTabs",
        'placed.classList.remove("has-preview")',
    ):
        assert piece in script, piece
    # The card is no longer dragged about: the head is not a handle.
    assert 'drag(card.querySelector(".preview-head"))' not in script
    css = (HERE / "static" / "app.css").read_text(encoding="utf-8")
    for rule in (
        ".preview-card.in-page {",
        ".preview-card.sheet {",
        ".preview-person {",
        ".preview-samples {",
        ".sg-side.has-preview:not(.has-snippet) .sg-context { display: none; }",
        ".voices-panes:has(.has-preview)",
        # The snippet (ADR 0023, v1.152.0).
        ".preview-card.snippet .preview-lines {",
        ".preview-card.snippet .preview-line.context {",
    ):
        assert rule in css, rule
    # The Preview of a voice is a snippet (v1.152.0): the line heard with one
    # either side, the player stopping after it, no reading on, the page's
    # column kept beside it.
    for piece in (
        "function isSnippet()",
        "function snippetRows()",
        "function snippetLine()",
        '" snippet"',
        '"has-snippet"',
        "stopAt = told.clock_verdict ? told.clock_verdict.play_to",
        "player.pause(); stopAt = null;",
        "!isSnippet() && noting === null",
        "function playSpan(",
        "floating.playSpan(",
        "the line heard, with a line either side",
        "more of their voice here: each plays one line",
    ):
        assert piece in script, piece


def test_the_pages_offer_the_column_and_the_buttons_carry_the_person():
    guided = (HERE / "templates" / "speakers-guided.html").read_text(encoding="utf-8")
    assert 'class="sg-preview" data-preview-host hidden' in guided
    assert 'class="sg-side"' in guided and 'id="sg-context"' in guided
    case = (HERE / "templates" / "case.html").read_text(encoding="utf-8")
    assert 'class="preview-side" data-preview-host hidden' in case
    assert "data-preview-person=" in case and "data-preview-speaker=" in case
    voices = (HERE / "templates" / "voices.html").read_text(encoding="utf-8")
    assert "data-preview-host" in voices and "data-preview-person=" in voices
    guided_js = (HERE / "static" / "speakers-guided.js").read_text(encoding="utf-8")
    assert "data-preview-person='" in guided_js and "data-preview-tabs='" in guided_js
    classic = (HERE / "static" / "speakers-page.js").read_text(encoding="utf-8")
    assert "data-preview-person='" in classic and "data-preview-tabs='" in classic


def test_the_speakers_tab_and_the_voices_place_are_cards():
    case = (HERE / "templates" / "case.html").read_text(encoding="utf-8")
    for piece in (
        'class="needs" id="needs"',
        "to name</div>",
        "sounds like</div>",
        "Nothing waits on you in this case.",
        'data-filter-for="people"',
        'data-filter="waiting"',
        'class="person-card',
        'details class="menu"',
        "Rename everywhere",
        "Save role and notes",
        "Merge into",
        "Unlearn their voice",
        "Delete from this case",
        "Stop keeping for the",
        "Keep for the {{ b.unit }}...",
        "Decided so far in this case",
        "Sounds like, per person",
        "Unnamed speakers, by recording",
        "Add a person",
        "people-cards.js",
    ):
        assert piece in case, piece
    # The tab never carries Accept: every waiting line points at the call.
    assert "match-accept" not in case
    voices = (HERE / "templates" / "voices.html").read_text(encoding="utf-8")
    for piece in (
        'class="month"',
        "check{{ this_month.checks|pluralize }} this month",
        'data-filter-for="voices"',
        'data-filter="forgotten"',
        'class="person-card',
        "Forget for the {{ unit }} unit",
        "Hear them on",
        "Keep again from a case",
        "decided from the book, by month",
    ):
        assert piece in voices, piece
    script = (HERE / "static" / "people-cards.js").read_text(encoding="utf-8")
    assert "data-filter-for" in script and "details.menu" in script
    css = (HERE / "static" / "app.css").read_text(encoding="utf-8")
    for rule in (".needs {", ".person-card {", "details.menu .menu-body {", ".month {"):
        assert rule in css, rule
