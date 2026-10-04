"""Names across many recordings (Phase 9 chapter 2).

The engine mishears names, and across 800 calls one person is "von
carutthers" in one transcript and "voncaruther" in the next. A Case keeps
the names and places it has learned, each with the spellings the engine has
been heard to give it (Also heard as), and the app uses them wherever it
reads: the names go to recognition with every recording added to the Case
(between the Office Vocabulary and the Batch's own), the spellings stand for
their name in Search and Find (marked also heard as), and Gideon is told
both. A Person of the Case is an entry by itself. No Transcript is ever
rewritten by any of it.

The same chapter names a voice across the Case: on a jail call one side is
the same person on every call, so the Speakers tab says once "On every call
in this case, Side 1 is Pike" and that side is named on every two-channel
call that has a transcript, now and as each later one lands. A call whose
side somebody named by hand keeps the hand's name.
"""

from __future__ import annotations

import re

from core import audit
from core.people import CaseTerm, Person

TERM_MOST = 120
SPELLINGS_MOST = 20


def parse_spellings(text: str) -> list[str]:
    """The Also heard as box: spellings with commas or on their own lines,
    trimmed, no repeats, at most twenty, each at most 120 characters."""
    out: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[,\n;]+", text or ""):
        one = " ".join(part.split())[:TERM_MOST]
        key = one.casefold()
        if one and key not in seen:
            seen.add(key)
            out.append(one)
        if len(out) >= SPELLINGS_MOST:
            break
    return out


def entries(case) -> list[dict]:
    """The Case vocabulary block's rows: the People first, then the terms."""
    rows = []
    for person in Person.objects.filter(case=case).order_by("name"):
        rows.append(
            {
                "kind": "person",
                "id": person.pk,
                "name": person.name,
                "role": person.role,
                "spellings": list(person.also_heard_as or []),
            }
        )
    for term in CaseTerm.objects.filter(case=case).order_by("term"):
        rows.append(
            {
                "kind": "term",
                "id": term.pk,
                "name": term.term,
                "role": "",
                "spellings": list(term.also_heard_as or []),
            }
        )
    return rows


def names_in(case) -> list[str]:
    """The names recognition is given: the People's names and the terms,
    never a spelling (a spelling is what the engine got wrong)."""
    if case is None:
        return []
    names = list(Person.objects.filter(case=case).values_list("name", flat=True))
    names += list(CaseTerm.objects.filter(case=case).values_list("term", flat=True))
    out: list[str] = []
    seen: set[str] = set()
    for one in names:
        key = one.strip().casefold()
        if key and key not in seen:
            seen.add(key)
            out.append(one.strip())
    return out


def count_in(case) -> int:
    return (
        Person.objects.filter(case=case).count()
        + CaseTerm.objects.filter(case=case).count()
    )


def _squeezed(text: str) -> str:
    return "".join(text.split()).casefold()


def heard_as(case, words) -> list[str]:
    """What else Search looks for when the words typed are a listed name or
    one of its spellings: the name and its other spellings, each as a phrase,
    and the joined and split forms of a name of more than one word, since a
    name run together or broken apart is the engine's commonest slip. Nothing
    when the words are no listed name."""
    if case is None or not words:
        return []
    typed = " ".join(" ".join(words).split()).casefold()
    if not typed:
        return []
    joined = _squeezed(typed)
    found: list[str] = []
    seen: set[str] = {typed}

    def take(phrase: str) -> None:
        key = " ".join(phrase.split()).casefold()
        if key and key not in seen:
            seen.add(key)
            found.append(" ".join(phrase.split()))

    for entry in entries(case):
        forms = [entry["name"], *entry["spellings"]]
        keys = {" ".join(one.split()).casefold() for one in forms}
        squeezed = {_squeezed(one) for one in forms}
        if typed not in keys and joined not in squeezed:
            continue
        for one in forms:
            take(one)
            if " " in one.strip():
                take("".join(one.split()).lower())
    return found


# Changing the list -----------------------------------------------------------


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
        entries=count_in(case),
        **details,
    )


def add_term(case, term: str, spellings: str, *, by, request=None) -> CaseTerm | None:
    """A name or a place typed on the case, with its spellings; a term already
    there, or a Person's name, gains the spellings instead."""
    name = " ".join((term or "").split())[:TERM_MOST]
    if not name:
        return None
    heard = parse_spellings(spellings)
    person = Person.objects.filter(case=case, name__iexact=name).first()
    if person is not None:
        set_person_spellings(person, heard, by=by, request=request, add=True)
        return None
    found = CaseTerm.objects.filter(case=case, term__iexact=name).first()
    if found is not None:
        merged = list(found.also_heard_as or [])
        for one in heard:
            if one.casefold() not in {m.casefold() for m in merged}:
                merged.append(one)
        found.also_heard_as = merged[:SPELLINGS_MOST]
        found.save(update_fields=["also_heard_as"])
        _row("case vocabulary changed", case, by, request)
        return found
    found = CaseTerm.objects.create(
        case=case, term=name, also_heard_as=heard, added_by=by
    )
    _row("case vocabulary added", case, by, request)
    return found


def set_term_spellings(term: CaseTerm, spellings: str, *, by, request=None) -> None:
    term.also_heard_as = parse_spellings(spellings)
    term.save(update_fields=["also_heard_as"])
    _row("case vocabulary changed", term.case, by, request)


def remove_term(term: CaseTerm, *, by, request=None) -> None:
    case = term.case
    term.delete()
    _row("case vocabulary removed", case, by, request)


def set_person_spellings(
    person: Person, spellings, *, by, request=None, add: bool = False
) -> None:
    """A Person's Also heard as spellings; `add` keeps the ones there."""
    heard = parse_spellings(spellings) if isinstance(spellings, str) else spellings
    if add:
        merged = list(person.also_heard_as or [])
        for one in heard:
            if one.casefold() not in {m.casefold() for m in merged}:
                merged.append(one)
        heard = merged[:SPELLINGS_MOST]
    person.also_heard_as = heard
    person.save(update_fields=["also_heard_as"])
    _row("case vocabulary changed", person.case, by, request)


# A voice named across the case ----------------------------------------------------


def side_rule(case) -> dict | None:
    """The rule as the Speakers tab shows it, or None."""
    if not case.side_number or case.side_person_id is None:
        return None
    return {"side": case.side_number, "person": case.side_person}


def set_side_rule(case, side: int, person: Person, *, by, request=None) -> int:
    """Side 1 or 2 of every two-channel call in the case is this Person, now
    and as each later call lands. Returns how many calls were named now."""
    case.side_number = side
    case.side_person = person
    case.save(update_fields=["side_number", "side_person"])
    named = sum(apply_side_rule(recording) for recording in case.recordings.all())
    _row(
        "side named across the case",
        case,
        by,
        request,
        side=side,
        calls=named,
    )
    return named


def clear_side_rule(case, *, by, request=None) -> None:
    case.side_number = None
    case.side_person = None
    case.save(update_fields=["side_number", "side_person"])
    _row("side rule removed", case, by, request)


def apply_side_rule(recording) -> int:
    """Name the rule's side on one two-channel call whose side still wears
    the engine's label; 1 when it did, 0 when there was nothing to do."""
    from core.assistant import _is_a_label
    from core.jobs import Segment

    case = recording.case
    if case is None or not recording.is_two_channel_call:
        return 0
    rule = side_rule(case)
    if rule is None or not hasattr(recording, "transcript"):
        return 0
    lines = Segment.objects.filter(
        transcript=recording.transcript, side__number=rule["side"]
    ).exclude(speaker="")
    labels = {one for one in lines.values_list("speaker", flat=True).distinct()}
    worn = [one for one in labels if _is_a_label(one)]
    if not worn:
        return 0
    lines.filter(speaker__in=worn).update(speaker=rule["person"].name)
    return 1


def on_transcript(recording) -> None:
    """As a transcript lands: the case's side rule, when it has one."""
    try:
        apply_side_rule(recording)
    except Exception:  # noqa: BLE001 - a rule must never fail a transcript
        import logging

        logging.getLogger(__name__).exception("the side rule could not be applied")
