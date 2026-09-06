"""Cases: a place a Recording lives after the person who uploaded it signs out.

A Case is a page, not a folder the user browses, and the only thing anybody
types about one is its name. The Recording is still the unit: a Case holds
Recordings, and everything the Workspace could do to a Recording it can do to
one in a Case.

Everything here is invisible until the Folder management setting is on. Off
hides and never deletes: the rows stay, the files under `cases/` stay, and
turning it on again brings back exactly what was hidden.

Two words are used with one meaning throughout, as the Retention chapter
fixes them: **deleted** means moved to the Recycle bin, where a Case can
still be restored; **wiped** means gone for good, files and rows. A person's
own Delete is a wipe under the older name, and is final.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from django.conf import settings as django_settings
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from core import audit, settings_store

CATEGORY = audit.Category.CASES

# The three causes a "case permanently deleted" row may carry.
WIPED_BY_THE_BIN = "recycle bin period"
WIPED_BY_OWNER = "owner"
WIPED_BY_ADMIN = "admin"


def cases_root() -> Path:
    """Where every Case's files live, beside scratch/."""
    return Path(django_settings.DATA_DIR) / "cases"


def folder_management_on() -> bool:
    """Whether Cases exist as far as anybody using the app can tell."""
    return bool(settings_store.get("folder_management"))


class Case(models.Model):
    """One case: a name, an owner, and the Recordings kept in it."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # The only field a person types. Not unique: two people may have a case of
    # the same name, and one person is warned but not stopped.
    name = models.CharField(max_length=200)

    owner = models.ForeignKey(
        "core.User", on_delete=models.PROTECT, related_name="cases"
    )

    created = models.DateTimeField(auto_now_add=True)

    # The Retention policy's clock. Moved by note_activity() for the acts the
    # specification counts, never by an Admin looking in.
    last_activity = models.DateTimeField(default=timezone.now)

    # The day the retention sweep first found this Case inside its warning
    # window and wrote the "retention warning" row. Cleared by any activity,
    # so the row is written once per approach to the edge and not nightly.
    warned_on = models.DateField(null=True, blank=True)

    # Filled the night the retention sweep deletes the Case into the Recycle
    # bin. A Case with a date here is out of every list and unusable until it
    # is restored or wiped; its files and rows stay meanwhile.
    deleted_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["owner", "name"])]

    def __str__(self) -> str:
        return f"{self.name} ({self.id})"

    @property
    def folder(self) -> Path:
        """Ids only, never the name, so a rename moves nothing on disk."""
        return cases_root() / str(self.id)

    @property
    def is_binned(self) -> bool:
        return self.deleted_on is not None

    def disk_bytes(self) -> int:
        if not self.folder.exists():
            return 0
        return sum(
            path.stat().st_size for path in self.folder.rglob("*") if path.is_file()
        )

    def member(self, user) -> str:
        """What this person is inside the Case: "owner", "collaborator", or "".

        A member's use is the Case's activity and needs no Admin access row.
        A Collaborator is one only while Sharing is on.
        """
        if self.owner_id == user.pk:
            return "owner"
        from core import sharing

        return "collaborator" if sharing.is_collaborator(self, user) else ""

    def role_of(self, user) -> str:
        """How this person stands to the Case: owner, collaborator, admin, or "".

        An Admin who is a member is a colleague on this Case, not an Admin
        looking in: no banner, no Admin access row, and their use counts.
        """
        return self.member(user) or (
            "admin" if getattr(user, "is_admin", False) else ""
        )

    def may_be_opened_by(self, user) -> bool:
        """Who may open this Case.

        The owner, a Collaborator, and an Admin under the Admin access rule
        (ADR 0004), which writes its own row and does not count as activity.
        Nobody may open a Case in the Recycle bin: it is restored first, or it
        is gone.
        """
        if self.is_binned:
            return False
        return bool(self.role_of(user))

    def may_be_run_by(self, user) -> bool:
        """Who may rename, share, transfer, or delete the Case: the owner and Admins."""
        return self.owner_id == user.pk or bool(getattr(user, "is_admin", False))


def reachable(recording) -> bool:
    """Whether a Recording's Case, if it has one, is out of the Recycle bin.

    Asked by every gate that hands out a Recording's bytes or pages: the
    viewer, the media gate, the exports, and the Clips. A Recording in a
    binned Case is nobody's until the Case is restored, an Admin's included.
    """
    return not recording.case_id or not recording.case.is_binned


def standing(recording, user) -> str:
    """How this person stands to a Recording: "own", "admin", or "".

    "own" is the person who uploaded it, or a member of its Case (the owner
    or a Collaborator): they work in it as their own, and nothing is written
    about their looking. "admin" is an Admin looking into somebody else's
    material under the Admin access rule (ADR 0004), which writes a row each
    time. "" is nobody, told "not found" rather than "not yours". A Recording
    in a binned Case is "" to everybody until the Case is restored.
    """
    if not reachable(recording):
        return ""
    if recording.user_id == user.pk:
        return "own"
    if recording.case_id and recording.case.member(user):
        return "own"
    if getattr(recording, "is_dictation", False):
        from core import dictation

        if dictation.is_recipient(recording, user):
            return "own"
    return "admin" if getattr(user, "is_admin", False) else ""


def may_throw_away(recording, user) -> bool:
    """Who may delete a Recording, process it again, or move it elsewhere.

    An action that throws away somebody else's work belongs to the owner of
    the Case, an Admin, or the person who brought that Recording in. A
    Collaborator may do it only to the Recordings they added themselves.
    """
    if not reachable(recording):
        return False
    if recording.user_id == user.pk or getattr(user, "is_admin", False):
        return True
    return bool(recording.case_id and recording.case.owner_id == user.pk)


def affected_by(recording, user):
    """Whose material an act on this Recording touches, for the audit row.

    The Case's owner when the Recording is in a Case (a Collaborator's or an
    Admin's act on a shared Case names the owner), else the uploader; and
    nobody when it is the actor's own.
    """
    whose = recording.case.owner if recording.case_id else recording.user
    return whose if whose.pk != user.pk else None


class OffSpell(models.Model):
    """A span during which Folder management was off.

    The Retention policy counts days of neglect, and days nobody could reach a
    Case are not neglect, so these spans are subtracted from every count. The
    row is kept whether or not the retention sweep exists yet: the days have to
    be recorded as they pass, because they cannot be worked out afterwards.
    """

    TOGGLE = "toggle"
    RESTORE = "restore"
    CAUSES = [(TOGGLE, "the setting was turned off"), (RESTORE, "a restore")]

    started = models.DateTimeField(default=timezone.now)
    ended = models.DateTimeField(null=True, blank=True)
    cause = models.CharField(max_length=10, choices=CAUSES, default=TOGGLE)

    class Meta:
        ordering = ["-started"]

    def __str__(self) -> str:
        return f"off from {self.started:%Y-%m-%d %H:%M}"


def open_spell(cause: str = OffSpell.TOGGLE) -> OffSpell | None:
    """The spell running now, if the app is inside one."""
    return OffSpell.objects.filter(ended__isnull=True, cause=cause).first()


def note_the_toggle(now_on: bool) -> None:
    """Start or end an Off spell as the setting changes.

    Called after the value is written, so what it reads is the new one. Turning
    it off twice in a row leaves one spell open, not two.
    """
    running = open_spell()
    if now_on:
        if running is not None:
            running.ended = timezone.now()
            running.save(update_fields=["ended"])
    elif running is None:
        OffSpell.objects.create(cause=OffSpell.TOGGLE)


def off_since():
    """When the current Off spell began, for the status page's line."""
    running = open_spell()
    return running.started if running else None


def _start_the_clock_over(case: Case) -> None:
    case.last_activity = timezone.now()
    case.warned_on = None
    case.save(update_fields=["last_activity", "warned_on"])


def note_activity(case: Case, by=None) -> None:
    """Move the Retention clock, for the acts the specification counts.

    The owner's use and a Collaborator's use both count. An Admin looking
    into somebody else's Case is not use, so it does not count, matching the
    Workspace rule. Nothing else here decides: every caller is a place the
    chapter names. Any activity also lifts the warning, so the next approach
    to the edge is warned about afresh.
    """
    if by is not None and not case.member(by):
        return
    _start_the_clock_over(case)


def used(recording, by) -> None:
    """The Retention clock, moved by an act on a Recording in a Case.

    Called from the places the chapter counts: opening a Recording, correcting
    a Segment, naming a Speaker, exporting, and saving a Clip. A Recording in
    no Case does nothing here, so every caller can call it without asking
    first.
    """
    if recording.case_id:
        note_activity(recording.case, by=by)


def keep(case: Case, actor, request=None) -> None:
    """Keep: one click that starts the clock over, as opening the Case would.

    It exists so a person who has seen the warning and knows they still need
    the Case does not have to open a Recording to prove it. Anybody who sees
    the mark may press it, an Admin included, and that is the one way an
    Admin's act moves a clock, so it is audited with the owner as the
    affected user.
    """
    _start_the_clock_over(case)
    audit.write(
        CATEGORY,
        "case kept",
        actor=actor,
        affected_user=case.owner if case.owner_id != actor.pk else None,
        object_type="case",
        object_id=case.pk,
        object_label=case.name,
        request=request,
    )


def recording_types() -> list[str]:
    """The labels a person may put on a Recording."""
    lines = settings_store.get("recording_types") or []
    if isinstance(lines, str):
        lines = lines.splitlines()
    return [one.strip() for one in lines if one.strip()]


def cases_for(user):
    """The Cases this person may put a Recording into.

    Their own and the ones shared with them, and none that is in the Recycle
    bin. Their own come first.
    """
    from core import sharing

    own = Q(owner=user)
    if sharing.on():
        own = own | Q(shares__person=user)
    return (
        Case.objects.filter(own, deleted_on__isnull=True)
        .distinct()
        .select_related("owner")
    )


def own_cases_for(user):
    """This person's own Cases, out of the Recycle bin."""
    return Case.objects.filter(owner=user, deleted_on__isnull=True)


def binned_for(user):
    """This person's Cases in the Recycle bin."""
    return Case.objects.filter(owner=user, deleted_on__isnull=False)


def name_already_used(user, name: str, besides=None) -> bool:
    """Whether another Case this person can see carries the same name.

    A warning, never a refusal: two cases may share a name.
    """
    others = cases_for(user).filter(name__iexact=name.strip())
    if besides is not None:
        others = others.exclude(pk=besides.pk)
    return others.exists()


def create(user, name: str, request=None) -> Case:
    case = Case.objects.create(owner=user, name=name.strip()[:200])
    audit.write(
        CATEGORY,
        "case created",
        actor=user,
        object_type="case",
        object_id=case.pk,
        object_label=case.name,
        request=request,
    )
    return case


def rename(case: Case, name: str, actor, request=None) -> None:
    was = case.name
    case.name = name.strip()[:200]
    case.save(update_fields=["name"])
    audit.write(
        CATEGORY,
        "case renamed",
        actor=actor,
        affected_user=case.owner,
        object_type="case",
        object_id=case.pk,
        object_label=case.name,
        request=request,
        was=was,
    )
    note_activity(case, by=actor)


def move_recording(recording, case: Case, actor, description="", request=None) -> None:
    """Put a Done Recording into a Case, or into another one.

    On disk this is a rename inside the same filesystem, so it is instant
    whatever the size. In the database it is one field. Both have to happen or
    neither: the folder is moved first, and it is put back if the row will not
    take.
    """
    from_case = recording.case
    if from_case is not None and from_case.pk == case.pk:
        return

    was = recording.folder
    recording.case = case
    now = recording.folder
    now.parent.mkdir(parents=True, exist_ok=True)

    if was.exists():
        shutil.move(str(was), str(now))
    try:
        with transaction.atomic():
            fields = ["case"]
            if description:
                recording.description = description[:2000]
                fields.append("description")
            recording.save(update_fields=fields)
    except Exception:
        # The row did not take, so the bytes go back where the row still says
        # they are.
        if now.exists():
            shutil.move(str(now), str(was))
        recording.case = from_case
        raise
    # A Recording moved in brings its named Speakers as People of the Case.
    from core import people

    people.moved_in(recording, by=actor, request=request)

    audit.write(
        CATEGORY,
        "recording moved between cases" if from_case else "recording moved to case",
        actor=actor,
        affected_user=case.owner,
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.title,
        request=request,
        case=case.name,
        **({"from_case": from_case.name} if from_case else {}),
    )
    note_activity(case, by=actor)


# Ways out of a Case -----------------------------------------------------------


def _remove_everything(case: Case, actor, request, recording_cause: str):
    """Take every Recording and the folder off the disk and out of the database.

    One audit row per Recording, as the Discard writes one per Recording it
    removes. The Case's own row is the caller's to write, because the three
    callers say three different things about why.
    """
    from core import lifecycle

    recordings = list(case.recordings.all())
    gigabytes = round(case.disk_bytes() / (1024**3), 1)
    for recording in recordings:
        lifecycle.remove_recording(
            recording, cause=recording_cause, actor=actor, request=request
        )
    shutil.rmtree(case.folder, ignore_errors=True)
    return len(recordings), gigabytes


def delete(case: Case, actor, request=None) -> tuple[int, int]:
    """A person's own Delete of a Case. Final: there is no way back.

    The Recycle bin is for what the clock takes, never for this.
    """
    cause = WIPED_BY_OWNER if case.owner_id == actor.pk else WIPED_BY_ADMIN
    count, gigabytes = _remove_everything(case, actor, request, cause)
    audit.write(
        CATEGORY,
        "case deleted",
        actor=actor,
        affected_user=case.owner,
        object_type="case",
        object_id=case.pk,
        object_label=case.name,
        request=request,
        recordings=count,
        gigabytes=gigabytes,
    )
    case.delete()
    return count, gigabytes


def put_in_the_bin(case: Case, on=None) -> tuple[int, float]:
    """The retention sweep's deletion: into the Recycle bin, whole.

    Nothing leaves the disk and no row is removed. The Case gets its deleted-on
    date, which takes it out of every list and every picker and makes every
    Recording in it unreachable, and the bin's own clock starts from that date.
    """
    count = case.recordings.count()
    gigabytes = round(case.disk_bytes() / (1024**3), 1)
    case.deleted_on = on or timezone.localdate()
    case.save(update_fields=["deleted_on"])
    audit.write(
        CATEGORY,
        "case deleted",
        system="retention",
        affected_user=case.owner,
        object_type="case",
        object_id=case.pk,
        object_label=case.name,
        cause="retention",
        recordings=count,
        gigabytes=gigabytes,
    )
    return count, gigabytes


def restore(case: Case, actor, request=None) -> None:
    """Put a binned Case back exactly as it was, and start its clock over.

    Over, because otherwise the clock that put it in the bin would put it
    straight back the same night. Nothing moved on disk, so a full quota never
    blocks this: the Case never left.
    """
    case.deleted_on = None
    case.warned_on = None
    case.last_activity = timezone.now()
    case.save(update_fields=["deleted_on", "warned_on", "last_activity"])
    audit.write(
        CATEGORY,
        "case restored",
        actor=actor,
        affected_user=case.owner if case.owner_id != actor.pk else None,
        object_type="case",
        object_id=case.pk,
        object_label=case.name,
        request=request,
    )


def wipe(case: Case, cause: str, actor=None, request=None) -> tuple[int, float]:
    """Gone for good: files and rows, nothing left, no recovery.

    Three causes: the bin's period, by the sweep with no actor; the owner
    emptying their bin or deleting one Case from it; an Admin doing either, or
    wiping a leaver's binned Cases from the Users page. The per-Recording rows
    say "retention" whichever it was, as the chapter fixes.
    """
    count, gigabytes = _remove_everything(case, actor, request, "retention")
    audit.write(
        CATEGORY,
        "case permanently deleted",
        actor=actor,
        system=None if actor is not None else "retention",
        affected_user=(
            case.owner if actor is None or actor.pk != case.owner_id else None
        ),
        object_type="case",
        object_id=case.pk,
        object_label=case.name,
        request=request,
        cause=cause,
        recordings=count,
        gigabytes=gigabytes,
    )
    case.delete()
    return count, gigabytes
