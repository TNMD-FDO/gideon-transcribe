"""How long a written output usually takes, from the office's own history
(v1.95.0).

Every run of the assistant writes one audit row with how long it took and,
from this release, how much it was given (`size_tokens`). The next run of
that output reads the office's last twenty such rows, takes the median pace
in seconds per token, and scales it to what this run is given: "usually
about 4 minutes". Until three runs exist the figure is a plain guess per
output, worded "roughly". The figure is worked out once, at the ask, and
kept on the run with the moment it was asked for and the moment the worker
started, so the page shows a stable expectation and a live count of how
long it has been, and can say when a run has passed its usual time. Queue
wait is in the count and never in the pace.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import median

from django.utils import timezone

from core import audit

HISTORY = 20  # the rows the pace is read from
ENOUGH = 3  # rows before the figure counts as measured
STEP_SECONDS = 30  # a measured figure is rounded up to this


@dataclass(frozen=True)
class Key:
    feature: str  # the audit row's feature
    guess: int  # seconds, before the office has history
    most_calls: int  # the calls a run can make, for the clamp
    limit: str  # the time-limit setting's feature, "" for none
    kind: str  # the words' subject: memo, proposals, comparison, summary, chat
    from_sheet: bool | None = None  # memo rows: the rewrite's or the full write's
    looked: bool | None = None  # proposals rows: a Look for run's or a full run's


KEYS = {
    "chat_turn": Key("chat_turn", 20, 1, "chat_turn", "chat"),
    "incident_chat": Key("incident_chat", 60, 1, "incident_chat", "chat"),
    "case_chat_turn": Key("case_chat_turn", 60, 4, "", "chat"),
    "summary": Key("summary", 90, 1, "summary", "summary"),
    "incident_memo": Key("incident_memo", 300, 4, "incident_memo", "memo", False),
    "incident_memo_rewrite": Key(
        "incident_memo", 120, 3, "incident_memo", "memo", True
    ),
    "incident_events": Key(
        "incident_events", 180, 40, "incident_events", "proposals", looked=False
    ),
    # The Look for run (v1.96.0): one look at each stretch, so about half.
    "incident_look_for": Key(
        "incident_events", 90, 20, "incident_events", "proposals", looked=True
    ),
    "compare_report": Key("compare_report", 180, 12, "compare_report", "comparison"),
}

THINGS = {
    "memo": "the memo",
    "proposals": "the proposals",
    "comparison": "the comparison",
    "summary": "the summary",
    "dictation": "the memo",
    "chat": "",
}
BIG = {
    "memo": "A memo this size gives the engine a great deal to read",
    "proposals": "An incident this size gives the engine a great deal to read",
    "comparison": "A report this size gives the engine a great deal to read",
    "summary": "A recording this size gives the engine a great deal to read",
    "dictation": "A dictation this size gives the engine a great deal to read",
}


def _thinking() -> bool:
    from core import assistant

    return assistant.thinking()


def _limit_seconds(key: Key) -> int | None:
    """The most a run may take before the app gives up: the feature's time
    limit (doubled while the model may think) times the calls it can make."""
    from core import assistant, settings_store

    if key.feature == "case_chat_turn":
        return settings_store.case_chat_question_seconds() * (2 if _thinking() else 1)
    if not key.limit:
        return None
    try:
        return assistant.time_limit(key.limit) * key.most_calls
    except Exception:  # noqa: BLE001 - a feature without a limit is unclamped
        return None


def _rows(key: Key):
    rows = audit.Row.objects.filter(
        category=audit.Category.LLM,
        event="AI assistant call",
        outcome=audit.Outcome.SUCCESS,
        details__feature=key.feature,
        details__size_tokens__gt=0,
    )
    # The rewrite's rows are told apart in Python: a JSON key a row lacks is
    # NULL to the database, and NOT (NULL = true) drops the row too.
    return rows.order_by("-at")[: HISTORY * 3]


def pace(key_name: str) -> float | None:
    """Seconds per token of what a run is given, from the office's last runs
    of this output; None until it has enough. Rows made while the model was
    thinking are read apart from the rest when there are enough of them."""
    key = KEYS[key_name]
    rates = []
    thinks = _thinking()
    for row in _rows(key):
        details = row.details or {}
        if (
            key.from_sheet is not None
            and bool(details.get("from_sheet")) != key.from_sheet
        ):
            continue
        if key.looked is not None and bool(details.get("looked")) != key.looked:
            continue
        try:
            seconds = float(details.get("duration_seconds") or 0)
            tokens = float(details.get("size_tokens") or 0)
        except (TypeError, ValueError):
            continue
        if seconds <= 0 or tokens <= 0:
            continue
        rates.append((bool(details.get("thinking")) == thinks, seconds / tokens))
    same = [rate for matches, rate in rates if matches]
    chosen = same if len(same) >= ENOUGH else [rate for _, rate in rates]
    chosen = chosen[:HISTORY]
    if len(chosen) < ENOUGH:
        return None
    return float(median(chosen))


def expect(key_name: str, tokens: int) -> tuple[int, bool]:
    """(seconds, measured): the office's figure for a run given `tokens`, or
    the guess before there is history."""
    key = KEYS[key_name]
    rate = pace(key_name)
    if rate is None:
        return key.guess, False
    seconds = rate * max(int(tokens or 0), 1)
    seconds = max(STEP_SECONDS, math.ceil(seconds / STEP_SECONDS) * STEP_SECONDS)
    limit = _limit_seconds(key)
    if limit:
        seconds = min(seconds, limit)
    return int(seconds), True


def note(key_name: str, tokens: int) -> dict:
    """What a run is told at the ask, kept on the run. Made once; never on a
    poll."""
    seconds, measured = expect(key_name, tokens)
    return {
        "key": key_name,
        "tokens": int(tokens or 0),
        "seconds": seconds,
        "measured": measured,
        "asked_at": timezone.now().isoformat(),
        "started_at": "",
    }


def started(stored: dict | None) -> dict:
    """The moment the worker picked the run up, stamped onto what was kept."""
    kept = dict(stored or {})
    kept["started_at"] = timezone.now().isoformat()
    return kept


def words(seconds: int, measured: bool, fine: bool = False) -> str:
    """ "usually about 4 minutes", "usually under a minute", "roughly 4
    minutes"; with `fine`, a chat's "usually about 15 seconds"."""
    from core.assistant import about

    if fine and seconds < 60:
        rounded = max(5, math.ceil(seconds / 5) * 5)
        base = f"about {rounded} seconds"
    else:
        base = about(int(seconds))
    if measured:
        return f"usually {base}"
    return base.replace("about ", "roughly ")


def over_words(measured: bool, kind: str) -> str:
    """Past the figure: the run is working normally, and why it can take
    longer. Said plainly, never as an alarm."""
    if kind == "chat":
        return "Still working on it."
    if measured:
        return (
            f"Still writing, and working normally. {BIG.get(kind, BIG['memo'])}, "
            "so it can run past the usual time; it will be here when it lands."
        )
    return (
        "Still writing, and working normally. The figure was a guess until your "
        "office has a few of these behind it; it will be here when it lands."
    )


def leave_words(kind: str) -> str:
    thing = THINGS.get(kind, "it")
    if not thing:
        return ""
    return f"You can leave this page; {thing} will be here when it lands."


def json_of(stored: dict | None, state: str, kind: str | None = None) -> dict:
    """What the page draws while the run is queued or running; {} otherwise."""
    if not stored or str(state).lower() not in ("queued", "running"):
        return {}
    key = KEYS.get(stored.get("key", ""))
    kind = kind or (key.kind if key else "memo")
    measured = bool(stored.get("measured"))
    seconds = int(stored.get("seconds") or 0)
    return {
        "expected_seconds": seconds,
        "measured": measured,
        "asked_at": stored.get("asked_at", ""),
        "started_at": stored.get("started_at", ""),
        "words": words(seconds, measured, fine=(kind == "chat")),
        "over_words": over_words(measured, kind),
        "leave_words": leave_words(kind),
    }


def for_audit(stored: dict | None) -> dict:
    """What the run's audit row carries so the next ask can read the pace:
    the size the ask measured, the figure it was given, and whether the model
    was thinking."""
    if not stored:
        return {}
    return {
        "size_tokens": int(stored.get("tokens") or 0),
        "expected_seconds": int(stored.get("seconds") or 0),
        "thinking": _thinking(),
    }
