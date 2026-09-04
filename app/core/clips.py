"""Clips: a chosen span of a Recording, as a file for use outside the app.

A Clip is a start and an end and nothing more. It is linked to the Transcript
by time only: the Segments in a Clip are whichever overlap its span at the
moment somebody asks, never a stored list of Segment ids, so a Correction, a
merge, a rename, or a Process again needs no bookkeeping here.

Nothing about a Clip goes stale except captions burned into a picture, which
are the one part that is written into the file rather than built when it is
downloaded. The excerpt and the caption file are made at download time like
every other export and are never stored.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from django.db import models

log = logging.getLogger("transcribe.clips")

# The shortest Clip anybody can save. The longest is an admin setting.
SHORTEST_SECONDS = 1.0


class RenderState:
    RENDERING = "rendering"
    READY = "ready"
    FAILED = "failed"

    CHOICES = [
        (RENDERING, "Rendering"),
        (READY, "Ready"),
        (FAILED, "Failed"),
    ]


class Clip(models.Model):
    """One span of one Recording, with a title, a note, and two options."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recording = models.ForeignKey(
        "core.Recording", on_delete=models.CASCADE, related_name="clips"
    )
    # Who saved it. In a Workspace that is always the owner; it is shown only
    # in a Case, where other people can save one (Phase 2).
    user = models.ForeignKey(
        "core.User", on_delete=models.CASCADE, related_name="clips"
    )

    title = models.CharField(max_length=120)
    # Kept inside the app and printed nowhere: not on an export, not in an
    # audit row, not in a file name.
    note = models.TextField(max_length=1000, blank=True, default="")

    start = models.FloatField()
    end = models.FloatField()

    burn_captions = models.BooleanField(default=False)
    include_excerpt = models.BooleanField(default=True)

    state = models.CharField(
        max_length=20, choices=RenderState.CHOICES, default=RenderState.RENDERING
    )
    failure_class = models.CharField(max_length=40, blank=True, default="")

    rendered = models.DateTimeField(null=True, blank=True)
    size_bytes = models.BigIntegerField(default=0)
    # What the Transcript looked like when the captions were burned in, so
    # that a Clip can say its captions are out of date without keeping a copy
    # of the text they were made from.
    captions_of = models.CharField(max_length=64, blank=True, default="")

    first_downloaded = models.DateTimeField(null=True, blank=True)
    downloads = models.IntegerField(default=0)

    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["recording", "start"]
        indexes = [models.Index(fields=["user", "created"])]

    def __str__(self) -> str:
        return f"{self.title} ({self.start:.1f}-{self.end:.1f})"

    @property
    def seconds(self) -> float:
        return max(0.0, self.end - self.start)

    @property
    def is_video(self) -> bool:
        playback = self.recording.playback_path()
        return bool(playback and playback.suffix == ".mp4")

    @property
    def suffix(self) -> str:
        """mp4 for a video Recording, mp3 for an audio one."""
        return ".mp4" if self.is_video else ".mp3"

    @property
    def folder(self) -> Path:
        return self.recording.folder / "clips"

    @property
    def path(self) -> Path:
        return self.folder / f"{self.id}{self.suffix}"

    @property
    def captions_are_stale(self) -> bool:
        """Only a picture with captions burned in can fall behind the text."""
        if not self.burn_captions or self.state != RenderState.READY:
            return False
        return self.captions_of != transcript_mark(self.recording)

    @property
    def shown_state(self) -> str:
        if self.captions_are_stale:
            return "Captions out of date"
        return dict(RenderState.CHOICES).get(self.state, self.state)

    def segments(self):
        """Whichever Segments overlap the span, right now."""
        transcript = getattr(self.recording, "transcript", None)
        if transcript is None:
            return []
        return list(
            transcript.segments.filter(
                start__lt=self.end, end__gt=self.start
            ).select_related("side")
        )


def transcript_mark(recording) -> str:
    """A short mark that changes whenever the Transcript's text does.

    It answers one question: has anything a caption would show changed since
    this Clip was rendered. A hash rather than a copy, so that nothing about
    the text can be read back out of it.
    """
    import hashlib

    transcript = getattr(recording, "transcript", None)
    if transcript is None:
        return ""

    digest = hashlib.sha256()
    for start, end, speaker, text in transcript.segments.values_list(
        "start", "end", "speaker", "text"
    ):
        digest.update(f"{start:.3f}|{end:.3f}|{speaker}|{text}|".encode())
    return digest.hexdigest()[:32]


def next_title(recording) -> str:
    """`Clip 1`, `Clip 2`, per Recording. Two Clips may still share a title."""
    return f"Clip {recording.clips.count() + 1}"
