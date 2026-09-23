"""The event's line and the merge hint's rule (Phase 8 chapter 8), the parts
that need no database: the text read as a line and a detail, and a
fragment's neighbour."""

from __future__ import annotations

from core import chronology, speakers_page
from core.speakers_page import Line


def test_a_short_text_is_the_line_alone():
    assert chronology.line_and_detail("Vehicle stopped.") == ("Vehicle stopped.", "")
    assert chronology.line_and_detail("  ") == ("", "")


def test_a_line_break_ends_the_line():
    line, detail = chronology.line_and_detail(
        "Vehicle stopped\nby the kerb,\nengine on"
    )
    assert line == "Vehicle stopped"
    assert detail == "by the kerb, engine on"


def test_a_long_text_is_cut_at_its_first_sentence():
    text = (
        "The officer asked for the registration; the driver said it was in the "
        "glove box. The officer told him to keep his hands where they could be seen."
    )
    line, detail = chronology.line_and_detail(text)
    assert line == "The officer asked for the registration;"
    assert detail.startswith("the driver said")
    # Under 120 characters the sentence rule does not apply.
    short = "One. Two. Three."
    assert chronology.line_and_detail(short) == (short, "")


def test_an_abbreviation_or_an_initial_does_not_end_the_line():
    text = (
        "Sgt. Hale and J. Smith spoke with Mr. Reyes at No. 12 about the car for "
        "a while before the search began. Then the dog was brought out of the unit."
    )
    line, detail = chronology.line_and_detail(text)
    assert line.endswith("before the search began.")
    assert detail == "Then the dog was brought out of the unit."


def test_a_line_still_too_long_is_cut_at_a_word_and_the_detail_is_the_whole():
    text = " ".join(["word"] * 60)  # 299 characters, no sentence end
    line, detail = chronology.line_and_detail(text)
    assert line.endswith("…") and len(line) <= chronology.LINE_CUT + 1
    assert detail == text


# The merge hint ---------------------------------------------------------------


def test_a_fragment_inside_anothers_turns_names_the_neighbour():
    officer = [Line(0, 10), Line(12, 20), Line(23, 30)]
    driver = [Line(40, 45)]
    fragment = [Line(10.5, 11.5), Line(20.5, 22)]
    assert (
        speakers_page.neighbour_of(fragment, {"Officer": officer, "Driver": driver})
        == "Officer"
    )


def test_a_fragment_far_from_everyone_has_no_neighbour():
    officer = [Line(0, 10), Line(30, 40)]
    fragment = [Line(15, 16), Line(20, 21)]
    assert speakers_page.neighbour_of(fragment, {"Officer": officer}) == ""


def test_more_than_half_of_the_lines_must_sit_inside_one_speakers_turns():
    officer = [Line(0, 10)]
    driver = [Line(30, 40)]
    fragment = [Line(10.5, 11), Line(40.5, 41)]
    assert (
        speakers_page.neighbour_of(fragment, {"Officer": officer, "Driver": driver})
        == ""
    )
    fragment = [Line(10.5, 11), Line(40.5, 41), Line(41.5, 42)]
    assert (
        speakers_page.neighbour_of(fragment, {"Officer": officer, "Driver": driver})
        == "Driver"
    )


def test_a_tie_on_a_line_goes_to_the_speaker_with_more_lines():
    officer = [Line(0, 10), Line(12, 14), Line(16, 18)]
    driver = [Line(11, 11.5)]
    # 10.5 sits one half second after the officer and one half second before
    # the driver: the officer, who has more lines, is its neighbour.
    fragment = [Line(10.5, 10.5)]
    assert (
        speakers_page.neighbour_of(fragment, {"Officer": officer, "Driver": driver})
        == "Officer"
    )
