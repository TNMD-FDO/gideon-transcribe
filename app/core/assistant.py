"""The AI assistant: Summary, Chat, and Speaker suggestions.

Three features, each run only when a user asks from the viewer, each working
from one Transcript and nothing else, each arriving whole. The calls run on
llm-worker, the one container on the engine's network; the pages poll. What
is stored lives as long as the Recording does: for the Login session in a
Workspace, and with the Case in a Case. Nothing typed, asked, or answered is
ever logged; the audit row is metadata only.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import time
import uuid
from urllib.parse import urlparse

from django.db import models
from django.utils import timezone

from core import audit, engine, prompts, settings_store

log = logging.getLogger("transcribe.assistant")

QUEUED, RUNNING, DONE, FAILED = "queued", "running", "done", "failed"
STATES = [(QUEUED, "queued"), (RUNNING, "running"), (DONE, "done"), (FAILED, "failed")]

# Starting values for the build gate, held in code, never settings: the time
# limits in seconds (doubled while the model may think), and the sampling.
TIME_LIMITS = {
    "summary": 300,
    "chat_turn": 120,
    "speaker_suggestions": 180,
    "moment": 120,
}
SAMPLING = {"temperature": 0.3, "top_p": 0.9}
SUGGESTION_SAMPLING = {"temperature": 0.0, "top_p": 1.0}

CUT_SHORT = "The answer was cut short."
# While the model may think, its thinking is billed against the same answer
# budget, so the cap is raised by this much to leave the answer its room: about
# a minute and a half of thinking on the Local engine, inside the doubled time
# limits. A small model thinks at length; when the whole budget still goes on
# thinking the answer is empty, and the page says so rather than "cut short".
THINKING_ALLOWANCE = 8000
# The reason word the page shows for that case; the audit row keeps llm_error.
THOUGHT_AWAY = "llm_thought_it_away"
THOUGHT_IT_AWAY = (
    "The model spent its whole budget thinking and never began the answer. "
    'Turn off "Let the model think before answering" on the AI assistant '
    "settings page, or try again."
)
SPOKEN = "the transcript"  # never logged; a placeholder for messages only


# Templates ---------------------------------------------------------------------------


class PromptTemplate(models.Model):
    """An Admin-editable instruction: Ground rules, Chat, Speaker suggestions, Case
    chat."""

    GROUND_RULES, CHAT, SUGGESTIONS = "ground_rules", "chat", "suggestions"
    CASE_CHAT = "case_chat"
    MOMENT = "moment"
    DIGEST = "digest"
    SPEAKER_CHECK = "speaker_check"
    INCIDENT_EVENTS = "incident_events"
    INCIDENT_MEMO = "incident_memo"
    INCIDENT_CHAT = "incident_chat"
    COMPARISON = "comparison"
    DEFAULTS = {
        GROUND_RULES: ("Ground rules", prompts.GROUND_RULES),
        CHAT: ("Chat", prompts.CHAT),
        SUGGESTIONS: ("Speaker suggestions", prompts.SUGGESTIONS),
        CASE_CHAT: ("Case chat", prompts.CASE_CHAT),
        MOMENT: ("Moment", prompts.MOMENT),
        DIGEST: ("Digest", prompts.DIGEST),
        SPEAKER_CHECK: ("Speaker check", prompts.SPEAKER_CHECK),
        INCIDENT_EVENTS: ("Proposed events", prompts.INCIDENT_EVENTS),
        INCIDENT_MEMO: ("Incident memo", prompts.INCIDENT_MEMO),
        INCIDENT_CHAT: ("Incident chat", prompts.INCIDENT_CHAT),
        COMPARISON: ("Comparison", prompts.COMPARISON),
    }

    key = models.CharField(max_length=30, unique=True)
    text = models.TextField()
    version = models.IntegerField(default=1)
    updated = models.DateTimeField(auto_now=True)
    # The hash of the shipped wording this row last took (made, reset, or
    # followed), so an upgrade can tell an unedited copy from the office's
    # own words (v1.53.0): unedited, it follows the new shipped wording.
    shipped_hash = models.CharField(max_length=16, blank=True, default="")

    @property
    def name(self) -> str:
        return self.DEFAULTS[self.key][0]

    @property
    def default_text(self) -> str:
        return self.DEFAULTS[self.key][1]

    @property
    def behind(self) -> bool:
        """Whether the shipped wording changed since this copy took it: an
        edited copy the Templates page tells about, so Reset is a choice."""
        return self.shipped_hash != prompts.text_hash(self.default_text)

    @classmethod
    def named(cls, key: str) -> PromptTemplate:
        """The template, made from the chapter's wording when first asked for,
        and brought to a later release's wording while nobody has edited it."""
        default = cls.DEFAULTS[key][1]
        row, _ = cls.objects.get_or_create(
            key=key,
            defaults={
                "text": default,
                "version": 1,
                "shipped_hash": prompts.text_hash(default),
            },
        )
        row.follow_shipped()
        return row

    def follow_shipped(self) -> bool:
        """An unedited copy takes the shipped wording of this release; the
        version rises as if reset. An edited copy is left as it is."""
        default = self.default_text
        if self.text == default:
            return False
        if prompts.text_hash(self.text) != self.shipped_hash:
            return False
        self.text = default
        self.version += 1
        self.shipped_hash = prompts.text_hash(default)
        self.save(update_fields=["text", "version", "shipped_hash", "updated"])
        return True

    def save_text(self, text: str) -> None:
        """Save raises the version by one; the text is never logged."""
        self.text = text
        self.version += 1
        self.save(update_fields=["text", "version", "updated"])

    def reset(self) -> None:
        self.save_text(self.default_text)
        self.shipped_hash = prompts.text_hash(self.default_text)
        self.save(update_fields=["shipped_hash"])


# The templates the app ships: the Standard summary and one per shipped
# Recording type, each with the types it is for. Built in: editable and
# resettable on the Templates page, never deleted, and made once the first
# time they are wanted, so an office that upgrades gets them too.
SHIPPED_TEMPLATES = (
    (
        "standard",
        "Standard summary",
        "A memo to the attorney: summary, people, what happened, statements "
        "that matter, names and dates, unclear parts.",
        (),
    ),
    (
        "video",
        "Video summary",
        "A memo from the words and the picture together: summary, people, what "
        "happened, statements that matter, names and dates.",
        (),
    ),
    (
        "jail_call",
        "Jail call summary",
        "Who is speaking, statements about the case, requests, threats or pressure.",
        ("Jail call",),
    ),
    (
        "body_camera",
        "Body camera summary",
        "A memo of the encounter from the words and the picture: people, what "
        "happened, commands and rights, statements that matter.",
        ("Body camera",),
    ),
    (
        "interview",
        "Interview summary",
        "Questions and answers, the account "
        "given, admissions and changes, rights and pressure.",
        ("Interview",),
    ),
    (
        "phone_call",
        "Phone call summary",
        "Who is speaking, key points, arrangements made.",
        ("Phone call",),
    ),
    (
        "hearing",
        "Hearing summary",
        "Rulings and dates, arguments, testimony, what the defendant says, next steps.",
        ("Hearing",),
    ),
    (
        "dictation",
        "Dictation memo",
        "The dictated words written out as the document, nothing summarised.",
        ("Dictation",),
    ),
    (
        "meeting",
        "Meeting summary",
        "What was decided, who is to do what, questions left open, what each "
        "person said.",
        ("Meeting",),
    ),
)


SHIPPED_DESCRIPTIONS = {key: line for key, _, line, _ in SHIPPED_TEMPLATES}


class SummaryTemplate(models.Model):
    """The shape a Summary takes.

    The shipped ones are built in and never deleted; an office adds its own
    with Add template. A template may be for one or more Recording types, and
    the viewer chooses it for a Recording of that type; one for no type is
    for any.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # The shipped templates' key ("standard", "jail_call", ...); "" for an
    # office's own. What Reset to default puts back is looked up by it.
    key = models.CharField(max_length=40, blank=True, default="")
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=200, blank=True, default="")
    text = models.TextField()
    version = models.IntegerField(default=1)
    enabled = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    built_in = models.BooleanField(default=False)
    # The Recording types this template is for, as the Recording types
    # setting names them; empty means any. A type removed from the setting
    # stays here, as a removed Role stays on a Person.
    recording_types = models.JSONField(default=list, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    # The hash of the shipped wording a built-in row last took (v1.53.0);
    # empty for an office's own template. See PromptTemplate.shipped_hash.
    shipped_hash = models.CharField(max_length=16, blank=True, default="")

    class Meta:
        ordering = ["-built_in", "name"]

    @property
    def shipped_text(self) -> str:
        """What Reset to default puts back, for a shipped template."""
        if self.key == "standard":
            return prompts.STANDARD_SUMMARY
        return prompts.SHIPPED_SUMMARIES.get(self.key, "")

    def is_for(self, recording_type: str) -> bool:
        wanted = (recording_type or "").strip().lower()
        return bool(wanted) and any(
            one.strip().lower() == wanted for one in self.recording_types or []
        )

    @classmethod
    def shipped(cls) -> None:
        """Make any shipped template that is not there yet, and bring every
        unedited one to this release's wording (v1.53.0)."""
        rows = {one.key: one for one in cls.objects.filter(built_in=True)}
        for key, name, description, types in SHIPPED_TEMPLATES:
            if key in rows:
                rows[key].follow_shipped()
                continue
            text = (
                prompts.STANDARD_SUMMARY
                if key == "standard"
                else prompts.SHIPPED_SUMMARIES[key]
            )
            cls.objects.create(
                key=key,
                name=name,
                description=description,
                text=text,
                built_in=True,
                recording_types=list(types),
                shipped_hash=prompts.text_hash(text),
                is_default=(
                    key == "standard"
                    and not cls.objects.filter(is_default=True).exists()
                ),
            )

    @classmethod
    def standard(cls) -> SummaryTemplate:
        cls.shipped()
        return cls.objects.get(built_in=True, key="standard")

    @classmethod
    def enabled_ones(cls) -> list[SummaryTemplate]:
        cls.shipped()
        return list(cls.objects.filter(enabled=True))

    @classmethod
    def for_type(cls, recording_type: str) -> list[SummaryTemplate]:
        """The Enabled templates for this type: the Default first, then by name."""
        found = [one for one in cls.enabled_ones() if one.is_for(recording_type)]
        return sorted(found, key=lambda one: (not one.is_default, one.name.lower()))

    @classmethod
    def chosen_for(cls, recording) -> SummaryTemplate:
        """What the viewer preselects: the type's template; else, for a video
        whose Moments reach answers, the Video summary; else the Default."""
        for_it = cls.for_type(getattr(recording, "recording_type", ""))
        if for_it:
            return for_it[0]
        if (
            features()["moments"]
            and settings_store.get("moments_in_answers")
            and has_picture(recording)
        ):
            video = cls.objects.filter(built_in=True, key="video", enabled=True).first()
            if video is not None:
                return video
        return cls.the_default()

    @classmethod
    def the_default(cls) -> SummaryTemplate:
        """Exactly one Default among the Enabled; the built-in one when none is set."""
        standard = cls.standard()
        chosen = cls.objects.filter(enabled=True, is_default=True).first()
        if chosen is None:
            if not standard.enabled:
                standard.enabled = True
            standard.is_default = True
            standard.save(update_fields=["enabled", "is_default"])
            chosen = standard
        return chosen

    def make_default(self) -> None:
        SummaryTemplate.objects.exclude(pk=self.pk).update(is_default=False)
        self.enabled = True
        self.is_default = True
        self.save(update_fields=["enabled", "is_default"])

    def save_text(self, text: str) -> None:
        self.text = text
        self.version += 1
        self.save(update_fields=["text", "version"])

    def reset(self) -> None:
        """Reset to default: the shipped wording back, the version up."""
        self.save_text(self.shipped_text)
        self.shipped_hash = prompts.text_hash(self.shipped_text)
        self.save(update_fields=["shipped_hash"])

    @property
    def behind(self) -> bool:
        """A built-in copy the office edited, whose shipped wording has since
        changed: the Templates page says so, and Reset is the office's choice."""
        return self.built_in and self.shipped_hash != prompts.text_hash(
            self.shipped_text
        )

    def follow_shipped(self) -> bool:
        """An unedited built-in copy takes this release's shipped wording and
        description; the version rises as if reset. Edited, it is left."""
        shipped = self.shipped_text
        if not self.built_in or self.text == shipped:
            return False
        if prompts.text_hash(self.text) != self.shipped_hash:
            return False
        self.text = shipped
        self.description = SHIPPED_DESCRIPTIONS.get(self.key, self.description)
        self.version += 1
        self.shipped_hash = prompts.text_hash(shipped)
        self.save(update_fields=["text", "description", "version", "shipped_hash"])
        return True


# What the features store -------------------------------------------------------


class Summary(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recording = models.ForeignKey(
        "core.Recording", on_delete=models.CASCADE, related_name="summaries"
    )
    asked_by = models.ForeignKey(
        "core.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    template = models.ForeignKey(
        SummaryTemplate, on_delete=models.SET_NULL, null=True, blank=True
    )
    # Snapshots, because a template is edited and a Summary keeps what it was made with.
    template_name = models.CharField(max_length=80)
    template_version = models.IntegerField(default=1)
    ground_rules_version = models.IntegerField(default=1)
    focus = models.CharField(max_length=200, blank=True, default="")
    length = models.CharField(max_length=10, default="standard")
    # Describe the recording at intervals before writing (Phase 4), and how
    # many described Moments the summary was handed (chapter 5).
    describe_first = models.BooleanField(default=False)
    moments_used = models.IntegerField(default=0)
    # Written from the Digest (chapter 6): how many parts it had; 0 when it
    # was written from the transcript and the camera block alone. And what
    # the lane is doing while it runs, for the card.
    digest_parts = models.IntegerField(default=0)
    stage = models.CharField(max_length=60, blank=True, default="")
    state = models.CharField(max_length=10, choices=STATES, default=QUEUED)
    reason_class = models.CharField(max_length=40, blank=True, default="")
    text = models.TextField(blank=True, default="")
    citations = models.JSONField(default=dict, blank=True)
    cut_short = models.BooleanField(default=False)
    model = models.CharField(max_length=120, blank=True, default="")
    # The Transcript this was written from, so a Summary of an earlier
    # Transcript says so after Process again.
    transcript_created = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    written_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created"]


class Chat(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recording = models.ForeignKey(
        "core.Recording", on_delete=models.CASCADE, related_name="chats"
    )
    asked_by = models.ForeignKey(
        "core.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    # From the first question: its first sixty characters, on a word.
    name = models.CharField(max_length=80, blank=True, default="")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]

    @staticmethod
    def name_from(question: str) -> str:
        words = question.strip().split()
        name = ""
        for word in words:
            if len(name) + len(word) + 1 > 60:
                break
            name = f"{name} {word}".strip()
        return name or question.strip()[:60] or "New chat"


class ChatTurn(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name="turns")
    number = models.IntegerField()
    question = models.TextField()
    answer = models.TextField(blank=True, default="")
    citations = models.JSONField(default=dict, blank=True)
    state = models.CharField(max_length=10, choices=STATES, default=QUEUED)
    reason_class = models.CharField(max_length=40, blank=True, default="")
    cut_short = models.BooleanField(default=False)
    model = models.CharField(max_length=120, blank=True, default="")
    transcript_created = models.DateTimeField(null=True, blank=True)
    asked_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["number"]


class Suggestion(models.Model):
    """A name for a Speaker who has none, with the line it came from."""

    PENDING, ACCEPTED, REJECTED = "pending", "accepted", "rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # On the Transcript, so Process again takes the suggestions with it.
    transcript = models.ForeignKey(
        "core.Transcript", on_delete=models.CASCADE, related_name="suggestions"
    )
    speaker = models.CharField(max_length=60)
    name = models.CharField(max_length=60)
    kind = models.CharField(max_length=10, default="name")
    confidence = models.CharField(max_length=10, default="medium")
    line = models.IntegerField(default=0)
    segment = models.ForeignKey(
        "core.Segment", on_delete=models.SET_NULL, null=True, blank=True
    )
    start = models.FloatField(default=0.0)
    quote = models.CharField(max_length=300, blank=True, default="")
    state = models.CharField(max_length=10, default=PENDING)
    created = models.DateTimeField(auto_now_add=True)


class SuggestionRun(models.Model):
    """One Suggest names click: what it is doing, so the panel can wait for it."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transcript = models.ForeignKey(
        "core.Transcript", on_delete=models.CASCADE, related_name="suggestion_runs"
    )
    asked_by = models.ForeignKey(
        "core.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    state = models.CharField(max_length=10, choices=STATES, default=QUEUED)
    reason_class = models.CharField(max_length=40, blank=True, default="")
    found = models.IntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created"]


class SpeakerCheck(models.Model):
    """One run of the Speaker check (Phase 5 chapter 3): queued as the
    Transcript lands or pressed on the Speakers page, so the page can wait
    for it and say how it went."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transcript = models.ForeignKey(
        "core.Transcript", on_delete=models.CASCADE, related_name="speaker_checks"
    )
    # Nobody when the check ran by itself as the Transcript landed.
    asked_by = models.ForeignKey(
        "core.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    state = models.CharField(max_length=10, choices=STATES, default=QUEUED)
    reason_class = models.CharField(max_length=40, blank=True, default="")
    found = models.IntegerField(default=0)
    windows = models.IntegerField(default=0)
    # Windows whose list was cut off at the answer cap (v1.56.0), so the
    # page can say the run did not see everything.
    cut_short = models.IntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created"]


class SpeakerCorrection(models.Model):
    """One line the Speaker check says belongs to another Speaker: proposed,
    never applied, until a person accepts it on the Speakers page. Hangs on
    the Transcript, so Process again takes it. Holds the line's words as the
    quote the page shows, and never a name that is not already a Speaker."""

    PENDING, ACCEPTED, DISMISSED = "pending", "accepted", "dismissed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transcript = models.ForeignKey(
        "core.Transcript", on_delete=models.CASCADE, related_name="corrections"
    )
    segment = models.ForeignKey(
        "core.Segment", on_delete=models.SET_NULL, null=True, blank=True
    )
    start = models.FloatField(default=0.0)
    quote = models.CharField(max_length=300, blank=True, default="")
    speaker_from = models.CharField(max_length=60)
    speaker_to = models.CharField(max_length=60)
    reason = models.CharField(max_length=120, blank=True, default="")
    state = models.CharField(max_length=10, default=PENDING)
    decided_by = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start", "created"]


class Moment(models.Model):
    """What the camera showed at one time of a video Recording, as a model described it.

    Hangs on the Transcript, as a Suggestion does, so Process again takes it
    with the old Transcript. Its text is a description and never the
    Transcript; the clip it was made from is never kept.
    """

    ASKED, CUE, INTERVAL = "asked", "cue", "interval"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transcript = models.ForeignKey(
        "core.Transcript", on_delete=models.CASCADE, related_name="moments"
    )
    segment = models.ForeignKey(
        "core.Segment", on_delete=models.SET_NULL, null=True, blank=True
    )
    # The chosen second, and the span of the clip shown around it.
    at = models.FloatField()
    span_start = models.FloatField(default=0.0)
    span_end = models.FloatField(default=0.0)
    # Asked for by a person, or one span of the picture record (source
    # interval, chapter 6); "cue" stays on rows made before v1.51.0.
    source = models.CharField(max_length=10, default=ASKED)
    # A question about the moment, answered from still frames; empty means a
    # description of the clip. Content, never logged.
    question = models.TextField(blank=True, default="")
    state = models.CharField(max_length=10, choices=STATES, default=QUEUED)
    reason_class = models.CharField(max_length=40, blank=True, default="")
    text = models.TextField(blank=True, default="")
    edited = models.BooleanField(default=False)
    model = models.CharField(max_length=120, blank=True, default="")
    # How many frames the engine was shown, for the Details panel; and how
    # long the call took, for the preparation's estimates (chapter 7).
    frames = models.IntegerField(default=0)
    seconds = models.FloatField(default=0.0)
    asked_by = models.ForeignKey(
        "core.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created = models.DateTimeField(auto_now_add=True)
    described_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["at", "created"]

    def __str__(self) -> str:
        return f"moment at {self.at:.1f}s of {self.transcript_id}"

    @property
    def is_question(self) -> bool:
        return bool((self.question or "").strip())


class DigestPart(models.Model):
    """One window of the Digest: the Transcript condensed with the camera lines in it.

    Phase 4 chapter 6. Kept per window with a signature of what it was made
    from, so a later summary remakes only the parts whose words or
    descriptions changed. Content, never logged, never shown.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transcript = models.ForeignKey(
        "core.Transcript", on_delete=models.CASCADE, related_name="digest_parts"
    )
    number = models.IntegerField(default=1)
    span_start = models.FloatField(default=0.0)
    span_end = models.FloatField(default=0.0)
    signature = models.CharField(max_length=64, blank=True, default="")
    text = models.TextField(blank=True, default="")
    moments_used = models.IntegerField(default=0)
    model = models.CharField(max_length=120, blank=True, default="")
    made_at = models.DateTimeField(null=True, blank=True)
    seconds = models.FloatField(default=0.0)
    # The part came back cut off at the cap and its window could not be
    # split further (one line): kept, and the Admin fold says so.
    cut_short = models.BooleanField(default=False)

    class Meta:
        ordering = ["number"]


class CueRun(models.Model):
    """One Describe the whole recording: the picture record being made.

    What it is doing, so the tab can wait: how many of how many spans are
    described so far. The sources transcript and media are left on rows made
    before v1.51.0, when the finders made Cues.
    """

    TRANSCRIPT, MEDIA, INTERVAL = "transcript", "media", "interval"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transcript = models.ForeignKey(
        "core.Transcript", on_delete=models.CASCADE, related_name="cue_runs"
    )
    source = models.CharField(max_length=12, default=TRANSCRIPT)
    asked_by = models.ForeignKey(
        "core.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    state = models.CharField(max_length=10, choices=STATES, default=QUEUED)
    reason_class = models.CharField(max_length=40, blank=True, default="")
    found = models.IntegerField(default=0)
    total = models.IntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created"]


# What is on and what is reachable ----------------------------------------------


def features() -> dict:
    """Which of the four features a page may show, and whether the engine answers."""
    on = bool(settings_store.get("assistant_available"))
    reachable = engine.is_reachable() if on else False
    return {
        "assistant": on,
        "summary": on and bool(settings_store.get("summary_available")),
        "chat": on and bool(settings_store.get("chat_available")),
        "suggestions": on and bool(settings_store.get("suggestions_available")),
        "moments": on and bool(settings_store.get("moments_available")),
        "speaker_check": on and bool(settings_store.get("speaker_check_available")),
        "reachable": reachable,
        "unavailable_line": engine.WHAT_TO_SAY.get(engine.UNREACHABLE, ""),
    }


def thinking() -> bool:
    return bool(settings_store.get("assistant_thinks"))


def _moments_on() -> bool:
    """Moments, from the settings alone: never the engine's minute check."""
    return bool(
        settings_store.get("assistant_available")
        and settings_store.get("moments_available")
    )


def record_on() -> bool:
    """The picture record (chapter 6): made for a summary, when the office says so."""
    return bool(_moments_on() and settings_store.get("picture_record_available"))


def digests_on() -> bool:
    return bool(_moments_on() and settings_store.get("digests_available"))


def stamp_on() -> bool:
    return bool(_moments_on() and settings_store.get("stamp_available"))


def clock_line(transcript) -> str:
    """The camera's clock for a prompt, when the stamp was read.

    The stamp is the Recording's (Phase 6 chapter 1); the Transcript is what
    every caller holds.
    """
    recording = getattr(transcript, "recording", None)
    return prompts.stamp_line(getattr(recording, "stamp", None))


def time_limit(feature: str) -> int:
    """The feature's time limit as set, doubled while the model may think."""
    return settings_store.time_limit_seconds(feature) * (2 if thinking() else 1)


def cap(answer_tokens: int) -> int:
    """The answer cap as sent: the feature's, plus room to think when thinking is on."""
    return answer_tokens + (settings_store.thinking_allowance() if thinking() else 0)


def window() -> int:
    return settings_store.engine_window_tokens()


class ThoughtItAway(engine.Problem):
    """The call failed the chapter's way, llm_error, but the page can say why."""

    def __init__(self) -> None:
        super().__init__(engine.ERROR, "the whole budget went on thinking")


def thought_it_away(answer: dict) -> bool:
    """Nothing said and the budget gone: every token went into thinking."""
    return answer["finish_reason"] == "length" and not answer["text"].strip()


def notice(model: str, when) -> str:
    """The AI notice with {model} and {date} filled from the call."""
    shown = settings_store.get("engine_display_name") or model or engine.model_name()
    text = settings_store.get("ai_notice") or ""
    return text.replace("{model}", shown).replace(
        "{date}", timezone.localtime(when).strftime("%d %B %Y") if when else ""
    )


# The calls ---------------------------------------------------------------------


def _messages(system: str, user: str, history: list[tuple[str, str]] | None = None):
    messages = [{"role": "system", "content": system}]
    for question, answer in history or []:
        messages.append({"role": "user", "content": question})
        messages.append({"role": "assistant", "content": answer})
    messages.append({"role": "user", "content": user})
    return messages


def _record(
    feature: str,
    recording,
    *,
    actor,
    templates: str,
    model: str,
    usage: dict,
    started: float,
    outcome: str,
    reason: str = "",
    **more,
):
    """The one audit row a call writes, metadata only, whatever happened.

    `more` is a Moment's source or a Digest part's number, never a word of it.
    """
    host = urlparse(engine.address()).hostname or ""
    audit.write(
        audit.Category.LLM,
        "AI assistant call",
        actor=actor,
        outcome=audit.Outcome.SUCCESS if outcome == "ok" else audit.Outcome.FAILURE,
        reason_class=reason,
        affected_user=(
            recording.user
            if actor is not None and recording.user_id != actor.pk
            else None
        ),
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
        feature=feature,
        model=model or engine.model_name(),
        endpoint_host=host,
        templates=templates,
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        duration_seconds=round(time.monotonic() - started, 1),
        **more,
    )


def _unreachable() -> engine.Problem | None:
    """Nothing waits: a call that finds the engine failing the check fails at once."""
    if not engine.is_reachable():
        return engine.Problem(
            engine.UNREACHABLE, "the engine is failing the minute check"
        )
    return None


def write_summary(summary_id) -> None:
    """One Summary, whole, from the whole Transcript."""
    summary = Summary.objects.filter(pk=summary_id).select_related("recording").first()
    if summary is None:
        return
    recording = summary.recording
    transcript = getattr(recording, "transcript", None)
    started = time.monotonic()
    ground = PromptTemplate.named(PromptTemplate.GROUND_RULES)
    template = summary.template or SummaryTemplate.the_default()
    templates_line = (
        f"ground-rules v{ground.version}; "
        f"{summary.template_name} v{summary.template_version}"
    )
    summary.state = RUNNING
    summary.ground_rules_version = ground.version
    summary.save(update_fields=["state", "ground_rules_version"])

    usage: dict = {}
    try:
        if transcript is None:
            raise engine.Problem(engine.ERROR, "there is no transcript")
        problem = _unreachable()
        if problem:
            raise problem
        # The picture first, when asked: the recording described at
        # intervals, in this lane, so the camera block below is full.
        # A video is prepared first (chapter 7): the record and the Digest,
        # by the transcript's own task if it is at it, else here and now.
        # Under a schedule the summary never starts the vision work: it is
        # written from the transcript, and Regenerate takes the vision in
        # later (chapter 5).
        from core import vision

        if (
            record_on()
            and has_picture(recording)
            and not prepared(transcript)
            and not vision.scheduled()
        ):
            summary.stage = "preparing"
            summary.save(update_fields=["stage"])
            wait_or_prepare(
                transcript,
                asked_by=summary.asked_by,
                still_wanted=lambda: Summary.objects.filter(pk=summary.pk).exists(),
            )
            # Deleted while the video was prepared: the preparation stands,
            # the transcript's own, and there is nothing left to write.
            if not Summary.objects.filter(pk=summary.pk).exists():
                return
            transcript.refresh_from_db()
        lines = prompts.lines_of(transcript)
        rendered = prompts.render(lines)
        seen = moments_for_answers(transcript)
        # The Digest (chapter 6): every scene informs, and a long recording
        # is never refused, because the Digest stands in for the transcript
        # when the transcript would not fit beside everything else.
        digest = digest_text(transcript) if seen and digests_on() else ""
        summary.digest_parts = transcript.digest_parts.count() if digest else 0
        summary.stage = "writing"
        summary.save(update_fields=["digest_parts", "stage"])
        # One account from the Digest (chapter 7); the two-source rules only
        # for a Summary that still reads the camera block.
        system = prompts.system_message(
            ground.text,
            template.text,
            prompts.with_narrative_rules(prompts.SUMMARY_FORMAT)
            if digest
            else prompts.with_camera_rules(prompts.SUMMARY_FORMAT, seen),
        )
        picture = prompts.digest_block(digest) if digest else prompts.camera_lines(seen)
        asked = prompts.summary_input(
            summary.focus, summary.length, len(seen), digest=bool(digest)
        )
        nature = "\n".join(
            part
            for part in [
                prompts.nature_line(recording, transcript),
                clock_line(transcript),
            ]
            if part
        )
        wanted = settings_store.summary_answer_cap(summary.length)
        user = "\n\n".join(part for part in [nature, rendered, picture, asked] if part)
        if not prompts.fits(system, user, answer_cap=cap(wanted), window=window()):
            if not digest:
                raise engine.Problem(engine.TOO_LONG, "the transcript is too long")
            user = "\n\n".join(part for part in [nature, picture, asked] if part)
            if not prompts.fits(system, user, answer_cap=cap(wanted), window=window()):
                raise engine.Problem(engine.TOO_LONG, "even the digest is too long")
        answer = engine.complete(
            _messages(system, user),
            max_completion_tokens=cap(wanted),
            thinking=thinking(),
            timeout=time_limit("summary"),
            **SAMPLING,
        )
        usage = answer
        summary.text = answer["text"].strip()
        summary.citations = prompts.citations(summary.text, lines, seen)
        if thought_it_away(answer):
            raise ThoughtItAway()
        summary.cut_short = answer["finish_reason"] == "length"
        summary.model = answer["model"]
        summary.moments_used = len(seen)
        summary.stage = ""
        summary.transcript_created = transcript.created
        summary.state = DONE
        summary.reason_class = ""
        summary.written_at = timezone.now()
        summary.save()
        _record(
            "summary",
            recording,
            actor=summary.asked_by,
            templates=templates_line,
            model=summary.model,
            usage=usage,
            started=started,
            outcome="ok",
        )
    except engine.Problem as problem:
        summary.state = FAILED
        summary.reason_class = (
            THOUGHT_AWAY if isinstance(problem, ThoughtItAway) else problem.reason
        )
        summary.save(update_fields=["state", "reason_class"])
        _record(
            "summary",
            recording,
            actor=summary.asked_by,
            templates=templates_line,
            model="",
            usage=usage,
            started=started,
            outcome=problem.reason,
            reason=problem.reason,
        )


def answer_turn(turn_id) -> None:
    """One Chat question, answered from the whole Transcript and the Chat so far."""
    turn = (
        ChatTurn.objects.filter(pk=turn_id)
        .select_related("chat", "chat__recording")
        .first()
    )
    if turn is None:
        return
    chat = turn.chat
    recording = chat.recording
    transcript = getattr(recording, "transcript", None)
    started = time.monotonic()
    ground = PromptTemplate.named(PromptTemplate.GROUND_RULES)
    template = PromptTemplate.named(PromptTemplate.CHAT)
    templates_line = f"ground-rules v{ground.version}; Chat v{template.version}"
    turn.state = RUNNING
    turn.save(update_fields=["state"])

    usage: dict = {}
    try:
        if transcript is None:
            raise engine.Problem(engine.ERROR, "there is no transcript")
        problem = _unreachable()
        if problem:
            raise problem
        from core import vision

        if (
            record_on()
            and has_picture(recording)
            and not prepared(transcript)
            and not vision.scheduled()
        ):
            wait_or_prepare(transcript, asked_by=chat.asked_by)
            transcript.refresh_from_db()
        lines = prompts.lines_of(transcript)
        rendered = prompts.render(lines)
        seen = moments_for_answers(transcript)
        # With a Digest (chapter 6) the chat is told the Digest instead of the
        # whole camera block, and the descriptions whose spans hold the times
        # the question names, so an answer about a time comes from the
        # description itself.
        digest = digest_text(transcript) if seen and digests_on() else ""
        near = (
            prompts.near_descriptions(
                seen,
                prompts.times_in(turn.question, float(recording.duration_seconds or 0)),
                settings_store.chat_descriptions_near(),
            )
            if digest
            else []
        )
        # The report for this recording (Phase 8 chapter 4, part 2).
        from core import documents

        papers, papers_note, named = documents.reading_block(
            documents.for_recording(recording) if recording.case_id else [],
            turn.question,
            heading="The report for this recording:",
        )
        system = prompts.system_message(
            ground.text,
            template.text,
            prompts.with_camera_rules(prompts.CHAT_FORMAT, seen)
            + ("\n\n" + documents.RULE if papers else ""),
        )
        earlier = [
            (one.question, one.answer)
            for one in chat.turns.filter(state=DONE, number__lt=turn.number)
        ]
        history = prompts.history_that_fits(
            earlier, settings_store.chat_history_tokens()
        )
        picture = (
            prompts.digest_block(digest) + prompts.near_block(near)
            if digest
            else prompts.camera_lines(seen)
        )
        user = "\n\n".join(
            part
            for part in [
                prompts.nature_line(recording, transcript),
                clock_line(transcript),
                rendered,
                picture,
                papers,
                turn.question,
            ]
            if part
        )
        history_text = "\n".join(q + "\n" + a for q, a in history)
        chat_cap = settings_store.chat_answer_cap()
        if not prompts.fits(
            system, user, history_text, answer_cap=cap(chat_cap), window=window()
        ):
            raise engine.Problem(engine.TOO_LONG, "the transcript is too long")
        answer = engine.complete(
            _messages(system, user, history),
            max_completion_tokens=cap(chat_cap),
            thinking=thinking(),
            timeout=time_limit("chat_turn"),
            **SAMPLING,
        )
        usage = answer
        turn.answer = documents.with_note(answer["text"].strip(), papers_note)
        turn.citations = {
            **prompts.citations(turn.answer, lines, seen),
            **documents.citations_in(turn.answer, named),
        }
        if thought_it_away(answer):
            raise ThoughtItAway()
        turn.cut_short = answer["finish_reason"] == "length"
        turn.model = answer["model"]
        turn.transcript_created = transcript.created
        turn.state = DONE
        turn.reason_class = ""
        turn.answered_at = timezone.now()
        turn.save()
        _record(
            "chat_turn",
            recording,
            actor=chat.asked_by,
            templates=templates_line,
            model=turn.model,
            usage=usage,
            started=started,
            outcome="ok",
        )
    except engine.Problem as problem:
        turn.state = FAILED
        turn.reason_class = (
            THOUGHT_AWAY if isinstance(problem, ThoughtItAway) else problem.reason
        )
        turn.save(update_fields=["state", "reason_class"])
        _record(
            "chat_turn",
            recording,
            actor=chat.asked_by,
            templates=templates_line,
            model="",
            usage=usage,
            started=started,
            outcome=problem.reason,
            reason=problem.reason,
        )


# Moments (Phase 4) --------------------------------------------------------------------
#
# What the camera showed at one time of a video Recording, on request. The
# clip is cut here, on llm-worker, which runs the app image with its ffmpeg:
# a few seconds from the Playback copy into a file of the container's own,
# read once into the request and deleted whatever happens. Nothing image-like
# ever touches the data directory, and the description is content: shown,
# exported, handed to Summary and Chat, and never logged.

# Two reasons of the Moment's own, beside the engine's table.
MEDIA_NOT_READY = "media_not_ready"
MEDIA_FAILED = "media_failed"
MOMENT_SAYS = {
    MEDIA_NOT_READY: "The video is still being prepared. Try again in a minute.",
    MEDIA_FAILED: "The clip could not be cut from the recording. Try again.",
}


# What one interval description takes the engine, about, so the summary
# dialog can say the minutes; a note, never a limit.
MOMENT_SECONDS_GUESS = 20


def moments_for_answers(transcript) -> list:
    """The Moments Summary and Chat are told about, or none.

    Only while Moments are on and the office hands them to answers; a Moment
    that failed or is still being described is not a description. Thinned to
    the camera block's budget when an office's numbers make it too big.
    """
    if not settings_store.get("moments_in_answers") or not features()["moments"]:
        return []
    return prompts.trim_camera_lines(
        list(transcript.moments.filter(state=DONE).exclude(text="")),
        prompts.CAMERA_BLOCK_TOKENS,
    )


def playable_video(recording) -> bool:
    """Whether the Playback copy exists and carries a picture."""
    playback = recording.playback_path()
    return bool(
        recording.playback_ready and playback is not None and playback.suffix == ".mp4"
    )


def has_picture(recording) -> bool:
    """Whether the Recording carries a picture: the Playback copy says so, or
    the probe does before the copy exists."""
    if playable_video(recording):
        return True
    from core import media

    try:
        return media.video_stream(getattr(recording, "probe", None) or {}) is not None
    except Exception:  # noqa: BLE001 - an odd probe is not a reason to fail the page
        return False


def moment_span(recording, at: float) -> tuple[float, float]:
    """The clip's span around a time: half the setting either side, inside the file."""
    half = ASKED_SPAN_SECONDS / 2
    length = float(recording.duration_seconds or 0.0)
    start = max(0.0, at - half)
    end = at + half
    if length > 0:
        end = min(length, end)
    return round(start, 3), round(max(end, start), 3)


def question_times(at: float, frames: int, length: float) -> list[float]:
    """The seconds a question's frames are taken at, spread a second either side."""
    frames = max(1, frames)
    if frames == 1:
        times = [at]
    else:
        step = 2.0 / (frames - 1)
        times = [at - 1.0 + step * n for n in range(frames)]
    times = [round(max(0.0, t), 3) for t in times]
    if length > 0:
        times = [min(t, round(length, 3)) for t in times]
    return times


def describe_moment(moment_id) -> None:
    """One Moment: a clip cut from the Playback copy, shown with its words.

    Or, when the Moment carries a question, a few still frames at the camera's
    own detail with the question, answered in a fixed shape.
    """
    import base64
    import os
    import shutil
    import tempfile
    from pathlib import Path

    from core import media

    moment = (
        Moment.objects.filter(pk=moment_id)
        .select_related("transcript", "transcript__recording")
        .first()
    )
    if moment is None:
        return
    transcript = moment.transcript
    recording = transcript.recording
    started = time.monotonic()
    ground = PromptTemplate.named(PromptTemplate.GROUND_RULES)
    template = PromptTemplate.named(PromptTemplate.MOMENT)
    templates_line = f"ground-rules v{ground.version}; Moment v{template.version}"
    moment.state = RUNNING
    moment.save(update_fields=["state"])

    usage: dict = {}
    clip = None
    stills = None
    try:
        problem = _unreachable()
        if problem:
            raise problem
        if not playable_video(recording):
            raise engine.Problem(MEDIA_NOT_READY, "no playback copy with a picture")
        record = (
            moment.source == Moment.INTERVAL and moment.span_end > moment.span_start
        )
        if record:
            # One span of the picture record: the span itself, never a clip
            # cut around a time (chapter 6).
            span_start, span_end = moment.span_start, moment.span_end
        else:
            span_start, span_end = moment_span(recording, moment.at)
        moment.span_start, moment.span_end = span_start, span_end
        lines = prompts.lines_of(transcript)
        spoken = prompts.lines_in_span(lines, span_start, span_end)
        answer_cap = settings_store.moments_answer_cap()

        if moment.is_question:
            # A question: a few frames at the camera's own detail, and the
            # question's fixed shape; the editable template still applies.
            height = QUESTION_HEIGHT
            times = question_times(
                moment.at,
                QUESTION_FRAMES,
                float(recording.duration_seconds or 0.0),
            )
            frames = len(times)
            system = prompts.system_message(
                ground.text,
                template.text + "\n\n" + prompts.QUESTION,
                prompts.QUESTION_FORMAT,
            )
            text = "\n\n".join(
                [
                    prompts.nature_line(recording, transcript),
                    prompts.question_input(
                        spoken, moment.at, span_start, span_end, moment.question
                    ),
                ]
            )
            extra = prompts.still_tokens(frames, height)
        else:
            fps = settings_store.moment_frames_per_second()
            if record:
                # A long still span costs no more than a short busy one.
                fps = record_fps(span_end - span_start, fps)
            height = settings_store.moment_frame_height()
            frames = max(1, round((span_end - span_start) * fps))
            style = (
                prompts.MOMENT_FORMAT_FULL
                if settings_store.moment_style() == "full"
                else prompts.MOMENT_FORMAT_BRIEF
            )
            previous = previous_description(moment) if record else ""
            if record:
                style = style + "\n" + prompts.RECORD_NEW
            system = prompts.system_message(ground.text, template.text, style)
            text = "\n\n".join(
                [
                    prompts.nature_line(recording, transcript),
                    prompts.moment_input(spoken, span_start, span_end, previous),
                ]
            )
            extra = prompts.video_tokens(frames, height)
        if not prompts.fits(
            system, text, answer_cap=answer_cap, window=window(), extra=extra
        ):
            raise engine.Problem(engine.TOO_LONG, "the clip would not fit")

        parts: list[dict] = [{"type": "text", "text": text}]
        if moment.is_question:
            stills = Path(tempfile.mkdtemp(prefix="moment-"))
            try:
                taken = media.grab_frames(
                    recording.playback_path(), stills, times, height=height
                )
            except media.MediaError as why:
                raise engine.Problem(MEDIA_FAILED, str(why)[:200]) from why
            for frame in taken:
                parts.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/jpeg;base64,"
                            + base64.b64encode(frame.read_bytes()).decode("ascii")
                        },
                    }
                )
            shutil.rmtree(stills, ignore_errors=True)
            stills = None
        else:
            handle, name = tempfile.mkstemp(suffix=".mp4", prefix="moment-")
            os.close(handle)
            clip = Path(name)
            try:
                media.cut_for_description(
                    recording.playback_path(),
                    clip,
                    span_start,
                    span_end,
                    fps=fps,
                    height=height,
                )
            except media.MediaError as why:
                raise engine.Problem(MEDIA_FAILED, str(why)[:200]) from why
            data_url = "data:video/mp4;base64," + base64.b64encode(
                clip.read_bytes()
            ).decode("ascii")
            clip.unlink(missing_ok=True)
            clip = None
            parts.append({"type": "video_url", "video_url": {"url": data_url}})

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": parts},
        ]
        # Never thinking: the frames are billed against the same budget, a
        # small model thinks at length over a picture, and a description is
        # perception, not deduction.
        answer = engine.complete(
            messages,
            max_completion_tokens=answer_cap,
            thinking=False,
            timeout=settings_store.time_limit_seconds("moment"),
            **SAMPLING,
        )
        usage = answer
        said = answer["text"].strip()
        if not said:
            raise engine.Problem(engine.BAD_OUTPUT, "an empty description")
        moment.text = said
        moment.model = answer["model"]
        moment.frames = frames
        moment.seconds = round(time.monotonic() - started, 1)
        moment.state = DONE
        moment.reason_class = ""
        moment.edited = False
        moment.described_at = timezone.now()
        moment.save()
        _record(
            "moment",
            recording,
            actor=moment.asked_by,
            templates=templates_line,
            model=moment.model,
            usage=usage,
            started=started,
            outcome="ok",
            source=moment.source,
            kind="question" if moment.is_question else "description",
        )
    except engine.Problem as problem:
        moment.state = FAILED
        moment.reason_class = problem.reason
        moment.save(update_fields=["state", "reason_class", "span_start", "span_end"])
        _record(
            "moment",
            recording,
            actor=moment.asked_by,
            templates=templates_line,
            model="",
            usage=usage,
            started=started,
            outcome=problem.reason,
            reason=problem.reason,
            source=moment.source,
            kind="question" if moment.is_question else "description",
        )
    finally:
        if clip is not None:
            clip.unlink(missing_ok=True)
        if stills is not None:
            shutil.rmtree(stills, ignore_errors=True)


def record_fps(length: float, fps: float, most: int | None = None) -> float:
    """The frames a second for a record span: the setting, thinned so a span never
    costs more than Picture record: frames per description."""
    if most is None:
        most = settings_store.picture_frames_most()
    most = max(1, int(most))
    if length <= 0:
        return float(fps)
    return round(min(float(fps), most / length), 3)


def previous_description(moment) -> str:
    """What the record's previous span showed, for the description to build on."""
    before = (
        moment.transcript.moments.filter(
            source=Moment.INTERVAL, state=DONE, at__lt=moment.at
        )
        .exclude(text="")
        .order_by("-at")
        .first()
    )
    return before.text if before is not None else ""


def _cut_spans(
    length: float, points: list[float], longest: float, shortest: float
) -> list[tuple[float, float]]:
    edges = (
        [0.0]
        + sorted({round(p, 2) for p in points if 0 < p < length})
        + [round(length, 2)]
    )
    spans: list[tuple[float, float]] = []
    for a, b in zip(edges, edges[1:], strict=False):
        if spans and (b - a) < shortest:
            spans[-1] = (spans[-1][0], b)
        else:
            spans.append((a, b))
    if len(spans) > 1 and (spans[0][1] - spans[0][0]) < shortest:
        first = spans.pop(0)
        spans[0] = (first[0], spans[0][1])
    cut: list[tuple[float, float]] = []
    for a, b in spans:
        pieces = max(1, math.ceil((b - a) / longest))
        step = (b - a) / pieces
        for n in range(pieces):
            end = b if n == pieces - 1 else round(a + (n + 1) * step, 2)
            cut.append((round(a + n * step, 2), end))
    return cut


def record_spans(
    length: float,
    points: list[float],
    longest: float,
    shortest: float,
    most: int,
    taken: list[tuple[float, float]] | None = None,
) -> list[tuple[float, float]]:
    """The spans of the picture record (chapter 6).

    The recording cut at the change points; a span longer than `longest` cut
    into equal pieces no longer than that; a span shorter than `shortest`
    joined to its neighbour. The spans touch, never overlap, and cover the
    recording; when more than `most`, the cut is made coarser until they fit.
    A span already covered by a Moment (`taken`, as (start, end) pairs) is
    left out: nothing is described twice.
    """
    if length <= 0 or longest <= 0:
        return []
    ceiling = float(longest)
    cut = _cut_spans(length, points, ceiling, shortest)
    while len(cut) > most and ceiling < length:
        ceiling *= 2
        cut = _cut_spans(length, points if ceiling < length else [], ceiling, shortest)
    if len(cut) > most:
        cut = cut[:most]
    taken = taken or []

    def covered(a: float, b: float) -> bool:
        return any(s <= a + 0.5 and e >= b - 0.5 for s, e in taken)

    return [(a, b) for a, b in cut if not covered(a, b)]


def taken_spans(transcript) -> list[tuple[float, float]]:
    """The spans of the Moments that stand: described, or being described."""
    return [
        (one.span_start, one.span_end)
        for one in transcript.moments.exclude(state=FAILED)
        if one.span_end > one.span_start
        and (one.text or one.state in (QUEUED, RUNNING))
    ]


def planned_spans(recording, transcript) -> tuple[list[tuple[float, float]], bool]:
    """What Describe the whole recording would make now, and whether that is an
    estimate (the picture not yet scanned, so the cut is by the clock alone)."""
    points = transcript.change_points
    spans = record_spans(
        float(recording.duration_seconds or 0.0),
        points or [],
        settings_store.moment_interval_seconds(),
        settings_store.picture_shortest_span(),
        settings_store.moment_interval_most(),
        taken_spans(transcript),
    )
    return spans, points is None


def describe_intervals(run_id) -> None:
    """The picture record: one Moment per span, one after another (chapter 6).

    In one lane, so a long recording never takes the assistant's four lanes
    from everyone else. Each span is described with the previous span's
    description in hand, so it says what is new. Stops when the engine goes
    away; a single failed Moment is left failed and the rest go on.
    """
    run = (
        CueRun.objects.filter(pk=run_id)
        .select_related("transcript", "transcript__recording")
        .first()
    )
    if run is None:
        return
    transcript = run.transcript
    recording = transcript.recording
    run.state = RUNNING
    run.save(update_fields=["state"])
    if not playable_video(recording):
        run.state = FAILED
        run.reason_class = MEDIA_NOT_READY
        run.finished_at = timezone.now()
        run.save(update_fields=["state", "reason_class", "finished_at"])
        return
    # The change points first, once per Transcript: the scan of the picture
    # and sound the record is cut by (chapter 6).
    if transcript.change_points is None:
        from core import media, moment_scan

        try:
            moment_scan.change_points_of(transcript, actor=run.asked_by)
        except media.MediaError as why:
            run.state = FAILED
            run.reason_class = why.reason_class
            run.finished_at = timezone.now()
            run.save(update_fields=["state", "reason_class", "finished_at"])
            return
        transcript.refresh_from_db(fields=["change_points"])
    if recording.stamp is None and stamp_on():
        read_stamp(recording, asked_by=run.asked_by)
    spans, _ = planned_spans(recording, transcript)
    moments = [
        Moment.objects.create(
            transcript=transcript,
            at=start,
            span_start=start,
            span_end=end,
            source=Moment.INTERVAL,
            asked_by=run.asked_by,
        )
        for start, end in spans
    ]
    run.total = len(moments)
    run.save(update_fields=["total"])
    reason = ""
    for moment in moments:
        if reason:
            moment.state = FAILED
            moment.reason_class = reason
            moment.save(update_fields=["state", "reason_class"])
            continue
        describe_moment(moment.pk)
        moment.refresh_from_db()
        if moment.state == DONE:
            run.found += 1
            run.save(update_fields=["found"])
        elif moment.reason_class == engine.UNREACHABLE:
            reason = engine.UNREACHABLE
        _prepare_tick(transcript)
    run.state = FAILED if reason else DONE
    run.reason_class = reason
    run.finished_at = timezone.now()
    run.save()


# The camera's stamp (Phase 4, chapter 6) --------------------------------------------
#
# Many body-worn cameras burn a date, a clock time and the camera's id into
# the picture. Read once per Transcript from a frame near the start, at the
# look-closer height, and checked against a second frame a minute on: the
# clock must have moved on by the same minute. Kept on the Transcript; told to
# the Summary, the Chat and the Digest as the camera's clock. Never blocks the
# record: a stamp that cannot be read is an empty one.

STAMP_AT = 2.0
STAMP_CHECK_AFTER = 60.0
STAMP_TOLERANCE = 3


def _read_stamp_frame(recording, transcript, at: float) -> tuple[dict, dict]:
    """One frame's stamp as the engine read it, and the call's usage."""
    import base64
    import shutil
    import tempfile
    from pathlib import Path

    from core import media

    ground = PromptTemplate.named(PromptTemplate.GROUND_RULES)
    height = STAMP_HEIGHT
    system = prompts.system_message(ground.text, prompts.STAMP, prompts.STAMP_FORMAT)
    text = "\n\n".join(
        [
            _stamp_nature(recording, transcript),
            f"The frame is from {prompts.clock(at)} of the recording.",
        ]
    )
    folder = Path(tempfile.mkdtemp(prefix="stamp-"))
    try:
        taken = media.grab_frames(
            recording.playback_path(), folder, [at], height=height
        )
        parts: list[dict] = [{"type": "text", "text": text}]
        for frame in taken:
            parts.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/jpeg;base64,"
                        + base64.b64encode(frame.read_bytes()).decode("ascii")
                    },
                }
            )
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    answer = engine.complete(
        [{"role": "system", "content": system}, {"role": "user", "content": parts}],
        max_completion_tokens=prompts.STAMP_CAP,
        thinking=False,
        timeout=settings_store.time_limit_seconds("moment"),
        schema=prompts.STAMP_SCHEMA,
        **SUGGESTION_SAMPLING,
    )
    try:
        parsed = json.loads(answer["text"])
    except ValueError:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    read = {
        key: " ".join(str(parsed.get(key, "") or "").split())[:200]
        for key in ("date", "time", "camera", "other")
    }
    return read, answer


def _stamp_nature(recording, transcript) -> str:
    """What the frame is from: the nature line when the transcript exists, else
    the recording's length alone, since the stamp may be read before it."""
    from core import exports

    if transcript is not None:
        return prompts.nature_line(recording, transcript)
    return f"This is a frame from a {exports.length_of(recording)} video recording."


def read_stamp(recording, *, asked_by) -> dict:
    """The stamp read and checked, kept on the Recording; empty when none.

    Read as the playback copy lands (Phase 6 chapter 1) or when the picture
    record is first made, whichever comes first; never twice.
    """
    from core import media

    transcript = getattr(recording, "transcript", None)
    started = time.monotonic()
    length = float(recording.duration_seconds or 0.0)
    at = min(STAMP_AT, length) if length > 0 else STAMP_AT
    usage: dict = {}
    stamp: dict = {}
    try:
        first, usage = _read_stamp_frame(recording, transcript, at)
        stamp = {**first, "at": at, "checked": False}
        seconds = prompts.clock_seconds(first.get("time", ""))
        later = at + STAMP_CHECK_AFTER
        if seconds is not None and length > later + 5:
            second, more = _read_stamp_frame(recording, transcript, later)
            usage = {
                "input_tokens": (usage.get("input_tokens") or 0)
                + (more.get("input_tokens") or 0),
                "output_tokens": (usage.get("output_tokens") or 0)
                + (more.get("output_tokens") or 0),
                "model": usage.get("model", ""),
            }
            then = prompts.clock_seconds(second.get("time", ""))
            if (
                then is not None
                and abs(((then - seconds) % 86400) - STAMP_CHECK_AFTER)
                <= STAMP_TOLERANCE
            ):
                stamp["checked"] = True
            elif then is not None:
                # The clock did not move as the recording did: not a clock.
                stamp["time"] = ""
        if not any(stamp.get(key) for key in ("date", "time", "camera")):
            stamp = {}
        outcome = "ok"
        reason = ""
    except (engine.Problem, media.MediaError) as why:
        log.warning("the stamp could not be read: %s", getattr(why, "reason", why))
        stamp = {}
        outcome = getattr(why, "reason", getattr(why, "reason_class", "media_failed"))
        reason = outcome
    recording.stamp = stamp
    recording.save(update_fields=["stamp"])
    _record(
        "stamp",
        recording,
        actor=asked_by,
        templates="ground-rules; Stamp (fixed)",
        model=usage.get("model", "") if isinstance(usage, dict) else "",
        usage=usage if isinstance(usage, dict) else {},
        started=started,
        outcome=outcome,
        reason=reason,
        found=bool(stamp),
        checked=bool(stamp.get("checked")),
    )
    return stamp


# Prepared videos (Phase 4, chapter 7) --------------------------------------------
#
# A video is prepared once its picture record is complete and its Digest is
# current. It happens by itself as the transcript lands (the task below,
# waiting for the Playback copy), on first use (a summary or a chat question
# prepares first, the card saying so), or on purpose from the case page.
# Nobody presses anything on the recording page. The count and the time left
# are kept on the Transcript, and the estimate comes from what descriptions
# and parts have taken on this engine rather than a guess.

PREPARING = "running"
# What the withdrawn features' settings were (the diary's chapters 1 and 2),
# kept as constants for the code paths that still read them: an asked
# moment's span, a question's frames, and the height the stamp is read at.
ASKED_SPAN_SECONDS = 10
QUESTION_HEIGHT = 720
QUESTION_FRAMES = 3
STAMP_HEIGHT = 720
DIGEST_SECONDS_GUESS = 30
PREPARE_WAIT_SECONDS = 3 * 3600
PLAYBACK_RETRY_SECONDS = 60
# How long the task waits before looking again at a transcript it found not
# yet marked queued on its first go (v1.54.1).
QUEUE_GRACE_SECONDS = 5
PLAYBACK_RETRIES = 120


def seconds_per_description() -> float:
    """What one span's description takes on this engine, from the last fifty."""
    recent = list(
        Moment.objects.filter(source=Moment.INTERVAL, state=DONE, seconds__gt=0)
        .order_by("-described_at")
        .values_list("seconds", flat=True)[:50]
    )
    return sum(recent) / len(recent) if recent else float(MOMENT_SECONDS_GUESS)


def seconds_per_part() -> float:
    recent = list(
        DigestPart.objects.filter(seconds__gt=0)
        .order_by("-made_at")
        .values_list("seconds", flat=True)[:50]
    )
    return sum(recent) / len(recent) if recent else float(DIGEST_SECONDS_GUESS)


def prepared(transcript) -> bool:
    """Whether the record is complete and the Digest current, as the last
    preparation left them; a change since (a Process again makes a new
    Transcript anyway) is caught by the Digest's signatures."""
    if transcript.prepare_state != DONE:
        return False
    return not (digests_on() and not digest_current(transcript))


def prepare_plan(recording, transcript) -> dict:
    """What preparing this video would do now, in numbers: the spans left, the
    parts stale, and about how long, from this engine's own pace."""
    spans, estimated = (
        planned_spans(recording, transcript) if record_on() else ([], False)
    )
    parts = 0
    # A Digest is made only once there are descriptions to condense.
    will_have = bool(spans) or bool(moments_for_answers(transcript))
    if digests_on() and will_have:
        have = {one.signature for one in transcript.digest_parts.all() if one.text}
        for window_plan in digest_plan(transcript):
            if window_plan["signature"] not in have:
                parts += 1
    seconds = len(spans) * seconds_per_description() + parts * seconds_per_part()
    return {
        "descriptions": len(spans),
        "estimated": estimated,
        "parts": parts,
        "seconds": int(round(seconds)),
    }


def _prepare_tick(transcript) -> None:
    """One more thing done, for the count the pages show while it runs."""
    if transcript.prepare_state != PREPARING:
        return
    transcript.prepare_done = models.F("prepare_done") + 1
    transcript.save(update_fields=["prepare_done"])
    transcript.refresh_from_db(fields=["prepare_done"])


def prepare(transcript, *, asked_by=None) -> bool:
    """The record, the stamp and the Digest, in this lane, with the count kept.

    Returns whether the video ended up prepared. Never raises: a preparation
    that fails is a state the pages say, and the Batch's mail is told either
    way.
    """
    from core import mail, media, moment_scan

    recording = transcript.recording
    started = time.monotonic()
    # A preparation taken up again (after a worker stopped part-way, or pressed
    # again after a failure) keeps the descriptions that stand and starts the
    # rest afresh: a span left queued, running or failed by the last attempt
    # would otherwise count as taken and never be described.
    transcript.moments.filter(source=Moment.INTERVAL).exclude(state=DONE).delete()
    plan = prepare_plan(recording, transcript)
    transcript.prepare_state = PREPARING
    transcript.prepare_reason = ""
    transcript.prepare_done = 0
    transcript.prepare_total = plan["descriptions"] + plan["parts"]
    transcript.prepare_started = timezone.now()
    transcript.save(
        update_fields=[
            "prepare_state",
            "prepare_reason",
            "prepare_done",
            "prepare_total",
            "prepare_started",
        ]
    )
    reason = ""
    try:
        if not playable_video(recording):
            raise engine.Problem(MEDIA_NOT_READY, "no playback copy with a picture")
        problem = _unreachable()
        if problem:
            raise problem
        if transcript.change_points is None:
            try:
                moment_scan.change_points_of(transcript, actor=asked_by)
            except media.MediaError as why:
                raise engine.Problem(why.reason_class, str(why)) from why
            transcript.refresh_from_db(fields=["change_points"])
            # The cut is known now, so the count the pages show is the cut's.
            plan = prepare_plan(recording, transcript)
            transcript.prepare_total = plan["descriptions"] + plan["parts"]
            transcript.save(update_fields=["prepare_total"])
        if recording.stamp is None and stamp_on():
            read_stamp(recording, asked_by=asked_by)
        if record_on():
            run = CueRun.objects.create(
                transcript=transcript, source=CueRun.INTERVAL, asked_by=asked_by
            )
            describe_intervals(run.pk)
            run.refresh_from_db()
            if run.reason_class == engine.UNREACHABLE:
                raise engine.Problem(engine.UNREACHABLE, "the engine went away")
        if digests_on() and moments_for_answers(transcript):
            make_digest(
                transcript,
                asked_by=asked_by,
                progress=lambda: _prepare_tick(transcript),
            )
        transcript.prepare_state = DONE
        transcript.prepared_at = timezone.now()
    except engine.Problem as problem:
        reason = problem.reason
        transcript.prepare_state = FAILED
        transcript.prepare_reason = reason
        # The engine gone during the night: the video waits for the next
        # window rather than failing (chapter 5).
        from core import vision

        if reason == engine.UNREACHABLE and vision.scheduled():
            transcript.prepare_state = vision.TONIGHT
            transcript.prepare_reason = vision.NOT_REACHED
    transcript.save(update_fields=["prepare_state", "prepare_reason", "prepared_at"])
    audit.write(
        audit.Category.RECORDINGS,
        "Video enriched",
        actor=asked_by,
        outcome=audit.Outcome.SUCCESS if not reason else audit.Outcome.FAILURE,
        reason_class=reason,
        affected_user=(
            recording.user
            if asked_by is not None and recording.user_id != asked_by.pk
            else None
        ),
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
        descriptions=transcript.moments.filter(
            source=Moment.INTERVAL, state=DONE
        ).count(),
        parts=transcript.digest_parts.count(),
        duration_seconds=round(time.monotonic() - started, 1),
    )
    # The Batch's mail waits for its videos to be prepared; under a schedule
    # the second message and the requests are told (chapter 5).
    mail.note_batch_progress(recording)
    from core import vision

    vision.note_progress(recording)
    return not reason


def wait_or_prepare(transcript, *, asked_by=None, still_wanted=None) -> bool:
    """Prepared by the transcript's own task if it is at it, else here and now.
    `still_wanted` says whether the caller's summary or question still exists;
    the wait ends early when it does not."""
    transcript.refresh_from_db(fields=["prepare_state"])
    if transcript.prepare_state in (QUEUED, PREPARING):
        waited = 0
        while waited < PREPARE_WAIT_SECONDS:
            time.sleep(5)
            waited += 5
            if still_wanted is not None and not still_wanted():
                return False
            transcript.refresh_from_db(fields=["prepare_state"])
            if transcript.prepare_state not in (QUEUED, PREPARING):
                return transcript.prepare_state == DONE
        raise engine.Problem(engine.TIMEOUT, "the preparation is taking too long")
    return prepare(transcript, asked_by=asked_by)


def queue_preparation(recording) -> bool:
    """A video's transcript has landed: its preparation is queued behind the
    Playback copy. Nothing for sound alone, or while the record is off."""
    transcript = getattr(recording, "transcript", None)
    if transcript is None or not record_on() or not has_picture(recording):
        return False
    from core import tasks

    transcript.prepare_state = QUEUED
    transcript.prepare_reason = ""
    transcript.prepare_done = 0
    transcript.prepare_total = 0
    transcript.save(
        update_fields=[
            "prepare_state",
            "prepare_reason",
            "prepare_done",
            "prepare_total",
        ]
    )
    tasks.prepare_video.defer(transcript_id=str(transcript.pk))
    return True


def prepare_words(transcript) -> tuple[str, str]:
    """What a page says about a video's vision, and the pill's tone: the one
    family of words chapter 5 fixes (Enriched with vision, Enriching now,
    Enriching tonight, Not yet enriched with vision)."""
    from core import vision

    return vision.words(transcript)


def seconds_left(transcript) -> int:
    """About how long a preparation has to go, from the engine's own pace."""
    if transcript.prepare_state == QUEUED or not transcript.prepare_total:
        return prepare_plan(transcript.recording, transcript)["seconds"]
    left = max(0, transcript.prepare_total - transcript.prepare_done)
    return int(round(left * seconds_per_description()))


def about(seconds: int) -> str:
    """ "about 18 minutes", "about 2 h 10 min", "under a minute"."""
    if seconds < 60:
        return "under a minute"
    minutes = int(round(seconds / 60))
    if minutes < 60:
        return f"about {minutes} minute{'' if minutes == 1 else 's'}"
    hours, rest = divmod(minutes, 60)
    return f"about {hours} h {rest:02d} min" if rest else f"about {hours} h"


def prepare_json(transcript) -> dict | None:
    """The preparation as the pages read it, or nothing for sound alone."""
    if transcript is None or not (record_on() and has_picture(transcript.recording)):
        return None
    words, tone = prepare_words(transcript)
    left = seconds_left(transcript) if transcript.prepare_state != DONE else 0
    from core import vision

    return {
        "state": transcript.prepare_state or "none",
        "done": transcript.prepare_done,
        "total": transcript.prepare_total,
        "seconds_left": left,
        "line": words,
        "tone": tone,
        "scheduled": vision.scheduled(),
        # The night's hours, for the summary form's line (v1.54.2).
        "window": vision.window_words(),
    }


# The Digest (Phase 4, chapter 6) -------------------------------------------------
#
# One text per Transcript, made in the summary's lane after the record: the
# Transcript in windows, each with the camera lines in it, condensed by one
# call each into a time-ordered record where every line says said, seen or
# both. Kept part by part with what each was made from, so the next summary
# remakes only the parts whose words or descriptions changed. Nobody reads it.


def digest_windows(
    lines: list, budget: int, forced: set[str] | None = None
) -> list[tuple[int, int]]:
    """The windows of the Transcript, cut on line boundaries, each within the
    budget, and cut before any line in `forced` (the splits a cut-off part
    made) whatever the budget says."""
    windows: list[tuple[int, int]] = []
    forced = forced or set()
    start = 0
    used = 0
    for index, line in enumerate(lines):
        cost = prompts.tokens(prompts.render([line])) + 1
        split_here = str(line.segment_id) in forced
        if index > start and (split_here or used + cost > budget):
            windows.append((start, index))
            start, used = index, 0
        used += cost
    if start < len(lines) or not windows:
        windows.append((start, len(lines)))
    return windows


def digest_signature(lines: list, moments: list) -> str:
    """What a part was made from, hashed: its lines and the descriptions in them."""
    digest = hashlib.sha256()
    for line in lines:
        digest.update(
            f"{line.segment_id}|{line.start}|{line.speaker}|{line.text}\n".encode()
        )
    for one in moments:
        digest.update(
            f"{one.pk}|{one.span_start}|{one.span_end}|{one.text}|{one.edited}\n".encode()
        )
    return digest.hexdigest()


def _moments_in(moments: list, start: float, end: float) -> list:
    """The described Moments whose spans fall in the window."""
    found = []
    for one in moments:
        a, b = prompts.span_of(one)
        if b >= start and a < end:
            found.append(one)
    return found


def digest_plan(transcript) -> list[dict]:
    """Each window with its span, its lines, its Moments and its signature."""
    recording = transcript.recording
    lines = prompts.lines_of(transcript)
    if not lines:
        return []
    moments = list(transcript.moments.filter(state=DONE).exclude(text=""))
    windows = digest_windows(
        lines,
        settings_store.digest_window_tokens(),
        set(transcript.digest_splits or []),
    )
    length = float(recording.duration_seconds or 0.0) or (lines[-1].start + 1.0)
    plan = []
    for number, (first, last) in enumerate(windows, start=1):
        start = 0.0 if number == 1 else lines[first].start
        end = lines[windows[number][0]].start if number < len(windows) else length
        mine = _moments_in(moments, start, end)
        plan.append(
            {
                "number": number,
                "total": len(windows),
                "start": start,
                "end": end,
                "lines": lines[first:last],
                "moments": mine,
                "signature": digest_signature(lines[first:last], mine),
            }
        )
    return plan


def digest_current(transcript) -> bool:
    """Whether every part stands for what the Transcript and the record hold now."""
    parts = list(transcript.digest_parts.all())
    plan = digest_plan(transcript)
    if not plan or len(parts) != len(plan):
        return False
    have = {one.signature for one in parts if one.text}
    return all(one["signature"] in have for one in plan)


def digest_text(transcript) -> str:
    """The Digest as it stands, part after part, or nothing."""
    return "\n".join(
        one.text for one in transcript.digest_parts.all() if one.text
    ).strip()


def digest_made_at(transcript):
    """When the Digest was last made: the newest part's time."""
    newest = transcript.digest_parts.exclude(made_at=None).order_by("-made_at").first()
    return newest.made_at if newest is not None else None


def make_digest(transcript, *, asked_by, summary=None, progress=None) -> str:
    """The Digest brought current: only the stale parts are made again.

    Called in the summary's lane, after the record. Raises the engine's
    Problem, which fails the Summary the ordinary way.
    """
    recording = transcript.recording
    ground = PromptTemplate.named(PromptTemplate.GROUND_RULES)
    template = PromptTemplate.named(PromptTemplate.DIGEST)
    templates_line = f"ground-rules v{ground.version}; Digest v{template.version}"
    # A part that comes back cut off at the cap means the window held more
    # than the cap could condense: the window is split in two at its middle
    # line, the split kept on the Transcript, and the plan started over. The
    # parts already made keep their signatures and are not made again; a
    # one-line window cannot split and its part is kept, marked cut.
    while True:
        plan = digest_plan(transcript)
        if not plan:
            return ""
        texts, split = _make_digest_parts(
            transcript,
            recording,
            plan,
            ground,
            template,
            templates_line,
            asked_by=asked_by,
            summary=summary,
            progress=progress,
        )
        if not split:
            break
    transcript.digest_parts.exclude(
        signature__in=[one["signature"] for one in plan]
    ).delete()
    return "\n".join(texts).strip()


def _split_windows(transcript, plan, number) -> int:
    """The window whose part came back cut off is split at its middle line,
    and so is every later window no part has been made for yet: they were cut
    to the same budget from the same kind of talk, and one call each to learn
    the same thing would be the v1.53.0 waste (ten calls thrown away on one
    video). Returns how many windows were split, so the count the pages show
    can grow by as many."""
    made = {one.signature for one in transcript.digest_parts.all() if one.text}
    splits = list(transcript.digest_splits or [])
    added = 0
    for window_plan in plan:
        if window_plan["number"] < number:
            continue
        if window_plan["number"] > number and window_plan["signature"] in made:
            continue
        lines = window_plan["lines"]
        if len(lines) < 2:
            continue
        # A later window keeps its start as a cut too, or the budget would
        # pack the lines afresh across the old boundaries and move them.
        if window_plan["number"] > number:
            first = str(lines[0].segment_id)
            if first not in splits:
                splits.append(first)
        middle = str(lines[len(lines) // 2].segment_id)
        if middle not in splits:
            splits.append(middle)
            added += 1
    transcript.digest_splits = splits
    transcript.save(update_fields=["digest_splits"])
    _prepare_grow(transcript, added)
    return added


def _prepare_grow(transcript, more: int) -> None:
    """More parts to make than the plan counted: the total the pages show
    grows with them, so the count never reads 5 of 4."""
    if more <= 0 or transcript.prepare_state != PREPARING:
        return
    transcript.prepare_total = models.F("prepare_total") + more
    transcript.save(update_fields=["prepare_total"])
    transcript.refresh_from_db(fields=["prepare_total"])


def _make_digest_parts(
    transcript,
    recording,
    plan,
    ground,
    template,
    templates_line,
    *,
    asked_by,
    summary,
    progress,
) -> tuple[list[str], bool]:
    """One pass over the plan: the stale parts made, in order. Returns the
    texts and whether a window was split, in which case the pass stopped
    there and the caller plans again."""
    existing = {one.signature: one for one in transcript.digest_parts.all()}
    texts = []
    for window_plan in plan:
        number = window_plan["number"]
        part = existing.get(window_plan["signature"])
        if part is not None and part.text:
            if part.number != number:
                part.number = number
                part.save(update_fields=["number"])
            texts.append(part.text)
            continue
        if summary is not None:
            summary.stage = f"condensing {number} of {window_plan['total']}"
            summary.save(update_fields=["stage"])
        started = time.monotonic()
        usage: dict = {}
        mine = window_plan["moments"]
        answer_cap = cap(settings_store.digest_part_cap())
        system = prompts.system_message(
            ground.text,
            template.text,
            prompts.with_camera_rules(prompts.DIGEST_FORMAT, mine),
        )
        user = "\n\n".join(
            part
            for part in [
                prompts.nature_line(recording, transcript),
                clock_line(transcript),
                prompts.digest_input(
                    number,
                    window_plan["total"],
                    window_plan["start"],
                    window_plan["end"],
                    prompts.render(window_plan["lines"]),
                    prompts.camera_lines(mine),
                ),
            ]
            if part
        )
        try:
            if not prompts.fits(system, user, answer_cap=answer_cap, window=window()):
                raise engine.Problem(engine.TOO_LONG, "a digest window would not fit")
            answer = engine.complete(
                _messages(system, user),
                max_completion_tokens=answer_cap,
                thinking=False,
                timeout=time_limit("summary"),
                **SAMPLING,
            )
            usage = answer
            text = answer["text"].strip()
            if not text:
                raise engine.Problem(engine.BAD_OUTPUT, "an empty digest part")
        except engine.Problem as problem:
            _record(
                "digest",
                recording,
                actor=asked_by,
                templates=templates_line,
                model="",
                usage=usage,
                started=started,
                outcome=problem.reason,
                reason=problem.reason,
                part=number,
                parts=window_plan["total"],
            )
            raise
        cut = answer["finish_reason"] == "length"
        if cut and len(window_plan["lines"]) > 1:
            _record(
                "digest",
                recording,
                actor=asked_by,
                templates=templates_line,
                model=answer["model"],
                usage=usage,
                started=started,
                outcome="ok",
                part=number,
                parts=window_plan["total"],
                cut=True,
                split=True,
            )
            _split_windows(transcript, plan, number)
            return texts, True
        if part is None:
            part = DigestPart(transcript=transcript, number=number)
        part.number = number
        part.span_start = window_plan["start"]
        part.span_end = window_plan["end"]
        part.signature = window_plan["signature"]
        part.text = text
        part.cut_short = cut
        part.moments_used = len(mine)
        part.model = answer["model"]
        part.made_at = timezone.now()
        part.seconds = round(time.monotonic() - started, 1)
        part.save()
        _record(
            "digest",
            recording,
            actor=asked_by,
            templates=templates_line,
            model=part.model,
            usage=usage,
            started=started,
            outcome="ok",
            part=number,
            parts=window_plan["total"],
            cut=cut,
        )
        texts.append(text)
        if progress is not None:
            progress()
    return texts, False


def unnamed_speakers(transcript) -> list[str]:
    """Speakers still wearing the app's own label, Speaker n or Side n Speaker n."""
    names = (
        transcript.segments.filter(same_as_other_side=False)
        .exclude(speaker="")
        .order_by("speaker")
        .values_list("speaker", flat=True)
        .distinct()
    )
    return [name for name in names if _is_a_label(name)]


def _is_a_label(name: str) -> bool:
    parts = name.split()
    return bool(parts) and parts[0] in ("Speaker", "Side") and parts[-1].isdigit()


def suggest_names(run_id) -> None:
    """One call for the whole Transcript, replacing every pending suggestion."""
    run = (
        SuggestionRun.objects.filter(pk=run_id)
        .select_related("transcript", "transcript__recording")
        .first()
    )
    if run is None:
        return
    transcript = run.transcript
    recording = transcript.recording
    started = time.monotonic()
    ground = PromptTemplate.named(PromptTemplate.GROUND_RULES)
    template = PromptTemplate.named(PromptTemplate.SUGGESTIONS)
    templates_line = (
        f"ground-rules v{ground.version}; Speaker suggestions v{template.version}"
    )
    run.state = RUNNING
    run.save(update_fields=["state"])

    usage: dict = {}
    try:
        problem = _unreachable()
        if problem:
            raise problem
        lines = prompts.lines_of(transcript)
        unnamed = unnamed_speakers(transcript)
        if len(unnamed) < 2:
            raise engine.Problem(engine.ERROR, "fewer than two unnamed speakers")
        all_names = set(
            transcript.segments.exclude(speaker="")
            .values_list("speaker", flat=True)
            .distinct()
        )
        taken = {name for name in all_names if not _is_a_label(name)}
        # Inside a Case the People come first, then the Vocabularies; the roles
        # are the Admin's list; the evidence is what the app found itself.
        from core import people

        known = people.known_names(recording)
        found = prompts.evidence(lines)
        system = prompts.system_message(
            ground.text, template.text, prompts.SUGGESTIONS_FORMAT
        )
        user = "\n\n".join(
            [
                prompts.nature_line(recording, transcript),
                prompts.render(lines),
                prompts.suggestions_input(unnamed, known),
                prompts.roles_line(people.roles()),
                prompts.evidence_lines(found),
            ]
        )
        suggestions_cap = settings_store.suggestions_answer_cap()
        if not prompts.fits(
            system, user, answer_cap=cap(suggestions_cap), window=window()
        ):
            raise engine.Problem(engine.TOO_LONG, "the transcript is too long")

        raw = None
        for attempt in (1, 2):
            answer = engine.complete(
                _messages(system, user),
                max_completion_tokens=cap(suggestions_cap),
                thinking=thinking(),
                timeout=time_limit("speaker_suggestions"),
                schema=prompts.suggestions_schema(unnamed),
                **SUGGESTION_SAMPLING,
            )
            usage = answer
            try:
                try:
                    parsed = json.loads(answer["text"])
                except ValueError:
                    # Cut off at the cap: keep the entries that were finished.
                    parsed = json.loads(prompts.salvage_json(answer["text"]))
                raw = parsed.get("suggestions", [])
                if not isinstance(raw, list):
                    raise ValueError("not a list")
                break
            except (ValueError, AttributeError) as bad:
                if attempt == 2:
                    raise engine.Problem(
                        engine.BAD_OUTPUT, "invalid suggestion JSON twice"
                    ) from bad
        kept = prompts.keep_suggestions(raw or [], unnamed, taken, lines, found)

        transcript.suggestions.filter(state=Suggestion.PENDING).delete()
        for one in kept:
            Suggestion.objects.create(
                transcript=transcript,
                speaker=one["speaker"],
                name=one["name"],
                kind=one["kind"],
                confidence=one["confidence"],
                line=one["line"],
                segment_id=one["segment_id"],
                start=one["start"],
                quote=one["quote"],
            )
        run.found = len(kept)
        run.state = DONE
        run.reason_class = ""
        run.finished_at = timezone.now()
        run.save()
        _record(
            "speaker_suggestions",
            recording,
            actor=run.asked_by,
            templates=templates_line,
            model=answer["model"],
            usage=usage,
            started=started,
            outcome="ok",
        )
    except engine.Problem as problem:
        run.state = FAILED
        run.reason_class = problem.reason
        run.finished_at = timezone.now()
        run.save(update_fields=["state", "reason_class", "finished_at"])
        _record(
            "speaker_suggestions",
            recording,
            actor=run.asked_by,
            templates=templates_line,
            model="",
            usage=usage,
            started=started,
            outcome=problem.reason,
            reason=problem.reason,
        )


def what_to_say(reason: str) -> str:
    """The person's line for a failed call, from the engine's own table."""
    if reason == THOUGHT_AWAY:
        return THOUGHT_IT_AWAY
    if reason in MOMENT_SAYS:
        return MOMENT_SAYS[reason]
    return engine.WHAT_TO_SAY.get(reason, engine.WHAT_TO_SAY.get(engine.ERROR, ""))
