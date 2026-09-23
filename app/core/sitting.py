"""One sitting (Phase 8 chapter 9).

The AI assistant reads an Incident at one sitting before it writes the memo,
checks the report or answers a question: every synced camera's record in one
call. The Sitting is what the engine can hold at once. This module is the one
place that fits a record to it, so the bar on the Cameras tab, the memo, the
incident chat and the comparison never disagree about what was read.

The rule: everything said is always read. When the whole does not fit, the
longest cameras are read by their words alone (their transcript in place of
their Digest), longest first, skipping Pinned cameras, until it fits. Only
when every unpinned camera is by words alone and the whole still does not fit
does the call fail, and the page says so.
"""

from __future__ import annotations

from collections.abc import Callable

from core import assistant, engine, prompts, settings_store

# The bar's zones, as a share of the Sitting: under NEARLY is green ("room
# for"), from NEARLY to the line amber ("nearly full"), past the line red.
NEARLY = 0.85


class TooLong(engine.Problem):
    """Every unpinned camera is by words alone and the whole still does not fit."""

    def __init__(self, pinned: list[str]) -> None:
        super().__init__(engine.TOO_LONG, "the words alone are too long")
        self.pinned = pinned


def pinned_names(incident) -> set[str]:
    return {
        one.camera_id()
        for one in incident.cameras.select_related("recording")
        if one.pinned and one.is_synced()
    }


def _seconds_of(incident) -> dict[str, float]:
    from core.incident_assistant import synced_cameras

    return {one.camera_id(): one.length() for one in synced_cameras(incident)}


def fit(
    incident,
    *,
    system: str,
    wrap: Callable[[str], str],
    answer_cap: int,
    window: int | None = None,
) -> tuple[dict, str, list[str]]:
    """Fit the incident record to the Sitting.

    `wrap` turns the record's text into the user message (the memo's shape,
    the question after it, the report's window). Returns the record as read,
    the user message, and the cameras read by their words alone, in the order
    they were moved. Raises TooLong when nothing more can be moved.
    """
    from core.incident_assistant import _record_text, record_of

    if window is None:
        window = engine.window()
    pins = pinned_names(incident)
    seconds = _seconds_of(incident)
    words_alone: list[str] = []
    while True:
        record = record_of(incident, words_alone=set(words_alone))
        user = wrap(_record_text(incident, record, set()))
        if prompts.fits(system, user, answer_cap=answer_cap, window=window):
            return record, user, words_alone
        movable = [name for name in record["used"] if name not in pins]
        if not movable:
            raise TooLong(sorted(pins))
        words_alone.append(max(movable, key=lambda name: seconds.get(name, 0.0)))


# The bar -------------------------------------------------------------------


def _memo_shape(incident) -> tuple[str, int]:
    """The memo's system message and answer cap: the largest reading an
    incident gets, so the bar is drawn against it."""
    from core.assistant import PromptTemplate

    ground = PromptTemplate.named(PromptTemplate.GROUND_RULES)
    template = PromptTemplate.named(PromptTemplate.INCIDENT_MEMO)
    system = prompts.system_message(
        ground.text,
        template.text,
        prompts.INCIDENT_MEMO_FORMAT
        + "\n\n"
        + prompts.NARRATIVE_RULES
        + "\n\n"
        + prompts.INCIDENT_RULES,
    )
    return system, assistant.cap(settings_store.incident_memo_answer_cap())


def _hours_words(hours: float) -> str:
    """Halves under ten hours, whole above; never "0"."""
    if hours < 10:
        rounded = max(0.5, round(hours * 2) / 2)
        whole = int(rounded)
        return f"{whole}½" if rounded != whole else str(whole)
    return str(int(round(hours)))


def _count(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def json_for(incident, extra_recordings=()) -> dict:
    """The Cameras tab's block and the Add cameras dialog's bar.

    `extra_recordings` are the case's videos ticked on the dialog, not yet in
    the incident: their record is counted as if added, so the bar says what
    the Sitting will hold with them in.
    """
    from core.incident_assistant import (
        _cameras_line,
        _chronology_lines,
        record_of,
        synced_cameras,
    )

    window = engine.window()
    cameras = [
        one for one in synced_cameras(incident) if hasattr(one.recording, "transcript")
    ]
    if not cameras and not extra_recordings:
        return {
            "on": False,
            "window": window,
            "window_source": engine.window_source(),
        }

    system, answer_cap = _memo_shape(incident)
    event_lines, _ = _chronology_lines(incident)
    pins = pinned_names(incident)

    # Each camera's share of the full record: what the assistant reads of it
    # when everything is read whole.
    full = record_of(incident)
    by_camera: dict[str, int] = {}
    for _, name, line in full["rows"]:
        by_camera[name] = by_camera.get(name, 0) + prompts.tokens(name + ": " + line)
    seconds = {one.camera_id(): one.length() for one in cameras}
    overhead = prompts.tokens(system) + prompts.tokens(
        prompts.incident_memo_input(
            _cameras_line(incident), event_lines, "", about=incident.about
        )
    )

    # The cameras being added, counted as if in.
    extra: list[dict] = []
    for recording in extra_recordings:
        transcript = getattr(recording, "transcript", None)
        if transcript is None:
            continue
        digest = assistant.digest_text(transcript) if assistant.digests_on() else ""
        text = digest or prompts.render(prompts.lines_of(transcript))
        name = (recording.stamp or {}).get("camera") or recording.title
        extra.append(
            {
                "name": name,
                "tokens": prompts.tokens(text),
                "seconds": float(recording.duration_seconds or 0.0),
            }
        )

    # The fit, as the memo would make it.
    words_alone: list[str] = []
    over = False
    try:
        _, _, words_alone = fit(
            incident,
            system=system,
            wrap=lambda body: prompts.incident_memo_input(
                _cameras_line(incident), event_lines, body, about=incident.about
            ),
            answer_cap=answer_cap,
            window=window,
        )
    except TooLong:
        over = True
        words_alone = sorted(name for name in full["used"] if name not in pins)

    added_tokens = sum(e["tokens"] for e in extra)
    need = overhead + answer_cap + sum(by_camera.values()) + added_tokens
    total_seconds = sum(seconds.values()) + sum(e["seconds"] for e in extra)
    record_tokens = sum(by_camera.values()) + added_tokens
    # Hours of camera: the cameras' own length is what is held, and the
    # sitting holds that many hours as often as the window holds the need.
    share = need / window if window else 0.0
    used_hours = total_seconds / 3600
    capacity_hours = used_hours / share if share else 0.0
    average = record_tokens / (len(cameras) + len(extra)) if (cameras or extra) else 0
    room = int((window - need) / average) if average and need < window else 0

    if extra:
        zone = "over" if share > 1 else ("nearly" if share >= NEARLY else "room")
        alone_count = len(words_alone)
    else:
        zone = (
            "over"
            if (over or words_alone)
            else ("nearly" if share >= NEARLY else "room")
        )
        alone_count = len(words_alone)
    count = len(cameras) + len(extra)
    shown = count - alone_count

    if zone == "room":
        sentence = (
            "It reads everything in this incident at one sitting before it writes "
            "the memo, checks the report or answers a question. "
            f"Room for about {_count(room, 'more camera')} of this length."
        )
    elif zone == "nearly":
        sentence = (
            "Nearly full. One more long camera and the assistant will stop reading "
            "what the longest cameras showed, and read their words alone. "
            "Everything said stays in, whatever is added."
        )
    elif over and not words_alone:
        sentence = (
            "The words alone of these cameras are more than the assistant can hold "
            "at once; leave a camera out."
        )
    else:
        sentence = (
            f"More than one sitting. The assistant reads everything said on all "
            f"{count} cameras, and what {shown} of them showed. The "
            f"{_count(alone_count, 'longest camera') if alone_count > 1 else 'longest camera'}"  # noqa: E501
            f"{' is' if alone_count == 1 else ' are'} read by "
            f"{'its' if alone_count == 1 else 'their'} words alone, so the memo, "
            "the report check and Gideon's answers say nothing about what "
            f"{'that camera' if alone_count == 1 else 'those cameras'} showed; the "
            "chronology keeps every camera's events. Each one says so where it is "
            "written."
        )
        if over:
            sentence += (
                " Even so it does not fit: lift a pin or leave a camera out."
                if pins
                else " Even so it does not fit; leave a camera out."
            )
    if extra and zone != "over":
        sentence = (
            "Still one sitting: the memo, the report check and Gideon's answers "
            f"read what was said and what was shown on all {count} cameras."
        )

    return {
        "on": True,
        "window": window,
        "window_source": engine.window_source(),
        "need": need,
        "share": round(share, 3),
        "zone": zone,
        "figure": (
            f"{_hours_words(used_hours)} of {_hours_words(capacity_hours)} hours' worth"
        ),
        "capacity_words": f"{_hours_words(capacity_hours)} hours' worth: one sitting",
        "count": count,
        "shown": shown,
        "sources": (
            f"{_count(count, 'camera')}, what was said and what they showed"
            if not alone_count
            else f"{_count(count, 'camera')}"
        ),
        "sentence": sentence,
        "cameras": [
            {
                "id": str(one.pk),
                "name": one.camera_id(),
                "seconds": seconds.get(one.camera_id(), 0.0),
                "tokens": by_camera.get(one.camera_id(), 0),
                "read": "words" if one.camera_id() in words_alone else "both",
                "pinned": one.pinned,
                "has_digest": one.camera_id() in full["used"],
            }
            for one in sorted(cameras, key=lambda one: one.starts_at or 0.0)
        ],
        "adding": [
            {"name": e["name"], "seconds": e["seconds"], "tokens": e["tokens"]}
            for e in extra
        ],
        "words_alone": words_alone,
        "pinned": sorted(pins),
    }


def read_words(count: int, shown: int, alone: list[str]) -> str:
    """ "everything said on 12 cameras and what 7 of them showed", for the
    memo's head line, the comparison's state line and Gideon's panel."""
    if count == shown:
        return f"everything said on {_count(count, 'camera')} and what they showed"
    return (
        f"everything said on {_count(count, 'camera')} and what {shown} of them "
        f"showed; {_count(len(alone), 'camera')} by words alone"
    )
