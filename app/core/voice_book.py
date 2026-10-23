"""The unit's voice book (Phase 5 chapter 2, "The unit's voice book"; ADR
0021 amended 2026-10-21; the voice plan's V4b, v1.146.0): a voice kept
beyond one Case, by choice, for the people the office meets again.

V4 keeps a Voice print inside one Case and matches it there on its own.
This adds one more place a print may live. On the Case's Speakers tab a
person who may open the case chooses to keep a Person's voice for the
case's unit (the owner's unit), only for a Person in a Role the Admin
allows (officers, interpreters, interviewers; never a defendant, a victim,
a witness or a client). The book's print is the mean of the case prints
that teach it, weighted by the seconds each heard; a case's share is added
when it keeps the Person, refined by each name or match accepted for them
there, and removed when the case unlearns, stops keeping, or deletes the
Person, so the book is never more sure than the cases behind it.

The book never proposes on its own. An unnamed card on a recording's
Speakers page is checked against it by a press, and the answer (Sounds like
with the pill "the unit's voices", a conflict, or no match) is accepted or
declined on that card, as every proposal is. Accept adds the Person to the
case with the book's name and Role, names the lines, teaches both prints,
and the case keeps the Person. A book is read and written by its unit only;
an Admin reads every book and acts in a case as the case's unit does. The
switch going off deletes every book; the cases' prints and names stay.
Nothing here is logged but counts; nothing is exported or sent anywhere.
"""

from __future__ import annotations

import logging
import uuid

import numpy as np
from django.db import models, transaction
from django.utils import timezone

from core import audit, clock_check, settings_store, units

log = logging.getLogger(__name__)

# The Roles that name a client's side or a witness: never kept, whatever
# the Admin's list says.
REFUSED_ROLES = ("Defendant", "Victim", "Witness", "Client")
# Turned down this often in thirty days, a book's print is called out.
DISMISSALS_TO_CALL_OUT = 3
# How long a forgotten row stays on the Voices page, greyed.
FORGOTTEN_SHOWN_DAYS = 60


class UnitVoice(models.Model):
    """One voice kept for a unit: the book's print (the weighted mean of
    the case prints that teach it, in `parts` by Person), the name and Role
    it goes with, who kept it and from which case, and when it was
    forgotten. Content: never logged, exported or sent anywhere."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    unit = models.CharField(max_length=40)
    name = models.CharField(max_length=60)
    role = models.CharField(max_length=40, blank=True, default="")
    vector = models.JSONField(null=True, blank=True)
    # {person id: {"vector", "seconds", "recordings", "case", "at"}}
    parts = models.JSONField(default=dict, blank=True)
    kept_by = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    kept_at = models.DateTimeField(default=timezone.now)
    from_case = models.ForeignKey(
        "core.Case",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    forgotten_at = models.DateTimeField(null=True, blank=True)
    forgotten_by = models.CharField(max_length=150, blank=True, default="")
    # Told to recognition (v1.156.0): the name goes with every recording in
    # the unit's cases as a word to listen for; off per voice at the
    # Voices place.
    tell_recognition = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["unit", "name"]

    @property
    def live(self) -> bool:
        return self.forgotten_at is None and bool(self.vector)


class UnitVoiceCheck(models.Model):
    """One press of Check against the unit's voices, as rows: a MATCH row
    per voice the book offered (two are a conflict), or one NONE row when
    nothing sounded like the Speaker. A label, a rating and a state; never
    a word of the recording."""

    MATCH, NONE = "match", "none"
    PENDING, ACCEPTED, DISMISSED, WITHDRAWN = (
        "pending",
        "accepted",
        "dismissed",
        "withdrawn",
    )

    id = models.AutoField(primary_key=True)
    transcript = models.ForeignKey(
        "core.Transcript", on_delete=models.CASCADE, related_name="book_checks"
    )
    press = models.UUIDField(default=uuid.uuid4)
    unit = models.CharField(max_length=40)
    speaker = models.CharField(max_length=60)
    voice = models.ForeignKey(
        UnitVoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checks",
    )
    kind = models.CharField(max_length=6, default=MATCH)
    rating = models.CharField(max_length=6, blank=True, default="")
    score = models.FloatField(default=0.0)
    compared = models.IntegerField(default=0)
    state = models.CharField(max_length=10, default=PENDING)
    by = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    decided_by = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created", "speaker", "-score"]


# The switch and the roles -------------------------------------------------------------


def on() -> bool:
    """Keep voices for the unit, with Remember voices across a case on and
    at least one unit listed."""
    from core import voice_prints

    return (
        bool(settings_store.get("unit_voices"))
        and voice_prints.on()
        and bool(units.names())
    )


def roles_allowed() -> list[str]:
    text = settings_store.get("unit_voice_roles") or ""
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and line.strip() not in REFUSED_ROLES
    ]


def check_roles_setting(text: str) -> str:
    """The Roles kept for the unit as they would be kept, or a refusal: a
    role that names a client's side or a witness is never allowed."""
    kept = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.casefold() in {one.casefold() for one in REFUSED_ROLES}:
            raise ValueError(
                f"Roles kept for the unit: {line} cannot be kept for the unit; "
                "a voice book holds officers and the office's own people, never "
                "a client's side or a witness"
            )
        kept.append(line[:40])
    return "\n".join(kept)


def unit_of_case(case) -> str:
    """The one book a case has: its owner's unit."""
    owner = getattr(case, "owner", None)
    return units.of(owner) if owner is not None else ""


def names_for_recognition(case) -> list[str]:
    """The names of the voices the case's unit keeps that are told to
    recognition (v1.156.0); none while the book is off or the owner is in
    no unit."""
    if case is None or not on():
        return []
    unit = unit_of_case(case)
    if not unit:
        return []
    return list(
        UnitVoice.objects.filter(
            unit=unit, forgotten_at=None, vector__isnull=False, tell_recognition=True
        )
        .order_by("name")
        .values_list("name", flat=True)
    )


def set_tell_recognition(book: UnitVoice, told: bool, *, by, request=None) -> None:
    """The switch on one kept voice: whether its name goes to recognition
    for the unit's cases. One audit row, naming the unit and the choice."""
    if book.tell_recognition == told:
        return
    book.tell_recognition = told
    book.save(update_fields=["tell_recognition"])
    audit.write(
        audit.Category.CASES,
        "Unit voice recognition switched",
        actor=by,
        request=request,
        object_type="unit",
        object_id=book.unit,
        object_label=book.unit,
        told=told,
    )


def counts_for_switch() -> dict[str, int]:
    """What turning the switch off would delete, per unit, for the tray."""
    out: dict[str, int] = {}
    for row in UnitVoice.objects.filter(forgotten_at=None).values("unit"):
        out[row["unit"]] = out.get(row["unit"], 0) + 1
    return out


# Keeping ------------------------------------------------------------------------------


def find(unit: str, name: str) -> UnitVoice | None:
    if not unit or not (name or "").strip():
        return None
    return UnitVoice.objects.filter(
        unit=unit, name__iexact=name.strip(), forgotten_at=None
    ).first()


def person_rule(person) -> str:
    """Why this Person's voice cannot be kept for any unit, or "" when it
    can: off, no print, role. The case's unit is the other half."""
    if not on():
        return "off"
    if not (person.voice_print or {}).get("vector"):
        return "no print"
    if not person.role or person.role not in roles_allowed():
        return "role"
    return ""


def may_keep(person) -> tuple[bool, str]:
    """Whether this Person's voice can be kept for the unit, and the unit
    when it can, or why not: off, no unit, no print, role."""
    if not on():
        return False, "off"
    unit = unit_of_case(person.case)
    if not unit:
        return False, "no unit"
    why = person_rule(person)
    if why:
        return False, why
    return True, unit


def books_of(person) -> list[UnitVoice]:
    """Every live book that holds this Person's share, in the Admin's
    order of units (v1.157.0: an Admin may keep one voice for several)."""
    found = list(
        UnitVoice.objects.filter(forgotten_at=None, parts__has_key=str(person.pk))
    )
    order = {name: n for n, name in enumerate(units.names())}
    found.sort(key=lambda one: (order.get(one.unit, len(order)), one.unit))
    return found


def units_kept(person) -> list[str]:
    return [one.unit for one in books_of(person)]


def units_offered(person, user) -> list[str]:
    """The units this user may still keep the Person for: every listed unit
    without them for an Admin; the case owner's unit for anyone else, when
    the owner is in one. Empty when the Person's own rules refuse."""
    if person_rule(person):
        return []
    held = set(units_kept(person))
    if getattr(user, "is_admin", False):
        return [one for one in units.names() if one not in held]
    unit = unit_of_case(person.case)
    return [unit] if unit and unit not in held else []


def _part_of(person) -> dict | None:
    kept = person.voice_print or {}
    if not kept.get("vector"):
        return None
    parts = kept.get("parts") or {}
    return {
        "vector": kept["vector"],
        "seconds": round(
            sum(float(one.get("seconds", 0)) for one in parts.values()), 1
        ),
        "recordings": len(parts),
        "case": str(person.case_id),
        "at": timezone.now().isoformat(timespec="seconds"),
    }


def _rebuild(book: UnitVoice) -> None:
    from core import voice_prints

    parts = book.parts or {}
    if not parts:
        book.vector = None
        return
    weights = np.asarray(
        [max(float(one.get("seconds", 0)), 1.0) for one in parts.values()]
    )
    vectors = np.stack(
        [np.asarray(voice_prints._unit(one["vector"])) for one in parts.values()]
    )
    book.vector = voice_prints._unit(
        (vectors * weights[:, None]).sum(axis=0) / weights.sum()
    )


def _mark_forgotten(book: UnitVoice, by, how: str = "") -> None:
    book.vector = None
    book.parts = {}
    book.forgotten_at = timezone.now()
    book.forgotten_by = getattr(by, "username", "") or how or ""
    UnitVoiceCheck.objects.filter(voice=book, state=UnitVoiceCheck.PENDING).update(
        state=UnitVoiceCheck.WITHDRAWN, decided_at=timezone.now()
    )


def teach(person) -> bool:
    """A kept Person's print changed (learnt, a recording forgotten, unlearnt):
    this case's share of the book follows. True when the book changed."""
    if not getattr(person, "kept_for_unit", False) or not on():
        return False
    books = books_of(person)
    if not books:
        return False
    part = _part_of(person)
    for book in books:
        _put_share(book, person, part)
    return True


def _put_share(book: UnitVoice, person, part: dict | None) -> None:
    """This case's share of one book: written, or taken out when the
    Person has no print left; a book with no share left is forgotten."""
    parts = dict(book.parts or {})
    if part is None:
        parts.pop(str(person.pk), None)
    else:
        parts[str(person.pk)] = part
    book.parts = parts
    _rebuild(book)
    if book.vector is None:
        _mark_forgotten(book, None, "the last case that taught it")
    book.save(update_fields=["parts", "vector", "forgotten_at", "forgotten_by"])


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


REFUSALS = {
    "off": "Voices are not kept for the unit.",
    "no unit": "This case's owner is in no unit.",
    "no print": "{name} has no voice print yet.",
    "role": "A {role} is not kept for the unit.",
}


def _refusal(person, why: str) -> ValueError:
    return ValueError(
        REFUSALS[why].format(
            name=person.name, role=person.role or "person with no role"
        )
    )


def keep(person, *, by, request=None) -> UnitVoice:
    """Keep for the unit, from the Case's Speakers tab: the Person's print
    becomes this case's share of the book, made now if the name has none."""
    ok, unit = may_keep(person)
    if not ok:
        raise _refusal(person, unit)
    return _keep_in(person, unit, by=by, request=request)


def keep_for(person, wanted: list[str], *, by, request=None) -> list[UnitVoice]:
    """An Admin keeps the Person for the units they tick (v1.157.0), whatever
    unit the case or the Admin is in; a unit already holding them is passed
    over. Anyone else is refused: their one unit is the case owner's."""
    if not getattr(by, "is_admin", False):
        raise ValueError("Only an Admin keeps a voice for a unit of their choosing.")
    why = person_rule(person)
    if why:
        raise _refusal(person, why)
    listed = units.names()
    chosen = []
    for one in wanted:
        name = (one or "").strip()
        if not name:
            continue
        if name not in listed:
            raise ValueError(f"{name!r} is not a unit the Admin has listed.")
        if name not in chosen:
            chosen.append(name)
    if not chosen:
        raise ValueError("Tick at least one unit.")
    held = set(units_kept(person))
    return [
        _keep_in(person, unit, by=by, request=request)
        for unit in chosen
        if unit not in held
    ]


def _keep_in(person, unit: str, *, by, request=None) -> UnitVoice:
    with transaction.atomic():
        book = find(unit, person.name)
        if book is None:
            book = UnitVoice.objects.create(
                unit=unit,
                name=person.name,
                role=person.role,
                kept_by=by,
                from_case=person.case,
            )
        elif not book.role and person.role:
            book.role = person.role
            book.save(update_fields=["role"])
        person.kept_for_unit = True
        person.voice_scope = "unit"
        person.save(update_fields=["kept_for_unit", "voice_scope"])
        _put_share(book, person, _part_of(person))
        book.refresh_from_db()
    _row("Voice kept for the unit", person.case, by, request, unit=unit)
    return book


def stop_keeping(person, *, by, request=None, why: str = "", unit: str = "") -> bool:
    """Stop keeping, from the tab, a Role change, Delete person or a merge:
    this case's share leaves the book; a book with no share left is
    forgotten. The case's own print stays. With a unit named (v1.157.0,
    the card's per-unit line) only that book lets go, and the Person stays
    kept while another unit's book holds them."""
    if not getattr(person, "kept_for_unit", False):
        return False
    books = books_of(person)
    if unit:
        books = [one for one in books if one.unit == unit]
        if not books:
            return False
    letting_go = {one.unit for one in books}
    left = [one.unit for one in books_of(person) if one.unit not in letting_go]
    with transaction.atomic():
        if not left:
            person.kept_for_unit = False
            person.voice_scope = "case"
            person.save(update_fields=["kept_for_unit", "voice_scope"])
        for book in books:
            parts = dict(book.parts or {})
            parts.pop(str(person.pk), None)
            book.parts = parts
            _rebuild(book)
            if book.vector is None:
                _mark_forgotten(book, by, "the last case stopped keeping it")
            book.save(update_fields=["parts", "vector", "forgotten_at", "forgotten_by"])
    for name in [one.unit for one in books] or [unit_of_case(person.case)]:
        _row(
            "Voice no longer kept for the unit",
            person.case,
            by,
            request,
            unit=name,
            why=why,
        )
    return True


def follow_rename(person, was: str) -> None:
    """The Person renamed: the book's name follows, unless the new name
    already has a book, in which case this case's share moves there."""
    if not getattr(person, "kept_for_unit", False):
        return
    for book in books_of(person):
        other = find(book.unit, person.name)
        if other is None or other.pk == book.pk:
            book.name = person.name
            book.save(update_fields=["name"])
            continue
        parts = dict(book.parts or {})
        parts.pop(str(person.pk), None)
        book.parts = parts
        _rebuild(book)
        if book.vector is None:
            _mark_forgotten(book, None, "renamed into another")
        book.save(update_fields=["parts", "vector", "forgotten_at", "forgotten_by"])
        _put_share(other, person, _part_of(person))


def follow_role(person, *, by, request=None) -> None:
    """The Person's Role changed: a Role no longer allowed stops the keeping;
    an allowed one goes with the voice."""
    if not getattr(person, "kept_for_unit", False):
        return
    if not person.role or person.role not in roles_allowed():
        stop_keeping(person, by=by, request=request, why="the role is not kept")
        return
    for book in books_of(person):
        if book.role != person.role:
            book.role = person.role
            book.save(update_fields=["role"])


def forget(book: UnitVoice, *, by, request=None) -> int:
    """Forget, on the Voices page: the book's print goes and no case keeps
    the name any longer; the names accepted from it stay, as do the cases'
    own prints. Returns how many cases stopped keeping."""
    from core.people import Person

    with transaction.atomic():
        ids = [one for one in (book.parts or {}) if _is_uuid(one)]
        _mark_forgotten(book, by)
        book.save(update_fields=["parts", "vector", "forgotten_at", "forgotten_by"])
        stopped = 0
        for person in Person.objects.filter(pk__in=ids, kept_for_unit=True):
            # Kept for another unit too (v1.157.0): that book still holds them.
            if books_of(person):
                continue
            person.kept_for_unit = False
            person.voice_scope = "case"
            person.save(update_fields=["kept_for_unit", "voice_scope"])
            stopped += 1
    audit.write(
        audit.Category.CASES,
        "Unit voice forgotten",
        actor=by,
        request=request,
        object_type="unit",
        object_id=book.unit,
        object_label=book.unit,
        cases=stopped,
    )
    return stopped


def _is_uuid(text: str) -> bool:
    try:
        uuid.UUID(str(text))
    except (ValueError, TypeError):
        return False
    return True


def forget_everything(*, by=None) -> dict:
    """The switch goes Off (or Remember voices does): every book goes; the
    cases' prints and names stay."""
    from core.people import Person

    counts = counts_for_switch()
    with transaction.atomic():
        people = Person.objects.filter(kept_for_unit=True).update(
            kept_for_unit=False, voice_scope="case"
        )
        withdrawn = UnitVoiceCheck.objects.filter(state=UnitVoiceCheck.PENDING).update(
            state=UnitVoiceCheck.WITHDRAWN, decided_at=timezone.now()
        )
        voices, _ = UnitVoice.objects.all().delete()
    audit.write(
        audit.Category.ADMIN,
        "Unit voice books forgotten",
        actor=by,
        voices=sum(counts.values()),
        units=len(counts),
        people=people,
        checks_withdrawn=withdrawn,
    )
    return {"voices": sum(counts.values()), "units": counts, "people": people}


# Checking -----------------------------------------------------------------------------


def can_check(recording, label: str) -> tuple[bool, str]:
    """Whether an unnamed card can be checked against the book: the unit
    when it can, or the reason the button is greyed ("" when there is no
    button at all)."""
    from core import voice_prints
    from core.assistant import _is_a_label

    if not on() or recording.case_id is None or not _is_a_label(label):
        return False, ""
    unit = unit_of_case(recording.case)
    if not unit:
        return False, ""
    if (
        not UnitVoice.objects.filter(unit=unit, forgotten_at=None)
        .exclude(vector=None)
        .exists()
    ):
        return False, "The unit's voice book holds no voice yet."
    transcript = getattr(recording, "transcript", None)
    found = voice_prints.print_of(transcript, label) if transcript else None
    if found is None:
        return (
            False,
            "The voice did not listen on this recording: its type is not under "
            "Voices help the check.",
        )
    if float(found.get("seconds", 0)) < voice_prints.SURE_SECONDS:
        return (
            False,
            f"Too little to compare: under {int(voice_prints.SURE_SECONDS)} seconds "
            "of clean voice.",
        )
    return True, unit


def check(recording, label: str, *, by, request=None) -> dict:
    """Check against the unit's voices, pressed on a card: the Speaker's
    print on this recording against every live voice of the unit; the
    rows are made and the card's answer returned."""
    from core import voice_prints

    ok, unit = can_check(recording, label)
    if not ok:
        raise ValueError(unit or "This speaker cannot be checked against the book.")
    transcript = recording.transcript
    found = voice_prints.print_of(transcript, label)
    books = list(
        UnitVoice.objects.filter(unit=unit, forgotten_at=None).exclude(vector=None)
    )
    last = transcript.speaker_checks.filter(state="done").first()
    midpoint = (
        ((last.second_look or {}).get("calibration") or {}).get("midpoint")
        if last
        else None
    )
    medium_line = (
        max(voice_prints.MEDIUM_COS, float(midpoint))
        if midpoint
        else voice_prints.MEDIUM_COS
    )
    seconds = float(found.get("seconds", 0))
    press = uuid.uuid4()
    rows = []
    for book in books:
        score = voice_prints._cos(found["vector"], book.vector)
        word = voice_prints._rating(score, len(book.parts or {}), seconds, medium_line)
        if not word:
            continue
        rows.append(
            UnitVoiceCheck(
                transcript=transcript,
                press=press,
                unit=unit,
                speaker=label,
                voice=book,
                kind=UnitVoiceCheck.MATCH,
                rating=word,
                score=round(score, 3),
                compared=len(books),
                by=by,
            )
        )
    with transaction.atomic():
        UnitVoiceCheck.objects.filter(
            transcript=transcript, speaker=label, state=UnitVoiceCheck.PENDING
        ).update(state=UnitVoiceCheck.WITHDRAWN, decided_at=timezone.now())
        if rows:
            UnitVoiceCheck.objects.bulk_create(rows)
        else:
            UnitVoiceCheck.objects.create(
                transcript=transcript,
                press=press,
                unit=unit,
                speaker=label,
                kind=UnitVoiceCheck.NONE,
                compared=len(books),
                by=by,
            )
    _row(
        "Unit voice check",
        recording.case,
        by,
        request,
        unit=unit,
        compared=len(books),
        found=len(rows),
    )
    for one in rows_for(transcript, by):
        if one["speaker"] == label:
            return one
    return {"speaker": label, "kind": "none", "compared": len(books)}


def heard_of(book: UnitVoice, user) -> list[dict]:
    """Where the reader may hear the voice: one line of the kept Person on
    a recording of a case the reader may open; empty when there is none."""
    from core import exports
    from core.cases import Case
    from core.jobs import Segment
    from core.people import Person
    from core.recordings import Recording

    for person_id, part in (book.parts or {}).items():
        if not _is_uuid(person_id):
            continue
        case = Case.objects.filter(pk=part.get("case"), deleted_on__isnull=True).first()
        if case is None or user is None or not case.may_be_opened_by(user):
            continue
        person = Person.objects.filter(pk=person_id).first()
        if person is None:
            continue
        for rid in (person.voice_print or {}).get("parts") or {}:
            lines = list(
                Segment.objects.filter(
                    transcript__recording_id=rid, speaker=person.name
                )
                .order_by("start")
                .values_list("start", "end", "clock")[:40]
            )
            if not lines:
                continue
            # A line whose clock the audio doubts (v1.151.0) is never the
            # one the Preview seeks to, while any other remains.
            lines = [
                (start, end)
                for start, end, clock in lines
                if not clock_check.unsure(clock)
            ] or [(start, end) for start, end, _ in lines]
            recording = Recording.objects.filter(pk=rid).first()
            if recording is None:
                continue
            long = [one for one in lines if one[1] - one[0] >= 2.0]
            start = (long or lines)[0][0]
            return [
                {
                    "recording": str(rid),
                    "title": recording.title,
                    "start": start,
                    "clock": exports.clock(start),
                }
            ]
    return []


def _opens_one(book: UnitVoice, user) -> bool:
    """Whether the reader may open any case that taught the voice; when
    not, the card says the voice is heard on a case they may not open."""
    from core.cases import Case

    ids = [one.get("case") for one in (book.parts or {}).values() if one.get("case")]
    return any(
        user is not None and case.may_be_opened_by(user)
        for case in Case.objects.filter(
            pk__in=[one for one in ids if _is_uuid(one)], deleted_on__isnull=True
        )
    )


def rows_for(transcript, user) -> list[dict]:
    """The latest press per Speaker label still on the transcript, for the
    card: a match, a conflict, or no match, with the voices to hear."""
    from core import exports

    labels = set(
        transcript.segments.filter(same_as_other_side=False)
        .exclude(speaker="")
        .values_list("speaker", flat=True)
        .distinct()
    )
    rows = list(
        UnitVoiceCheck.objects.filter(transcript=transcript)
        .select_related("voice")
        .order_by("-created")
    )
    by_label: dict[str, list] = {}
    press_of: dict[str, uuid.UUID] = {}
    for row in rows:
        if row.speaker not in labels:
            continue
        press = press_of.setdefault(row.speaker, row.press)
        if row.press != press:
            continue
        by_label.setdefault(row.speaker, []).append(row)
    out = []
    for label, mine in by_label.items():
        first = mine[0]
        live = [
            one
            for one in mine
            if one.kind == UnitVoiceCheck.MATCH
            and one.state == UnitVoiceCheck.PENDING
            and one.voice is not None
        ]
        if first.kind == UnitVoiceCheck.NONE:
            out.append(
                {
                    "speaker": label,
                    "kind": "none",
                    "unit": first.unit,
                    "compared": first.compared,
                    "at": timezone.localtime(first.created).strftime("%d %b %H:%M"),
                    "voices": [],
                }
            )
            continue
        if not live:
            continue
        out.append(
            {
                "speaker": label,
                "kind": "conflict" if len(live) > 1 else "match",
                "unit": first.unit,
                "compared": first.compared,
                "at": timezone.localtime(first.created).strftime("%d %b %H:%M"),
                "voices": [
                    {
                        "id": one.pk,
                        "name": one.voice.name,
                        "role": one.voice.role,
                        "rating": one.rating,
                        "cases": len(one.voice.parts or {}),
                        "heard": heard_of(one.voice, user),
                        "openable": _opens_one(one.voice, user),
                    }
                    for one in sorted(live, key=lambda one: -one.score)
                ],
            }
        )
    del exports
    return out


def state_for(transcript, user) -> dict:
    """What the Speakers page needs: whether the book is here, the unit,
    per unnamed label whether Check is lit and why not, and the answers."""
    recording = transcript.recording
    if not on() or recording.case_id is None:
        return {"on": False, "unit": "", "can": {}, "checks": []}
    unit = unit_of_case(recording.case)
    if not unit:
        return {"on": False, "unit": "", "can": {}, "checks": []}
    from core.assistant import _is_a_label

    labels = (
        transcript.segments.filter(same_as_other_side=False)
        .exclude(speaker="")
        .values_list("speaker", flat=True)
        .distinct()
    )
    can = {}
    for label in labels:
        if _is_a_label(label):
            ok, why = can_check(recording, label)
            can[label] = {"ok": ok, "why": "" if ok else why}
    return {
        "on": True,
        "unit": unit,
        "can": can,
        "checks": rows_for(transcript, user),
    }


def accept(row: UnitVoiceCheck, *, by, request=None) -> int:
    """Accept on the card: the Person joins the case with the book's name
    and Role (or is the one of that name already there), the Speaker label
    takes the name on every line with the viewer's Undo, both prints learn,
    and the case keeps the Person for the unit."""
    from core import people, speaker_check, voice_prints

    transcript = row.transcript
    recording = transcript.recording
    book = row.voice
    if book is None or not book.live:
        raise ValueError("That voice is no longer in the unit's book.")
    changed = 0
    followed = None
    with transaction.atomic():
        person, _ = people.join_or_create(
            recording.case,
            book.name,
            by=by,
            how="the unit's voices accepted",
            request=request,
            role=book.role,
        )
        moved = list(
            transcript.segments.filter(speaker=row.speaker).values_list("pk", flat=True)
        )
        changed = transcript.segments.filter(pk__in=moved).update(speaker=person.name)
        followed = speaker_check.follow(transcript, row.speaker, person.name, by=by)
        changes = list(transcript.speaker_changes or [])
        changes.append(
            {
                "from": row.speaker,
                "to": person.name,
                "segments": moved,
                "merged": False,
                "corrections": followed,
                "book_check": row.pk,
                "at": timezone.now().isoformat(),
            }
        )
        transcript.speaker_changes = changes[-20:]
        transcript.save(update_fields=["speaker_changes"])
        voice_prints.learn(
            recording, row.speaker, person, by=by, how=voice_prints.VOICE
        )
        person.refresh_from_db()
        if person.role in roles_allowed() and (person.voice_print or {}).get("vector"):
            person.kept_for_unit = True
            person.voice_scope = "unit"
            person.save(update_fields=["kept_for_unit", "voice_scope"])
            # The matched book takes this case's share; any other book that
            # already holds them (v1.157.0) learns too.
            _put_share(book, person, _part_of(person))
            teach(person)
        row.state = UnitVoiceCheck.ACCEPTED
        row.decided_by = by
        row.decided_at = timezone.now()
        row.save(update_fields=["state", "decided_by", "decided_at"])
        UnitVoiceCheck.objects.filter(
            transcript=transcript, speaker=row.speaker, state=UnitVoiceCheck.PENDING
        ).exclude(pk=row.pk).update(
            state=UnitVoiceCheck.WITHDRAWN, decided_by=by, decided_at=timezone.now()
        )
        voice_prints.settle(transcript)
    speaker_check.reread_after_name(
        transcript, row.speaker, person.name, by=by, followed=followed
    )
    _row(
        "Unit voice accepted",
        recording.case,
        by,
        request,
        unit=row.unit,
        rating=row.rating,
        segments_changed=changed,
    )
    return changed


def dismiss(row: UnitVoiceCheck, *, by, request=None) -> None:
    """Not them: counted against the book's print; nothing is taught."""
    row.state = UnitVoiceCheck.DISMISSED
    row.decided_by = by
    row.decided_at = timezone.now()
    row.save(update_fields=["state", "decided_by", "decided_at"])
    _row(
        "Unit voice dismissed",
        row.transcript.recording.case,
        by,
        request,
        unit=row.unit,
        rating=row.rating,
    )


def undo_accept(transcript, change: dict) -> None:
    """The viewer's Undo of an Accept: the row goes back to waiting."""
    row = UnitVoiceCheck.objects.filter(pk=change.get("book_check")).first()
    if row is None:
        return
    row.state = UnitVoiceCheck.PENDING
    row.decided_by = None
    row.decided_at = None
    row.save(update_fields=["state", "decided_by", "decided_at"])


# The pages ----------------------------------------------------------------------------


def tab_line(person, user) -> dict | None:
    """What the Case tab's Voice column says about the book for this
    Person: kept (with since, by and Stop keeping), an offer with the box,
    one muted sentence for a Role not kept, or nothing."""
    if not on():
        return None
    admin = bool(getattr(user, "is_admin", False))
    unit = unit_of_case(person.case)
    if not unit and not admin:
        return None
    mine = admin or units.of(user) == unit
    books = books_of(person) if getattr(person, "kept_for_unit", False) else []
    if books:
        # The owner's unit's book says since and by when it holds them, else
        # the first (v1.157.0: an Admin may have kept them for several).
        book = next((one for one in books if one.unit == unit), books[0])
        part = (book.parts or {}).get(str(person.pk))
        since = (part or {}).get("at", "")[:10] if part else ""
        held = [one.unit for one in books]
        return {
            "state": "kept",
            "unit": unit,
            "units": held,
            "more": units_offered(person, user) if admin else [],
            "admin": admin,
            "mine": mine,
            "since": since or book.kept_at.date().isoformat(),
            "by": (book.kept_by.username if book.kept_by else ""),
            "cases": len(book.parts or {}),
        }
    why = person_rule(person)
    if not why and (admin or unit):
        return {
            "state": "offer",
            "unit": unit,
            "admin": admin,
            "choices": units.names() if admin else [unit],
            "mine": mine,
        }
    if why == "role" and (person.voice_print or {}).get("vector"):
        return {
            "state": "not-kept",
            "unit": unit,
            "admin": admin,
            "mine": mine,
            "role": person.role,
        }
    return None


def rail(user) -> dict:
    """The place on the rail: whether it is there, and its line."""
    if user is None or not getattr(user, "is_authenticated", False) or not on():
        return {"on": False, "units": [], "line": ""}
    seen = units.seen_by(user)
    if not seen:
        return {"on": False, "units": [], "line": ""}
    if getattr(user, "is_admin", False) and len(seen) > 1:
        line = "Every unit's known voices"
    else:
        line = f"The {seen[0]} unit's known voices"
    return {"on": True, "units": seen, "line": line}


def page_rows(unit: str, user) -> list[dict]:
    """The Voices place's table for one unit: a row per voice, live first."""
    from django.db.models import Count

    from core.cases import Case
    from core.people import Person

    since_month = timezone.now() - timezone.timedelta(days=30)
    cutoff = timezone.now() - timezone.timedelta(days=FORGOTTEN_SHOWN_DAYS)
    books = [
        one
        for one in UnitVoice.objects.filter(unit=unit)
        .select_related("kept_by", "from_case")
        .order_by("forgotten_at", "name")
        if one.forgotten_at is None or one.forgotten_at >= cutoff
    ]
    decided: dict = {}
    for row in (
        UnitVoiceCheck.objects.filter(voice__in=books)
        .values("voice_id", "state")
        .annotate(n=Count("id"))
    ):
        decided[(row["voice_id"], row["state"])] = row["n"]
    lately: dict = {}
    for row in (
        UnitVoiceCheck.objects.filter(
            voice__in=books, state=UnitVoiceCheck.DISMISSED, decided_at__gte=since_month
        )
        .values("voice_id")
        .annotate(n=Count("id"))
    ):
        lately[row["voice_id"]] = row["n"]
    last_heard = {
        row["voice_id"]: row["latest"]
        for row in UnitVoiceCheck.objects.filter(voice__in=books)
        .values("voice_id")
        .annotate(latest=models.Max("created"))
    }
    live_elsewhere = list(
        UnitVoice.objects.filter(forgotten_at=None)
        .exclude(unit=unit)
        .values("unit", "parts")
    )
    order = {name: n for n, name in enumerate(units.names())}
    out = []
    for book in books:
        parts = book.parts or {}
        case_ids = {one.get("case") for one in parts.values() if one.get("case")}
        # Also kept for (v1.157.0): the other units whose live books hold a
        # share of the same people.
        also_units = sorted(
            {
                one["unit"]
                for one in live_elsewhere
                if set(one["parts"] or {}) & set(parts)
            },
            key=lambda name: (order.get(name, len(order)), name),
        )
        cases = {
            str(one.pk): one
            for one in Case.objects.filter(pk__in=[c for c in case_ids if _is_uuid(c)])
        }
        openable = sum(
            1
            for one in cases.values()
            if user is not None and one.may_be_opened_by(user)
        )
        from_case = book.from_case
        from_text = (
            from_case.name
            if from_case is not None
            and user is not None
            and from_case.may_be_opened_by(user)
            else "a case you may not open"
        )
        others = max(
            len(case_ids)
            - (1 if from_case is not None and str(from_case.pk) in case_ids else 0),
            0,
        )
        also = []
        for person in Person.objects.filter(pk__in=[p for p in parts if _is_uuid(p)]):
            for name in person.also_called or []:
                if name not in also:
                    also.append(name)
        out.append(
            {
                "book": book,
                "live": book.live,
                "cases": max(len(case_ids), 1 if parts else 0),
                "recordings": sum(
                    int(one.get("recordings", 0)) for one in parts.values()
                ),
                "heard": heard_of(book, user) if book.live else [],
                "from_text": from_text,
                "from_case": from_case
                if from_text != "a case you may not open"
                else None,
                "others": others,
                "also_units": also_units,
                "kept_by_admin": bool(
                    book.kept_by is not None
                    and getattr(book.kept_by, "is_admin", False)
                ),
                "openable": openable,
                "also_called": also[:4],
                "accepted": decided.get((book.pk, UnitVoiceCheck.ACCEPTED), 0),
                "dismissed": decided.get((book.pk, UnitVoiceCheck.DISMISSED), 0),
                "last_heard": last_heard.get(book.pk) or book.kept_at,
                "called_out": lately.get(book.pk, 0) >= DISMISSALS_TO_CALL_OUT,
                "medium_at_best": book.live and len(parts) < 2,
            }
        )
    return out


def decided_by_month(unit: str) -> list[dict]:
    """Decided from the book, this unit, per month: presses, accepted, not
    them, no match; the last three months with anything in them."""
    from django.db.models.functions import TruncMonth

    months: dict = {}
    for row in (
        UnitVoiceCheck.objects.filter(unit=unit)
        .annotate(month=TruncMonth("created"))
        .values("month", "press", "kind", "state")
    ):
        slot = months.setdefault(
            row["month"], {"presses": set(), "accepted": 0, "dismissed": 0, "none": 0}
        )
        slot["presses"].add(row["press"])
        if row["kind"] == UnitVoiceCheck.NONE:
            slot["none"] += 1
        elif row["state"] == UnitVoiceCheck.ACCEPTED:
            slot["accepted"] += 1
        elif row["state"] == UnitVoiceCheck.DISMISSED:
            slot["dismissed"] += 1
    out = []
    for month in sorted(months, reverse=True)[:3]:
        slot = months[month]
        out.append(
            {
                "month": month.strftime("%B %Y"),
                "checks": len(slot["presses"]),
                "accepted": slot["accepted"],
                "dismissed": slot["dismissed"],
                "none": slot["none"],
            }
        )
    return out
