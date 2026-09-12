"""The Digest and the camera's stamp (Phase 4, chapter 6, v1.51.0).

The rules checked here: the Transcript is cut into windows within the budget
on line boundaries; a part's signature is what it was made from; a summary
makes the Digest after the record and is written from it, and remakes only
the stale parts the next time; a transcript too long for the window is
summarised from the Digest alone rather than refused; the Chat is told the
Digest in place of the block plus the descriptions at the times it names;
the Case Chat reads a Digest after each transcript and the Digest alone when
the case is too big; the audit rows carry the part's number and never its
words; the stamp is read from two frames, checked, kept, and told to the
model as the camera's clock; nobody sees a Digest.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from core import assistant, case_chat, engine, media, prompts, settings_store
from core.assistant import Chat, ChatTurn, DigestPart, Moment, Summary
from core.audit import Row
from core.cases import Case
from core.jobs import Segment, Transcript
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording

PASSWORD = "a-long-enough-password"


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("asker", PASSWORD)


def a_recording(person, tmp_path, settings, case=None, title="Stop"):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        case=case,
        title=title,
        original_filename="bodycam.mp4",
        media_state=MediaState.READY,
        duration_seconds=900.0,
        diarize=True,
        playback_ready=True,
    )
    recording.folder.mkdir(parents=True, exist_ok=True)
    (recording.folder / "playback.mp4").write_bytes(b"not really media")
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


def answering(monkeypatch, answers):
    """The engine answering from a list, in order, remembering every call."""
    monkeypatch.setattr(engine, "is_reachable", lambda: True)
    monkeypatch.setattr(engine, "address", lambda: "http://gideon-generator:8000/v1")
    asked = []
    queue = list(answers)

    def complete(messages, **options):
        asked.append({"messages": messages, **options})
        return {
            "text": queue.pop(0) if queue else "more",
            "finish_reason": "stop",
            "input_tokens": 100,
            "output_tokens": 20,
            "model": "the-model",
        }

    monkeypatch.setattr(engine, "complete", complete)
    return asked


def described(transcript, start, end, text):
    return Moment.objects.create(
        transcript=transcript,
        at=start,
        span_start=start,
        span_end=end,
        source=Moment.INTERVAL,
        state=assistant.DONE,
        text=text,
        model="the-model",
    )


def a_line(number, start, text):
    return prompts.Line(
        number=number, segment_id=number, start=start, speaker="A", text=text
    )


# Without a database ------------------------------------------------------------------


def test_the_transcript_is_cut_into_windows_on_line_boundaries():
    lines = [a_line(n, float(n * 10), "word " * 30) for n in range(1, 11)]
    one = prompts.tokens(prompts.render([lines[0]])) + 1
    windows = assistant.digest_windows(lines, one * 3)
    assert windows == [(0, 3), (3, 6), (6, 9), (9, 10)]
    assert assistant.digest_windows(lines, 10**6) == [(0, 10)]
    assert assistant.digest_windows([], 100) == [(0, 0)]
    # A line larger than the budget is a window of its own, never cut.
    assert assistant.digest_windows(lines, 1) == [(n, n + 1) for n in range(10)]


def test_the_digest_block_and_the_words_are_as_the_chapter_says():
    assert prompts.digest_block("") == ""
    assert prompts.digest_block("1. x").startswith(prompts.RECORD_HEADING + "\n1. x")
    told = prompts.digest_input(2, 3, 600.0, 900.0, "[1] words", "")
    assert told.startswith("Window 2 of 3, from [00:10:00] to [00:15:00]")
    assert "(none transcribed)" in prompts.digest_input(1, 1, 0.0, 9.0, "", "")
    assert "(said), (seen), or (both)" in prompts.DIGEST
    assert "Unchanged" in prompts.DIGEST and "Unchanged:" in prompts.RECORD_NEW
    assert "numbered lines only" in prompts.DIGEST_FORMAT
    assert prompts.DIGEST_CAP == 1200 and prompts.DIGEST_WINDOW_TOKENS == 12000


# With a database ----------------------------------------------------------------------


@pytest.mark.django_db
def test_a_summary_makes_the_digest_and_is_written_from_it(ready, person, monkeypatch):
    transcript = ready.transcript
    described(transcript, 0.0, 300.0, "A doorway.")
    described(transcript, 300.0, 600.0, "Unchanged: the doorway.")
    described(transcript, 600.0, 900.0, "A car.")
    asked = answering(
        monkeypatch,
        [
            "1. [00:00:00]-[00:05:00] (both) An officer at a doorway.",
            "Summary: a doorway [00:00:00] and a car [00:10:00].",
        ],
    )
    summary = Summary.objects.create(
        recording=ready,
        asked_by=person,
        template_name="Standard summary",
        length="short",
    )
    assistant.write_summary(summary.pk)
    summary.refresh_from_db()
    assert summary.state == assistant.DONE and summary.digest_parts == 1
    assert summary.moments_used == 3 and summary.stage == ""
    assert len(asked) == 2

    # The Digest's call: the fixed instructions, the window with its camera
    # lines, no thinking, the part cap.
    digest_call = asked[0]
    system = digest_call["messages"][0]["content"]
    assert prompts.DIGEST in system and system.endswith(
        prompts.DIGEST_FORMAT + "\n\n" + prompts.CAMERA_RULES
    )
    user = digest_call["messages"][-1]["content"]
    assert "Window 1 of 1, from [00:00:00] to [00:15:00]" in user
    assert "[2] [00:00:12] Speaker 2: Look at that, right there." in user
    assert "[00:05:00]-[00:10:00] [camera] Unchanged: the doorway." in user
    assert digest_call["thinking"] is False
    assert digest_call["max_completion_tokens"] == 1200

    # The summary's call: the transcript, the Digest in place of the block.
    user = asked[1]["messages"][-1]["content"]
    assert prompts.RECORD_HEADING in user and "An officer at a doorway." in user
    assert prompts.CAMERA_HEADING not in user and "[camera]" not in user
    assert "[2] [00:00:12] Speaker 2" in user
    assert "The record of this recording is complete" in user
    assert summary.citations == {"[00:00:00]": 0.0, "[00:10:00]": 600.0}

    (part,) = DigestPart.objects.all()
    assert part.number == 1 and part.moments_used == 3 and part.model == "the-model"
    assert part.text.startswith("1. [00:00:00]")
    assert (part.span_start, part.span_end) == (0.0, 900.0)
    assert assistant.digest_current(transcript) is True
    rows = Row.objects.filter(category="llm").order_by("at")
    assert [row.details["feature"] for row in rows] == ["digest", "summary"]
    assert rows[0].details["part"] == 1 and rows[0].details["parts"] == 1
    assert "doorway" not in json.dumps(rows[0].details)

    # The next summary finds the Digest current and makes no part again.
    again = Summary.objects.create(
        recording=ready,
        asked_by=person,
        template_name="Standard summary",
        length="short",
    )
    assistant.write_summary(again.pk)
    assert (
        len(asked) == 3
        and prompts.RECORD_HEADING in asked[2]["messages"][-1]["content"]
    )

    # A description edited: the part is stale, and the next summary remakes it.
    moment = transcript.moments.get(at=600.0)
    moment.text = "A car with its door open."
    moment.edited = True
    moment.save()
    assert assistant.digest_current(transcript) is False
    third = Summary.objects.create(
        recording=ready,
        asked_by=person,
        template_name="Standard summary",
        length="short",
    )
    assistant.write_summary(third.pk)
    assert len(asked) == 5 and prompts.DIGEST in asked[3]["messages"][0]["content"]
    assert DigestPart.objects.count() == 1

    # Digests off: the block as before, and no part made.
    settings_store.set_to("digests_available", False)
    DigestPart.objects.all().delete()
    fourth = Summary.objects.create(
        recording=ready,
        asked_by=person,
        template_name="Standard summary",
        length="short",
    )
    assistant.write_summary(fourth.pk)
    fourth.refresh_from_db()
    assert fourth.digest_parts == 0 and DigestPart.objects.count() == 0
    assert prompts.CAMERA_HEADING in asked[5]["messages"][-1]["content"]


@pytest.mark.django_db
def test_a_transcript_too_long_is_summarised_from_the_digest_alone(
    ready, person, monkeypatch
):
    transcript = ready.transcript
    described(transcript, 0.0, 900.0, "A doorway.")
    asked = answering(
        monkeypatch, ["1. [00:00:00]-[00:15:00] (both) A doorway.", "Summary."]
    )
    # A window too small for the transcript, large enough for the Digest:
    # three lines of about 3,300 tokens each against a window of 8,000.
    long = "many words " * 1200
    for one in transcript.segments.all():
        one.text = long
        one.save(update_fields=["text"])
    settings_store.set_to("engine_window_tokens", 8000)
    settings_store.set_to("digest_window_tokens", 4000)
    settings_store.set_to("digest_part_tokens", 300)
    summary = Summary.objects.create(
        recording=ready,
        asked_by=person,
        template_name="Standard summary",
        length="short",
    )
    assistant.write_summary(summary.pk)
    summary.refresh_from_db()
    assert summary.state == assistant.DONE, summary.reason_class
    # Three windows, one line each, then the summary without the transcript.
    assert len(asked) == 4 and DigestPart.objects.count() == 3
    user = asked[3]["messages"][-1]["content"]
    assert prompts.RECORD_HEADING in user and "many words" not in user

    # Without a Digest the same transcript is refused as too long, as before.
    settings_store.set_to("digests_available", False)
    refused = Summary.objects.create(
        recording=ready,
        asked_by=person,
        template_name="Standard summary",
        length="short",
    )
    assistant.write_summary(refused.pk)
    refused.refresh_from_db()
    assert refused.state == assistant.FAILED and refused.reason_class == engine.TOO_LONG


@pytest.mark.django_db
def test_the_chat_is_told_the_digest_and_the_descriptions_at_the_times_asked(
    ready, person, monkeypatch
):
    transcript = ready.transcript
    described(transcript, 0.0, 300.0, "A doorway.")
    described(transcript, 300.0, 600.0, "A car.")
    described(transcript, 600.0, 900.0, "A bag on the seat.")
    DigestPart.objects.create(
        transcript=transcript,
        number=1,
        span_start=0.0,
        span_end=900.0,
        signature="x",
        text="1. [00:00:00]-[00:15:00] (both) A stop.",
        moments_used=3,
    )
    asked = answering(monkeypatch, ["The camera shows a bag [00:10:00]."])
    chat = Chat.objects.create(recording=ready, asked_by=person)
    turn = ChatTurn.objects.create(
        chat=chat, number=1, question="what was on the seat at 12:40?"
    )
    assistant.answer_turn(turn.pk)
    turn.refresh_from_db()
    assert turn.state == assistant.DONE
    user = asked[0]["messages"][-1]["content"]
    assert prompts.RECORD_HEADING in user and "(both) A stop." in user
    assert prompts.CAMERA_HEADING not in user
    # 12:40 is 760 s, inside the third span: that description, and no other.
    assert prompts.NEAR_HEADING in user
    assert "[00:10:00]-[00:15:00] [camera] A bag on the seat." in user
    assert "[camera] A doorway." not in user
    assert asked[0]["messages"][0]["content"].endswith(prompts.CAMERA_RULES)
    assert turn.citations == {"[00:10:00]": 600.0}

    # No time in the question: the Digest alone for the picture.
    second = ChatTurn.objects.create(chat=chat, number=2, question="and then?")
    assistant.answer_turn(second.pk)
    user = asked[1]["messages"][-1]["content"]
    assert prompts.RECORD_HEADING in user and prompts.NEAR_HEADING not in user
    # The setting at 0: never the descriptions.
    settings_store.set_to("chat_descriptions_near", 0)
    third = ChatTurn.objects.create(chat=chat, number=3, question="at 12:40?")
    assistant.answer_turn(third.pk)
    assert prompts.NEAR_HEADING not in asked[2]["messages"][-1]["content"]
    assert prompts.near_descriptions([], [760.0], 6) == []


@pytest.mark.django_db
def test_the_case_chat_reads_a_digest_after_each_transcript_and_alone_when_too_big(
    person, tmp_path, settings, monkeypatch
):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("chat_across_cases", True)
    case = Case.objects.create(owner=person, name="Ramirez")
    first = a_recording(person, tmp_path, settings, case=case, title="First")
    second = a_recording(person, tmp_path, settings, case=case, title="Second")
    DigestPart.objects.create(
        transcript=first.transcript,
        number=1,
        span_end=900.0,
        signature="x",
        text="1. [00:00:00]-[00:15:00] (both) The first stop.",
    )
    asked = answering(monkeypatch, ["An answer [00:00:00]."])
    from core.case_chat import CaseChat, CaseChatTurn

    chat = CaseChat.objects.create(case=case, asked_by=person)
    turn = CaseChatTurn.objects.create(chat=chat, number=1, question="what happened?")
    case_chat.answer_case_turn(turn.pk)
    turn.refresh_from_db()
    assert turn.state == assistant.DONE, turn.reason_class
    user = asked[0]["messages"][-1]["content"]
    # The first recording: its transcript, then its Digest; the second: the
    # transcript alone. The rules follow the format because a Digest is present.
    assert "Recording 1 of 2: First" in user and "Recording 2 of 2: Second" in user
    assert user.count(prompts.RECORD_HEADING) == 1
    assert user.index("Look at that") < user.index(prompts.RECORD_HEADING)
    assert "(both) The first stop." in user
    assert asked[0]["messages"][0]["content"].endswith(prompts.CAMERA_RULES)
    assert turn.readings[0]["digest"] is True and turn.readings[1]["digest"] is False

    # Over the hours ceiling: the recording with a Digest contributes the
    # Digest alone, its hours no longer counted, and the question goes on.
    for one in (first, second):
        one.duration_seconds = 4 * 3600.0
        one.save(update_fields=["duration_seconds"])
    settings_store.set_to("case_chat_hours", 6)
    turn = CaseChatTurn.objects.create(chat=chat, number=2, question="and?")
    case_chat.answer_case_turn(turn.pk)
    turn.refresh_from_db()
    assert turn.state == assistant.DONE, turn.reason_detail
    user = asked[1]["messages"][-1]["content"]
    assert "Recording 1 of 2: First" in user and "(both) The first stop." in user
    first_block = user[user.index("Recording 1 of 2") : user.index("Recording 2 of 2")]
    assert "Look at that" not in first_block and "Look at that" in user
    # Both over, and only one Digest: too large, as before.
    for one in (first, second):
        one.duration_seconds = 8 * 3600.0
        one.save(update_fields=["duration_seconds"])
    turn = CaseChatTurn.objects.create(chat=chat, number=3, question="more?")
    case_chat.answer_case_turn(turn.pk)
    turn.refresh_from_db()
    assert turn.state == assistant.FAILED
    assert turn.reason_class == case_chat.CASE_TOO_LARGE


@pytest.mark.django_db
def test_the_stamp_is_read_from_two_frames_checked_and_told_to_the_model(
    ready, person, monkeypatch
):
    transcript = ready.transcript
    grabbed = []

    def grab(source, folder, times, *, height, timeout=120):
        grabbed.append((times, height))
        frame = Path(folder) / "frame.jpg"
        frame.write_bytes(b"\xff\xd8jpeg")
        return [frame]

    monkeypatch.setattr(media, "grab_frames", grab)
    asked = answering(
        monkeypatch,
        [
            json.dumps(
                {
                    "date": "06/07/2025",
                    "time": "21:56:19",
                    "camera": "BWC2-098679",
                    "other": "MOTOROLA SOLUTIONS",
                }
            ),
            json.dumps(
                {"date": "06/07/2025", "time": "21:57:20", "camera": "", "other": ""}
            ),
        ],
    )
    stamp = assistant.read_stamp(transcript, asked_by=person)
    assert stamp["date"] == "06/07/2025" and stamp["time"] == "21:56:19"
    assert stamp["camera"] == "BWC2-098679" and stamp["at"] == 2.0
    assert stamp["checked"] is True
    transcript.refresh_from_db()
    assert transcript.stamp == stamp
    # Two frames at the look-closer height, two seconds in and a minute on.
    assert grabbed == [([2.0], 720), ([62.0], 720)]
    system = asked[0]["messages"][0]["content"]
    assert prompts.STAMP in system and asked[0]["schema"] == prompts.STAMP_SCHEMA
    assert asked[0]["thinking"] is False and asked[0]["temperature"] == 0.0
    parts = asked[0]["messages"][-1]["content"]
    assert parts[0]["type"] == "text" and "[00:00:02]" in parts[0]["text"]
    assert parts[1]["type"] == "image_url"
    row = Row.objects.filter(category="llm").latest("at")
    assert row.details["feature"] == "stamp" and row.details["checked"] is True
    assert "098679" not in json.dumps(row.details)
    # What the model is told, and what Details and the export say.
    line = assistant.clock_line(transcript)
    assert "21:56:19 at [00:00:02]" in line and "was 21:56:17" in line
    assert "camera BWC2-098679" in line
    assert "not checked" not in line

    # A second frame whose clock did not move as the recording did: the
    # time is dropped, the camera id kept, and the stamp says so.
    transcript.stamp = None
    transcript.save(update_fields=["stamp"])
    asked.clear()
    answering(
        monkeypatch,
        [
            json.dumps({"date": "", "time": "21:56:19", "camera": "BWC2", "other": ""}),
            json.dumps({"date": "", "time": "21:56:19", "camera": "BWC2", "other": ""}),
        ],
    )
    stamp = assistant.read_stamp(transcript, asked_by=person)
    assert stamp["time"] == "" and stamp["camera"] == "BWC2" and not stamp["checked"]
    # Nothing read at all: an empty stamp, kept so it is not read again.
    transcript.stamp = None
    transcript.save(update_fields=["stamp"])
    answering(monkeypatch, ["not json at all"])
    assert assistant.read_stamp(transcript, asked_by=person) == {}
    transcript.refresh_from_db()
    assert transcript.stamp == {} and assistant.clock_line(transcript) == ""


@pytest.mark.django_db
def test_the_details_and_the_state_say_the_digest_exists_but_never_show_it(
    ready, person, client
):
    signed_in(client, person)
    transcript = ready.transcript
    described(transcript, 0.0, 900.0, "A doorway.")
    from django.utils import timezone

    DigestPart.objects.create(
        transcript=transcript,
        number=1,
        span_end=900.0,
        signature="x",
        text="1. [00:00:00]-[00:15:00] (both) A private line.",
        moments_used=1,
        made_at=timezone.now(),
    )
    transcript.stamp = {
        "date": "06/07/2025",
        "time": "21:56:19",
        "camera": "BWC2-098679",
        "at": 2.0,
        "checked": True,
    }
    transcript.save(update_fields=["stamp"])
    rows = dict(client.get(f"/recording/{ready.pk}/details").json()["rows"])
    assert (
        rows["Digest"].startswith("made ")
        and "1 description, in 1 part" in rows["Digest"]
    )
    assert rows["Camera stamp"] == (
        "06/07/2025, 21:56:19 at [00:00:02], camera BWC2-098679 "
        "(checked against a second frame)"
    )
    assert "private line" not in json.dumps(rows)
    state = client.get(f"/recording/{ready.pk}/assistant").json()
    digest = state["cue_runs"]["digest"]
    assert digest["parts"] == 1 and digest["moments"] == 1 and digest["made"]
    assert "private line" not in json.dumps(state)
    assert state["cue_runs"]["stamp"].startswith("06/07/2025")
    # The export's processing record carries the stamp, never the Digest.
    from core import exports

    text = exports.plain_text(ready)
    assert "private line" not in text
    word = exports.word(ready, "asker")
    import io
    import zipfile

    document = zipfile.ZipFile(io.BytesIO(word)).read("word/document.xml").decode()
    assert "Camera stamp" in document and "BWC2-098679" in document
    assert "private line" not in document
