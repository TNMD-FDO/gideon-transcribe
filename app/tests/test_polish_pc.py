"""The polish walk's PC cut (v1.175.0): what the measurements found at laptop
and wide-screen widths, pinned so it stays fixed."""

from __future__ import annotations

import re
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
CSS = (APP / "static" / "app.css").read_text(encoding="utf-8")
TEMPLATES = APP / "templates"


def test_no_type_under_the_label_size():
    # The look allows five sizes and nothing under 11; the chronology's lane
    # labels and the strip's swap had been 9 and 10.
    assert not re.search(r"font-size:\s*(9|10)px", CSS)
    assert not re.search(r"font-size:\s*0\.[0-6]\d*rem", CSS)


def test_the_name_column_is_floored_by_its_own_class():
    assert ".tbl td.name { min-width: 12rem; }" in CSS
    assert "#recordings td:first-child { min-width" not in CSS
    case = (TEMPLATES / "case.html").read_text(encoding="utf-8")
    # The Recordings table (whose first cell is the tick when the person may
    # direct) and the clips; the loose videos table left the Incidents tab in
    # v1.180.1 and the incidents table in v1.199.0 (the Reader lists them).
    assert case.count('<td class="name">') == 2
    # The notes column had been the one crushed to 39 px once the name held.
    assert ".tbl td.notes { min-width: 7rem; }" in CSS
    assert ".panes.audit .tbl td.mono { white-space: nowrap; }" in CSS


def test_the_panels_wide_tables_wrap_or_scroll_in_a_box():
    audit = ".panes.audit .tbl td { white-space: normal; overflow-wrap: break-word; }"
    assert audit in CSS
    assert ".tbl.users td.small, .tbl.users td.muted { min-width: 9rem; }" in CSS
    for name in ("users.html", "audit.html"):
        page = (TEMPLATES / "panel" / name).read_text(encoding="utf-8")
        assert '<div class="tbl-wrap">' in page and page.count("</div>") >= 1, name


def test_contrast_nudges_and_the_focus_ring():
    # The ok pill's ink against its soft background: 5.8 to 1, was 4.4.
    assert "--ok: #27683f;" in CSS and "--ok: #2f7d4f;" not in CSS
    # The changed mark reads as ink; the citation link has a dark-theme shade.
    assert "color: var(--changed-ink)" in CSS and "--changed-ink: #7a5c00;" in CSS
    assert "color: var(--cite)" in CSS and "--cite: #8ec7ea;" in CSS
    # No rule removes the focus ring on keyboard focus any more.
    for rule in re.findall(r"[^{}]+\{[^}]*outline:\s*(?:none|0)[^}]*\}", CSS):
        selector = rule.split("{")[0]
        assert ":focus-visible" not in selector or ":not(:focus-visible)" in rule, rule


def test_the_incident_page_has_a_heading():
    page = (TEMPLATES / "incident.html").read_text(encoding="utf-8")
    assert '<h1 class="grow" id="inc-title">' in page
    look = ".inc-head h1#inc-title { font: inherit; font-weight: 600; margin: 0; }"
    assert look in CSS


def test_the_preview_never_autoplays():
    # v1.175.1: the Preview's media had the autoplay attribute, so the Notes
    # tab's Page shape played at open whatever the quiet flag said; the
    # script's own play() is the only thing that starts a recording.
    preview = (APP / "static" / "preview.js").read_text(encoding="utf-8")
    assert "autoplay" not in preview.replace("No autoplay attribute", "")


def test_what_arrives_after_the_paint_keeps_its_place():
    # The motion release (v1.176.0): placeholders in each thing's own shape,
    # replaced by the script, never pushed; the rail folded before the paint.
    viewer = (TEMPLATES / "viewer.html").read_text(encoding="utf-8")
    assert viewer.count('<li class="seg skeleton"') == 1 and "123456789012" in viewer
    # The rail that folded before the paint went into the walker (v1.221.0).
    assert 'id="walker"' in viewer and "caserail-fold" not in viewer
    incident = (TEMPLATES / "incident.html").read_text(encoding="utf-8")
    assert '<div class="lane placeholder"' in incident and "state.cameras" in incident
    chron = (APP / "static" / "chronology.js").read_text(encoding="utf-8")
    assert 'host.classList.add("loading")' in chron
    assert chron.count('host.classList.remove("loading")') == 2
    for rule in (
        ".transcript li.skeleton {",
        ".chron.loading { min-height: 50vh; }",
        "#lanes .lane.placeholder .track {",
    ):
        assert rule in CSS, rule
    # Playback touches the lit line and the play button only when they change.
    preview = (APP / "static" / "preview.js").read_text(encoding="utf-8")
    assert "if (was !== lit)" in preview
    notes = (APP / "static" / "notes-page.js").read_text(encoding="utf-8")
    assert "play.dataset.state !== state" in notes


def test_the_stylesheet_keeps_its_own_scale_and_the_templates_keep_no_spacing():
    # The stylesheet's tidy-up (v1.177.0): every size on the look's scale is
    # its token; the common margins, gaps and widths are classes, not inline
    # styles; nothing opens a browser pop-up.
    # Since v1.178.0 no size at all is written in pixels: every one is a token.
    assert not re.search(r"font-size:\s*\d+px", CSS)
    for token in ("--t-count: 20px;", "--t-reading: 16px;"):
        assert token in CSS, token
    classes = (".m0 {", ".mt6 {", ".mb8 {", ".gap6 {", ".wrap {", ".scroll-x {")
    for cls in classes + (".inline-form {",):
        assert cls in CSS, cls
    inline = 0
    pages = list(TEMPLATES.glob("*.html")) + list((TEMPLATES / "panel").glob("*.html"))
    for path in pages:
        inline += path.read_text(encoding="utf-8").count('style="')
    # A ratchet: 96 after the conversion, down from 241; the rest are values
    # computed per element (a bar's width, a colour) and one-offs.
    assert inline <= 96, inline
    for script in (APP / "static").glob("*.js"):
        text = script.read_text(encoding="utf-8")
        assert not re.search(r"(?<![\w.])(?<!function )alert\(", text), script.name


def test_the_chronology_paints_cameras_in_the_pages_tokens():
    # The dark walk (v1.179.0): the server names a camera by the light
    # palette hex the exports draw with; the page paints the same camera in
    # its own --sp token, so dark gets the dark palette and the ink reads.
    from core.chronology import FIGURE_COLOURS

    script = (APP / "static" / "chronology.js").read_text(encoding="utf-8")
    for index, hexcode in enumerate(FIGURE_COLOURS, start=1):
        assert f'"{hexcode}": {index}' in script, hexcode
    assert "paint(e.colour)" in script and "paint(b.colour)" in script
    assert "e.colour ||" not in script and "+ b.colour +" not in script
    assert '.colour + "' not in script


def test_the_case_tabs_walk_fixes_hold():
    # The case tabs walk (v1.216.0): every tab of a case at 1366 and 2560 with
    # long names and titles. The seven breaks and the nine that looked wrong,
    # each pinned by the rule that fixed it.
    for rule in (
        "@media (max-width: 1399px) { .rail .item b { flex-wrap: wrap; } }",
        ".case-bar .tabs .tab { white-space: nowrap; flex: none; }",
        ".case-tabs .here { min-width: 0; max-width: 100%; overflow: hidden;",
        ".inc-work { max-height: calc(100vh - 250px); }",
        ".case-page #recordings td.name { white-space: normal; min-width: 18rem; }",
        "#recordings td.name > b { display: inline-block; max-width: 36rem;",
        ".kv { grid-template-columns: fit-content(16rem) minmax(0, 1fr); }",
        ".seg .actions .w { display: none; }",
        ".people-toolbar .add-person form.card { position: absolute;",
        ".sg-ctx-line .s { max-width: 13rem; overflow: hidden;",
        ".clips-tbl .fold { display: none; }",
        ".chron .tags .tag { min-height: 0; height: 16px; line-height: 16px; }",
        ".inc-cameras th, .inc-cameras td.mono { white-space: nowrap; }",
        "minmax(7rem, 11rem) minmax(7rem, 10rem) minmax(10rem, 1fr) auto; }",
        ".doc-ways .btn { display: block; max-width: 100%; min-width: 0;",
        ".compare-rows td.t { white-space: normal; }",
    ):
        assert rule in CSS, rule
    case = (TEMPLATES / "case.html").read_text(encoding="utf-8")
    assert '<table class="tbl clips-tbl">' in case
    assert case.count('class="fold"') == 4 and case.count('class="muted fold"') == 2
    assert 'class="muted small fold-line"' in case
    assert "{% if holds.has_video %}<th>Vision</th>{% endif %}" in case
    static = APP / "static"
    viewer = (static / "viewer.js").read_text(encoding="utf-8")
    assert viewer.count("<span class='w'>") == 4
    chronology = (static / "chronology.js").read_text(encoding="utf-8")
    assert "Math.max(6, Math.min(ticked().length, most()) + 2)" in chronology
    assert 'querySelectorAll(".tag:not(.build)")' in chronology
    guided = (static / "speakers-guided.js").read_text(encoding="utf-8")
    assert "title='\" + escape(seg.speaker) + \"'>" in guided


def test_the_production_walk_fixes_hold():
    # The production walk (v1.217.0): the whole site on the office's server
    # at 1366, 2560 and 3440, by a probe and by eye. The one break and the
    # eight that looked wrong the maintainer picked first, each pinned by the
    # rule or the line that fixed it.
    for rule in (
        "#transcript .seg { position: relative; grid-template-columns: 5.5em 9em",
        "#transcript .seg .actions { position: absolute; right: 6px; top: 3px;",
        "#transcript .seg.here .actions { position: static; grid-column: 3;",
        "#documents th:first-child, #documents td:first-child { min-width: 16rem; }",
        ".shelf-gallery { grid-template-columns: repeat(auto-fill, minmax(18rem",
        ".shelf-picture .document-more .menu-body { left: 0; right: 0;",
        "#case-notes-desk .np-left { max-height: none; }",
        ".chron .lane-row .lane-name .w > span { display: block; flex: 1 1 auto;",
        ".map-help > div { left: auto; right: 0; max-width: calc(100vw - 48px); }",
        ".map-row .tk-none { display: block; width: 14px; height: 14px; }",
        "(max-width: 1599px) { .panes.users { grid-template-columns: minmax(0, 1fr);",
        ".quota-raise-form .form input[type=text] { width: 100%; min-width: 0;",
    ):
        assert rule in CSS, rule
    static = APP / "static"
    map_js = (static / "map.js").read_text(encoding="utf-8")
    cell = "<span class='tk-none'></span>"
    cell += "<span class='dot' style='background: var(--muted)'></span>"
    assert map_js.count(cell) == 2
    chronology = (static / "chronology.js").read_text(encoding="utf-8")
    name = '\'><span>" + esc(b.name || shortName(b)) + "</span></button>"'
    assert name in chronology


def test_the_ultrawide_measure_holds():
    # The ultrawide measure (v1.218.0): the drawing's figures 3, 4 and 6 for
    # the production walk's findings 4, 19 and 3, with 5, 6 and 9 riding.
    for rule in (
        "@media (min-width: 1800px) { .case-page #recordings { width: auto; } }",
        ".search-hits .hit-words { max-width: 90ch; }",
        "minmax(0, max-content) minmax(0, 90ch); }",
        "(max-width: 1599px) { body.gideon-open .shell > main { padding-right: 0; } }",
        ".case-page #recordings td.prepared { min-width: 7rem; }",
        ".case-page #recordings td.prepared .pill { white-space: nowrap; }",
    ):
        assert rule in CSS, rule
    case = (TEMPLATES / "case.html").read_text(encoding="utf-8")
    chevron = '<a href="{% url \'viewer\' recording.pk %}" class="plain">'
    chevron += '<span class="chev" aria-hidden="true">&#8250;</span> <b>'
    assert chevron in case
    assert '<td><div class="hit-words">{{ hit.text }}' in case
    # 9 was the case's list folding on a short window; since v1.221.0 the
    # list is the walker's and the speakers fold on a short window instead.
    viewer = (APP / "static" / "viewer.js").read_text(encoding="utf-8")
    assert "window.innerHeight < 900" in viewer and "caserail-fold" not in viewer


def test_the_shelf_menus_drop_clear_of_the_card():
    # The Documents tab's menus (v1.219.0): the shelf card scrolls sideways,
    # which clips a menu opened inside it; while a menu is open the card
    # lets it out instead of growing a scrollbar.
    rule = ".card.shelf-card:has(details.menu[open])"
    rule += " { overflow: visible !important; }"
    assert rule in CSS
    # And the menu opens rightwards, capped, its long names wrapping.
    opens = "details.menu.compare-against > ul, .cmp-page details.menu.cmp-against > ul"
    opens += " { left: 0; right: auto;"
    assert opens in CSS
    assert "details.menu.cmp-against > ul button { white-space: normal;" in CSS
