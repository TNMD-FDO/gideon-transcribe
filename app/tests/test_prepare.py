"""Prepared videos (Phase 4, chapter 7, v1.52.0).

The rules checked here: a video's preparation is queued as its transcript
lands and waits for the Playback copy; the preparation makes the record and
the Digest with the count kept as it goes, writes one row, and ends prepared
or not; a summary or a chat question on a video not yet prepared prepares
it first and waits for a preparation already running; the Batch's mail waits
for the Batch's videos and says how they went; the batch page and the case
page say the count and the time left, and the case's press queues the rest;
an Admin sees the digest under Details; nobody presses anything on the
recording page.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from core import assistant, engine, mail, media, settings_store, tasks
from core.assistant import DigestPart, Moment
from core.audit import Row
from core.cases import Case
from core.jobs import Segment, Transcript
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording

PASSWORD = "a-long-enough-password"


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("asker", PASSWORD)


def a_recording(
    person, tmp_path, settings, case=None, title="Stop", batch=None, video=True
):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"
    recording = Recording.objects.create(
        batch=batch or Batch.objects.create(user=person),
        user=person,
        case=case,
        title=title,
        original_filename="bodycam.mp4" if video else "call.m4a",
        media_state=MediaState.READY,
        duration_seconds=900.0,
        diarize=True,
        playback_ready=True,
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
    settings_store.set_to("moment_interval_seconds", 300)
    settings_store.set_to("stamp_available", False)
    return recording


@pytest.fixture
def ready(person, tmp_path, settings):
    return a_recording(person, tmp_path, settings)


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def engine_answering(monkeypatch, answers):
    monkeypatch.setattr(engine, "is_reachable", lambda: True)
    monkeypatch.setattr(engine, "address", lambda: "http://gideon-generator:8000/v1")
    asked = []
    queue = list(answers)

    def complete(messages, **options):
        asked.append({"messages": messages, **options})
        return {
            "text": queue.pop(0) if queue else "more",
            "finish_reason": "stop",
            "input_tokens": 1,
            "output_tokens": 1,
            "model": "the-model",
        }

    monkeypatch.setattr(engine, "complete", complete)
    return asked


def no_ffmpeg(monkeypatch):
    from core import moment_scan

    monkeypatch.setattr(moment_scan, "scene_changes", lambda *a, **k: [100.0])
    monkeypatch.setattr(moment_scan, "loud_seconds", lambda *a, **k: [])

    def cut(source, target, start, end, *, fps, height, timeout=120):
        Path(target).write_bytes(b"\x00\x00\x00\x18ftypmp42")

    monkeypatch.setattr(media, "cut_for_description", cut)


# Without a database ------------------------------------------------------------------


def test_the_words_for_a_wait():
    assert assistant.about(30) == "under a minute"
    assert assistant.about(90) == "about 2 minutes"
    assert assistant.about(60 * 18) == "about 18 minutes"
    assert assistant.about(3600 * 2 + 60 * 10) == "about 2 h 10 min"
    assert assistant.about(3600 * 3) == "about 3 h"


# With a database ----------------------------------------------------------------------


@pytest.mark.django_db
def test_the_preparation_is_queued_as_the_transcript_lands_and_waits_for_the_copy(
    ready, person, monkeypatch
):
    deferred = []
    monkeypatch.setattr(
        tasks.prepare_video, "defer", lambda **fields: deferred.append(fields)
    )
    transcript = ready.transcript
    assert assistant.queue_preparation(ready) is True
    transcript.refresh_from_db()
    assert transcript.prepare_state == assistant.QUEUED
    assert deferred == [{"transcript_id": str(transcript.pk)}]
    # Sound alone, or the record off: nothing queued.
    settings_store.set_to("picture_record_available", False)
    assert assistant.queue_preparation(ready) is False
    settings_store.set_to("picture_record_available", True)

    # The task waits a minute at a time for the Playback copy.
    ready.playback_ready = False
    ready.save(update_fields=["playback_ready"])
    later = []

    class Configured:
        def __init__(self, **options):
            self.options = options

        def defer(self, **fields):
            later.append((self.options, fields))

    monkeypatch.setattr(tasks.prepare_video, "configure", lambda **o: Configured(**o))
    ran = []
    monkeypatch.setattr(assistant, "prepare", lambda t, **k: ran.append(t.pk) or True)
    tasks.prepare_video(str(transcript.pk))
    assert later == [
        (
            {"schedule_in": {"seconds": 60}},
            {"transcript_id": str(transcript.pk), "attempt": 2},
        )
    ]
    assert ran == []
    ready.playback_ready = True
    ready.save(update_fields=["playback_ready"])
    tasks.prepare_video(str(transcript.pk), attempt=2)
    assert ran == [transcript.pk]
    # A transcript no longer queued (prepared meanwhile, or gone) is left alone.
    transcript.prepare_state = assistant.DONE
    transcript.save(update_fields=["prepare_state"])
    tasks.prepare_video(str(transcript.pk))
    assert ran == [transcript.pk]


@pytest.mark.django_db
def test_the_preparation_makes_the_record_and_the_digest_and_keeps_count(
    ready, person, monkeypatch
):
    no_ffmpeg(monkeypatch)
    asked = engine_answering(
        monkeypatch,
        [
            "A doorway.",
            "Unchanged: the doorway.",
            "A car.",
            "A bag.",
            "1. [00:00:00]-[00:15:00] (both) A stop.",
        ],
    )
    transcript = ready.transcript
    counts = []
    real_tick = assistant._prepare_tick

    def tick(t):
        real_tick(t)
        counts.append(t.prepare_done)

    monkeypatch.setattr(assistant, "_prepare_tick", tick)
    assert assistant.prepare(transcript, asked_by=person) is True
    transcript.refresh_from_db()
    # Cut at the one change point (100 s) with a 300 s ceiling: 0-100,
    # 100-300, 300-600, 600-900, then the one Digest part: five things.
    assert transcript.prepare_state == assistant.DONE and transcript.prepared_at
    assert transcript.prepare_total == 5 and transcript.prepare_done == 5
    assert counts == [1, 2, 3, 4, 5]
    assert transcript.change_points == [100.0]
    assert len(asked) == 5
    assert (
        Moment.objects.filter(source=Moment.INTERVAL, state=assistant.DONE).count() == 4
    )
    assert DigestPart.objects.count() == 1
    assert assistant.prepared(transcript) is True
    row = Row.objects.get(event="Video prepared")
    assert row.details["descriptions"] == 4 and row.details["parts"] == 1
    assert row.outcome == "success"
    assert assistant.prepare_words(transcript) == ("Prepared", "ok")
    said = assistant.prepare_json(transcript)
    assert said["state"] == "done" and said["seconds_left"] == 0

    # A second preparation finds nothing left: no calls, the row written again.
    assert assistant.prepare(transcript, asked_by=person) is True
    assert len(asked) == 5
    assert Row.objects.filter(event="Video prepared").count() == 2

    # The engine gone: not prepared, the reason kept, the row a failure.
    monkeypatch.setattr(engine, "is_reachable", lambda: False)
    transcript.moments.all().delete()
    assert assistant.prepare(transcript, asked_by=person) is False
    transcript.refresh_from_db()
    assert transcript.prepare_state == assistant.FAILED
    assert transcript.prepare_reason == "llm_unreachable"
    assert assistant.prepare_words(transcript)[1] == "danger"
    assert assistant.prepare_words(transcript)[0].startswith("Not prepared: ")


@pytest.mark.django_db
def test_a_preparation_left_by_a_worker_that_stopped_is_taken_up_again(
    ready, person, monkeypatch
):
    """An upgrade restarts the workers part-way through a preparation. The
    queue gives the job back, the task takes a transcript still marked
    running, and the spans the last attempt left queued, running or failed
    are described afresh rather than counted as taken (v1.52.1)."""
    no_ffmpeg(monkeypatch)
    asked = engine_answering(
        monkeypatch,
        [
            "A doorway.",
            "Unchanged: the doorway.",
            "A car.",
            "A bag.",
            "1. [00:00:00]-[00:15:00] (both) A stop.",
        ],
    )
    transcript = ready.transcript
    transcript.prepare_state = assistant.PREPARING
    transcript.prepare_total = 5
    transcript.prepare_done = 1
    transcript.save(update_fields=["prepare_state", "prepare_total", "prepare_done"])
    left = (
        (0.0, 100.0, assistant.FAILED),
        (100.0, 300.0, assistant.RUNNING),
        (300.0, 600.0, assistant.QUEUED),
    )
    for start, end, state in left:
        Moment.objects.create(
            transcript=transcript,
            at=start,
            span_start=start,
            span_end=end,
            source=Moment.INTERVAL,
            state=state,
        )
    tasks.prepare_video(str(transcript.pk))
    transcript.refresh_from_db()
    assert transcript.prepare_state == assistant.DONE
    assert transcript.prepare_total == 5 and transcript.prepare_done == 5
    assert len(asked) == 5
    standing = Moment.objects.filter(source=Moment.INTERVAL)
    assert standing.count() == 4
    assert standing.filter(state=assistant.DONE).count() == 4


@pytest.mark.django_db
def test_the_estimate_comes_from_the_engines_own_pace(ready, person):
    transcript = ready.transcript
    plan = assistant.prepare_plan(ready, transcript)
    # No pace measured yet: the guess, three spans at 300 s, then the one
    # Digest part those descriptions will make.
    assert plan["descriptions"] == 3 and plan["estimated"] is True
    assert plan["parts"] == 1
    assert plan["seconds"] == int(
        round(3 * assistant.MOMENT_SECONDS_GUESS + assistant.DIGEST_SECONDS_GUESS)
    )
    for n in range(3):
        Moment.objects.create(
            transcript=transcript,
            at=float(n),
            span_start=float(n),
            span_end=float(n + 1),
            source=Moment.INTERVAL,
            state=assistant.DONE,
            text="x",
            seconds=10.0,
            described_at="2026-09-12T12:00:00Z",
        )
    assert assistant.seconds_per_description() == 10.0
    plan = assistant.prepare_plan(ready, transcript)
    assert plan["parts"] == 1
    assert plan["seconds"] == int(
        round(plan["descriptions"] * 10.0 + assistant.seconds_per_part())
    )
    transcript.prepare_state = assistant.PREPARING
    transcript.prepare_total = 10
    transcript.prepare_done = 4
    transcript.save()
    assert assistant.seconds_left(transcript) == 60
    assert assistant.prepare_words(transcript) == (
        "Preparing 4 of 10, about 1 minute",
        "warn",
    )


@pytest.mark.django_db
def test_a_chat_question_waits_for_a_preparation_already_running(
    ready, person, monkeypatch
):
    from core.assistant import Chat, ChatTurn

    transcript = ready.transcript
    transcript.prepare_state = assistant.PREPARING
    transcript.save(update_fields=["prepare_state"])
    asked = engine_answering(monkeypatch, ["An answer."])
    slept = []

    def sleep(seconds):
        slept.append(seconds)
        # The other lane finishes: prepared, with a Digest.
        transcript.prepare_state = assistant.DONE
        transcript.save(update_fields=["prepare_state"])

    monkeypatch.setattr(assistant.time, "sleep", sleep)
    chat = Chat.objects.create(recording=ready, asked_by=person)
    turn = ChatTurn.objects.create(chat=chat, number=1, question="what happened?")
    assistant.answer_turn(turn.pk)
    turn.refresh_from_db()
    assert turn.state == assistant.DONE and slept == [5] and len(asked) == 1


@pytest.mark.django_db
def test_the_batch_mail_waits_for_the_videos_and_says_how_they_went(
    person, tmp_path, settings, monkeypatch
):
    sent = []
    monkeypatch.setattr(
        mail, "send_to_person", lambda *a, **k: sent.append((a, k)) or True
    )
    batch = Batch.objects.create(user=person, email_when_done=True)
    video = a_recording(person, tmp_path, settings, batch=batch, title="Cam")
    a_recording(
        person, tmp_path / "two", settings, batch=batch, title="Call", video=False
    )
    from core.jobs import Job, JobState

    for recording in batch.recordings.all():
        Job.objects.create(recording=recording, batch=batch, state=JobState.DONE)
    transcript = video.transcript
    transcript.prepare_state = assistant.QUEUED
    transcript.save(update_fields=["prepare_state"])
    # Finished transcribing, but a video still preparing: no mail yet.
    assert mail.batch_finished(batch) is False and sent == []
    from django.utils import timezone

    transcript.prepare_state = assistant.DONE
    transcript.prepare_started = timezone.now()
    transcript.prepared_at = transcript.prepare_started + timezone.timedelta(minutes=18)
    transcript.save()
    assert mail.batch_finished(batch) is True
    batch.refresh_from_db()
    assert batch.mail_sent_at is not None and len(sent) == 1
    body = sent[0][0][3]
    assert "1 video prepared for summaries and chat in 18 minutes." in body
    assert "2 transcribed" in body


@pytest.mark.django_db
def test_the_batch_page_and_the_case_page_say_the_count_and_the_time_left(
    person, tmp_path, settings, client, monkeypatch
):
    settings_store.set_to("folder_management", True)
    case = Case.objects.create(owner=person, name="Ramirez")
    batch = Batch.objects.create(user=person)
    video = a_recording(person, tmp_path, settings, case=case, batch=batch, title="Cam")
    transcript = video.transcript
    transcript.prepare_state = assistant.PREPARING
    transcript.prepare_total = 10
    transcript.prepare_done = 4
    transcript.save()
    signed_in(client, person)
    state = client.get(f"/batch/{batch.pk}/state").json()
    (row,) = state["recordings"]
    assert row["prepare"]["state"] == "running" and row["prepare"]["done"] == 4
    assert row["prepare"]["line"].startswith("Preparing 4 of 10")
    assert state["preparing"]["count"] == 1 and state["preparing"]["about"]
    page = client.get(f"/case/{case.pk}").content.decode()
    assert "<th>Prepared</th>" in page and "Preparing 4 of 10" in page
    assert "Prepare them now" not in page

    # Not prepared: the case page offers the press, which queues them.
    transcript.prepare_state = ""
    transcript.save(update_fields=["prepare_state"])
    page = client.get(f"/case/{case.pk}").content.decode()
    assert "1 video not yet prepared for summaries and chat" in page
    assert "Prepare them now" in page
    deferred = []
    monkeypatch.setattr(
        tasks.prepare_video, "defer", lambda **fields: deferred.append(fields)
    )
    answer = client.post(f"/case/{case.pk}/prepare")
    assert answer.status_code == 302
    transcript.refresh_from_db()
    assert transcript.prepare_state == assistant.QUEUED
    assert deferred == [{"transcript_id": str(transcript.pk)}]
    state = client.get(f"/batch/{batch.pk}/state").json()
    assert state["recordings"][0]["prepare"]["state"] == "queued"
    assert state["preparing"]["count"] == 1


@pytest.mark.django_db
def test_an_admin_sees_the_digest_under_details(ready, person, client):
    signed_in(client, person)
    transcript = ready.transcript
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
    Moment.objects.create(
        transcript=transcript,
        at=0.0,
        span_start=0.0,
        span_end=300.0,
        source=Moment.INTERVAL,
        state=assistant.DONE,
        text="A doorway, described.",
        model="the-model",
    )
    body = client.get(f"/recording/{ready.pk}/details").json()
    digest = body["digest"]
    assert digest["parts"][0]["text"].startswith("1. [00:00:00]")
    assert digest["descriptions"][0]["span"] == "[00:00:00]-[00:05:00]"
    assert digest["descriptions"][0]["text"] == "A doorway, described."
    assert digest["templates"]["digest"] == 1 and "moment" in digest["templates"]
    page = client.get(f"/recording/{ready.pk}").content.decode()
    assert 'id="admin-digest"' in page
    # The Digest's instructions are a template on the Templates page.
    assert assistant.PromptTemplate.DIGEST in assistant.PromptTemplate.DEFAULTS
    templates = client.get("/panel/templates").content.decode()
    assert "Digest" in templates
