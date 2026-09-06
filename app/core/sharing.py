"""Sharing: a Case's owner lets named colleagues in.

A Share is one row naming one Case and one person. There is one kind: whoever
a Case is shared with, a Collaborator, can do inside it everything the owner
can, short of sharing, renaming, transferring, or deleting the Case, and short
of throwing away a Recording somebody else brought in. Nothing inside a
shared Case is private: one Case, one page, and everyone in it sees the same
Transcripts, People, Summaries, Chats, and Clips.

The Sharing setting hides every Share while it is off and deletes none of
them, and it needs Folder management, which hides every Case. Both toggles
keep the rows, so On brings everything back as it was.

The "case shared with you" mail is the Email notifications chapter's, which is
not built: the Share is recorded here and the mail waits.
"""

from __future__ import annotations

import logging

from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from core import audit, settings_store

log = logging.getLogger(__name__)

CATEGORY = audit.Category.CASES

# The words the owner reads before confirming, and the "case shared with you"
# mail repeats. Fixed wording in the app and the user guide, not a setting.
WORDS = (
    "They will be able to do everything in this case except share, rename, "
    "or delete it: add recordings, correct transcripts, name speakers, ask "
    "for summaries and chats, and save clips.",
    "Recordings they add count against your storage space.",
)

# The words an owner reads before handing a Case over.
TRANSFER_WORDS = (
    "They become the owner: the case counts against their storage space, and "
    "sharing, renaming, and deleting it become theirs.",
    "You stay on the case as a collaborator, and can leave it whenever you like.",
)


class Share(models.Model):
    """One Case, opened to one colleague."""

    case = models.ForeignKey(
        "core.Case", on_delete=models.CASCADE, related_name="shares"
    )
    person = models.ForeignKey(
        "core.User", on_delete=models.CASCADE, related_name="shares"
    )
    added_by = models.ForeignKey(
        "core.User", on_delete=models.SET_NULL, null=True, related_name="+"
    )
    added_on = models.DateTimeField(default=timezone.now)

    # When the Collaborator last opened the Case, kept here so the owner's
    # "who has seen this" outlives Audit retention. Empty until the first
    # opening, which is what the New mark on their Cases page reads.
    last_opened = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["case", "person"], name="one_share_per_person_per_case"
            )
        ]
        ordering = ["added_on"]

    def __str__(self) -> str:
        return f"{self.case_id} with {self.person_id}"

    @property
    def status(self) -> str:
        """Empty while the person is Active; else their status word, greyed."""
        word = self.person.status
        return "" if word == "active" else word


# The setting ------------------------------------------------------------------------


def on() -> bool:
    """Whether Shares are in force: the Sharing toggle, under Folder management."""
    return bool(settings_store.get("folder_management")) and bool(
        settings_store.get("sharing")
    )


# Who is in a Case -------------------------------------------------------------------


def is_collaborator(case, user) -> bool:
    """Whether this person holds a Share on this Case, while Sharing is on.

    A Deactivated or Blocked Collaborator cannot sign in, so their Share is
    not tested for that here; it is shown greyed on the owner's panel and
    works again if the directory readmits them.
    """
    if user is None or not getattr(user, "pk", None) or not on():
        return False
    return Share.objects.filter(case=case, person_id=user.pk).exists()


def shared_with(user):
    """The Cases shared with this person, out of the bin, while Sharing is on."""
    from core.cases import Case

    if not on():
        return Case.objects.none()
    return Case.objects.filter(shares__person=user, deleted_on__isnull=True)


def collaborators(case):
    """The Shares on a Case, oldest first, with their people."""
    return case.shares.select_related("person", "added_by").order_by("added_on")


def shares_of(user):
    """The Shares this person holds, for their Cases page's New marks."""
    return Share.objects.filter(person=user)


def note_opened(case, user) -> None:
    """A Collaborator opened the Case: the Share remembers when."""
    Share.objects.filter(case=case, person_id=user.pk).update(
        last_opened=timezone.now()
    )


# Who may be shared with -------------------------------------------------------------


def candidates(case):
    """The people a Case may be shared with.

    Accounts that have signed in at least once and are Active, minus the owner
    and the existing Collaborators. Local admins are not offered: they are
    the break-glass accounts, not colleagues.
    """
    from core.models import User

    return (
        User.objects.filter(
            last_sign_in__isnull=False,
            deactivated_at__isnull=True,
            blocked_at__isnull=True,
            is_local=False,
        )
        .exclude(pk=case.owner_id)
        .exclude(shares__case=case)
        .order_by("display_name", "username")
    )


class NotFound(Exception):
    """No one, or more than one person, answers to what was typed."""


def find(case, typed: str):
    """The one candidate a typed name or username means.

    The username exactly, else the display name exactly, else one person
    whose display name or username contains what was typed. Two people who
    both match is a question back, not a guess.
    """
    typed = typed.strip()
    if not typed:
        raise NotFound("Type a colleague's name.")
    people = candidates(case)
    exact = people.filter(username__iexact=typed).first()
    if exact is None:
        named = list(people.filter(display_name__iexact=typed)[:2])
        if len(named) == 1:
            exact = named[0]
        elif len(named) > 1:
            raise NotFound(
                f'More than one person is called "{typed}". Use their username.'
            )
    if exact is None:
        found = list(
            people.filter(
                Q(display_name__icontains=typed) | Q(username__icontains=typed)
            )[:2]
        )
        if len(found) == 1:
            exact = found[0]
        elif len(found) > 1:
            raise NotFound(
                f'More than one person matches "{typed}". Type more of the name.'
            )
    if exact is None:
        raise NotFound(
            f'Nobody called "{typed}" can be shared with. A colleague appears '
            "here once they have signed in to the app."
        )
    return exact


# Granting and taking back -----------------------------------------------------------


def _affected(case, actor):
    return case.owner if case.owner_id != actor.pk else None


@transaction.atomic
def grant(case, person, actor, request=None, cause: str = "") -> Share:
    """Share the Case with one person, and say so in the log.

    Sharing again with somebody already on the Case changes nothing and
    writes nothing. The Case's clock moves, because sharing is use.
    """
    share, made = Share.objects.get_or_create(
        case=case, person=person, defaults={"added_by": actor}
    )
    if not made:
        return share
    audit.write(
        CATEGORY,
        "Share granted",
        actor=actor,
        affected_user=_affected(case, actor),
        object_type="case",
        object_id=case.pk,
        object_label=case.name,
        request=request,
        collaborator=person.username,
        **({"cause": cause} if cause else {}),
    )
    from core import cases

    cases.note_activity(case, by=actor)
    _case_shared_mail(share)
    return share


def revoke(share: Share, actor, request=None) -> None:
    """Take a Share back. Whatever the Collaborator added stays in the Case."""
    case = share.case
    person = share.person
    share.delete()
    audit.write(
        CATEGORY,
        "Share revoked",
        actor=actor,
        affected_user=_affected(case, actor),
        object_type="case",
        object_id=case.pk,
        object_label=case.name,
        request=request,
        collaborator=person.username,
    )


@transaction.atomic
def transfer(case, to_whom, actor, request=None) -> None:
    """The owner gives the Case to a colleague and stays on it as a Collaborator.

    The Case reassigned row is the one Reassign writes, so the log reads the
    same whichever way a Case changed hands; the old owner's Share writes its
    own "Share granted" beside it, and the new owner's Share, if they had one,
    ends because an owner needs none. The clock does not move: handing a
    Case over is not use, and the new owner inherits the days left.
    """
    was = case.owner
    case.owner = to_whom
    case.save(update_fields=["owner"])
    Share.objects.filter(case=case, person=to_whom).delete()
    audit.write(
        CATEGORY,
        "case reassigned",
        actor=actor,
        affected_user=was,
        object_type="case",
        object_id=case.pk,
        object_label=case.name,
        request=request,
        to=to_whom.username,
        cause="transfer",
    )
    share, _ = Share.objects.get_or_create(
        case=case, person=was, defaults={"added_by": actor}
    )
    audit.write(
        CATEGORY,
        "Share granted",
        actor=actor,
        affected_user=None,
        object_type="case",
        object_id=case.pk,
        object_label=case.name,
        request=request,
        collaborator=was.username,
        cause="transfer",
    )
    _case_handed_mail(case, was, to_whom)


def _case_shared_mail(share: Share) -> None:
    """The "case shared with you" Notification: the Email chapter's, not built.

    The event is counted in the log so the chapter has something to hook, and
    nothing is sent. A Deactivated or Blocked Collaborator would not be mailed.
    """
    if share.person.status == "active":
        log.info(
            "a 'case shared with you' notification would go to %s",
            share.person.username,
        )


def _case_handed_mail(case, was, to_whom) -> None:
    """The "case handed to you" Notification, likewise waiting for the Email chapter."""
    if to_whom.status == "active":
        log.info("a 'case handed to you' notification would go to %s", to_whom.username)
