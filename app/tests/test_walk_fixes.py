"""v1.75.1: the fix release from the walk of 2026-09-22, the parts a test
can hold: the Start tile's line for an Admin who owns nothing, the
sign-out page's line, a Search hit cut to the sentence with the words,
and nothing that needs a recording (the Report tab's switch is in
test_documents_read)."""

from __future__ import annotations

from pathlib import Path

import pytest
from core import case_search, lifecycle, pages, settings_store
from core.cases import Case
from core.models import User

PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def switches(db):
    settings_store.set_to("folder_management", True)


@pytest.fixture
def admin(db):
    return User.objects.create_local_admin("asker", PASSWORD)


@pytest.fixture
def someone(db):
    return User.objects.from_directory("colleague", display_name="A Colleague")


def test_the_start_tile_tells_an_admin_about_the_office(admin, someone):
    assert pages._cases_line(admin) == "None yet"
    Case.objects.create(owner=someone, name="Theirs")
    Case.objects.create(owner=someone, name="Theirs too")
    assert pages._cases_line(admin) == "None of yours yet; 2 cases in the office"
    assert pages._cases_line(someone) == "2 cases"
    Case.objects.create(owner=admin, name="Mine")
    assert pages._cases_line(admin) == "1 case"


def test_the_sign_out_page_says_what_stays(admin):
    lines = lifecycle.sign_out_lines(admin)
    assert "Nothing of yours is waiting here; your cases and clips stay." in lines
    assert not any("nothing here to remove" in one for one in lines)


def test_a_hit_is_cut_to_the_sentence_with_the_words():
    short = "The car was stolen. It was towed."
    assert case_search.sentence_with(short, ["stolen"]) == short
    long = " ".join(
        [
            "On the night the officers arrived at the station and spoke at "
            "length about the weather and the shift.",
            "The vehicle was not currently reported stolen at the time of the arrest.",
            "They then discussed where to tow it and who would sign the "
            "paperwork for the impound lot.",
            "Nothing else of note happened for the rest of the evening "
            "according to the report.",
        ]
    )
    assert len(long) > 240
    cut = case_search.sentence_with(long, ["stolen"])
    assert (
        cut
        == "The vehicle was not currently reported stolen at the time of the arrest."
    )
    none = case_search.sentence_with(long, ["zebra"])
    assert none.endswith("...") and len(none) <= 244


# The walk of 2026-10-02 (v1.106.0): the five shapes that broke ----------------

APP = Path(__file__).resolve().parents[1]


def test_the_five_breaks_of_the_october_walk_are_held_in_the_files():
    """v1.106.0: on a laptop the transcript had no lines in view under the
    case's list; the Panel's menu scattered under 900 wide; the Speakers
    page read one word a line at 1366; tables wrapped names letter by
    letter on a phone; the sign-in card ran off it. Each fix is a rule a
    test can read back."""
    css = (APP / "static" / "app.css").read_text(encoding="utf-8")
    viewer = (APP / "templates" / "viewer.html").read_text(encoding="utf-8")
    script = (APP / "static" / "viewer.js").read_text(encoding="utf-8")
    # 1. The case's list folds to a strip, by itself on a short window.
    assert 'id="case-fold"' in viewer and 'aria-controls="caserail"' in viewer
    assert ".stage .caserail.folded .caselist" in css
    assert "window.innerHeight < 900 || window.innerWidth < 1280" in script
    assert 'localStorage.getItem("caserail-fold")' in script
    # 2. The Panel's menu is a chip row under 900, over the whole width.
    assert ".panel-shell .rail a {" in css and "border-radius: 999px" in css
    assert ".panel-shell { display: block; }" in css
    # 3. The Speakers page's band layout from 1500 down, one column under 900.
    assert "@media (max-width: 1499px) {" in css
    assert ".sp-middle { grid-row: 3; grid-column: 1; }" in css
    # 4. Row-per-thing tables are cards under 700; tab rows scroll.
    assert ".tbl.as-cards thead { display: none; }" in css
    for name in ("cases.html", "case.html", "clips.html", "recordings.html"):
        page = (APP / "templates" / name).read_text(encoding="utf-8")
        assert 'class="tbl as-cards" id="recordings"' in page, name
    case = (APP / "templates" / "case.html").read_text(encoding="utf-8")
    assert 'class="tbl as-cards" id="incidents"' in case
    assert 'class="tbl as-cards" id="documents"' in case
    assert ".tabs { overflow-x: auto; flex-wrap: nowrap;" in css
    # 5. The sign-in card fits the page's own width.
    assert ".gate .card.with-logo { width: min(32rem, 100%); }" in css


def test_the_three_slips_of_the_server_check_are_held_in_the_stylesheet():
    """v1.106.1: seen on the server at v1.106.0. The Panel's current chip had
    no visible label (the chip's surface background came after the rail had
    set accent-ink text); the cards' separator trailed the last fact (the
    last cell is the button cell); the Speakers page in one column fitted
    the window and starved the transcript."""
    css = (APP / "static" / "app.css").read_text(encoding="utf-8")
    assert (
        ".panel-shell .rail a.on { border-color: var(--accent); "
        "background: var(--accent); color: var(--accent-ink); }"
    ) in css
    assert ':has(~ td:not(.acts):not(:empty))::after { content: " · "; }' in css
    assert "last-of-type::after" not in css
    assert "body.viewer.speakers-page { overflow: auto; }" in css
    assert ".sp-middle { min-height: 50vh; }" in css
    # v1.106.2: the page sits in the shell's row; "flex: none" on it stopped
    # it shrinking sideways. Only the desk, in the page's column, is held.
    assert ".speakers-page .sp-desk { flex: none; }" in css
    assert "main.wide, .speakers-page .sp-desk" not in css


def test_the_system_is_written_down_once_and_the_pages_keep_to_it():
    """v1.107.0, the system release of the walk: five sizes of type, four
    buttons at two sizes, one card radius, one page head, the reading pages
    capped, one empty-state pattern, one primary a page; and the Speakers
    page's two phone items folded in."""
    css = (APP / "static" / "app.css").read_text(encoding="utf-8")
    # Type: the label size joins the tokens; the stray sizes are gone.
    assert "--t-label: 11px;" in css
    assert ".eyebrow {\n  font-size: var(--t-label);" in css
    assert ".tiny { font-size: 0.78em; }" not in css
    assert ".welcome h1" not in css
    # Buttons: two sizes, tiny is small, big is the default but on the player bar.
    assert "button.small, .btn.small, button.tiny, .btn.tiny { min-height: 28px;" in css
    assert "button.big, .btn.big { min-height: 34px;" in css
    assert ".transport button.big { min-height: 40px;" in css
    assert ".record .btn.big" not in css
    assert ".done-hero button.primary" not in css
    assert "button.on, .btn.on {" in css
    # Cards: one radius.
    assert "--radius-lg: 8px;" in css
    # The page head, and the pages that take it.
    assert ".page-head { display: grid;" in css
    for name in (
        "upload.html",
        "record.html",
        "cases.html",
        "case.html",
        "clips.html",
        "recycle-bin.html",
    ):
        page = (APP / "templates" / name).read_text(encoding="utf-8")
        assert '<header class="page-head">' in page, name
        assert 'class="welcome"' not in page, name
    panel = (APP / "templates" / "panel" / "base.html").read_text(encoding="utf-8")
    assert '<span class="eyebrow">Panel</span>' in panel
    # Space: the reading pages' cap.
    assert ".page.roomy { max-width: 1400px; }" in css
    # One empty-state pattern, inside Home's sections too.
    assert ".empty.in-section {" in css
    home = (APP / "templates" / "home.html").read_text(encoding="utf-8")
    assert home.count('{% include "empty.html" with compact=True') == 3
    assert 'empty-line">Nothing uploaded' not in home
    recordings = (APP / "templates" / "recordings.html").read_text(encoding="utf-8")
    assert 'title="Nothing uploaded this session"' in recordings
    # One primary a page: the rows' buttons are secondary, the filters are lit.
    cases = (APP / "templates" / "cases.html").read_text(encoding="utf-8")
    assert cases.count('class="btn primary"') == 1 and "primary small" not in cases
    assert "{% if expiring %} on{% endif %}" in cases
    status = (APP / "templates" / "panel" / "status.html").read_text(encoding="utf-8")
    assert "primary" not in status
    reports = (APP / "templates" / "panel" / "reports.html").read_text(encoding="utf-8")
    assert "primary" not in reports.split("<table")[0]
    for name in ("case.html", "clips.html", "recordings.html"):
        page = (APP / "templates" / name).read_text(encoding="utf-8")
        assert 'class="btn primary small">Open' not in page, name
        assert 'class="btn primary small">Download' not in page, name
    # The Speakers page on a phone: the words on their own line, the lanes uncapped.
    assert ".sp-read .seg .words { grid-column: 1 / -1; }" in css
    assert ".sp-right { grid-row: 2; grid-column: 1; max-height: none; }" in css


def test_the_four_slips_of_the_system_walk_are_held_in_the_files():
    """v1.107.1: seen on the server at v1.107.0. A case's Recordings table
    crushed the name to one letter a line; the Speakers page's phone rule
    named .txt where the words sit in .words; the 1400 cap lost to an older
    1600; Recorded here said "nothing" in a plain sentence."""
    css = (APP / "static" / "app.css").read_text(encoding="utf-8")
    assert "#recordings td:first-child { min-width: 12rem; }" in css
    assert ".sp-read .seg .txt { grid-column" not in css
    assert ".page.workbench { max-width: 1400px; }" in css
    assert ".page.workbench { max-width: 100rem; }" not in css
    page = (APP / "templates" / "recorded_here.html").read_text(encoding="utf-8")
    assert 'title="Nothing recorded here yet"' in page and 'action="Record now"' in page


def test_the_recording_pages_head_is_two_lines():
    """v1.108.0, the walk's item 12: the title line and the action line,
    where one line had held eleven controls at 1366; Export shrinks to its
    icon under 1200. The cap is written in pixels, since the root is 15px."""
    css = (APP / "static" / "app.css").read_text(encoding="utf-8")
    viewer = (APP / "templates" / "viewer.html").read_text(encoding="utf-8")
    assert '<div class="head-title">' in viewer and '<div class="head-acts">' in viewer
    title_line = viewer.index('<div class="head-title">')
    assert title_line < viewer.index('id="recording-title"')
    assert viewer.index('<div class="head-acts">') < viewer.index('class="search-box"')
    assert '<span class="lbl">Export</span>' in viewer
    assert ".desk .head .head-title, .desk .head .head-acts { display: flex;" in css
    assert ".desk .head h1 { font-size: var(--t-title);" in css
    assert ".desk .head .head-acts summary .lbl { display: none; }" in css
    assert "max-width: 87.5rem" not in css


def test_the_case_pages_actions_are_gathered():
    """v1.109.0, the walk's item 10: the side column is the facts, one row of
    the case's actions (Rename, Share, Download), Shared with, then Delete
    alone at the foot. The document row keeps Re-link as a plain choice, as
    Phase 8 chapter 4 says."""
    css = (APP / "static" / "app.css").read_text(encoding="utf-8")
    page = (APP / "templates" / "case.html").read_text(encoding="utf-8")
    acts = page.index('class="row actions case-acts"')
    assert acts < page.index('id="share"') < page.index("Download all transcripts")
    assert page.index('id="rename"') < page.index('id="share"')
    assert page.index('id="shared-with"') < page.index('class="case-foot"')
    assert page.index('class="case-foot"') < page.index('id="delete-case"')
    assert ".about-case .case-foot {" in css
    assert 'class="row relink"' in page


def test_the_users_pages_row_is_two_actions_and_more():
    """v1.110.0, the walk's item 16: Block and Reassign on the row, the rest
    under More (opened in place, since the card scrolls sideways), the quota
    set in its own column. The actions keep their names, so the Admin guide's
    words hold."""
    css = (APP / "static" / "app.css").read_text(encoding="utf-8")
    page = (APP / "templates" / "panel" / "users.html").read_text(encoding="utf-8")
    more = page.index('<details class="more-acts">')
    assert page.index('value="block"') < more < page.index('value="end-sessions"')
    assert page.index('value="reassign"') < more
    for name in ("Open their Workspace", "Activity", "Access to their material"):
        assert more < page.index(f">{name}</a>")
    assert more < page.index('value="admin-flag"')
    assert more < page.index('value="delete-data"')
    assert page.index('class="row small quota-form"') < page.index('"row user-acts"')
    assert ".more-acts .menu { flex-basis: 100%;" in css
    assert ".more-acts:not([open]) .menu { display: none; }" in css
    guide = (APP.parent / "docs" / "admin-guide.md").read_text(encoding="utf-8")
    assert "the rest are under **More**" in guide


def test_the_small_placement_items_of_the_walk():
    """v1.111.0, the walk's items 13, 14, 15 and 18: Report a problem at the
    foot of the rail (no page foot, no second link on the incident page);
    the Cases filter narrows as you type and the Filter button is gone; a
    row's name is a link to the recording where the row folds open; the
    cast's tools stand apart from the count."""
    css = (APP / "static" / "app.css").read_text(encoding="utf-8")
    base = (APP / "templates" / "base.html").read_text(encoding="utf-8")
    assert 'id="report-open" class="item report"' in base
    assert "page-foot" not in base and "page-foot" not in css
    assert ".rail .item.report { margin-top: auto; }" in css
    incident = (APP / "templates" / "incident.html").read_text(encoding="utf-8")
    assert 'id="report-open"' not in incident
    cases = (APP / "templates" / "cases.html").read_text(encoding="utf-8")
    assert 'id="case-filter"' in cases and ">Filter</button>" not in cases
    script = (APP / "static" / "cases.js").read_text(encoding="utf-8")
    assert 'getElementById("case-filter")' in script and "row.hidden" in script
    for name in ("case.html", "recordings.html"):
        page = (APP / "templates" / name).read_text(encoding="utf-8")
        assert 'class="plain"><b>{{ recording.title }}</b></a>' in page, name
    assert ".tbl tr.pick a.plain { color: inherit;" in css
    viewer = (APP / "templates" / "viewer.html").read_text(encoding="utf-8")
    assert '<span class="cast-tools">' in viewer
    assert viewer.index('id="cast-count"') < viewer.index('<span class="cast-tools">')
    assert ".cast .cast-tools {" in css
    for name in ("user-guide.md", "admin-guide.md"):
        guide = (APP.parent / "docs" / name).read_text(encoding="utf-8")
        assert "at the foot of the rail" in guide, name


def test_the_three_larger_placement_items_of_the_walk():
    """v1.112.0, the walk's items 17, 19 and 20: the incident panel's tab bar
    wraps and its Find box gives way; on a phone the Upload page's drop zone
    is shorter and a step's button stays in view; on a wide window the open
    chat drawer docks as a column the page makes room for."""
    css = (APP / "static" / "app.css").read_text(encoding="utf-8")
    assert ".inc-work .tabbar { flex-wrap: wrap; }" in css
    assert ".inc-find { margin-left: auto; align-self: center; flex: 1 1 7rem;" in css
    assert ".steps > li > .dialog { position: sticky; bottom: 0;" in css
    assert "body.gideon-open .shell > main { padding-right: calc(var(--gideon" in css
    script = (APP / "static" / "gideon.js").read_text(encoding="utf-8")
    assert 'document.body.classList.add("gideon-open")' in script


def test_the_list_tables_card_class_matches_no_other_rule():
    """v1.110.0: the class that turns a list table into cards under 700 had
    matched the older `.cards` rule (a grid of cards on the document pages),
    which laid the whole table out as a grid above 700 and left the header's
    names beside the wrong columns. Found by the maintainer."""
    css = (APP / "static" / "app.css").read_text(encoding="utf-8")
    assert ".tbl.as-cards thead { display: none; }" in css
    assert ".tbl.cards" not in css
    for name in ("cases.html", "case.html", "clips.html", "recordings.html"):
        page = (APP / "templates" / name).read_text(encoding="utf-8")
        assert 'class="tbl as-cards"' in page and 'class="tbl cards"' not in page, name
