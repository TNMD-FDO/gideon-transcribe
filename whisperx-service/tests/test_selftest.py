"""The self-test's verdicts on a card (v1.84.0): a generation the stack was
run on is verified; another is a warning and never a problem; one below the
floor is a warning that says so; and the fit line follows the README's rule
of thumb."""

from service import selftest


def test_the_verified_generation_is_said_so():
    line, warning = selftest.card_verdict(12, 0)
    assert line.startswith("verified (")
    assert warning is None


def test_another_generation_is_a_warning_not_a_problem():
    line, warning = selftest.card_verdict(8, 9)
    assert line == "not yet verified on this generation"
    assert warning and "8.9" in warning and "Please report" in warning


def test_a_generation_below_the_floor_is_said_so():
    line, warning = selftest.card_verdict(7, 0)
    assert line == "not yet verified on this generation"
    assert warning and "below 7.5" in warning


def test_the_fit_line_follows_the_budget():
    # 12 GB of model, 2 GB for batch 16, 4 GB of diarizer: 18 GB wanted.
    line, warning = selftest.fit_verdict(96.0, 16)
    assert line.startswith("18 GB wanted at batch 16, 96 GB on the card")
    assert warning is None
    line, warning = selftest.fit_verdict(24.0, 16)
    assert warning is None and line.endswith("on the card")
    line, warning = selftest.fit_verdict(16.0, 16)
    assert warning and "lower WHISPERX_BATCH_SIZE" in warning
    line, warning = selftest.fit_verdict(16.0, 4)
    # 12 + 0.5 + 4 = 16.5 GB wanted: over a 16 GB card.
    assert warning is not None
    line, warning = selftest.fit_verdict(20.0, 4)
    assert warning is None and line.endswith(": tight")
