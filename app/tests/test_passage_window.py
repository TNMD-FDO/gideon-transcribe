"""The passage window (Phase 12 chapter 11, v1.220.0; the drawing
comparison-passage.html, figure 6): a finding's quote on the Comparison
page is a press that opens a floating window with the report's pages in
one scroll, opened at the cited paragraph. These pins hold the pieces
together: the script, its place on the page, the quote's markup, the hook,
and the stylesheet's rules."""

from pathlib import Path

APP = Path(__file__).resolve().parent.parent
STATIC = APP / "static"
CSS = (STATIC / "app.css").read_text(encoding="utf-8")


def test_the_script_holds_the_window():
    script = (STATIC / "passage-window.js").read_text(encoding="utf-8")
    assert "window.PASSAGE_WINDOW = { open: open, close: close" in script
    # The report's pages stacked in one scroll, a label between them, the
    # cited paragraph lit, and the zoom's three steps.
    gap = '<div class=\'pw-gap\'>page " + one.number + " of " + pages.length'
    assert gap in script
    assert "data-zoom='fit'" in script and "data-zoom='1'" in script
    assert "data-zoom='1.5'" in script
    assert "one.width * 110 / 72 * parseFloat(zoom)" in script
    # Opened a third of the way down, Back to the citation once away,
    # remembered size and zoom, Escape closes.
    assert "top - doc.clientHeight / 3" in script
    assert "back.hidden = !away;" in script
    assert 'var KEY = "passage-window";' in script
    assert 'event.key === "Escape" && win' in script
    # A paragraph pressed tells the page.
    assert "hooks.onParagraph(parseInt(box.dataset.page, 10)" in script


def test_the_quote_is_the_press():
    panel = (STATIC / "report-panel.js").read_text(encoding="utf-8")
    quote = "<button type='button' class='quote-press' data-passage='1'"
    quote += " data-page='\" + one.page + \"' data-para='\" + one.n + \"'"
    assert quote in panel
    # The window where the page has one, the paragraph card elsewhere.
    assert "if (hooks.passage) { hooks.passage(quote); return; }" in panel
    card = "if (cite && window.PARAGRAPH_CARD) { window.PARAGRAPH_CARD.open(cite); }"
    assert card in panel
    page = (STATIC / "comparison-page.js").read_text(encoding="utf-8")
    assert "passage: function (quote) {" in page
    assert "stateUrl: page.dataset.documentState," in page
    assert "onParagraph: function (number, n) { lightRows(number, n); }" in page
    template = (APP / "templates" / "comparison.html").read_text(encoding="utf-8")
    assert "{% static 'passage-window.js' %}" in template
    assert template.index("passage-window.js") < template.index("comparison-page.js")


def test_the_window_rules_hold():
    for rule in (
        ".quote-press { font: inherit; color: var(--muted); background: none;",
        ".passage-win { position: fixed; right: 20px; bottom: 20px; z-index: 46;",
        "width: 640px; height: 560px; min-width: 360px; min-height: 280px;",
        "overflow: hidden; resize: both; }",
        "body.gideon-open .passage-win { right: calc(var(--gideon, 420px) + 28px); }",
        ".passage-doc { flex: 1 1 auto; min-height: 0; overflow: auto;",
        ".pw-page .doc-box.lit { outline: 2px solid var(--accent);",
        ".pw-zoom button.on { background: var(--accent-soft); color: var(--accent);",
    ):
        assert rule in CSS, rule
