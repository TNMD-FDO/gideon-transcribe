"""v1.75.1: the fix release from the walk of 2026-09-22, the parts a test
can hold: the Start tile's line for an Admin who owns nothing, the
sign-out page's line, a Search hit cut to the sentence with the words,
and nothing that needs a recording (the Report tab's switch is in
test_documents_read)."""

from __future__ import annotations

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
