"""Language detection and the task table, checked against the contract."""

import pytest
from service.detection import (
    Window,
    combine,
    decide,
    strongest_non_english,
    window_offsets,
)


def spanish_call() -> list[Window]:
    return [
        Window(0.0, "es", 0.97),
        Window(400.0, "es", 0.95),
        Window(800.0, "es", 0.98),
    ]


def interpreted_interview() -> list[Window]:
    """Two languages, each heard confidently. This is what mixed means."""
    return [
        Window(0.0, "en", 0.88),
        Window(400.0, "es", 0.72),
        Window(800.0, "en", 0.66),
    ]


# The windows -----------------------------------------------------------------


def test_a_long_file_gets_three_windows_spread_through_it():
    assert window_offsets(1800.0) == [0.0, 600.0, 1200.0]


def test_the_windows_never_overlap_at_ninety_seconds():
    offsets = window_offsets(90.0)
    assert offsets == [0.0, 30.0, 60.0]


def test_a_short_file_gets_as_many_windows_as_fit():
    assert window_offsets(75.0) == [0.0, 30.0]


def test_a_very_short_file_still_gets_one_window():
    assert window_offsets(4.0) == [0.0]


# Reading the windows together ------------------------------------------------


def test_windows_that_agree_give_that_language_and_its_probability():
    detection = combine(spanish_call())
    assert detection.detected == "es"
    assert detection.mixed is False
    assert detection.probability == pytest.approx(0.9666, abs=0.001)


def test_two_confident_languages_are_mixed():
    detection = combine(interpreted_interview())
    assert detection.mixed is True


def test_a_second_language_heard_faintly_is_not_mixed():
    windows = [
        Window(0.0, "es", 0.95),
        Window(400.0, "en", 0.31),
        Window(800.0, "es", 0.92),
    ]
    detection = combine(windows)
    assert detection.mixed is False
    assert detection.detected == "es"


def test_the_winner_is_the_language_with_the_highest_total():
    detection = combine(interpreted_interview())
    assert detection.detected == "en"
    assert detection.combined["en"] == pytest.approx((0.88 + 0.66) / 3)
    assert detection.combined["es"] == pytest.approx(0.72 / 3)


def test_a_combined_figure_never_passes_one():
    detection = combine(spanish_call())
    assert all(0.0 <= total <= 1.0 for total in detection.combined.values())


def test_detection_needs_a_window():
    with pytest.raises(ValueError, match="at least one window"):
        combine([])


def test_the_strongest_other_language_is_what_whisper_is_told():
    assert strongest_non_english(combine(interpreted_interview())) == "es"


def test_an_english_only_file_falls_back_to_english():
    windows = [Window(0.0, "en", 0.99)]
    assert strongest_non_english(combine(windows)) == "en"


# The task table --------------------------------------------------------------


def test_transcribe_with_a_language_named_does_not_detect():
    decision = decide("transcribe", "es", False, None)
    assert (decision.task_run, decision.task_reason, decision.language) == (
        "transcribe",
        "requested",
        "es",
    )


def test_transcribe_with_nothing_named_transcribes_what_was_heard():
    decision = decide("transcribe", None, False, combine(spanish_call()))
    assert (decision.task_run, decision.task_reason, decision.language) == (
        "transcribe",
        "requested",
        "es",
    )


def test_a_mixed_file_is_translated_when_the_office_setting_is_on():
    decision = decide("transcribe", None, True, combine(interpreted_interview()))
    assert (decision.task_run, decision.task_reason, decision.language) == (
        "translate",
        "mixed_detected",
        "es",
    )


def test_a_mixed_file_is_only_transcribed_when_the_setting_is_off():
    decision = decide("transcribe", None, False, combine(interpreted_interview()))
    assert (decision.task_run, decision.task_reason) == ("transcribe", "requested")


def test_translate_with_a_language_named_translates_from_it():
    decision = decide("translate", "es", False, None)
    assert (decision.task_run, decision.task_reason, decision.language) == (
        "translate",
        "requested",
        "es",
    )


def test_translate_with_nothing_named_tells_whisper_the_other_language():
    decision = decide("translate", None, False, combine(interpreted_interview()))
    assert (decision.task_run, decision.language) == ("translate", "es")


def test_translate_if_needed_with_english_named_just_transcribes():
    decision = decide("translate_if_needed", "en", False, None)
    assert (decision.task_run, decision.task_reason) == ("transcribe", "requested")


def test_translate_if_needed_with_another_language_named_translates():
    decision = decide("translate_if_needed", "es", False, None)
    assert (decision.task_run, decision.task_reason) == ("translate", "requested")


def test_translate_if_needed_transcribes_when_english_was_heard():
    windows = [Window(0.0, "en", 0.99), Window(400.0, "en", 0.98)]
    decision = decide("translate_if_needed", None, False, combine(windows))
    assert (decision.task_run, decision.task_reason) == (
        "transcribe",
        "english_detected",
    )


def test_translate_if_needed_translates_when_another_language_was_heard():
    decision = decide("translate_if_needed", None, False, combine(spanish_call()))
    assert (decision.task_run, decision.task_reason) == ("translate", "requested")


def test_translate_if_needed_translates_a_mixed_file_even_when_english_won():
    """Settled with the maintainer on 2026-09-03.

    The winner here is English, but the file holds Spanish too. The point of
    this task is English out, and under translate the English half passes
    through untouched, so the whole file is translated.
    """
    detection = combine(interpreted_interview())
    assert detection.detected == "en"
    decision = decide("translate_if_needed", None, False, detection)
    assert (decision.task_run, decision.task_reason, decision.language) == (
        "translate",
        "mixed_detected",
        "es",
    )


def test_an_unknown_task_is_refused():
    with pytest.raises(ValueError, match="unknown task"):
        decide("summarise", None, False, None)


def test_detection_is_required_when_no_language_was_named():
    with pytest.raises(ValueError, match="detection is needed"):
        decide("transcribe", None, False, None)
