"""The comparison (Phase 8 chapter 4, part 3): a report against the record.

Compare with the report reads one Document in windows of pages against the
incident record and the Chronology (or one Recording's transcript and
Digest), and gathers findings: one row each, the report's paragraph and the
record's moment both cited, marked agrees, differs, not on camera or not in
the report. A finding with a side missing is dropped by the app. The rows
land as a layer; a person marks them and makes one an Event. The comparison
is kept on its home, one per document, replaced by Compare again, stale when
the cameras or the Chronology change, as the memo is.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from urllib.parse import urlparse

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from core import (
    assistant,
    audit,
    chronology,
    engine,
    incidents,
    prompts,
    settings_store,
)
from core.assistant import DONE, FAILED, QUEUED, RUNNING, PromptTemplate
from core.documents import READY, Document

log = logging.getLogger("transcribe.comparison")

FEATURE = "compare_report"
AGREES = "agrees"
DIFFERS = "differs"
NOT_ON_CAMERA = "not_on_camera"
NOT_IN_REPORT = "not_in_report"
MARKS = (AGREES, DIFFERS, NOT_ON_CAMERA, NOT_IN_REPORT)
MARK_WORDS = {
    AGREES: "Agrees",
    DIFFERS: "Differs",
    NOT_ON_CAMERA: "Not on camera",
    NOT_IN_REPORT: "Not in the report",
}
# The window of pages one call reads against the whole record.
PAGES_A_WINDOW = 8
# The most findings kept from one window, and per comparison.
WINDOW_MOST = 25
FINDINGS_MOST = 200
STAMP = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})")
CLAIM_MOST = 300
WHY_MOST = 300


class Comparison(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="comparisons"
    )
    incident = models.ForeignKey(
        "core.Incident",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="comparisons",
    )
    recording = models.ForeignKey(
        "core.Recording",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="comparisons",
    )
    asked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    state = models.CharField(max_length=10, default=QUEUED)
    stage = models.CharField(max_length=80, blank=True, default="")
    reason_class = models.CharField(max_length=40, blank=True, default="")
    # [{"id", "mark", "page", "n", "paragraph", "claim", "at", "why",
    #   "dismissed", "note", "event"}]
    findings = models.JSONField(default=list, blank=True)
    windows = models.IntegerField(default=0)
    cut_short = models.IntegerField(default=0)
    left_out_check = models.BooleanField(default=False)
    # v1.74.2: answers the app could not read, and the findings it dropped
    # by reason, so an empty comparison says why.
    unreadable = models.IntegerField(default=0)
    dropped = models.JSONField(default=dict, blank=True)
    model = models.CharField(max_length=120, blank=True, default="")
    template_version = models.IntegerField(default=1)
    ground_rules_version = models.IntegerField(default=1)
    cameras_used = models.JSONField(default=list, blank=True)
    # Read by their words alone to fit the Sitting (Phase 8 chapter 9).
    cameras_words_alone = models.JSONField(default=list, blank=True)
    record_lines = models.IntegerField(default=0)
    events_signature = models.CharField(max_length=32, blank=True, default="")
    cameras_signature = models.CharField(max_length=32, blank=True, default="")
    created = models.DateTimeField(auto_now_add=True)
    written_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self) -> str:
        return f"comparison of {self.document_id}"

    def home(self):
        return self.incident or self.recording

    def counts(self) -> dict:
        out = {mark: 0 for mark in MARKS}
        for one in self.findings:
            if not one.get("dismissed"):
                out[one["mark"]] = out.get(one["mark"], 0) + 1
        return out


# The settings -------------------------------------------------------------------------


def on() -> bool:
    return bool(
        settings_store.get("documents")
        and settings_store.get("documents_compare")
        and assistant.features()["chat"]
    )


def answer_cap() -> int:
    return int(settings_store.get("documents_compare_answer_tokens"))


def possible(document: Document, home) -> tuple[bool, str]:
    """Whether a comparison can run: the document read, and the home with
    words to compare against."""
    if not on():
        return False, "The comparison is off."
    if document.state != READY:
        return False, "The document is still being read."
    if isinstance(home, incidents.Incident):
        from core.incident_assistant import synced_cameras

        if not any(
            getattr(one.recording, "transcript", None) is not None
            for one in synced_cameras(home)
        ):
            return False, "Sync a camera that has a transcript first."
        return True, ""
    if getattr(home, "transcript", None) is None:
        return False, "The recording has no transcript to compare against yet."
    return True, ""


def of(document: Document, home) -> Comparison | None:
    if isinstance(home, incidents.Incident):
        return document.comparisons.filter(incident=home).first()
    return document.comparisons.filter(recording=home).first()


def ask_for(document: Document, home, *, by) -> Comparison | None:
    """Compare with the report: one comparison per document and home,
    replaced by Compare again; the call runs on the llm queue."""
    can, _ = possible(document, home)
    if not can:
        return None
    old = of(document, home)
    if old is not None and old.state in (QUEUED, RUNNING):
        return old
    if old is not None:
        old.delete()
    fields = (
        {"incident": home}
        if isinstance(home, incidents.Incident)
        else {"recording": home}
    )
    comparison = Comparison.objects.create(document=document, asked_by=by, **fields)
    from core import tasks

    tasks.compare_report.defer(comparison_id=str(comparison.pk))
    return comparison


# The reading --------------------------------------------------------------------------


def _paragraph_windows(document: Document) -> list[list[dict]]:
    """The document's paragraphs in windows of pages."""
    rows = []
    for page in document.page_rows.order_by("number"):
        for one in page.paragraphs:
            rows.append({"page": page.number, "n": one["n"], "text": one["text"]})
    windows: list[list[dict]] = []
    for row in rows:
        if not windows or (row["page"] - windows[-1][0]["page"]) >= PAGES_A_WINDOW:
            windows.append([row])
        else:
            windows[-1].append(row)
    return windows


def _paragraph_lines(rows: list[dict]) -> str:
    return "\n".join(
        f"[Report, page {row['page']}, paragraph {row['n']}] {row['text']}"
        for row in rows
    )


def _record_for(comparison: Comparison) -> dict:
    """What the report is compared against: the incident record and the
    chronology on the incident clock, or the recording's lines and digest."""
    if comparison.incident_id:
        from core.incident_assistant import (
            _cameras_line,
            _chronology_lines,
            _record_text,
            record_of,
        )

        incident = comparison.incident
        record = record_of(incident, words_alone=set(comparison.cameras_words_alone))
        event_lines, _ = _chronology_lines(incident)
        return {
            "head": _cameras_line(incident),
            "events": event_lines,
            "record": _record_text(incident, record, set()),
            "lines": len(record["rows"]),
            "cameras": record["used"] + record["transcript_only"],
            "words_alone": record["words_alone"],
            "clock": incident.has_clock(),
        }
    recording = comparison.recording
    transcript = recording.transcript
    lines = prompts.lines_of(transcript)
    digest = assistant.digest_text(transcript) if assistant.digests_on() else ""
    body = prompts.render(lines)
    return {
        "head": prompts.nature_line(recording, transcript)
        + " Every time is hh:mm:ss into the recording.",
        "events": [],
        "record": body + ("\n\n" + prompts.digest_block(digest) if digest else ""),
        "lines": len(lines),
        "cameras": [recording.title],
        "clock": False,
    }


def _seconds_of(comparison: Comparison, stamp: str) -> float | None:
    """A [hh:mm:ss] in an answer as seconds on the home's clock, or None
    when it is not a time or lies outside the home."""
    found = STAMP.search(stamp or "")
    if not found:
        return None
    h, m, s = (int(part) for part in found.groups())
    whole = h * 3600 + m * 60 + s
    if comparison.incident_id:
        incident = comparison.incident
        low, high = incidents.span_of(incident)
        at = (
            float(whole - incident.clock_zero) if incident.has_clock() else float(whole)
        )
        if incident.has_clock():
            at = (
                incidents._wrapped(whole - incident.clock_zero)
                if hasattr(incidents, "_wrapped")
                else at
            )
        if at < low - 1 or at > high + 1:
            return None
        return round(max(low, at), 2)
    length = float(comparison.recording.duration_seconds or 0)
    if whole > length + 1:
        return None
    return round(min(float(whole), length), 2)


# Why a finding was dropped, as the state line says it.
NOT_A_FINDING = "not a finding"
MARK_UNKNOWN = "mark unknown"
PARAGRAPH_NOT_FOUND = "paragraph not found"
NO_TIME = "no time on the clock"
NO_CLAIM = "no claim"
TWIN = "said twice"


def _keep(comparison: Comparison, item: dict, known: dict, taken: set) -> dict | None:
    """One finding from an answer, or None: the mark must be one of the
    four, the paragraph real (except for not in the report), the moment real
    (except for not on camera). `_why_dropped` says the reason."""
    one, _ = _keep_or_why(comparison, item, known, taken)
    return one


def _keep_or_why(
    comparison: Comparison, item: dict, known: dict, taken: set
) -> tuple[dict | None, str]:
    if not isinstance(item, dict):
        return None, NOT_A_FINDING
    mark = str(item.get("mark", "")).strip().lower().replace(" ", "_")
    if mark not in MARKS:
        return None, MARK_UNKNOWN
    page = item.get("page")
    n = item.get("paragraph")
    try:
        page = int(page) if page not in (None, "") else 0
        n = int(n) if n not in (None, "") else 0
    except (TypeError, ValueError):
        return None, PARAGRAPH_NOT_FOUND
    paragraph = known.get((page, n), "")
    if mark != NOT_IN_REPORT and not paragraph:
        return None, PARAGRAPH_NOT_FOUND
    at = _seconds_of(comparison, str(item.get("at", "")))
    if mark in (AGREES, DIFFERS, NOT_IN_REPORT) and at is None:
        return None, NO_TIME
    claim = " ".join(str(item.get("claim", "")).split())[:CLAIM_MOST]
    if not claim:
        return None, NO_CLAIM
    key = (mark, page, n, claim.lower()[:60])
    if key in taken:
        return None, TWIN
    taken.add(key)
    return {
        "id": uuid.uuid4().hex[:12],
        "mark": mark,
        "page": page,
        "n": n,
        "paragraph": paragraph,
        "claim": claim,
        "at": at,
        "why": " ".join(str(item.get("why", "")).split())[:WHY_MOST],
        "dismissed": False,
        "note": "",
        "event": "",
    }, ""


FENCE = re.compile(r"^\s*```[a-zA-Z]*\s*\n|\n\s*```\s*$", re.MULTILINE)


def _unfenced(text: str) -> str:
    """The answer without a Markdown code fence around it, and without any
    words before its first brace: the engine wraps JSON in ```json ... ```
    when asked for JSON only (v1.74.2, from the first real report)."""
    text = FENCE.sub("", text or "")
    starts = [at for at in (text.find("{"), text.find("[")) if at >= 0]
    return text[min(starts) :].strip() if starts else text.strip()


def _parse(text: str) -> list:
    text = _unfenced(text)
    try:
        parsed = json.loads(text)
    except ValueError:
        parsed = json.loads(prompts.salvage_json(text))
    raw = parsed.get("findings", []) if isinstance(parsed, dict) else parsed
    if not isinstance(raw, list):
        raise ValueError("not a list")
    return raw


def compare(comparison_id, attempt: int = 1) -> None:
    """The call: the record and the chronology, and the report in windows of
    pages, in; the findings out; one audit row per window and one for the run."""
    comparison = (
        Comparison.objects.filter(pk=comparison_id)
        .select_related(
            "document", "document__case", "incident", "recording", "asked_by"
        )
        .first()
    )
    if comparison is None:
        if attempt == 1:
            from core import tasks

            tasks.compare_report.configure(
                schedule_in={"seconds": assistant.QUEUE_GRACE_SECONDS}
            ).defer(comparison_id=str(comparison_id), attempt=attempt + 1)
        return
    if comparison.state not in (QUEUED, RUNNING):
        return
    document = comparison.document
    started = time.monotonic()
    ground = PromptTemplate.named(PromptTemplate.GROUND_RULES)
    template = PromptTemplate.named(PromptTemplate.COMPARISON)
    templates_line = f"ground-rules v{ground.version}; Comparison v{template.version}"
    comparison.state = RUNNING
    comparison.stage = "Reading the record"
    comparison.template_version = template.version
    comparison.ground_rules_version = ground.version
    comparison.save(
        update_fields=["state", "stage", "template_version", "ground_rules_version"]
    )
    usage: dict = {"input_tokens": 0, "output_tokens": 0}
    calls = 0
    try:
        problem = assistant._unreachable()
        if problem:
            raise problem
        can, why = possible(document, comparison.home())
        if not can:
            raise engine.Problem(engine.ERROR, why or "the comparison cannot run")
        windows = _paragraph_windows(document)
        if not windows:
            raise engine.Problem(engine.ERROR, "the document has no words to compare")
        against = _record_for(comparison)
        if not against["record"].strip():
            raise engine.Problem(engine.ERROR, "nothing to compare against")
        known = {
            (row["page"], row["n"]): row["text"] for window in windows for row in window
        }
        system = prompts.system_message(
            ground.text,
            template.text,
            prompts.COMPARISON_FORMAT + "\n\n" + prompts.INCIDENT_RULES,
        )
        cap = assistant.cap(answer_cap())
        # One sitting (Phase 8 chapter 9): the record fitted once, against
        # the largest page window, the longest cameras' pictures going first.
        if comparison.incident_id:
            from core import sitting

            largest = max(windows, key=lambda window: len(_paragraph_lines(window)))
            try:
                _, _, words_alone = sitting.fit(
                    comparison.incident,
                    system=system,
                    wrap=lambda body: prompts.comparison_input(
                        against["head"],
                        against["events"],
                        body,
                        _paragraph_lines(largest),
                        first=largest[0]["page"],
                        last=largest[-1]["page"],
                    ),
                    answer_cap=cap,
                )
            except sitting.TooLong:
                raise engine.Problem(
                    engine.TOO_LONG, "the words alone are too long"
                ) from None
            comparison.cameras_words_alone = list(words_alone)
            against = _record_for(comparison)
        findings: list[dict] = []
        taken: set = set()
        cut = 0
        model = ""
        unreadable = 0
        dropped: dict = {}

        def drop(why: str) -> None:
            dropped[why] = dropped.get(why, 0) + 1

        for number, window in enumerate(windows, start=1):
            comparison.stage = f"Reading pages, window {number} of {len(windows)}"
            comparison.save(update_fields=["stage"])
            user = prompts.comparison_input(
                against["head"],
                against["events"],
                against["record"],
                _paragraph_lines(window),
                first=window[0]["page"],
                last=window[-1]["page"],
            )
            if not prompts.fits(
                system, user, answer_cap=cap, window=assistant.window()
            ):
                raise engine.Problem(engine.TOO_LONG, "the record is too long")
            answer = engine.complete(
                assistant._messages(system, user),
                max_completion_tokens=cap,
                thinking=assistant.thinking(),
                timeout=assistant.time_limit(FEATURE),
                **assistant.SAMPLING,
            )
            calls += 1
            usage["input_tokens"] += answer.get("input_tokens", 0) or 0
            usage["output_tokens"] += answer.get("output_tokens", 0) or 0
            model = answer.get("model", "") or model
            if answer.get("finish_reason") == "length":
                cut += 1
            if assistant.thought_it_away(answer):
                raise assistant.ThoughtItAway()
            try:
                raw = _parse(answer["text"])
            except (ValueError, AttributeError):
                log.warning(
                    "comparison %s: an answer was unreadable (%d chars, starts %r)",
                    comparison.pk,
                    len(answer.get("text") or ""),
                    (answer.get("text") or "")[:12],
                )
                unreadable += 1
                continue
            kept_here = 0
            for item in raw:
                if kept_here >= WINDOW_MOST or len(findings) >= FINDINGS_MOST:
                    break
                one, why = _keep_or_why(comparison, item, known, taken)
                if one is None:
                    drop(why)
                    continue
                if one["mark"] == NOT_IN_REPORT:
                    continue
                findings.append(one)
                kept_here += 1
        # What the report leaves out: the chronology against the whole
        # report, when the whole fits; otherwise said so.
        left_out_check = False
        if against["events"] and comparison.incident_id:
            comparison.stage = "Checking what the report leaves out"
            comparison.save(update_fields=["stage"])
            whole = _paragraph_lines([row for window in windows for row in window])
            user = prompts.comparison_left_out_input(
                against["head"], against["events"], whole
            )
            if prompts.fits(system, user, answer_cap=cap, window=assistant.window()):
                answer = engine.complete(
                    assistant._messages(system, user),
                    max_completion_tokens=cap,
                    thinking=assistant.thinking(),
                    timeout=assistant.time_limit(FEATURE),
                    **assistant.SAMPLING,
                )
                calls += 1
                usage["input_tokens"] += answer.get("input_tokens", 0) or 0
                usage["output_tokens"] += answer.get("output_tokens", 0) or 0
                if answer.get("finish_reason") == "length":
                    cut += 1
                if assistant.thought_it_away(answer):
                    raise assistant.ThoughtItAway()
                try:
                    for item in _parse(answer["text"]):
                        if len(findings) >= FINDINGS_MOST:
                            break
                        one, why = _keep_or_why(comparison, item, known, taken)
                        if one is None:
                            drop(why)
                        elif one["mark"] == NOT_IN_REPORT:
                            findings.append(one)
                except (ValueError, AttributeError):
                    log.warning(
                        "comparison %s: the left-out answer was unreadable",
                        comparison.pk,
                    )
                    unreadable += 1
            else:
                left_out_check = True
        findings.sort(
            key=lambda one: (one["page"] or 9999, one["n"] or 9999, one["at"] or 0)
        )
        if not Comparison.objects.filter(pk=comparison.pk).exists():
            return
        comparison.findings = findings
        comparison.windows = len(windows)
        comparison.cut_short = cut
        comparison.unreadable = unreadable
        comparison.dropped = dropped
        comparison.left_out_check = left_out_check
        comparison.model = model
        comparison.cameras_used = against["cameras"]
        comparison.record_lines = against["lines"]
        if comparison.incident_id:
            from core.incident_assistant import cameras_signature, events_signature

            comparison.events_signature = events_signature(comparison.incident)
            comparison.cameras_signature = cameras_signature(comparison.incident)
        comparison.stage = ""
        comparison.state = DONE
        comparison.reason_class = ""
        comparison.written_at = timezone.now()
        comparison.save()
        _audit(
            comparison,
            templates_line,
            usage,
            started,
            "ok",
            calls=calls,
            words_alone=len(comparison.cameras_words_alone),
        )
        counts = comparison.counts()
        audit.write(
            audit.Category.CASES,
            "Comparison run",
            actor=comparison.asked_by,
            affected_user=(
                document.case.owner
                if comparison.asked_by is not None
                and document.case.owner_id != comparison.asked_by.pk
                else None
            ),
            object_type="document",
            object_id=document.pk,
            object_label=document.title,
            windows=len(windows),
            findings=len(findings),
            unreadable=unreadable,
            dropped=sum(dropped.values()),
            **{mark: counts[mark] for mark in MARKS},
        )
    except engine.Problem as problem:
        if not Comparison.objects.filter(pk=comparison.pk).exists():
            return
        comparison.state = FAILED
        comparison.stage = ""
        comparison.reason_class = (
            assistant.THOUGHT_AWAY
            if isinstance(problem, assistant.ThoughtItAway)
            else problem.reason
        )
        comparison.save(update_fields=["state", "stage", "reason_class"])
        _audit(
            comparison,
            templates_line,
            usage,
            started,
            problem.reason,
            reason=problem.reason,
        )


def sitting_read_words(comparison: Comparison) -> str:
    """ "everything said on 12 cameras and what 7 of them showed" (Phase 8
    chapter 9), for the state line and the Word export."""
    from core import sitting

    count = len(comparison.cameras_used)
    alone = list(comparison.cameras_words_alone)
    return sitting.read_words(count, count - len(alone), alone)


def _audit(
    comparison, templates, usage, started, outcome, *, reason="", **more
) -> None:
    document = comparison.document
    actor = comparison.asked_by
    audit.write(
        audit.Category.LLM,
        "AI assistant call",
        actor=actor,
        outcome=audit.Outcome.SUCCESS if outcome == "ok" else audit.Outcome.FAILURE,
        reason_class=reason,
        affected_user=(
            document.case.owner
            if actor is not None and document.case.owner_id != actor.pk
            else None
        ),
        object_type="document",
        object_id=document.pk,
        object_label=document.title,
        feature=FEATURE,
        model=comparison.model or engine.model_name(),
        endpoint_host=urlparse(engine.address()).hostname or "",
        templates=templates,
        window_source=engine.window_source(),
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        duration_seconds=round(time.monotonic() - started, 1),
        **more,
    )


# The page -----------------------------------------------------------------------------


def counts_words(counts: dict) -> str:
    """ "31 findings: 12 agree, 6 differ, 9 not on camera, 4 not in the report"."""
    total = sum(counts.values())
    return (
        f"{total} finding{'' if total == 1 else 's'}: {counts[AGREES]} agree, "
        f"{counts[DIFFERS]} differ, {counts[NOT_ON_CAMERA]} not on camera, "
        f"{counts[NOT_IN_REPORT]} not in the report"
    )


def dropped_words(comparison: Comparison) -> str:
    """ "; 1 answer could not be read; 5 findings dropped: paragraph not
    found 3, no time on the clock 2", or nothing."""
    words = ""
    unread = int(comparison.unreadable or 0)
    if unread:
        words += f"; {unread} answer{'' if unread == 1 else 's'} could not be read"
    dropped = comparison.dropped or {}
    total = sum(dropped.values())
    if total:
        by_reason = ", ".join(
            f"{why} {count}"
            for why, count in sorted(dropped.items(), key=lambda one: (-one[1], one[0]))
        )
        words += f"; {total} finding{'' if total == 1 else 's'} dropped: {by_reason}"
    return words


def stale_words(comparison: Comparison) -> str:
    if comparison.state != DONE or not comparison.incident_id:
        return ""
    from core.incident_assistant import cameras_signature, events_signature

    incident = comparison.incident
    if comparison.events_signature != events_signature(incident):
        return "the chronology changed since"
    if comparison.cameras_signature != cameras_signature(incident):
        return "the cameras changed since"
    return ""


def clock_words(comparison: Comparison, at) -> str:
    if at is None:
        return ""
    if comparison.incident_id:
        return incidents.time_of_day(comparison.incident, float(at))
    return prompts.clock(float(at)).strip("[]")


def as_json(comparison: Comparison | None, document: Document, home) -> dict:
    """The comparison as the layer draws it."""
    can, why = possible(document, home)
    base = {
        "on": on(),
        "possible": can,
        "why": why,
        "document": document.title,
        "document_url": document.url(),
        "compare_url": reverse(
            "document-compare", args=[document.case_id, document.pk]
        ),
        "act_url": reverse(
            "document-comparison-act", args=[document.case_id, document.pk]
        ),
        "home": "incident" if isinstance(home, incidents.Incident) else "recording",
        "home_id": str(home.pk),
        "can_make_event": isinstance(home, incidents.Incident),
        "marks": [{"key": mark, "words": MARK_WORDS[mark]} for mark in MARKS],
    }
    if comparison is None:
        return {
            **base,
            "state": "",
            "words": "",
            "findings": [],
            "counts": {},
            "busy": False,
        }
    if comparison.state == QUEUED:
        words = "Waiting for the engine..."
    elif comparison.state == RUNNING:
        words = comparison.stage or "Reading..."
    elif comparison.state == FAILED:
        words = assistant.what_to_say(comparison.reason_class)
    else:
        counts = comparison.counts()
        when = (
            timezone.localtime(comparison.written_at).strftime("%H:%M")
            if comparison.written_at
            else ""
        )
        cut = comparison.cut_short
        words = (
            f"{document.pages} pages against "
            + (
                sitting_read_words(comparison)
                if comparison.incident_id
                else f"{len(comparison.cameras_used)} "
                f"{'camera' if len(comparison.cameras_used) == 1 else 'cameras'}"
            )
            + "; "
            + counts_words(counts)
            + (f"; written at {when}" if when else "")
            + (
                f"; {cut} answer{'' if cut == 1 else 's'} cut short, "
                "raise the Comparison answer cap"
                if cut
                else ""
            )
            + (
                "; the report was too long to check for what it leaves out"
                if comparison.left_out_check
                else ""
            )
            + dropped_words(comparison)
        )
    return {
        **base,
        "id": str(comparison.pk),
        "state": comparison.state,
        "busy": comparison.state in (QUEUED, RUNNING),
        "words": words,
        "stale": stale_words(comparison),
        "counts": comparison.counts() if comparison.state == DONE else {},
        "export_url": reverse(
            "document-comparison-export", args=[document.case_id, document.pk]
        )
        + f"?{base['home']}={home.pk}",
        "findings": [
            {
                **one,
                "mark_words": MARK_WORDS.get(one["mark"], one["mark"]),
                "clock": clock_words(comparison, one.get("at")),
                "paragraph_url": (
                    f"{document.url()}?page={one['page']}&para={one['n']}"
                    if one.get("page")
                    else ""
                ),
            }
            for one in comparison.findings
        ]
        if comparison.state == DONE
        else [],
    }


# Marks on the findings ----------------------------------------------------------------


def _finding(comparison: Comparison, finding_id: str) -> dict | None:
    return next((one for one in comparison.findings if one["id"] == finding_id), None)


def set_dismissed(comparison: Comparison, finding_id: str, dismissed: bool) -> bool:
    one = _finding(comparison, finding_id)
    if one is None:
        return False
    one["dismissed"] = dismissed
    comparison.save(update_fields=["findings"])
    return True


def set_note(comparison: Comparison, finding_id: str, note: str) -> bool:
    one = _finding(comparison, finding_id)
    if one is None:
        return False
    one["note"] = " ".join(str(note or "").split())[:2000]
    comparison.save(update_fields=["findings"])
    return True


def make_event(comparison: Comparison, finding_id: str, *, at=None, by, request=None):
    """Make it an event: on the chronology at the moment, the claim as its
    line, source report, resting on the paragraph, the mark as its why."""
    one = _finding(comparison, finding_id)
    if one is None or not comparison.incident_id:
        raise ValueError("no such finding")
    moment = one.get("at") if at is None else at
    if moment is None:
        raise ValueError("Say the moment on the incident clock this event is at.")
    rests = (
        f"[Report, page {one['page']}, paragraph {one['n']}] {one['paragraph']}"
        if one.get("page")
        else ""
    )
    why = MARK_WORDS.get(one["mark"], "") + (
        f": {one['why']}" if one.get("why") else ""
    )
    event = chronology.add(
        comparison.incident,
        {
            "at": str(float(moment)),
            "text": one["claim"],
            "source": chronology.REPORT,
            "rests_on": rests,
            "why": why,
            "note": one.get("note", ""),
        },
        by=by,
        request=request,
    )
    one["event"] = str(event.pk)
    comparison.save(update_fields=["findings"])
    return event


# The export ---------------------------------------------------------------------------


def word(comparison: Comparison, exported_by: str) -> bytes:
    """Comparison to Word: the cover, then one table of the findings."""
    import io

    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt

    from core import exports

    document = comparison.document
    home = comparison.home()
    home_name = home.name if comparison.incident_id else home.title
    doc = exports._open_record_document()
    exports._office_head(doc)
    heading = doc.add_paragraph(f"Comparison: {document.title}")
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    heading.runs[0].bold = True
    heading.runs[0].font.size = Pt(20)
    counts = comparison.counts()
    exports._facts(
        doc,
        [
            (
                "Against",
                f"{'Incident' if comparison.incident_id else 'Recording'} {home_name}",
            ),
            ("Cameras", ", ".join(comparison.cameras_used) or "none"),
            ("Report", f"{document.title}, {document.pages_line()}"),
            ("Findings", counts_words(counts)),
            (
                "Written",
                f"{timezone.localtime(comparison.written_at):%d %B %Y %H:%M}"
                if comparison.written_at
                else "",
            ),
            ("Exported", f"{timezone.localtime():%d %B %Y %H:%M} by {exported_by}"),
        ],
        __import__("docx.shared", fromlist=["Inches"]).Inches,
    )
    doc.add_paragraph()
    notice = doc.add_paragraph(
        "The report is the officer's account and the cameras are the record; a "
        "description of the picture is a description. Every finding cites the "
        "paragraph and the moment; a person marks them. Not a legal conclusion."
    )
    notice.runs[0].italic = True
    table = doc.add_table(rows=1, cols=6)
    table.style = "Light Grid Accent 1"
    for cell, title in zip(
        table.rows[0].cells,
        ("Mark", "Paragraph", "Claim", "Moment", "Why", "Note"),
        strict=True,
    ):
        cell.text = title
    for one in comparison.findings:
        cells = table.add_row().cells
        cells[0].text = MARK_WORDS.get(one["mark"], one["mark"]) + (
            " (dismissed)" if one.get("dismissed") else ""
        )
        cells[1].text = (
            f"Page {one['page']}, paragraph {one['n']}: {one['paragraph']}"
            if one.get("page")
            else ""
        )
        cells[2].text = one["claim"]
        cells[3].text = clock_words(comparison, one.get("at"))
        cells[4].text = one.get("why", "")
        cells[5].text = one.get("note", "")
    exports.stamp_pages(
        doc, f"{document.title}, {home_name}", "Comparison", document.title
    )
    holder = io.BytesIO()
    doc.save(holder)
    return holder.getvalue()


def export_name(comparison: Comparison) -> str:
    from core import exports

    return exports.without_clashes(
        set(), f"{exports.safe_name(comparison.document.title)} comparison.docx"
    )
