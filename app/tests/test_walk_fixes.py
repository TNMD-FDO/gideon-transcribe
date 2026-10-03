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
    assert ".tbl.cards thead { display: none; }" in css
    for name in ("cases.html", "case.html", "clips.html", "recordings.html"):
        page = (APP / "templates" / name).read_text(encoding="utf-8")
        assert 'class="tbl cards" id="recordings"' in page, name
    case = (APP / "templates" / "case.html").read_text(encoding="utf-8")
    assert 'class="tbl cards" id="incidents"' in case
    assert 'class="tbl cards" id="documents"' in case
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
    assert ".page.roomy { max-width: 87.5rem; }" in css
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
    assert ".sp-read .seg .txt { grid-column: 1 / -1; }" in css
    assert ".sp-right { grid-row: 2; grid-column: 1; max-height: none; }" in css
