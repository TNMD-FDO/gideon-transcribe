"""The time expectation a written output is given (v1.95.0): the guess before
the office has history, the pace read from the office's own audit rows and
scaled to what this run is given, the words, and what the page is sent."""

from __future__ import annotations

import pytest
from core import audit, expectation, settings_store


def a_run(feature, seconds, tokens, *, ok=True, thinking=False, **more):
    audit.write(
        audit.Category.LLM,
        "AI assistant call",
        system="worker",
        outcome=audit.Outcome.SUCCESS if ok else audit.Outcome.FAILURE,
        object_type="incident",
        object_id="x",
        feature=feature,
        duration_seconds=seconds,
        input_tokens=tokens * 2,
        output_tokens=100,
        size_tokens=tokens,
        thinking=thinking,
        **more,
    )


def test_before_history_the_figure_is_the_guess_worded_roughly(db):
    assert expectation.pace("incident_memo") is None
    seconds, measured = expectation.expect("incident_memo", 50_000)
    assert (seconds, measured) == (300, False)
    assert expectation.words(seconds, measured) == "roughly 5 minutes"
    assert expectation.words(20, False, fine=True) == "roughly 20 seconds"
    assert expectation.words(45, False) == "under a minute"


def test_three_runs_make_the_pace_and_it_scales_with_the_size(db):
    for seconds, tokens in ((60, 10_000), (120, 20_000), (90, 15_000)):
        a_run("incident_memo", seconds, tokens)
    assert expectation.pace("incident_memo") == pytest.approx(0.006)
    seconds, measured = expectation.expect("incident_memo", 50_000)
    assert measured and seconds == 300
    seconds, measured = expectation.expect("incident_memo", 100_000)
    assert measured and seconds == 600
    assert expectation.words(seconds, measured) == "usually about 10 minutes"
    assert expectation.words(30, True) == "usually under a minute"
    assert expectation.words(12, True, fine=True) == "usually about 15 seconds"


def test_failures_other_outputs_and_rows_without_a_size_do_not_count(db):
    a_run("incident_memo", 600, 10_000, ok=False)
    a_run("incident_events", 600, 10_000)
    a_run("incident_memo", 60, 10_000)
    a_run("incident_memo", 60, 10_000)
    audit.write(
        audit.Category.LLM,
        "AI assistant call",
        system="worker",
        object_type="incident",
        object_id="x",
        feature="incident_memo",
        duration_seconds=600,
        input_tokens=10_000,
    )
    assert expectation.pace("incident_memo") is None
    a_run("incident_memo", 60, 10_000)
    assert expectation.pace("incident_memo") == pytest.approx(0.006)


def test_the_rewrite_and_the_full_write_are_read_apart(db):
    for _ in range(3):
        a_run("incident_memo", 300, 10_000)
        a_run("incident_memo", 30, 5_000, from_sheet=True)
    assert expectation.pace("incident_memo") == pytest.approx(0.03)
    assert expectation.pace("incident_memo_rewrite") == pytest.approx(0.006)


def test_only_the_last_twenty_rows_are_read(db):
    for _ in range(5):
        a_run("summary", 1000, 1_000)
    for _ in range(20):
        a_run("summary", 10, 1_000)
    assert expectation.pace("summary") == pytest.approx(0.01)


def test_rows_made_while_thinking_are_read_apart_when_there_are_enough(db):
    for _ in range(3):
        a_run("summary", 10, 1_000, thinking=False)
    for _ in range(3):
        a_run("summary", 100, 1_000, thinking=True)
    assert expectation.pace("summary") == pytest.approx(0.01)
    settings_store.set_to("assistant_thinks", True)
    assert expectation.pace("summary") == pytest.approx(0.1)


def test_the_figure_is_clamped_to_what_the_run_may_take(db):
    for _ in range(3):
        a_run("chat_turn", 100, 100)  # a second a token: absurd
    seconds, measured = expectation.expect("chat_turn", 100_000)
    assert measured
    assert seconds == settings_store.time_limit_seconds("chat_turn")


def test_what_the_run_keeps_and_what_the_page_is_sent(db):
    stored = expectation.note("incident_memo", 40_000)
    assert stored["key"] == "incident_memo" and stored["tokens"] == 40_000
    assert stored["seconds"] == 300 and stored["measured"] is False
    assert stored["asked_at"] and stored["started_at"] == ""
    assert expectation.json_of(stored, "done") == {}
    told = expectation.json_of(stored, "queued", "memo")
    assert told["expected_seconds"] == 300 and told["measured"] is False
    assert told["words"] == "roughly 5 minutes"
    assert told["leave_words"] == (
        "You can leave this page; the memo will be here when it lands."
    )
    assert told["over_words"] == (
        "Still writing, and working normally. The figure was a guess until your "
        "office has a few of these behind it; it will be here when it lands."
    )
    stamped = expectation.started(stored)
    assert stamped["started_at"] and stored["started_at"] == ""
    running = expectation.json_of(stamped, "running", "memo")
    assert running["started_at"] == stamped["started_at"]
    assert expectation.for_audit(stamped) == {
        "size_tokens": 40_000,
        "expected_seconds": 300,
        "thinking": False,
    }
    assert expectation.for_audit({}) == {}


def test_the_glossary_and_the_guide_carry_the_words():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent.parent
    glossary = (root / "CONTEXT.md").read_text(encoding="utf-8")
    guide = (root / "docs" / "user-guide.md").read_text(encoding="utf-8")
    assert "**Expectation**:" in glossary
    assert '"usually about 4 minutes" once the office has three runs' in glossary
    assert (
        "how long a question like this usually takes on your office's engine" in guide
    )
    assert "the tab says which pass it is on" in guide
    assert "the line by the button says which window of pages it is on" in guide
    assert "while it is written the row says how long that usually takes" in guide


def test_a_look_for_run_has_its_own_figure(db):
    """v1.96.0: a Look for run's rows and a full run's are read apart, as
    the rewrite's are from the memo's."""
    assert expectation.expect("incident_look_for", 10_000) == (90, False)
    for _ in range(3):
        a_run("incident_events", 50, 10_000, looked=True)
    assert expectation.expect("incident_look_for", 10_000) == (60, True)
    assert expectation.expect("incident_events", 10_000) == (180, False)


def test_the_look_for_run_is_in_the_glossary_and_the_guide():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent.parent
    glossary = (root / "CONTEXT.md").read_text(encoding="utf-8")
    guide = (root / "docs" / "user-guide.md").read_text(encoding="utf-8")
    assert "**Look for**:" in glossary
    assert "proposes only the moments that bear on what was typed" in glossary
    assert "the button reads **Look for it**" in guide
    assert "**Dismiss all** puts them all away after asking once" in guide


def test_the_reassurance_names_what_the_engine_was_given(db):
    assert expectation.over_words(True, "memo").startswith(
        "Still writing, and working normally. A memo this size gives the engine "
        "a great deal to read, so it can run past the usual time;"
    )
    assert "A report this size" in expectation.over_words(True, "comparison")
    assert "An incident this size" in expectation.over_words(True, "proposals")
    assert "A recording this size" in expectation.over_words(True, "summary")
    assert expectation.over_words(True, "chat") == "Still working on it."
    assert expectation.leave_words("chat") == ""
    assert expectation.leave_words("comparison") == (
        "You can leave this page; the comparison will be here when it lands."
    )
    for kind in ("memo", "proposals", "comparison", "summary", "dictation", "chat"):
        said = (expectation.over_words(True, kind), expectation.leave_words(kind))
        assert all(chr(8212) not in words for words in said)
