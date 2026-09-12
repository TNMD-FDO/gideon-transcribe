"""People: inside a Case, a Speaker's name means a person.

Every Speaker in the Case's Transcripts given the same name is the same
Person; the name is the link, and there is no separate assignment step. A
Person holds a name, an optional Role from the Admin-kept list, and notes;
lives only inside its Case; and stays until someone deletes or merges it.

The build's decision on the chapter's open point: there is no Person link on
the Segment. The link is the name itself, kept equal in the same transaction
by the operations here, which is what the chapter says the link must be kept
equal to anyway. Nothing about a Person is ever logged but its id and its
Case's name.
"""

from __future__ import annotations

import uuid

from django.db import models, transaction
from django.db.models.functions import Lower

from core import audit, settings_store

# Notes are a few lines for people, never for the AI assistant.
NOTES_LENGTH = 1000


class Person(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        "core.Case", on_delete=models.CASCADE, related_name="people"
    )
    name = models.CharField(max_length=60)
    role = models.CharField(max_length=40, blank=True, default="")
    notes = models.TextField(max_length=NOTES_LENGTH, blank=True, default="")
    added_by = models.ForeignKey(
        "core.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created = models.DateTimeField(auto_now_add=True)
    changed = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"), "case", name="one_person_per_name_in_a_case"
            )
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def label(self) -> str:
        """The snapshot label an audit row carries: the id, never the name."""
        return f"Person {self.pk} in {self.case.name}"

    def shown(self) -> str:
        """Name (Role) when a Role is set, for the Known names line and the badges."""
        return f"{self.name} ({self.role})" if self.role else self.name

    def segments(self):
        """Every Segment in the Case's Transcripts that carries this Person's name."""
        from core.jobs import Segment

        return Segment.objects.filter(
            transcript__recording__case=self.case, speaker__iexact=self.name.strip()
        )

    def recordings(self):
        """The Recordings the Person appears in, with the first Segment of each."""
        from core.recordings import Recording

        found = []
        ids = (
            self.segments()
            .values_list("transcript__recording_id", flat=True)
            .distinct()
        )
        for recording in Recording.objects.filter(pk__in=list(ids)).order_by("title"):
            first = (
                self.segments()
                .filter(transcript__recording=recording)
                .order_by("start")
                .first()
            )
            found.append((recording, first.start if first else 0.0))
        return found


# Finding and making --------------------------------------------------------------


def roles() -> list[str]:
    """The Speaker roles list, one per line, as the Admin keeps it."""
    text = settings_store.get("speaker_roles") or ""
    return [line.strip() for line in str(text).splitlines() if line.strip()]


def find(case, name: str) -> Person | None:
    return Person.objects.filter(case=case, name__iexact=(name or "").strip()).first()


def _row(event: str, person: Person, actor, request=None, **details) -> None:
    audit.write(
        audit.Category.CASES,
        event,
        actor=actor,
        request=request,
        affected_user=(
            person.case.owner
            if actor is not None and person.case.owner_id != actor.pk
            else None
        ),
        object_type="person",
        object_id=person.pk,
        object_label=person.label,
        **details,
    )


def join_or_create(
    case, name: str, *, by, how: str, request=None, role: str = "", notes: str = ""
) -> tuple[Person, bool]:
    """A name that matches a Person joins it; one that matches none makes one.

    `how` is the chapter's word for the way the Person came to be: typed on the
    tab, named in the viewer, suggestion accepted, moved in.
    """
    wanted = (name or "").strip()[:60]
    if not wanted:
        raise ValueError("a person needs a name")
    found = find(case, wanted)
    if found is not None:
        return found, False
    person = Person.objects.create(
        case=case, name=wanted, role=role[:40], notes=notes[:NOTES_LENGTH], added_by=by
    )
    _row("Person added", person, by, request, how=how)
    return person, True


def on_named(
    recording, name: str, *, by, how: str, request=None, role: str = ""
) -> Person | None:
    """A Speaker was named inside a Case: the Person is joined or created.

    A Role given here goes on a Person made now and never on one that exists.
    """
    if recording.case_id is None or not (name or "").strip():
        return None
    from core.assistant import _is_a_label

    if _is_a_label(name):
        return None
    person, _ = join_or_create(
        recording.case, name, by=by, how=how, request=request, role=role
    )
    return person


def moved_in(recording, *, by, request=None) -> int:
    """A Recording moved into a Case brings its named Speakers as People."""
    transcript = getattr(recording, "transcript", None)
    if transcript is None or recording.case_id is None:
        return 0
    from core.assistant import _is_a_label

    names = (
        transcript.segments.exclude(speaker="")
        .order_by("speaker")
        .values_list("speaker", flat=True)
        .distinct()
    )
    made = 0
    for name in names:
        if _is_a_label(name):
            continue
        _, created = join_or_create(
            recording.case, name, by=by, how="moved in", request=request
        )
        made += int(created)
    return made


# The tab's operations ----------------------------------------------------------------


def rename(person: Person, new_name: str, *, by, request=None) -> int:
    """The Person and every linked Speaker across the Case, in one transaction."""
    wanted = (new_name or "").strip()[:60]
    if not wanted:
        raise ValueError("a person needs a name")
    other = find(person.case, wanted)
    if other is not None and other.pk != person.pk:
        raise ValueError("already in this case; merge instead")
    with transaction.atomic():
        changed = person.segments().update(speaker=wanted)
        person.name = wanted
        person.save(update_fields=["name", "changed"])
    _row("Person renamed", person, by, request, segments_relinked=changed)
    return changed


def edit(
    person: Person,
    *,
    role: str | None = None,
    notes: str | None = None,
    by,
    request=None,
) -> list[str]:
    fields = []
    if role is not None and role != person.role:
        person.role = role[:40]
        fields.append("role")
    if notes is not None and notes != person.notes:
        person.notes = notes[:NOTES_LENGTH]
        fields.append("notes")
    if fields:
        person.save(update_fields=[*fields, "changed"])
        _row("Person edited", person, by, request, fields=fields)
    return fields


def merge(merged: Person, survivor: Person, *, by, request=None) -> tuple[int, int]:
    """Every Speaker of the merged Person is renamed; the merged Person goes."""
    if merged.pk == survivor.pk or merged.case_id != survivor.case_id:
        raise ValueError("merge two different people of one case")
    with transaction.atomic():
        recordings = (
            merged.segments()
            .values_list("transcript__recording_id", flat=True)
            .distinct()
            .count()
        )
        changed = merged.segments().update(speaker=survivor.name)
        if merged.notes.strip():
            survivor.notes = (
                f"{survivor.notes}\n\n{merged.name}: {merged.notes}".strip()
            )[:NOTES_LENGTH]
            survivor.save(update_fields=["notes", "changed"])
        _row(
            "Person merged",
            survivor,
            by,
            request,
            survivor=str(survivor.pk),
            merged=str(merged.pk),
            segments_relinked=changed,
            recordings=recordings,
        )
        merged.delete()
    return changed, recordings


def delete(person: Person, *, by, request=None) -> int:
    """The Person's Speakers go back to their labels; the row goes."""
    from core import queue
    from core.jobs import Transcript

    unnamed = 0
    with transaction.atomic():
        transcripts = Transcript.objects.filter(
            pk__in=person.segments().values_list("transcript_id", flat=True).distinct()
        )
        for transcript in transcripts:
            unnamed += queue.unname(transcript, person.name)
        _row("Person deleted", person, by, request, segments_unnamed=unnamed)
        person.delete()
    return unnamed


# What the pages and the AI assistant read ------------------------------------------


def unnamed_by_recording(case) -> list[tuple]:
    """(recording, how many unnamed) for every Recording whose Transcript has one."""
    from core.assistant import unnamed_speakers

    found = []
    for recording in case.recordings.order_by("title"):
        transcript = getattr(recording, "transcript", None)
        if transcript is None:
            continue
        count = len(unnamed_speakers(transcript))
        if count:
            found.append((recording, count))
    return found


def _in_a_case(recording) -> bool:
    """In a Case, and Folder management On: the People show only then."""
    from core import cases

    return recording.case_id is not None and cases.folder_management_on()


def known_names(recording) -> list[str]:
    """The Known names line's list: the Case's People first, then the Vocabularies."""
    names: list[str] = []
    seen: set[str] = set()

    def take(one: str, key: str | None = None) -> None:
        key = (key if key is not None else one).strip().casefold()
        if key and key not in seen:
            seen.add(key)
            names.append(one.strip())

    if _in_a_case(recording):
        for person in Person.objects.filter(case=recording.case):
            # Shown as "Name (Role)", but the name alone is what a Vocabulary
            # entry would repeat, so the name is the key.
            take(person.shown(), key=person.name)
    for word in recording.vocabulary or []:
        take(str(word))
    for line in str(settings_store.get("office_vocabulary") or "").splitlines():
        take(line)
    return names


def role_of(recording, name: str) -> str:
    """The Role of the Person a Speaker's name matches, inside a Case; else nothing."""
    if not _in_a_case(recording) or not name:
        return ""
    person = find(recording.case, name)
    return person.role if person else ""
