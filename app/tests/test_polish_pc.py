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
    # direct), the Incidents table, the loose recordings table and the clips.
    assert case.count('<td class="name">') == 4
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
    assert 'localStorage.getItem("caserail-fold")' in viewer
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
