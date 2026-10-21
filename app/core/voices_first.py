"""Voices first (Phase 5 chapter 3 as rewritten in v1.145.0; the drawing
docs/spec/mockups/phase-5-voices-first.html, chosen 2026-10-21).

On a recording the voice listens to (Voices help the check lists its type)
the Speaker check's run is turned over. As the transcript lands the voice
step does its work: the cast as voices with their prints, the hand-overs,
the Sounds like against the Case's prints, and the lines in doubt (a line
whose print sits nearer another speaker's than its own, a line the voice
cannot tell between two, a line that carries two voices); the words run
only for names, which become hints on the cards. Then the page has three
stages: who is speaking (the person names the voices), lines in doubt (the
person decides the voice's lines, with the words' second reading of them
arriving after the voice), and done (the words read the whole call once,
against the named cast, and propose what little is left).

With the voice off for the recording's type the run is as before: the
words at arrival, no stages. Nothing is named by the voice alone.
"""

from __future__ import annotations

import logging
import time

from django.db import transaction
from django.utils import timezone

from core import assistant, audit, call_system, engine, prompts, voices
from core.assistant import DONE, PromptTemplate, SpeakerCheck, SpeakerCorrection

log = logging.getLogger(__name__)

VOICES, WORDS = "voices", "words"
STAGES = (1, 2, 3)
# Lines in doubt: near another speaker's print (the voice's own proposals,
# more of them than the words-first run allowed), the voice unable to tell
# between two, and the lines that carry two voices.
DOUBT_CAP = 80
UNSURE_CAP = 40
MIXED_LEAST_WORDS = 2
MIXED_LEAST_SECONDS = 1.0
# The words' second reading of the lines in doubt: so many lines a call.
READING_BATCH = 24
READING_CONTEXT = 2
FEATURE = "speaker_check"


def on_for(recording) -> bool:
    """Voices first applies where the voice listens (ADR 0021, per type)."""
    return voices.on_for(recording)


def mode_of(check) -> str:
    return ((check.second_look or {}).get("mode") or "") if check else ""


def latest_done(transcript):
    return transcript.speaker_checks.filter(state=DONE).first()


def stage_of(transcript) -> int | None:
    """The stage the page is at, or None when the run was not voices first."""
    run = latest_done(transcript)
    if run is None:
        return None
    look = run.second_look or {}
    if look.get("mode") != VOICES and not look.get("stage"):
        return None
    return int(look.get("stage") or 1)


# The lines in doubt --------------------------------------------------------------


def owners(transcript) -> dict[str, str]:
    """The engine's label -> the speaker who wears it now, by most lines."""
    counts: dict[str, dict[str, int]] = {}
    for label, speaker in (
        transcript.segments.filter(same_as_other_side=False)
        .exclude(speaker="")
        .exclude(speaker_label="")
        .values_list("speaker_label", "speaker")
    ):
        counts.setdefault(label, {})
        counts[label][speaker] = counts[label].get(speaker, 0) + 1
    return {
        label: max(by.items(), key=lambda kv: kv[1])[0] for label, by in counts.items()
    }


def mixed_lines(transcript, taken: set) -> list[dict]:
    """Lines whose words the diarizer gave to two labels: a run of at least
    two words at the end (or the start) wearing another speaker's label, a
    second long enough. Each is a proposal to split the line at that word
    and give that part to the label's owner."""
    owner = owners(transcript)
    rows = []
    for seg in (
        transcript.segments.filter(same_as_other_side=False)
        .exclude(speaker="")
        .order_by("start", "id")
    ):
        if seg.pk in taken or call_system.is_system(seg.speaker):
            continue
        words = [w for w in (seg.words or []) if isinstance(w, dict)]
        if len(words) < 2 * MIXED_LEAST_WORDS:
            continue
        own = seg.speaker_label or ""
        labels = [w.get("speaker") or own for w in words]
        i = len(labels)
        while i > 0 and labels[i - 1] != own:
            i -= 1
        tail = len(labels) - i
        j = 0
        while j < len(labels) and labels[j] != own:
            j += 1
        head = j
        if MIXED_LEAST_WORDS <= tail < len(labels):
            foreign, part, at = labels[-1], "second", i
            try:
                seconds = float(words[-1]["end"]) - float(words[i]["start"])
            except (KeyError, TypeError, ValueError):
                continue
        elif MIXED_LEAST_WORDS <= head < len(labels):
            foreign, part, at = labels[0], "first", head
            try:
                seconds = float(words[head - 1]["end"]) - float(words[0]["start"])
            except (KeyError, TypeError, ValueError):
                continue
        else:
            continue
        if seconds < MIXED_LEAST_SECONDS:
            continue
        to = owner.get(foreign, "")
        if not to or to == seg.speaker or call_system.is_system(to):
            continue
        rows.append(
            {
                "segment_id": seg.pk,
                "start": seg.start,
                "quote": (seg.text or "")[:300],
                "from": seg.speaker,
                "to": to,
                "reason": f"two voices: the {part} part sounds like {to}",
                "voice": SpeakerCorrection.VOICE_AGREES,
                "source": SpeakerCorrection.VOICE,
                "split_at": at,
                "split_part": part,
            }
        )
    return rows


def doubt_rows(transcript, judge, kept: dict) -> dict:
    """The lines in doubt added to `kept`: near another speaker (the voice's
    own proposals, under the doubt cap), the voice unable to tell between
    two, and the mixed lines. Returns the counts."""
    from core.jobs import Segment

    counts = {"near": 0, "unsure": 0, "mixed": 0}
    taken = set(kept)
    proposals = judge.own_proposals(taken, DOUBT_CAP)
    lines = {
        seg.pk: seg
        for seg in Segment.objects.filter(pk__in=[p["segment_id"] for p in proposals])
    }
    for one in proposals:
        seg = lines.get(one["segment_id"])
        if seg is None or seg.speaker != one["from"]:
            continue
        kept[one["segment_id"]] = {
            "segment_id": one["segment_id"],
            "start": seg.start,
            "quote": (seg.text or "")[:300],
            "from": one["from"],
            "to": one["to"],
            "reason": f"the voice sounds like {one['to']}",
            "voice": SpeakerCorrection.VOICE_AGREES,
            "source": SpeakerCorrection.VOICE,
        }
        counts["near"] += 1
    taken = set(kept)
    unsure = judge.unsure_lines(taken, UNSURE_CAP)
    lines = {
        seg.pk: seg
        for seg in Segment.objects.filter(pk__in=[u["segment_id"] for u in unsure])
    }
    for one in unsure:
        seg = lines.get(one["segment_id"])
        if seg is None or seg.speaker != one["from"]:
            continue
        kept[one["segment_id"]] = {
            "segment_id": one["segment_id"],
            "start": seg.start,
            "quote": (seg.text or "")[:300],
            "from": one["from"],
            "to": one["to"],
            "reason": f"the voice cannot tell between {one['from']} and {one['to']}",
            "voice": "",
            "source": SpeakerCorrection.VOICE,
        }
        counts["unsure"] += 1
    for one in mixed_lines(transcript, set(kept)):
        kept[one["segment_id"]] = one
        counts["mixed"] += 1
    return counts


# The arrival run -------------------------------------------------------------------


def arrival(check, transcript, recording) -> bool:
    """The voices-first run: no engine call for moves. Returns False when the
    voice could not be read, and the words run as before."""
    from core import speaker_check, voice_prints

    kept: dict = {}
    summary = speaker_check._voice_notes(transcript, kept, check, doubt=True)
    if summary.get("voice") != "titanet":
        return False
    summary["mode"] = VOICES
    summary["stage"] = 1
    check.second_look = summary
    speaker_check._store(transcript, kept)
    speaker_check._store_handovers(
        transcript, check, check.second_look.get("handovers") or []
    )
    check.second_look["handovers"] = len(check.second_look.get("handovers") or [])
    check.found = len(kept)
    check.windows = 0
    check.cut_short = 0
    check.state = DONE
    check.reason_class = ""
    check.finished_at = timezone.now()
    check.save()
    audit.write(
        audit.Category.RECORDINGS,
        "Voices read first",
        actor=check.asked_by,
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
        lines_in_doubt=len(kept),
        **(summary.get("doubt") or {}),
        handovers=check.second_look["handovers"],
    )
    speaker_check._names_pass(check)
    try:
        voice_prints.match(check)
    except Exception:  # noqa: BLE001 - a match is a proposal, never the run
        log.exception("speaker check for %s: the voice matches failed", transcript.pk)
    return True


def after_words_run(check) -> None:
    """The words have run: the mode says so, and where a voices-first run
    came before, the page is at its third stage."""
    look = dict(check.second_look or {})
    look["mode"] = WORDS
    earlier = (
        check.transcript.speaker_checks.filter(state=DONE)
        .exclude(pk=check.pk)
        .order_by("-created")
        .first()
    )
    if earlier is not None and (earlier.second_look or {}).get("mode") == VOICES:
        look["stage"] = 3
    check.second_look = look
    check.save(update_fields=["second_look"])


# The stages -------------------------------------------------------------------------


def set_stage(transcript, stage: int, *, by=None, request=None) -> dict:
    """The person moves to a stage: 2 asks the words for their second
    reading of the lines in doubt; 3 queues the words' run over the whole
    call against the named cast; 1 just shows the voices again."""
    from core import speaker_check, tasks

    run = latest_done(transcript)
    if run is None or stage not in STAGES:
        return {"ok": False, "error": "no run to stage"}
    look = dict(run.second_look or {})
    look["stage"] = stage
    queued = ""
    if stage == 2:
        reading = look.get("reading") or {}
        if reading.get("state") not in ("queued", "running", "done"):
            look["reading"] = {"state": "queued"}
            queued = "reading"
            transaction.on_commit(lambda: tasks.read_doubts.defer(check_id=str(run.pk)))
    run.second_look = look
    run.save(update_fields=["second_look"])
    if stage == 3:
        made = speaker_check.queue_check(
            transcript.recording, by=by, how="stage 3", mode=WORDS
        )
        queued = "words" if made is not None else ""
    audit.write(
        audit.Category.RECORDINGS,
        "Speakers stage moved",
        actor=by,
        request=request,
        object_type="recording",
        object_id=transcript.recording.pk,
        object_label=transcript.recording.original_filename,
        stage=stage,
        queued=queued,
    )
    return {"ok": True, "stage": stage, "queued": queued}


def doubt_counts(transcript) -> dict:
    rows = transcript.corrections.filter(
        state=SpeakerCorrection.PENDING, source=SpeakerCorrection.VOICE
    )
    mixed = rows.exclude(split_at=None).count()
    return {
        "near": rows.filter(split_at=None).exclude(voice="").count(),
        "unsure": rows.filter(split_at=None, voice="").count(),
        "mixed": mixed,
        "agree": rows.filter(words=SpeakerCorrection.VOICE_AGREES).count(),
        "words_against": rows.filter(words=SpeakerCorrection.VOICE_AGAINST).count(),
    }


# The words' second reading --------------------------------------------------------


def read_doubts(check_id) -> None:
    """Stage 2: one narrow engine call (a few at most) for the lines in
    doubt, with the named cast in hand: which of these speakers said each.
    The answer lands on each row as the words' word, agreeing with the voice
    or not; a problem leaves the voice's rows as they are and says so."""
    from core import speaker_check

    check = (
        SpeakerCheck.objects.filter(pk=check_id)
        .select_related("transcript", "transcript__recording")
        .first()
    )
    if check is None:
        return
    transcript = check.transcript
    recording = transcript.recording
    look = dict(check.second_look or {})
    look["reading"] = {"state": "running"}
    check.second_look = look
    check.save(update_fields=["second_look"])
    rows = list(
        transcript.corrections.filter(
            state=SpeakerCorrection.PENDING, source=SpeakerCorrection.VOICE
        ).order_by("start")
    )
    started = time.monotonic()
    usage = {"input_tokens": 0, "output_tokens": 0}
    model = ""
    agree = against = other = 0
    try:
        if not rows:
            raise engine.Problem(engine.ERROR, "nothing in doubt")
        problem = assistant._unreachable()
        if problem:
            raise problem
        speakers = speaker_check.speakers_of(transcript)
        ground = PromptTemplate.named(PromptTemplate.GROUND_RULES)
        system = prompts.system_message(
            ground.text, prompts.LINES_IN_DOUBT, prompts.LINES_IN_DOUBT_FORMAT
        )
        lines = prompts.lines_of(transcript, without_system=True)
        by_segment = {line.segment_id: i for i, line in enumerate(lines)}
        number_of = {line.segment_id: line.number for line in lines}
        cast = prompts.cast_lines(transcript, speakers)
        limit = assistant.time_limit(FEATURE)
        for start in range(0, len(rows), READING_BATCH):
            batch = [one for one in rows[start : start + READING_BATCH]]
            blocks = []
            for one in batch:
                i = by_segment.get(one.segment_id)
                if i is None:
                    continue
                around = lines[max(0, i - READING_CONTEXT) : i + READING_CONTEXT + 1]
                blocks.append(
                    prompts.doubt_block(
                        number_of[one.segment_id], one.speaker_from, around
                    )
                )
            if not blocks:
                continue
            user = prompts.lines_in_doubt_input(cast, blocks)
            answer = engine.complete(
                assistant._messages(system, user),
                max_completion_tokens=60 * len(batch) + 100,
                thinking=False,
                timeout=limit,
                schema=prompts.lines_in_doubt_schema(speakers),
                **assistant.SUGGESTION_SAMPLING,
            )
            model = answer.get("model", "") or model
            usage["input_tokens"] += answer.get("input_tokens", 0)
            usage["output_tokens"] += answer.get("output_tokens", 0)
            try:
                parsed = prompts.parse_json(answer["text"])
                raw = parsed.get("lines", [])
                if not isinstance(raw, list):
                    raise ValueError("not a list")
            except (ValueError, AttributeError, KeyError):
                log.warning(
                    "lines in doubt for %s: an answer was unreadable", transcript.pk
                )
                continue
            by_number = {number_of[one.segment_id]: one for one in batch}
            for item in raw:
                if not isinstance(item, dict):
                    continue
                try:
                    row = by_number[int(item.get("line"))]
                except (KeyError, TypeError, ValueError):
                    continue
                said = str(item.get("speaker", "")).strip()
                why = str(item.get("reason", "")).strip()[:120]
                if said == row.speaker_to:
                    row.words = SpeakerCorrection.VOICE_AGREES
                    agree += 1
                elif said == row.speaker_from:
                    row.words = SpeakerCorrection.VOICE_AGAINST
                    against += 1
                elif said in speakers:
                    row.words = ""
                    other += 1
                    why = f"the words read it as {said}'s" + (f": {why}" if why else "")
                else:
                    continue
                row.words_why = why
                row.save(update_fields=["words", "words_why"])
        look["reading"] = {
            "state": "done",
            "rows": len(rows),
            "agree": agree,
            "against": against,
            "other": other,
            "at": timezone.now().isoformat(timespec="seconds"),
        }
        check.second_look = look
        check.save(update_fields=["second_look"])
        assistant._record(
            FEATURE,
            recording,
            actor=check.asked_by,
            templates="lines in doubt",
            model=model,
            usage=usage,
            started=started,
            outcome="ok",
            lines=len(rows),
            agree=agree,
            against=against,
        )
    except engine.Problem as problem:
        look["reading"] = {
            "state": "failed" if problem.reason != engine.ERROR or rows else "done",
            "rows": len(rows),
            "said": assistant.what_to_say(problem.reason) if rows else "",
        }
        check.second_look = look
        check.save(update_fields=["second_look"])
        if rows:
            assistant._record(
                FEATURE,
                recording,
                actor=check.asked_by,
                templates="lines in doubt",
                model=model,
                usage=usage,
                started=started,
                outcome=problem.reason,
                reason=problem.reason,
                lines=len(rows),
            )
