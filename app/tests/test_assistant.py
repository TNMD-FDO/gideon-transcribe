"""The AI assistant: Summary, Chat, and Speaker suggestions.

The prompt arithmetic runs without a database. The rest runs against a fake
engine: what the viewer asks for, what the calls store, which times become
Citations, what the exports carry, and what the audit rows say and never say.
"""

from __future__ import annotations

import json

import pytest
from core import assistant, engine, prompts, settings_store
from core.assistant import Chat, ChatTurn, PromptTemplate, Suggestion, Summary
from core.audit import Row
from core.jobs import Segment, Transcript
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording

PASSWORD = "a-long-enough-password"


# The prompts, without a database -----------------------------------------------


def a_line(number, start, speaker, text):
    return prompts.Line(
        number=number, segment_id=number, start=start, speaker=speaker, text=text
    )


LINES = [
    a_line(1, 0.0, "Speaker 1", "This is Detective Ruiz, it is nine in the morning."),
    a_line(2, 12.4, "Speaker 2", "Thanks, Maria, I understand."),
    a_line(3, 724.0, "Speaker 1 (corrected)", "Tell me about the car."),
]


def test_the_transcript_renders_one_numbered_line_per_segment():
    rendered = prompts.render(LINES)
    assert rendered.splitlines() == [
        "[1] [00:00:00] Speaker 1: This is Detective Ruiz, it is nine in the morning.",
        "[2] [00:00:12] Speaker 2: Thanks, Maria, I understand.",
        "[3] [00:12:04] Speaker 1 (corrected): Tell me about the car.",
    ]
    # No label at all when there is no diarization and one side.
    assert prompts.render([a_line(1, 5.0, "", "Hello")]) == "[1] [00:00:05] Hello"


def test_a_time_is_a_citation_only_when_a_segment_starts_then():
    text = "He mentions the car at [00:12:04] and again at [00:15:00]. Also [00:00:12]."
    found = prompts.citations(text, LINES)
    assert found == {"[00:12:04]": 724.0, "[00:00:12]": 12.4}


def test_the_token_estimate_is_four_characters_with_a_margin():
    assert prompts.tokens("a" * 400) == 110
    assert prompts.fits("a" * 4000, answer_cap=100)
    assert not prompts.fits("a" * (prompts.ENGINE_WINDOW * 4), answer_cap=100)


def test_the_chat_history_keeps_the_latest_turns_that_fit(monkeypatch):
    monkeypatch.setattr(prompts, "HISTORY_TOKENS", 60)
    turns = [("q1", "a" * 100), ("q2", "b" * 100), ("q3", "c" * 40)]
    kept = prompts.history_that_fits(turns)
    # Newest first: q3 costs 12 tokens and q2 29 more, 41 of the 60; q1's 29
    # would pass the budget, so it is the one dropped.
    assert kept == [("q2", "b" * 100), ("q3", "c" * 40)]


def test_the_summary_input_carries_the_length_and_the_focus():
    said = prompts.summary_input("the car", "short")
    assert said.splitlines()[0] == "Keep the whole summary under about 250 words."
    assert "Concentrate on: the car." in said
    assert (
        prompts.summary_input("", "detailed")
        == "Write up to about 1,500 words; be thorough."
    )


def test_suggestions_are_kept_only_when_every_check_holds():
    raw = [
        {
            "speaker": "Speaker 1",
            "name": "Detective Ruiz",
            "kind": "name",
            "confidence": "high",
            "line": 1,
            "quote": "This is Detective Ruiz",
        },
        {
            "speaker": "Speaker 2",
            "name": "Maria",
            "kind": "name",
            "confidence": "low",
            "line": 2,
            "quote": "Thanks, Maria",
        },
        {
            "speaker": "Speaker 3",
            "name": "Officer",
            "kind": "role",
            "confidence": "medium",
            "line": 99,
            "quote": "x",
        },
        {
            "speaker": "Speaker 3",
            "name": "unknown",
            "kind": "unknown",
            "confidence": "high",
            "line": 3,
            "quote": "x",
        },
        {
            "speaker": "Speaker 4",
            "name": "Detective Ruiz",
            "kind": "name",
            "confidence": "medium",
            "line": 3,
            "quote": "y",
        },
        {
            "speaker": "Speaker 5",
            "name": "Judge Lee",
            "kind": "name",
            "confidence": "high",
            "line": 2,
            "quote": "z",
        },
    ]
    kept = prompts.keep_suggestions(
        raw,
        ["Speaker 1", "Speaker 2", "Speaker 3", "Speaker 4", "Speaker 5"],
        {"Judge Lee"},
        LINES,
    )
    # Low is dropped, a missing line is dropped, unknown is dropped, a name a
    # speaker already holds is dropped, and a name proposed twice goes to the
    # surer speaker.
    assert [(one["speaker"], one["name"]) for one in kept] == [
        ("Speaker 1", "Detective Ruiz")
    ]
    assert kept[0]["segment_id"] == 1 and kept[0]["start"] == 0.0


def test_the_suggestions_schema_is_bounded_and_a_cut_answer_is_salvaged():
    schema = prompts.suggestions_schema(["Speaker 1", "Speaker 2", "Speaker 3"])
    assert schema["properties"]["suggestions"]["maxItems"] == 3
    assert (
        schema["properties"]["suggestions"]["items"]["properties"]["quote"]["maxLength"]
        == 300
    )
    cut = (
        '{"suggestions": [{"speaker": "Speaker 1", "name": "Officer", "kind": "role", '
        '"confidence": "high", "line": 1, "quote": "x"}, {"speaker": "Speaker 2", "na'
    )
    whole = json.loads(prompts.salvage_json(cut))
    assert [one["speaker"] for one in whole["suggestions"]] == ["Speaker 1"]
    assert prompts.salvage_json("not json at all") == "not json at all"


def test_a_chat_is_named_from_its_first_question():
    assert (
        Chat.name_from("When is the car first mentioned?")
        == "When is the car first mentioned?"
    )
    long = "word " * 40
    assert len(Chat.name_from(long)) <= 60
    assert Chat.name_from("   ") == "New chat"


def test_a_speaker_label_is_told_from_a_name():
    assert assistant._is_a_label("Speaker 1")
    assert assistant._is_a_label("Side 2 Speaker 1")
    assert not assistant._is_a_label("Detective Ruiz")
    assert not assistant._is_a_label("Speaker")


def test_a_label_offered_as_a_name_is_dropped():
    for label in (
        "Speaker3",
        "Speaker 3",
        "SPEAKER_02",
        "Side 1 Speaker 2",
        "side1speaker2",
        "Side 2",
    ):
        assert prompts.looks_like_a_label(label), label
    for name in (
        "Detective Ruiz",
        "Officer",
        "Speaker of the House",
        "Sidney",
        "Maria",
    ):
        assert not prompts.looks_like_a_label(name), name
    raw = [
        {
            "speaker": "Speaker 1",
            "name": "Speaker3",
            "kind": "name",
            "confidence": "high",
            "line": 1,
            "quote": "x",
        },
        {
            "speaker": "Speaker 2",
            "name": "Officer",
            "kind": "role",
            "confidence": "medium",
            "line": 2,
            "quote": "y",
        },
    ]
    kept = prompts.keep_suggestions(raw, ["Speaker 1", "Speaker 2"], set(), LINES)
    assert [(one["speaker"], one["name"]) for one in kept] == [("Speaker 2", "Officer")]


# The features, against a fake engine ---------------------------------------------


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("asker", PASSWORD)


@pytest.fixture
def ready(person, tmp_path, settings):
    settings.DATA_DIR = tmp_path
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        title="Interview",
        original_filename="interview.mp4",
        media_state=MediaState.READY,
        duration_seconds=900.0,
        diarize=True,
        vocabulary=["Maria Lopez"],
    )
    transcript = Transcript.objects.create(recording=recording, language="en")
    for start, speaker, text in (
        (0.0, "Speaker 1", "This is Detective Ruiz."),
        (12.4, "Speaker 2", "Thanks, Maria."),
        (724.0, "Speaker 1", "Tell me about the car."),
    ):
        Segment.objects.create(
            transcript=transcript,
            start=start,
            end=start + 5,
            text=text,
            speaker=speaker,
            speaker_label=speaker.upper().replace(" ", "_"),
        )
    settings_store.set_to("assistant_available", True)
    # Suggestions start Off; these tests exercise them, so they turn it on.
    settings_store.set_to("suggestions_available", True)
    return recording


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def reachable(monkeypatch, answer_text, finish="stop"):
    """An engine that is up and answers every call with one text."""
    monkeypatch.setattr(engine, "is_reachable", lambda: True)
    monkeypatch.setattr(engine, "address", lambda: "http://gideon-generator:8000/v1")
    asked = []

    def complete(messages, **options):
        asked.append({"messages": messages, **options})
        return {
            "text": answer_text,
            "finish_reason": finish,
            "input_tokens": 1234,
            "output_tokens": 56,
            "model": "the-model",
        }

    monkeypatch.setattr(engine, "complete", complete)
    return asked


def swallow_defers(monkeypatch):
    from core import tasks

    for name in ("write_summary", "answer_turn", "suggest_names"):
        monkeypatch.setattr(getattr(tasks, name), "defer", lambda **fields: None)


@pytest.mark.django_db
def test_a_summary_is_written_whole_with_its_citations(
    ready, person, client, monkeypatch
):
    swallow_defers(monkeypatch)
    asked = reachable(
        monkeypatch,
        "Overview:\nAn interview. The car comes up at [00:12:04].\n"
        "Key points:\n- The detective introduces himself [00:00:00]\n"
        "- Made-up time [00:05:00]",
    )
    signed_in(client, person)

    made = client.post(
        f"/recording/{ready.pk}/summaries",
        json.dumps({"focus": "the car", "length": "short"}),
        "application/json",
    )
    assert made.status_code == 200
    summary = Summary.objects.get(pk=made.json()["id"])
    assert (
        summary.state == assistant.QUEUED
        and summary.template_name == "Standard summary"
    )

    assistant.write_summary(summary.pk)
    summary.refresh_from_db()
    assert summary.state == assistant.DONE
    assert summary.citations == {"[00:12:04]": 724.0, "[00:00:00]": 0.0}
    assert summary.model == "the-model"

    # The call: ground rules then the template then the format in the system
    # message; the nature line, the transcript and the length line in the user's.
    call = asked[0]
    system = call["messages"][0]["content"]
    assert (
        system.startswith(prompts.GROUND_RULES) and prompts.STANDARD_SUMMARY in system
    )
    user = call["messages"][-1]["content"]
    assert user.startswith(
        "This is an automatic machine transcription of a 15 min recording in English."
    )
    assert "Speakers were separated automatically" in user
    assert "[3] [00:12:04] Speaker 1: Tell me about the car." in user
    assert "under about 250 words" in user and "Concentrate on: the car." in user
    assert call["max_completion_tokens"] == 600 and call["temperature"] == 0.3
    assert call["thinking"] is False and call["timeout"] == 300

    state = client.get(f"/recording/{ready.pk}/assistant").json()
    assert state["summary"] and state["busy"] is False
    shown = state["summaries"][0]
    assert shown["state"] == "done" and shown["citations"]["[00:12:04]"] == 724.0
    assert "AI-generated and unverified" in shown["notice"]
    assert "the-model" in shown["notice"]

    # One audit row, metadata only: never the text, the focus, or the prompt.
    row = Row.objects.filter(category="llm").latest("at")
    assert row.event == "AI assistant call" and row.details["feature"] == "summary"
    assert row.details["templates"] == "ground-rules v1; Standard summary v1"
    assert row.details["input_tokens"] == 1234 and row.outcome == "success"
    assert "the car" not in json.dumps(row.details)

    word = client.get(f"/summary/{summary.pk}/export")
    assert word.status_code == 200
    assert word["Content-Disposition"].startswith(
        'attachment; filename="Interview - summary (Standard summary)'
    )
    assert word.content[:2] == b"PK"


@pytest.mark.django_db
def test_a_summary_fails_at_once_while_the_engine_is_down(ready, person, monkeypatch):
    monkeypatch.setattr(engine, "is_reachable", lambda: False)
    summary = Summary.objects.create(
        recording=ready, asked_by=person, template_name="Standard summary"
    )
    assistant.write_summary(summary.pk)
    summary.refresh_from_db()
    assert (
        summary.state == assistant.FAILED and summary.reason_class == "llm_unreachable"
    )
    row = Row.objects.filter(category="llm").latest("at")
    assert row.outcome == "failure" and row.reason_class == "llm_unreachable"


@pytest.mark.django_db
def test_a_chat_answers_from_the_transcript_and_carries_its_history(
    ready, person, client, monkeypatch
):
    swallow_defers(monkeypatch)
    asked = reachable(monkeypatch, "The car comes up at [00:12:04].")
    signed_in(client, person)

    chat_id = client.post(f"/recording/{ready.pk}/chats").json()["id"]
    first = client.post(
        f"/chat/{chat_id}/ask",
        json.dumps({"question": "When is the car mentioned?"}),
        "application/json",
    )
    assert first.status_code == 200
    chat = Chat.objects.get(pk=chat_id)
    assert chat.name == "When is the car mentioned?"
    turn = ChatTurn.objects.get(pk=first.json()["id"])
    assistant.answer_turn(turn.pk)
    turn.refresh_from_db()
    assert turn.state == assistant.DONE and turn.citations == {"[00:12:04]": 724.0}

    # A second question is refused while the first is still being answered,
    # and once answered it goes with the first turn as history.
    second = client.post(
        f"/chat/{chat_id}/ask",
        json.dumps({"question": "Who spoke first?"}),
        "application/json",
    )
    assert second.status_code == 200
    assistant.answer_turn(second.json()["id"])
    messages = asked[-1]["messages"]
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert messages[1]["content"] == "When is the car mentioned?"
    assert messages[2]["content"] == "The car comes up at [00:12:04]."
    assert asked[-1]["max_completion_tokens"] == 1500 and asked[-1]["timeout"] == 120

    state = client.get(f"/recording/{ready.pk}/assistant").json()
    assert len(state["chats"][0]["turns"]) == 2
    word = client.get(f"/chat/{chat_id}/export")
    assert word.status_code == 200 and word.content[:2] == b"PK"

    gone = client.post(f"/chat/{chat_id}/delete")
    assert gone.status_code == 200 and not Chat.objects.filter(pk=chat_id).exists()
    assert Row.objects.filter(category="edits", event="Chat deleted").exists()


@pytest.mark.django_db
def test_suggest_names_keeps_what_the_checks_allow_and_accept_renames(
    ready, person, client, monkeypatch
):
    swallow_defers(monkeypatch)
    asked = reachable(
        monkeypatch,
        json.dumps(
            {
                "suggestions": [
                    {
                        "speaker": "Speaker 1",
                        "name": "Detective Ruiz",
                        "kind": "name",
                        "confidence": "high",
                        "line": 1,
                        "quote": "This is Detective Ruiz.",
                    },
                    {
                        "speaker": "Speaker 2",
                        "name": "Maria Lopez",
                        "kind": "name",
                        "confidence": "low",
                        "line": 2,
                        "quote": "Thanks, Maria.",
                    },
                ]
            }
        ),
    )
    signed_in(client, person)

    started = client.post(f"/recording/{ready.pk}/suggest")
    assert started.status_code == 200
    assistant.suggest_names(started.json()["id"])

    call = asked[0]
    assert call["schema"]["properties"]["suggestions"]["maxItems"] == 2
    assert call["temperature"] == 0.0
    assert "Unnamed speakers: Speaker 1, Speaker 2" in call["messages"][-1]["content"]
    assert "Known names: Maria Lopez" in call["messages"][-1]["content"]

    state = client.get(f"/recording/{ready.pk}/assistant").json()
    assert state["suggestion_run"]["state"] == "done"
    assert [(one["speaker"], one["name"]) for one in state["pending"]] == [
        ("Speaker 1", "Detective Ruiz")
    ]
    assert state["pending"][0]["clock"] == "00:00:00"

    suggestion = Suggestion.objects.get(state=Suggestion.PENDING)
    accepted = client.post(f"/suggestion/{suggestion.pk}/accept")
    assert accepted.json()["changed"] == 2
    assert set(
        Segment.objects.filter(transcript=ready.transcript).values_list(
            "speaker", flat=True
        )
    ) == {"Detective Ruiz", "Speaker 2"}
    row = Row.objects.filter(category="edits", event="Suggestion accepted").latest("at")
    assert "Ruiz" not in json.dumps(row.details)
    # One unnamed speaker is left, so the run is refused now.
    assert client.post(f"/recording/{ready.pk}/suggest").status_code == 409


@pytest.mark.django_db
def test_invalid_suggestion_json_twice_is_bad_output(ready, person, monkeypatch):
    reachable(monkeypatch, "not json at all")
    run = assistant.SuggestionRun.objects.create(
        transcript=ready.transcript, asked_by=person
    )
    assistant.suggest_names(run.pk)
    run.refresh_from_db()
    assert run.state == assistant.FAILED and run.reason_class == "llm_bad_output"


@pytest.mark.django_db
def test_the_features_hide_when_the_assistant_is_off(ready, person, client):
    settings_store.set_to("assistant_available", False)
    signed_in(client, person)
    state = client.get(f"/recording/{ready.pk}/assistant").json()
    assert state["assistant"] is False and state["summary"] is False
    assert (
        client.post(
            f"/recording/{ready.pk}/summaries", "{}", "application/json"
        ).status_code
        == 404
    )
    page = client.get(f"/recording/{ready.pk}").content.decode()
    assert 'data-panel="summary"' not in page and "assistant.js" not in page


@pytest.mark.django_db
def test_the_viewer_offers_the_tabs_when_the_assistant_is_on(
    ready, person, client, monkeypatch
):
    monkeypatch.setattr(engine, "is_reachable", lambda: True)
    signed_in(client, person)
    page = client.get(f"/recording/{ready.pk}").content.decode()
    assert 'data-panel="summary"' in page and 'data-panel="chat"' in page
    # The shared Chat fills its root; the two scripts come in that order.
    assert 'id="chat-root"' in page
    assert page.index("chat-ui.js") < page.index("assistant.js")
    # In the Workspace there is no case to ask about.
    assert "caseChatUrl: null" in page
    assert 'id="suggest-names"' in page and "assistant.js" in page


@pytest.mark.django_db
def test_the_templates_page_saves_resets_and_versions(person, client):
    signed_in(client, person)
    page = client.get("/panel/templates").content.decode()
    assert "Ground rules" in page and "Standard summary" in page and "version 1" in page

    client.post(
        "/panel/templates/prompt/chat", {"action": "save", "text": "Answer briefly."}
    )
    chat = PromptTemplate.named(PromptTemplate.CHAT)
    assert chat.text == "Answer briefly." and chat.version == 2
    client.post("/panel/templates/prompt/chat", {"action": "reset"})
    chat.refresh_from_db()
    assert chat.text == prompts.CHAT and chat.version == 3

    client.post(
        "/panel/templates/summary",
        {
            "name": "Short brief",
            "description": "For a quick read",
            "text": "Three bullet points.",
        },
    )
    added = assistant.SummaryTemplate.objects.get(name="Short brief")
    assert added.enabled and not added.is_default
    client.post(f"/panel/templates/summary/{added.pk}", {"action": "default"})
    assert assistant.SummaryTemplate.the_default().pk == added.pk
    client.post(f"/panel/templates/summary/{added.pk}", {"action": "delete"})
    assert not assistant.SummaryTemplate.objects.filter(pk=added.pk).exists()
    # The built-in one takes the Default back and is never deleted.
    standard = assistant.SummaryTemplate.standard()
    assert assistant.SummaryTemplate.the_default().pk == standard.pk
    client.post(f"/panel/templates/summary/{standard.pk}", {"action": "delete"})
    assert assistant.SummaryTemplate.objects.filter(pk=standard.pk).exists()
    rows = Row.objects.filter(category="admin", object_type="template")
    assert rows.count() >= 5
    assert "Answer briefly" not in json.dumps([row.details for row in rows])


@pytest.mark.django_db
def test_the_starter_questions_are_the_offices_own_and_start_empty(
    ready, person, client
):
    signed_in(client, person)
    assert settings_store.get("chat_starters") == ""
    assert client.get(f"/recording/{ready.pk}/assistant").json()["starters"] == []
    page = client.get("/panel/templates").content.decode()
    assert "Chat starter questions" in page and "Case chat starter questions" in page

    client.post(
        "/panel/templates/starters/chat_starters",
        {"text": "Who is speaking?\n\n  What is this about?  \n"},
    )
    assert settings_store.lines_of("chat_starters") == [
        "Who is speaking?",
        "What is this about?",
    ]
    assert client.get(f"/recording/{ready.pk}/assistant").json()["starters"] == [
        "Who is speaking?",
        "What is this about?",
    ]
    row = Row.objects.get(category="admin", event="Setting changed")
    assert row.object_id == "chat_starters" and row.details["was"] == "(empty)"
    # An unknown list is refused without a row.
    client.post("/panel/templates/starters/nonsense", {"text": "x"})
    assert Row.objects.filter(category="admin", event="Setting changed").count() == 1


@pytest.mark.django_db
def test_thinking_gets_its_own_room_and_an_empty_answer_says_why(
    ready, person, monkeypatch
):
    # Thinking on: the cap sent is the answer's plus the allowance, and a model
    # that spends it all thinking leaves an empty answer at the cap, which is
    # not "cut short" but its own plain failure line.
    settings_store.set_to("assistant_thinks", True)
    asked = reachable(monkeypatch, "", finish="length")
    summary = Summary.objects.create(
        recording=ready,
        asked_by=person,
        template_name="Standard summary",
        length="short",
    )
    assistant.write_summary(summary.pk)
    summary.refresh_from_db()
    assert asked[0]["max_completion_tokens"] == 600 + assistant.THINKING_ALLOWANCE
    assert asked[0]["thinking"] is True and asked[0]["timeout"] == 600
    assert summary.state == assistant.FAILED
    assert summary.reason_class == assistant.THOUGHT_AWAY
    assert "Turn off" in assistant.what_to_say(summary.reason_class)
    # The audit row keeps the chapter's own class.
    row = Row.objects.filter(category="llm").latest("at")
    assert row.reason_class == "llm_error"

    # Thinking off: the cap is the answer's alone.
    settings_store.set_to("assistant_thinks", False)
    asked.clear()
    again = Summary.objects.create(
        recording=ready,
        asked_by=person,
        template_name="Standard summary",
        length="short",
    )
    assistant.write_summary(again.pk)
    assert asked[0]["max_completion_tokens"] == 600 and asked[0]["thinking"] is False


@pytest.mark.django_db
def test_speaker_suggestions_start_off(ready, person, client):
    settings_store.set_to("suggestions_available", False)
    settings_store.set_to("assistant_available", True)
    assert settings_store.definition("suggestions_available").default is False
    signed_in(client, person)
    state = client.get(f"/recording/{ready.pk}/assistant").json()
    assert state["suggestions"] is False and state["summary"] is True
    assert client.post(f"/recording/{ready.pk}/suggest").status_code == 404
    assert (
        'id="suggest-names"'
        not in client.get(f"/recording/{ready.pk}").content.decode()
    )
