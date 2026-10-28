"""A hand-over held while the service was not answering (v1.163.1).

A recording uploaded while the recogniser was busy with another job's pieces
was refused as service_refused and failed for good, and its row read Ready.
Now a 503 carries the service's own reason, the hand-over is held and tried
again by the minute sweep, half an hour at most, and the row says what it
waits for; a Job that failed reads Failed.
"""

from __future__ import annotations

import datetime as dt

import pytest
from core import pages, queue, settings_store, whisperx
from core.cases import Case
from core.jobs import Job, JobState, Reason, Run
from core.models import User
from core.recordings import Batch, MediaState, Recording, Side
from django.utils import timezone

PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def switches(db):
    settings_store.set_to("folder_management", True)


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("keeper", PASSWORD)


@pytest.fixture
def a_case(person):
    return Case.objects.create(owner=person, name="Harbour")


def a_recording(person, case):
    return Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        case=case,
        title="A call",
        original_filename="a-call.mp4",
        media_state=MediaState.READY,
        duration_seconds=736.0,
        playback_ready=True,
    )


def a_job(recording):
    side = Side.objects.create(recording=recording, number=1, kind=Side.WHOLE, name="")
    job = Job.objects.create(
        recording=recording, batch=recording.batch, state=JobState.QUEUED
    )
    Run.objects.create(job=job, side=side, service_job_id="", lane="")
    return job


# The service client ----------------------------------------------------------


def test_a_503_carries_the_services_reason_and_waits(monkeypatch, tmp_path):
    audio = tmp_path / "side.wav"
    audio.write_bytes(b"RIFF")
    monkeypatch.setattr(
        whisperx,
        "_request",
        lambda *a, **k: (
            503,
            {
                "error": "the recogniser container is not answering",
                "reason_class": "recogniser_unavailable",
            },
        ),
    )
    with pytest.raises(whisperx.ServiceError) as told:
        whisperx.submit(audio, {})
    assert told.value.reason_class == "recogniser_unavailable" and told.value.wait

    # A 503 with no body is the service, or what stands before it, not there.
    monkeypatch.setattr(whisperx, "_request", lambda *a, **k: (503, None))
    with pytest.raises(whisperx.ServiceError) as told:
        whisperx.submit(audio, {})
    assert told.value.reason_class == "service_unreachable" and told.value.wait

    # A refusal of the request itself is still a refusal, not a wait.
    monkeypatch.setattr(
        whisperx,
        "_request",
        lambda *a, **k: (400, {"error": "no", "reason_class": "bad_input"}),
    )
    with pytest.raises(whisperx.ServiceError) as told:
        whisperx.submit(audio, {})
    assert told.value.reason_class == "bad_input" and not told.value.wait

    monkeypatch.setattr(whisperx, "_request", lambda *a, **k: (401, None))
    with pytest.raises(whisperx.ServiceError) as told:
        whisperx.submit(audio, {})
    assert told.value.reason_class == "service_refused" and not told.value.wait


# The hand-over ----------------------------------------------------------------


def _not_answering(audio, request, lane=""):
    raise whisperx.ServiceError("not answering", "recogniser_unavailable")


def test_a_hand_over_that_meets_a_busy_container_is_held_not_failed(
    person, a_case, monkeypatch
):
    job = a_job(a_recording(person, a_case))
    monkeypatch.setattr(whisperx, "submit", _not_answering)
    monkeypatch.setattr(whisperx, "lane_for", lambda recording: "")
    told = queue.hand_over(job)
    assert told.state == JobState.QUEUED
    assert told.failure_class == Reason.RECOGNISER_UNAVAILABLE
    first = told.held_since
    assert first is not None
    # Held again a minute later: the holding's start is kept.
    told = queue.hand_over(told)
    assert told.state == JobState.QUEUED and told.held_since == first
    # The sweep's own list still has it, so it is handed over again.
    stale = timezone.now() - dt.timedelta(minutes=3)
    Job.objects.filter(pk=told.pk).update(created=stale)
    assert list(queue.never_handed_over()) == [told]


def test_a_hold_ends_in_a_failure_after_the_limit(person, a_case, monkeypatch):
    job = a_job(a_recording(person, a_case))
    monkeypatch.setattr(whisperx, "submit", _not_answering)
    monkeypatch.setattr(whisperx, "lane_for", lambda recording: "")
    job.held_since = timezone.now() - queue.HOLD_LIMIT - dt.timedelta(minutes=1)
    job.save(update_fields=["held_since"])
    told = queue.hand_over(job)
    assert told.state == JobState.FAILED
    assert told.failure_class == Reason.RECOGNISER_UNAVAILABLE
    assert "did not answer for half an hour" in Reason.MESSAGES[told.failure_class]
    assert "half an hour" in Reason.MESSAGES[Reason.DIARIZER_UNAVAILABLE]


def test_a_hand_over_that_goes_through_ends_the_holding(person, a_case, monkeypatch):
    job = a_job(a_recording(person, a_case))
    job.held_since = timezone.now() - dt.timedelta(minutes=2)
    job.failure_class = Reason.RECOGNISER_UNAVAILABLE
    job.save(update_fields=["held_since", "failure_class"])
    monkeypatch.setattr(
        whisperx,
        "submit",
        lambda audio, request, lane="": whisperx.Submitted(
            id="s9", position=1, audio_minutes_ahead=0.0
        ),
    )
    monkeypatch.setattr(whisperx, "lane_for", lambda recording: "")
    told = queue.hand_over(job)
    assert told.state == JobState.QUEUED
    assert told.held_since is None and told.failure_class == ""
    assert told.runs.get().service_job_id == "s9"


def test_a_refusal_of_the_app_itself_still_fails(person, a_case, monkeypatch):
    job = a_job(a_recording(person, a_case))

    def refused(audio, request, lane=""):
        raise whisperx.ServiceError("unknown token", "service_refused")

    monkeypatch.setattr(whisperx, "submit", refused)
    monkeypatch.setattr(whisperx, "lane_for", lambda recording: "")
    told = queue.hand_over(job)
    assert told.state == JobState.FAILED and told.held_since is None


# The row ----------------------------------------------------------------------------


def test_the_row_says_what_a_held_job_waits_for_and_failed_for_a_failed_one(
    person, a_case, monkeypatch
):
    recording = a_recording(person, a_case)
    job = a_job(recording)
    job.held_since = timezone.now()
    job.failure_class = Reason.RECOGNISER_UNAVAILABLE
    job.save(update_fields=["held_since", "failure_class"])
    (row,) = pages._with_their_state(Recording.objects.filter(pk=recording.pk))
    assert (row.state_word, row.state_tone) == ("Waiting for the recogniser", "warn")

    job.held_since = None
    job.failure_class = ""
    job.save(update_fields=["held_since", "failure_class"])
    (row,) = pages._with_their_state(Recording.objects.filter(pk=recording.pk))
    assert (row.state_word, row.state_tone) == ("In the queue", "warn")

    job.state = JobState.FAILED
    job.failure_class = Reason.SERVICE_REFUSED
    job.save(update_fields=["state", "failure_class"])
    (row,) = pages._with_their_state(Recording.objects.filter(pk=recording.pk))
    assert (row.state_word, row.state_tone) == ("Failed", "danger")


def test_the_case_page_and_my_recordings_say_failed_and_offer_retry(
    person, a_case, client
):
    """v1.163.2: the case page's rows carry the same flags, and a failed Job
    is offered Retry on both pages, not only a failed media step; before,
    the case row read Ready and Delete was the only way."""
    from tests.helpers import signed_in

    recording = a_recording(person, a_case)
    job = a_job(recording)
    job.state = JobState.FAILED
    job.failure_class = Reason.SERVICE_REFUSED
    job.save(update_fields=["state", "failure_class"])
    signed_in(client, person)
    page = client.get(f"/case/{a_case.pk}").content.decode()
    assert ">Failed<" in page
    assert f'data-recording="{recording.pk}">Retry</button>' in page
    # My recordings lists a person's own recordings outside any case.
    loose = a_recording(person, None)
    gone = a_job(loose)
    gone.state = JobState.FAILED
    gone.failure_class = Reason.SERVICE_REFUSED
    gone.save(update_fields=["state", "failure_class"])
    mine = client.get("/recordings").content.decode()
    assert ">Failed<" in mine
    assert f'data-recording="{loose.pk}">Retry</button>' in mine

    # Held: the row says what it waits for, and offers nothing yet.
    job.state = JobState.QUEUED
    job.held_since = timezone.now()
    job.failure_class = Reason.RECOGNISER_UNAVAILABLE
    job.save(update_fields=["state", "held_since", "failure_class"])
    page = client.get(f"/case/{a_case.pk}").content.decode()
    assert "Waiting for the recogniser" in page and 'class="small retry"' not in page
