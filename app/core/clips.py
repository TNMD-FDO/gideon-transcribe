"""Clips: a chosen span of a Recording, as a file for use outside the app.

A Clip is a start and an end and nothing more. It is linked to the Transcript
by time only: the Segments in a Clip are whichever overlap its span at the
moment somebody asks, never a stored list of Segment ids, so a Correction, a
merge, a rename, or a Process again needs no bookkeeping here. An Incident
clip (Phase 7 chapter 1) is the same row with `picture` set: the cameras
with each one's offset, the layout, the sound camera and the burn choices,
everything Render again needs, on the Recording of the camera it is heard
from.

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

    # An Incident clip (Phase 7 chapter 1): the Incident and the Event it was
    # cut from, kept while they live, and the picture: the cameras in tile
    # order with each one's offset and id, the layout, the sound camera, the
    # burn choices, the span on the Incident clock and the clock's second at
    # the first frame. All copied when the clip is made, so that a camera
    # re-synced or renamed afterwards changes nothing about this clip and
    # Render again remakes it the same. Null on a recording's own Clip.
    incident = models.ForeignKey(
        "core.Incident",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clips",
    )
    event = models.ForeignKey(
        "core.Event",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clips",
    )
    picture = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["recording", "start"]
        indexes = [models.Index(fields=["user", "created"])]

    def __str__(self) -> str:
        return f"{self.title} ({self.start:.1f}-{self.end:.1f})"

    @property
    def seconds(self) -> float:
        return max(0.0, self.end - self.start)

    @property
    def is_incident_clip(self) -> bool:
        return self.picture is not None

    @property
    def is_video(self) -> bool:
        if self.picture is not None:
            return True
        playback = self.recording.playback_path()
        return bool(playback and playback.suffix == ".mp4")

    @property
    def suffix(self) -> str:
        """mp4 for a video Recording, mp3 for an audio one."""
        return ".mp4" if self.is_video else ".mp3"

    @property
    def span_label(self) -> str:
        """The span as an audit row carries it: on the Incident clock for an
        Incident clip, on the Recording's own for any other."""
        low, high = self.incident_span if self.picture else (self.start, self.end)
        return f"{low:.1f}-{high:.1f}"

    @property
    def incident_span(self) -> tuple[float, float]:
        """An Incident clip's span in seconds on the Incident clock."""
        low, high = (self.picture or {}).get("span") or (self.start, self.end)
        return float(low), float(high)

    @property
    def span(self) -> str:
        """The span as a person reads it: clocks, or the Incident's times."""
        from core import exports, incidents

        if self.picture:
            low, high = self.incident_span
            clock = self.picture.get("clock")
            if clock is not None:
                return (
                    f"{incidents.hms(clock)} to {incidents.hms(clock + (high - low))}"
                )
            return f"{incidents.elapsed(low)} to {incidents.elapsed(high)}"
        return f"{exports.clock(self.start)} to {exports.clock(self.end)}"

    @property
    def length(self) -> str:
        return spell(self.seconds)

    @property
    def cameras_line(self) -> str:
        """ "4 cameras, Focus" on an Incident clip; nothing on any other."""
        if not self.picture:
            return ""
        count = len(self.picture.get("cameras") or [])
        layout = "Focus" if self.picture.get("layout") == "focus" else "Grid"
        return f"{count} camera{'' if count == 1 else 's'}, {layout}"

    @property
    def from_event(self) -> str:
        """ "from the event ..." under an Incident clip's title."""
        if not self.picture:
            return ""
        if self.event_id and self.event is not None:
            return f"from the event {self.event.text}"
        return "from an event since removed"

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


def spell(seconds: float) -> str:
    """A length a person reads: "45 s", "1 min 37 s", "1 h 2 min"."""
    whole = int(round(seconds or 0))
    hours, rest = divmod(whole, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours} h {minutes} min" if minutes else f"{hours} h"
    if minutes:
        return f"{minutes} min {secs} s" if secs else f"{minutes} min"
    return f"{secs} s"
