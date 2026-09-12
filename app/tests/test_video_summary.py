"""The video summary and the video-aware chat (Phase 4, chapter 5, v1.43.0).

The rules checked here: a video without a type gets the Video summary
preselected, a typed one its type's template, and sound alone the Default;
Summary and Chat are told the camera rules only when a camera block is
given, and the summary how many of its lines to draw on; a staff-edited
Moment's line says so; the block is thinned to its budget with every asked
Moment kept; the state carries the rule for the dialog's tick and the page
says Summarise this video; the wording is clean; the settings and the
catalogue agree.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from core import assistant, engine, prompts, settings_store
from core.assistant import Chat, ChatTurn, Moment, Summary, SummaryTemplate
from core.jobs import Segment, Transcript
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording

PASSWORD = "a-long-enough-password"
CATALOGUE = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "spec"
    / "ADMIN-SETTINGS-CATALOGUE.md"
)


class Seen:
    """A Moment as the prompt helpers see one, without a database."""

    def __init__(self, at, text, source="asked", edited=False, question=""):
        self.at, self.text, self.source = at, text, source
        self.edited, self.question = edited, question


# Without a database ------------------------------------------------------------------


def test_the_camera_block_carries_its_legend_and_marks_staff_words():
    block = prompts.camera_lines(
        [
            Seen(12.4, "A hand holds a small bag."),
            Seen(30.0, "A clear bag.", edited=True),
            Seen(
                45.0,
                "Visible: a dark shape. Consistent with: a phone. Cannot be told: x.",
                question="what is in his hand?",
            ),
        ]
    )
    lines = block.split("\n")
    assert lines[0] == prompts.CAMERA_HEADING
    assert lines[1] == prompts.CAMERA_NOTE
    assert lines[2] == "[00:00:12] [camera] A hand holds a small bag."
    assert lines[3] == "[00:00:30] [camera] A clear bag. (edited by staff)"
    assert lines[4].startswith(
        '[00:00:45] [camera] (asked "what is in his hand?") Visible'
    )
    assert "[camera]" not in prompts.CAMERA_NOTE


def test_the_summary_is_told_what_to_make_of_the_picture():
    assert "camera block" not in prompts.summary_input("", "short")
    assert "camera block" not in prompts.summary_input("", "short", 0)
    few = prompts.summary_input("", "short", 3)
    assert "The camera block has 3 lines; draw on the ones that add a fact" in few
    # No per-length cap since v1.51.0: the Digest does the choosing, and
    # without one the model is told to leave the rest out.
    many = prompts.summary_input("", "short", 23)
    assert "Draw on at most" not in many and "leave the rest out" in many
    assert "The camera block has 1 line;" in prompts.summary_input("", "short", 1)
    told = prompts.summary_input("", "short", 23, digest=True)
    assert "The record of this recording is complete" in told
    assert "camera block" not in told
    # The rules go after the answer format only when a block is given.
    assert (
        prompts.with_camera_rules(prompts.SUMMARY_FORMAT, []) == prompts.SUMMARY_FORMAT
    )
    assert prompts.with_camera_rules(prompts.CHAT_FORMAT, [Seen(1.0, "x")]).endswith(
        prompts.CAMERA_RULES
    )


def test_the_camera_block_is_thinned_to_its_budget_keeping_every_asked_moment():
    long = "A road, a parked car, a man in a grey hoodie beside it. " * 4
    intervals = [Seen(30.0 + 60 * n, long, source="interval") for n in range(50)]
    asked = [Seen(12.4, "A hand holds a small bag."), Seen(2999.0, "A bag.", "cue")]
    everything = intervals + asked
    assert prompts.trim_camera_lines(everything, 100000) == sorted(
        everything, key=lambda one: one.at
    )
    budget = 800
    kept = prompts.trim_camera_lines(everything, budget)
    assert prompts.tokens(prompts.camera_lines(kept)) <= budget
    assert asked[0] in kept and asked[1] in kept
    kept_intervals = [one for one in kept if one.source == "interval"]
    assert 0 < len(kept_intervals) < 50
    # Spread over the recording, not taken from the start.
    assert kept_intervals[0] is intervals[0]
    assert kept_intervals[-1].at > intervals[25].at
    assert [one.at for one in kept] == sorted(one.at for one in kept)
    assert Moment.INTERVAL == "interval"


def test_the_wording_is_clean_and_the_templates_say_seen_but_not_said():
    DASH = chr(0x2014)
    for name in dir(prompts):
        value = getattr(prompts, name)
        if isinstance(value, str):
            assert DASH not in value, name
        if isinstance(value, dict):
            for text in value.values():
                if isinstance(text, str):
                    assert DASH not in text, name
    assert "the camera shows" in prompts.CAMERA_RULES
    assert "the camera shows" in prompts.CHAT
    assert "No moments were described" in prompts.SUMMARY_FORMAT
    for key in ("video", "body_camera"):
        text = prompts.SHIPPED_SUMMARIES[key]
        assert "Seen but not said" in text and "the camera shows" in text
        assert "Overview" in text and "Unclear parts" in text
    assert "Never a name from the camera" in prompts.SHIPPED_SUMMARIES["video"]
    assert "consented" in prompts.CHAT and "Moments tab" in prompts.CHAT


def test_the_settings_and_the_catalogue_agree():
    assert "summary_moments_enough" not in settings_store.DEFINITIONS
    assert settings_store.DEFINITIONS["summary_describes_first"].default is True
    record = settings_store.DEFINITIONS["picture_record_available"]
    assert record.page == settings_store.ASSISTANT and record.default is True
    assert record.needs == "moments_available"
    text = CATALOGUE.read_text(encoding="utf-8")
    for name in (
        "Summaries describe the moments first",
        "Picture record for summaries",
    ):
        assert f"| {name} |" in text, f"the catalogue has no row for {name}"
    assert "Video summary" in text


# With a database ----------------------------------------------------------------------


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("asker", PASSWORD)


def a_recording(person, tmp_path, settings, video=True, recording_type=""):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        title="Stop",
        original_filename="bodycam.mp4" if video else "call.m4a",
        media_state=MediaState.READY,
        duration_seconds=900.0,
        diarize=True,
        playback_ready=True,
        recording_type=recording_type,
    )
    recording.folder.mkdir(parents=True, exist_ok=True)
    (recording.folder / ("playback.mp4" if video else "playback.m4a")).write_bytes(
        b"not really media"
    )
    transcript = Transcript.objects.create(recording=recording, language="en")
    for start, speaker, text in (
        (0.0, "Speaker 1", "This is Officer Ruiz."),
        (12.4, "Speaker 2", "Look at that, right there."),
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
    settings_store.set_to("moments_available", True)
    return recording


@pytest.fixture
def ready(person, tmp_path, settings):
    return a_recording(person, tmp_path, settings)


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def reachable(monkeypatch, answer_text):
    monkeypatch.setattr(engine, "is_reachable", lambda: True)
    monkeypatch.setattr(engine, "address", lambda: "http://gideon-generator:8000/v1")
    asked = []

    def complete(messages, **options):
        asked.append({"messages": messages, **options})
        return {
            "text": answer_text,
            "finish_reason": "stop",
            "input_tokens": 3000,
            "output_tokens": 80,
            "model": "the-model",
        }

    monkeypatch.setattr(engine, "complete", complete)
    return asked


def described(transcript, at, text, **fields):
    return Moment.objects.create(
        transcript=transcript,
        at=at,
        state=assistant.DONE,
        text=text,
        model="the-model",
        **fields,
    )


@pytest.mark.django_db
def test_a_video_without_a_type_gets_the_video_summary(
    ready, person, tmp_path, settings, client
):
    assert SummaryTemplate.chosen_for(ready).key == "video"
    # The type wins.
    ready.recording_type = "Body camera"
    assert SummaryTemplate.chosen_for(ready).key == "body_camera"
    ready.recording_type = ""
    # Sound alone gets the Default.
    audio = a_recording(person, tmp_path, settings, video=False)
    assert SummaryTemplate.chosen_for(audio).key == "standard"
    # An office that hands no Moments to answers, or has Moments off, or has
    # disabled the Video summary, gets the Default too.
    settings_store.set_to("moments_in_answers", False)
    assert SummaryTemplate.chosen_for(ready).key == "standard"
    settings_store.set_to("moments_in_answers", True)
    settings_store.set_to("moments_available", False)
    assert SummaryTemplate.chosen_for(ready).key == "standard"
    settings_store.set_to("moments_available", True)
    video = SummaryTemplate.objects.get(key="video")
    video.enabled = False
    video.save()
    assert SummaryTemplate.chosen_for(ready).key == "standard"
    video.enabled = True
    video.save()
    assert SummaryTemplate.the_default().key == "standard"

    signed_in(client, person)
    state = client.get(f"/recording/{ready.pk}/assistant").json()
    assert state["default_template_key"] == "video"
    assert state["default_template"] == str(video.pk)
    assert state["type_line"] == "This is a video, so the Video summary is chosen."
    state = client.get(f"/recording/{audio.pk}/assistant").json()
    assert state["default_template_key"] == "standard" and state["type_line"] == ""
    # Nothing is chosen for the video while the office writes from words alone.
    settings_store.set_to("moments_in_answers", False)
    state = client.get(f"/recording/{ready.pk}/assistant").json()
    assert state["default_template_key"] == "standard" and state["type_line"] == ""


@pytest.mark.django_db
def test_the_summary_is_told_the_rules_and_remembers_what_it_drew_on(
    ready, person, monkeypatch
):
    asked = reachable(monkeypatch, "Summary: the camera shows a bag [00:00:12].")
    # The block's path, without a Digest (test_digest has the Digest's).
    settings_store.set_to("digests_available", False)
    transcript = ready.transcript
    described(transcript, 12.4, "A hand holds a small bag.")
    described(transcript, 30.0, "A clear bag.", edited=True)
    described(transcript, 45.0, "Visible: a phone.", question="what is in his hand?")
    for n in range(4):
        described(transcript, 100.0 + 60 * n, "A road.", source=Moment.INTERVAL)
    SummaryTemplate.shipped()
    summary = Summary.objects.create(
        recording=ready,
        asked_by=person,
        template=SummaryTemplate.objects.get(key="video"),
        template_name="Video summary",
        length="short",
    )
    assistant.write_summary(summary.pk)
    summary.refresh_from_db()
    assert summary.state == assistant.DONE
    assert summary.moments_used == 7
    system = asked[0]["messages"][0]["content"]
    user = asked[0]["messages"][-1]["content"]
    assert system.endswith(prompts.SUMMARY_FORMAT + "\n\n" + prompts.CAMERA_RULES)
    assert "Seen but not said" in system
    assert prompts.CAMERA_HEADING + "\n" + prompts.CAMERA_NOTE in user
    assert "[00:00:30] [camera] A clear bag. (edited by staff)" in user
    assert (
        '[00:00:45] [camera] (asked "what is in his hand?") Visible: a phone.' in user
    )
    assert "The camera block has 7 lines; draw on the ones that add a fact" in user
    assert summary.citations == {"[00:00:12]": 12.4}

    # Without a block: no rules, no camera line in the input, nothing counted.
    Moment.objects.all().delete()
    summary.state = assistant.QUEUED
    summary.save()
    assistant.write_summary(summary.pk)
    summary.refresh_from_db()
    assert summary.moments_used == 0
    system = asked[1]["messages"][0]["content"]
    user = asked[1]["messages"][-1]["content"]
    assert prompts.CAMERA_RULES not in system and system.endswith(
        prompts.SUMMARY_FORMAT
    )
    assert "camera block" not in user and prompts.CAMERA_HEADING not in user


@pytest.mark.django_db
def test_chat_is_told_the_rules_and_cites_the_camera(ready, person, monkeypatch):
    asked = reachable(
        monkeypatch, "The camera shows a dark object in his right hand [00:00:45]."
    )
    described(ready.transcript, 45.0, "A dark object in the right hand.")
    chat = Chat.objects.create(recording=ready, asked_by=person)
    turn = ChatTurn.objects.create(
        chat=chat, number=1, question="what was in his hand at 0:45?"
    )
    assistant.answer_turn(turn.pk)
    turn.refresh_from_db()
    assert turn.state == assistant.DONE
    system = asked[0]["messages"][0]["content"]
    assert system.endswith(prompts.CHAT_FORMAT + "\n\n" + prompts.CAMERA_RULES)
    assert "the camera shows" in system
    assert prompts.CAMERA_NOTE in asked[0]["messages"][-1]["content"]
    assert turn.citations == {"[00:00:45]": 45.0}

    Moment.objects.all().delete()
    second = ChatTurn.objects.create(chat=chat, number=2, question="and then?")
    assistant.answer_turn(second.pk)
    system = asked[1]["messages"][0]["content"]
    assert prompts.CAMERA_RULES not in system and system.endswith(prompts.CHAT_FORMAT)


@pytest.mark.django_db
def test_the_state_says_when_the_summary_looks_first(
    ready, person, tmp_path, settings, client
):
    signed_in(client, person)

    def runs():
        return client.get(f"/recording/{ready.pk}/assistant").json()["cue_runs"]

    # Shipped: the toggle On, spans left to describe: ticked. 900 s at the
    # 15 s ceiling is sixty spans by the clock alone, an estimate.
    first = runs()
    assert first["describe_first_default"] is True
    assert first["described"] == 0 and first["answers_use_moments"] is True
    assert first["intervals"]["count"] == 60 and first["intervals"]["estimated"]
    assert first["intervals"]["minutes"] == 20
    # Moments without spans cover nothing: still ticked (v1.51.0; the Enough
    # setting of v1.43.0 is withdrawn).
    for n in range(10):
        described(ready.transcript, 500.0 + n, "A road.", source=Moment.INTERVAL)
    second = runs()
    assert second["described"] == 10 and second["describe_first_default"] is True
    assert second["intervals"]["count"] == 60
    # The office's toggle Off: never ticked.
    settings_store.set_to("summary_describes_first", False)
    assert runs()["describe_first_default"] is False
    settings_store.set_to("summary_describes_first", True)
    # Nothing left to describe: unticked, whatever the rest says.
    settings_store.set_to("moment_interval_seconds", 600)
    Moment.objects.all().delete()
    for start, end in ((0.0, 450.0), (450.0, 900.0)):
        described(
            ready.transcript,
            start,
            "A road.",
            source=Moment.INTERVAL,
            span_start=start,
            span_end=end,
        )
    third = runs()
    assert third["intervals"]["count"] == 0 and third["intervals"]["minutes"] == 0
    assert third["describe_first_default"] is False
    # Moments off: no runs at all, as before.
    settings_store.set_to("moments_available", False)
    assert runs() == {}
    settings_store.set_to("moments_available", True)

    # The page's words: Summarise this video on a video, New summary on sound.
    page = client.get(f"/recording/{ready.pk}").content.decode()
    assert "Summarise this video" in page and "Look at the picture first" in page
    assert 'id="summary-look-line"' in page
    audio = a_recording(person, tmp_path, settings, video=False)
    page = client.get(f"/recording/{audio.pk}").content.decode()
    assert "New summary" in page and "Look at the picture first" not in page

    # A summary's card says how many moments it drew on.
    summary = Summary.objects.create(
        recording=ready,
        asked_by=person,
        template_name="Video summary",
        state=assistant.DONE,
        text="Summary.",
        moments_used=6,
    )
    state = client.get(f"/recording/{ready.pk}/assistant").json()
    assert state["summaries"][0]["id"] == str(summary.pk)
    assert state["summaries"][0]["moments_used"] == 6
    answer = client.post(
        f"/recording/{ready.pk}/summaries",
        data=json.dumps({"length": "short"}),
        content_type="application/json",
    )
    assert answer.status_code == 200
    assert Summary.objects.get(pk=answer.json()["id"]).moments_used == 0
