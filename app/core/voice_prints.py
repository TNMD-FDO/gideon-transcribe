"""Voice prints (Phase 5 chapter 2 in force; ADR 0021 decision 6; the voice
plan's V4, v1.144.0): the Case remembers a voice only when told.

A Person's Voice print is one vector, kept as a field of the Person inside
its Case, learnt only from names and matches people accept: when a Speaker
is named inside the Case, the Speaker's print on that recording (the mean
of its lines' vectors, as the voice step builds it) becomes a part of the
Person's print, and the print is the unit mean of its parts. Each part
remembers how it came (by hand, by a match accepted, by the case rule
confirmed), who accepted it and when: that is the chain the Case's Speakers
tab shows and Unlearn undoes.

After a Speaker check's one run on a recording inside a Case, each unnamed
Speaker's print is compared with every Person's print of the Case. A match
is a proposal on the card ("Sounds like Dana Reyes"), rated by the weakest
link of the score, the print's own confidence (one recording rates medium
at best) and how much of the voice was heard; only high and medium are
ever made. Two People over one voice are a conflict, offered together. On
a two-channel call named across the Case by the Side rule, a Side that does
not sound like its Person is an alarm, never a rename.

The per-line vectors still go when the run is done (decision 5); while the
Admin's switch is on, one vector per Speaker label stays on the run so the
print can be learnt when the Speaker is named later. Turning the switch off
deletes every print, every kept label vector and every waiting match, and
stamps each Case. Nothing here is logged but counts; nothing is exported;
the Call system has no print; nothing crosses a Case (the print's scope is
"case"; the field is the hook for the unit's voice book, drawn later).
"""

from __future__ import annotations

import logging

import numpy as np
from django.db import transaction
from django.utils import timezone

from core import audit, call_system, settings_store

log = logging.getLogger(__name__)

HIGH, MEDIUM = "high", "medium"
# Cosine of a Speaker's print to a Person's: at or over HIGH_COS the voice
# is sure, at or over MEDIUM_COS it leans; under, nothing is said. A run's
# own midpoint between same-voice and other-voice scores raises the medium
# line where the recording's voices sit apart.
HIGH_COS = 0.65
MEDIUM_COS = 0.50
# Under this the Side rule's Person is not heard on the Side: the alarm.
AGAINST_COS = 0.35
# The voice heard for less than this many seconds rates medium at best.
SURE_SECONDS = 10.0
# A print from fewer recordings than this rates medium at best.
SURE_PARTS = 2
# Dismissed this often in thirty days, a Person's print is called out.
DISMISSALS_TO_CALL_OUT = 3
HAND, VOICE, RULE = "hand", "voice", "rule"


def on() -> bool:
    """The Admin's switch, Remember voices across a case, with Cases on."""
    return bool(settings_store.get("remember_voices")) and bool(
        settings_store.get("folder_management")
    )


def _unit(vector) -> list[float]:
    arr = np.asarray(vector, dtype="float32")
    n = float(np.linalg.norm(arr))
    return [round(float(x), 5) for x in (arr / n if n else arr)]


def _cos(a, b) -> float:
    return float(np.asarray(_unit(a)) @ np.asarray(_unit(b)))


def _is_a_label(name: str) -> bool:
    from core.assistant import _is_a_label

    return _is_a_label(name)


# What a run keeps -------------------------------------------------------------------


def label_prints(judge) -> dict:
    """One vector per Speaker label from the judge's centroids: the label's
    print on this recording, with how many lines and seconds built it."""
    out: dict = {}
    for (side, name), centre in judge.centroids.items():
        if call_system.is_system(name):
            continue
        members = judge.members.get((side, name), [])
        seconds = sum(judge.stretches[sid]["net"] for sid in members)
        kept = out.get(name)
        if kept is None or seconds > kept["seconds"]:
            out[name] = {
                "vector": _unit(centre),
                "lines": len(members),
                "seconds": round(float(seconds), 1),
            }
    return out


def keep_prints(check, judge) -> None:
    """Kept on the run while the switch is on and the recording is in a
    Case, so a Speaker named later teaches its Person's print."""
    if check is None or judge is None:
        return
    recording = check.transcript.recording
    if not on() or recording.case_id is None:
        check.prints = {}
        return
    check.prints = label_prints(judge)


def print_of(transcript, label: str) -> dict | None:
    """The label's kept print from the newest run that has one, or None."""
    for check in transcript.speaker_checks.exclude(prints={}).order_by("-created"):
        found = (check.prints or {}).get(label)
        if found and found.get("vector"):
            return found
    return None


# Learning -----------------------------------------------------------------------------


def _rebuild(person) -> None:
    kept = person.voice_print or {}
    parts = kept.get("parts") or {}
    if not parts:
        person.voice_print = None
        return
    vectors = [np.asarray(_unit(one["vector"])) for one in parts.values()]
    kept["vector"] = _unit(np.stack(vectors).mean(axis=0))
    kept["scope"] = kept.get("scope") or "case"
    person.voice_print = kept


def learn(recording, label: str, person, *, by, how: str = HAND) -> bool:
    """A Speaker named inside the Case: the label's print on this recording
    becomes a part of the Person's print. True when something was learnt."""
    if person is None or not on() or recording.case_id is None:
        return False
    if call_system.is_system(person.name):
        return False
    transcript = getattr(recording, "transcript", None)
    if transcript is None:
        return False
    # The label's print, or the one already filed under the name when the
    # run's prints followed the name first.
    found = print_of(transcript, label) or print_of(transcript, person.name)
    if found is None:
        return False
    kept = person.voice_print or {"vector": None, "parts": {}, "scope": "case"}
    parts = kept.setdefault("parts", {})
    parts[str(recording.pk)] = {
        "vector": found["vector"],
        "label": label,
        "lines": found.get("lines", 0),
        "seconds": found.get("seconds", 0.0),
        "how": how,
        "by": getattr(by, "username", "") or "",
        "at": timezone.now().isoformat(timespec="seconds"),
    }
    person.voice_print = kept
    _rebuild(person)
    person.voice_unlearnt_at = None
    person.voice_unlearnt_by = ""
    person.save(update_fields=["voice_print", "voice_unlearnt_at", "voice_unlearnt_by"])
    case = person.case
    if case.voices_forgotten_at is not None:
        case.voices_forgotten_at = None
        case.save(update_fields=["voices_forgotten_at"])
    return True


def learn_on_name(recording, label: str, name: str, *, by, how: str = HAND) -> bool:
    """The hook the viewer and the suggestions call once a Speaker label has
    taken a Person's name."""
    if not on() or recording.case_id is None or not _is_a_label(label):
        return False
    from core import people

    person = people.find(recording.case, name)
    return learn(recording, label, person, by=by, how=how)


def forget_recording(recording, name: str) -> bool:
    """Undo of a name: the print forgets this recording's part."""
    if recording.case_id is None:
        return False
    from core import people

    person = people.find(recording.case, name)
    if person is None or not person.voice_print:
        return False
    parts = (person.voice_print or {}).get("parts") or {}
    if str(recording.pk) not in parts:
        return False
    del parts[str(recording.pk)]
    _rebuild(person)
    person.save(update_fields=["voice_print"])
    return True


# Matching -----------------------------------------------------------------------------


def _rating(score: float, part_count: int, seconds: float, medium_line: float) -> str:
    """The weakest link: the score's word, then the print's own confidence,
    then how much of the voice was heard."""
    if score >= HIGH_COS:
        word = HIGH
    elif score >= medium_line:
        word = MEDIUM
    else:
        return ""
    if part_count < SURE_PARTS or seconds < SURE_SECONDS:
        word = MEDIUM
    return word


def match(check) -> int:
    """After a run inside a Case: every unnamed Speaker's print against every
    Person's; the matches, conflicts and the Side alarm as rows the card
    shows. Earlier pending rows of the transcript are replaced. Returns how
    many rows were made."""
    from core import vocabulary
    from core.assistant import VoiceMatch
    from core.people import Person

    transcript = check.transcript
    recording = transcript.recording
    if not on() or recording.case_id is None:
        return 0
    prints = check.prints or {}
    if not prints:
        return 0
    people = [
        one
        for one in Person.objects.filter(case_id=recording.case_id)
        if (one.voice_print or {}).get("vector")
    ]
    if not people:
        return 0
    midpoint = ((check.second_look or {}).get("calibration") or {}).get("midpoint")
    medium_line = max(MEDIUM_COS, float(midpoint)) if midpoint else MEDIUM_COS
    rows: list[VoiceMatch] = []
    for label, kept in prints.items():
        if not _is_a_label(label):
            continue
        for person in people:
            score = _cos(kept["vector"], person.voice_print["vector"])
            parts = (person.voice_print or {}).get("parts") or {}
            word = _rating(
                score, len(parts), float(kept.get("seconds", 0)), medium_line
            )
            if not word:
                continue
            rows.append(
                VoiceMatch(
                    transcript=transcript,
                    run=check,
                    speaker=label,
                    person=person,
                    kind=VoiceMatch.MATCH,
                    rating=word,
                    score=round(score, 3),
                )
            )
    # The Side rule's check: the named Side that does not sound like its Person.
    rule = (
        vocabulary.side_rule(recording.case) if recording.is_two_channel_call else None
    )
    if rule is not None and (rule["person"].voice_print or {}).get("vector"):
        kept = prints.get(rule["person"].name)
        if kept and float(kept.get("seconds", 0)) >= SURE_SECONDS:
            score = _cos(kept["vector"], rule["person"].voice_print["vector"])
            if score < AGAINST_COS:
                rows.append(
                    VoiceMatch(
                        transcript=transcript,
                        run=check,
                        speaker=rule["person"].name,
                        person=rule["person"],
                        kind=VoiceMatch.SIDE,
                        rating=MEDIUM,
                        score=round(score, 3),
                    )
                )
    with transaction.atomic():
        VoiceMatch.objects.filter(
            transcript=transcript, state=VoiceMatch.PENDING
        ).update(state=VoiceMatch.WITHDRAWN, decided_at=timezone.now())
        VoiceMatch.objects.bulk_create(rows)
    return len(rows)


def settle(transcript) -> int:
    """Rows whose Speaker label has gone (named by hand, merged, split) are
    withdrawn; a Side alarm whose Side no longer wears the Person's name too."""
    from core.assistant import VoiceMatch

    labels = set(
        transcript.segments.filter(same_as_other_side=False)
        .exclude(speaker="")
        .values_list("speaker", flat=True)
        .distinct()
    )
    gone = 0
    for row in VoiceMatch.objects.filter(
        transcript=transcript, state=VoiceMatch.PENDING
    ):
        if row.speaker not in labels:
            row.state = VoiceMatch.WITHDRAWN
            row.decided_at = timezone.now()
            row.save(update_fields=["state", "decided_at"])
            gone += 1
    return gone


# What the card shows ------------------------------------------------------------------


def where_heard(person, *, exclude=None) -> list[dict]:
    """Where the Person's voice can be heard: one line per part recording,
    for the card's Preview and the tab's play."""
    from core.jobs import Segment
    from core.recordings import Recording

    parts = (person.voice_print or {}).get("parts") or {}
    out = []
    recordings = {
        str(one.pk): one for one in Recording.objects.filter(pk__in=list(parts))
    }
    for recording_id in parts:
        if exclude is not None and str(exclude) == recording_id:
            continue
        recording = recordings.get(recording_id)
        transcript = getattr(recording, "transcript", None) if recording else None
        if transcript is None:
            continue
        lines = list(
            Segment.objects.filter(transcript=transcript, speaker=person.name)
            .order_by("start")
            .values_list("start", "end")[:40]
        )
        if not lines:
            continue
        long = [one for one in lines if one[1] - one[0] >= 2.0]
        line = (long or lines)[0]
        from core import exports

        out.append(
            {
                "recording": str(recording.pk),
                "title": recording.title,
                "start": line[0],
                "clock": exports.clock(line[0]),
            }
        )
    return out


def rows_for(transcript) -> dict:
    """The waiting matches of one transcript, by Speaker label, with the
    conflicts and the Side alarm told apart, and the labels Unlearn returned."""
    from core.assistant import VoiceMatch

    pending = list(
        VoiceMatch.objects.filter(transcript=transcript, state=VoiceMatch.PENDING)
        .select_related("person")
        .order_by("speaker", "-score")
    )
    by_label: dict[str, list] = {}
    for row in pending:
        by_label.setdefault(row.speaker, []).append(row)
    out = []
    recording = transcript.recording
    # The matches the last re-read made (v1.144.1): "new" on the card.
    done_run = transcript.speaker_checks.filter(state="done").first()
    fresh = (
        set(((done_run.second_look or {}).get("reread") or {}).get("new_matches") or [])
        if done_run
        else set()
    )

    def heard_of(person) -> list[dict]:
        found = where_heard(person)
        for one in found:
            one["here"] = one["recording"] == str(recording.pk)
        # The other recordings first, this one last.
        return sorted(found, key=lambda one: one["here"])

    for label, rows in by_label.items():
        side = [one for one in rows if one.kind == VoiceMatch.SIDE]
        matches = [one for one in rows if one.kind == VoiceMatch.MATCH]
        if side:
            one = side[0]
            out.append(
                {
                    "speaker": label,
                    "kind": "side",
                    "people": [
                        {
                            "id": one.pk,
                            "name": one.person.name,
                            "role": one.person.role,
                            "rating": one.rating,
                            "heard": heard_of(one.person),
                        }
                    ],
                }
            )
        if matches:
            out.append(
                {
                    "speaker": label,
                    "kind": "conflict" if len(matches) > 1 else "match",
                    "people": [
                        {
                            "id": one.pk,
                            "name": one.person.name,
                            "role": one.person.role,
                            "rating": one.rating,
                            "recordings": len(
                                (one.person.voice_print or {}).get("parts") or {}
                            ),
                            "heard": heard_of(one.person),
                            "new": one.pk in fresh,
                        }
                        for one in matches
                    ],
                }
            )
    unlearnt = [
        {"speaker": one.speaker, "person": one.person.name}
        for one in VoiceMatch.objects.filter(
            transcript=transcript, state=VoiceMatch.UNLEARNT
        ).select_related("person")
    ]
    labels = set(transcript.segments.values_list("speaker", flat=True).distinct())
    return {
        "matches": out,
        "unlearnt": [one for one in unlearnt if one["speaker"] in labels],
    }


def suggested_names(transcript) -> dict[str, str]:
    """Label -> the one Person it sounds like, for the picker's pill."""
    from core.assistant import VoiceMatch

    out: dict[str, str] = {}
    seen: dict[str, int] = {}
    for row in VoiceMatch.objects.filter(
        transcript=transcript, state=VoiceMatch.PENDING, kind=VoiceMatch.MATCH
    ).select_related("person"):
        seen[row.speaker] = seen.get(row.speaker, 0) + 1
        out[row.speaker] = row.person.name
    return {label: name for label, name in out.items() if seen[label] == 1}


# Deciding -----------------------------------------------------------------------------


def _row(event: str, case, actor, request=None, **details) -> None:
    audit.write(
        audit.Category.CASES,
        event,
        actor=actor,
        request=request,
        affected_user=(
            case.owner if actor is not None and case.owner_id != actor.pk else None
        ),
        object_type="case",
        object_id=case.pk,
        object_label=case.name,
        **details,
    )


def accept(row, *, by, request=None) -> int:
    """Accept on the card: the Speaker label takes the Person's name on every
    line, as the viewer's rename does and with its Undo; the print learns
    this recording; the other People offered for the voice are set aside.
    A Side alarm accepted ("it is her") keeps the name and teaches the print."""
    from core import people, speaker_check
    from core.assistant import VoiceMatch

    transcript = row.transcript
    recording = transcript.recording
    person = row.person
    changed = 0
    followed = None
    with transaction.atomic():
        if row.kind == VoiceMatch.MATCH and row.speaker != person.name:
            moved = list(
                transcript.segments.filter(speaker=row.speaker).values_list(
                    "pk", flat=True
                )
            )
            changed = transcript.segments.filter(pk__in=moved).update(
                speaker=person.name
            )
            followed = speaker_check.follow(transcript, row.speaker, person.name, by=by)
            changes = list(transcript.speaker_changes or [])
            changes.append(
                {
                    "from": row.speaker,
                    "to": person.name,
                    "segments": moved,
                    "merged": False,
                    "corrections": followed,
                    "voice_match": row.pk,
                    "at": timezone.now().isoformat(),
                }
            )
            transcript.speaker_changes = changes[-20:]
            transcript.save(update_fields=["speaker_changes"])
            people.on_named(
                recording,
                person.name,
                by=by,
                how="sounds like accepted",
                request=request,
            )
        learn(
            recording,
            row.speaker if row.kind == VoiceMatch.MATCH else person.name,
            person,
            by=by,
            how=VOICE if row.kind == VoiceMatch.MATCH else RULE,
        )
        row.state = VoiceMatch.ACCEPTED
        row.decided_by = by
        row.decided_at = timezone.now()
        row.save(update_fields=["state", "decided_by", "decided_at"])
        # The other People offered for this voice are set aside, not turned
        # down: the person chose, and nobody's print is called out for it.
        VoiceMatch.objects.filter(
            transcript=transcript, speaker=row.speaker, state=VoiceMatch.PENDING
        ).exclude(pk=row.pk).update(
            state=VoiceMatch.WITHDRAWN, decided_by=by, decided_at=timezone.now()
        )
    if row.kind == VoiceMatch.MATCH:
        # The re-read after a name (v1.144.1).
        speaker_check.reread_after_name(
            transcript, row.speaker, person.name, by=by, followed=followed
        )
    _row(
        "Sounds like accepted"
        if row.kind == VoiceMatch.MATCH
        else "Side voice confirmed",
        recording.case,
        by,
        request,
        rating=row.rating,
        segments_changed=changed,
    )
    return changed


def dismiss(row, *, by, request=None) -> None:
    """Not her: the match is set aside for this recording; the print is not
    taught by a refusal."""
    from core.assistant import VoiceMatch

    row.state = VoiceMatch.DISMISSED
    row.decided_by = by
    row.decided_at = timezone.now()
    row.save(update_fields=["state", "decided_by", "decided_at"])
    _row(
        "Sounds like dismissed"
        if row.kind == VoiceMatch.MATCH
        else "Side voice dismissed",
        row.transcript.recording.case,
        by,
        request,
        rating=row.rating,
    )


def dismissed_lately(person) -> int:
    from core.assistant import VoiceMatch

    since = timezone.now() - timezone.timedelta(days=30)
    return VoiceMatch.objects.filter(
        person=person, state=VoiceMatch.DISMISSED, decided_at__gte=since
    ).count()


# Unlearn ------------------------------------------------------------------------------


def unlearn_preview(person) -> dict:
    """What Unlearn would do, for the box: the recordings the voice named
    (returned), the ones named by hand (kept), the matches waiting (withdrawn)."""
    from core.assistant import VoiceMatch
    from core.recordings import Recording

    parts = (person.voice_print or {}).get("parts") or {}
    titles = {
        str(one.pk): one.title for one in Recording.objects.filter(pk__in=list(parts))
    }
    returned = [
        titles.get(rid, "a recording")
        for rid, part in parts.items()
        if part.get("how") == VOICE
    ]
    kept = [
        titles.get(rid, "a recording")
        for rid, part in parts.items()
        if part.get("how") != VOICE
    ]
    waiting = VoiceMatch.objects.filter(person=person, state=VoiceMatch.PENDING).count()
    return {"returned": returned, "kept": kept, "waiting": waiting}


def unlearn(person, *, by, request=None) -> dict:
    """Unlearn: the print goes; every Speaker the voice named goes back to
    its label and is marked; the names given by hand stay; waiting matches
    are withdrawn. Counts only in the audit row."""
    from core import queue
    from core.assistant import VoiceMatch
    from core.jobs import Transcript

    parts = (person.voice_print or {}).get("parts") or {}
    returned = 0
    recordings_returned = 0
    with transaction.atomic():
        for recording_id, part in parts.items():
            if part.get("how") != VOICE:
                continue
            transcript = Transcript.objects.filter(recording_id=recording_id).first()
            if transcript is None:
                continue
            mine = list(
                transcript.segments.filter(speaker=person.name).values_list(
                    "pk", flat=True
                )
            )
            if not mine:
                continue
            returned += queue.unname(transcript, person.name)
            recordings_returned += 1
            labels = set(
                transcript.segments.filter(pk__in=mine)
                .values_list("speaker", flat=True)
                .distinct()
            )
            # The check's proposals follow the name back to the label, and
            # are re-read for it (v1.144.1).
            from core import speaker_check

            for label in labels:
                followed = speaker_check.follow(transcript, person.name, label, by=by)
                speaker_check.reread_after_name(
                    transcript, person.name, label, by=by, followed=followed
                )
            for label in labels:
                VoiceMatch.objects.create(
                    transcript=transcript,
                    speaker=label,
                    person=person,
                    kind=VoiceMatch.MATCH,
                    rating=MEDIUM,
                    score=0.0,
                    state=VoiceMatch.UNLEARNT,
                    decided_by=by,
                    decided_at=timezone.now(),
                )
        withdrawn = VoiceMatch.objects.filter(
            person=person, state=VoiceMatch.PENDING
        ).update(state=VoiceMatch.WITHDRAWN, decided_by=by, decided_at=timezone.now())
        person.voice_print = None
        person.voice_unlearnt_at = timezone.now()
        person.voice_unlearnt_by = getattr(by, "username", "") or ""
        person.save(
            update_fields=["voice_print", "voice_unlearnt_at", "voice_unlearnt_by"]
        )
    _row(
        "Voice unlearnt",
        person.case,
        by,
        request,
        recordings_returned=recordings_returned,
        segments_returned=returned,
        matches_withdrawn=withdrawn,
    )
    return {
        "recordings_returned": recordings_returned,
        "segments_returned": returned,
        "matches_withdrawn": withdrawn,
    }


def forget_everything(*, by=None) -> dict:
    """The Admin's switch goes Off: every print, every kept label vector and
    every waiting match go; each Case is stamped; the names stay."""
    from core.assistant import SpeakerCheck, VoiceMatch
    from core.cases import Case
    from core.people import Person

    now = timezone.now()
    with transaction.atomic():
        people_count = Person.objects.exclude(voice_print=None).count()
        cases = Case.objects.filter(
            pk__in=Person.objects.exclude(voice_print=None).values_list(
                "case_id", flat=True
            )
        )
        cases_count = cases.update(voices_forgotten_at=now)
        Person.objects.exclude(voice_print=None).update(voice_print=None)
        SpeakerCheck.objects.exclude(prints={}).update(prints={})
        withdrawn = VoiceMatch.objects.filter(state=VoiceMatch.PENDING).update(
            state=VoiceMatch.WITHDRAWN, decided_at=now
        )
    audit.write(
        audit.Category.ADMIN,
        "Voice prints forgotten",
        actor=by,
        people=people_count,
        cases=cases_count,
        matches_withdrawn=withdrawn,
    )
    return {"people": people_count, "cases": cases_count, "matches": withdrawn}


def counts_for_switch() -> dict:
    """What turning the switch off would delete, for the tray's note."""
    from core.people import Person

    held = Person.objects.exclude(voice_print=None)
    return {
        "people": held.count(),
        "cases": held.values("case_id").distinct().count(),
    }


# The Case's tab --------------------------------------------------------------------


def _nothing(case) -> dict:
    return {
        "remember": on(),
        "per_person": {},
        "side_alarms": [],
        "decided": [],
        "per_person_counts": [],
        "with_print": 0,
        "waiting": 0,
        "forgotten_at": case.voices_forgotten_at,
        "any_voice": False,
    }


def tab_rows(case, people) -> dict:
    """What the tab's Voice column and its blocks read: per Person the print's
    state, the chain, the matches waiting; the Side alarms; the counts. A
    fixed handful of queries whatever the case's size (the tab's budget):
    with the switch off and nothing remembered, two."""
    from django.db.models import Count

    from core import exports
    from core.assistant import Handover, SpeakerCorrection, Suggestion, VoiceMatch
    from core.jobs import Segment
    from core.recordings import Recording

    remember = on()
    with_prints = [one for one in people if (one.voice_print or {}).get("vector")]
    unlearnt = [one for one in people if one.voice_unlearnt_at is not None]
    transcripts_in_case = list(
        Recording.objects.filter(case=case, transcript__isnull=False).values_list(
            "transcript__pk", flat=True
        )
    )
    rows = list(
        VoiceMatch.objects.filter(transcript_id__in=transcripts_in_case)
        .select_related("person", "transcript__recording")
        .order_by("speaker")
    )
    if not with_prints and not unlearnt and not rows:
        return _nothing(case)

    pending = [one for one in rows if one.state == VoiceMatch.PENDING]
    since = timezone.now() - timezone.timedelta(days=30)
    dismissed_lately: dict = {}
    accepted: dict = {}
    dismissed: dict = {}
    for one in rows:
        if one.kind != VoiceMatch.MATCH:
            continue
        if one.state == VoiceMatch.ACCEPTED:
            accepted[one.person_id] = accepted.get(one.person_id, 0) + 1
        elif one.state == VoiceMatch.DISMISSED:
            dismissed[one.person_id] = dismissed.get(one.person_id, 0) + 1
            if one.decided_at and one.decided_at >= since:
                dismissed_lately[one.person_id] = (
                    dismissed_lately.get(one.person_id, 0) + 1
                )
    waiting_by_person: dict = {}
    side_alarms = []
    claims: dict = {}
    for row in pending:
        if row.kind == VoiceMatch.SIDE:
            side_alarms.append(
                {
                    "person": row.person.name,
                    "recording": row.transcript.recording,
                    "speaker": row.speaker,
                }
            )
            continue
        claims.setdefault((row.transcript_id, row.speaker), []).append(row.person_id)
        waiting_by_person.setdefault(row.person_id, []).append(
            {
                "recording": row.transcript.recording,
                "speaker": row.speaker,
                "rating": row.rating,
                "key": (row.transcript_id, row.speaker),
            }
        )
    for rows_of in waiting_by_person.values():
        for one in rows_of:
            one["others"] = len(claims.get(one.pop("key"), [])) - 1

    # The recordings the prints were taught from: titles once, and one line
    # of each Person on each, for "hear them" and the chain.
    part_ids: set = set()
    for person in with_prints:
        part_ids.update((person.voice_print or {}).get("parts") or {})
    titles = {
        str(pk): title
        for pk, title in Recording.objects.filter(pk__in=list(part_ids)).values_list(
            "pk", "title"
        )
    }
    lines: dict = {}
    if part_ids and with_prints:
        for rid, name, start, end in (
            Segment.objects.filter(
                transcript__recording_id__in=list(part_ids),
                speaker__in=[one.name for one in with_prints],
            )
            .order_by("start")
            .values_list("transcript__recording_id", "speaker", "start", "end")
        ):
            kept = lines.setdefault((str(rid), name), [])
            if len(kept) < 40:
                kept.append((start, end))

    def heard(person) -> dict | None:
        for rid in (person.voice_print or {}).get("parts") or {}:
            found = lines.get((rid, person.name))
            if not found:
                continue
            long = [one for one in found if one[1] - one[0] >= 2.0]
            start = (long or found)[0][0]
            return {
                "recording": rid,
                "title": titles.get(rid, "a recording"),
                "start": start,
                "clock": exports.clock(start),
            }
        return None

    per_person: dict = {}
    for person in people:
        kept = person.voice_print or {}
        parts = kept.get("parts") or {}
        chain = []
        for rid, part in sorted(parts.items(), key=lambda kv: kv[1].get("at", "")):
            when = (part.get("at") or "")[:10]
            how = {
                HAND: "named by hand",
                VOICE: "matched by voice",
                RULE: "the case rule confirmed",
            }.get(part.get("how"), "named")
            chain.append(
                f"{how} on {titles.get(rid, 'a recording')}"
                + (f" ({when}, {part['by']})" if part.get("by") else f" ({when})")
            )
        has_print = bool(kept.get("vector"))
        preview = None
        if has_print:
            preview = {
                "returned": [
                    titles.get(rid, "a recording")
                    for rid, part in parts.items()
                    if part.get("how") == VOICE
                ],
                "kept": [
                    titles.get(rid, "a recording")
                    for rid, part in parts.items()
                    if part.get("how") != VOICE
                ],
                "waiting": len(waiting_by_person.get(person.pk, [])),
            }
        per_person[person.pk] = {
            "has_print": has_print,
            "parts": len(parts),
            "chain": chain,
            "heard": heard(person) if has_print else None,
            "waiting": waiting_by_person.get(person.pk, []),
            "unlearnt_at": person.voice_unlearnt_at,
            "unlearnt_by": person.voice_unlearnt_by,
            "called_out": dismissed_lately.get(person.pk, 0) >= DISMISSALS_TO_CALL_OUT,
            "medium_at_best": 0 < len(parts) < SURE_PARTS,
            "preview": preview,
        }

    # Decided so far in this case, per source: one grouped count per table.
    def grouped(rows_q, keys) -> dict:
        return {
            tuple(one[k] for k in keys): one["n"]
            for one in rows_q.values(*keys).annotate(n=Count("id"))
        }

    corrections = grouped(
        SpeakerCorrection.objects.filter(transcript_id__in=transcripts_in_case),
        ("source", "state"),
    )
    handovers = grouped(
        Handover.objects.filter(transcript_id__in=transcripts_in_case), ("state",)
    )
    suggestions = grouped(
        Suggestion.objects.filter(transcript_id__in=transcripts_in_case), ("state",)
    )
    match_states: dict = {}
    for one in rows:
        if one.kind == VoiceMatch.MATCH:
            match_states[one.state] = match_states.get(one.state, 0) + 1
    decided = [
        {
            "source": "Moves from the words",
            "accepted": corrections.get(
                (SpeakerCorrection.WORDS, SpeakerCorrection.ACCEPTED), 0
            ),
            "dismissed": corrections.get(
                (SpeakerCorrection.WORDS, SpeakerCorrection.DISMISSED), 0
            ),
        },
        {
            "source": "Moves from the voice",
            "accepted": corrections.get(
                (SpeakerCorrection.VOICE, SpeakerCorrection.ACCEPTED), 0
            ),
            "dismissed": corrections.get(
                (SpeakerCorrection.VOICE, SpeakerCorrection.DISMISSED), 0
            ),
        },
        {
            "source": "Hand-overs",
            "accepted": handovers.get((Handover.ACCEPTED,), 0),
            "dismissed": handovers.get((Handover.DISMISSED,), 0),
        },
        {
            "source": "Names from the words",
            "accepted": suggestions.get((Suggestion.ACCEPTED,), 0),
            "dismissed": suggestions.get((Suggestion.REJECTED,), 0),
        },
        {
            "source": "Sounds like",
            "accepted": match_states.get(VoiceMatch.ACCEPTED, 0),
            "dismissed": match_states.get(VoiceMatch.DISMISSED, 0),
        },
    ]
    mentioned = {one.person_id for one in rows if one.kind == VoiceMatch.MATCH}
    per_person_counts = [
        {
            "person": person,
            "accepted": accepted.get(person.pk, 0),
            "dismissed": dismissed.get(person.pk, 0),
            "waiting": len(per_person[person.pk]["waiting"]),
            "unlearnt": person.voice_unlearnt_at is not None,
        }
        for person in people
        if per_person[person.pk]["has_print"]
        or person.voice_unlearnt_at is not None
        or person.pk in mentioned
    ]
    with_print = len(with_prints)
    waiting = sum(len(one["waiting"]) for one in per_person.values())
    return {
        "remember": remember,
        "per_person": per_person,
        "side_alarms": side_alarms,
        "decided": decided,
        "per_person_counts": per_person_counts,
        "with_print": with_print,
        "waiting": waiting,
        "forgotten_at": case.voices_forgotten_at,
        "any_voice": True,
    }
