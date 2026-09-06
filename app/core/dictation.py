"""Dictation: a recording of one person's speech, kept on its own (Phase 3).

A Dictation is a Recording made on the Dictate page, kept past sign-out, the
person's alone until sent, in no Case unless they add it to one afterwards.
Its product is a Memo: a Summary written by the shipped Dictation memo
template, which writes the dictated words out and never summarises. Send to
hands one Dictation to one colleague, who reads it under "Sent to you" on
their own Dictations page.

The office's Retention period applies to each Dictation on its own: days
since it was last used, no Recycle bin.
"""

from __future__ import annotations

import logging

from django.db import models, transaction
from django.utils import timezone

from core import audit, settings_store
from core.recordings import Recording

log = logging.getLogger(__name__)

CATEGORY = audit.Category.RECORDINGS
TYPE = "Dictation"

# The words a person reads before sending, fixed in the app.
SEND_WORDS = (
    "They will see this recording, its transcript, and its memo or summary "
    "under Sent to you on their Record tab, and they will be mailed that it "
    "is there.",
)
SEND_WORDS_WITH_FILE = SEND_WORDS + (
    "The memo or summary, as a Word file, and the recording itself will be "
    "attached to that mail.",
)


class DictationShare(models.Model):
    """One Dictation, sent to one colleague."""

    recording = models.ForeignKey(
        "core.Recording", on_delete=models.CASCADE, related_name="dictation_shares"
    )
    person = models.ForeignKey(
        "core.User", on_delete=models.CASCADE, related_name="dictations_received"
    )
    sent_by = models.ForeignKey(
        "core.User", on_delete=models.SET_NULL, null=True, related_name="+"
    )
    sent_on = models.DateTimeField(default=timezone.now)
    last_opened = models.DateTimeField(null=True, blank=True)
    # Whether the Memo rode with the mail, for the row and the page.
    attached = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["recording", "person"], name="one_dictation_share_per_person"
            )
        ]
        ordering = ["sent_on"]


# The setting --------------------------------------------------------------------


def on() -> bool:
    """Whether the Dictations tab exists: the setting, under Live recording."""
    from core import live

    return live.on() and bool(settings_store.get("dictation"))


def by_email() -> bool:
    from core import mail

    return mail.configured() and bool(settings_store.get("dictation_by_email"))


# Whose, and who may read --------------------------------------------------------


def mine(user):
    """This person's Dictations, newest first, in a Case or not."""
    return (
        Recording.objects.filter(user=user, is_dictation=True)
        .select_related("case")
        .order_by("-created")
    )


def sent_to(user):
    """The Dictations colleagues have sent this person, newest first."""
    return (
        DictationShare.objects.filter(person=user)
        .select_related("recording", "recording__user", "sent_by")
        .order_by("-sent_on")
    )


def is_recipient(recording, user) -> bool:
    if not getattr(recording, "is_dictation", False) or user is None:
        return False
    return DictationShare.objects.filter(
        recording=recording, person_id=user.pk
    ).exists()


# Use, and the clock --------------------------------------------------------------


def note_used(recording: Recording, by=None) -> None:
    """A Dictation was used: the clock starts over; a recipient's opening is noted."""
    if not recording.is_dictation:
        return
    Recording.objects.filter(pk=recording.pk).update(last_used=timezone.now())
    if by is not None and by.pk != recording.user_id:
        DictationShare.objects.filter(recording=recording, person_id=by.pk).update(
            last_opened=timezone.now()
        )


def days_left(recording: Recording) -> int:
    """Days until the sweep takes a Dictation in no Case; the Case's clock otherwise."""
    from core import retention

    if recording.case_id:
        return retention.days_left(recording.case)
    since = recording.last_used or recording.created
    unused = (timezone.localdate() - timezone.localtime(since).date()).days
    return retention.retention_days() - unused


# The Memo ---------------------------------------------------------------------------


def memo_template():
    from core.assistant import SummaryTemplate

    SummaryTemplate.shipped()
    return SummaryTemplate.objects.filter(key="dictation").first()


def memo_of(recording: Recording):
    """The Dictation's Memo: its newest Summary, if any."""
    return recording.summaries.order_by("-created").first()


def product_of(recording: Recording) -> str:
    """ "memo" for a dictation, "summary" for a meeting or a call."""
    from core import live

    style = (recording.live or {}).get("style") or "dictation"
    return live.STYLES.get(style, live.STYLES["dictation"])["product"]


def write_memo(recording: Recording, by, request=None):
    """Ask for the product: a Memo for a dictation, a summary for the others.

    One Summary, with the template the viewer would choose for the
    recording's type (the Dictation memo for a dictation, the Interview or
    Meeting summary for the others), at the Detailed length for a memo so
    nothing is cut short.
    """
    from core import assistant, tasks
    from core.assistant import Summary, SummaryTemplate

    word = product_of(recording)
    if not assistant.features()["summary"]:
        raise Refused(f"The AI assistant is off, so no {word} can be written. Ask IT.")
    if getattr(recording, "transcript", None) is None:
        raise Refused("The transcript is not there yet.")
    template = SummaryTemplate.chosen_for(recording)
    if word == "memo":
        template = memo_template() or template
    summary = Summary.objects.create(
        recording=recording,
        asked_by=by,
        template=template,
        template_name=template.name,
        template_version=template.version,
        focus="",
        length="detailed" if word == "memo" else "standard",
    )
    tasks.write_summary.defer(summary_id=str(summary.pk))
    note_used(recording, by=by)
    return summary


class Refused(Exception):
    """Why a Dictation cannot be sent or written up, in the person's words."""


# Send to ----------------------------------------------------------------------------


def candidates(recording: Recording):
    """The colleagues a Dictation may be sent to: the Share list's rule."""
    from core.models import User

    return (
        User.objects.filter(
            last_sign_in__isnull=False,
            deactivated_at__isnull=True,
            blocked_at__isnull=True,
            is_local=False,
        )
        .exclude(pk=recording.user_id)
        .exclude(dictations_received__recording=recording)
        .order_by("display_name", "username")
    )


def find(recording: Recording, typed: str):
    """One candidate for what was typed, the Share dialog's way."""
    from django.db.models import Q

    typed = (typed or "").strip()
    if not typed:
        raise Refused("Type a colleague's name.")
    people = candidates(recording)
    found = people.filter(username__iexact=typed).first()
    if found is None:
        named = list(people.filter(display_name__iexact=typed)[:2])
        if len(named) == 1:
            found = named[0]
        elif len(named) > 1:
            raise Refused(
                f'More than one person is called "{typed}". Use their username.'
            )
    if found is None:
        near = list(
            people.filter(
                Q(display_name__icontains=typed) | Q(username__icontains=typed)
            )[:2]
        )
        if len(near) == 1:
            found = near[0]
        elif len(near) > 1:
            raise Refused(
                f'More than one person matches "{typed}". Type more of the name.'
            )
    if found is None:
        raise Refused(
            f'Nobody called "{typed}" can be sent this. A colleague appears here once '
            "they have signed in to the app."
        )
    return found


@transaction.atomic
def send(recording: Recording, person, actor, request=None) -> DictationShare:
    """Send one Dictation to one colleague: the share, the row, the mail."""
    from core import mail

    share, made = DictationShare.objects.get_or_create(
        recording=recording, person=person, defaults={"sent_by": actor}
    )
    if not made:
        return share
    # With the switch on, the mail carries what there is: the memo or summary
    # when one is written, and the recording itself when it fits the limit.
    attach = by_email()
    share.attached = attach
    share.save(update_fields=["attached"])
    audit.write(
        CATEGORY,
        "Dictation sent",
        actor=actor,
        request=request,
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
        recipient=person.username,
        attached=attach,
    )
    note_used(recording, by=actor)
    mail.dictation_sent(recording, actor, person, attach_memo=attach)
    return share


def take_back(share: DictationShare, actor, request=None) -> None:
    recording = share.recording
    person = share.person
    share.delete()
    audit.write(
        CATEGORY,
        "Dictation taken back",
        actor=actor,
        request=request,
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
        recipient=person.username,
    )
    note_used(recording, by=actor)


# The sweep --------------------------------------------------------------------------


def sweep() -> dict:
    """The nightly pass over Dictations in no Case: delete what has run out.

    Independent of Folder management, since Dictations do not depend on
    Cases. Each is its own clock; the Recording's own row says it went.
    """
    from core import lifecycle

    deleted = 0
    for recording in Recording.objects.filter(is_dictation=True, case__isnull=True):
        if days_left(recording) <= 0:
            lifecycle.remove_recording(recording, cause="retention", actor=None)
            deleted += 1
    if deleted:
        log.info("the dictation sweep deleted %d dictation(s)", deleted)
    return {"deleted": deleted}


def for_tonights_digest() -> dict:
    """Per person, the Dictations inside the warning window: the digest's block."""
    from core import retention

    lines: dict = {}
    for recording in Recording.objects.filter(
        is_dictation=True, case__isnull=True
    ).select_related("user"):
        left = days_left(recording)
        if retention.is_warned(left) and left > 0:
            lines.setdefault(recording.user_id, []).append(
                {"title": recording.title, "days_left": left}
            )
    return lines
