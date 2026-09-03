"""The line: order, position, duplicates, retries, retention, and speed."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from service import errors
from service.settings import Settings
from service.store import DONE, FAILED, QUEUED, RUNNING, SPEED_WINDOW, Store


@pytest.fixture
def settings(tmp_path):
    return Settings(
        state_dir=tmp_path / "state",
        tokens_file=tmp_path / "tokens",
        max_upload_bytes=2 * 1024**3,
        max_audio_seconds=8 * 3600,
        timeout_base_minutes=30,
        timeout_per_audio_hour_minutes=60,
        result_hours=24,
        job_history_days=30,
        batch_size=16,
        vad_onset=0.5,
        vad_offset=0.363,
        align_languages=("en", "es"),
        log_level="info",
    )


@pytest.fixture
def store(settings):
    store = Store(settings)
    yield store
    store.close()


def add(store, consumer="transcribe", seconds=600.0, reference=None, **request):
    request = {"model": "large-v3", "client_reference": reference, **request}
    audio = store.settings.audio_dir / f"{consumer}-{seconds}-{reference}.wav"
    audio.write_bytes(b"not really audio")
    return store.add(consumer, request, audio, seconds)


# Order and position ----------------------------------------------------------


def test_a_new_job_is_queued(store):
    job = add(store)
    assert job.state == QUEUED
    assert job.attempt == 1


def test_jobs_run_in_the_order_they_arrived(store):
    first = add(store)
    second = add(store)
    assert store.take_next().id == first.id
    store.finish(first.id, store.settings.results_dir / "one.json", 60.0)
    assert store.take_next().id == second.id


def test_only_one_job_runs_at_a_time(store):
    add(store)
    add(store)
    assert store.take_next() is not None
    assert store.take_next() is None


def test_the_line_is_shared_by_every_consumer(store):
    add(store, consumer="transcribe")
    theirs = add(store, consumer="another-app")
    jobs, minutes = store.ahead_of(theirs)
    assert jobs == 1
    assert minutes == pytest.approx(10.0)


def test_the_running_job_counts_as_one_ahead(store):
    add(store, seconds=1200.0)
    waiting = add(store)
    store.take_next()
    jobs, minutes = store.ahead_of(waiting)
    assert jobs == 1
    assert minutes == pytest.approx(20.0)


def test_a_finished_job_has_nothing_ahead_of_it(store):
    job = add(store)
    store.take_next()
    store.finish(job.id, store.settings.results_dir / "one.json", 30.0)
    assert store.ahead_of(store.job(job.id)) == (0, 0.0)


# Who may see what ------------------------------------------------------------


def test_another_consumer_is_told_the_job_does_not_exist(store):
    job = add(store, consumer="transcribe")
    with pytest.raises(errors.ServiceError) as raised:
        store.job_for(job.id, consumer="another-app", admin=False)
    assert raised.value.status_code == 404


def test_an_admin_token_sees_every_job(store):
    job = add(store, consumer="transcribe")
    assert store.job_for(job.id, consumer="it", admin=True).id == job.id


def test_a_consumer_lists_only_its_own(store):
    add(store, consumer="transcribe")
    add(store, consumer="another-app")
    assert len(store.jobs_for("transcribe", admin=False)) == 1
    assert len(store.jobs_for("it", admin=True)) == 2


# Duplicates ------------------------------------------------------------------


def test_the_same_reference_finds_the_job_already_in_the_line(store):
    job = add(store, reference="run-1")
    assert store.duplicate_of("transcribe", "run-1").id == job.id


def test_a_finished_job_is_not_a_duplicate(store):
    job = add(store, reference="run-1")
    store.take_next()
    store.finish(job.id, store.settings.results_dir / "one.json", 30.0)
    assert store.duplicate_of("transcribe", "run-1") is None


def test_another_consumers_reference_is_not_a_duplicate(store):
    add(store, consumer="transcribe", reference="run-1")
    assert store.duplicate_of("another-app", "run-1") is None


def test_no_reference_never_matches(store):
    add(store)
    assert store.duplicate_of("transcribe", None) is None


# Ending, and what is left behind ---------------------------------------------


def test_finishing_deletes_the_audio_and_keeps_the_result(store):
    job = add(store)
    store.take_next()
    result = store.settings.results_dir / "one.json"
    result.write_text(json.dumps({"segments": []}))
    store.finish(job.id, result, 42.0)

    finished = store.job(job.id)
    assert finished.state == DONE
    assert finished.audio_path is None
    assert not (store.settings.audio_dir / job.audio_path.split("/")[-1]).exists()
    assert result.exists()


def test_failing_deletes_the_audio(store):
    job = add(store)
    store.take_next()
    store.fail(job.id, errors.GPU_ERROR, "the card faulted")

    failed = store.job(job.id)
    assert failed.state == FAILED
    assert failed.failure_class == errors.GPU_ERROR
    assert failed.audio_path is None


def test_an_unknown_reason_class_is_refused(store):
    job = add(store)
    with pytest.raises(ValueError, match="unknown reason class"):
        store.fail(job.id, "it_broke", "something")


def test_a_job_that_has_ended_does_not_end_again(store):
    job = add(store)
    store.take_next()
    store.cancel(job.id)
    store.fail(job.id, errors.TIMEOUT, "too slow")
    assert store.job(job.id).failure_class == errors.CANCELLED


def test_removing_a_job_takes_its_result_with_it(store):
    job = add(store)
    store.take_next()
    result = store.settings.results_dir / "one.json"
    result.write_text("{}")
    store.finish(job.id, result, 10.0)
    store.remove(job.id)

    assert store.job(job.id) is None
    assert not result.exists()


# Restarts and retries --------------------------------------------------------


def test_a_job_interrupted_once_goes_back_to_the_head_of_the_line(store):
    job = add(store)
    store.take_next()
    assert store.recover() == [job.id]

    again = store.job(job.id)
    assert again.state == QUEUED
    assert again.attempt == 2
    assert again.started is None


def test_a_job_interrupted_twice_fails(store):
    job = add(store)
    store.take_next()
    store.recover()
    store.take_next()
    assert store.recover() == []

    failed = store.job(job.id)
    assert failed.state == FAILED
    assert failed.failure_class == errors.SERVICE_RESTARTED


def test_recovery_keeps_a_queued_job_where_it_was(store):
    first = add(store)
    second = add(store)
    store.take_next()
    store.recover()
    assert store.take_next().id == first.id
    assert second.state == QUEUED


# Retention -------------------------------------------------------------------


def test_a_result_is_dropped_once_its_hours_are_up(store):
    job = add(store)
    store.take_next()
    result = store.settings.results_dir / "one.json"
    result.write_text("{}")
    store.finish(job.id, result, 10.0)

    # Two days old: past the day a result is kept, and nowhere near the month
    # the row itself is kept.
    two_days_ago = datetime.now(UTC) - timedelta(days=2)
    store._db.execute(
        "UPDATE jobs SET finished = ? WHERE id = ?",
        (two_days_ago.isoformat(timespec="seconds"), job.id),
    )
    results, rows = store.sweep()

    assert results == 1
    assert not result.exists()
    assert store.job(job.id).state == DONE
    assert store.job(job.id).result_deleted is True


def test_a_row_is_dropped_once_its_days_are_up(store):
    job = add(store)
    store.take_next()
    store.fail(job.id, errors.BAD_INPUT, "no audio")
    store._db.execute(
        "UPDATE jobs SET finished = ? WHERE id = ?",
        ("2020-01-01T00:00:00+00:00", job.id),
    )

    _, rows = store.sweep()
    assert rows == 1
    assert store.job(job.id) is None


def test_a_queued_job_is_never_swept(store):
    job = add(store)
    assert store.sweep() == (0, 0)
    assert store.job(job.id) is not None


# The measured speed ----------------------------------------------------------


def test_speed_says_nothing_until_there_are_enough_jobs(store):
    for _ in range(SPEED_WINDOW - 1):
        job = add(store)
        store.take_next()
        store.finish(job.id, store.settings.results_dir / "r.json", 60.0)
    assert store.speed("large-v3", diarize=False) is None


def test_speed_is_audio_seconds_over_wall_seconds(store):
    for _ in range(SPEED_WINDOW):
        job = add(store, seconds=600.0)
        store.take_next()
        store.finish(job.id, store.settings.results_dir / "r.json", 60.0)
    assert store.speed("large-v3", diarize=False) == pytest.approx(10.0)


def test_speed_is_kept_apart_per_model_and_diarization(store):
    for _ in range(SPEED_WINDOW):
        job = add(store, seconds=600.0, diarize=True)
        store.take_next()
        store.finish(job.id, store.settings.results_dir / "r.json", 120.0)
    assert store.speed("large-v3", diarize=True) == pytest.approx(5.0)
    assert store.speed("large-v3", diarize=False) is None


# What a restart keeps --------------------------------------------------------


def test_the_line_survives_a_restart(settings):
    first = Store(settings)
    job = add(first)
    first.close()

    second = Store(settings)
    kept = second.job(job.id)
    assert kept.state == QUEUED
    assert kept.request["model"] == "large-v3"
    second.close()


def test_a_running_job_is_not_handed_out_twice_after_a_restart(settings):
    first = Store(settings)
    job = add(first)
    first.take_next()
    first.close()

    second = Store(settings)
    second.recover()
    assert second.take_next().id == job.id
    assert second.job(job.id).state == RUNNING
    second.close()
