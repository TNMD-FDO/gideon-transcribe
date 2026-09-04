"""Jobs, Runs, and the Transcript they produce.

Two lines exist by design and their units differ. The app's Job is one
Recording; the WhisperX service's job is one Side, which the app calls a Run. A
Job holds one Run per Side, and the Runs' Segments are merged into the one
Transcript by time.

The app keeps its own Queue only for what the service cannot know: Batches, the
one-Batch rule, the order of a Recording's Sides, the keep-alive rule, and what
users see. Nothing is held back and nothing is reordered.
"""

from __future__ import annotations

import uuid

from django.db import models


class JobState:
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"

    CHOICES = [
        (QUEUED, "Queued"),
        (RUNNING, "Running"),
        (DONE, "Done"),
        (FAILED, "Failed"),
        (CANCELLED, "Cancelled"),
    ]

    LIVE = (QUEUED, RUNNING)


class Reason:
    """Why a Job failed. The service's nine classes pass through unchanged.

    The app adds its own for the things the service cannot know about.
    """

    # The service's, from its contract.
    BAD_INPUT = "bad_input"
    TOO_LARGE = "too_large"
    TOO_LONG = "too_long"
    MODEL_UNAVAILABLE = "model_unavailable"
    GPU_ERROR = "gpu_error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    SERVICE_RESTARTED = "service_restarted"
    INTERNAL = "internal"

    # The app's own.
    MEDIA_FAILED = "media_failed"
    SERVICE_UNREACHABLE = "service_unreachable"
    SERVICE_REFUSED = "service_refused"
    RESULT_EXPIRED = "result_expired"
    MERGE_FAILED = "merge_failed"

    # One plain message each, for the person; the class itself is for Admins.
    MESSAGES = {
        BAD_INPUT: "The audio in this recording could not be read.",
        TOO_LARGE: "This recording is too large for the transcription service.",
        TOO_LONG: "This recording is too long for the transcription service.",
        MODEL_UNAVAILABLE: ("The transcription models are not installed. Contact IT."),
        GPU_ERROR: "The transcription service's card faulted. Try again.",
        TIMEOUT: "Transcription took longer than allowed and was stopped.",
        CANCELLED: "Cancelled.",
        SERVICE_RESTARTED: (
            "The transcription service restarted while this was running."
        ),
        INTERNAL: "The transcription service failed. Contact IT.",
        MEDIA_FAILED: "This recording could not be prepared for transcription.",
        SERVICE_UNREACHABLE: (
            "The transcription service could not be reached. Try again later."
        ),
        SERVICE_REFUSED: ("The transcription service refused this app. Contact IT."),
        RESULT_EXPIRED: (
            "The transcript was not collected in time and is gone. Try again."
        ),
        MERGE_FAILED: "The transcript could not be stored. Try again.",
    }


# What the service reports, and the plain words a person reads instead.
STEPS = {
    "loading model": "Loading the model",
    "transcribing": "Transcribing",
    "aligning": "Aligning words",
    "diarizing": "Separating speakers",
    "finishing": "Finishing",
}
MERGING = "Merging sides"


class Job(models.Model):
    """One Recording's pass through the Queue, made the moment it is Ready."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recording = models.ForeignKey(
        "core.Recording", on_delete=models.CASCADE, related_name="jobs"
    )
    batch = models.ForeignKey(
        "core.Batch", on_delete=models.CASCADE, related_name="jobs"
    )

    state = models.CharField(
        max_length=20, choices=JobState.CHOICES, default=JobState.QUEUED
    )
    merging = models.BooleanField(default=False)

    failure_class = models.CharField(max_length=40, blank=True, default="")

    created = models.DateTimeField(auto_now_add=True)
    started = models.DateTimeField(null=True, blank=True)
    finished = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created"]
        indexes = [models.Index(fields=["state"])]

    def __str__(self) -> str:
        return f"job {self.id} for {self.recording_id}"

    @property
    def is_live(self) -> bool:
        return self.state in JobState.LIVE

    @property
    def failure_message(self) -> str:
        return Reason.MESSAGES.get(self.failure_class, "")

    @property
    def step(self) -> str:
        """The plain words a person reads while this Job runs.

        A Recording with more than one Side says which Side it is on, because
        otherwise the progress appears to go backwards when the second Side
        starts.
        """
        if self.merging:
            return MERGING
        running = self.runs.filter(state="running").order_by("side__number").first()
        if running is None:
            return ""

        step = STEPS.get(running.stage or "", "")
        if step == "Transcribing" and running.percent is not None:
            step = f"Transcribing {running.percent:.0f}%"

        total = self.runs.count()
        if total > 1:
            return f"Side {running.side.number} of {total}: {step}"
        return step


class Run(models.Model):
    """One Side's pass through the WhisperX service."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="runs")
    side = models.ForeignKey("core.Side", on_delete=models.CASCADE)

    # The service's own id for this Run, and the reference it knows it by. The
    # reference is this Run's id, which is what makes a repeated submission
    # return the job that already exists rather than a second one.
    service_job_id = models.CharField(max_length=64, blank=True, default="")

    state = models.CharField(max_length=20, default="pending")
    stage = models.CharField(max_length=30, blank=True, default="")
    percent = models.FloatField(null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)
    audio_minutes_ahead = models.FloatField(null=True, blank=True)

    failure_class = models.CharField(max_length=40, blank=True, default="")

    submitted = models.DateTimeField(null=True, blank=True)
    finished = models.DateTimeField(null=True, blank=True)

    # Everything the service echoed back, kept for the Provenance.
    settings_used = models.JSONField(default=dict, blank=True)
    service_versions = models.JSONField(default=dict, blank=True)
    timings = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["side__number"]
        indexes = [models.Index(fields=["state"])]

    def __str__(self) -> str:
        return f"run {self.id} of {self.job_id}"


class Transcript(models.Model):
    """What a Job produced: one per Recording, replaced by a Process again."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recording = models.OneToOneField(
        "core.Recording", on_delete=models.CASCADE, related_name="transcript"
    )
    job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True)

    created = models.DateTimeField(auto_now_add=True)

    # What the service ran and why, which is what the viewer's markers and the
    # export notices are built from.
    task_run = models.CharField(max_length=20, blank=True, default="")
    task_reason = models.CharField(max_length=30, blank=True, default="")
    language = models.CharField(max_length=10, blank=True, default="")
    language_probability = models.FloatField(null=True, blank=True)
    language_mixed = models.BooleanField(default=False)
    detection = models.JSONField(default=dict, blank=True)

    word_timestamps = models.BooleanField(default=False)
    word_timestamps_reason = models.CharField(max_length=30, blank=True, default="")

    # How many Segments the two Sides of a call said together, which the app
    # shows once rather than twice. Said out loud in the viewer and on every
    # export, because the app never quietly decides what a transcript shows.
    shared_segments = models.IntegerField(default=0)

    # Every setting the service echoed, its version, and its pins.
    provenance = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self) -> str:
        return f"transcript of {self.recording_id}"


class Segment(models.Model):
    """One stretch of speech. The Transcript is these, in order."""

    transcript = models.ForeignKey(
        Transcript, on_delete=models.CASCADE, related_name="segments"
    )
    side = models.ForeignKey("core.Side", on_delete=models.CASCADE, null=True)

    start = models.FloatField()
    end = models.FloatField()
    text = models.TextField()

    # The name a person reads, already renamed from the engine's own labels.
    speaker = models.CharField(max_length=60, blank=True, default="")

    # What the engine called this voice, kept beside the name because an
    # export's Appearances table prints both and a rename must not lose the
    # label the Provenance refers to.
    speaker_label = models.CharField(max_length=60, blank=True, default="")

    # Word timings, when the language could be aligned. A word the aligner
    # could not place keeps its word and loses its times.
    words = models.JSONField(default=list, blank=True)

    # Somebody changed the text. The viewer marks it and exports say so, so
    # that machine text and human text are never confused for one another.
    corrected = models.BooleanField(default=False)

    # The other Side said the same words at the same moment, which is what a
    # phone system's recorded announcement does: both parties hear it, so both
    # Sides transcribe it. This one is the second copy. It is kept, and left
    # out of the reading, the exports, and the search, while its twin is named
    # for both Sides. Nothing is deleted and the transcript says how many.
    same_as_other_side = models.BooleanField(default=False)

    class Meta:
        ordering = ["start", "id"]
        indexes = [models.Index(fields=["transcript", "start"])]

    def __str__(self) -> str:
        return f"{self.start:.1f}-{self.end:.1f}"
