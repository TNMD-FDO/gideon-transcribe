"""The performance pass of 14 October 2026 (v1.134.0): the queue's rules, kept.

Findings 4, 5, 24, 25, 39 and 40 of the audit page: a Run the service's list
left out is asked for by its id before it counts as missing; the poll's
queries do not grow with Runs that have nothing new, and it waits thirty
seconds while everything is queued; the submit body streams from the file;
the default worker runs two jobs and the workers are health-checked every
five minutes; the two-sides match walks Side 2 with a pointer and finds what
it found before.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from core import queue, tasks, whisperx
from core.jobs import Job, JobState, Reason, Run
from core.models import User
from core.recordings import Batch, MediaState, Recording, Side
from django.db import connection
from django.test.utils import CaptureQueriesContext

HERE = Path(__file__).resolve().parents[2]
PASSWORD = "a-long-enough-password"


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("poller", PASSWORD)


def a_recording(person, title="one"):
    return Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        title=title,
        original_filename="one.mp4",
        media_state=MediaState.READY,
    )


def a_job(recording, service_job_id, state="queued"):
    side = Side.objects.create(recording=recording, number=1, kind=Side.WHOLE, name="")
    job = Job.objects.create(recording=recording, batch=recording.batch)
    Run.objects.create(job=job, side=side, service_job_id=service_job_id, state=state)
    return job


# 4. A Run absent from the list is asked for before it is taken for lost ---------------


def test_a_run_the_list_left_out_is_asked_for_before_it_counts_as_missing(
    person, monkeypatch
):
    job = a_job(a_recording(person), "deep-in-the-line")
    asked = []

    def told(job_id, lane=""):
        asked.append((job_id, lane))
        return {"id": job_id, "state": "queued", "position": 250}

    monkeypatch.setattr(whisperx, "status_of", told)
    for _ in range(queue.POLLS_BEFORE_MISSING + 2):
        queue.take_state_from(job, {})
    run = job.runs.get()
    # Asked each time, and the answer is the Run's state: no miss counted.
    assert asked == [("deep-in-the-line", "")] * (queue.POLLS_BEFORE_MISSING + 2)
    assert run.missing_polls == 0 and run.position == 250
    job.refresh_from_db()
    assert job.state == JobState.QUEUED

    # A service that has no such job is the miss, as before.
    monkeypatch.setattr(whisperx, "status_of", lambda job_id, lane="": None)
    monkeypatch.setattr(whisperx, "delete", lambda job_id, lane="": None)
    for _ in range(queue.POLLS_BEFORE_MISSING):
        queue.take_state_from(job, {})
    job.refresh_from_db()
    assert job.state == JobState.FAILED
    assert job.failure_class == Reason.SERVICE_RESTARTED


def test_status_of_reads_the_one_answer_and_a_404_is_none(monkeypatch):
    answers = {"here": (200, {"id": "here", "state": "running"}), "gone": (404, None)}
    monkeypatch.setattr(
        whisperx, "_request", lambda method, path, **rest: answers[path.rsplit("/")[-1]]
    )
    assert whisperx.status_of("here")["state"] == "running"
    assert whisperx.status_of("gone") is None
    monkeypatch.setattr(whisperx, "_request", lambda method, path, **rest: (401, None))
    with pytest.raises(whisperx.ServiceError):
        whisperx.status_of("here")


# 5. The poll's cost does not grow with Runs that have nothing new --------------------


def test_the_poll_of_ten_jobs_costs_no_more_when_nothing_changed(person):
    for number in range(10):
        a_job(a_recording(person, title=f"r{number}"), f"s{number}")
    states = {
        f"s{number}": {
            "state": "queued",
            "stage": "",
            "percent": None,
            "position": number + 1,
            "audio_minutes_ahead": 5.0 * number,
        }
        for number in range(10)
    }

    def poll():
        with CaptureQueriesContext(connection) as caught:
            for job in queue.live_jobs():
                queue.take_state_from(job, states)
        return caught.captured_queries

    first = poll()
    second = poll()
    # The first poll writes each Run's place in the line, with the fields
    # that changed; the second has nothing to write.
    updates = [one["sql"] for one in first if one["sql"].startswith("UPDATE")]
    assert len(updates) == 10
    assert all('"position"' in one and '"settings_used"' not in one for one in updates)
    assert not any(one["sql"].startswith("UPDATE") for one in second)
    # The Runs come with the Jobs: two queries for the ten, not one per Job.
    assert len(second) == 2


def test_the_poll_waits_thirty_seconds_while_everything_is_queued(person):
    job = a_job(a_recording(person), "s1")
    assert tasks._poll_cadence() == tasks.POLL_SECONDS_WHILE_QUEUED
    Run.objects.filter(job=job).update(state="running")
    assert tasks._poll_cadence() == tasks.POLL_SECONDS


def test_the_poll_is_locked_against_running_twice(monkeypatch):
    configured = {}

    class Configured:
        def __init__(self, **options):
            configured.update(options)

        def defer(self, **kwargs):
            configured["deferred"] = kwargs

    monkeypatch.setattr(tasks.poll_service, "configure", lambda **o: Configured(**o))
    tasks._poll_again(1, when=7)
    # The queueing lock keeps one poll waiting; the plain lock keeps a waiting
    # poll from starting while one runs, now that the worker runs two jobs.
    assert configured["lock"] == tasks.POLL_LOCK
    assert configured["queueing_lock"] == tasks.POLL_LOCK
    assert configured["schedule_in"] == {"seconds": 7}
    assert configured["deferred"] == {"attempt": 1}


# 25. The speakers pass writes its lines in batches ----------------------------------


def test_the_speakers_pass_writes_its_lines_in_one_batch(person):
    from core.jobs import Segment, Transcript

    recording = a_recording(person)
    side = Side.objects.create(recording=recording, number=1, kind=Side.WHOLE, name="")
    transcript = Transcript.objects.create(recording=recording, language="en")
    for number in range(40):
        Segment.objects.create(
            transcript=transcript,
            side=side,
            start=number * 5.0,
            end=number * 5.0 + 4.0,
            text=f"line {number}",
            speaker="Speaker 1",
            speaker_label="S0",
        )
    turns = [
        {"start": number * 5.0, "end": number * 5.0 + 4.5, "speaker": f"S{number % 2}"}
        for number in range(40)
    ]
    count: dict = {}
    with CaptureQueriesContext(connection) as caught:
        changed = queue.apply_turns(transcript, side, turns, False, count)
    # Every other line moves to Speaker 2; the first speaker's lines keep
    # their name and are not written.
    assert changed == 20 and count == {side.pk: 2}
    updates = [one for one in caught.captured_queries if "UPDATE" in one["sql"]]
    assert len(updates) == 1
    assert transcript.segments.filter(speaker="Speaker 2").count() == 20


# 24. The submit body streams from the file --------------------------------------------


def test_the_submit_body_streams_from_the_file(tmp_path):
    audio = tmp_path / "side.wav"
    sound = b"RIFF" + b"x" * (3 * whisperx.SEND_CHUNK + 5)
    audio.write_bytes(sound)
    body, content_type = whisperx._multipart(audio, {"model": "large-v3"})
    assert isinstance(body, whisperx.StreamedBody)
    chunks = list(body)
    # The head, the file a megabyte at a time, the tail.
    assert len(chunks) == 1 + 4 + 1
    assert sum(len(one) for one in chunks) == body.size
    whole = b"".join(chunks)
    boundary = content_type.split("boundary=")[1]
    assert whole.startswith(f"--{boundary}\r\n".encode())
    assert whole.endswith(f"\r\n--{boundary}--\r\n".encode())
    assert b'name="request"' in whole and b'"model": "large-v3"' in whole
    assert b'name="audio"; filename="side.wav"' in whole and sound in whole


def test_the_request_says_the_streamed_bodys_length(tmp_path, monkeypatch):
    audio = tmp_path / "side.wav"
    audio.write_bytes(b"RIFF" + b"x" * 100)
    body, content_type = whisperx._multipart(audio, {})
    seen = {}

    class Answer:
        status = 202

        def read(self):
            return b'{"id": "j1"}'

        def __enter__(self):
            return self

        def __exit__(self, *ignored):
            return False

    def urlopen(request, timeout):
        seen["request"] = request
        return Answer()

    monkeypatch.setattr(whisperx.urllib.request, "urlopen", urlopen)
    status, answer = whisperx._request("POST", "/v1/jobs", body, content_type)
    assert (status, answer) == (202, {"id": "j1"})
    assert seen["request"].data is body
    assert seen["request"].get_header("Content-length") == str(body.size)
    assert seen["request"].get_header("Content-type") == content_type


# 24 and 39. The default worker and the health checks --------------------------------


def test_the_default_worker_runs_two_jobs_and_the_checks_come_every_five_minutes():
    entrypoint = (HERE / "app" / "entrypoint.sh").read_text(encoding="utf-8")
    assert "--queues default --concurrency 2" in entrypoint
    compose = (HERE / "compose.yaml").read_text(encoding="utf-8").splitlines()
    checks = [
        number
        for number, line in enumerate(compose)
        if '"procrastinate", "healthchecks"' in line
    ]
    assert len(checks) == 3
    for number in checks:
        following = " ".join(compose[number + 1 : number + 8])
        assert "interval: 5m" in following and "start_period: 30s" in following


# 40. The two-sides match with a moving pointer finds what it found before -----------


class Line:
    def __init__(self, side, start, text):
        self.side_id = side
        self.start = start
        self.end = start + 3.0
        self.text = text
        self.speaker = f"Side {side}"
        self.same_as_other_side = False


class Call:
    is_two_channel_call = True


def the_old_way(segments):
    """The rule as it was written before v1.134.0, kept here as the measure."""
    by_side: dict = {}
    for one in segments:
        by_side.setdefault(one.side_id, []).append(one)
    first, second = (by_side[key] for key in sorted(by_side))
    pairs = []
    taken = set()
    for one in first:
        words = queue._plainly(one.text)
        if len(words) < queue.LONG_ENOUGH:
            continue
        for other in second:
            if id(other) in taken:
                continue
            if abs(other.start - one.start) > queue.SAME_MOMENT_SECONDS:
                continue
            if queue._plainly(other.text) != words:
                continue
            pairs.append((one, other))
            taken.add(id(other))
            break
    return pairs


def test_the_pointer_finds_the_same_pairs_as_the_walk_over_everything():
    chance = random.Random(7)
    sayings = [
        "This call is from a correctional facility and may be recorded.",
        "To accept this call, press one now.",
        "Thank you for using our service.",
        "Yeah, I can hear you fine, go on.",
        "Hey, it is me, can you hear me all right?",
    ]
    segments = []
    at = 0.0
    for number in range(400):
        text = sayings[number % len(sayings)]
        segments.append(Line(1, at, text))
        # Mostly the same line on both Sides a little apart; sometimes a
        # different line, a far-off twin, or two copies close together.
        roll = chance.random()
        if roll < 0.6:
            segments.append(Line(2, at + chance.uniform(-0.9, 0.9), text))
        elif roll < 0.75:
            segments.append(Line(2, at + 1.5, text))
        elif roll < 0.9:
            segments.append(Line(2, at + 0.3, sayings[(number + 1) % len(sayings)]))
        else:
            segments.append(Line(2, at + 0.2, text))
            segments.append(Line(2, at + 0.8, text))
        at += chance.uniform(0.5, 6.0)
    segments.sort(key=lambda one: one.start)

    expected = the_old_way(segments)
    found = queue._the_stretch_on_both_sides(segments, Call())
    assert found == len(expected) >= queue.A_STRETCH
    kept = {id(one) for one in segments if one.speaker == queue.BOTH_SIDES}
    copies = {id(one) for one in segments if one.same_as_other_side}
    assert kept == {id(one) for one, _ in expected}
    assert copies == {id(other) for _, other in expected}
