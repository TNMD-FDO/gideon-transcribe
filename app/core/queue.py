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

import datetime as dt
import logging
import math
import re

from django.db import IntegrityError, transaction
from django.utils import timezone

from core import audit, settings_store, whisperx
from core.jobs import SPEAKERS, Job, JobState, Reason, Run, Segment, Transcript
from core.recordings import MediaState, Recording, Side

log = logging.getLogger("transcribe.queue")

# Two polls in a row have to fail before a Job is given up on. One dropped
# packet must not fail a two-hour transcription.
POLLS_BEFORE_GIVING_UP = 2
# A slow answer (a read timeout) is given more polls than a refused one
# (v1.132.0): the service loading a model is busy, not gone.
POLLS_BEFORE_GIVING_UP_ON_A_SLOW_ANSWER = 5


def make_job(recording: Recording) -> Job:
    """A Job for a Ready Recording, with one Run per Side, over the whole.

    A Live recording transcribed in stretches has its Job made stretch by
    stretch instead (core.live); this is the whole-file path, and Process
    again on such a recording comes back through it.
    """
    # The database keeps one live Job per recording (v1.131.0, migration
    # 0078): the minute sweep and the media worker can both arrive here, and
    # the second maker gets the first's Job rather than a twin.
    try:
        with transaction.atomic():
            job = Job.objects.create(recording=recording, batch=recording.batch)
            for side in recording.sides.all().order_by("number"):
                Run.objects.create(job=job, side=side)
    except IntegrityError:
        return (
            recording.jobs.filter(state__in=JobState.LIVE, kind="")
            .order_by("-created")
            .first()
        )
    return job


def _office_vocabulary() -> list[str]:
    """The Admin's list, one term per line, blank lines dropped."""
    return [
        line.strip()
        for line in settings_store.get("office_vocabulary").splitlines()
        if line.strip()
    ]


def _case_vocabulary(recording) -> list[str]:
    """The Case vocabulary's names, for a recording in a Case (Phase 9
    chapter 2): the People and the terms, never a spelling."""
    if recording.case_id is None:
        return []
    from core import vocabulary

    return vocabulary.recognition_names(recording.case)


def request_for(run: Run) -> dict:
    """What the service is asked for this Side.

    The task and language follow the person's two choices. A Two-channel call
    sends an empty speaker hint for each Side, whatever the hint says: an
    "exactly 2" meant for the whole call would be wrong for one side of it.
    A speakers pass (v1.94.0) asks for the turns alone.
    """
    recording = run.job.recording
    if run.job.kind == SPEAKERS:
        return {
            # The diarize-only task (service 0.4.0): who spoke when over the
            # whole recording, and no words.
            "task": "diarize",
            "model": recording.model or settings_store.get("model"),
            "diarize": True,
            "diarizer": settings_store.diarizer(),
            "client_reference": str(run.id),
            # Behind a stretch of one still recording, ahead of the uploads.
            "priority": 90,
        }

    # Which model writes the words (ADR 0025): the Panel's choice, except that
    # a Live recording stays on Whisper, as the Fast lane does.
    recogniser = "whisper" if recording.is_live else settings_store.recogniser()

    # Translate ticked asks for English whatever is spoken; unticked asks for
    # the speech in its own language. The service decides the rest from the
    # language field and its own detection. Qwen3-ASR never writes English:
    # until the chat engine's translation is built (ADR 0026) a Recording
    # under it is transcribed in the language spoken, and the Upload page
    # greys the choice with that reason.
    task = (
        "translate_if_needed"
        if recording.translate and recogniser == "whisper"
        else "transcribe"
    )

    request: dict = {
        "task": task,
        "recogniser": recogniser,
        "language": recording.spoken_language or "",
        "model": recording.model or settings_store.get("model"),
        "diarize": recording.diarize,
        # The office's own list goes ahead of the Case's (Phase 9 chapter 2)
        # and the Case's ahead of the Batch's, and the service cuts from the
        # end of a prompt that is too long, so the Batch's own terms are the
        # ones that survive.
        "vocabulary": _office_vocabulary()
        + _case_vocabulary(recording)
        + list(recording.vocabulary or []),
        "context": recording.context or "",
        "return_speaker_embeddings": False,
        # Which model tells voices apart (Phase 5 chapter 4); the service
        # refuses a hint or an embeddings request with nemotron.
        "diarizer": settings_store.diarizer(),
        # The Run's own id, which is the service's duplicate protection: a
        # submission it has seen comes back as that job rather than a second.
        "client_reference": str(run.id),
        # A Live recording goes ahead of every uploaded one: a meeting that
        # has just ended is transcribed before the batches waiting. A stretch
        # of one still recording goes ahead of a recording that has ended,
        # so the recording that ends next is the one whose last stretch is
        # transcribed first.
        "priority": (100 if run.stretch else 90) if recording.is_live else 0,
    }

    if run.stretch and recording.diarize and request["diarizer"] == "pyannote":
        # Each stretch is labelled on its own; the voices are what match the
        # labels across stretches when the Transcript is put together. Only
        # pyannote returns them; under Nemotron the stretches keep their own
        # labels, as a stretch with one voice does.
        request["return_speaker_embeddings"] = True

    if (
        not recording.translate
        and not recording.spoken_language
        and recogniser == "whisper"
    ):
        # Only meaningful on a detected transcribe. With the setting off, or
        # with translation turned off altogether, such a Recording is
        # transcribed in its winning language and the viewer says so.
        request["translate_if_mixed"] = settings_store.get(
            "translate_mixed"
        ) and settings_store.get("translation_available")

    if (
        recording.diarize
        and not recording.is_two_channel_call
        and request["diarizer"] == "pyannote"
    ):
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
    lane = whisperx.lane_for(job.recording)
    for run in job.runs.all().order_by("side__number"):
        if run.service_job_id:
            continue
        try:
            submitted = whisperx.submit(run.audio_path, request_for(run), lane)
        except whisperx.ServiceError as problem:
            return fail(job, problem.reason_class)
        except Exception:  # noqa: BLE001 - the last resort (v1.132.0)
            # A missing prepared file, or an answer of the wrong shape, used
            # to leave the Job queued for ever and handed over every minute.
            log.exception("job %s could not be handed over", job.id)
            return fail(job, Reason.INTERNAL)

        run.service_job_id = submitted.id
        run.lane = lane
        run.state = "queued"
        run.position = submitted.position
        run.audio_minutes_ahead = submitted.audio_minutes_ahead
        run.submitted = timezone.now()
        run.save()

    job.state = JobState.QUEUED
    job.save(update_fields=["state"])
    log.info("job %s handed over: %d run(s)", job.id, job.runs.count())
    return job


# How many polls a Run may be missing from the service's list before its Job
# is failed as service_restarted (v1.131.0): about half a minute.
POLLS_BEFORE_MISSING = 10


def _number(value) -> float | None:
    """A float from the service's answer, or None for anything that is not one
    (v1.132.0): a percent of "n/a" used to kill the poll each minute."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _whole(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def take_state_from(
    job: Job, service_jobs: dict[str, dict], silent_lanes: frozenset = frozenset()
) -> Job:
    """Bring one Job up to date from what the service just said.

    The service is asked once for everything, so this reads from that one
    answer rather than asking again per Run. The Runs are read once too
    (v1.134.0; live_jobs prefetches them), and a Run is written only when
    something about it changed, with the fields that did: ten queued Jobs
    used to cost thirty queries a poll with nothing to say.
    """
    runs = list(job.runs.all())
    for run in runs:
        state = service_jobs.get(run.service_job_id)
        if state is None:
            if run.lane in silent_lanes:
                # The lane did not answer this round (v1.132.0): its Runs
                # are left where they were, not counted as missing.
                continue
            if run.service_job_id and run.state not in ("done", "failed", "cancelled"):
                # The service does not list it (v1.131.0): its store was
                # recreated, its token changed, or the job aged out. Before
                # a miss is counted the service is asked for that one Run
                # (v1.134.0): an answer is its state, and only a service
                # that has no such job, or none, counts against it. A few
                # polls' grace, then the Job fails plainly rather than
                # staying queued for ever.
                state = _asked_for(run)
                if state is None:
                    run.missing_polls += 1
                    run.save(update_fields=["missing_polls"])
                    if run.missing_polls >= POLLS_BEFORE_MISSING:
                        run.failure_class = Reason.SERVICE_RESTARTED
                        run.save(update_fields=["failure_class"])
                        return fail(job, Reason.SERVICE_RESTARTED)
                    continue
            else:
                continue

        changed = _take(run, state)
        if changed:
            run.save(update_fields=sorted(changed))

    if job.open:
        # A stretch that fails while the recording continues does not fail
        # the recording: it is written off for now and cut again at Stop,
        # from the whole file, when the tail is sent.
        from core import live

        for run in [one for one in runs if one.failure_class and one.stretch]:
            log.warning(
                "stretch %d of recording %s failed (%s); again at Stop",
                run.stretch,
                job.recording_id,
                run.failure_class,
            )
            live.mark_stretch(job.recording, run.stretch, "failed")
            if run.service_job_id:
                whisperx.delete(run.service_job_id, run.lane)
            run.delete()
            runs.remove(run)

    failed = next((run for run in runs if run.failure_class), None)
    if failed is not None:
        # One Run failing fails the Job as a whole, with that Run's reason.
        # The other Runs are still at the service, so they are cancelled to
        # give the card back rather than left to run for nobody.
        for run in runs:
            if run.service_job_id and run is not failed:
                whisperx.delete(run.service_job_id, run.lane)
        return fail(job, failed.failure_class)

    if any(run.state == "running" for run in runs):
        if job.started is None:
            job.started = timezone.now()
            job.state = JobState.RUNNING
            job.save(update_fields=["started", "state"])
        elif job.state != JobState.RUNNING:
            job.state = JobState.RUNNING
            job.save(update_fields=["state"])

    if runs and all(run.state == "done" for run in runs) and not job.open:
        return relabel(job) if job.kind == SPEAKERS else merge(job)

    return job


def _asked_for(run: Run) -> dict | None:
    """The service's own answer for one Run the list left out, or None when
    it has no such job or cannot say (v1.134.0)."""
    try:
        return whisperx.status_of(run.service_job_id, run.lane)
    except whisperx.ServiceError as problem:
        log.warning("run %s could not be asked for: %s", run.pk, problem)
        return None


def _take(run: Run, state: dict) -> set[str]:
    """Put one status body on a Run; the names of the fields that changed."""
    before = {
        name: getattr(run, name)
        for name in (
            "missing_polls",
            "state",
            "stage",
            "percent",
            "position",
            "audio_minutes_ahead",
            "failure_class",
        )
    }
    run.missing_polls = 0
    run.state = str(state.get("state") or run.state)
    run.stage = str(state.get("stage") or "")
    run.percent = _number(state.get("percent"))
    run.position = _whole(state.get("position"))
    run.audio_minutes_ahead = _number(state.get("audio_minutes_ahead"))
    if state["state"] in ("failed", "cancelled") and not run.failure_class:
        failure = state.get("failure") or {}
        run.failure_class = failure.get("reason_class") or Reason.INTERNAL
    return {name for name, was in before.items() if getattr(run, name) != was}


def merge(job: Job) -> Job:
    """Turn the Runs' results into the one Transcript.

    Segments are merged by time. Speaker labels arrive per Run as SPEAKER_00
    and on, which mean nothing to a person and nothing across Sides, so they
    are renamed before anybody sees them.

    Not one transaction any more (v1.134.0): the results are fetched from the
    service first, which can take minutes for a long recording, and only the
    storing runs inside a transaction. A transaction held open across the
    fetch kept locks and a connection busy for nothing.
    """
    job.merging = True
    job.save(update_fields=["merging"])

    try:
        results = {}
        for run in job.runs.all():
            results[run.pk] = whisperx.result(run.service_job_id, run.lane)
    except whisperx.ServiceError as problem:
        return fail(job, problem.reason_class)
    except Exception:  # noqa: BLE001 - the last resort (v1.132.0)
        # Anything else here used to kill the poll and have the merge tried
        # again every minute for ever, every other job waiting behind it.
        log.exception("the results of job %s could not be fetched", job.id)
        return fail(job, Reason.INTERNAL)

    try:
        # One transaction (v1.131.0): the old Transcript is deleted before the
        # new one is built, so a failure here rolls back to before the delete
        # and the person keeps what they had; the failure is then written.
        with transaction.atomic():
            transcript = _store(job, results)
    except Exception:  # noqa: BLE001 - anything here is the same failure
        log.exception("the transcript of job %s could not be stored", job.id)
        return fail(job, Reason.MERGE_FAILED)

    # A Live recording's Speakers are named from the taps made while it ran.
    if job.recording.is_live and job.recording.speaker_taps:
        from core import live

        try:
            live.name_from_taps(job.recording, transcript)
        except Exception:  # noqa: BLE001 - a naming that fails leaves the labels
            log.exception(
                "the taps of recording %s could not be applied", job.recording_id
            )

    # The Call system's lines (ADR 0021, v1.138.0), before anything reads the
    # Speakers: the check, the names and the side rule never see them.
    from core import call_system, clock_check

    call_system.on_landed(transcript)
    # The clock verdict (ADR 0022, v1.151.0): the lines against the audio's
    # own pauses, before the check reads anything and while the prepared
    # audio is still on disk.
    clock_check.on_landed(transcript)

    for run in job.runs.all():
        whisperx.delete(run.service_job_id, run.lane)

    job.state = JobState.DONE
    job.merging = False
    job.finished = timezone.now()
    job.save()
    # A video's vision is queued, marked for tonight, or left for an Admin
    # before the Batch is looked at, so the Batch's mail knows (Phase 4
    # chapter 5).
    from core import vision

    vision.on_transcript(job.recording)
    # The English from the words as spoken (ADR 0026, v1.162.0), before the
    # summary and the check are queued so they read it once it is there,
    # and before the Batch is looked at so its mail waits for it.
    from core import translation

    translation.on_transcript(job.recording)
    # Its summary tonight, when the upload carried the tick (Phase 9 chapter 5).
    from core import summaries_tonight

    summaries_tonight.on_transcript(job.recording)
    # The Speaker check, when the office has it on (Phase 5 chapter 3).
    from core import speaker_check

    speaker_check.on_transcript(job.recording)
    # A voice named across the case (Phase 9 chapter 2).
    from core import vocabulary

    vocabulary.on_transcript(job.recording)
    # A Live recording transcribed in stretches whose speakers could not be
    # matched by voice gets one pass over the whole recording (v1.94.0).
    if job.recording.is_live and any(run.stretch for run in job.runs.all()):
        from core import live

        live.ask_for_speakers_pass(job.recording, results)
    _the_batch_may_have_finished(job)

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


# The speakers pass (v1.94.0) ----------------------------------------------------------
#
# Each stretch of a Live recording is diarized on its own, and under Nemotron
# the stretches carry no voice prints to match their labels by, so two people
# in a nine-minute meeting came back as four speakers. One diarize-only pass
# over the whole recording at Stop says who spoke when across all of it; every
# line then takes the speaker of the turn that covers most of it, numbered in
# the order people first spoke, and the taps name them again. The words are
# not touched. A line somebody has already renamed keeps its name.

MACHINE_NAME = re.compile(r"^(?:.+ )?Speaker \d+$")


def relabel(job: Job) -> Job:
    """The pass landed: the Transcript's Segments take the whole recording's
    speakers. A pass that fails leaves the stretches' labels as they were.

    The results are fetched before any transaction is opened (v1.134.0), as
    in merge; the relabelling itself is one transaction, so a pass that
    fails half-way leaves every label as it was.
    """
    from core import live

    recording = job.recording
    transcript = getattr(recording, "transcript", None)
    if transcript is None:
        live.mark_speakers_pass(recording, "failed")
        return fail(job, Reason.MERGE_FAILED)
    try:
        results = {
            run.pk: whisperx.result(run.service_job_id, run.lane)
            for run in job.runs.all()
        }
    except whisperx.ServiceError as problem:
        live.mark_speakers_pass(recording, "failed")
        return fail(job, problem.reason_class)
    except Exception:  # noqa: BLE001 - the last resort (v1.132.0)
        log.exception("the speakers pass of job %s could not be fetched", job.id)
        live.mark_speakers_pass(recording, "failed")
        return fail(job, Reason.INTERNAL)

    runs = {run.pk: run for run in job.runs.all()}
    many_sides = len({run.side_id for run in runs.values()}) > 1
    count: dict = {}
    changed = 0
    with transaction.atomic():
        for run_id, result in results.items():
            turns = (result.get("speakers") or {}).get("turns") or []
            changed += apply_turns(
                transcript, runs[run_id].side, turns, many_sides, count
            )

        if recording.speaker_taps:
            try:
                live.name_from_taps(recording, transcript)
            except Exception:  # noqa: BLE001 - a naming that fails leaves the labels
                log.exception(
                    "the taps of recording %s could not be applied", recording.pk
                )

        for run_id, result in results.items():
            run = runs[run_id]
            run.settings_used = result.get("settings_used", {})
            run.service_versions = result.get("service", {})
            run.timings = result.get("timings_seconds", {})
            run.finished = timezone.now()
            run.save(
                update_fields=[
                    "settings_used",
                    "service_versions",
                    "timings",
                    "finished",
                ]
            )
    for run in runs.values():
        whisperx.delete(run.service_job_id, run.lane)

    job.state = JobState.DONE
    job.finished = timezone.now()
    job.save(update_fields=["state", "finished"])
    live.mark_speakers_pass(recording, "done")
    audit.write(
        audit.Category.JOBS,
        "Speakers matched",
        system="worker",
        affected_user=recording.user,
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
        lines_changed=changed,
        speakers=sum(count.values()),
    )
    log.info(
        "speakers pass for %s: %d line(s) changed, %d speaker(s)",
        recording.pk,
        changed,
        sum(count.values()),
    )
    return job


def apply_turns(transcript, side, turns: list, many_sides: bool, count: dict) -> int:
    """Give each Segment of a Side the speaker of the turn that covers most of
    it. `count` carries the numbering across Sides. Returns the lines changed.

    A Segment nobody's turn touches keeps the label it had; a Segment a person
    renamed keeps the name.
    """
    ordered = sorted(
        (
            {
                "start": float(one["start"]),
                "end": float(one["end"]),
                "speaker": str(one["speaker"]),
            }
            for one in turns
        ),
        key=lambda one: (one["start"], one["end"]),
    )
    named: dict[str, str] = {}
    changed = []
    for segment in transcript.segments.filter(side=side).order_by("start", "pk"):
        best, most = None, 0.0
        for turn in ordered:
            if turn["end"] <= segment.start:
                continue
            if turn["start"] >= segment.end:
                break
            overlap = min(turn["end"], segment.end) - max(turn["start"], segment.start)
            if overlap > most:
                best, most = turn["speaker"], overlap
        if best is None:
            continue
        if best not in named:
            count[side.pk] = count.get(side.pk, 0) + 1
            named[best] = (
                f"{side.name} Speaker {count[side.pk]}"
                if many_sides
                else f"Speaker {count[side.pk]}"
            )
        name = named[best]
        if segment.speaker and not MACHINE_NAME.match(segment.speaker):
            continue
        if segment.speaker == name and segment.speaker_label == best:
            continue
        segment.speaker = name
        segment.speaker_label = best
        changed.append(segment)
    # Written in batches (v1.134.0) rather than one UPDATE per line: a long
    # recording's pass used to hold its transaction through thousands.
    Segment.objects.bulk_update(changed, ["speaker", "speaker_label"], batch_size=500)
    return len(changed)


def _store(job: Job, results: dict) -> Transcript:
    """Write the Transcript and its Segments, and keep the Provenance.

    The notes on the old Transcript's lines are remembered first and carried
    to the new lines at their moments (Phase 8 chapter 2).
    """
    from core import notes

    kept = notes.remember(job.recording)
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
    many_sides = len({run.side_id for run in runs.values()}) > 1
    in_stretches = any(run.stretch for run in runs.values())
    across = (
        _names_across_stretches(results, runs, many_sides, job.recording.diarize)
        if in_stretches
        else {}
    )

    segments = []
    for run_id, result in results.items():
        run = runs[run_id]
        names = (
            across[run_id]
            if in_stretches
            else _speaker_names(result, run.side, many_sides, job.recording.diarize)
        )
        # A stretch's times start at zero; the Recording's clock starts at
        # the stretch's own offset.
        shift = run.offset_seconds if run.stretch else 0.0
        for segment in result.get("segments", []):
            words = segment.get("words") or []
            if shift:
                words = [
                    {
                        **word,
                        **({"start": word["start"] + shift} if "start" in word else {}),
                        **({"end": word["end"] + shift} if "end" in word else {}),
                    }
                    for word in words
                ]
            segments.append(
                Segment(
                    transcript=transcript,
                    side=run.side,
                    start=(segment.get("start") or 0.0) + shift,
                    end=(segment.get("end") or 0.0) + shift,
                    text=(segment.get("text") or "").strip(),
                    speaker=names.get(segment.get("speaker", ""), names.get("", "")),
                    speaker_label=segment.get("speaker", "") or "",
                    words=words,
                    # The line's own language under Qwen3-ASR (ADR 0025,
                    # v1.162.0); the Whisper path gives none.
                    language=(segment.get("language") or "")[:8],
                )
            )

    segments.sort(key=lambda one: one.start)
    shared = _the_stretch_on_both_sides(segments, job.recording)
    if shared:
        transcript.shared_segments = shared
        transcript.save(update_fields=["shared_segments"])
    Segment.objects.bulk_create(segments, batch_size=500)
    notes.carry(kept, transcript)

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

    # Side 2 in start order with each text made plain once (v1.134.0): the
    # match used to visit every Side 2 line for every long Side 1 line and
    # make the text plain on each visit. A pointer walks Side 2 instead, as
    # the Side 1 lines are in start order too, and only the lines within a
    # second of the Side 1 line's start are looked at.
    second = sorted(second, key=lambda one: one.start)
    plain = [_plainly(other.text) for other in second]
    pairs = []
    taken = set()
    pointer = 0
    for one in sorted(first, key=lambda one: one.start):
        words = _plainly(one.text)
        if len(words) < LONG_ENOUGH:
            continue
        while pointer < len(second) and (
            second[pointer].start < one.start - SAME_MOMENT_SECONDS
        ):
            pointer += 1
        for index in range(pointer, len(second)):
            other = second[index]
            if other.start - one.start > SAME_MOMENT_SECONDS:
                break
            if index in taken:
                continue
            if plain[index] != words:
                continue
            pairs.append((one, other))
            taken.add(index)
            break

    if len(pairs) < A_STRETCH:
        return 0

    for kept, copy in pairs:
        kept.speaker = BOTH_SIDES
        copy.same_as_other_side = True
    return len(pairs)


def _cosine(a: list, b: list) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def _names_across_stretches(
    results: dict, runs: dict, many_sides: bool, diarized: bool
) -> dict:
    """Speaker names for a Transcript put together from stretches.

    The engine labels each stretch on its own, SPEAKER_00 and on, so the same
    label in two stretches may be two people and two labels one person. The
    voice embeddings the stretches were asked for say which: a label whose
    voice is close enough to one already named is that person; a new voice is
    the next Speaker. Stretches are taken in order, on each Side, so the
    numbering follows the order people first spoke. A stretch with no
    embeddings (an engine that gave none, or separation off) keeps its own
    labels numbered after the rest.
    """
    from core import live

    names: dict = {}
    voices: dict = {}  # side_id -> [(name, embedding)]
    count: dict = {}  # side_id -> speakers named so far
    for run_id, run in sorted(
        runs.items(), key=lambda pair: (pair[1].side.number, pair[1].stretch)
    ):
        result = results[run_id]
        side = run.side
        labels = sorted(result.get("speakers", {}).get("labels", []))
        spoken = result.get("speakers", {})
        embeddings = (spoken.get("embeddings") or {}) if diarized else {}
        mapping = {"": side.name if many_sides else ""}
        if not diarized or not labels:
            names[run_id] = mapping
            continue
        for label in labels:
            vector = embeddings.get(label)
            found = None
            if vector:
                best = 0.0
                for name, known in voices.setdefault(side.pk, []):
                    close = _cosine(vector, known)
                    if close > best:
                        best, found = close, name
                if best < live.SAME_VOICE:
                    found = None
            if found is None:
                count[side.pk] = count.get(side.pk, 0) + 1
                found = (
                    f"{side.name} Speaker {count[side.pk]}"
                    if many_sides
                    else f"Speaker {count[side.pk]}"
                )
                if vector:
                    voices.setdefault(side.pk, []).append((found, vector))
            mapping[label] = found
        names[run_id] = mapping
    return names


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


def _the_batch_may_have_finished(job: Job) -> None:
    """The "Batch finished" mail, if this Job was the last thing in its Batch."""
    from core import mail

    mail.note_batch_progress(job.recording)


def fail(job: Job, reason_class: str) -> Job:
    """End a Job with one reason class, and say so in the log.

    Files are kept, so a Retry reuses the media steps that already worked.
    """
    job.state = JobState.FAILED
    job.merging = False
    job.failure_class = reason_class
    job.finished = timezone.now()
    job.save()
    _the_batch_may_have_finished(job)
    if job.kind == SPEAKERS:
        # The Transcript stays as the stretches made it; the Details say why
        # the labels are per stretch (v1.94.0).
        from core import live

        live.mark_speakers_pass(job.recording, "failed")

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
    # The Runs come with the Jobs (v1.134.0): the poll reads each Job's Runs
    # once, from here, rather than querying per Job.
    return (
        Job.objects.filter(state__in=JobState.LIVE)
        .select_related("recording")
        .prefetch_related("runs")
    )


def something_is_running() -> bool:
    """Whether any Run of a live Job is running at the service (v1.134.0):
    the poll asks every three seconds while one is, every thirty while
    everything is still waiting its turn."""
    return Run.objects.filter(job__state__in=JobState.LIVE, state="running").exists()


def ready_without_a_job():
    """Recordings that are Ready and have not joined the line yet."""
    return Recording.objects.filter(media_state=MediaState.READY, jobs__isnull=True)


def without_a_playback_copy(older_than_seconds: int = 600):
    """Ready recordings whose playback copy never came (v1.132.0): the task
    is deferred once, and a copy whose making died is made again by the
    minute sweep after ten minutes."""
    stale = timezone.now() - dt.timedelta(seconds=older_than_seconds)
    return Recording.objects.filter(
        media_state=MediaState.READY,
        playback_ready=False,
        created__lt=stale,
        playback_tries__lt=3,
    )


def never_handed_over(older_than_seconds: int = 120):
    """Live Jobs with a Run that has no service id after a couple of minutes:
    a hand-over that was lost (v1.131.0), handed over again by the sweep."""
    stale = timezone.now() - dt.timedelta(seconds=older_than_seconds)
    return (
        Job.objects.filter(
            state__in=JobState.LIVE,
            open=False,
            created__lt=stale,
            runs__service_job_id="",
        )
        .exclude(runs__isnull=True)
        .distinct()
    )


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
