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
TIME_LIMITS = {"summary": 300, "chat_turn": 120, "speaker_suggestions": 180}
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
    DEFAULTS = {
        GROUND_RULES: ("Ground rules", prompts.GROUND_RULES),
        CHAT: ("Chat", prompts.CHAT),
        SUGGESTIONS: ("Speaker suggestions", prompts.SUGGESTIONS),
        CASE_CHAT: ("Case chat", prompts.CASE_CHAT),
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


# What is on and what is reachable ----------------------------------------------


def features() -> dict:
    """Which of the three features a page may show, and whether the engine answers."""
    on = bool(settings_store.get("assistant_available"))
    reachable = engine.is_reachable() if on else False
    return {
        "assistant": on,
        "summary": on and bool(settings_store.get("summary_available")),
        "chat": on and bool(settings_store.get("chat_available")),
        "suggestions": on and bool(settings_store.get("suggestions_available")),
        "reachable": reachable,
        "unavailable_line": engine.WHAT_TO_SAY.get(engine.UNREACHABLE, ""),
    }


def thinking() -> bool:
    return bool(settings_store.get("assistant_thinks"))


def time_limit(feature: str) -> int:
    return TIME_LIMITS[feature] * (2 if thinking() else 1)


def cap(answer_tokens: int) -> int:
    """The answer cap as sent: the feature's, plus room to think when thinking is on."""
    return answer_tokens + (THINKING_ALLOWANCE if thinking() else 0)


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
):
    """The one audit row a call writes, metadata only, whatever happened."""
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
        lines = prompts.lines_of(transcript)
        rendered = prompts.render(lines)
        system = prompts.system_message(
            ground.text, template.text, prompts.SUMMARY_FORMAT
        )
        user = "\n\n".join(
            [
                prompts.nature_line(recording, transcript),
                rendered,
                prompts.summary_input(summary.focus, summary.length),
            ]
        )
        wanted = prompts.ANSWER_CAPS.get(
            summary.length, prompts.ANSWER_CAPS["standard"]
        )
        if not prompts.fits(system, user, answer_cap=cap(wanted)):
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
        summary.citations = prompts.citations(summary.text, lines)
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
        system = prompts.system_message(ground.text, template.text, prompts.CHAT_FORMAT)
        earlier = [
            (one.question, one.answer)
            for one in chat.turns.filter(state=DONE, number__lt=turn.number)
        ]
        history = prompts.history_that_fits(earlier)
        user = "\n\n".join(
            [prompts.nature_line(recording, transcript), rendered, turn.question]
        )
        history_text = "\n".join(q + "\n" + a for q, a in history)
        if not prompts.fits(
            system, user, history_text, answer_cap=cap(prompts.CHAT_CAP)
        ):
            raise engine.Problem(engine.TOO_LONG, "the transcript is too long")
        answer = engine.complete(
            _messages(system, user, history),
            max_completion_tokens=cap(prompts.CHAT_CAP),
            thinking=thinking(),
            timeout=time_limit("chat_turn"),
            **SAMPLING,
        )
        usage = answer
        turn.answer = answer["text"].strip()
        turn.citations = prompts.citations(turn.answer, lines)
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
        if not prompts.fits(system, user, answer_cap=prompts.SUGGESTIONS_CAP):
            raise engine.Problem(engine.TOO_LONG, "the transcript is too long")

        raw = None
        for attempt in (1, 2):
            answer = engine.complete(
                _messages(system, user),
                max_completion_tokens=cap(prompts.SUGGESTIONS_CAP),
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
    return engine.WHAT_TO_SAY.get(reason, engine.WHAT_TO_SAY.get(engine.ERROR, ""))
