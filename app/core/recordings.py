"""Batches, Recordings, and Sides: what a person uploads and what it becomes.

A Batch is what somebody submits together. A Recording is one file in it. A
Side is one distinct sound source of a Recording that is transcribed on its
own, which for most recordings is the whole of it, and for a two-party phone
call is each channel.

None of this outlives the Login session that made it. What a person wants to
keep, they export.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from django.conf import settings as django_settings
from django.db import models


class MediaState:
    """Where a Recording has got to, before any transcription."""

    UPLOADING = "uploading"
    CHECKING = "checking"
    PREPARING = "preparing"
    READY = "ready"
    REJECTED = "rejected"
    FAILED = "failed"

    CHOICES = [
        (UPLOADING, "Uploading"),
        (CHECKING, "Checking"),
        (PREPARING, "Preparing"),
        (READY, "Ready"),
        (REJECTED, "Rejected"),
        (FAILED, "Failed"),
    ]

    # A Batch is unfinished while any Recording in it is still on its way.
    UNFINISHED = (UPLOADING, CHECKING, PREPARING)


class Refusal:
    """Why an upload was refused. One identifier per reason, never free text.

    The specification fixes `too_large`, `too_long`, `quota_exceeded`,
    `limit_exceeded`, `batch_in_progress`, `service_unreachable`, and
    `disk_full`, and leaves the identifiers for the format, empty-file, and
    duplicate refusals to the build. Those three are named for what they mean
    to the person who sees them.
    """

    TOO_LARGE = "too_large"
    TOO_LONG = "too_long"
    QUOTA_EXCEEDED = "quota_exceeded"
    LIMIT_EXCEEDED = "limit_exceeded"
    BATCH_IN_PROGRESS = "batch_in_progress"
    SERVICE_UNREACHABLE = "service_unreachable"
    DISK_FULL = "disk_full"

    EMPTY_FILE = "empty_file"
    ARCHIVE = "archive"
    NO_AUDIO = "no_audio"
    UNDECODABLE = "undecodable"
    ALREADY_UPLOADED = "already_uploaded"

    # Every refusal identifier, so that a media step can say whether what
    # went wrong was the file's fault or the app's.
    ALL = frozenset(
        {
            TOO_LARGE,
            TOO_LONG,
            QUOTA_EXCEEDED,
            LIMIT_EXCEEDED,
            BATCH_IN_PROGRESS,
            SERVICE_UNREACHABLE,
            DISK_FULL,
            EMPTY_FILE,
            ARCHIVE,
            NO_AUDIO,
            UNDECODABLE,
            ALREADY_UPLOADED,
        }
    )

    # The words the person sees. The figures are filled in where a setting
    # decides them.
    MESSAGES = {
        EMPTY_FILE: "The file is empty",
        ARCHIVE: (
            "Zip files are not accepted. Choose the recordings inside it instead."
        ),
        NO_AUDIO: "This file has no audio track",
        UNDECODABLE: "The audio in this file could not be decoded",
        TOO_LARGE: "Over the size limit ({limit})",
        TOO_LONG: "Over the length limit ({limit})",
        ALREADY_UPLOADED: "You already have this file in your recordings as {title}",
        QUOTA_EXCEEDED: (
            "This batch would go over your storage space ({used} of {quota}). "
            "Remove some files, or delete recordings you no longer need. IT can "
            "raise your space."
        ),
        LIMIT_EXCEEDED: (
            "A batch can hold up to {limit} files. Remove {over} to continue."
        ),
        BATCH_IN_PROGRESS: "You have a batch in progress; wait for it to finish.",
        SERVICE_UNREACHABLE: (
            "Transcription is not available right now. Try again later."
        ),
        DISK_FULL: "Uploading is paused because the server is low on space. Ask IT.",
    }


class Batch(models.Model):
    """What a person submitted together. A person has one unfinished at a time."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "core.User", on_delete=models.CASCADE, related_name="batches"
    )
    created = models.DateTimeField(auto_now_add=True)

    # A Process again makes a Batch of one Recording, marked so that lists can
    # say "Processing again" rather than showing it as a new upload.
    is_reprocessing = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created"]

    def __str__(self) -> str:
        return f"batch {self.id} for {self.user.username}"

    @property
    def is_finished(self) -> bool:
        """Finished when nothing in it is still on its way.

        A Batch with no Recordings at all is finished: it was submitted and
        everything in it was refused, or it never got that far.
        """
        return not self.recordings.filter(
            media_state__in=MediaState.UNFINISHED
        ).exists()

    @classmethod
    def unfinished_for(cls, user) -> Batch | None:
        for batch in cls.objects.filter(user=user):
            if not batch.is_finished:
                return batch
        return None


class Recording(models.Model):
    """One file somebody uploaded, and everything the app worked out about it."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(
        Batch, on_delete=models.CASCADE, related_name="recordings"
    )
    user = models.ForeignKey(
        "core.User", on_delete=models.CASCADE, related_name="recordings"
    )

    # The title starts as the file name without its extension and can be
    # changed. The original name stays, because it is the only way to
    # recognise a recording after it is discarded.
    title = models.CharField(max_length=300)
    original_filename = models.CharField(max_length=400)

    size_bytes = models.BigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True, default="", db_index=True)
    duration_seconds = models.FloatField(null=True, blank=True)

    media_state = models.CharField(
        max_length=20, choices=MediaState.CHOICES, default=MediaState.UPLOADING
    )
    playback_ready = models.BooleanField(default=False)

    refusal_class = models.CharField(max_length=40, blank=True, default="")
    failure_message = models.CharField(max_length=300, blank=True, default="")

    # The raw ffprobe output, kept for the Provenance. It is a fact about the
    # file, not content.
    probe = models.JSONField(default=dict, blank=True)

    # What the person chose, recorded per Recording at submission and copied
    # onto the Job, so the Provenance names exactly what was used.
    diarize = models.BooleanField(default=False)
    speakers_exactly = models.IntegerField(null=True, blank=True)
    speakers_between = models.JSONField(null=True, blank=True)
    translate = models.BooleanField(default=False)
    spoken_language = models.CharField(max_length=10, blank=True, default="")
    vocabulary = models.JSONField(default=list, blank=True)
    context = models.CharField(max_length=500, blank=True, default="")
    model = models.CharField(max_length=40, blank=True, default="")
    preprocessing = models.CharField(max_length=20, default="standard")

    # What the analysis found.
    is_two_channel_call = models.BooleanField(default=False)
    tracks_found = models.IntegerField(default=0)
    tracks_distinct = models.IntegerField(default=0)

    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created"]

    def __str__(self) -> str:
        return f"{self.title} ({self.id})"

    @property
    def folder(self) -> Path:
        """Where this Recording's bytes live. Ids only, never a name."""
        return django_settings.SCRATCH_DIR / str(self.user_id) / str(self.id)

    @property
    def original_path(self) -> Path:
        suffix = Path(self.original_filename).suffix.lower()
        return self.folder / f"original{suffix}"

    @property
    def is_ready(self) -> bool:
        return self.media_state == MediaState.READY

    def disk_bytes(self) -> int:
        """Everything on disk for this Recording, which is what a quota counts."""
        if not self.folder.exists():
            return 0
        return sum(
            path.stat().st_size for path in self.folder.rglob("*") if path.is_file()
        )


class Side(models.Model):
    """One distinct sound source of a Recording, transcribed on its own.

    Most Recordings have one. A two-party call has one per channel, and a file
    with genuinely different audio tracks has one per track, so that nothing on
    any track is missed.
    """

    WHOLE = "whole"
    CHANNEL = "channel"
    TRACK = "track"

    KINDS = [
        (WHOLE, "the whole recording"),
        (CHANNEL, "one channel of a two-channel call"),
        (TRACK, "one audio track"),
    ]

    recording = models.ForeignKey(
        Recording, on_delete=models.CASCADE, related_name="sides"
    )
    number = models.IntegerField()
    kind = models.CharField(max_length=10, choices=KINDS, default=WHOLE)

    # What a person reads: "Side 1", "Track 2", or nothing at all for a
    # recording with one side.
    name = models.CharField(max_length=40, blank=True, default="")

    class Meta:
        ordering = ["recording", "number"]
        constraints = [
            models.UniqueConstraint(
                fields=["recording", "number"], name="one_number_per_side"
            )
        ]

    def __str__(self) -> str:
        return self.name or f"side {self.number}"

    @property
    def asr_path(self) -> Path:
        """The prepared audio the WhisperX service is sent: 16 kHz, mono, PCM."""
        return self.recording.folder / f"asr-side{self.number}.wav"
