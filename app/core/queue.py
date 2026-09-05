"""The Queue: handing Sides to the service, watching them, and merging results.

The service holds the only line that matters, one job at a time across every
Consumer. This is the app's side of it: a Job per Recording, a Run per Side,
and the merge that turns the Runs' answers into one Transcript.

Nothing is held back and nothing is reordered. A Recording joins the line the
moment it is Ready, in Ready order rather than upload order, so a small
recording uploaded after a large video overtakes it while the video is still
being prepared.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from core import audit, settings_store, whisperx
from core.jobs import Job, JobState, Reason, Run, Segment, Transcript
from core.recordings import MediaState, Recording, Side

log = logging.getLogger("transcribe.queue")

# Two polls in a row have to fail before a Job is given up on. One dropped
# packet must not fail a two-hour transcription.
POLLS_BEFORE_GIVING_UP = 2


def make_job(recording: Recording) -> Job:
    """A Job for a Ready Recording, with one Run per Side."""
    job = Job.objects.create(recording=recording, batch=recording.batch)
    for side in recording.sides.all().order_by("number"):
        Run.objects.create(job=job, side=side)
    return job


def _office_vocabulary() -> list[str]:
    """The Admin's list, one term per line, blank lines dropped."""
    return [
        line.strip()
        for line in settings_store.get("office_vocabulary").splitlines()
        if line.strip()
    ]


def request_for(run: Run) -> dict:
    """What the service is asked for this Side.

    The task and language follow the person's two choices. A Two-channel call
    sends an empty speaker hint for each Side, whatever the hint says: an
    "exactly 2" meant for the whole call would be wrong for one side of it.
    """
    recording = run.job.recording

    # Translate ticked asks for English whatever is spoken; unticked asks for
    # the speech in its own language. The service decides the rest from the
    # language field and its own detection.
    task = "translate_if_needed" if recording.translate else "transcribe"

    request: dict = {
        "task": task,
        "language": recording.spoken_language or "",
        "model": recording.model or settings_store.get("model"),
        "diarize": recording.diarize,
        # The office's own list goes ahead of the Batch's, and the service
        # cuts from the end of a prompt that is too long, so the Batch's own
        # terms are the ones that survive.
        "vocabulary": _office_vocabulary() + list(recording.vocabulary or []),
        "context": recording.context or "",
        "return_speaker_embeddings": False,
        # The Run's own id, which is the service's duplicate protection: a
        # submission it has seen comes back as that job rather than a second.
        "client_reference": str(run.id),
    }

    if not recording.translate and not recording.spoken_language:
        # Only meaningful on a detected transcribe. With the setting off, or
        # with translation turned off altogether, such a Recording is
        # transcribed in its winning language and the viewer says so.
        request["translate_if_mixed"] = settings_store.get(
            "translate_mixed"
        ) and settings_store.get("translation_available")

    if recording.diarize and not recording.is_two_channel_call:
        if recording.speakers_exactly:
            request["speakers"] = {"exactly": recording.speakers_exactly}
        elif recording.speakers_between:
            request["speakers"] = {"between": list(recording.speakers_between)}

    return request


def hand_over(job: Job) -> Job:
    """Give every Run of a Job to the service, back to back.

    Back to back so that a multi-Side Recording never has another user's Job
    interleaved between its Sides. The Job's place in the line is its first
    Run's.
    """
    for run in job.runs.all().order_by("side__number"):
        if run.service_job_id:
            continue
        try:
            submitted = whisperx.submit(run.side.asr_path, request_for(run))
        except whisperx.ServiceError as problem:
            return fail(job, problem.reason_class)

        run.service_job_id = submitted.id
        run.state = "queued"
        run.position = submitted.position
        run.audio_minutes_ahead = submitted.audio_minutes_ahead
        run.submitted = timezone.now()
        run.save()

    job.state = JobState.QUEUED
    job.save(update_fields=["state"])
    log.info("job %s handed over: %d run(s)", job.id, job.runs.count())
    return job


def take_state_from(job: Job, service_jobs: dict[str, dict]) -> Job:
    """Bring one Job up to date from what the service just said.

    The service is asked once for everything, so this reads from that one
    answer rather than asking again per Run.
    """
    for run in job.runs.all():
        state = service_jobs.get(run.service_job_id)
        if state is None:
            continue

        run.state = state["state"]
        run.stage = state.get("stage") or ""
        run.percent = state.get("percent")
        run.position = state.get("position")
        run.audio_minutes_ahead = state.get("audio_minutes_ahead")

        if state["state"] in ("failed", "cancelled") and not run.failure_class:
            failure = state.get("failure") or {}
            run.failure_class = failure.get("reason_class") or Reason.INTERNAL
        run.save()

    runs = list(job.runs.all())

    failed = next((run for run in runs if run.failure_class), None)
    if failed is not None:
        # One Run failing fails the Job as a whole, with that Run's reason.
        # The other Runs are still at the service, so they are cancelled to
        # give the card back rather than left to run for nobody.
        for run in runs:
            if run.service_job_id and run is not failed:
                whisperx.delete(run.service_job_id)
        return fail(job, failed.failure_class)

    if any(run.state == "running" for run in runs) and job.started is None:
        job.started = timezone.now()
        job.state = JobState.RUNNING
        job.save(update_fields=["started", "state"])
    elif any(run.state == "running" for run in runs):
        job.state = JobState.RUNNING
        job.save(update_fields=["state"])

    if runs and all(run.state == "done" for run in runs):
        return merge(job)

    return job


@transaction.atomic
def merge(job: Job) -> Job:
    """Turn the Runs' results into the one Transcript.

    Segments are merged by time. Speaker labels arrive per Run as SPEAKER_00
    and on, which mean nothing to a person and nothing across Sides, so they
    are renamed before anybody sees them.
    """
    job.merging = True
    job.save(update_fields=["merging"])

    try:
        results = {}
        for run in job.runs.all():
            results[run.pk] = whisperx.result(run.service_job_id)
    except whisperx.ServiceError as problem:
        return fail(job, problem.reason_class)

    try:
        transcript = _store(job, results)
    except Exception:  # noqa: BLE001 - anything here is the same failure
        log.exception("the transcript of job %s could not be stored", job.id)
        return fail(job, Reason.MERGE_FAILED)

    for run in job.runs.all():
        whisperx.delete(run.service_job_id)

    job.state = JobState.DONE
    job.merging = False
    job.finished = timezone.now()
    job.save()

    seconds = (job.finished - job.created).total_seconds()
    audit.write(
        audit.Category.JOBS,
        "Job completed",
        system="worker",
        affected_user=job.recording.user,
        object_type="recording",
        object_id=job.recording_id,
        object_label=job.recording.original_filename,
        duration_seconds=round(seconds, 1),
        sides=job.runs.count(),
    )
    log.info(
        "job %s done in %.0fs: %d segments",
        job.id,
        seconds,
        transcript.segments.count(),
    )
    return job


def _store(job: Job, results: dict) -> Transcript:
    """Write the Transcript and its Segments, and keep the Provenance."""
    Transcript.objects.filter(recording=job.recording).delete()

    first = next(iter(results.values()))
    language = first.get("language", {})
    timing = first.get("word_timestamps", {})

    transcript = Transcript.objects.create(
        recording=job.recording,
        job=job,
        task_run=first.get("settings_used", {}).get("task_run", ""),
        task_reason=first.get("settings_used", {}).get("task_reason", ""),
        language=language.get("detected") or "",
        language_probability=language.get("probability"),
        language_mixed=bool(language.get("mixed")),
        detection={
            "windows": language.get("windows", []),
            "combined": language.get("combined", {}),
        },
        word_timestamps=bool(timing.get("present")),
        word_timestamps_reason=timing.get("reason") or "",
        provenance={
            str(run_id): {
                "settings_used": result.get("settings_used", {}),
                "service": result.get("service", {}),
                "timings_seconds": result.get("timings_seconds", {}),
                "gpu": result.get("gpu", {}),
                "audio": result.get("audio", {}),
            }
            for run_id, result in results.items()
        },
    )

    runs = {run.pk: run for run in job.runs.all()}
    many_sides = len(runs) > 1

    segments = []
    for run_id, result in results.items():
        run = runs[run_id]
        names = _speaker_names(result, run.side, many_sides, job.recording.diarize)
        for segment in result.get("segments", []):
            segments.append(
                Segment(
                    transcript=transcript,
                    side=run.side,
                    start=segment.get("start") or 0.0,
                    end=segment.get("end") or 0.0,
                    text=(segment.get("text") or "").strip(),
                    speaker=names.get(segment.get("speaker", ""), names.get("", "")),
                    speaker_label=segment.get("speaker", "") or "",
                    words=segment.get("words") or [],
                )
            )

    segments.sort(key=lambda one: one.start)
    shared = _the_stretch_on_both_sides(segments, job.recording)
    if shared:
        transcript.shared_segments = shared
        transcript.save(update_fields=["shared_segments"])
    Segment.objects.bulk_create(segments, batch_size=500)

    for run_id, result in results.items():
        run = runs[run_id]
        run.settings_used = result.get("settings_used", {})
        run.service_versions = result.get("service", {})
        run.timings = result.get("timings_seconds", {})
        run.finished = timezone.now()
        run.save()

    return transcript


# What both parties hear before a call connects: the recorded announcement,
# the ringing, the operator. A phone system puts that on both channels, so
# both Sides transcribe it and the first minutes of a call read twice over.
# Nothing is wrong with the recording or with the transcription; it is what
# the file holds.
#
# Two Segments are the same thing heard twice when they say the same words at
# the same moment. The guards are against coincidence, not against noise: two
# people can both say "yeah" at once, so a match needs real words, and one
# match is not a stretch, so a run of them is needed before any of it counts.
SAME_MOMENT_SECONDS = 1.0
LONG_ENOUGH = 12
A_STRETCH = 3

BOTH_SIDES = "Side 1 and Side 2"


def _plainly(text: str) -> str:
    """The words alone, so punctuation and capitals cannot part a pair."""
    kept = [one.lower() if one.isalnum() else " " for one in text]
    return " ".join("".join(kept).split())


def _the_stretch_on_both_sides(segments: list, recording) -> int:
    """Find what both Sides heard, name it for both, and mark the second copy.

    Nothing is removed. The Segment that is kept is renamed to say it was on
    both Sides; its twin is marked and stays in the database, out of the
    reading, the exports, and the search, so the announcement at the head of a
    call is read once rather than twice.

    Returns how many pairs were found, which the viewer and the exports say
    out loud: the app does not quietly decide what a transcript shows.
    """
    if not recording.is_two_channel_call:
        return 0

    by_side: dict = {}
    for one in segments:
        by_side.setdefault(one.side_id, []).append(one)
    if len(by_side) != 2:
        return 0

    # Sorted as numbers, not as text: Side ids are database ids, and as
    # text "10" sorts before "9".
    first, second = (by_side[key] for key in sorted(by_side))

    pairs = []
    taken = set()
    for one in first:
        words = _plainly(one.text)
        if len(words) < LONG_ENOUGH:
            continue
        for other in second:
            if id(other) in taken:
                continue
            if abs(other.start - one.start) > SAME_MOMENT_SECONDS:
                continue
            if _plainly(other.text) != words:
                continue
            pairs.append((one, other))
            taken.add(id(other))
            break

    if len(pairs) < A_STRETCH:
        return 0

    for kept, copy in pairs:
        kept.speaker = BOTH_SIDES
        copy.same_as_other_side = True
    return len(pairs)


def _speaker_names(
    result: dict, side: Side, many_sides: bool, diarized: bool
) -> dict[str, str]:
    """Turn the engine's labels into names a person can read.

    The engine says SPEAKER_00 and on, per Run, so the same label means
    different people on different Sides. On one Side they become Speaker 1 and
    on. Across Sides they carry the Side, and a Side with only one voice is
    named by its Side alone, so a two-party call reads the way it would
    without speaker separation and a three-way call still comes out right.
    """
    labels = sorted(result.get("speakers", {}).get("labels", []))

    if not diarized or not labels:
        # Without separation the Sides are the speakers, and a recording with
        # one Side has nobody to name.
        return {"": side.name if many_sides else ""}

    if many_sides and len(labels) == 1:
        return {labels[0]: side.name, "": side.name}

    names = {}
    for number, label in enumerate(labels, start=1):
        names[label] = (
            f"{side.name} Speaker {number}" if many_sides else f"Speaker {number}"
        )
    names[""] = side.name if many_sides else ""
    return names


def fail(job: Job, reason_class: str) -> Job:
    """End a Job with one reason class, and say so in the log.

    Files are kept, so a Retry reuses the media steps that already worked.
    """
    job.state = JobState.FAILED
    job.merging = False
    job.failure_class = reason_class
    job.finished = timezone.now()
    job.save()

    audit.write(
        audit.Category.JOBS,
        "Job failed",
        system="worker",
        outcome=audit.Outcome.FAILURE,
        reason_class=reason_class,
        affected_user=job.recording.user,
        object_type="recording",
        object_id=job.recording_id,
        object_label=job.recording.original_filename,
    )
    log.warning("job %s failed: %s", job.id, reason_class)
    return job


def live_jobs():
    """Every Job that is still at the service, or on its way there."""
    return Job.objects.filter(state__in=JobState.LIVE).select_related("recording")


def ready_without_a_job():
    """Recordings that are Ready and have not joined the line yet."""
    return Recording.objects.filter(media_state=MediaState.READY, jobs__isnull=True)


def unname(transcript: Transcript, name: str) -> int:
    """Put the Speakers of one name back to their labels, Speaker 1 and on.

    The reverse of _speaker_names, for a Person deleted on a Case's Speakers
    tab: the labels the engine gave are still on every Segment, so the app's
    names are worked out again from them, per Side, exactly as at storage.
    """
    recording = transcript.recording
    sides = list(recording.sides.all())
    many_sides = len(sides) > 1
    changed = 0
    for side in sides or [None]:
        rows = (
            transcript.segments.filter(side=side) if side else transcript.segments.all()
        )
        labels = sorted(
            set(rows.exclude(speaker_label="").values_list("speaker_label", flat=True))
        )
        side_name = side.name if (side is not None and many_sides) else ""
        if many_sides and len(labels) == 1:
            names = {labels[0]: side_name, "": side_name}
        else:
            names = {
                label: (f"{side_name} Speaker {n}" if side_name else f"Speaker {n}")
                for n, label in enumerate(labels, start=1)
            }
            names[""] = side_name
        for segment in rows.filter(speaker__iexact=name.strip()):
            segment.speaker = names.get(segment.speaker_label, side_name)
            segment.save(update_fields=["speaker"])
            changed += 1
    return changed
