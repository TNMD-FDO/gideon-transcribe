"""The Preservation copy (Phase 14 chapter 1).

One zip of a Case's work, every document in it a Word document, laid out to be saved
to the client's file of record. What the app and its people made goes in;
what was uploaded is listed and left out, since the office holds it already;
a Recording made in the app goes in, since nothing else holds it.

Every document is one of the app's own Word exports, or a Word document
written here in the same typography. PDF was the first choice and was set
aside the day it was tried (docs/research/pdf-maker.md): the free tool that
makes one lays a page out differently from Word, and a Transcript is cited
by its line numbers. The work is queued on the `media` queue, so the page
can say how far it has got and a Stop is honoured every few documents. A copy
with a hole in it would be worse than none: a document that cannot be made
fails the whole copy, by name.
"""

from __future__ import annotations

import hashlib
import io
import logging
import shutil
import uuid
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.db import models
from django.db.models import Count, Max, Q
from django.utils import timezone

log = logging.getLogger("transcribe.preservation")

QUEUED, MAKING, READY, FAILED, STOPPED = (
    "queued",
    "making",
    "ready",
    "failed",
    "stopped",
)
UNDER_WAY = (QUEUED, MAKING)

# How often the making says how far it has got and looks for a Stop: every
# so many documents, few enough that the page's count moves and a Stop is
# prompt.
EVERY = 8

SAVE_IT = "Save this file to the client's file of record."

# Who made a copy nobody pressed for: the Retention policy's deletion.
BY_THE_APP = "Gideon Transcribe"


class Failed(Exception):
    """A document that could not be written, said in the page's own words."""


class PreservationCopy(models.Model):
    """One making of a Case's Preservation copy, and the file it left."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        "core.Case", on_delete=models.CASCADE, related_name="preservation_copies"
    )
    made_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    state = models.CharField(max_length=10, default=QUEUED)
    # Why it could not be made, in the page's own words.
    reason = models.CharField(max_length=300, blank=True, default="")
    documents_total = models.IntegerField(default=0)
    documents_done = models.IntegerField(default=0)
    size_bytes = models.BigIntegerField(default=0)
    # The Case as it stood when the making began: what "behind the case" is
    # judged against.
    signature = models.CharField(max_length=64, blank=True, default="")
    created = models.DateTimeField(auto_now_add=True)
    finished = models.DateTimeField(null=True, blank=True)
    # Begun by a Delete (chapter 2): when it is ready the Case is deleted,
    # and a failure is said as "was not deleted".
    then_delete = models.BooleanField(default=False)
    # Who made it, as the page says it, for a copy the app made by itself
    # (the Retention policy's) and for one whose maker has since left.
    made_by_name = models.CharField(max_length=200, blank=True, default="")
    downloaded_at = models.DateTimeField(null=True, blank=True)
    downloaded_by_name = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["-created"]

    @property
    def path(self) -> Path:
        """In the Case's own folder, so it is binned and restored with the Case."""
        return self.case.folder / "preservation" / f"{self.pk}.zip"


OWNER, ADMIN, RETENTION = "owner", "admin", "retention"


class ArchivedCopy(models.Model):
    """The Preservation copy of a Case that is gone for good (chapter 2).

    The Case's row is gone, so what the page says about it is kept here as
    words: its name, whose it was, how it went. The owner is kept as a
    person too, while they are one, so the page can be theirs.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case_id_was = models.UUIDField(db_index=True)
    case_name = models.CharField(max_length=300)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="archived_copies",
    )
    owner_name = models.CharField(max_length=200, blank=True, default="")
    # The day the Case was gone for good: what the copy's days count from.
    gone_on = models.DateField()
    how = models.CharField(max_length=10, default=OWNER)
    gone_by_name = models.CharField(max_length=200, blank=True, default="")
    made = models.DateTimeField()
    made_by_name = models.CharField(max_length=200, blank=True, default="")
    documents = models.IntegerField(default=0)
    size_bytes = models.BigIntegerField(default=0)
    downloaded_at = models.DateTimeField(null=True, blank=True)
    downloaded_by_name = models.CharField(max_length=200, blank=True, default="")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["gone_on", "case_name"]

    @property
    def path(self) -> Path:
        """Under cases/, so every Backup has it with no change to the Backup;
        the file sweeper passes over it, looking only at Recording folders."""
        return archive_folder() / f"{self.pk}.zip"


def archive_folder() -> Path:
    return Path(settings.DATA_DIR) / "cases" / "archived"


# What the page shows ---------------------------------------------------------


def may_make(case, user) -> bool:
    """Whoever can already export each piece: the owner, a Collaborator, and
    an Admin looking in."""
    return bool(case.role_of(user))


def under_way(case) -> PreservationCopy | None:
    return case.preservation_copies.filter(state__in=UNDER_WAY).first()


def ready(case) -> PreservationCopy | None:
    return case.preservation_copies.filter(state=READY).first()


def kept_bytes(case) -> int:
    """What the Case's kept copy weighs, for the owner's room."""
    total = case.preservation_copies.filter(state=READY).aggregate(
        total=models.Sum("size_bytes")
    )["total"]
    return total or 0


def for_page(case) -> dict:
    """The part on the Details tab, as the page and its script read it."""
    from core import uploads

    making = under_way(case)
    kept = ready(case)
    latest = case.preservation_copies.first()
    failed = latest if latest is not None and latest.state == FAILED else None
    told: dict = {
        "state": "none",
        # What the Delete question says, when a copy is kept at deletion.
        "keep_days": keep_days() if at_deletion_on() else 0,
    }
    if kept is not None:
        by = _maker(kept)
        told.update(
            state="behind" if kept.signature != signature(case) else "ready",
            made=f"{timezone.localtime(kept.finished):%d %b %Y %H:%M}",
            made_day=f"{timezone.localtime(kept.finished):%d %b}",
            made_by=by,
            documents=kept.documents_total,
            size=uploads.as_size(kept.size_bytes),
            id=str(kept.pk),
        )
    if failed is not None:
        told.update(failed=failed.reason or "It could not be made.")
        if failed.then_delete:
            # A Delete that stopped because its copy could not be made.
            told["not_deleted"] = told["failed"]
        if kept is None:
            told["state"] = "failed"
    if making is not None:
        told.update(
            making=True,
            deleting=making.then_delete,
            done=making.documents_done,
            total=making.documents_total,
        )
    elif kept is not None and kept.then_delete:
        # The copy is ready and the Case is going this moment: still a
        # Delete's wait, so the page keeps asking until it is told the Case
        # has gone.
        told.update(
            making=True,
            deleting=True,
            done=kept.documents_total,
            total=kept.documents_total,
        )
    return told


def _maker(copy) -> str:
    if copy.made_by_name:
        return copy.made_by_name
    return copy.made_by.shown_name if copy.made_by else "someone who has left"


def signature(case) -> str:
    """The Case's work in one line: counts and latest dates of what a copy
    holds. Opening the Case moves none of them; adding, removing or editing
    something in it does."""
    from core.assistant import Chat, ChatTurn, SpeakerCorrection, Summary
    from core.case_chat import CaseChatTurn
    from core.chronology import Event
    from core.clips import Clip
    from core.comparison import Comparison
    from core.incident_assistant import IncidentMemo
    from core.jobs import Segment, Transcript
    from core.notes import MomentNote
    from core.people import CaseTerm, Person

    inside = Q(recording__case=case)
    facts: list = [str(case.pk), case.name]

    def add(rows, *dates):
        told = rows.aggregate(n=Count("pk"), **{d: Max(d) for d in dates})
        facts.append([told["n"], *[str(told[d] or "") for d in dates]])

    add(case.recordings.all(), "created")
    add(Transcript.objects.filter(inside), "created")
    add(Segment.objects.filter(transcript__recording__case=case))
    add(SpeakerCorrection.objects.filter(transcript__recording__case=case))
    add(Summary.objects.filter(inside), "written_at")
    add(Chat.objects.filter(inside), "created")
    add(ChatTurn.objects.filter(chat__recording__case=case))
    add(CaseChatTurn.objects.filter(chat__case=case))
    add(MomentNote.objects.filter(inside), "note_changed", "created")
    add(Event.objects.filter(incident__case=case))
    add(case.incidents.all(), "created")
    add(IncidentMemo.objects.filter(incident__case=case), "written_at")
    add(Clip.objects.filter(inside), "created")
    add(case.documents.all(), "created")
    add(
        Comparison.objects.filter(
            Q(case=case) | Q(incident__case=case) | Q(document__case=case)
        )
    )
    add(Person.objects.filter(case=case), "changed")
    add(CaseTerm.objects.filter(case=case), "created")
    return hashlib.sha256(repr(facts).encode("utf-8")).hexdigest()


# Starting and stopping -------------------------------------------------------


def start(case, by, request=None, then_delete: bool = False) -> PreservationCopy:
    """Queue a making, or hand back the one already under way. With
    `then_delete` the Case is deleted once the copy is ready (chapter 2); a
    Delete while one is being made waits for that one."""
    from core import deferring, tasks

    making = under_way(case)
    if making is not None:
        if then_delete and not making.then_delete:
            making.then_delete = True
            making.made_by = by
            making.save(update_fields=["then_delete", "made_by"])
        return making
    # A Delete that stopped earlier is answered by this making.
    case.preservation_copies.filter(state=FAILED).delete()
    copy = PreservationCopy.objects.create(
        case=case,
        made_by=by,
        documents_total=len(plan(case, by)),
        signature=signature(case),
        then_delete=then_delete,
    )
    deferring.after_commit(
        lambda: tasks.make_preservation_copy.defer(copy_id=str(copy.pk))
    )
    return copy


def stop(case, by, request=None) -> bool:
    """End the making at its next batch; nothing is left behind."""
    making = under_way(case)
    if making is None:
        # Keep the case: a Delete that stopped is no longer said on the page.
        case.preservation_copies.filter(state=FAILED, then_delete=True).delete()
        case.preservation_copies.filter(then_delete=True).update(then_delete=False)
        return False
    making.state = STOPPED
    making.finished = timezone.now()
    making.save(update_fields=["state", "finished"])
    _audit("preservation copy stopped", making, actor=by, request=request)
    return True


def _audit(event: str, copy: PreservationCopy, actor=None, request=None, **details):
    from core import audit

    case = copy.case
    by = actor or copy.made_by
    audit.write(
        audit.Category.EXPORTS,
        event,
        actor=by,
        system=None if by is not None else "preservation",
        affected_user=(case.owner if by is None or by.pk != case.owner_id else None),
        object_type="case",
        object_id=case.pk,
        object_label=case.name,
        request=request,
        **details,
    )


# At deletion, and Archived (chapter 2) ----------------------------------------


def at_deletion_on() -> bool:
    from core import settings_store

    return bool(settings_store.get("preservation_at_deletion"))


def keep_days() -> int:
    from core import settings_store

    return int(settings_store.get("preservation_copy_days"))


def usable(case) -> PreservationCopy | None:
    """The Case's kept copy, when it is not behind the case and its file is
    there: the one a deletion keeps as it is."""
    copy = ready(case)
    if copy is None or not copy.path.exists():
        return None
    return copy if copy.signature == signature(case) else None


def make_now(case, by=None) -> PreservationCopy:
    """A copy made here and now, not queued: by the nightly sweep before it
    bins a Case, and at a wipe that finds none."""
    copy = PreservationCopy.objects.create(
        case=case,
        made_by=by,
        made_by_name="" if by is not None else BY_THE_APP,
        documents_total=0,
        signature=signature(case),
    )
    make(str(copy.pk))
    copy.refresh_from_db()
    return copy


def for_the_bin(case) -> str:
    """Before the Retention policy bins a Case: its copy, unless it has one
    that is not behind. The Case is binned whatever this says."""
    if not at_deletion_on():
        return "none"
    if usable(case) is not None:
        return "kept"
    try:
        return "kept" if make_now(case).state == READY else "failed"
    except Exception:
        log.exception("the copy of %s could not be made for the bin", case.pk)
        return "failed"


def before_it_goes(case, how: str, actor=None, request=None, keep: bool = True) -> str:
    """The Case is about to be gone for good: its copy to Archived first.

    Says what became of the copy, for the Case's own audit row: kept, none
    (the office has it off), declined (deleted without one, by the person's
    second word), or failed. Never stops the deletion: whether a deletion
    may go ahead without a copy is decided before this is reached.
    """
    if not at_deletion_on():
        return "none"
    if not keep:
        return "declined"
    try:
        copy = usable(case) or make_now(case, by=actor)
        if copy.state != READY:
            return "failed"
        archive(copy, how, actor, request)
        return "kept"
    except Exception:
        log.exception("the copy of %s could not be archived", case.pk)
        return "failed"


def archive(copy: PreservationCopy, how: str, actor=None, request=None) -> ArchivedCopy:
    """Move a Case's copy out of the Case's folder, which is about to go."""
    from core import audit

    case = copy.case
    kept = ArchivedCopy(
        case_id_was=case.pk,
        case_name=case.name,
        owner=case.owner,
        owner_name=case.owner.shown_name,
        gone_on=timezone.localdate(),
        how=how,
        gone_by_name=actor.shown_name if actor is not None else "",
        made=copy.finished or timezone.now(),
        made_by_name=_maker(copy),
        documents=copy.documents_total,
        size_bytes=copy.size_bytes,
        downloaded_at=copy.downloaded_at,
        downloaded_by_name=copy.downloaded_by_name,
    )
    kept.path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(copy.path), str(kept.path))
    kept.save()
    copy.delete()
    audit.write(
        audit.Category.CASES,
        "preservation copy archived",
        actor=actor,
        system=None if actor is not None else "retention",
        affected_user=(
            case.owner if actor is None or actor.pk != case.owner_id else None
        ),
        object_type="case",
        object_id=case.pk,
        object_label=case.name,
        request=request,
        cause=how,
        days=keep_days(),
    )
    return kept


def days_left(kept: ArchivedCopy, now=None) -> int:
    """Whole days until the sweep removes it, the Off spells left out as the
    Recycle bin leaves them out. Zero or less means tonight."""
    from core import retention

    now = now or timezone.now()
    since = retention._at_midnight(kept.gone_on)
    waited = retention.whole_days(since, now) - retention.days_off_between(since, now)
    return keep_days() - max(0, waited)


def archived_for(user, owner: str = ""):
    """The copies this person sees: their own, or as an Admin everyone's."""
    if getattr(user, "is_admin", False):
        rows = ArchivedCopy.objects.all()
        return rows.filter(owner__username=owner) if owner else rows
    return ArchivedCopy.objects.filter(owner=user)


def waiting_count(user) -> int:
    """Their own copies not yet downloaded: the number on the Archived tab."""
    return ArchivedCopy.objects.filter(owner=user, downloaded_at__isnull=True).count()


def remove(kept: ArchivedCopy, cause: str, actor=None, request=None) -> None:
    """Out of Archived for good: by its days, its owner, or an Admin."""
    from core import audit

    kept.path.unlink(missing_ok=True)
    audit.write(
        audit.Category.CASES,
        "preservation copy removed",
        actor=actor,
        system=None if actor is not None else "retention",
        affected_user=(
            kept.owner if actor is None or actor.pk != kept.owner_id else None
        ),
        object_type="case",
        object_id=kept.case_id_was,
        object_label=kept.case_name,
        request=request,
        cause=cause,
        downloaded=kept.downloaded_at is not None,
    )
    kept.delete()


def sweep_archived(now=None) -> int:
    """The nightly sweep's part: every copy past its days, downloaded or not."""
    gone = 0
    for kept in list(ArchivedCopy.objects.all()):
        if days_left(kept, now) <= 0:
            remove(kept, "its days")
            gone += 1
    return gone


def downloaded(copy, by) -> None:
    """Marked on a Case's own copy and on an archived one alike."""
    copy.downloaded_at = timezone.now()
    copy.downloaded_by_name = by.shown_name
    copy.save(update_fields=["downloaded_at", "downloaded_by_name"])


# The plan: what goes in, in order --------------------------------------------


@dataclass
class Item:
    """One file of the copy: a Word document written for it, or a file
    that goes in as it is (the sound of a Recording made in the app)."""

    name: str  # the path inside the zip, without its ending
    word: Callable[[], bytes] | None = None
    file: Path | None = None


def made_here(recording) -> bool:
    """A Dictation, or a Recording made from the New recording page."""
    return bool(recording.is_dictation or recording.is_live)


def plan(case, by) -> list[Item]:
    """Every file the copy holds, in the order the zip lists them. It names the
    documents and makes none of them."""
    from core import (
        case_chronology,
        chronology,
        comparison,
        documents,
        exports,
        incident_assistant,
    )
    from core.assistant import DONE
    from core.clips import Clip
    from core.comparison import Comparison
    from core.notes import MomentNote

    # A copy the app makes by itself, for the Retention policy, is by the app.
    username = by.username if by is not None else BY_THE_APP
    shown = by.shown_name if by is not None else BY_THE_APP
    taken: set[str] = set()

    def named(folder: str, title: str) -> str:
        stem = exports.safe_name(title)
        return exports.without_clashes(taken, f"{folder}/{stem}" if folder else stem)

    items: list[Item] = [Item("00 Read me first")]
    recordings = list(
        case.recordings.select_related("transcript", "user").order_by("created")
    )
    folders: set[str] = set()
    for recording in recordings:
        if not hasattr(recording, "transcript"):
            continue
        folder = exports.without_clashes(
            folders, f"01 Recordings/{exports.safe_name(exports.title_of(recording))}"
        )
        items.append(
            Item(
                named(folder, "Transcript"),
                word=lambda r=recording: exports.word(r, username),
            )
        )
        for summary in recording.summaries.filter(state=DONE).order_by("created"):
            items.append(
                Item(
                    named(folder, _stem(exports.summary_name(summary))),
                    word=lambda s=summary: exports.summary_word(s, username),
                )
            )
        for chat in recording.chats.order_by("created"):
            if not chat.turns.filter(state=DONE).exists():
                continue
            items.append(
                Item(
                    named(folder, _stem(exports.chat_name(chat))),
                    word=lambda c=chat: exports.chat_word(c, username),
                )
            )
        if made_here(recording) and recording.original_path.exists():
            items.append(
                Item(
                    named(folder, Path(recording.original_filename).stem),
                    file=recording.original_path,
                )
            )
    for chat in case.chats.order_by("created"):
        if not chat.turns.filter(state=DONE).exists():
            continue
        items.append(
            Item(
                named("02 Case chats", _stem(exports.case_chat_name(chat))),
                word=lambda c=chat: exports.case_chat_word(c, username),
            )
        )
    notes = MomentNote.objects.filter(recording__case=case).exclude(note="")
    if notes.exists():
        items.append(
            Item(
                "03 Notes and chronology/Notes",
                word=lambda: _notes_word(case, shown),
            )
        )
    if case_chronology.days_of(case):
        items.append(
            Item(
                "03 Notes and chronology/Chronology",
                word=lambda: case_chronology.word(case, None, shown),
            )
        )
    done = Comparison.objects.filter(state="done", parent__isnull=True)
    for incident in case.incidents.order_by("created"):
        folder = exports.without_clashes(
            folders, f"04 Incidents/{exports.safe_name(incident.name)}"
        )
        items.append(
            Item(
                named(folder, "Chronology"),
                word=lambda i=incident: chronology.word(i, None, shown),
            )
        )
        memo = incident_assistant.memo_of(incident)
        if memo is not None and memo.state == incident_assistant.DONE:
            items.append(
                Item(
                    named(folder, "Memo"),
                    word=lambda m=memo: incident_assistant.memo_word(m, None, shown),
                )
            )
        for made in done.filter(incident=incident).order_by("created"):
            items.append(
                Item(
                    named(folder, f"Comparison with {made.document.title}"),
                    word=lambda m=made: comparison.word(m, shown),
                )
            )
    others = done.filter(incident__isnull=True).filter(
        Q(case=case) | Q(document__case=case)
    )
    for made in others.order_by("created"):
        items.append(
            Item(
                named("05 Comparisons", f"Comparison with {made.document.title}"),
                word=lambda m=made: comparison.word(m, shown),
            )
        )
    # A picture of the map or a timelapse saved to the Documents shelf was
    # made in the app, so the file itself goes in; a report was uploaded and
    # is listed.
    for made in case.documents.exclude(kind=documents.REPORT).order_by("created"):
        if made.original_path.exists():
            items.append(
                Item(
                    named("06 Map pictures and timelapses", made.title),
                    file=made.original_path,
                )
            )
    if Clip.objects.filter(recording__case=case).exists():
        items.append(Item("07 Record of clips", word=lambda: _clips_word(case, shown)))
    items.append(
        Item(
            "08 Recordings and documents, listed",
            word=lambda: _listed_word(case, shown),
        )
    )
    if case.people.exists() or case.terms.exists():
        items.append(
            Item("09 People and names", word=lambda: _people_word(case, shown))
        )
    items.append(Item("10 Activity record", word=lambda: _activity_word(case, shown)))
    # The first page is written last, once it can count what the rest hold.
    items[0].word = lambda: _read_me_word(case, shown, items)
    return items


def _stem(name: str) -> str:
    return name.rsplit(".", 1)[0]


def zip_name(case, when) -> str:
    from core import exports

    return f"{exports.safe_name(case.name)} - preservation copy {when:%Y-%m-%d}.zip"


# The making ------------------------------------------------------------------


def make(copy_id: str) -> None:
    """Write each document into the zip; the worker's side of Make the
    Preservation copy."""
    copy = (
        PreservationCopy.objects.select_related("case", "made_by")
        .filter(pk=copy_id, state=QUEUED)
        .first()
    )
    if copy is None:
        return
    case = copy.case
    target = copy.path
    partial = target.with_suffix(".partial")
    try:
        items = plan(case, copy.made_by)
        copy.state = MAKING
        copy.documents_total = len(items)
        copy.save(update_fields=["state", "documents_total"])
        target.parent.mkdir(parents=True, exist_ok=True)
        # A Word file and a sound file are packed already, so both are
        # stored as they are: as small, and faster.
        with zipfile.ZipFile(partial, "w", zipfile.ZIP_STORED) as bundle:
            for number, one in enumerate(items, 1):
                if number % EVERY == 1 and _stopped(copy):
                    return
                if one.word is not None:
                    try:
                        body = one.word()
                    except Exception as error:
                        log.exception("preservation copy %s: %s", copy.pk, one.name)
                        told = f"{Path(one.name).name} could not be written."
                        raise Failed(told) from error
                    bundle.writestr(f"{one.name}.docx", body)
                elif one.file is not None:
                    bundle.write(one.file, f"{one.name}{one.file.suffix}")
                if number % EVERY == 0:
                    PreservationCopy.objects.filter(pk=copy.pk).update(
                        documents_done=number
                    )
        if _stopped(copy):
            return
        partial.replace(target)
        copy.state = READY
        copy.documents_done = copy.documents_total
        copy.size_bytes = target.stat().st_size
        copy.finished = timezone.now()
        copy.save(update_fields=["state", "documents_done", "size_bytes", "finished"])
        _forget_older(copy)
        _audit(
            "preservation copy made",
            copy,
            documents=copy.documents_total,
            megabytes=round(copy.size_bytes / 1024 / 1024, 1),
        )
        if copy.then_delete and copy.made_by is not None:
            # The Delete this making was begun by (chapter 2): the copy is
            # there, so the Case goes, and the copy to Archived with it.
            from core import cases

            try:
                cases.delete(case, actor=copy.made_by)
            except Exception:
                # The copy is made and kept; the Case stays, and the page
                # stops saying it is being deleted.
                log.exception("the case %s was not deleted after its copy", case.pk)
                PreservationCopy.objects.filter(pk=copy.pk).update(then_delete=False)
    except Failed as error:
        _fail(copy, str(error))
    except Exception:
        log.exception("preservation copy %s failed", copy.pk)
        _fail(copy, "Something went wrong while it was being made.")
    finally:
        partial.unlink(missing_ok=True)


def _stopped(copy: PreservationCopy) -> bool:
    state = (
        PreservationCopy.objects.filter(pk=copy.pk)
        .values_list("state", flat=True)
        .first()
    )
    return state != MAKING


def _fail(copy: PreservationCopy, reason: str) -> None:
    changed = PreservationCopy.objects.filter(pk=copy.pk, state__in=UNDER_WAY).update(
        state=FAILED, reason=reason[:300], finished=timezone.now()
    )
    if changed:
        _audit("preservation copy failed", copy, reason=reason[:300])


def _forget_older(copy: PreservationCopy) -> None:
    """The new copy replaces the one before it, and the rows of makings that
    were stopped or failed go with it."""
    for old in copy.case.preservation_copies.exclude(pk=copy.pk).exclude(
        state__in=UNDER_WAY
    ):
        old.path.unlink(missing_ok=True)
        old.delete()


# The documents written here --------------------------------------------------


def _open(case, kind: str):
    """A document in the exports' typography with the Case's cover."""
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt

    from core import exports

    document = exports._open_record_document()
    exports._office_head(document)
    title = document.add_paragraph(case.name)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.runs[0].bold = True
    title.runs[0].font.size = Pt(20)
    said = document.add_paragraph(kind)
    said.alignment = WD_ALIGN_PARAGRAPH.CENTER
    said.runs[0].font.size = Pt(13)
    document.add_paragraph()
    return document


def _close(document, case, kind: str) -> bytes:
    from core import exports

    exports.stamp_pages(document, case.name, kind, "")
    holder = io.BytesIO()
    document.save(holder)
    return holder.getvalue()


def _heading(document, words: str) -> None:
    from docx.shared import Pt, RGBColor

    line = document.add_paragraph(words.upper())
    line.runs[0].bold = True
    line.runs[0].font.size = Pt(9)
    line.runs[0].font.color.rgb = RGBColor(0x55, 0x55, 0x55)
    line.paragraph_format.space_before = Pt(10)
    line.paragraph_format.space_after = Pt(2)


def _plural(count: int, one: str, many: str = "") -> str:
    return f"{count} {one if count == 1 else (many or one + 's')}"


def _made_line(shown: str) -> str:
    from core import exports

    return f"{timezone.localtime():{exports.DAY_AND_TIME}} by {shown}"


def _read_me_word(case, shown: str, items: list[Item]) -> bytes:
    from docx.shared import Inches, Pt

    from core import documents as shelf
    from core import exports
    from core.clips import Clip

    document = _open(case, "Preservation copy")
    box = document.add_table(rows=1, cols=1)
    box.style = "Table Grid"
    cell = box.rows[0].cells[0]
    cell.text = SAVE_IT
    cell.paragraphs[0].runs[0].bold = True
    cell.paragraphs[0].runs[0].font.size = Pt(12)
    document.add_paragraph()
    shared = ", ".join(
        sorted(one.person.shown_name for one in case.shares.select_related("person"))
    )
    exports._facts(
        document,
        [
            ("Case", case.name),
            ("Owner", case.owner.shown_name),
            ("Shared with", shared or "nobody"),
            ("Last used", f"{exports.local(case.last_activity):{exports.DAY}}"),
            ("Copy made", _made_line(shown)),
        ],
        Inches,
    )

    def count(prefix: str, ending: str = "") -> int:
        return sum(
            1
            for one in items
            if one.name.startswith(prefix) and one.name.endswith(ending)
        )

    recordings = case.recordings.count()
    here = sum(
        1
        for one in items
        if one.file is not None and one.name.startswith("01 Recordings/")
    )
    pictures = count("06 Map pictures and timelapses/")
    transcripts = count("01 Recordings/", "/Transcript")
    beside = count("01 Recordings/") - transcripts - here
    clips = Clip.objects.filter(recording__case=case).count()
    documents = case.documents.filter(kind=shelf.REPORT).count()
    _heading(document, "In this copy")
    lines = [
        _plural(transcripts, "transcript")
        + (
            f", with {_plural(beside, 'summary or chat', 'summaries and chats')}"
            if beside
            else ""
        )
        + " (folder 01)"
    ]
    if here:
        lines.append(
            _plural(here, "recording")
            + " made in the app, as recorded, beside its transcript (folder 01)"
        )
    if count("02 Case chats/"):
        lines.append(_plural(count("02 Case chats/"), "case chat") + " (folder 02)")
    if count("03 Notes and chronology/"):
        lines.append("The notes and the chronology (folder 03)")
    if count("04 Incidents/"):
        lines.append(
            _plural(case.incidents.count(), "incident")
            + ": each one's chronology, and its memo and comparisons where it has "
            "them (folder 04)"
        )
    if count("05 Comparisons/"):
        lines.append(_plural(count("05 Comparisons/"), "comparison") + " (folder 05)")
    if pictures:
        lines.append(
            _plural(
                pictures,
                "picture of the map or timelapse",
                "pictures of the map and timelapses",
            )
            + " saved in the case (folder 06)"
        )
    if clips:
        lines.append(f"A record of {_plural(clips, 'clip')} (file 07)")
    if count("09 People and names"):
        lines.append("The people and names of the case (file 09)")
    lines.append("The activity record: who did what in this case, and when (file 10)")
    for line in lines:
        document.add_paragraph(line, style="List Bullet")
    _heading(document, "Not in this copy")
    uploaded = recordings - here
    left_out = []
    if uploaded or documents:
        what = " and ".join(
            part
            for part in (
                _plural(uploaded, "recording") if uploaded else "",
                _plural(documents, "document") if documents else "",
            )
            if part
        )
        left_out.append(
            f"The {what} that were uploaded. The office holds them already; file 08 "
            "lists each by file name, size and date, to be matched to the permanent "
            "record."
        )
    if clips:
        left_out.append(
            f"The {_plural(clips, 'clip')} as files. File 07 says which recording "
            "each was cut from, and from when to when, so any of them can be cut again."
        )
    if not left_out:
        left_out.append("Nothing made in this case is left out.")
    for line in left_out:
        document.add_paragraph(line, style="List Bullet")
    _heading(document, "About these documents")
    document.add_paragraph(
        "Each transcript was made by a machine and corrected, where it was "
        "corrected, by the people named in its processing record. Summaries, chat "
        "answers, memos and comparisons were written by an AI assistant from those "
        "transcripts and are not evidence. Each document carries its own notices."
    )
    return _close(document, case, "Preservation copy")


def _notes_word(case, shown: str) -> bytes:
    from docx.shared import Inches, Pt, RGBColor

    from core import exports
    from core.notes import MomentNote

    document = _open(case, "Notes")
    notes = (
        MomentNote.objects.filter(recording__case=case)
        .exclude(note="")
        .select_related("recording", "note_by")
        .order_by("recording__created", "at")
    )
    document.add_paragraph(
        f"The {_plural(notes.count(), 'note')} written in this case, by recording "
        f"and by time. Made {_made_line(shown)}."
    )
    last = None
    for one in notes:
        if one.recording_id != last:
            last = one.recording_id
            head = document.add_paragraph(exports.title_of(one.recording))
            head.runs[0].bold = True
            head.paragraph_format.space_before = Pt(12)
        line = document.add_paragraph()
        line.paragraph_format.left_indent = Inches(0.3)
        stamp = line.add_run(f"[{exports.clock(one.at)}] ")
        stamp.font.name = "Consolas"
        stamp.font.size = Pt(10)
        line.add_run(one.note)
        who = one.note_by.shown_name if one.note_by else "someone who has left"
        when = one.note_changed or one.created
        said = document.add_paragraph(
            f"{who}, {exports.local(when):{exports.DAY_AND_TIME}}"
            + (" · marked to check" if one.note_to_check else "")
        )
        said.paragraph_format.left_indent = Inches(0.3)
        said.runs[0].font.size = Pt(9)
        said.runs[0].font.color.rgb = RGBColor(0x55, 0x55, 0x55)
    return _close(document, case, "Notes")


def _clips_word(case, shown: str) -> bytes:
    from docx.shared import Inches, Pt, RGBColor

    from core import exports
    from core.clips import Clip

    document = _open(case, "Record of clips")
    clips = list(
        Clip.objects.filter(recording__case=case)
        .select_related("recording", "user", "incident")
        .order_by("created")
    )
    document.add_paragraph(
        f"The {_plural(len(clips), 'clip')} cut in this case. The clip files are not "
        "in this copy: each can be cut again from the recording named, between the "
        f"two times given. Made {_made_line(shown)}."
    )
    for number, clip in enumerate(clips, 1):
        top = document.add_paragraph(f"{number}. {clip.title}")
        top.runs[0].bold = True
        top.paragraph_format.space_before = Pt(12)
        who = clip.user.shown_name if clip.user else "someone who has left"
        rows = [
            ("Cut from", clip.recording.original_filename),
            (
                "From and to",
                f"{exports.clock(clip.start)} to {exports.clock(clip.end)} "
                f"({round(clip.end - clip.start)} s)",
            ),
            ("Made", f"{exports.local(clip.created):{exports.DAY_AND_TIME}} by {who}"),
            ("Incident", clip.incident.name if clip.incident_id else "none"),
            ("Captions burned in", "yes" if clip.burn_captions else "no"),
        ]
        if clip.note:
            rows.append(("Note", clip.note))
        exports._facts(document, rows, Inches)
        if not hasattr(clip.recording, "transcript"):
            continue
        said = clip.recording.transcript.segments.filter(
            start__gte=clip.start, start__lt=clip.end
        ).order_by("start")
        for one in said:
            line = document.add_paragraph()
            line.paragraph_format.left_indent = Inches(0.3)
            line.paragraph_format.space_after = Pt(0)
            stamp = line.add_run(f"[{exports.clock(one.start)}] ")
            stamp.font.name = "Consolas"
            stamp.font.size = Pt(9)
            stamp.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
            words = line.add_run(
                (f"{one.speaker}: " if one.speaker else "") + (one.english or one.text)
            )
            words.font.size = Pt(10)
    return _close(document, case, "Record of clips")


def _table(document, heads: list[str], rows: list[list[str]], small: int = 8):
    from docx.shared import Pt

    table = document.add_table(rows=1, cols=len(heads))
    table.style = "Table Grid"
    for cell, words in zip(table.rows[0].cells, heads, strict=True):
        cell.text = words
        for run in cell.paragraphs[0].runs:
            run.bold = True
            run.font.size = Pt(small)
    for row in rows:
        cells = table.add_row().cells
        for cell, words in zip(cells, row, strict=True):
            cell.text = str(words)
            for run in cell.paragraphs[0].runs:
                run.font.size = Pt(small)
    return table


def _listed_word(case, shown: str) -> bytes:
    from core import documents as shelf
    from core import exports, uploads

    document = _open(case, "Recordings and documents, listed")
    document.add_paragraph(
        "What was brought to this case, to be matched to the permanent record. The "
        "files themselves are not in this copy, but for a recording made in the "
        f"app, which is marked. Made {_made_line(shown)}."
    )
    recordings = case.recordings.select_related("user").order_by("created")
    _heading(document, _plural(recordings.count(), "recording"))
    _table(
        document,
        ["File", "Size", "Length", "Uploaded", "By", "SHA-256"],
        [
            [
                one.original_filename
                + (" (made in the app; in this copy)" if made_here(one) else ""),
                uploads.as_size(one.size_bytes),
                exports.length_of(one),
                f"{exports.local(one.created):{exports.DAY}}",
                one.user.shown_name if one.user else "",
                one.sha256,
            ]
            for one in recordings
        ],
        small=7,
    )
    documents = (
        case.documents.filter(kind=shelf.REPORT)
        .select_related("added_by")
        .order_by("created")
    )
    if documents.exists():
        _heading(document, _plural(documents.count(), "document"))
        _table(
            document,
            ["Title", "File", "Size", "Pages", "Added", "By"],
            [
                [
                    one.title,
                    one.original_filename,
                    uploads.as_size(one.size_bytes),
                    one.pages or "",
                    f"{exports.local(one.created):{exports.DAY}}",
                    one.added_by.shown_name if one.added_by else "",
                ]
                for one in documents
            ],
        )
    return _close(document, case, "Recordings and documents, listed")


def _people_word(case, shown: str) -> bytes:
    document = _open(case, "People and names")
    document.add_paragraph(
        "The people named in this case and the places and terms it keeps, as the "
        f"Details tab holds them. Made {_made_line(shown)}."
    )
    people = case.people.order_by("name")
    if people.exists():
        _heading(document, _plural(people.count(), "person", "people"))
        _table(
            document,
            ["Name", "Role", "Also called", "Also heard as", "Notes"],
            [
                [
                    one.name,
                    one.role,
                    ", ".join(one.also_called or []),
                    ", ".join(one.also_heard_as or []),
                    one.notes,
                ]
                for one in people
            ],
            small=9,
        )
    terms = case.terms.order_by("term")
    if terms.exists():
        _heading(document, _plural(terms.count(), "place or term", "places and terms"))
        _table(
            document,
            ["Place or term", "Also heard as"],
            [[one.term, ", ".join(one.also_heard_as or [])] for one in terms],
            small=9,
        )
    return _close(document, case, "People and names")


def _activity_word(case, shown: str) -> bytes:
    from core import exports
    from core.audit import Row
    from core.clips import Clip

    document = _open(case, "Activity record")
    ids = {str(case.pk)}
    ids.update(str(pk) for pk in case.recordings.values_list("pk", flat=True))
    ids.update(str(pk) for pk in case.incidents.values_list("pk", flat=True))
    ids.update(str(pk) for pk in case.chats.values_list("pk", flat=True))
    ids.update(str(pk) for pk in case.documents.values_list("pk", flat=True))
    ids.update(
        str(pk)
        for pk in Clip.objects.filter(recording__case=case).values_list("pk", flat=True)
    )
    rows = Row.objects.filter(object_id__in=ids).order_by("at")
    first = rows.first()
    reach = (
        f"The audit log reaches back to {exports.local(first.at):{exports.DAY}} for "
        "this case; the office's Audit retention setting removes older rows."
        if first
        else "The audit log holds no row about this case."
    )
    document.add_paragraph(
        f"What was done in this case and to what, oldest first, as the app's audit "
        f"log records it. {reach} Made {_made_line(shown)}."
    )
    if first:
        _table(
            document,
            ["When", "Who", "What", "To what"],
            [
                [
                    f"{exports.local(one.at):%d %b %Y %H:%M}",
                    one.actor_username or one.actor_kind,
                    one.event
                    + (
                        f" ({one.details['kind']})"
                        if isinstance(one.details, dict) and one.details.get("kind")
                        else ""
                    ),
                    one.object_label,
                ]
                for one in rows
            ],
        )
    return _close(document, case, "Activity record")
