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
