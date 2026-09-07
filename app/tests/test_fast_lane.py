"""The fast lane: a second copy of the service for what must not wait.

A Live recording's Runs go to the lane when the office turned it on and it
answers; everything else, and everything when there is no lane, goes to the
batch service as before. A Run remembers its lane, so the poll, the fetch,
and the delete go to the copy that has the job.
"""

import pytest
from core import queue, tasks, whisperx
from core.jobs import Job
from core.models import User
from core.recordings import Batch, MediaState, Recording, Side


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("lane", "a-long-enough-password")


def a_recording(person, live: bool) -> Recording:
    batch = Batch.objects.create(user=person, is_live=live)
    recording = Recording.objects.create(
        batch=batch,
        user=person,
        title="one",
        original_filename="one.webm",
        media_state=MediaState.READY,
        duration_seconds=60.0,
        live={"started": "2026-09-07T10:00:00Z"} if live else {},
    )
    Side.objects.create(recording=recording, number=1, kind=Side.WHOLE)
    return recording


def test_without_a_lane_everything_goes_to_the_batch_service(person, settings):
    settings.WHISPERX_FAST_URL = ""
    assert not whisperx.fast_lane_configured()
    assert whisperx.lane_for(a_recording(person, live=True)) == ""
    assert whisperx.lane_for(a_recording(person, live=False)) == ""
    # A lane nobody configured is never alive, and is never asked.
    assert whisperx.is_alive(whisperx.FAST) is False


def test_a_live_recording_takes_the_lane_when_it_answers(person, settings, monkeypatch):
    settings.WHISPERX_FAST_URL = "http://whisperx-fast:8000"
    asked = []
    monkeypatch.setattr(
        whisperx, "is_alive", lambda lane="": asked.append(lane) or True
    )

    assert whisperx.lane_for(a_recording(person, live=True)) == whisperx.FAST
    assert asked == [whisperx.FAST]
    # An upload never takes the lane, whatever the lane says.
    assert whisperx.lane_for(a_recording(person, live=False)) == ""
    assert asked == [whisperx.FAST]

    # A lane that is down is not waited for: the batch service, as before.
    monkeypatch.setattr(whisperx, "is_alive", lambda lane="": False)
    assert whisperx.lane_for(a_recording(person, live=True)) == ""


def test_the_run_remembers_its_lane_and_is_fetched_from_it(
    person, settings, monkeypatch
):
    settings.WHISPERX_FAST_URL = "http://whisperx-fast:8000"
    monkeypatch.setattr(whisperx, "is_alive", lambda lane="": True)
    monkeypatch.setattr(tasks, "_poll_again", lambda attempt, when=3: None)
    submitted = []
    monkeypatch.setattr(
        whisperx,
        "submit",
        lambda audio, request, lane="": (
            submitted.append(lane)
            or whisperx.Submitted(id="job-1", position=0, audio_minutes_ahead=0.0)
        ),
    )
    recording = a_recording(person, live=True)
    job = queue.make_job(recording)

    queue.hand_over(job)

    assert submitted == [whisperx.FAST]
    run = job.runs.get()
    assert run.lane == whisperx.FAST and run.service_job_id == "job-1"

    # The poll asks both copies and reads the lane's answer for the lane's Run.
    polled = []

    def jobs(lane=""):
        polled.append(lane)
        if not lane:
            return []
        return [{"id": "job-1", "state": "running", "stage": "transcribing"}]

    monkeypatch.setattr(whisperx, "jobs", jobs)
    tasks.poll_service.func(attempt=1)
    assert polled == ["", whisperx.FAST]
    run.refresh_from_db()
    assert run.state == "running" and run.stage == "transcribing"

    # The fetch and the delete name the lane too.
    fetched = []
    monkeypatch.setattr(
        whisperx,
        "result",
        lambda job_id, lane="": (
            fetched.append(("result", job_id, lane))
            or {"segments": [], "language": {}, "settings_used": {}}
        ),
    )
    monkeypatch.setattr(
        whisperx,
        "delete",
        lambda job_id, lane="": fetched.append(("delete", job_id, lane)),
    )
    monkeypatch.setattr(
        whisperx,
        "jobs",
        lambda lane="": [{"id": "job-1", "state": "done"}] if lane else [],
    )
    tasks.poll_service.func(attempt=1)
    job.refresh_from_db()
    assert job.state == "done"
    assert ("result", "job-1", whisperx.FAST) in fetched
    assert ("delete", "job-1", whisperx.FAST) in fetched


def test_a_lane_that_does_not_answer_the_poll_is_a_warning_not_a_failure(
    person, settings, monkeypatch
):
    settings.WHISPERX_FAST_URL = "http://whisperx-fast:8000"
    recording = a_recording(person, live=True)
    job = queue.make_job(recording)
    run = job.runs.get()
    run.service_job_id = "job-2"
    run.lane = whisperx.FAST
    run.state = "queued"
    run.save()
    job.state = "queued"
    job.save()

    def jobs(lane=""):
        if lane:
            raise whisperx.ServiceError("down", "service_unreachable")
        return []

    monkeypatch.setattr(whisperx, "jobs", jobs)
    monkeypatch.setattr(tasks, "_poll_again", lambda attempt, when=3: None)
    tasks.poll_service.func(attempt=queue.POLLS_BEFORE_GIVING_UP)

    job.refresh_from_db()
    # The batch service answered, so nothing is given up on.
    assert job.state == "queued"
    assert Job.objects.get(pk=job.pk).runs.get().state == "queued"
