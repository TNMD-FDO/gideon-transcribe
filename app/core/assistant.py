"""The AI assistant: Summary, Chat, and Speaker suggestions.

Three features, each run only when a user asks from the viewer, each working
from one Transcript and nothing else, each arriving whole. The calls run on
llm-worker, the one container on the engine's network; the pages poll. What
is stored lives as long as the Recording does: for the Login session in a
Workspace, and with the Case in a Case. Nothing typed, asked, or answered is
ever logged; the audit row is metadata only.
"""

from __future__ import annotations

import json
import logging
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
    FINDER = "finder"
    DEFAULTS = {
        GROUND_RULES: ("Ground rules", prompts.GROUND_RULES),
        CHAT: ("Chat", prompts.CHAT),
        SUGGESTIONS: ("Speaker suggestions", prompts.SUGGESTIONS),
        CASE_CHAT: ("Case chat", prompts.CASE_CHAT),
        MOMENT: ("Moment", prompts.MOMENT),
        FINDER: ("Find moments", prompts.FINDER),
    }

    key = models.CharField(max_length=30, unique=True)
    text = models.TextField()
    version = models.IntegerField(default=1)
    updated = models.DateTimeField(auto_now=True)

    @property
    def name(self) -> str:
        return self.DEFAULTS[self.key][0]

    @property
    def default_text(self) -> str:
        return self.DEFAULTS[self.key][1]

    @classmethod
    def named(cls, key: str) -> PromptTemplate:
        """The template, made from the chapter's wording when first asked for."""
        row, _ = cls.objects.get_or_create(
            key=key, defaults={"text": cls.DEFAULTS[key][1], "version": 1}
        )
        return row

    def save_text(self, text: str) -> None:
        """Save raises the version by one; the text is never logged."""
        self.text = text
        self.version += 1
        self.save(update_fields=["text", "version", "updated"])

    def reset(self) -> None:
        self.save_text(self.default_text)


# The templates the app ships: the Standard summary and one per shipped
# Recording type, each with the types it is for. Built in: editable and
# resettable on the Templates page, never deleted, and made once the first
# time they are wanted, so an office that upgrades gets them too.
SHIPPED_TEMPLATES = (
    (
        "standard",
        "Standard summary",
        "Overview, key points, notable statements, names and dates, unclear parts.",
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
        "Timeline of the encounter, commands and rights, what the person stopped says.",
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
        """Make any shipped template that is not there yet."""
        have = set(cls.objects.filter(built_in=True).values_list("key", flat=True))
        for key, name, description, types in SHIPPED_TEMPLATES:
            if key in have:
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
        """What the viewer preselects: the type's template, else the Default."""
        for_it = cls.for_type(getattr(recording, "recording_type", ""))
        return for_it[0] if for_it else cls.the_default()

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
    # Describe the recording at intervals before writing (Phase 4).
    describe_first = models.BooleanField(default=False)
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
    # Asked for by a person, or accepted from a Cue; the phrase is content.
    source = models.CharField(max_length=10, default=ASKED)
    cue_text = models.CharField(max_length=80, blank=True, default="")
    # A question about the moment, answered from still frames; empty means a
    # description of the clip. Content, never logged.
    question = models.TextField(blank=True, default="")
    state = models.CharField(max_length=10, choices=STATES, default=QUEUED)
    reason_class = models.CharField(max_length=40, blank=True, default="")
    text = models.TextField(blank=True, default="")
    edited = models.BooleanField(default=False)
    model = models.CharField(max_length=120, blank=True, default="")
    # How many frames the engine was shown, for the Details panel.
    frames = models.IntegerField(default=0)
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


class Cue(models.Model):
    """A line, or a second, where the picture would tell what the words cannot.

    Found by the finder reading the Transcript, or by the scan of the picture
    and sound; never by a word list. Nothing is described until a person
    accepts one. The reason is content: shown on the pill, never logged.
    """

    TRANSCRIPT, PICTURE, SOUND = "transcript", "picture", "sound"
    PENDING, ACCEPTED, DISMISSED = "pending", "accepted", "dismissed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transcript = models.ForeignKey(
        "core.Transcript", on_delete=models.CASCADE, related_name="cues"
    )
    segment = models.ForeignKey(
        "core.Segment", on_delete=models.SET_NULL, null=True, blank=True
    )
    at = models.FloatField()
    line = models.IntegerField(default=0)
    kind = models.CharField(max_length=12, default="change")
    reason = models.CharField(max_length=120, blank=True, default="")
    confidence = models.CharField(max_length=8, default="medium")
    source = models.CharField(max_length=12, default=TRANSCRIPT)
    state = models.CharField(max_length=10, default=PENDING)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["at", "created"]


class CueRun(models.Model):
    """One Find moments press, per finder, or one Describe the whole recording.

    What it is doing, so the tab can wait; for the intervals, how many of how
    many are described so far.
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
        "reachable": reachable,
        "unavailable_line": engine.WHAT_TO_SAY.get(engine.UNREACHABLE, ""),
    }


def thinking() -> bool:
    return bool(settings_store.get("assistant_thinks"))


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

    `more` is a Moment's source (asked, or from a cue), never a word of it.
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
        if (
            summary.describe_first
            and features()["moments"]
            and playable_video(recording)
        ):
            run = CueRun.objects.create(
                transcript=transcript, source=CueRun.INTERVAL, asked_by=summary.asked_by
            )
            describe_intervals(run.pk)
            run.refresh_from_db()
            if run.reason_class == engine.UNREACHABLE:
                raise engine.Problem(engine.UNREACHABLE, "the engine went away")
        lines = prompts.lines_of(transcript)
        rendered = prompts.render(lines)
        seen = moments_for_answers(transcript)
        system = prompts.system_message(
            ground.text, template.text, prompts.SUMMARY_FORMAT
        )
        user = "\n\n".join(
            part
            for part in [
                prompts.nature_line(recording, transcript),
                rendered,
                prompts.camera_lines(seen),
                prompts.summary_input(summary.focus, summary.length),
            ]
            if part
        )
        wanted = settings_store.summary_answer_cap(summary.length)
        if not prompts.fits(system, user, answer_cap=cap(wanted), window=window()):
            raise engine.Problem(engine.TOO_LONG, "the transcript is too long")
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
        lines = prompts.lines_of(transcript)
        rendered = prompts.render(lines)
        seen = moments_for_answers(transcript)
        system = prompts.system_message(ground.text, template.text, prompts.CHAT_FORMAT)
        earlier = [
            (one.question, one.answer)
            for one in chat.turns.filter(state=DONE, number__lt=turn.number)
        ]
        history = prompts.history_that_fits(
            earlier, settings_store.chat_history_tokens()
        )
        user = "\n\n".join(
            part
            for part in [
                prompts.nature_line(recording, transcript),
                rendered,
                prompts.camera_lines(seen),
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
        turn.answer = answer["text"].strip()
        turn.citations = prompts.citations(turn.answer, lines, seen)
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


def moments_for_answers(transcript) -> list:
    """The Moments Summary and Chat are told about, or none.

    Only while Moments are on and the office hands them to answers; a Moment
    that failed or is still being described is not a description.
    """
    if not settings_store.get("moments_in_answers") or not features()["moments"]:
        return []
    return list(transcript.moments.filter(state=DONE).exclude(text=""))


def playable_video(recording) -> bool:
    """Whether the Playback copy exists and carries a picture."""
    playback = recording.playback_path()
    return bool(
        recording.playback_ready and playback is not None and playback.suffix == ".mp4"
    )


def moment_span(recording, at: float) -> tuple[float, float]:
    """The clip's span around a time: half the setting either side, inside the file."""
    half = settings_store.moment_span_seconds() / 2
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
        span_start, span_end = moment_span(recording, moment.at)
        moment.span_start, moment.span_end = span_start, span_end
        lines = prompts.lines_of(transcript)
        spoken = prompts.lines_in_span(lines, span_start, span_end)
        answer_cap = settings_store.moments_answer_cap()

        if moment.is_question:
            # A question: a few frames at the camera's own detail, and the
            # question's fixed shape; the editable template still applies.
            height = settings_store.moment_question_height()
            times = question_times(
                moment.at,
                settings_store.moment_question_frames(),
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
            height = settings_store.moment_frame_height()
            frames = max(1, round((span_end - span_start) * fps))
            style = (
                prompts.MOMENT_FORMAT_FULL
                if settings_store.moment_style() == "full"
                else prompts.MOMENT_FORMAT_BRIEF
            )
            system = prompts.system_message(ground.text, template.text, style)
            text = "\n\n".join(
                [
                    prompts.nature_line(recording, transcript),
                    prompts.moment_input(spoken, span_start, span_end),
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


def interval_times(
    length: float, interval: float, most: int, taken: list[float]
) -> list[float]:
    """The seconds to describe at: from half an interval in, one every interval.

    A time within half an interval of one already described is skipped, and
    more than `most` are spread evenly over the recording.
    """
    if length <= 0 or interval <= 0:
        return []
    half = interval / 2
    times = []
    at = half
    while at < length:
        if not any(abs(at - done) < half for done in taken):
            times.append(round(at, 3))
        at += interval
    if len(times) > most:
        step = len(times) / most
        times = [times[int(n * step)] for n in range(most)]
    return times


def describe_intervals(run_id) -> None:
    """Describe the whole recording: one Moment per interval, one after another.

    In one lane, so a long recording never takes the assistant's four lanes
    from everyone else. Stops when the engine goes away; a single failed
    Moment is left failed and the rest go on.
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
    taken = [
        one.at for one in transcript.moments.exclude(state=FAILED).exclude(text="")
    ] + [one.at for one in transcript.moments.filter(state__in=(QUEUED, RUNNING))]
    times = interval_times(
        float(recording.duration_seconds or 0.0),
        settings_store.moment_interval_seconds(),
        settings_store.moment_interval_most(),
        taken,
    )
    moments = [
        Moment.objects.create(
            transcript=transcript, at=at, source=Moment.INTERVAL, asked_by=run.asked_by
        )
        for at in times
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
    run.state = FAILED if reason else DONE
    run.reason_class = reason
    run.finished_at = timezone.now()
    run.save()


def find_moments(run_id) -> None:
    """One read of the whole Transcript, replacing every pending Cue from the words."""
    run = (
        CueRun.objects.filter(pk=run_id)
        .select_related("transcript", "transcript__recording")
        .first()
    )
    if run is None:
        return
    transcript = run.transcript
    recording = transcript.recording
    started = time.monotonic()
    ground = PromptTemplate.named(PromptTemplate.GROUND_RULES)
    template = PromptTemplate.named(PromptTemplate.FINDER)
    templates_line = f"ground-rules v{ground.version}; Find moments v{template.version}"
    run.state = RUNNING
    run.save(update_fields=["state"])

    usage: dict = {}
    try:
        problem = _unreachable()
        if problem:
            raise problem
        lines = prompts.lines_of(transcript)
        if not lines:
            raise engine.Problem(engine.ERROR, "there are no lines to read")
        most = settings_store.moment_finder_most()
        system = prompts.system_message(
            ground.text, template.text, prompts.FINDER_FORMAT
        )
        user = "\n\n".join(
            [
                prompts.nature_line(recording, transcript),
                prompts.render(lines),
                prompts.finder_input(most),
            ]
        )
        finder_cap = settings_store.moment_finder_cap()
        if not prompts.fits(system, user, answer_cap=cap(finder_cap), window=window()):
            raise engine.Problem(engine.TOO_LONG, "the transcript is too long")

        raw = None
        for attempt in (1, 2):
            answer = engine.complete(
                _messages(system, user),
                max_completion_tokens=cap(finder_cap),
                thinking=thinking(),
                timeout=time_limit("moment_finder"),
                schema=prompts.finder_schema(most),
                **SUGGESTION_SAMPLING,
            )
            usage = answer
            try:
                try:
                    parsed = json.loads(answer["text"])
                except ValueError:
                    parsed = json.loads(prompts.salvage_json(answer["text"]))
                raw = parsed.get("cues", [])
                if not isinstance(raw, list):
                    raise ValueError("not a list")
                break
            except (ValueError, AttributeError) as bad:
                if attempt == 2:
                    raise engine.Problem(
                        engine.BAD_OUTPUT, "invalid finder JSON twice"
                    ) from bad
        kept = prompts.keep_cues(
            raw or [], lines, settings_store.moment_finder_confidence(), most
        )
        transcript.cues.filter(source=Cue.TRANSCRIPT, state=Cue.PENDING).delete()
        for one in kept:
            Cue.objects.create(
                transcript=transcript,
                segment_id=one["segment_id"],
                at=one["start"],
                line=one["line"],
                kind=one["kind"],
                reason=one["reason"],
                confidence=one["confidence"],
                source=Cue.TRANSCRIPT,
            )
        run.found = len(kept)
        run.state = DONE
        run.reason_class = ""
        run.finished_at = timezone.now()
        run.save()
        _record(
            "moment_finder",
            recording,
            actor=run.asked_by,
            templates=templates_line,
            model=answer["model"],
            usage=usage,
            started=started,
            outcome="ok",
            found=len(kept),
        )
    except engine.Problem as problem:
        run.state = FAILED
        run.reason_class = problem.reason
        run.finished_at = timezone.now()
        run.save(update_fields=["state", "reason_class", "finished_at"])
        _record(
            "moment_finder",
            recording,
            actor=run.asked_by,
            templates=templates_line,
            model="",
            usage=usage,
            started=started,
            outcome=problem.reason,
            reason=problem.reason,
        )


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
