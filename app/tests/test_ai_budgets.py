"""v1.37.0: the AI assistant's budgets are settings, with their code values as defaults.

The rules checked here: every budget setting's default is the figure the
code kept as its constant, so nothing moved by becoming a setting; the
assistant reads the settings at every call (a cap, a time limit, the
thinking allowance, the Case Chat's sizes); the prompt helpers take the
budget they are handed and fall back to the chapter's values; the AI
assistant page shows each budget with its default and a Reset to default,
and the page-wide reset; the catalogue names every one.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from core import assistant, case_chat, prompts, settings_store
from core.models import LoginSession, User
from django.urls import reverse

PASSWORD = "a-long-enough-password"
CATALOGUE = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "spec"
    / "ADMIN-SETTINGS-CATALOGUE.md"
)

# Each setting and the constant it took its default from.
PAIRS = {
    "chat_answer_tokens": prompts.CHAT_CAP,
    "summary_short_tokens": prompts.ANSWER_CAPS["short"],
    "summary_standard_tokens": prompts.ANSWER_CAPS["standard"],
    "summary_detailed_tokens": prompts.ANSWER_CAPS["detailed"],
    "suggestions_answer_tokens": prompts.SUGGESTIONS_CAP,
    "thinking_allowance_tokens": assistant.THINKING_ALLOWANCE,
    "chat_time_seconds": assistant.TIME_LIMITS["chat_turn"],
    "summary_time_seconds": assistant.TIME_LIMITS["summary"],
    "suggestions_time_seconds": assistant.TIME_LIMITS["speaker_suggestions"],
    "chat_history_tokens": prompts.HISTORY_TOKENS,
    "engine_window_tokens": prompts.ENGINE_WINDOW,
    "reading_tokens": case_chat.READING_TOKENS,
    "readings_at_once": case_chat.READINGS_AT_ONCE,
    "case_chat_part_tokens": case_chat.PART_CAP,
    "case_chat_combined_tokens": case_chat.COMBINED_CAP,
    "case_chat_question_minutes": case_chat.QUESTION_LIMIT // 60,
}


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


# The definitions ----------------------------------------------------------------------


def test_every_budget_starts_at_the_code_value():
    for key, constant in PAIRS.items():
        known = settings_store.DEFINITIONS[key]
        assert known.page == settings_store.ASSISTANT, key
        assert known.kind == settings_store.NUMBER, key
        assert known.default == constant, (key, known.default, constant)
        assert known.least <= known.default <= known.most, key


def test_the_thinking_allowance_is_greyed_while_thinking_is_off():
    assert settings_store.DEFINITIONS["thinking_allowance_tokens"].needs == (
        "assistant_thinks"
    )


def test_the_catalogue_names_every_budget():
    text = CATALOGUE.read_text(encoding="utf-8")
    for name in (
        "Chat answer cap",
        "Summary answer cap, Short; Standard; Detailed",
        "Speaker suggestions answer cap",
        "Thinking allowance",
        "Chat time limit; Summary time limit; Speaker suggestions time limit",
        "Chat history",
        "Engine window",
        "Reading size",
        "Readings at once",
        "Case chat answer cap, each part; combined",
        "Case chat question time limit",
    ):
        assert f"| {name} |" in text, f"the catalogue has no row for {name}"


# The helpers take the budget they are handed ------------------------------------------


def test_fits_and_history_take_the_budget_handed_or_the_chapters_value():
    assert prompts.fits("a" * 4000, answer_cap=100)
    assert not prompts.fits("a" * 4000, answer_cap=100, window=1000)
    assert not prompts.fits("a" * (prompts.ENGINE_WINDOW * 4), answer_cap=100)
    turns = [("q1", "a" * 100), ("q2", "b" * 100), ("q3", "c" * 40)]
    assert prompts.history_that_fits(turns) == turns
    assert prompts.history_that_fits(turns, 60) == turns[1:]
    assert prompts.history_that_fits(turns, 0) == []


def test_pack_takes_the_reading_size_handed_or_the_chapters_value():
    small = "y" * 400
    assert case_chat.pack([(1, small), (2, small), (3, small)]) == [[1, 2, 3]]
    assert case_chat.pack([(1, small), (2, small), (3, small)], 200) == [
        [1],
        [2],
        [3],
    ]


# The assistant reads them at every call ------------------------------------------


@pytest.mark.django_db
def test_the_assistant_reads_the_settings_at_every_call():
    assert assistant.time_limit("chat_turn") == 120
    assert assistant.cap(1500) == 1500
    assert assistant.window() == 131072
    assert settings_store.summary_answer_cap("detailed") == 2500
    assert settings_store.summary_answer_cap("nonsense") == 1200
    assert case_chat.time_limit_for_the_question() == 15 * 60

    settings_store.set_to("chat_time_seconds", 45)
    settings_store.set_to("assistant_thinks", True)
    settings_store.set_to("thinking_allowance_tokens", 20000)
    settings_store.set_to("engine_window_tokens", 262144)
    settings_store.set_to("summary_detailed_tokens", 4000)
    settings_store.set_to("case_chat_question_minutes", 30)
    assert assistant.time_limit("chat_turn") == 90
    assert assistant.cap(1500) == 21500
    assert assistant.window() == 262144
    assert settings_store.summary_answer_cap("detailed") == 4000
    assert case_chat.time_limit_for_the_question() == 60 * 60

    settings_store.set_to("assistant_thinks", False)
    assert assistant.cap(1500) == 1500
    assert assistant.time_limit("chat_turn") == 45


@pytest.mark.django_db
def test_a_budget_outside_its_range_is_refused():
    with pytest.raises(ValueError):
        settings_store.set_to("readings_at_once", 9)
    with pytest.raises(ValueError):
        settings_store.set_to("engine_window_tokens", 100)
    assert settings_store.readings_at_once() == 2


# The page -----------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_page_shows_each_budget_with_its_default_and_a_reset(client):
    admin = User.objects.create_local_admin("admin", PASSWORD)
    signed_in(client, admin)
    settings_store.set_to("chat_answer_tokens", 900)
    page = client.get(
        reverse("panel-settings", args=[settings_store.ASSISTANT])
    ).content.decode()
    assert 'id="chat_answer_tokens"' in page and 'data-default="1500"' in page
    assert "Default: 1500 tokens" in page
    # Reset beside the field: shown for the changed one, hidden for the rest.
    assert (
        '<button type="button" class="ghost small reset-to-default" '
        'data-for="chat_answer_tokens">Reset to default</button>'
    ) in page
    assert ('data-for="summary_short_tokens" hidden>Reset to default</button>') in page
    assert 'id="reset-page"' in page and "Reset every number on this page" in page
    # The thinking allowance is greyed while thinking is off, and says why.
    assert 'id="thinking_allowance_tokens"' in page
    assert "disabled" in page.split('id="thinking_allowance_tokens"')[1].split(">")[0]


@pytest.mark.django_db
def test_every_number_on_every_page_offers_reset(client):
    admin = User.objects.create_local_admin("admin", PASSWORD)
    signed_in(client, admin)
    page = client.get(
        reverse("panel-settings", args=[settings_store.LIMITS])
    ).content.decode()
    assert 'data-for="files_per_batch"' in page
    assert page.count("reset-to-default") >= 5
