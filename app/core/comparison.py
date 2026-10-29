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

import datetime as dt
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
    expectation,
    incidents,
    prompts,
    proposals,
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
# What the expectation's size allows for the system message and the
# chronology when it asks whether the whole report reads in one window
# (v1.134.0); the run itself fits the real text.
SIZE_TEMPLATES_ALLOWANCE = 6000
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
    # The whole case as the home (Phase 10 chapter 4, v1.170.0): one row that
    # reads the document against every recording of the case in turn, each
    # reading a child row of its own with `parent` set; the parent holds the
    # findings merged, each naming its recording, by day and time.
    case = models.ForeignKey(
        "core.Case",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="comparisons",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
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
    # The time expectation given at the ask (v1.95.0): the size measured,
    # the office's figure, when it was asked for and when the worker began.
    expectation = models.JSONField(default=dict, blank=True)
    # v1.74.2: answers the app could not read, and the findings it dropped
    # by reason, so an empty comparison says why.
    unreadable = models.IntegerField(default=0)
    dropped = models.JSONField(default=dict, blank=True)
    # The check against the record's lines (v1.104.0): how many Agrees and
    # Differs rows it read, how many it moved to not on camera or dropped,
    # how many it left because its two readings differed or could not be
    # read. {"rows", "moved", "dropped", "apart", "unread", "calls"}
    second_look = models.JSONField(default=dict, blank=True)
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
        return self.incident or self.recording or self.case

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
    if _is_case(home):
        if not _readable(home):
            return False, "No recording in the case has a transcript yet."
        return True, ""
    if getattr(home, "transcript", None) is None:
        return False, "The recording has no transcript to compare against yet."
    return True, ""


def _is_case(home) -> bool:
    from core.cases import Case

    return isinstance(home, Case)


def _readable(case) -> list:
    """The recordings a case comparison reads: those with a transcript."""
    return [
        one
        for one in case.recordings.select_related("transcript").order_by(
            "created", "title"
        )
        if getattr(one, "transcript", None) is not None
    ]


def of(document: Document, home) -> Comparison | None:
    if isinstance(home, incidents.Incident):
        return document.comparisons.filter(incident=home).first()
    if _is_case(home):
        return document.comparisons.filter(case=home).first()
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
        # Every older one, not the first found (v1.131.0); a case row's
        # children go with it.
        if _is_case(home):
            document.comparisons.filter(case=home).delete()
        else:
            document.comparisons.filter(
                incident=home if isinstance(home, incidents.Incident) else None,
                recording=home if not isinstance(home, incidents.Incident) else None,
                parent__isnull=True,
            ).delete()
    if isinstance(home, incidents.Incident):
        fields = {"incident": home}
    elif _is_case(home):
        fields = {"case": home}
    else:
        fields = {"recording": home}
    comparison = Comparison.objects.create(
        document=document,
        asked_by=by,
        expectation=expectation.note("compare_report", _size_of(document, home)),
        **fields,
    )
    from core import tasks

    if _is_case(home):
        tasks.compare_report_case.defer(comparison_id=str(comparison.pk))
    else:
        tasks.compare_report.defer(comparison_id=str(comparison.pk))
    return comparison


# The reading --------------------------------------------------------------------------


def _size_of(document: Document, home) -> int:
    """What the comparison is given, in tokens (v1.95.0): the record once per
    window of pages, and the pages themselves."""
    from core import sitting

    windows = _paragraph_windows(document)
    if _is_case(home):
        # Every recording read in turn (v1.170.0): the sum of their readings.
        return sum(_size_of(document, one) for one in _readable(home))
    if isinstance(home, incidents.Incident):
        record = sitting.record_tokens(home)
    else:
        record = assistant.reading_size(getattr(home, "transcript", None))
    pages = sum(prompts.tokens(_paragraph_lines(one)) for one in windows)
    # Read in one window when the whole report fits beside the record
    # (v1.134.0), the templates allowed for at SIZE_TEMPLATES_ALLOWANCE.
    one_window = (
        record + pages + assistant.cap(answer_cap()) + SIZE_TEMPLATES_ALLOWANCE
        <= assistant.window()
    )
    return (1 if one_window else len(windows)) * record + pages


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


def _one_window_if_it_fits(windows: list[list[dict]], fits) -> list[list[dict]]:
    """The report's windows of pages as one window when the whole report fits
    beside the record (v1.134.0); `fits` is given the rows and says. The
    windows as they were otherwise."""
    if len(windows) <= 1:
        return windows
    whole = [row for window in windows for row in window]
    return [whole] if fits(whole) else windows


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
            "rows": record["rows"],
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
TWIN_MOMENT = "same moment told twice"
SHOWN_NOTHING = "nothing"
# What a finding turns on (v1.103.0). A finding that turns on one of these
# alone is dropped and counted: a vision model's colours, makes and counts
# are impressions, and wording is not a fact.
TRIVIAL_KINDS = ("colour", "size", "make", "count", "wording")


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
    basis = str(item.get("basis", "")).strip().lower()
    why = " ".join(str(item.get("why", "")).split())[:WHY_MOST]
    # The record agrees only on the picture or a civilian's words (v1.90.1):
    # an agrees the model rests on an officer's words alone, or on nothing,
    # is not on camera, and the why says so.
    if mark == AGREES and basis in ("officer", "none"):
        mark = NOT_ON_CAMERA
        said = (
            "An officer's words alone: "
            if basis == "officer"
            else "Nothing on the record: "
        )
        why = (said + why)[:WHY_MOST]
    shown = str(item.get("shown", "")).strip().lower()
    kind = str(item.get("kind", "")).strip().lower()
    # Differences alone are narrowed (v1.103.1): a claim not on camera, an
    # agreement and an omission are findings whatever they turn on.
    if mark == DIFFERS and kind in TRIVIAL_KINDS:
        return None, f"on {kind} alone"
    if mark == DIFFERS and shown == SHOWN_NOTHING:
        mark = NOT_ON_CAMERA
        why = ("Nothing on the record shows otherwise: " + why)[:WHY_MOST]
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
    if mark == DIFFERS:
        # One difference per paragraph and moment (v1.103.0): a second on
        # the same picture at the same second is the same finding told twice.
        moment = (DIFFERS, page, n, at)
        if moment in taken:
            return None, TWIN_MOMENT
        taken.add(moment)
    return {
        "id": uuid.uuid4().hex[:12],
        "mark": mark,
        "page": page,
        "n": n,
        "paragraph": paragraph,
        "claim": claim,
        "at": at,
        "basis": basis,
        "kind": kind,
        "why": why,
        "dismissed": False,
        "note": "",
        "note_id": "",
    }, ""


# The check against the record's lines (v1.104.0) -------------------------------
# The lines within this many seconds of a moment a finding cites, the most
# moments, lines a moment and lines a finding; the findings one call checks;
# and the readings each finding gets. The app acts only where the readings
# agree, as the clock's read does.
CHECK_NEAR = 15.0
CHECK_TIMES = 4
CHECK_LINES_A_TIME = 12
CHECK_LINES_A_FINDING = 30
CHECK_BATCH = 20
CHECK_READINGS = 2
# What a difference may not rest on alone. From the picture, a colour, a
# make, a size or a count is a vision model's impression; said by a person,
# a number is a fact (three orders against one is a difference). Spelling
# and wording are never a difference, whoever they come from.
PICTURE_TRIVIA = ("colour", "make", "size", "count")
ANY_TRIVIA = ("spelling", "wording")
LACKS = "lacks"
OFFICER = "officer"
DROP = "drop:"


def _record_rows(against: dict) -> list[tuple[float, str]]:
    """The record as (seconds, line): an incident's rows on its clock, or a
    recording's lines by the first time each carries."""
    if against.get("rows") is not None:
        return [(at, f"{name}: {line}") for at, name, line in against["rows"]]
    rows: list[tuple[float, str]] = []
    at = 0.0
    for line in against["record"].splitlines():
        found = STAMP.search(line)
        if found:
            hours, minutes, seconds = (int(part) for part in found.groups())
            at = float(hours * 3600 + minutes * 60 + seconds)
        if line.strip():
            rows.append((at, line))
    return rows


def _check_lines(comparison: Comparison, rows: list, finding: dict) -> list[str]:
    """The record's lines at the moments a finding cites: its own moment and
    every time its why names."""
    times: list[float] = []
    if finding.get("at") is not None:
        times.append(float(finding["at"]))
    for stamp in STAMP.finditer(finding.get("why") or ""):
        at = _seconds_of(comparison, stamp.group(0))
        if at is not None and all(abs(at - other) > CHECK_NEAR for other in times):
            times.append(at)
    picked: list[tuple[float, str]] = []
    for at in times[:CHECK_TIMES]:
        near = [row for row in rows if abs(row[0] - at) <= CHECK_NEAR]
        near.sort(key=lambda row, at=at: abs(row[0] - at))
        picked.extend(near[:CHECK_LINES_A_TIME])
    seen: set[str] = set()
    lines: list[str] = []
    for _, line in sorted(picked, key=lambda row: row[0]):
        if line not in seen:
            seen.add(line)
            lines.append(line)
    return lines[:CHECK_LINES_A_FINDING]


def _verdict(mark: str, check: dict) -> str:
    """What one reading says to do with one finding: DROP and the reason,
    LACKS or OFFICER to move it to not on camera, or nothing."""
    record = check.get("record", "")
    source = check.get("source", "")
    but_for = check.get("but_for", "")
    if mark == DIFFERS:
        if but_for in ANY_TRIVIA or (but_for in PICTURE_TRIVIA and source == "picture"):
            return f"{DROP}on {but_for} alone"
        return LACKS if record == LACKS else ""
    if record == LACKS:
        return LACKS
    return OFFICER if source == OFFICER else ""


def _parse_checks(text: str) -> dict[int, dict]:
    text = _unfenced(text)
    try:
        parsed = json.loads(text)
    except ValueError:
        parsed = json.loads(prompts.salvage_json(text))
    raw = parsed.get("checks", []) if isinstance(parsed, dict) else parsed
    if not isinstance(raw, list):
        raise ValueError("not a list")
    checks: dict[int, dict] = {}
    for one in raw:
        if not isinstance(one, dict):
            continue
        try:
            number = int(one.get("n"))
        except (TypeError, ValueError):
            continue
        checks[number] = {
            key: str(one.get(key, "")).strip().lower()
            for key in ("record", "source", "but_for")
        }
    return checks


def _check(
    comparison: Comparison,
    findings: list[dict],
    against: dict,
    ground_text: str,
    cap: int,
    usage: dict,
    drop,
) -> tuple[list[dict], dict]:
    """The Agrees and Differs rows read again beside the record's lines, twice;
    where both readings say the same, the app acts: a difference that rests
    on trivia is dropped, a row whose lines lack the thing or hold it only
    in an officer's words is not on camera. A reading that fails changes
    nothing: the findings stand as written."""
    judged = [one for one in findings if one["mark"] in (AGREES, DIFFERS)]
    summary = {
        "rows": len(judged),
        "moved": 0,
        "dropped": 0,
        "apart": 0,
        "unread": 0,
        "calls": 0,
    }
    if not judged:
        return findings, summary
    rows = _record_rows(against)
    system = prompts.system_message(
        ground_text, prompts.COMPARISON_CHECK, prompts.COMPARISON_CHECK_FORMAT
    )
    said: dict[str, list[str]] = {}
    for start in range(0, len(judged), CHECK_BATCH):
        batch = judged[start : start + CHECK_BATCH]
        user = prompts.comparison_check_input(
            [
                {
                    "claim": one["claim"],
                    "mark": one["mark"],
                    "why": one["why"],
                    "lines": _check_lines(comparison, rows, one),
                }
                for one in batch
            ]
        )
        if not prompts.fits(system, user, answer_cap=cap, window=assistant.window()):
            continue
        for _ in range(CHECK_READINGS):
            try:
                answer = engine.complete(
                    assistant._messages(system, user),
                    max_completion_tokens=cap,
                    thinking=assistant.thinking(),
                    timeout=assistant.time_limit(FEATURE),
                    **assistant.SAMPLING,
                )
            except engine.Problem as problem:
                log.warning(
                    "comparison %s: a check could not be asked (%s)",
                    comparison.pk,
                    problem.reason,
                )
                continue
            summary["calls"] += 1
            usage["input_tokens"] += answer.get("input_tokens", 0) or 0
            usage["output_tokens"] += answer.get("output_tokens", 0) or 0
            try:
                checks = _parse_checks(answer.get("text") or "")
            except (ValueError, AttributeError):
                log.warning(
                    "comparison %s: a check was unreadable (%d chars, finish %s)",
                    comparison.pk,
                    len(answer.get("text") or ""),
                    answer.get("finish_reason"),
                )
                continue
            for number, one in enumerate(batch, start=1):
                if number in checks:
                    said.setdefault(one["id"], []).append(
                        _verdict(one["mark"], checks[number])
                    )
    kept: list[dict] = []
    for one in findings:
        if one["mark"] not in (AGREES, DIFFERS):
            kept.append(one)
            continue
        verdicts = said.get(one["id"], [])
        if len(verdicts) < CHECK_READINGS:
            summary["unread"] += 1
            kept.append(one)
            continue
        if len(set(verdicts)) > 1:
            summary["apart"] += 1
            kept.append(one)
            continue
        verdict = verdicts[0]
        if verdict.startswith(DROP):
            drop(verdict[len(DROP) :])
            summary["dropped"] += 1
            continue
        if verdict == LACKS:
            lead = (
                "Nothing on the record shows otherwise: "
                if one["mark"] == DIFFERS
                else "Nothing on the record: "
            )
            one = {**one, "mark": NOT_ON_CAMERA, "why": (lead + one["why"])[:WHY_MOST]}
            summary["moved"] += 1
        elif verdict == OFFICER:
            one = {
                **one,
                "mark": NOT_ON_CAMERA,
                "basis": OFFICER,
                "why": ("An officer's words alone: " + one["why"])[:WHY_MOST],
            }
            summary["moved"] += 1
        kept.append(one)
    return kept, summary


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
    comparison.expectation = expectation.started(comparison.expectation)
    comparison.save(
        update_fields=[
            "state",
            "stage",
            "template_version",
            "ground_rules_version",
            "expectation",
        ]
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
        # The whole report in one window when it fits beside the record
        # (v1.134.0): the record was sent once per eight pages, whatever
        # the room. Eight-page windows only when the whole does not fit.
        windows = _one_window_if_it_fits(
            windows,
            lambda rows: prompts.fits(
                system,
                prompts.comparison_input(
                    against["head"],
                    against["events"],
                    against["record"],
                    _paragraph_lines(rows),
                    first=rows[0]["page"],
                    last=rows[-1]["page"],
                ),
                answer_cap=cap,
                window=assistant.window(),
            ),
        )
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
                against["head"],
                against["events"],
                whole,
                most=settings_store.compare_left_out_most(),
            )
            # The omissions answer in a format of their own (v1.103.1).
            system_left = prompts.system_message(
                ground.text,
                template.text,
                prompts.COMPARISON_LEFT_OUT_FORMAT + "\n\n" + prompts.INCIDENT_RULES,
            )
            if prompts.fits(
                system_left, user, answer_cap=cap, window=assistant.window()
            ):
                answer = engine.complete(
                    assistant._messages(system_left, user),
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
                        # Everything this pass names is an omission; a mark
                        # left off is not a reason to lose it.
                        if isinstance(item, dict) and not item.get("mark"):
                            item = {**item, "mark": NOT_IN_REPORT}
                        one, why = _keep_or_why(comparison, item, known, taken)
                        if one is None:
                            drop(why)
                        elif one["mark"] == NOT_IN_REPORT:
                            findings.append(one)
                except (ValueError, AttributeError):
                    # The size and the first characters, never the words
                    # (v1.103.1): the next unreadable answer can be told
                    # from a cut one or a refusal.
                    log.warning(
                        "comparison %s: the left-out answer was unreadable "
                        "(%d chars, starts %r, finish %s)",
                        comparison.pk,
                        len(answer.get("text") or ""),
                        (answer.get("text") or "")[:12],
                        answer.get("finish_reason"),
                    )
                    unreadable += 1
            else:
                left_out_check = True
        # The check against the record's lines (v1.104.0), once everything
        # is written: a reading that fails changes nothing.
        comparison.stage = "Checking the findings against the record"
        comparison.save(update_fields=["stage"])
        findings, second_look = _check(
            comparison, findings, against, ground.text, cap, usage, drop
        )
        calls += second_look["calls"]
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
        comparison.second_look = second_look
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
            checked=second_look["rows"],
            moved=second_look["moved"],
            **expectation.for_audit(comparison.expectation),
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
            **expectation.for_audit(comparison.expectation),
        )


# The case as the home (Phase 10 chapter 4, v1.170.0) -----------------------------


def compare_for_case(comparison_id, attempt: int = 1) -> None:
    """One run per recording, in turn: each a child comparison of the parent
    row, read as a recording's comparison reads a transcript and its Digest,
    since one record of a whole case does not fit a call. The parent says
    how far it has got, and when every child is done holds their findings
    merged, each naming its recording, by day and time on the case's clock."""
    parent = (
        Comparison.objects.filter(pk=comparison_id, case__isnull=False)
        .select_related("document", "document__case", "case", "asked_by")
        .first()
    )
    if parent is None or parent.state not in (QUEUED, RUNNING):
        return
    document = parent.document
    recordings = _readable(parent.case)
    parent.state = RUNNING
    parent.stage = f"Reading recording 1 of {len(recordings)}"
    parent.expectation = expectation.started(parent.expectation)
    parent.save(update_fields=["state", "stage", "expectation"])
    read = 0
    failed = ""
    for number, recording in enumerate(recordings, 1):
        if not Comparison.objects.filter(pk=parent.pk).exists():
            return
        child = Comparison.objects.create(
            document=document,
            recording=recording,
            parent=parent,
            asked_by=parent.asked_by,
            expectation=expectation.note(
                "compare_report", _size_of(document, recording)
            ),
        )
        compare(child.pk)
        child.refresh_from_db()
        if child.state == DONE:
            read += 1
        else:
            failed = child.reason_class or failed
        Comparison.objects.filter(pk=parent.pk).update(
            stage=f"Read {number} of {len(recordings)} recordings"
        )
    parent.refresh_from_db()
    if not read:
        parent.state = FAILED
        parent.stage = ""
        parent.reason_class = failed or engine.ERROR
        parent.save(update_fields=["state", "stage", "reason_class"])
        return
    _merge(parent)
    parent.cameras_used = [
        _recording_words(child.recording)
        for child in parent.children.filter(state=DONE)
        .order_by("created")
        .select_related("recording")
    ]
    parent.windows = max((child.windows for child in parent.children.all()), default=0)
    parent.cut_short = sum(child.cut_short for child in parent.children.all())
    parent.record_lines = sum(child.record_lines for child in parent.children.all())
    parent.stage = ""
    parent.state = DONE
    parent.reason_class = ""
    parent.written_at = timezone.now()
    parent.save()
    counts = parent.counts()
    audit.write(
        audit.Category.CASES,
        "Comparison run",
        actor=parent.asked_by,
        affected_user=(
            document.case.owner
            if parent.asked_by is not None
            and document.case.owner_id != parent.asked_by.pk
            else None
        ),
        object_type="document",
        object_id=document.pk,
        object_label=document.title,
        whole_case=True,
        recordings=len(recordings),
        read=read,
        findings=len(parent.findings),
        **{mark: counts[mark] for mark in MARKS},
    )


def _recording_words(recording) -> str:
    return str((recording.stamp or {}).get("camera") or recording.title)


def _merge(parent: Comparison) -> None:
    """The children's findings as one list on the parent: each id the
    child's and the finding's joined, the recording named, the moment as
    the case's clock has it, in day and time order with the recordings' own
    order inside a moment; a Not on camera finding first on its recording."""
    from core import case_chronology, exports

    rows = []
    for child in (
        parent.children.filter(state=DONE)
        .order_by("created")
        .select_related("recording")
    ):
        recording = child.recording
        name = _recording_words(recording)
        date, start, how = case_chronology.clock_of(recording)
        for one in child.findings:
            at = one.get("at")
            # The key: the day, the moment on the case's clock, then the
            # recording; a finding with no moment sorts at its recording's
            # start, before its timed ones.
            day = date or dt.date.max
            if at is None:
                key = (day, start or 0.0, -1, name)
                clock = ""
            elif date is not None and start is not None:
                key = (day, start + float(at), 0, name)
                clock = (
                    f"{case_chronology.day_words(date)} "
                    f"{case_chronology.hms(start + float(at))}"
                )
            elif date is not None:
                key = (day, float(at), 0, name)
                clock = (
                    f"{case_chronology.day_words(date)} · "
                    f"{exports.clock(float(at))} into {name}"
                )
            else:
                key = (day, float(at), 0, name)
                clock = f"{exports.clock(float(at))} into {name}"
            rows.append(
                (
                    key,
                    {
                        **one,
                        "id": f"{child.pk}:{one['id']}",
                        "recording": name,
                        "recording_id": str(recording.pk),
                        "child": str(child.pk),
                        "clock_words": clock,
                    },
                )
            )
    rows.sort(key=lambda row: row[0])
    parent.findings = [row[1] for row in rows]
    parent.save(update_fields=["findings"])


def _resolve(parent: Comparison, finding_id: str):
    """A merged finding's child comparison and its own id there."""
    child_id, _, own = str(finding_id).partition(":")
    if not own:
        return None, ""
    try:
        uuid.UUID(child_id)
    except ValueError:
        return None, ""
    child = parent.children.filter(pk=child_id).first()
    return child, own


def not_yet_compared(parent: Comparison) -> int:
    """Recordings with a transcript the case run has not read: landed since."""
    if not parent.case_id:
        return 0
    read = set(parent.children.values_list("recording_id", flat=True))
    return sum(1 for one in _readable(parent.case) if one.pk not in read)


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


def second_look_words(comparison: Comparison) -> str:
    """ "; 6 findings checked against the record's lines, 4 moved to not on
    camera, 1 dropped; 1 left as written where the two checks differed", or
    nothing for a comparison written before the check (v1.104.0)."""
    look = comparison.second_look or {}
    rows = int(look.get("rows") or 0)
    if not rows:
        return ""
    unread = int(look.get("unread") or 0)
    if unread >= rows:
        return "; the findings could not be checked against the record's lines"
    words = (
        f"; {rows} finding{'' if rows == 1 else 's'} checked against the record's lines"
    )
    if look.get("moved"):
        words += f", {look['moved']} moved to not on camera"
    if look.get("dropped"):
        words += f", {look['dropped']} dropped"
    if look.get("apart"):
        words += f"; {look['apart']} left as written where the two checks differed"
    if unread:
        words += f"; {unread} could not be checked"
    return words


def stale_words(comparison: Comparison) -> str:
    if comparison.state == DONE and comparison.case_id:
        left = not_yet_compared(comparison)
        return (
            f"{left} recording{'' if left == 1 else 's'} landed since and "
            "not yet compared"
            if left
            else ""
        )
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
        "home": (
            "incident"
            if isinstance(home, incidents.Incident)
            else ("case" if _is_case(home) else "recording")
        ),
        "home_id": str(home.pk),
        "can_make_note": True,
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
    elif comparison.state == DONE and comparison.case_id:
        counts = comparison.counts()
        when = (
            timezone.localtime(comparison.written_at).strftime("%H:%M")
            if comparison.written_at
            else ""
        )
        read = len(comparison.cameras_used)
        words = (
            f"{document.pages} pages against {read} "
            f"{'recording' if read == 1 else 'recordings'}, read one at a time; "
            + counts_words(counts)
            + (f"; written at {when}" if when else "")
            + (
                f"; {comparison.cut_short} answer"
                f"{'' if comparison.cut_short == 1 else 's'} cut short, "
                "raise the Comparison answer cap"
                if comparison.cut_short
                else ""
            )
        )
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
            + second_look_words(comparison)
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
                "clock": (
                    one.get("clock_words", "")
                    if comparison.case_id
                    else clock_words(comparison, one.get("at"))
                ),
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


def _on_child(comparison: Comparison, finding_id: str, act):
    """An act on a case row's finding: done on the child's own, then merged."""
    child, own = _resolve(comparison, finding_id)
    if child is None:
        return None
    out = act(child, own)
    _merge(comparison)
    return out


def set_dismissed(comparison: Comparison, finding_id: str, dismissed: bool) -> bool:
    if comparison.case_id:
        return bool(
            _on_child(
                comparison,
                finding_id,
                lambda child, own: set_dismissed(child, own, dismissed),
            )
        )
    one = _finding(comparison, finding_id)
    if one is None:
        return False
    one["dismissed"] = dismissed
    comparison.save(update_fields=["findings"])
    return True


def set_note(comparison: Comparison, finding_id: str, note: str) -> bool:
    if comparison.case_id:
        return bool(
            _on_child(
                comparison, finding_id, lambda child, own: set_note(child, own, note)
            )
        )
    one = _finding(comparison, finding_id)
    if one is None:
        return False
    one["note"] = " ".join(str(note or "").split())[:2000]
    comparison.save(update_fields=["findings"])
    return True


def make_note(comparison: Comparison, finding_id: str, *, at=None, by, request=None):
    """Make it a note (Phase 10 chapter 4, v1.168.0): the claim becomes a note
    on the recording at the moment, in the person's name, saying it came
    from the report, page and paragraph; on an incident the note goes on
    the camera running at the moment, the one with a line being spoken
    first. The chronology shows it as a note event resting on the paragraph."""
    if comparison.case_id:
        child, own = _resolve(comparison, finding_id)
        if child is None:
            raise ValueError("no such finding")
        home = make_note(child, own, at=at, by=by, request=request)
        _merge(comparison)
        return home
    one = _finding(comparison, finding_id)
    if one is None:
        raise ValueError("no such finding")
    if one.get("note_id"):
        return None
    moment = one.get("at") if at is None else at
    if moment is None:
        raise ValueError("Say the moment this note is at.")
    moment = float(moment)
    if comparison.incident_id:
        incident = comparison.incident
        running = [
            cam
            for cam in incident.cameras.select_related("recording")
            if str(cam.pk) in chronology.running_cameras(incident, moment)
        ]
        if not running:
            raise ValueError(
                "No camera runs at that moment, so there is no line to note."
            )
        from core import notes

        camera = next(
            (
                cam
                for cam in running
                if notes.spoken_at(
                    getattr(cam.recording, "transcript", None), moment - cam.starts_at
                )
                is not None
            ),
            running[0],
        )
        recording = camera.recording
        seconds = max(0.0, moment - camera.starts_at)
        where = camera.camera_id()
    else:
        recording = comparison.recording
        seconds = max(0.0, moment)
        where = recording.title or recording.original_filename
    rests = (
        f"[Report, page {one['page']}, paragraph {one['n']}] {one['paragraph']}"
        if one.get("page")
        else ""
    )
    why = MARK_WORDS.get(one["mark"], "") + (
        f": {one['why']}" if one.get("why") else ""
    )
    origin = {
        "kind": "finding",
        "source": "report",
        "why": why,
        "rests_on": rests,
        "comparison": str(comparison.pk),
        "finding": one["id"],
        "words": proposals.origin_words("report", page=one.get("page"), n=one.get("n")),
    }
    kind, home = proposals.write_note(
        recording, seconds, one["claim"], origin=origin, by=by, request=request
    )
    one["note_id"] = str(home.pk)
    one["note_kind"] = kind
    one["note_on"] = where
    comparison.save(update_fields=["findings"])
    return home


# The export ---------------------------------------------------------------------------


def word(comparison: Comparison, exported_by: str) -> bytes:
    """Comparison to Word: the cover, then one table of the findings."""
    import io

    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt

    from core import exports

    document = comparison.document
    home = comparison.home()
    home_name = (
        home.name if (comparison.incident_id or comparison.case_id) else home.title
    )
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
                (
                    f"the case {home_name}, every recording with a transcript"
                    if comparison.case_id
                    else f"{'Incident' if comparison.incident_id else 'Recording'} "
                    f"{home_name}"
                ),
            ),
            (
                "Recordings" if comparison.case_id else "Cameras",
                ", ".join(comparison.cameras_used) or "none",
            ),
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
    whole = bool(comparison.case_id)
    table = doc.add_table(rows=1, cols=7 if whole else 6)
    table.style = "Light Grid Accent 1"
    titles = ("Mark", "Paragraph", "Claim", "Moment", "Why", "Note")
    if whole:
        titles = ("Mark", "Recording", "Paragraph", "Claim", "Moment", "Why", "Note")
    for cell, title in zip(table.rows[0].cells, titles, strict=True):
        cell.text = title
    for one in comparison.findings:
        cells = list(table.add_row().cells)
        cells[0].text = MARK_WORDS.get(one["mark"], one["mark"]) + (
            " (dismissed)" if one.get("dismissed") else ""
        )
        if whole:
            cells[1].text = one.get("recording", "")
            cells = [cells[0]] + cells[2:]
        cells[1].text = (
            f"Page {one['page']}, paragraph {one['n']}: {one['paragraph']}"
            if one.get("page")
            else ""
        )
        cells[2].text = one["claim"]
        cells[3].text = (
            one.get("clock_words", "")
            if whole
            else clock_words(comparison, one.get("at"))
        )
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
