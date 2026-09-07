"""Transcription during the recording (Phase 3, step five).

While a Live recording continues, every closed stretch of it is cut from the
pieces on the server and transcribed as a Run of the recording's one open
Job; at Stop the tail is sent, the Job is closed, and the stretches' Segments
are merged by time into the one Transcript, with the speakers matched across
stretches by their voices. Nothing is shown before the Transcript is whole.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from core import live, media, pipeline, queue, settings_store, tasks, uploads, whisperx
from core.cases import Case
from core.jobs import Job, JobState, Run, Transcript
from core.models import LoginSession, User
from core.recordings import MediaState
from django.urls import reverse

PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"
    (tmp_path / "uploads").mkdir()
    return tmp_path


@pytest.fixture(autouse=True)
def room(monkeypatch):
    monkeypatch.setattr(uploads, "free_disk_bytes", lambda: 10**15)


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("recorder", PASSWORD)


@pytest.fixture
def on(db):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("live_recording", True)


@pytest.fixture
def a_case(person):
    return Case.objects.create(owner=person, name="Ramirez")


@pytest.fixture
def quiet(monkeypatch):
    """Nothing deferred runs; what was asked for is written down."""
    asked = {"stretch": [], "hand_over": [], "playback": []}
    monkeypatch.setattr(
        tasks.prepare_stretch, "defer", lambda **f: asked["stretch"].append(f)
    )
    monkeypatch.setattr(
        tasks.prepare_stretch,
        "configure",
        lambda **c: NS(defer=lambda **f: asked["stretch"].append({**f, **c})),
    )
    monkeypatch.setattr(
        tasks.hand_over_job, "defer", lambda **f: asked["hand_over"].append(f)
    )
    monkeypatch.setattr(
        tasks.make_playback_copy, "defer", lambda **f: asked["playback"].append(f)
    )
    return asked


class FakeMedia:
    """A media module that writes a file of the length asked for, or shorter
    while "arriving" is less than the span's end."""

    def __init__(self, monkeypatch):
        self.arrived = 10**9  # seconds of audio on the server
        self.cuts = []
        monkeypatch.setattr(media, "probe", self.probe)
        monkeypatch.setattr(media, "make_asr_audio", self.make_asr_audio)

    def probe(self, path):
        text = Path(path).read_text(encoding="utf-8") if Path(path).exists() else ""
        seconds = float(text) if text.replace(".", "").isdigit() else 0.0
        return NS(best_track=None, duration_seconds=seconds)

    def make_asr_audio(
        self, source, target, track, channel=None, profile="standard", span=None
    ):
        start, end = span if span else (0.0, 0.0)
        got = max(0.0, min(end, self.arrived) - start)
        self.cuts.append((Path(source).name, Path(target).name, channel, span))
        Path(target).parent.mkdir(parents=True, exist_ok=True)
        Path(target).write_text(f"{got:.1f}", encoding="utf-8")


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def a_live_recording(person, a_case, tmp_path, with_computer=False):
    recording = live.start(person, a_case, with_computer=with_computer)
    live.note_upload(recording, "tus1")
    (tmp_path / "uploads" / "tus1").write_bytes(b"\x1aE\xdf\xa3" + b"x" * 100)
    return recording


# Closing a stretch --------------------------------------------------------------------


def test_the_page_closes_a_stretch_and_the_worker_is_asked(
    on, person, a_case, client, tmp_path, quiet
):
    recording = a_live_recording(person, a_case, tmp_path)
    signed_in(client, person)

    # Too short to be a job of its own: it runs on.
    answer = client.post(
        reverse("record-stretch", args=[recording.pk]),
        json.dumps({"end": 12}),
        "application/json",
    )
    assert answer.status_code == 200 and answer.json()["closed"] is False
    assert not quiet["stretch"]

    answer = client.post(
        reverse("record-stretch", args=[recording.pk]),
        json.dumps({"end": 300}),
        "application/json",
    )
    assert answer.json()["closed"] is True
    recording.refresh_from_db()
    assert live.stretches_of(recording) == [
        {"number": 1, "start": 0.0, "end": 300.0, "state": "cutting"}
    ]
    assert quiet["stretch"] == [
        {"recording_id": str(recording.pk), "number": 1, "attempt": 1}
    ]
    # The next starts where this one ended.
    client.post(
        reverse("record-stretch", args=[recording.pk]),
        json.dumps({"end": 480.5}),
        "application/json",
    )
    recording.refresh_from_db()
    assert live.stretches_of(recording)[1] == {
        "number": 2,
        "start": 300.0,
        "end": 480.5,
        "state": "cutting",
    }
    # Nothing closes once the recording has ended: the tail is the server's.
    live.ended(recording, how="stop", seconds=500)
    recording.refresh_from_db()
    assert live.stretch_closed(recording, 500) is None
    assert len(live.stretches_of(recording)) == 2
    finished = queue.audit.Row.objects.get(event="Live recording finished")
    assert finished.details["stretches"] == 2


# Cutting and sending ----------------------------------------------------------------


def test_a_stretch_is_cut_from_what_arrived_and_tried_again_while_short(
    on, person, a_case, tmp_path, quiet, monkeypatch
):
    fake = FakeMedia(monkeypatch)
    recording = a_live_recording(person, a_case, tmp_path)
    live.stretch_closed(recording, 300)

    # The last pieces are still arriving: the cut is short, and asked again.
    fake.arrived = 297.0
    tasks.prepare_stretch.func(str(recording.pk), 1, attempt=1)
    assert quiet["stretch"][-1] == {
        "recording_id": str(recording.pk),
        "number": 1,
        "attempt": 2,
        "schedule_in": {"seconds": live.STRETCH_RETRY_SECONDS},
    }
    assert not Run.objects.filter(job__recording=recording).exists()
    assert fake.cuts[-1] == ("tus1", "001-1.wav", None, (0.0, 300.0))

    # Everything is there: one Run, on the recording's open Job, on the lane.
    fake.arrived = 10**9
    tasks.prepare_stretch.func(str(recording.pk), 1, attempt=2)
    recording.refresh_from_db()
    job = Job.objects.get(recording=recording)
    assert job.open and job.state == JobState.QUEUED
    run = job.runs.get()
    assert run.stretch == 1 and run.offset_seconds == 0.0 and run.seconds == 300.0
    assert run.audio_path == live.stretch_path(recording, 1, 1)
    assert live.stretches_of(recording)[0]["state"] == "sent"
    assert quiet["hand_over"] == [{"job_id": str(job.pk)}]
    # The Side was made from how the recording is made, once, and is kept.
    assert recording.sides.count() == 1 and not recording.is_two_channel_call

    # The request: the live priority ahead of an ended recording, and the
    # voices, so the stretches' speakers can be matched afterwards.
    asked = queue.request_for(run)
    assert asked["priority"] == 100 and asked["return_speaker_embeddings"] is True

    # A stretch with nothing to cut from is written off, to be tried at Stop.
    live.stretch_closed(recording, 600)
    (tmp_path / "uploads" / "tus1").unlink()
    tasks.prepare_stretch.func(str(recording.pk), 2, attempt=1)
    recording.refresh_from_db()
    assert live.stretches_of(recording)[1]["state"] == "failed"


def test_a_call_cuts_both_channels_of_every_stretch(
    on, person, a_case, tmp_path, quiet, monkeypatch
):
    fake = FakeMedia(monkeypatch)
    recording = a_live_recording(person, a_case, tmp_path, with_computer=True)
    live.stretch_closed(recording, 300)
    tasks.prepare_stretch.func(str(recording.pk), 1, attempt=1)
    recording.refresh_from_db()
    assert recording.is_two_channel_call
    assert [one[1:3] for one in fake.cuts] == [("001-1.wav", 0), ("001-2.wav", 1)]
    assert Run.objects.filter(job__recording=recording, stretch=1).count() == 2
    # Each Side is asked for as the recording asks; a Side's labels are
    # matched across its own stretches, never across Sides.
    asked = queue.request_for(Run.objects.filter(job__recording=recording).first())
    assert asked["diarize"] == recording.diarize and "speakers" not in asked


# The open Job -------------------------------------------------------------------------


def test_an_open_job_is_not_merged_and_a_failed_stretch_waits_for_stop(
    on, person, a_case, tmp_path, quiet, monkeypatch
):
    FakeMedia(monkeypatch)
    recording = a_live_recording(person, a_case, tmp_path)
    live.stretch_closed(recording, 300)
    tasks.prepare_stretch.func(str(recording.pk), 1, attempt=1)
    live.stretch_closed(recording, 600)
    tasks.prepare_stretch.func(str(recording.pk), 2, attempt=1)
    job = Job.objects.get(recording=recording)
    first, second = job.runs.order_by("stretch")
    first.service_job_id, second.service_job_id = "s1", "s2"
    first.save()
    second.save()
    merged = []
    monkeypatch.setattr(queue, "merge", lambda job: merged.append(job) or job)
    monkeypatch.setattr(whisperx, "delete", lambda job_id, lane="": None)

    # Both done, but the Job is open: nothing is merged yet.
    queue.take_state_from(job, {"s1": {"state": "done"}, "s2": {"state": "done"}})
    assert not merged
    # A stretch that fails is written off for now, not the recording.
    queue.take_state_from(
        job,
        {
            "s1": {"state": "done"},
            "s2": {"state": "failed", "failure": {"reason_class": "internal"}},
        },
    )
    job.refresh_from_db()
    recording.refresh_from_db()
    assert job.state != JobState.FAILED and job.runs.count() == 1
    assert live.stretches_of(recording)[1]["state"] == "failed"


def test_stop_sends_the_tail_and_the_failed_stretch_again_and_closes_the_job(
    on, person, a_case, tmp_path, quiet, monkeypatch
):
    fake = FakeMedia(monkeypatch)
    recording = a_live_recording(person, a_case, tmp_path)
    live.stretch_closed(recording, 300)
    tasks.prepare_stretch.func(str(recording.pk), 1, attempt=1)
    live.stretch_closed(recording, 600)
    live.mark_stretch(recording, 2, "failed")
    live.ended(recording, how="stop", seconds=650)

    # The whole file arrives and is prepared; the Sides are kept, not remade.
    recording.refresh_from_db()
    recording.folder.mkdir(parents=True, exist_ok=True)
    recording.original_path.write_text("650.0", encoding="utf-8")
    recording.duration_seconds = 650.0
    recording.media_state = MediaState.READY
    recording.save()
    side_before = recording.sides.get().pk
    pipeline._find_sides(recording)
    assert recording.sides.get().pk == side_before

    job = live.finish_stretches(recording)
    job.refresh_from_db()
    recording.refresh_from_db()
    assert not job.open
    assert [
        (r.stretch, r.offset_seconds, r.seconds) for r in job.runs.order_by("stretch")
    ] == [
        (1, 0.0, 300.0),
        (2, 300.0, 300.0),
        (3, 600.0, 50.0),
    ]
    assert [one["state"] for one in live.stretches_of(recording)] == [
        "sent",
        "sent",
        "sent",
    ]
    # The failed stretch and the tail were cut from the original, whole.
    assert [one[0] for one in fake.cuts[-2:]] == [
        recording.original_path.name,
        recording.original_path.name,
    ]


# The merge ------------------------------------------------------------------


def a_result(segments, labels=(), embeddings=None, language="en"):
    return {
        "segments": [
            {
                "start": start,
                "end": end,
                "text": text,
                "speaker": label,
                "words": [{"word": text, "start": start, "end": end}],
            }
            for start, end, text, label in segments
        ],
        "speakers": {"labels": list(labels), "embeddings": embeddings or {}},
        "language": {"detected": language, "probability": 0.9},
        "word_timestamps": {"present": True},
        "settings_used": {"task_run": "transcribe", "diarize": bool(labels)},
    }


def test_the_stretches_merge_by_time_with_the_speakers_matched_by_voice(
    on, person, a_case, tmp_path, quiet, monkeypatch
):
    FakeMedia(monkeypatch)
    recording = a_live_recording(person, a_case, tmp_path)
    recording.diarize = True
    recording.save()
    live.stretch_closed(recording, 300)
    tasks.prepare_stretch.func(str(recording.pk), 1, attempt=1)
    live.stretch_closed(recording, 600)
    tasks.prepare_stretch.func(str(recording.pk), 2, attempt=1)
    job = Job.objects.get(recording=recording)
    job.open = False
    job.save()
    first, second = job.runs.order_by("stretch")
    first.service_job_id, second.service_job_id = "s1", "s2"
    first.state = second.state = "done"
    first.save()
    second.save()

    ana, ben = [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]
    results = {
        # Stretch one: two voices, labelled 00 and 01.
        "s1": a_result(
            [(2.0, 8.0, "hello", "SPEAKER_00"), (10.0, 15.0, "hi", "SPEAKER_01")],
            labels=["SPEAKER_00", "SPEAKER_01"],
            embeddings={"SPEAKER_00": ana, "SPEAKER_01": ben},
        ),
        # Stretch two: the engine labels Ben 00 this time, and a new voice 01.
        "s2": a_result(
            [(1.0, 4.0, "yes", "SPEAKER_00"), (20.0, 25.0, "new", "SPEAKER_01")],
            labels=["SPEAKER_00", "SPEAKER_01"],
            embeddings={"SPEAKER_00": [0.1, 0.99, 0.0], "SPEAKER_01": [0.0, 0.0, 1.0]},
        ),
    }
    monkeypatch.setattr(whisperx, "result", lambda job_id, lane="": results[job_id])
    monkeypatch.setattr(whisperx, "delete", lambda job_id, lane="": None)

    queue.merge(job)
    job.refresh_from_db()
    assert job.state == JobState.DONE
    transcript = Transcript.objects.get(recording=recording)
    rows = list(
        transcript.segments.order_by("start").values_list(
            "start", "end", "text", "speaker"
        )
    )
    assert rows == [
        (2.0, 8.0, "hello", "Speaker 1"),
        (10.0, 15.0, "hi", "Speaker 2"),
        (301.0, 304.0, "yes", "Speaker 2"),
        (320.0, 325.0, "new", "Speaker 3"),
    ]
    # The words moved with their segment.
    late = transcript.segments.get(text="yes")
    assert late.words == [{"word": "yes", "start": 301.0, "end": 304.0}]
    # The provenance is one entry per Run and nothing else: the exporter
    # reads every entry as a Run's.
    assert set(transcript.provenance) == {str(first.pk), str(second.pk)}
    from core import exports

    assert exports.model_of(transcript) == ""
    # A provenance from v1.32.0, with the count written beside the Runs,
    # still exports.
    transcript.provenance["stretches"] = 2
    transcript.save()
    assert exports.model_of(transcript) == "" and len(exports.runs_of(transcript)) == 2
    assert ("Transcribed while recording", "in 2 stretches, the last at Stop") in (
        live.provenance_rows(recording)
    )


def test_the_line_says_finishing_for_a_recording_in_stretches(
    on, person, a_case, tmp_path, quiet, monkeypatch
):
    FakeMedia(monkeypatch)
    recording = a_live_recording(person, a_case, tmp_path)
    live.stretch_closed(recording, 300)
    tasks.prepare_stretch.func(str(recording.pk), 1, attempt=1)
    live.ended(recording, how="stop", seconds=330)
    recording.refresh_from_db()
    recording.media_state = MediaState.READY
    recording.save()
    job = Job.objects.get(recording=recording)
    run = job.runs.get()
    run.state = "done"
    run.save()
    Run.objects.create(
        job=job, side=run.side, stretch=2, offset_seconds=300, seconds=30
    )
    job.open = False
    job.save()
    monkeypatch.setattr(live, "measured_speed", lambda: 60.0)
    assert live.line_for(recording) == {
        "state": "transcribing",
        "says": "Finishing: about 1 minute.",
    }
