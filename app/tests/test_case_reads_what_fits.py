"""Gideon reads what fits (Phase 9 chapter 6, ADR 0018).

The rules checked here: the scope the page posts is kept honest (a kind the
chapter names and ids in this case, nothing else) and a narrowed question
reads those recordings alone and says so; the route is one rule (whole or
narrowed within the ceiling, the overviews first over it when any recording
has a Summary, the refusal only when none has); pass one sends one line per
recording and its Overview cut to a budget under a schema, without thinking,
and pass two reads the recordings pointed to whole, in upload order, as many
as fill the allowed Readings, with the answer's first line saying what was
read; a selection that names nothing answers so; the turn keeps the route,
the scope and the selection, the audit row carries the counts and never a
word, the export says what each question read, and the settings and the
template exist.
"""

from __future__ import annotations

import json

import pytest
from core import (
    assistant,
    case_chat,
    case_scope,
    engine,
    prompts,
    settings_store,
    tasks,
)
from core.assistant import DONE, PromptTemplate, Summary
from core.audit import Row
from core.case_chat import CaseChat, CaseChatTurn
from core.cases import Case
from core.models import LoginSession, User
from tests.test_case_chat import a_recording

PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"


@pytest.fixture
def owner(db):
    return User.objects.create_local_admin("case-owner", PASSWORD)


@pytest.fixture
def a_case(owner):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("assistant_available", True)
    return Case.objects.create(owner=owner, name="Pike calls")


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def summarised(recording, overview: str):
    return Summary.objects.create(
        recording=recording,
        state=DONE,
        template_name="Jail call summary",
        transcript_created=recording.transcript.created,
        text=f"Overview:\n{overview}\n\nWhat is discussed:\nThe rest.",
    )


def engine_answering(monkeypatch, answers):
    """An engine that is up: each call takes the next answer, and the calls
    are kept with their options."""
    monkeypatch.setattr(engine, "is_reachable", lambda: True)
    monkeypatch.setattr(engine, "address", lambda: "http://gideon-generator:8000/v1")
    asked = []
    queue = list(answers)

    def complete(messages, **options):
        asked.append({"messages": messages, **options})
        return {
            "text": queue.pop(0) if len(queue) > 1 else queue[0],
            "finish_reason": "stop",
            "input_tokens": 100,
            "output_tokens": 10,
            "model": "the-model",
        }

    monkeypatch.setattr(engine, "complete", complete)
    return asked


def a_turn(a_case, owner, question="Who mentioned the storage unit?", scope=None):
    chat = CaseChat.objects.create(case=a_case, asked_by=owner)
    return CaseChatTurn.objects.create(
        chat=chat, number=1, question=question, scope=scope or {}
    )


# Without an engine -------------------------------------------------------------------


def test_the_settings_and_the_template_exist():
    known = settings_store.DEFINITIONS
    assert known["case_chat_hours"].name == (
        "Case chat: hours of talk read whole per question"
    )
    picks = known["case_chat_picks_most"]
    assert (picks.default, picks.least, picks.most) == (30, 5, 60)
    after = known["case_chat_readings_after"]
    assert (after.default, after.least, after.most) == (1, 1, 4)
    assert PromptTemplate.DEFAULTS["case_chat_select"] == (
        "Case chat: which recordings",
        prompts.CASE_CHAT_SELECT,
    )
    assert "also heard as" in prompts.CASE_CHAT_SELECT
    assert "prompt:case_chat_select" in prompts.SHIPPED_HISTORY


def test_an_overview_is_cut_at_a_sentence_end_to_its_budget():
    long = "The first sentence is here. The second one follows it. " * 40
    cut = case_scope.cut_overview(long, 20)
    assert cut.endswith(".") and prompts.tokens(cut) <= 30
    assert case_scope.cut_overview("Short.", 20) == "Short."
    assert case_scope.cut_overview("", 20) == ""


def test_the_picks_that_fit_are_taken_in_relevance_order_then_put_in_upload_order():
    class One:
        def __init__(self, pk, size):
            self.pk, self.size, self.created = pk, size, pk

    picks = [
        {"recording": One(n, size), "why": ""}
        for n, size in enumerate((40, 70, 30, 10))
    ]
    kept = case_scope.fitting(picks, lambda one: one.size, 100, 1)
    # 40 fits; 70 would not join it; 30 does; 10 does not (40 + 30 + 10 > 100
    # by the estimate's margin is false, so it does). One Reading of 100.
    assert [one["recording"].pk for one in kept] == [0, 2, 3]
    # Two Readings: 40 and 70 apart, 30 would make a third, 10 joins the 70.
    two = case_scope.fitting(picks, lambda one: one.size, 100, 2)
    assert [one["recording"].pk for one in two] == [0, 1, 3]
    # One too big for a Reading alone is passed over.
    big = [{"recording": One(9, 500), "why": ""}] + picks
    assert [
        one["recording"].pk
        for one in case_scope.fitting(big, lambda one: one.size, 100, 1)
    ] == [0, 2, 3]


# The scope and the routes ---------------------------------------------------------


@pytest.mark.django_db
def test_the_scope_posted_is_kept_honest(owner, a_case):
    first = a_recording(owner, a_case, "Call 1")
    other = Case.objects.create(owner=owner, name="Other")
    elsewhere = a_recording(owner, other, "Elsewhere")
    assert case_scope.scope_of(a_case, None) == {
        "kind": "all",
        "recordings": [],
        "dropped": 0,
    }
    assert (
        case_scope.scope_of(a_case, {"kind": "picker", "recordings": [str(first.pk)]})[
            "kind"
        ]
        == "all"
    )
    kept = case_scope.scope_of(
        a_case,
        {"kind": "filter", "recordings": [str(first.pk), str(elsewhere.pk), "junk"]},
    )
    assert kept == {"kind": "filter", "recordings": [str(first.pk)], "dropped": 2}
    assert (
        case_scope.scope_of(a_case, {"kind": "search", "recordings": ["junk"]})["kind"]
        == "all"
    )


@pytest.mark.django_db
def test_the_route_is_one_rule(owner, a_case):
    first = a_recording(owner, a_case, "Call 1", hours=4)
    second = a_recording(owner, a_case, "Call 2", hours=4)
    read = [first, second]
    assert case_scope.route_for(read, {}) == case_scope.WHOLE
    assert (
        case_scope.route_for(
            read, {}, {"kind": "filter", "recordings": [str(first.pk)]}
        )
        == case_scope.NARROWED
    )
    settings_store.set_to("case_chat_hours", 6)
    assert case_scope.route_for(read, {}) == case_scope.DIGEST
    assert (
        case_scope.route_for(read, {first.pk: "An overview."}) == case_scope.OVERVIEWS
    )


@pytest.mark.django_db
def test_a_narrowed_question_reads_those_recordings_alone_and_says_so(
    owner, a_case, client, monkeypatch
):
    first = a_recording(owner, a_case, "Call 1")
    a_recording(owner, a_case, "Call 2")
    asked = engine_answering(monkeypatch, ["Nobody did [Recording 1, 00:12:45]."])
    monkeypatch.setattr(tasks.answer_case_turn, "defer", lambda **f: None)
    signed_in(client, owner)
    chat_id = client.post(f"/case/{a_case.pk}/chats").json()["id"]
    told = client.post(
        f"/case-chat/{chat_id}/ask",
        data=json.dumps(
            {
                "question": "Who?",
                "scope": {"kind": "filter", "recordings": [str(first.pk), "junk"]},
            }
        ),
        content_type="application/json",
    )
    turn = CaseChatTurn.objects.get(pk=told.json()["id"])
    assert turn.scope == {"kind": "filter", "recordings": [str(first.pk)], "dropped": 1}
    assert turn.expectation["key"] == "case_chat_turn"
    case_chat.answer_case_turn(turn.pk)
    turn.refresh_from_db()
    assert turn.state == "done" and turn.route == case_scope.NARROWED
    user = asked[0]["messages"][-1]["content"]
    assert "Recording 1 of 1: Call 1" in user and "Call 2" not in user
    assert turn.answer.startswith("Read the 1 recording narrowed to on the page.")
    assert [one["title"] for one in turn.readings] == ["Call 1"]
    state = client.get(f"/case/{a_case.pk}/chat").json()
    drawn = state["chats"][0]["turns"][0]
    assert drawn["route"] == "narrowed"
    assert (
        drawn["read_words"]
        == "Asked of the 1 recordings narrowed to on the recordings list."
    )
    assert state["head"] == "This case" and state["over"] is False
    row = Row.objects.get(category="llm", event="AI assistant call")
    assert row.details["route"] == "narrowed" and row.details["scope_kind"] == "filter"
    assert (
        row.details["scope_count"] == 1 and row.details["feature"] == "case_chat_turn"
    )
    assert "Who" not in json.dumps(row.details)


# Over the ceiling: the two passes --------------------------------------------------


@pytest.mark.django_db
def test_over_the_ceiling_the_overviews_are_read_first_then_the_picks_whole(
    owner, a_case, client, monkeypatch
):
    settings_store.set_to("case_chat_hours", 6)
    calls = [a_recording(owner, a_case, f"Call {n}", hours=2) for n in range(1, 6)]
    summarised(calls[0], "Pike asks about the storage unit on Elm Street.")
    summarised(calls[2], "Small talk about the weather and a visit.")
    summarised(calls[3], "The caller says the storage unit was emptied.")
    selection = json.dumps(
        {
            "picks": [
                {"recording": 4, "why": "the unit was emptied"},
                {"recording": 1, "why": "asks about the unit"},
                {"recording": 9, "why": "not a recording"},
                {"recording": 4, "why": "again"},
            ],
            "none": False,
            "note": "",
        }
    )
    asked = engine_answering(
        monkeypatch,
        [selection, "It was emptied [Recording 2, 00:12:45]."],
    )
    monkeypatch.setattr(tasks.answer_case_turn, "defer", lambda **f: None)
    signed_in(client, owner)
    chat_id = client.post(f"/case/{a_case.pk}/chats").json()["id"]
    state = client.get(f"/case/{a_case.pk}/chat").json()
    assert (
        state["over"] is True and state["summarised"] == 3 and state["no_summary"] == 2
    )
    assert (
        state["head"] == "Reads the overviews first, then the recordings they point to"
    )
    told = client.post(
        f"/case-chat/{chat_id}/ask",
        data=json.dumps({"question": "Who mentioned the storage unit?"}),
        content_type="application/json",
    )
    turn = CaseChatTurn.objects.get(pk=told.json()["id"])
    assert turn.expectation["key"] == "case_chat_two_pass"
    case_chat.answer_case_turn(turn.pk)
    turn.refresh_from_db()
    assert turn.state == "done", turn.reason_detail
    assert turn.route == case_scope.OVERVIEWS
    # Pass one: one line per recording with its overview, under the schema,
    # without thinking, with the facts sheet's sampling.
    first = asked[0]
    assert first["schema"]["properties"]["picks"]["maxItems"] == 30
    assert first["thinking"] is False and first["temperature"] == 0.0
    assert prompts.CASE_CHAT_SELECT in first["messages"][0]["content"]
    user = first["messages"][-1]["content"]
    assert "The 5 recordings of this case, numbered." in user
    assert "1. Call 1, Jail call" in user and "storage unit on Elm Street" in user
    assert "2. Call 2, Jail call" in user and "(no summary yet)" in user
    assert user.rstrip().endswith("The question: Who mentioned the storage unit?")
    # Pass two: the picks whole, in upload order, numbered among themselves.
    second = asked[1]["messages"][-1]["content"]
    assert "Recording 1 of 2: Call 1" in second and "Recording 2 of 2: Call 4" in second
    assert "Call 3" not in second and "Call 2," not in second
    assert turn.selection["pointed_to"] == 2 and turn.selection["read_whole"] == 2
    assert turn.selection["overviews_read"] == 3 and turn.selection["no_summary"] == 2
    assert [one["title"] for one in turn.selection["picks"]] == ["Call 4", "Call 1"]
    assert turn.answer.startswith(
        "Read the overviews of 3 recordings, then 2 whole. 2 recordings have no "
        "summary yet and were not read; the case page offers to write the "
        "missing summaries tonight."
    )
    assert turn.citations["[Recording 2, 00:12:45]"]["recording"] == str(calls[3].pk)
    assert [one["title"] for one in turn.readings] == ["Call 1", "Call 4"]
    row = Row.objects.get(category="llm", event="AI assistant call")
    assert row.details["feature"] == "case_chat_two_pass"
    assert row.details["route"] == "overviews" and row.details["selections"] == 1
    assert row.details["overviews_read"] == 3 and row.details["pointed_to"] == 2
    assert row.details["read_whole"] == 2 and row.details["no_summary"] == 2
    assert "case-chat-select v1" in row.details["templates"]
    details = json.dumps(row.details)
    assert "storage" not in details and "emptied" not in details
    drawn = client.get(f"/case/{a_case.pk}/chat").json()["chats"][0]["turns"][0]
    assert drawn["read_words"] == (
        "Asked over the overviews of 3 recordings, then 2 read whole."
    )


@pytest.mark.django_db
def test_the_picks_fill_the_allowed_readings_and_the_answer_says_how_many(
    owner, a_case, monkeypatch
):
    settings_store.set_to("case_chat_hours", 6)
    calls = [a_recording(owner, a_case, f"Call {n}", hours=4) for n in range(1, 4)]
    for one in calls:
        summarised(one, "About the unit.")
    selection = json.dumps(
        {
            "picks": [{"recording": n, "why": "unit"} for n in (3, 1, 2)],
            "none": False,
            "note": "",
        }
    )
    asked = engine_answering(monkeypatch, [selection, "Yes [Recording 1, 00:00:00]."])
    # A Reading the size of one transcript: one pick fits. The overviews keep
    # a budget of their own here, so pass one stays one call.
    size = prompts.tokens(prompts.render(prompts.lines_of(calls[0].transcript))) + 20
    monkeypatch.setattr(settings_store, "reading_tokens", lambda: size)
    monkeypatch.setattr(case_scope, "budget_for", lambda count, fixed: 100)
    turn = a_turn(a_case, owner)
    case_chat.answer_case_turn(turn.pk)
    turn.refresh_from_db()
    assert turn.state == "done", (turn.reason_class, turn.reason_detail)
    assert turn.selection["read_whole"] == 1
    assert turn.selection["pointed_to"] == 3
    assert "read 1 of the 3 they pointed to, so narrow the question" in turn.answer
    assert [one["title"] for one in turn.readings] == ["Call 3"]
    assert len(asked) == 2


@pytest.mark.django_db
def test_a_selection_that_names_nothing_is_the_answer(owner, a_case, monkeypatch):
    settings_store.set_to("case_chat_hours", 6)
    for n in range(1, 3):
        summarised(a_recording(owner, a_case, f"Call {n}", hours=4), "Weather.")
    asked = engine_answering(
        monkeypatch,
        [
            json.dumps(
                {"picks": [], "none": True, "note": "No overview mentions a car."}
            )
        ],
    )
    turn = a_turn(a_case, owner, "What colour was the car?")
    case_chat.answer_case_turn(turn.pk)
    turn.refresh_from_db()
    assert turn.state == "done" and len(asked) == 1
    assert turn.answer == (
        "Read the overviews of 2 recordings, then 0 whole. The overviews do not "
        "point to any recording for this question. No overview mentions a car."
    )
    assert turn.readings == [] and turn.selection["read_whole"] == 0
    row = Row.objects.get(category="llm", event="AI assistant call")
    assert row.details["feature"] == "case_chat_two_pass" and row.outcome == "success"
    assert "car" not in json.dumps(row.details)


@pytest.mark.django_db
def test_pass_one_splits_in_two_when_the_overviews_would_not_fit(
    owner, a_case, monkeypatch
):
    settings_store.set_to("case_chat_hours", 6)
    calls = [a_recording(owner, a_case, f"Call {n}", hours=4) for n in range(1, 5)]
    for one in calls:
        summarised(one, "The unit again. " * 30)
    # A Reading so small that four overviews cannot share it above the least
    # budget: two selection calls, merged by rank.
    monkeypatch.setattr(settings_store, "reading_tokens", lambda: 2000 + 4 * 40)
    monkeypatch.setattr(
        case_scope, "budget_for", lambda count, fixed: 40 if count > 2 else 90
    )
    first_half = json.dumps(
        {"picks": [{"recording": 2, "why": "a"}], "none": False, "note": ""}
    )
    second_half = json.dumps(
        {
            "picks": [{"recording": 4, "why": "b"}, {"recording": 3, "why": "c"}],
            "none": False,
            "note": "",
        }
    )
    asked = engine_answering(
        monkeypatch, [first_half, second_half, "Yes [Recording 1, 00:00:00]."]
    )
    turn = a_turn(a_case, owner)
    case_chat.answer_case_turn(turn.pk)
    turn.refresh_from_db()
    assert turn.state == "done", turn.reason_detail
    assert len(asked) == 3
    assert "recordings 1 to 2 of 4" in asked[0]["messages"][-1]["content"]
    assert "recordings 3 to 4 of 4" in asked[1]["messages"][-1]["content"]
    # Merged by rank: 2 and 4 first, then 3.
    assert [one["title"] for one in turn.selection["picks"]] == [
        "Call 2",
        "Call 4",
        "Call 3",
    ]
    row = Row.objects.get(category="llm", event="AI assistant call")
    assert row.details["selections"] == 2


@pytest.mark.django_db
def test_over_the_ceiling_with_no_summary_the_refusal_survives_and_points_the_way(
    owner, a_case, monkeypatch
):
    settings_store.set_to("case_chat_hours", 6)
    a_recording(owner, a_case, "Long one", hours=4)
    a_recording(owner, a_case, "Long two", hours=4)
    asked = engine_answering(monkeypatch, ["never"])
    turn = a_turn(a_case, owner)
    case_chat.answer_case_turn(turn.pk)
    turn.refresh_from_db()
    assert turn.state == "failed" and turn.reason_class == "llm_case_too_large"
    assert turn.route == case_scope.DIGEST and asked == []
    assert "no recording in it has a summary yet" in case_chat.what_to_say(turn)
    assert "write the summaries tonight" in case_chat.what_to_say(turn)


@pytest.mark.django_db
def test_the_export_says_what_each_question_read(owner, a_case, client, monkeypatch):
    from io import BytesIO

    from docx import Document

    a_recording(owner, a_case, "Call 1")
    engine_answering(monkeypatch, ["Nothing [Recording 1, 00:00:00]."])
    turn = a_turn(a_case, owner, "Anything?")
    case_chat.answer_case_turn(turn.pk)
    signed_in(client, owner)
    got = client.get(f"/case-chat/{turn.chat_id}/export")
    assert got.status_code == 200
    text = "\n".join(
        paragraph.text for paragraph in Document(BytesIO(got.content)).paragraphs
    )
    assert "Asked of every recording in the case." in text


@pytest.mark.django_db
def test_the_overviews_are_read_in_one_query_and_prefer_the_current_transcript(
    owner, a_case, django_assert_max_num_queries
):
    calls = [a_recording(owner, a_case, f"Call {n}") for n in range(1, 4)]
    summarised(calls[0], "Current.")
    Summary.objects.create(
        recording=calls[1], state=DONE, template_name="x", text="Overview:\nOld words."
    )
    with django_assert_max_num_queries(2):
        found = assistant.overviews_for(calls)
    assert found[calls[0].pk] == "Current." and found[calls[1].pk] == "Old words."
    assert calls[2].pk not in found
