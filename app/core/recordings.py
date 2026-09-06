"""Batches, Recordings, and Sides: what a person uploads and what it becomes.

A Batch is what somebody submits together. A Recording is one file in it. A
Side is one distinct sound source of a Recording that is transcribed on its
own, which for most recordings is the whole of it, and for a two-party phone
call is each channel.

None of this outlives the Login session that made it, unless it is in a Case.
What a person wants to keep, they put in a Case or they export.
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
    # The wording key for the same refusal on somebody else's Case; the
    # reason class stays QUOTA_EXCEEDED.
    QUOTA_EXCEEDED_THEIRS = "quota_exceeded_theirs"
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
        # Not a reason class of its own: the same refusal, worded for an
        # upload into somebody else's Case, which counts against their space.
        "quota_exceeded_theirs": (
            "This batch would go over {owner}'s storage space ({used} of "
            "{quota}), which recordings added to their case count against. "
            "Remove some files, or ask them to make room."
        ),
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

    # "Email me when this batch finishes", ticked on the Upload page; and when
    # that message went, so it is sent once and never resent.
    email_when_done = models.BooleanField(default=False)
    mail_sent_at = models.DateTimeField(null=True, blank=True)

    # A Live recording's own Batch (Phase 3): one Recording, made on the
    # Record page, which never holds up the person's uploads.
    is_live = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created"]

    def __str__(self) -> str:
        return f"batch {self.id} for {self.user.username}"

    @property
    def is_finished(self) -> bool:
        """Finished when nothing in it is still on its way.

        Two things count, and missing either leaves a Batch looking finished
        while it is not: a Recording still uploading, being checked or being
        prepared, and a Job still queued or running at the service. A Batch
        that only watched the first would stop being watched the moment the
        audio was ready, with the transcription still to come, and it would
        let somebody start a second Batch while the first was still running.

        A Batch with no Recordings at all is finished: everything in it was
        refused, or it never got that far.
        """
        from core.jobs import JobState

        if self.recordings.filter(media_state__in=MediaState.UNFINISHED).exists():
            return False

        return not self.jobs.filter(state__in=JobState.LIVE).exists()

    @classmethod
    def unfinished_for(cls, user) -> Batch | None:
        """The person's one unfinished upload Batch, if any.

        A Live recording's Batch is not one: a person may record while a
        batch runs and upload while a recording is transcribed.
        """
        for batch in cls.objects.filter(user=user, is_live=False):
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

    # Empty means the Workspace, which is where every Recording is in Phase 1
    # and where most are afterwards. A Recording with a Case survives the
    # sign-out that would have discarded it.
    case = models.ForeignKey(
        "core.Case",
        on_delete=models.PROTECT,
        related_name="recordings",
        null=True,
        blank=True,
    )

    # Both are Case fields, and both stay empty in the Workspace: a Recording
    # is given a type and a description when it is added to a Case or moved
    # into one, and either may be skipped.
    recording_type = models.CharField(max_length=60, blank=True, default="")
    description = models.TextField(blank=True, default="")

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

    # A Live recording's facts (Phase 3): when it started, its sources, the
    # browser, the pauses, how it ended, and the sidecar upload its pieces
    # went into. Empty for an uploaded Recording. Facts about the recording,
    # never content.
    live = models.JSONField(null=True, blank=True)

    # While a Live recording ran: the moments a person was tapped as they
    # started talking (a moment and a name), from which the Transcript's
    # Speakers are named; and the Marks (a moment and an optional word). A
    # Mark's word is content and is never in a row or a message.
    speaker_taps = models.JSONField(default=list, blank=True)
    marks = models.JSONField(default=list, blank=True)

    # A Dictation (Phase 3): kept past sign-out on its own, in no Case unless
    # added to one, on its own clock (last_used) while it has no Case.
    is_dictation = models.BooleanField(default=False)
    last_used = models.DateTimeField(null=True, blank=True)

    @property
    def is_live(self) -> bool:
        return bool(self.live)

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

    # When the Discard marked this Recording, set before anything is
    # removed, so that a crash half way through leaves the mark: the next
    # minute finishes it, and the daily sweeper finishes anything that has
    # been marked for more than an hour.
    discarding_since = models.DateTimeField(null=True, blank=True)

    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created"]

    def __str__(self) -> str:
        return f"{self.title} ({self.id})"

    @property
    def folder(self) -> Path:
        """Where this Recording's bytes live. Ids only, never a name.

        A Recording in a Case sits under that Case, so moving one into a Case
        is a folder rename and nothing more. Renaming the Case moves nothing,
        because the path carries the Case's id and not its name.
        """
        if self.case_id:
            return (
                Path(django_settings.DATA_DIR)
                / "cases"
                / str(self.case_id)
                / str(self.id)
            )
        return django_settings.SCRATCH_DIR / str(self.user_id) / str(self.id)

    @property
    def original_path(self) -> Path:
        suffix = Path(self.original_filename).suffix.lower()
        return self.folder / f"original{suffix}"

    @property
    def waveform_path(self) -> Path:
        return self.folder / "waveform.json"

    def playback_path(self) -> Path | None:
        """The one file the player is given, whichever shape it took."""
        for suffix in (".mp4", ".m4a"):
            candidate = self.folder / f"playback{suffix}"
            if candidate.exists():
                return candidate
        return None

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
