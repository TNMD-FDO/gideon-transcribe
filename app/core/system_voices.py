"""The phone system's voice (Phase 5 chapter 2, "The phone system's voice",
v1.159.0; the second half of the Call system of ADR 0021, the drawing
docs/spec/mockups/phase-5-system-voices.html).

On a jail call the prepaid-call system's announcements are the Call
system's lines by their words (core/call_system.py). The words miss some:
a prompt the recogniser heard wrongly, a phrase not on the list, a line
cut short. This module teaches the app the system's voice from the lines
the words found, and in the same reading of the voice step gives the
Call system the lines its voice finds, under five guards against a person
taken for the system, at the maintainer's worry of 2026-10-26:

1. Taught from the words only. The print is the mean of the system's
   word-found lines on every call that taught it; a line given by voice
   never teaches it, so a party's voice never enters it.
2. Nearer the system than its own speaker, by a firm margin: the line's
   own vector must be closer to the system's print than to its own label's
   print, and than to every other party's, by the margin the check uses
   for a sure move on that recording (the judge's threshold).
3. Next to the words: within NEAR_WORDS_SECONDS of a line the words found,
   or a very strong match (STRONG) on its own.
4. A ceiling per call: when the voice would take more than CEILING_SHARE
   of one label's lines, it takes none from that label on that call and
   the page says "held back".
5. Counted and reversible: every line given by voice carries a pill and
   "Not the system" on the guided page; BACK_TO_STOP lines given back in a
   month stop the giving by themselves.

And it ships listening, not moving: a new phone system starts with
`giving` off, the voice step counts what it would have given, and an
Admin starts the giving from the Voices place once the numbers on the
office's own calls satisfy them.

The voice is the office's, not a unit's; one row per phone system the
office meets (a call's announcements that sound like no known system make
a new row). Never logged, exported or sent anywhere; nothing of a party's
voice is in it.
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter, defaultdict

import numpy as np
from django.db import models, transaction
from django.utils import timezone

from core import audit, call_system

log = logging.getLogger(__name__)

# A call's announcements this near a known print (cosine) are that system's;
# further, and they are a system the office has not met. Most offices meet
# one; the figure is low on purpose so that one system does not split into
# two cards over a noisy call. Judged on the office's calls, a constant.
SAME_SYSTEM = 0.45
# A system line teaches the print only with this much clean speech and
# timed words (the voice step's own bar for a print).
TEACH_LEAST_SECONDS = 2.0
# A call teaches with at least this many such lines (the phrases' own
# minimum for an untyped recording).
TEACH_LEAST_LINES = 3
# Guard 3: within this many seconds of a word-found line, or alone when the
# match is this strong.
NEAR_WORDS_SECONDS = 15.0
STRONG = 0.8
# Guard 4: more than this share of one label's lines, and none are taken.
CEILING_SHARE = 0.2
# Guard 5: this many lines given back by hand in a month stop the giving.
BACK_TO_STOP = 3
# The first phone system's name; the next are numbered. An Admin renames.
FIRST_NAME = "Call system"


class SystemVoice(models.Model):
    """One phone system the office has met: its print (the mean of the
    calls' announcement prints in `parts`, weighted by seconds), its name,
    whether its voice gives lines or only counts, and the month's counts."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=60, default=FIRST_NAME)
    vector = models.JSONField(null=True, blank=True)
    # {recording id: {"vector", "seconds", "lines", "at"}}
    parts = models.JSONField(default=dict, blank=True)
    # Off at first: counting what it would give until an Admin starts it.
    giving = models.BooleanField(default=False)
    first_heard = models.DateTimeField(default=timezone.now)
    last_heard = models.DateTimeField(null=True, blank=True)
    # {"2026-10": {"calls", "words", "would", "given", "held", "back"}}
    months = models.JSONField(default=dict, blank=True)
    called_out_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created"]

    @property
    def live(self) -> bool:
        return bool(self.vector)


# The switch and the sums --------------------------------------------------------------


def on() -> bool:
    """With the Call system: nothing here runs while that switch is off."""
    return call_system.on()


def _unit(v) -> np.ndarray:
    arr = np.asarray(v, dtype="float32")
    n = float(np.linalg.norm(arr))
    return arr / n if n else arr


def _month(now=None) -> str:
    return (now or timezone.now()).strftime("%Y-%m")


COUNTS = ("calls", "words", "would", "given", "held", "back")


def bump(voice: SystemVoice, now=None, **counts: int) -> None:
    months = dict(voice.months or {})
    month = dict(months.get(_month(now)) or {})
    for key, n in counts.items():
        if n:
            month[key] = int(month.get(key, 0)) + int(n)
    months[_month(now)] = month
    voice.months = months


def month_counts(voice: SystemVoice, now=None) -> dict:
    month = (voice.months or {}).get(_month(now)) or {}
    return {key: int(month.get(key, 0)) for key in COUNTS}


def totals(voice: SystemVoice) -> dict:
    out = dict.fromkeys(COUNTS, 0)
    for month in (voice.months or {}).values():
        for key in COUNTS:
            out[key] += int(month.get(key, 0))
    return out


def rebuild(voice: SystemVoice) -> None:
    parts = voice.parts or {}
    if not parts:
        voice.vector = None
        return
    weights = np.asarray(
        [max(float(one.get("seconds", 0)), 1.0) for one in parts.values()]
    )
    vectors = np.stack([_unit(one["vector"]) for one in parts.values()])
    voice.vector = [round(float(x), 5) for x in _unit(weights @ vectors)]


def find_for(centre: np.ndarray) -> tuple[SystemVoice | None, float]:
    """The known phone system nearest this call's announcements, when near
    enough to be the same one."""
    best, score = None, -2.0
    for voice in SystemVoice.objects.all():
        if not voice.live:
            continue
        cos = float(_unit(voice.vector) @ centre)
        if cos > score:
            best, score = voice, cos
    if best is None or score < SAME_SYSTEM:
        return None, score
    return best, score


def _block(transcript) -> dict:
    return dict((transcript.provenance or {}).get("call_system") or {})


def _save_block(transcript, block: dict) -> None:
    provenance = dict(transcript.provenance or {})
    provenance["call_system"] = block
    transcript.provenance = provenance
    transcript.save(update_fields=["provenance"])


# Teaching -----------------------------------------------------------------------------


def teach(transcript, stretches: dict, now=None) -> SystemVoice | None:
    """This call's announcements, by their words, teach the phone system
    they sound like, or make a new one. Guard 1: a line given by voice is
    never among them. Returns the system taught, or None when the call had
    too few readable announcement lines."""
    block = _block(transcript)
    by_voice = set((block.get("by_voice") or {}).keys())
    ids = [
        str(pk)
        for pk in transcript.segments.filter(speaker=call_system.NAME).values_list(
            "pk", flat=True
        )
        if str(pk) not in by_voice
    ]
    vectors, seconds = [], 0.0
    for sid in ids:
        row = stretches.get(sid) or {}
        if not row.get("vector") or not row.get("timed"):
            continue
        if float(row.get("net") or 0.0) < TEACH_LEAST_SECONDS:
            continue
        vectors.append(_unit(row["vector"]))
        seconds += float(row["net"])
    if len(vectors) < TEACH_LEAST_LINES:
        return None
    centre = _unit(np.stack(vectors).mean(axis=0))
    recording = transcript.recording
    with transaction.atomic():
        voice, _score = find_for(centre)
        made = voice is None
        if made:
            live = SystemVoice.objects.count()
            voice = SystemVoice.objects.create(
                name=FIRST_NAME if live == 0 else f"{FIRST_NAME} {live + 1}",
                first_heard=now or timezone.now(),
            )
        parts = dict(voice.parts or {})
        new_part = str(recording.pk) not in parts
        parts[str(recording.pk)] = {
            "vector": [round(float(x), 5) for x in centre],
            "seconds": round(seconds, 1),
            "lines": len(vectors),
            "at": (now or timezone.now()).isoformat(timespec="seconds"),
        }
        voice.parts = parts
        rebuild(voice)
        voice.last_heard = now or timezone.now()
        bump(voice, now, calls=1 if new_part else 0, words=len(ids) if new_part else 0)
        voice.save()
    if made:
        audit.write(
            audit.Category.SYSTEM,
            "Phone system first heard",
            system="voices",
            object_type="recording",
            object_id=str(recording.pk),
            object_label=recording.title,
            lines=len(vectors),
        )
    block["voice"] = str(voice.pk)
    _save_block(transcript, block)
    return voice


# Giving -------------------------------------------------------------------------------


def give(transcript, judge, voices: list[SystemVoice], now=None) -> dict:
    """The lines the phone system's voice would give to the Call system
    under the guards, given when the system is giving, counted either way.
    `judge` is the voice step's judge, built before any line here moves."""
    out = {"would": 0, "given": 0, "held": {}, "giving": False, "voice": ""}
    live = [one for one in voices if one.live]
    if judge is None or not live:
        return out
    out["giving"] = any(one.giving for one in live)
    out["voice"] = live[0].name
    prints = [(one, _unit(one.vector)) for one in live]
    block = _block(transcript)
    back = set((block.get("back") or {}).keys())
    system_starts = list(
        transcript.segments.filter(speaker=call_system.NAME).values_list(
            "start", flat=True
        )
    )
    found: dict[str, list[str]] = defaultdict(list)
    for sid, row in judge.stretches.items():
        if sid in back or not row.get("timed") or row["net"] < judge.floor:
            continue
        own = judge.name_of(sid)
        threshold = judge.threshold(row["net"])
        cos_own = judge.cos_to(sid, own)
        if not own or threshold is None or cos_own is None:
            continue
        v = judge.vec[sid]
        cos_system = max(float(v @ print_) for _voice, print_ in prints)
        # Guard 2: nearer the system than its own speaker, and than every
        # other party, by the firm margin.
        if cos_system - cos_own < threshold:
            continue
        others = [judge.cos_to(sid, key[1]) for key in judge.others_for(sid)]
        others = [one for one in others if one is not None]
        if others and cos_system - max(others) < threshold:
            continue
        # Guard 3: next to the words, or very strong on its own.
        near = any(
            abs(float(row["start"]) - float(start)) <= NEAR_WORDS_SECONDS
            for start in system_starts
        )
        if not near and cos_system < STRONG:
            continue
        found[own].append(sid)
    # Guard 4: the ceiling per label.
    totals_by_label = Counter(
        name for name in judge.names.values() if not call_system.is_system(name)
    )
    would: list[tuple[str, str]] = []
    for own, ids in found.items():
        if len(ids) > CEILING_SHARE * max(totals_by_label.get(own, 0), 1):
            out["held"][own] = len(ids)
            continue
        would.extend((sid, own) for sid in ids)
    out["would"] = len(would)
    if out["giving"] and would:
        from core.jobs import Segment

        Segment.objects.filter(pk__in=[int(sid) for sid, _own in would]).update(
            speaker=call_system.NAME
        )
        by_voice = dict(block.get("by_voice") or {})
        by_voice.update({sid: own for sid, own in would})
        block["by_voice"] = by_voice
        out["given"] = len(would)
    block["voice_would"] = out["would"]
    block["held"] = dict(out["held"])
    _save_block(transcript, block)
    for voice, _print in prints:
        bump(
            voice,
            now,
            would=out["would"],
            given=out["given"],
            held=sum(out["held"].values()),
        )
        voice.save(update_fields=["months"])
        break  # the counts go to the system this call taught, or the first
    return out


def on_voices(transcript, stretches: dict, judge) -> dict:
    """The voice step's hook (speaker_check._voice_notes): teach, then
    give or count. Never fails the check."""
    if not on() or judge is None:
        return {}
    try:
        taught = teach(transcript, stretches)
        voices = [taught] if taught is not None else list(SystemVoice.objects.all())
        return give(transcript, judge, voices)
    except Exception as error:  # noqa: BLE001 - the check must not fail on this
        log.exception("the phone system's voice could not be read")
        return {"error": str(error)[:120]}


# The way back -------------------------------------------------------------------------


def _voice_of(transcript) -> SystemVoice | None:
    pk = _block(transcript).get("voice")
    return SystemVoice.objects.filter(pk=pk).first() if pk else None


def give_back(transcript, segment_id: int, *, by, request=None) -> str:
    """Not the system, on the guided page: the line goes back to the label
    the recogniser had; it is never given again by voice. Guard 5: the
    month's count, and the giving stops at BACK_TO_STOP."""
    block = _block(transcript)
    by_voice = dict(block.get("by_voice") or {})
    sid = str(segment_id)
    if sid not in by_voice:
        raise ValueError("That line was not given by the phone system's voice.")
    was = by_voice.pop(sid)
    transcript.segments.filter(pk=segment_id).update(speaker=was)
    back = dict(block.get("back") or {})
    back[sid] = was
    block["by_voice"], block["back"] = by_voice, back
    _save_block(transcript, block)
    voice = _voice_of(transcript)
    stopped = False
    if voice is not None:
        bump(voice, back=1)
        if voice.giving and month_counts(voice)["back"] >= BACK_TO_STOP:
            voice.giving = False
            voice.called_out_at = timezone.now()
            stopped = True
        voice.save(update_fields=["months", "giving", "called_out_at"])
    recording = transcript.recording
    audit.write(
        audit.Category.EDITS,
        "Phone system line given back",
        actor=by,
        request=request,
        object_type="recording",
        object_id=str(recording.pk),
        object_label=recording.title,
        stopped=stopped,
    )
    if stopped and voice is not None:
        audit.write(
            audit.Category.SYSTEM,
            "Phone system called out",
            system="voices",
            object_type="phone system",
            object_id=str(voice.pk),
            object_label=voice.name,
            back=month_counts(voice)["back"],
        )
    return was


def give_again(transcript, segment_id: int, *, by, request=None) -> None:
    """The system after all: a line given back goes to the Call system
    once more, by hand this time."""
    block = _block(transcript)
    back = dict(block.get("back") or {})
    sid = str(segment_id)
    if sid not in back:
        raise ValueError("That line was not given back.")
    was = back.pop(sid)
    transcript.segments.filter(pk=segment_id).update(speaker=call_system.NAME)
    by_voice = dict(block.get("by_voice") or {})
    by_voice[sid] = was
    block["by_voice"], block["back"] = by_voice, back
    _save_block(transcript, block)
    recording = transcript.recording
    audit.write(
        audit.Category.EDITS,
        "Phone system line given again",
        actor=by,
        request=request,
        object_type="recording",
        object_id=str(recording.pk),
        object_label=recording.title,
    )


# The pages ----------------------------------------------------------------------------


def page_state(transcript) -> dict | None:
    """What the guided page says of the phone system on this recording:
    the lines by words, by voice (each with its way back), the ones given
    back, the ones held, and whether the voice gives or only counts."""
    if transcript is None or not on():
        return None
    from core import exports

    block = _block(transcript)
    if not block:
        return None
    by_voice = block.get("by_voice") or {}
    back = block.get("back") or {}
    system_total = transcript.segments.filter(speaker=call_system.NAME).count()

    def line(sid: str, was: str) -> dict | None:
        one = transcript.segments.filter(pk=int(sid)).first()
        if one is None:
            return None
        return {
            "segment": one.pk,
            "start": one.start,
            "end": one.end,
            "clock": exports.clock(one.start),
            "quote": one.text[:120],
            "was": was,
        }

    voice = _voice_of(transcript)
    return {
        "words": max(system_total - len(by_voice), 0),
        "voice": len(by_voice),
        "would": int(block.get("voice_would") or 0),
        "held": dict(block.get("held") or {}),
        "giving": bool(voice.giving) if voice is not None else False,
        "name": voice.name if voice is not None else "",
        "voice_lines": [
            one
            for one in (line(sid, was) for sid, was in sorted(by_voice.items()))
            if one
        ],
        "back_lines": [
            one for one in (line(sid, was) for sid, was in sorted(back.items())) if one
        ],
    }


def heard_of(voice: SystemVoice, user) -> dict | None:
    """One announcement the reader may hear: a word-found system line on a
    call that taught the print and that the reader may open."""
    from core import cases
    from core.jobs import Segment
    from core.recordings import Recording

    for rid in voice.parts or {}:
        recording = Recording.objects.filter(pk=rid).select_related("user").first()
        if recording is None or user is None or not cases.standing(recording, user):
            continue
        row = (
            Segment.objects.filter(
                transcript__recording_id=rid, speaker=call_system.NAME
            )
            .order_by("start")
            .values_list("start", "end")
            .first()
        )
        if row is None:
            continue
        return {
            "recording": str(recording.pk),
            "start": row[0],
            "title": recording.title,
        }
    return None


def rows_for(user) -> list[dict]:
    """The Phone systems tab: one row per system the office has met."""
    out = []
    for voice in SystemVoice.objects.all():
        parts = voice.parts or {}
        out.append(
            {
                "voice": voice,
                "live": voice.live,
                "calls": len(parts),
                "lines": sum(int(one.get("lines", 0)) for one in parts.values()),
                "minutes": round(
                    sum(float(one.get("seconds", 0)) for one in parts.values()) / 60, 1
                ),
                "month": month_counts(voice),
                "totals": totals(voice),
                "heard": heard_of(voice, user),
                "well_taught": len(parts) >= 3,
            }
        )
    return out


def set_giving(voice: SystemVoice, giving: bool, *, by, request=None) -> None:
    if voice.giving == giving:
        return
    voice.giving = giving
    if giving:
        voice.called_out_at = None
    voice.save(update_fields=["giving", "called_out_at"])
    audit.write(
        audit.Category.ADMIN,
        "Phone system giving started" if giving else "Phone system giving stopped",
        actor=by,
        request=request,
        object_type="phone system",
        object_id=str(voice.pk),
        object_label=voice.name,
    )


def rename(voice: SystemVoice, name: str, *, by, request=None) -> None:
    wanted = (name or "").strip()[:60]
    if not wanted:
        raise ValueError("A phone system needs a name.")
    was = voice.name
    if wanted == was:
        return
    voice.name = wanted
    voice.save(update_fields=["name"])
    audit.write(
        audit.Category.ADMIN,
        "Phone system renamed",
        actor=by,
        request=request,
        object_type="phone system",
        object_id=str(voice.pk),
        object_label=wanted,
    )


def forget(voice: SystemVoice, *, by, request=None) -> None:
    """The print goes with its row; the next call makes it again, off."""
    name, pk = voice.name, str(voice.pk)
    voice.delete()
    audit.write(
        audit.Category.ADMIN,
        "Phone system forgotten",
        actor=by,
        request=request,
        object_type="phone system",
        object_id=pk,
        object_label=name,
    )


def forget_everything() -> int:
    """The Call system switch goes off: the phone systems' prints go too."""
    count, _ = SystemVoice.objects.all().delete()
    return count
