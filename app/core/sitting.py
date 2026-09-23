"""One sitting (Phase 8 chapter 9), and its bar on the case page (chapter 10).

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

Chapter 10: each camera's share of the Sitting is kept on the camera
(`record_tokens`, `words_tokens`, `record_made_at`) and refreshed when its
Digest is newer, so the bar is drawn from the shares and a case page reads
no Digest to draw a row. The real calls still fit the record itself (`fit`).
"""

from __future__ import annotations

from collections.abc import Callable

from django.utils import timezone

from core import assistant, engine, prompts, settings_store

# The bar's zones, as a share of the Sitting: under NEARLY is green ("room
# for"), from NEARLY to the line amber ("nearly full"), past the line red.
NEARLY = 0.85


class TooLong(engine.Problem):
    """Every unpinned camera is by words alone and the whole still does not fit."""

    def __init__(self, pinned: list[str]) -> None:
        super().__init__(engine.TOO_LONG, "the words alone are too long")
        self.pinned = pinned


def available() -> bool:
    """Whether the bar is drawn at all: the assistant on, and Incidents on."""
    from core import incidents

    return bool(incidents.on() and settings_store.get("assistant_available"))


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


# The shares (chapter 10) ------------------------------------------------------


def _record_tokens_by_camera(incident, words_alone=frozenset()) -> dict[str, int]:
    from core.incident_assistant import record_of

    record = record_of(incident, words_alone=words_alone)
    by_camera: dict[str, int] = {}
    for _, name, line in record["rows"]:
        by_camera[name] = by_camera.get(name, 0) + prompts.tokens(name + ": " + line)
    return by_camera


def _stale(camera) -> bool:
    """A share is stale when it was never counted or its Digest is newer."""
    if camera.record_made_at is None:
        return True
    transcript = getattr(camera.recording, "transcript", None)
    if transcript is None:
        return False
    made = assistant.digest_made_at(transcript)
    return bool(made and made > camera.record_made_at)


def refresh_shares(incident, cameras=None) -> None:
    """Count every synced camera's record and words, and keep them. One
    reading of the record for the whole incident, never one per camera."""
    from core.incident_assistant import synced_cameras

    if cameras is None:
        cameras = [
            one
            for one in synced_cameras(incident)
            if hasattr(one.recording, "transcript")
        ]
    if not cameras:
        return
    whole = _record_tokens_by_camera(incident)
    words = _record_tokens_by_camera(
        incident, words_alone=frozenset(one.camera_id() for one in cameras)
    )
    now = timezone.now()
    for camera in cameras:
        name = camera.camera_id()
        camera.record_tokens = whole.get(name, 0)
        camera.words_tokens = words.get(name, 0)
        camera.record_made_at = now
        camera.save(update_fields=["record_tokens", "words_tokens", "record_made_at"])


def _shares_of(incident) -> list[dict]:
    """Every synced camera's share, refreshed where stale."""
    from core.incident_assistant import synced_cameras

    cameras = [
        one for one in synced_cameras(incident) if hasattr(one.recording, "transcript")
    ]
    if any(_stale(one) for one in cameras):
        refresh_shares(incident, cameras)
    return [
        {
            "id": str(one.pk),
            "name": one.camera_id(),
            "seconds": one.length(),
            "record": one.record_tokens,
            "words": one.words_tokens,
            "pinned": one.pinned,
            "has_digest": one.record_tokens != one.words_tokens,
            "adding": False,
        }
        for one in cameras
    ]


def _share_of_recording(recording) -> dict | None:
    """A video not yet in an incident (the offer, the Add cameras dialog):
    counted for the draw and not kept."""
    transcript = getattr(recording, "transcript", None)
    if transcript is None:
        return None
    name = (recording.stamp or {}).get("camera") or recording.title
    words_text = prompts.render(prompts.lines_of(transcript))
    digest = assistant.digest_text(transcript) if assistant.digests_on() else ""
    words = prompts.tokens(words_text)
    record = prompts.tokens(digest) if digest else words
    return {
        "id": "",
        "name": name,
        "seconds": float(recording.duration_seconds or 0.0),
        "record": record,
        "words": words,
        "pinned": False,
        "has_digest": bool(digest),
        "adding": True,
    }


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


def _overhead(incident) -> int:
    """What a reading costs before any camera: the templates, the cameras
    line and the chronology (empty for an incident that does not exist yet)."""
    from core.incident_assistant import _cameras_line, _chronology_lines

    system, _ = _memo_shape(incident)
    if incident is None:
        head, events, about = "", [], ""
    else:
        head = _cameras_line(incident)
        events, _ = _chronology_lines(incident)
        about = incident.about
    return prompts.tokens(system) + prompts.tokens(
        prompts.incident_memo_input(head, events, "", about=about)
    )


def _hours_words(hours: float) -> str:
    """Halves under ten hours, whole above; never "0"."""
    if hours < 10:
        rounded = max(0.5, round(hours * 2) / 2)
        whole = int(rounded)
        if rounded == whole:
            return str(whole)
        return "½" if whole == 0 else f"{whole}½"
    return str(int(round(hours)))


def _count(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def _bar(shares: list[dict], *, overhead: int, answer_cap: int, offer: bool) -> dict:
    """The bar from the shares: chapter 9's arithmetic on the kept figures.
    The longest camera with a Digest, not pinned, goes to words alone first
    when the whole does not fit, the same rule the real fit follows."""
    window = engine.window()
    adding = any(one["adding"] for one in shares)
    full = overhead + answer_cap + sum(one["record"] for one in shares)
    need = full
    words_alone: list[str] = []
    over = False
    while need > window:
        movable = [
            one
            for one in shares
            if one["has_digest"]
            and not one["pinned"]
            and one["name"] not in words_alone
        ]
        if not movable:
            over = True
            break
        longest = max(movable, key=lambda one: one["seconds"])
        need -= longest["record"] - longest["words"]
        words_alone.append(longest["name"])
    pins = sorted(one["name"] for one in shares if one["pinned"])

    total_seconds = sum(one["seconds"] for one in shares)
    share = full / window if window else 0.0
    used_hours = total_seconds / 3600
    capacity_hours = used_hours / share if share else 0.0
    record_tokens = sum(one["record"] for one in shares)
    average = record_tokens / len(shares) if shares else 0
    room = int((window - full) / average) if average and full < window else 0
    zone = (
        "over" if (over or words_alone) else ("nearly" if share >= NEARLY else "room")
    )
    count = len(shares)
    alone_count = len(words_alone)
    shown = count - alone_count

    if zone == "room":
        sentence = (
            "Still one sitting: the memo, the report check and Gideon's "
            f"answers read what was said and what was shown on all {count} "
            "cameras. "
            if adding
            else "It reads everything in this incident at one sitting before "
            "it writes the memo, checks the report or answers a question. "
        ) + f"Room for about {_count(room, 'more camera')} of this length."
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
    # The case page's short word beside the small bar (chapter 10).
    if over and not words_alone:
        word, tone = "does not fit", "danger"
    elif words_alone:
        word, tone = f"{_count(alone_count, 'camera')} by words alone", "warn"
    else:
        word, tone = f"all {count} whole" if count > 1 else "read whole", "muted"
    if offer:
        short = (
            f"More than one sitting: the assistant would read what {shown} of "
            f"{count} showed."
            if words_alone
            else f"Room for about {_count(room, 'more camera')} of this length."
        )
    else:
        short = ""

    return {
        "on": True,
        "window": window,
        "window_source": engine.window_source(),
        "need": full,
        "share": round(share, 3),
        "percent": min(100.0, round(share * 100, 1)),
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
        "short": short,
        "word": word,
        "tone": tone,
        "cameras": [
            {
                "id": one["id"],
                "name": one["name"],
                "seconds": one["seconds"],
                "tokens": one["record"],
                # Its width on a bar whose whole is the sitting.
                "percent": round(one["record"] / window * 100, 2) if window else 0,
                "read": "words" if one["name"] in words_alone else "both",
                "pinned": one["pinned"],
                "has_digest": one["has_digest"],
                "adding": one["adding"],
            }
            for one in shares
        ],
        "adding": [
            {"name": one["name"], "seconds": one["seconds"], "tokens": one["record"]}
            for one in shares
            if one["adding"]
        ],
        "words_alone": words_alone,
        "pinned": pins,
    }


def json_for(incident, extra_recordings=()) -> dict:
    """The Cameras tab's block, the Add cameras dialog's bar, the case page's
    row, and the offer to add a video to an incident.

    `extra_recordings` are videos not yet in the incident: counted as if
    added, so the bar says what the Sitting will hold with them in.
    """
    if not available():
        return {"on": False}
    shares = _shares_of(incident)
    for recording in extra_recordings:
        one = _share_of_recording(recording)
        if one is not None:
            shares.append(one)
    if not shares:
        return {
            "on": False,
            "window": engine.window(),
            "window_source": engine.window_source(),
        }
    _, answer_cap = _memo_shape(incident)
    return _bar(
        shares,
        overhead=_overhead(incident),
        answer_cap=answer_cap,
        offer=bool(extra_recordings),
    )


def json_for_recordings(recordings) -> dict:
    """The offer's bar (chapter 10): the incident as it would read with these
    videos in, before it exists; nothing is kept."""
    if not available():
        return {"on": False}
    shares = [
        one
        for one in (_share_of_recording(recording) for recording in recordings)
        if one is not None
    ]
    if not shares:
        return {"on": False}
    _, answer_cap = _memo_shape(None)
    return _bar(shares, overhead=_overhead(None), answer_cap=answer_cap, offer=True)


def read_words(count: int, shown: int, alone: list[str]) -> str:
    """ "everything said on 12 cameras and what 7 of them showed", for the
    memo's head line, the comparison's state line and Gideon's panel."""
    if count == shown:
        return f"everything said on {_count(count, 'camera')} and what they showed"
    return (
        f"everything said on {_count(count, 'camera')} and what {shown} of them "
        f"showed; {_count(len(alone), 'camera')} by words alone"
    )
