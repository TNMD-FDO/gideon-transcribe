"""Usage: how much the office uses the app (Phase 13 chapter 3, v1.239.0).

One row a month of numbers, counted each night from what the app already
keeps (the Jobs, the Recordings and the audit log) and kept for the life of
the install, so sweeping a Case or the audit log does not change history.
Counts only: never a Recording's name, a Case's name, a word that was said,
a question that was asked, or who did anything. The Panel's Usage page is
drawn from these rows and nothing else.

Two rules the counting keeps. A count never goes down: a month is counted
again each night until it and the month after it have ended, and where a
later count is lower (a Case was swept in between) the higher figure stands.
And a month that had already ended when it was first counted is told apart
on the page, because it could only be counted from what the server still
held that day.
"""

from __future__ import annotations

import logging
import shutil
from datetime import date, datetime, time, timedelta
from statistics import median

from django.conf import settings
from django.db import models
from django.db.models import Count, Min, Q, Sum
from django.db.models.fields.json import KeyTextTransform
from django.utils import timezone

from core import audit

log = logging.getLogger("transcribe.usage")

# A first count never reaches further back than this many months.
FIRST_COUNT_MONTHS = 36
# The page's chart, and its middle period.
YEAR = 12

MONTH = "month"
TWELVE = "year"
ALL = "all"
PERIODS = (
    (MONTH, "This month"),
    (TWELVE, "Last 12 months"),
    (ALL, "Since the install"),
)


class UsageMonth(models.Model):
    """One month's numbers. `month` is its first day, in the office's time."""

    month = models.DateField(unique=True)
    counts = models.JSONField(default=dict)
    first_counted = models.DateTimeField(default=timezone.now)
    counted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["month"]

    def __str__(self) -> str:
        return f"{self.month:%Y-%m}"


class UsageMark(models.Model):
    """That a person used a part of the app this month, for the parts that
    write no audit row (a search, the Map). Kept only until the month after
    has ended: by then the month's count is final and the marks are deleted,
    so what stays is the number and never who."""

    month = models.DateField()
    part = models.CharField(max_length=20)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["month", "part", "user"], name="usage_mark_once_a_month"
            )
        ]


# The parts of the app the page counts people for: the key, the words on the
# page, and the audit rows that show a person used it (None where the app
# writes no row, and a mark is kept instead).
CHAT_FEATURES = (
    "chat_turn",
    "incident_chat",
    "case_chat_turn",
    "case_chat_two_pass",
    "case_chat_files",
)
SEARCH = "search"
MAP = "map"
BULK = "bulk"
PARTS = (
    (
        "notes",
        "Notes",
        Q(
            category=audit.Category.EDITS,
            event__in=(
                "Note added",
                "Note changed",
                "Note removed",
                "note marked to check",
            ),
        ),
    ),
    (SEARCH, "Search in a case", None),
    (
        "chat",
        "Chat",
        Q(category=audit.Category.LLM, details__feature__in=CHAT_FEATURES),
    ),
    ("clips", "Clips", Q(category=audit.Category.CLIPS)),
    ("exports", "Exports", Q(category=audit.Category.EXPORTS)),
    (
        "speakers",
        "Naming speakers",
        Q(category=audit.Category.EDITS, event__startswith="Speaker"),
    ),
    (
        "corrections",
        "Corrections",
        Q(
            category=audit.Category.EDITS,
            event__in=("Segment corrected", "Line split at a word"),
        ),
    ),
    (
        "incidents",
        "Incidents",
        Q(
            event__in=(
                "incident made",
                "incident changed",
                "camera placed",
                "Camera pinned",
                "recording placed on the clock",
            )
        ),
    ),
    (MAP, "Map", None),
    ("comparison", "Comparison", Q(event="Comparison run")),
    ("sharing", "Sharing", Q(event="Share granted")),
    ("dictation", "Dictation", Q(event="Dictation sent")),
    ("live", "Live recording", Q(event="Live recording started")),
    (BULK, "Bulk transcription", None),
)
MARKED = tuple(key for key, _words, rows in PARTS if rows is None)

# The AI assistant's work, by the audit row's feature.
AI = (
    ("chat", "Chat questions", CHAT_FEATURES),
    ("summary", "Summaries written", ("summary",)),
    ("speaker_check", "Speaker checks", ("speaker_check",)),
    ("proposals", "Proposed events runs", ("incident_events",)),
    ("memo", "Incident memos", ("incident_memo",)),
    ("comparison", "Comparisons", ("compare_report",)),
    ("translation", "Translations", ("translation",)),
)
AI_OTHER = ("other", "Other")
# Why an AI assistant call failed, in the page's words.
REASON_WORDS = {
    "llm_unreachable": "the engine could not be reached",
    "llm_timeout": "the engine took too long",
    "llm_refused": "the engine refused",
    "llm_too_long": "too long for the engine",
    "llm_bad_output": "an answer the app could not use",
    "llm_error": "an engine error",
    "llm_no_vision": "an engine that takes no video",
}

# Figures that are a level on the day of the count, not a count of the month:
# the newest stands, and only the month being lived in sets them.
LEVELS = ("disk_held", "disk_free", "disk_total", "accounts")
# A typical figure and the count it was worked out from: the one worked out
# from more stands.
TYPICALS = {"wait_typical": "waits", "chat_typical": "chat_timed"}


# Months ------------------------------------------------------------------------


def month_of(day: date) -> date:
    return day.replace(day=1)


def after(month: date) -> date:
    return (month.replace(day=28) + timedelta(days=4)).replace(day=1)


def before(month: date) -> date:
    return (month - timedelta(days=1)).replace(day=1)


def span(month: date) -> tuple[datetime, datetime]:
    """The month's first instant and the next month's, in the office's time."""
    zone = timezone.get_current_timezone()
    return (
        timezone.make_aware(datetime.combine(month, time.min), zone),
        timezone.make_aware(datetime.combine(after(month), time.min), zone),
    )


def this_month() -> date:
    return month_of(timezone.localdate())


# The marks ---------------------------------------------------------------------


def seen(user, part: str) -> None:
    """Remember that this person used a part this month. One small row, and
    never a reason for a page to fail."""
    if not getattr(user, "is_authenticated", False) or part not in MARKED:
        return
    try:
        UsageMark.objects.bulk_create(
            [UsageMark(month=this_month(), part=part, user=user)],
            ignore_conflicts=True,
        )
    except Exception:  # noqa: BLE001 - a count is never worth a broken page
        log.exception("a usage mark was not kept")


# Counting ----------------------------------------------------------------------


def count(month: date) -> dict:
    """The month's numbers, from what the server holds now."""
    from core.jobs import Job, JobState
    from core.models import User
    from core.recordings import Recording

    start, end = span(month)
    counts: dict = {}

    # What was transcribed: each Recording once, however often it was run.
    jobs = (
        Job.objects.filter(
            kind="", state=JobState.DONE, finished__gte=start, finished__lt=end
        )
        .select_related("recording", "recording__transcript")
        .order_by("finished")
    )
    recordings: dict = {}
    waits: list[float] = []
    for job in jobs.iterator(chunk_size=500):
        recordings[job.recording_id] = job.recording
        if job.created and job.finished and job.finished >= job.created:
            waits.append((job.finished - job.created).total_seconds())
    types: dict[str, float] = {}
    languages: dict[str, float] = {}
    seconds = translated = 0.0
    for recording in recordings.values():
        length = float(recording.duration_seconds or 0)
        seconds += length
        kind = (recording.recording_type or "").strip()
        types[kind] = types.get(kind, 0.0) + length
        transcript = getattr(recording, "transcript", None)
        language = (getattr(transcript, "language", "") or "").strip().lower()
        if language:
            languages[language] = languages.get(language, 0.0) + length
        if recording.translate:
            translated += length
    counts["recordings"] = len(recordings)
    counts["seconds"] = round(seconds)
    counts["types"] = {key: round(value) for key, value in types.items()}
    counts["languages"] = {key: round(value) for key, value in languages.items()}
    counts["translated_seconds"] = round(translated)
    counts["waits"] = len(waits)
    if waits:
        counts["wait_typical"] = round(median(waits))
        counts["wait_longest"] = round(max(waits))

    rows = audit.Row.objects.filter(at__gte=start, at__lt=end)
    people = rows.filter(actor_kind="user").exclude(actor_user_id=None)
    counts["people"] = people.values("actor_user_id").distinct().count()

    # The cases worked on: one named on a row, or holding a Recording named on one.
    cases = set(
        people.filter(object_type="case").values_list("object_id", flat=True).distinct()
    )
    touched = [
        value
        for value in people.filter(object_type="recording")
        .values_list("object_id", flat=True)
        .distinct()
        if value
    ]
    for at in range(0, len(touched), 500):
        cases.update(
            str(value)
            for value in Recording.objects.filter(pk__in=touched[at : at + 500])
            .exclude(case=None)
            .values_list("case_id", flat=True)
        )
    cases.discard("")
    counts["cases"] = len(cases)
    counts["cases_opened"] = rows.filter(event="case created").count()

    # Who used which part: the audit rows, and the marks where there are none.
    parts: dict[str, int] = {}
    for key, _words, told in PARTS:
        if told is None:
            parts[key] = (
                UsageMark.objects.filter(month=month, part=key)
                .values("user_id")
                .distinct()
                .count()
            )
        else:
            parts[key] = people.filter(told).values("actor_user_id").distinct().count()
    counts["parts"] = parts

    # The AI assistant, by feature and outcome.
    calls = rows.filter(category=audit.Category.LLM, event="AI assistant call")
    group_of = {feature: key for key, _words, features in AI for feature in features}
    asked: dict[str, int] = {}
    failed = 0
    for row in (
        calls.annotate(feature=KeyTextTransform("feature", "details"))
        .values("feature", "outcome")
        .annotate(n=Count("id"))
    ):
        key = group_of.get(row["feature"] or "", AI_OTHER[0])
        asked[key] = asked.get(key, 0) + row["n"]
        if row["outcome"] != audit.Outcome.SUCCESS:
            failed += row["n"]
    counts["ai"] = asked
    counts["ai_failed"] = failed
    counts["ai_reasons"] = {
        row["reason_class"]: row["n"]
        for row in calls.exclude(outcome=audit.Outcome.SUCCESS)
        .exclude(reason_class="")
        .values("reason_class")
        .annotate(n=Count("id"))
    }
    took = []
    for value in (
        calls.filter(outcome=audit.Outcome.SUCCESS, details__feature__in=CHAT_FEATURES)
        .annotate(took=KeyTextTransform("duration_seconds", "details"))
        .values_list("took", flat=True)
    ):
        try:
            took.append(float(value))
        except (TypeError, ValueError):
            continue
    counts["chat_timed"] = len(took)
    if took:
        counts["chat_typical"] = round(median(took))

    counts["uploads"] = rows.filter(event="upload accepted").count()
    counts["refused"] = rows.filter(event="upload rejected").count()
    counts["jobs_failed"] = rows.filter(event="Job failed").count()

    # The levels, only for the month being lived in.
    if month == this_month():
        held = Recording.objects.aggregate(n=Sum("on_disk_bytes"))["n"] or 0
        counts["disk_held"] = int(held)
        try:
            disk = shutil.disk_usage(settings.DATA_DIR)
            counts["disk_free"] = int(disk.free)
            counts["disk_total"] = int(disk.total)
        except OSError:
            log.warning("the data folder's drive could not be measured")
        counts["accounts"] = User.objects.filter(
            deactivated_at=None, blocked_at=None
        ).count()
    return counts


def merged(old: dict, new: dict) -> dict:
    """The stored numbers and a fresh count, as one: a count never goes down,
    a level is the newest, and a typical figure is the one worked out from more."""
    out = dict(old)
    for key, value in new.items():
        if key in LEVELS or key in TYPICALS:
            continue
        was = old.get(key)
        if isinstance(value, dict):
            was = was if isinstance(was, dict) else {}
            out[key] = {
                name: max(value.get(name, 0), was.get(name, 0))
                for name in {*value, *was}
            }
        else:
            out[key] = max(value, was or 0)
    for key in LEVELS:
        if key in new:
            out[key] = new[key]
    for key, basis in TYPICALS.items():
        if key in new and new.get(basis, 0) >= (old.get(basis) or 0):
            out[key] = new[key]
    return out


def _earliest() -> date | None:
    """The first month the server holds anything of."""
    from core.jobs import Job

    firsts = [
        audit.Row.objects.aggregate(n=Min("at"))["n"],
        Job.objects.exclude(finished=None).aggregate(n=Min("finished"))["n"],
    ]
    firsts = [timezone.localtime(value).date() for value in firsts if value]
    return month_of(min(firsts)) if firsts else None


def tally() -> dict:
    """The nightly step. The month being lived in and the one before it are
    counted again; on the first night every month the server still holds
    anything of is counted once. Marks older than last month are deleted."""
    now = timezone.now()
    current = this_month()
    last = before(current)
    months = [last, current]
    if not UsageMonth.objects.exists():
        first = _earliest()
        floor = current
        for _ in range(FIRST_COUNT_MONTHS):
            floor = before(floor)
        month = max(first, floor) if first else current
        months = []
        while month <= current:
            months.append(month)
            month = after(month)
    done = 0
    for month in months:
        fresh = count(month)
        row = UsageMonth.objects.filter(month=month).first()
        if row is None:
            # A month with nothing in it, before anything was ever counted,
            # is not a month of use.
            if month != current and not _anything(fresh):
                continue
            row = UsageMonth(month=month, first_counted=now, counts={})
        row.counts = merged(row.counts, fresh)
        row.counted_at = now
        row.save()
        done += 1
    swept, _ = UsageMark.objects.filter(month__lt=last).delete()
    log.info("usage counted: %s months, %s old marks removed", done, swept)
    return {"months": done, "marks_removed": swept}


def _anything(counts: dict) -> bool:
    return bool(
        counts.get("recordings")
        or counts.get("people")
        or counts.get("uploads")
        or sum((counts.get("ai") or {}).values())
    )


# The page ----------------------------------------------------------------------


def _number(value) -> str:
    return f"{int(round(value or 0)):,}"


def hours(seconds) -> str:
    value = (seconds or 0) / 3600
    if 0 < value < 10:
        return f"{value:.1f} h"
    return f"{_number(value)} h"


def length(seconds) -> str:
    """A wait, in the unit that suits it."""
    seconds = int(round(seconds or 0))
    if seconds < 90:
        return f"{seconds} s"
    minutes = round(seconds / 60)
    if minutes < 90:
        return f"{minutes} min"
    whole, rest = divmod(minutes, 60)
    if whole >= 48:
        return f"{round(minutes / 1440)} days"
    return f"{whole} h {rest} min" if rest else f"{whole} h"


def size(figure) -> str:
    figure = float(figure or 0)
    if figure >= 1024**4:
        return f"{figure / 1024**4:.1f} TB"
    if figure >= 1024**3:
        return f"{figure / 1024**3:.0f} GB"
    return f"{figure / 1024**2:.0f} MB"


def _share(part, whole) -> str:
    if not whole:
        return ""
    value = 100 * part / whole
    if 0 < value < 10:
        return f"{value:.1f}%"
    return f"{value:.0f}%"


def _people(n: int) -> str:
    return f"{_number(n)} {'person' if n == 1 else 'people'}"


def _bars(pairs, said) -> list[dict]:
    """Rows with a bar each, the longest full width."""
    most = max((value for _words, value in pairs), default=0)
    return [
        {
            "words": words,
            "figure": said(value),
            "width": round(100 * value / most) if most else 0,
            "quiet": bool(most) and value * 10 < most,
        }
        for words, value in pairs
    ]


def _language_name(code: str) -> str:
    from core import exports

    return exports.language_name(code)


def page(period: str = TWELVE) -> dict:
    """Everything the Usage page is drawn with, for one period."""
    from core import reports, settings_store

    if period not in dict(PERIODS):
        period = TWELVE
    every = list(UsageMonth.objects.all())
    current = this_month()
    shown = {
        "period": period,
        "periods": [
            {"key": key, "words": words, "here": key == period}
            for key, words in PERIODS
        ],
        "any": bool(every),
    }
    if not every:
        return shown

    first_count = min(row.first_counted for row in every)
    last_count = max(row.counted_at for row in every)
    # The year's months, oldest first, with an empty month where none was counted.
    by_month = {row.month: row for row in every}
    year = [current]
    while len(year) < YEAR:
        year.insert(0, before(year[0]))
    if period == MONTH:
        rows = [by_month[current]] if current in by_month else []
    elif period == TWELVE:
        rows = [by_month[month] for month in year if month in by_month]
    else:
        rows = every
    ended = [row for row in rows if row.month != current]

    def total(key: str) -> float:
        return sum(row.counts.get(key) or 0 for row in rows)

    def totals(key: str) -> dict:
        out: dict = {}
        for row in rows:
            for name, value in (row.counts.get(key) or {}).items():
                out[name] = out.get(name, 0) + value
        return out

    def typical(key: str) -> int:
        """One month's figure where the period is one month; else a typical
        month's, since the same people cannot be told apart across months."""
        basis = ended if (period != MONTH and ended) else rows
        values = [row.counts.get(key) or 0 for row in basis]
        return round(median(values)) if values else 0

    one = period == MONTH
    seconds = total("seconds")
    recordings = total("recordings")
    newest = by_month.get(current) or every[-1]
    accounts = newest.counts.get("accounts")

    # The waits: one month's own, or the middle of the months' typical waits.
    waited = [row for row in rows if row.counts.get("wait_typical") is not None]
    wait = (
        round(median(row.counts["wait_typical"] for row in waited)) if waited else None
    )
    longest = max((row.counts.get("wait_longest") or 0 for row in rows), default=0)

    working_days = max(1, round(len(rows) * 21))
    shown["tiles"] = [
        {
            "figure": hours(seconds),
            "words": "of recordings transcribed",
            "more": "",
        },
        {
            "figure": _number(recordings),
            "words": "recording" if recordings == 1 else "recordings",
            "more": (
                f"about {_number(recordings / working_days)} each working day"
                if not one and recordings >= working_days
                else ""
            ),
        },
        {
            "figure": _number(typical("people")),
            "words": (
                "people used the app"
                if one
                else "people used the app in a typical month"
            ),
            "more": f"of {_number(accounts)} with an account now" if accounts else "",
        },
        {
            "figure": _number(typical("cases")),
            "words": "cases worked on" if one else "cases worked on in a typical month",
            "more": f"{_number(total('cases_opened'))} opened in this period",
        },
        {
            "figure": length(wait) if wait is not None else "none yet",
            "words": "typical wait, from sending to ready",
            "more": f"longest: {length(longest)}" if longest else "",
            "warn": bool(wait) and longest > wait * 6,
        },
    ]

    # Twelve bars, always the last twelve months, whatever the period.
    month_seconds = [
        (
            month,
            (by_month[month].counts.get("seconds") or 0) if month in by_month else 0,
        )
        for month in year
    ]
    tallest = max((value for _month, value in month_seconds), default=0)
    shown["months"] = [
        {
            "label": f"{month:%b}",
            "title": f"{month:%B %Y}",
            "figure": _number(value / 3600) if value else "",
            "height": max(2, round(100 * value / tallest)) if tallest and value else 0,
            "now": month == current,
            "late": month in by_month
            and span(month)[1] <= by_month[month].first_counted,
        }
        for month, value in month_seconds
    ]

    # What was transcribed, by Recording type: the six largest, the rest folded.
    types = sorted(totals("types").items(), key=lambda pair: -pair[1])
    listed = [(name or "No type given", value) for name, value in types[:6]]
    if len(types) > 6:
        listed.append(("Other types", sum(value for _name, value in types[6:])))
    shown["types"] = _bars(listed, hours)
    languages = sorted(totals("languages").items(), key=lambda pair: -pair[1])
    shown["languages"] = ", ".join(
        f"{_language_name(code)} {hours(value)}" for code, value in languages[:4]
    )
    if len(languages) > 4:
        rest = sum(value for _code, value in languages[4:])
        shown["languages"] += f", {len(languages) - 4} more {hours(rest)}"
    translated = total("translated_seconds")
    shown["translated"] = (
        f"{hours(translated)} ({_share(translated, seconds)})" if translated else ""
    )

    # Who used which part: the same people cannot be told apart across
    # months, so a period longer than a month shows its last whole month. A
    # month that had ended before the first count has no marks for the parts
    # the audit log does not record, so it is not the month shown: until a
    # whole month has been counted as it was lived, the month so far is.
    told = rows[-1] if rows else None
    if not one:
        lived = [row for row in ended if span(row.month)[1] > row.first_counted]
        if lived:
            told = lived[-1]
        elif current in by_month:
            told = by_month[current]
    parts = (told.counts.get("parts") or {}) if told else {}
    shown["parts_month"] = (
        f"{told.month:%B %Y}" + (" so far" if told.month == current else "")
        if told
        else ""
    )
    shown["parts_people"] = (told.counts.get("people") or 0) if told else 0
    pairs = sorted(
        ((words, parts.get(key, 0)) for key, words, _rows in PARTS),
        key=lambda pair: -pair[1],
    )
    shown["parts"] = _bars(pairs, _people)
    marked_words = [words for key, words, rows in PARTS if rows is None]
    shown["marked"] = (
        ", ".join(marked_words[:-1]) + " and " + marked_words[-1]
        if len(marked_words) > 1
        else "".join(marked_words)
    )
    shown["first_count"] = timezone.localtime(first_count)
    shown["last_count"] = timezone.localtime(last_count)
    late = [row for row in rows if span(row.month)[1] <= row.first_counted]
    shown["late"] = bool(late)

    # The AI assistant.
    asked = totals("ai")
    calls = sum(asked.values())
    pairs = [(words, asked.get(key, 0)) for key, words, _features in AI]
    if asked.get(AI_OTHER[0]):
        pairs.append((AI_OTHER[1], asked[AI_OTHER[0]]))
    shown["ai"] = _bars([pair for pair in pairs if pair[1]], _number)
    failed = total("ai_failed")
    reasons = sorted(totals("ai_reasons").items(), key=lambda pair: -pair[1])
    timed = [row for row in rows if row.counts.get("chat_typical") is not None]
    shown["ai_words"] = {
        "calls": calls,
        "chat_typical": (
            length(median(row.counts["chat_typical"] for row in timed)) if timed else ""
        ),
        "failed": _number(failed),
        "failed_share": _share(failed, calls),
        "reason": REASON_WORDS.get(reasons[0][0], reasons[0][0]) if reasons else "",
    }

    # The disk: the newest level, and how fast it has grown.
    levels = [row for row in every if row.counts.get("disk_held") is not None]
    disk: dict = {}
    if levels:
        level = levels[-1].counts
        disk = {
            "held": size(level["disk_held"]),
            "total": size(level.get("disk_total")) if level.get("disk_total") else "",
            "free": size(level.get("disk_free")) if level.get("disk_free") else "",
        }
        # The last three month-to-month steps, where that many were counted.
        recent = levels[-4:]
        steps = [
            later.counts["disk_held"] - earlier.counts["disk_held"]
            for earlier, later in zip(recent, recent[1:], strict=False)
        ]
        if steps:
            growth = sum(steps) / len(steps)
            disk["steps"] = len(steps)
            if growth > 0:
                disk["growth"] = size(growth)
                room = (
                    level.get("disk_free") or 0
                ) - settings_store.minimum_free_disk_bytes()
                if level.get("disk_free"):
                    months_left = max(0, room) / growth
                    disk["room"] = (
                        "more than five years"
                        if months_left > 60
                        else f"about {round(months_left)} months"
                        if months_left >= 1.5
                        else "about a month or less"
                    )
                    disk["tight"] = months_left < 6
    shown["disk"] = disk

    uploads, refused = total("uploads"), total("refused")
    shown["wrong"] = {
        "refused": _number(refused),
        "refused_share": _share(refused, uploads + refused),
        "jobs_failed": _number(total("jobs_failed")),
    }

    # The figures as plain words, for the Admin to copy where they choose.
    period_words = dict(PERIODS)[period].lower()
    lines = [
        f"Gideon Transcribe, usage, {period_words} (counts only)",
        f"Recordings transcribed: {_number(recordings)} ({hours(seconds)})",
        f"{shown['tiles'][2]['words'].capitalize()}: {shown['tiles'][2]['figure']}",
        f"{shown['tiles'][3]['words'].capitalize()}: {shown['tiles'][3]['figure']}",
    ]
    if wait is not None:
        lines.append(f"Typical wait from sending to ready: {length(wait)}")
    if translated:
        lines.append(f"Translated to English: {_share(translated, seconds)} of hours")
    if calls:
        said = ", ".join(
            f"{row['figure']} {row['words'].lower()}" for row in shown["ai"]
        )
        lines.append(
            f"AI assistant: {said}"
            + (f"; {_share(failed, calls)} of calls failed" if failed else "")
        )
    if disk:
        lines.append(
            f"Disk: recordings hold {disk['held']}"
            + (
                f", growing about {disk['growth']} a month"
                if disk.get("growth")
                else ""
            )
        )
    lines.append(f"Release: {reports.release()}")
    shown["copy"] = "\n".join(lines)
    return shown
