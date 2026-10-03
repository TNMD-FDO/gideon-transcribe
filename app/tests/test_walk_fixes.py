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
