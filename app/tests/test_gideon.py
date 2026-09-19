"""v1.67.0: Gideon, the chat with a name, a place of its own, and the
incident's chat (Phase 7, chapter 5).

The rules checked here: the name is a setting that shows on the tabs, the
Ask button and the export's title, and falls back to Chat when empty; the
Ask button is on the case, recording and incident pages and greyed with
the reason when the engine is off; a case chat citation carries the media
the preview plays; the incident's conversations are the incident's, are
listed apart from the case's, answer from the incident record with
citations on the incident clock, and refuse while the chat is off or no
synced camera has a transcript; nothing of a question is logged.
"""

from __future__ import annotations

import json

import pytest
from core import case_chat, chronology, incident_chat, incidents, settings_store, tasks
from core.assistant import PromptTemplate
from core.audit import Row
from core.case_chat import CaseChat, CaseChatTurn
from core.cases import Case
from core.jobs import Segment, Transcript
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording
from tests.test_prepare import engine_answering

PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"


@pytest.fixture(autouse=True)
def switched_on(db, monkeypatch):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("incidents", True)
    settings_store.set_to("assistant_available", True)
    settings_store.set_to("chat_available", True)
    settings_store.set_to("chat_across_cases", True)
    monkeypatch.setattr(tasks.answer_incident_turn, "defer", lambda **f: None)
    monkeypatch.setattr(tasks.answer_case_turn, "defer", lambda **f: None)


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("asker", PASSWORD)


@pytest.fixture
def a_case(person):
    return Case.objects.create(owner=person, name="Traffic stop")


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def stamp(time: str, camera: str):
    return {
        "date": "06/07/2025",
        "time": time,
        "camera": camera,
        "at": 2.0,
        "checked": True,
    }


def video(person, case, title, *, seconds=600.0, stamp=None, lines=()):
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        case=case,
        title=title,
        original_filename=f"{title}.mp4",
        media_state=MediaState.READY,
        duration_seconds=seconds,
        playback_ready=True,
        stamp=stamp,
        probe={},
    )
    recording.folder.mkdir(parents=True, exist_ok=True)
    (recording.folder / "playback.mp4").write_bytes(b"not really media")
    if lines:
        transcript = Transcript.objects.create(recording=recording, language="en")
        for start, speaker, text in lines:
            Segment.objects.create(
                transcript=transcript,
                start=start,
                end=start + 4,
                text=text,
                speaker=speaker,
                speaker_label=speaker.upper().replace(" ", "_"),
            )
    return recording


@pytest.fixture
def incident(person, a_case):
    first = video(
        person,
        a_case,
        "first",
        stamp=stamp("21:56:19", "BWC2-1"),
        lines=((30.0, "Officer Hale", "I got, I got gun, I got gun."),),
    )
    second = video(person, a_case, "second", stamp=stamp("22:01:00", "BWC2-2"))
    return incidents.make(a_case, "Stop", [first, second], by=person)


# The name -----------------------------------------------------------------------------


def test_the_name_is_a_setting_shown_on_the_pages(person, a_case, incident, client):
    assert settings_store.chat_name() == "Gideon"
    signed_in(client, person)
    page = client.get(f"/case/{a_case.pk}").content.decode()
    assert ">Gideon</a>" in page and "Ask Gideon" in page
    assert 'data-kind="case"' in page and 'id="gideon-open"' in page
    first = a_case.recordings.get(title="first")
    page = client.get(f"/recording/{first.pk}").content.decode()
    assert 'data-panel="chat">Gideon<' in page and 'data-kind="recording"' in page
    page = client.get(f"/case/{a_case.pk}/incident/{incident.pk}").content.decode()
    assert 'data-kind="incident"' in page and "Ask Gideon" in page
    # The engine is off in tests, so the button is greyed with the reason.
    greyed = 'aria-controls="gideon-drawer"\n          disabled title="'
    assert greyed in page
    settings_store.set_to("chat_name", "  ")
    assert settings_store.chat_name() == "Chat"
    page = client.get(f"/case/{a_case.pk}").content.decode()
    assert ">Chat</a>" in page and "Ask Chat" in page
    settings_store.set_to("chat_name", "Second Chair")
    page = client.get(f"/case/{a_case.pk}").content.decode()
    assert ">Second Chair</a>" in page
    # The word in the setting's own row stays Chat.
    definition = settings_store.definition("chat_name")
    assert definition.page == "appearance" and definition.needs == "chat_available"


def test_a_case_chat_citation_carries_what_the_preview_plays(
    person, a_case, incident, client
):
    first = a_case.recordings.get(title="first")
    chat = CaseChat.objects.create(case=a_case, asked_by=person, name="Gun?")
    CaseChatTurn.objects.create(
        chat=chat,
        number=1,
        question="Gun?",
        answer="Yes [Recording 1, 00:00:30].",
        citations={
            "[Recording 1, 00:00:30]": {"recording": str(first.pk), "seconds": 30.0}
        },
        readings=[case_chat.reading_of(first, first.transcript)],
        state="done",
    )
    signed_in(client, person)
    got = client.get(f"/case/{a_case.pk}/chat").json()
    cited = got["chats"][0]["turns"][0]["citations"]["[Recording 1, 00:00:30]"]
    assert cited["seconds"] == 30.0
    assert cited["media"].endswith("/playback.mp4") and str(first.pk) in cited["media"]
    assert cited["all"].startswith(incident.url())


# The incident's chat ----------------------------------------------------------------


def test_the_incidents_conversations_are_the_incidents(
    person, a_case, incident, client
):
    signed_in(client, person)
    url = f"/case/{a_case.pk}/incident/{incident.pk}"
    got = client.post(url + "/chats").json()
    chat = CaseChat.objects.get(pk=got["id"])
    assert chat.incident_id == incident.pk and chat.case_id == a_case.pk
    # Listed on the incident page, not on the case's Chat tab.
    state = client.get(url + "/chat").json()
    assert [one["id"] for one in state["chats"]] == [str(chat.pk)]
    assert state["readable"] == 1 and state["left_out"] == []
    assert client.get(f"/case/{a_case.pk}/chat").json()["chats"] == []
    # A question is queued for the incident's own answer.
    answer = client.post(
        f"/case-chat/{chat.pk}/ask",
        json.dumps({"question": "Was a gun found?"}),
        content_type="application/json",
    )
    assert answer.status_code == 200
    turn = chat.turns.get()
    assert turn.question == "Was a gun found?" and turn.state == "queued"
    CaseChatTurn.objects.filter(pk=turn.pk).update(state="done")
    # Off, or nothing synced with words, refuses plainly.
    settings_store.set_to("incidents_chat", False)
    answer = client.post(
        f"/case-chat/{chat.pk}/ask",
        json.dumps({"question": "Again?"}),
        content_type="application/json",
    )
    assert (
        answer.status_code == 409
        and answer.json()["error"] == "the incident chat is off"
    )
    assert client.post(url + "/chats").status_code == 403
    settings_store.set_to("incidents_chat", True)
    turn.delete()
    for camera in incident.cameras.all():
        incidents.IncidentCamera.objects.filter(pk=camera.pk).update(
            placed=incidents.GUESS
        )
    answer = client.post(
        f"/case-chat/{chat.pk}/ask",
        json.dumps({"question": "Again?"}),
        content_type="application/json",
    )
    assert answer.status_code == 409 and "no synced camera" in answer.json()["error"]
    # The conversation goes with the incident.
    incidents.delete(incident, by=person) if hasattr(
        incidents, "delete"
    ) else incident.delete()
    assert not CaseChat.objects.filter(pk=chat.pk).exists()
    for row in Row.objects.all():
        assert "gun" not in json.dumps(row.details).lower()


def test_the_answer_reads_the_record_and_cites_the_incident_clock(
    person, a_case, incident, monkeypatch
):
    cams = {one.camera_id(): one for one in incident.cameras.all()}
    chronology.add(
        incident,
        {
            "at": "30",
            "text": "Gun found",
            "camera": str(cams["BWC2-1"].pk),
            "note": "Page 4",
        },
        by=person,
    )
    incidents.set_about(incident, "The stop on Route 9.", by=person)
    chat = incident_chat.new_chat(incident, by=person)
    turn = CaseChatTurn.objects.create(chat=chat, number=1, question="Was a gun found?")
    asked = engine_answering(
        monkeypatch,
        ["An officer said he had found a gun at [21:56:47] on BWC2-1; see [23:59:59]."],
    )
    incident_chat.answer_incident_turn(turn.pk)
    turn.refresh_from_db()
    assert turn.state == "done"
    assert turn.citations == {"[21:56:47]": 30.0}
    # The system carries the Incident chat template and the incident rules;
    # the question follows the record and the chronology with its note and About.
    system = asked[0]["messages"][0]["content"]
    assert PromptTemplate.named(PromptTemplate.INCIDENT_CHAT).text in system
    assert "on one clock" in system
    user = asked[0]["messages"][-1]["content"]
    assert "The question: Was a gun found?" in user
    assert "Gun found" in user and "Page 4" in user and "Route 9" in user
    assert "I got, I got gun" in user
    assert asked[0]["max_completion_tokens"] == 2000
    # The page's shape: the clock, the seconds, the incident page at that moment.
    state = incident_chat.state_json(incident)
    cited = state["chats"][0]["turns"][0]["citations"]["[21:56:47]"]
    assert cited == {
        "clock": "21:56:47",
        "seconds": 30.0,
        "href": f"{incident.url()}?t=30.00",
    }
    row = Row.objects.filter(event="AI assistant call").order_by("-at").first()
    assert row.details.get("feature") == "incident_chat"
    assert "gun" not in json.dumps(row.details).lower()
    # A second question is asked with the first as history.
    second = CaseChatTurn.objects.create(chat=chat, number=2, question="And then?")
    asked = engine_answering(monkeypatch, ["Then nothing."])
    incident_chat.answer_incident_turn(second.pk)
    assert [m["role"] for m in asked[0]["messages"]] == [
        "system",
        "user",
        "assistant",
        "user",
    ]
    # The template and its settings are in their places.
    assert PromptTemplate.named(PromptTemplate.INCIDENT_CHAT).name == "Incident chat"
    assert settings_store.definition("incidents_chat").group == "The assistant"
    assert settings_store.time_limit_seconds("incident_chat") == 300
