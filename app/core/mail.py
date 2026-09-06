"""Mail: the app's one way out by email (Phase 2, Email notifications).

Plain text over the office's relay, and nothing else. Four kinds of
Notification to people (the Retention digest, a Case shared with them, a Case
handed to them, a Batch finished) and Operator mail to one IT mailbox. Mail
announces and never acts: nothing waits for a message, deletion least of all,
and a person without an Email address loses the message and nothing else.

A message says what an audit row may: names of Cases and Recordings, counts,
dates, display names, one link. Never content. The never-logged list is the
never-mailed list.

Every message is one background task on the worker, tried three times within
thirty minutes (at once, after 5 minutes, after 25), then dropped with an
"Email failed" row. The digest simply comes again the next night; the other
kinds are not resent, because the app's pages are the record.
"""

from __future__ import annotations

import logging
import os
import smtplib
import string
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from django.db import models
from django.utils import timezone

from core import audit, settings_store

log = logging.getLogger(__name__)

# The kinds, as the audit rows and the Status page name them.
DIGEST = "retention_digest"
SHARED = "case_shared"
HANDED = "case_handed"
BATCH = "batch_finished"
DICTATION = "dictation_sent"
OPERATOR = "operator"
TEST = "test"

# The reason classes when the relay will not take a message.
SMTP_UNREACHABLE = "smtp_unreachable"
SMTP_REFUSED = "smtp_refused"
SMTP_AUTH_FAILED = "smtp_auth_failed"

TIMEOUT_SECONDS = 20
TRIES = 3
# Minutes before the second and the third try: at once, then 5, then 25.
WAITS = (5, 20)

# The four Notifications' templates: their setting keys, their placeholders,
# and the defaults the chapter fixes. The blocks ({cases}, {shared},
# {failed_list}) and the footer are the app's own lines.
TEMPLATES = {
    DIGEST: {
        "subject_key": "digest_subject",
        "body_key": "digest_body",
        "placeholders": {"name", "cases", "shared", "dictations", "link"},
        "subject": "Gideon Transcribe: cases deleting soon",
        "body": (
            "Hello {name},\n"
            "\n"
            "These cases delete unless someone uses them:\n"
            "{cases}\n"
            "\n"
            "{shared}\n"
            "\n"
            "{dictations}\n"
            "\n"
            "Open a case, or press Keep on the Cases page, to start its clock "
            "over: {link}\n"
        ),
    },
    DICTATION: {
        "subject_key": "dictation_subject",
        "body_key": "dictation_body",
        "placeholders": {"name", "by", "title", "link"},
        "subject": "Gideon Transcribe: {by} sent you a recording",
        "body": (
            "Hello {name},\n"
            "\n"
            '{by} sent you the recording "{title}". It is under Sent to you on '
            "your Record tab.\n"
            "\n"
            "Open it: {link}\n"
        ),
    },
    SHARED: {
        "subject_key": "shared_subject",
        "body_key": "shared_body",
        "placeholders": {"name", "owner", "case", "link"},
        "subject": 'Gideon Transcribe: {owner} shared the case "{case}" with you',
        "body": (
            "Hello {name},\n"
            "\n"
            '{owner} shared the case "{case}" with you. You can do everything in '
            "it except share, rename, transfer, or delete it; recordings you add "
            "count against {owner}'s space.\n"
            "\n"
            "Open it: {link}\n"
        ),
    },
    HANDED: {
        "subject_key": "handed_subject",
        "body_key": "handed_body",
        "placeholders": {"name", "by", "case", "days", "link"},
        "subject": 'Gideon Transcribe: the case "{case}" is now yours',
        "body": (
            "Hello {name},\n"
            "\n"
            '{by} handed you the case "{case}". It deletes in {days} days unless '
            "used, so open it to start its clock over.\n"
            "\n"
            "Open it: {link}\n"
        ),
    },
    BATCH: {
        "subject_key": "batch_subject",
        "body_key": "batch_body",
        "placeholders": {
            "name",
            "count",
            "done",
            "failed",
            "failed_list",
            "where",
            "time",
            "link",
        },
        "subject": (
            "Gideon Transcribe: your batch has finished ({done} done, {failed} failed)"
        ),
        "body": (
            "Hello {name},\n"
            "\n"
            "Your batch of {count} recordings finished at {time}: {done} "
            "transcribed, {failed} failed.\n"
            "\n"
            "{failed_list}\n"
            "\n"
            "The recordings are {where}.\n"
            "\n"
            "Open them: {link}\n"
        ),
    },
}


class MailStatus(models.Model):
    """One row: what the Status page's Email line says."""

    last_sent_at = models.DateTimeField(null=True, blank=True)
    last_sent_kind = models.CharField(max_length=40, blank=True, default="")
    last_failed_at = models.DateTimeField(null=True, blank=True)
    last_failed_reason = models.CharField(max_length=40, blank=True, default="")
    # Whether the most recent try, sent or failed, failed: the line is red then.
    last_try_failed = models.BooleanField(default=False)

    @classmethod
    def the_one(cls) -> MailStatus:
        row, _ = cls.objects.get_or_create(pk=1)
        return row


class MailFailure(Exception):
    """The relay would not take the message, with the reason class."""

    def __init__(self, reason_class: str, detail: str = ""):
        super().__init__(detail or reason_class)
        self.reason_class = reason_class
        self.detail = detail


# The environment ------------------------------------------------------------------


def _env(key: str, default: str = "") -> str:
    return (os.environ.get(key) or default).strip()


def host() -> str:
    return _env("SMTP_HOST")


def port() -> int:
    try:
        return int(_env("SMTP_PORT", "25"))
    except ValueError:
        return 25


def starttls_mode() -> str:
    """auto, always, or never; anything else reads as auto."""
    mode = _env("SMTP_STARTTLS", "auto").lower()
    return mode if mode in ("auto", "always", "never") else "auto"


def user() -> str:
    return _env("SMTP_USER")


def password() -> str:
    path = _env("SMTP_PASSWORD_FILE")
    if not path:
        return ""
    try:
        with open(path, encoding="utf-8") as file:
            return file.read().strip()
    except OSError:
        return ""


def mail_from() -> str:
    return _env("MAIL_FROM")


def operator_email() -> str:
    return _env("OPERATOR_EMAIL")


def configured() -> bool:
    """Whether the app can send mail at all: a relay and a sender are named."""
    return bool(host()) and bool(mail_from())


def notifications_on() -> bool:
    """Whether mail to people goes: configured, and the Admin switch On."""
    return configured() and bool(settings_store.get("email_notifications"))


def batch_mail_on() -> bool:
    """Whether the Upload page offers its tick at all."""
    return notifications_on() and bool(settings_store.get("batch_finished_emails"))


def app_url(path: str = "/") -> str:
    """The app's address, as the links and the footer print it."""
    hostname = _env("APP_HOSTNAME", "localhost")
    https_port = _env("HTTPS_PORT", "8443")
    port_part = "" if https_port == "443" else f":{https_port}"
    return f"https://{hostname}{port_part}{path}"


def footer() -> str:
    replies = operator_email()
    line = f"Sent automatically by Gideon Transcribe ({app_url()})."
    if replies:
        line += f" Replies go to {replies}."
    return line


# The templates -------------------------------------------------------------------


def placeholders_in(text: str) -> set[str]:
    """The {names} a template uses; anything else in braces is left alone."""
    found = set()
    for _, name, _, _ in string.Formatter().parse(text):
        if name:
            found.add(name.split(".")[0].split("[")[0])
    return found


def check_template(kind: str, text: str) -> str:
    """Why a template cannot be applied, or "" when it can.

    Apply refuses a placeholder the kind does not have, as the chapter says.
    It does not refuse an omitted one: an office may drop a line it does not
    want, and a message with fewer facts is still a true message.
    """
    allowed = TEMPLATES[kind]["placeholders"]
    strange = sorted(placeholders_in(text) - allowed)
    if strange:
        which = ", ".join("{" + one + "}" for one in strange)
        return f"This message has no placeholder {which}."
    return ""


def template_kind_of(key: str) -> str:
    """Which kind a template setting belongs to, or "" for any other setting."""
    for kind, told in TEMPLATES.items():
        if key in (told["subject_key"], told["body_key"]):
            return kind
    return ""


class _Filled(dict):
    """Leaves an unknown placeholder as it was rather than failing the message."""

    def __missing__(self, key):
        return "{" + key + "}"


def _fill(text: str, values: dict) -> str:
    return string.Formatter().vformat(text, (), _Filled(values))


def _collapse(text: str) -> str:
    """An empty block leaves no blank paragraph behind it."""
    lines = text.split("\n")
    out: list[str] = []
    for line in lines:
        if not line.strip() and out and not out[-1].strip():
            continue
        out.append(line)
    return "\n".join(out).strip("\n") + "\n"


def render(kind: str, **values) -> tuple[str, str]:
    """The subject and the body of one message, footer included.

    The templates are the settings; the blocks come in through `values` as
    the app built them. A template an Admin has emptied falls back to the
    default, so no message ever goes out blank.
    """
    told = TEMPLATES[kind]
    subject = (settings_store.get(told["subject_key"]) or told["subject"]).strip()
    body = settings_store.get(told["body_key"]) or told["body"]
    subject = " ".join(_fill(subject, values).split())
    body = _collapse(_fill(body, values)) + "\n" + footer() + "\n"
    return subject, body


def with_footer(body: str) -> str:
    """A fixed-wording message (Operator mail, the test) gets the footer too."""
    return _collapse(body) + "\n" + footer() + "\n"


# Sending -----------------------------------------------------------------------------


def build(to_address: str, subject: str, body: str, attachment=None) -> EmailMessage:
    """One plain-text message, marked automatic so nothing auto-replies to it.

    `attachment` is one (filename, bytes) pair or a list of them, for the one
    kind of message that carries files: a recording sent to a colleague, its
    memo or summary and the recording itself, when the office has turned
    that on.
    """
    message = EmailMessage()
    message["From"] = formataddr(("Gideon Transcribe", mail_from()))
    message["To"] = to_address
    message["Subject"] = subject
    message["Date"] = timezone.now()
    message["Message-ID"] = make_msgid(domain=mail_from().rsplit("@", 1)[-1] or None)
    if operator_email():
        message["Reply-To"] = operator_email()
    # RFC 3834 for everybody, and the header Exchange reads, so that
    # out-of-office replies and vacation responders stay quiet.
    message["Auto-Submitted"] = "auto-generated"
    message["X-Auto-Response-Suppress"] = "All"
    message["Precedence"] = "bulk"
    message.set_content(body)
    files = (
        attachment
        if isinstance(attachment, list)
        else ([attachment] if attachment else [])
    )
    for filename, data in files:
        maintype, subtype = _mime_of(filename)
        message.add_attachment(
            data, maintype=maintype, subtype=subtype, filename=filename
        )
    return message


def _mime_of(filename: str) -> tuple[str, str]:
    """The type a file is sent as, from its ending; a Word file or a recording."""
    ending = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return {
        "docx": (
            "application",
            "vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
        "m4a": ("audio", "mp4"),
        "mp4": ("video", "mp4"),
        "webm": ("audio", "webm"),
        "mp3": ("audio", "mpeg"),
        "wav": ("audio", "wav"),
    }.get(ending, ("application", "octet-stream"))


def deliver(to_address: str, subject: str, body: str, attachment=None) -> str:
    """Hand one message to the relay, now, and return the relay's reply.

    Raises MailFailure with the reason class when the relay will not take it.
    The three SMTP steps are taken one at a time so the reply to the last is
    the relay's own words, which the test message shows on the page.
    """
    if not configured():
        raise MailFailure(SMTP_UNREACHABLE, "mail is not configured")
    message = build(to_address, subject, body, attachment)
    try:
        with smtplib.SMTP(host(), port(), timeout=TIMEOUT_SECONDS) as relay:
            relay.ehlo()
            offers_tls = relay.has_extn("starttls")
            mode = starttls_mode()
            if mode == "always" or (mode == "auto" and offers_tls):
                if not offers_tls:
                    raise MailFailure(
                        SMTP_UNREACHABLE, "the relay offers no TLS and always was asked"
                    )
                relay.starttls()
                relay.ehlo()
            elif password() and mode == "auto":
                raise MailFailure(
                    SMTP_AUTH_FAILED, "the relay offered no TLS while a password is set"
                )
            if password():
                relay.login(user() or mail_from(), password())
            code, words = relay.mail(mail_from())
            if code not in (250, 251):
                raise MailFailure(
                    SMTP_REFUSED, f"sender refused: {code} {_text(words)}"
                )
            code, words = relay.rcpt(to_address)
            if code not in (250, 251):
                raise MailFailure(
                    SMTP_REFUSED, f"recipient refused: {code} {_text(words)}"
                )
            code, words = relay.data(message.as_bytes())
            if code != 250:
                raise MailFailure(
                    SMTP_REFUSED, f"message refused: {code} {_text(words)}"
                )
            return f"{code} {_text(words)}"
    except MailFailure:
        raise
    except smtplib.SMTPAuthenticationError as why:
        raise MailFailure(SMTP_AUTH_FAILED, _text(why.smtp_error)) from why
    except (
        smtplib.SMTPRecipientsRefused,
        smtplib.SMTPSenderRefused,
        smtplib.SMTPDataError,
        smtplib.SMTPResponseException,
    ) as why:
        raise MailFailure(SMTP_REFUSED, str(why)[:200]) from why
    except (smtplib.SMTPException, OSError) as why:
        raise MailFailure(SMTP_UNREACHABLE, str(why)[:200]) from why


def _text(words) -> str:
    if isinstance(words, bytes):
        return words.decode("utf-8", "replace").strip()
    return str(words).strip()


# The queue: one task per message, three tries --------------------------------------


def send_to_person(
    kind: str,
    person,
    subject: str,
    body: str,
    *,
    object_type: str = "",
    object_id: str = "",
    object_label: str = "",
    **details,
) -> bool:
    """Queue one Notification to a person, when it may go.

    Nothing is queued and nothing is written while mail to people is Off,
    while the person has no Email address, or while they are Deactivated or
    Blocked: the pages are the record, and they lose nothing else.
    """
    if not notifications_on():
        return False
    if not person.email or not person.is_active:
        return False
    _queue(
        kind,
        person.email,
        person.username,
        subject,
        body,
        object_type=object_type,
        object_id=str(object_id),
        object_label=object_label,
        details=details,
    )
    return True


def send_to_operator(kind: str, subject: str, body: str, **details) -> bool:
    """Queue one message to the Operator address, which obeys `.env` alone."""
    if not configured() or not operator_email():
        return False
    _queue(
        kind,
        operator_email(),
        "operator",
        subject,
        with_footer(body),
        object_type="",
        object_id="",
        object_label="",
        details=details,
    )
    return True


def _queue(kind, to_address, recipient, subject, body, **fields) -> None:
    from core.tasks import send_email

    send_email.defer(
        kind=kind,
        to_address=to_address,
        recipient=recipient,
        subject=subject,
        body=body,
        tries=1,
        **fields,
    )


def attempt(
    *,
    kind: str,
    to_address: str,
    recipient: str,
    subject: str,
    body: str,
    tries: int,
    object_type: str = "",
    object_id: str = "",
    object_label: str = "",
    details: dict | None = None,
) -> str | None:
    """One try. Returns the wait in minutes before the next, or None when done.

    Done is either sent, with its row, or failed for the last time, with its
    row and the Status page's red line. The recipient in the row is a
    username or "operator", never an address.
    """
    details = details or {}
    status = MailStatus.the_one()
    attachment = None
    if details.get("attach_memo"):
        # The attachments, built now: the memo or summary as it stands when
        # the mail goes, and the recording itself when it fits the office's
        # limit. A recording left out for size is said so in the body.
        files, left_out = _attachments_for(details.get("attach_memo"))
        attachment = files
        if left_out:
            body = body.replace(
                "\nSent automatically by",
                f"\n{left_out}\n\nSent automatically by",
                1,
            )
        details = {key: value for key, value in details.items() if key != "attach_memo"}
        details["attached"] = bool(files)
        details["files"] = [name for name, _ in files]
    try:
        reply = deliver(to_address, subject, body, attachment)
    except MailFailure as why:
        if tries < TRIES:
            log.info(
                "mail (%s) to %s failed on try %d (%s); trying again",
                kind,
                recipient,
                tries,
                why.reason_class,
            )
            return WAITS[tries - 1]
        audit.write(
            audit.Category.EMAIL,
            "Email failed",
            system="mailer",
            outcome=audit.Outcome.FAILURE,
            reason_class=why.reason_class,
            object_type=object_type,
            object_id=object_id,
            object_label=object_label,
            kind=kind,
            recipient=recipient,
            tries=tries,
            **details,
        )
        status.last_failed_at = timezone.now()
        status.last_failed_reason = why.reason_class
        status.last_try_failed = True
        status.save()
        log.warning("mail (%s) to %s dropped after %d tries", kind, recipient, tries)
        return None
    audit.write(
        audit.Category.EMAIL,
        "Email sent",
        system="mailer",
        object_type=object_type,
        object_id=object_id,
        object_label=object_label,
        kind=kind,
        recipient=recipient,
        **details,
    )
    status.last_sent_at = timezone.now()
    status.last_sent_kind = kind
    status.last_try_failed = False
    status.save()
    log.info("mail (%s) to %s accepted: %s", kind, recipient, reply)
    return None


def _attachments_for(recording_id) -> tuple[list, str]:
    """The files a sent recording's mail carries, and the line for one left out.

    The memo or summary as a Word file when there is one; the recording's
    playback copy (its original when there is none yet) when it is no larger
    than the office's limit, else a line saying so.
    """
    from core.recordings import Recording

    files: list = []
    recording = Recording.objects.filter(pk=recording_id).first()
    if recording is None:
        return files, ""
    memo = _memo_file(recording_id)
    if memo is not None:
        files.append(memo)
    path = recording.playback_path() or (
        recording.original_path if recording.original_path.exists() else None
    )
    if path is None or not path.exists():
        return files, ""
    limit = int(settings_store.get("attachment_most_mb") or 20) * 1024 * 1024
    size = path.stat().st_size
    if size > limit:
        return files, (
            f"The recording itself ({size / 1024 / 1024:.0f} MB) is too large to "
            f"attach (the office's limit is {limit // 1024 // 1024} MB); the link "
            "above opens it."
        )
    stem = "".join(ch for ch in recording.title if ch.isalnum() or ch in " -_")[:80]
    files.append((f"{stem.strip() or 'Recording'}{path.suffix}", path.read_bytes()))
    return files, ""


def _memo_file(recording_id) -> tuple | None:
    """A dictation's Memo as a Word file, or None when there is no Memo yet."""
    from core import dictation, exports
    from core.recordings import Recording

    recording = Recording.objects.filter(pk=recording_id).first()
    if recording is None:
        return None
    memo = dictation.memo_of(recording)
    if memo is None or not memo.text:
        return None
    name = "".join(ch for ch in recording.title if ch.isalnum() or ch in " -_")[:80]
    return (
        f"{name.strip() or 'Dictation'} - memo.docx",
        exports.summary_word(memo, "mail"),
    )


# The test message -----------------------------------------------------------------


TEST_SUBJECT = "Gideon Transcribe: test message"
TEST_BODY = (
    "This is a test message from Gideon Transcribe. If it reached you, the "
    "relay takes mail from the app's server and lets its sender address "
    "through. Nothing else was checked, and nothing needs doing."
)


def send_test(to_address: str, actor=None, request=None) -> str:
    """The test message, sent within the request so its reply can be shown.

    One try, no queue: an Admin pressing the button wants the relay's own
    words now, not a row half an hour later. The row records the address and
    the reply, or the reason class when the relay would not take it.
    """
    try:
        reply = deliver(to_address, TEST_SUBJECT, with_footer(TEST_BODY))
    except MailFailure as why:
        audit.write(
            audit.Category.EMAIL,
            "Test email sent",
            actor=actor,
            system=None if actor is not None else "check",
            outcome=audit.Outcome.FAILURE,
            reason_class=why.reason_class,
            request=request,
            recipient_address=to_address,
            reply=why.detail[:200],
        )
        raise
    audit.write(
        audit.Category.EMAIL,
        "Test email sent",
        actor=actor,
        system=None if actor is not None else "check",
        request=request,
        recipient_address=to_address,
        reply=reply[:200],
    )
    status = MailStatus.the_one()
    status.last_sent_at = timezone.now()
    status.last_sent_kind = TEST
    status.last_try_failed = False
    status.save()
    return reply


# The Status page ------------------------------------------------------------------


def people_without_email() -> int:
    from core.models import User

    return User.objects.filter(
        deactivated_at__isnull=True, blocked_at__isnull=True, email=""
    ).count()


KIND_WORDS = {
    DIGEST: "retention digest",
    DICTATION: "recording sent",
    SHARED: "case shared",
    HANDED: "case handed over",
    BATCH: "batch finished",
    OPERATOR: "operator",
    TEST: "test message",
}

REASON_WORDS = {
    SMTP_UNREACHABLE: "the relay could not be reached",
    SMTP_REFUSED: "the relay refused the message",
    SMTP_AUTH_FAILED: "the relay refused the password",
}


def status_for_the_panel() -> dict:
    """The Email line: not configured, or last sent and last failure."""
    if not configured():
        return {
            "colour": "plain",
            "says": "not configured",
            "without_email": people_without_email(),
        }
    row = MailStatus.the_one()
    parts = []
    if row.last_sent_at:
        when = timezone.localtime(row.last_sent_at).strftime("%a %H:%M")
        kind = KIND_WORDS.get(row.last_sent_kind, row.last_sent_kind)
        parts.append(f"last sent {when} ({kind})")
    else:
        parts.append("nothing sent yet")
    if row.last_failed_at:
        when = timezone.localtime(row.last_failed_at).strftime("%a %H:%M")
        why = REASON_WORDS.get(row.last_failed_reason, row.last_failed_reason)
        parts.append(f"last failure {when} ({why})")
    return {
        "colour": "red" if row.last_try_failed else "plain",
        "says": "; ".join(parts),
        "without_email": people_without_email(),
    }


# The kinds: what each message says, and when it goes --------------------------------
#
# Each builder fills a template with the app's own blocks and queues the
# message when it may go. None of them is ever waited on.


def _when(moment) -> str:
    """A time in office time, as a message prints it."""
    return timezone.localtime(moment).strftime("%d %B %Y %H:%M")


def _digest_line(line: dict) -> str:
    """One Case's line in the digest: the number the Cases page shows."""
    left = line["days_left"]
    days = f"{left} day{'' if left == 1 else 's'}"
    return f"deletes in {days} unless used"


def send_digests(digests: dict, dictations: dict | None = None) -> int:
    """The night's Retention digests, one per person, and the Operator's message.

    `digests` is retention.digests_for_tonight()'s answer: per person, their
    lines, an owner's own and the ones shared with them (marked shared_by);
    `dictations` is dictation.for_tonights_digest()'s, per person. Deactivated
    and Blocked people are never mailed; their own Cases go to the Operator
    address instead, so an Admin can Reassign or Keep.
    """
    from core.models import User

    dictations = dictations or {}
    sent = 0
    for user_id in set(digests) | set(dictations):
        lines = digests.get(user_id, [])
        person = User.objects.filter(pk=user_id).first()
        if person is None or not person.is_active:
            continue
        own = [one for one in lines if not one.get("shared_by")]
        shared = [one for one in lines if one.get("shared_by")]
        theirs = dictations.get(user_id, [])
        dictation_block = ""
        if theirs:
            dictation_block = "Dictations deleting soon:\n" + "\n".join(
                f"- {one['title']}: {_digest_line(one)}" for one in theirs
            ).replace("unless used", "unless opened")
        cases_block = "\n".join(
            f"- {one['case']}: {_digest_line(one)} (last used "
            f"{timezone.localtime(one['last_used']):%Y-%m-%d}, "
            f"{one['recordings']} recording{'' if one['recordings'] == 1 else 's'})"
            for one in own
        )
        if not own:
            # The editable line above the block introduces it, so an empty
            # block says so rather than leaving the line hanging.
            cases_block = "- (none of your own)"
        shared_block = ""
        if shared:
            shared_block = "Shared with you:\n" + "\n".join(
                f"- {one['case']} (owner: {one['shared_by']}): {_digest_line(one)}"
                for one in shared
            )
        if not own and not shared and theirs:
            cases_block = "- (none)"
        subject, body = render(
            DIGEST,
            name=person.shown_name,
            cases=cases_block,
            shared=shared_block,
            dictations=dictation_block,
            link=app_url("/cases"),
        )
        if send_to_person(
            DIGEST,
            person,
            subject,
            body,
            object_type="digest",
            object_label="digest",
            own=len(own),
            shared=len(shared),
            dictations=len(theirs),
        ):
            sent += 1
    return sent


def dictation_sent(recording, by, to_whom, attach_memo: bool = False) -> bool:
    """ "Dictation sent", at once, to the colleague; the Memo attached when asked."""
    subject, body = render(
        DICTATION,
        name=to_whom.shown_name,
        by=by.shown_name,
        title=recording.title,
        link=app_url("/record"),
    )
    return send_to_person(
        DICTATION,
        to_whom,
        subject,
        body,
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
        **({"attach_memo": str(recording.pk)} if attach_memo else {}),
    )


def send_owner_left(lines: list) -> bool:
    """The Operator's nightly message: Cases whose owner has left, deleting soon.

    One line per Case whose owner is Deactivated or Blocked and that is inside
    the warning window: its name, its owner, its days left. Nothing on a
    night with no such Case.
    """
    if not lines:
        return False
    body = (
        "These cases belong to people who can no longer sign in, and they "
        "delete unless somebody uses them. Reassign or Keep them from the "
        'Cases page\'s "Owner deactivated" and "Expiring" filters.\n'
        "\n"
        + "\n".join(
            f"- {one['case']} (owner: {one['owner']}): {_digest_line(one)}"
            for one in lines
        )
        + f"\n\nThe Cases page: {app_url('/cases?who=everyone&owner_deactivated=1')}\n"
    )
    return send_to_operator(
        OPERATOR,
        "Gideon Transcribe: cases whose owner has left are deleting soon",
        body,
        cases=len(lines),
    )


def case_shared(case, person, owner) -> bool:
    """ "Case shared with you", at once, to the new Collaborator."""
    subject, body = render(
        SHARED,
        name=person.shown_name,
        owner=owner.shown_name,
        case=case.name,
        link=app_url(f"/case/{case.pk}"),
    )
    return send_to_person(
        SHARED,
        person,
        subject,
        body,
        object_type="case",
        object_id=case.pk,
        object_label=case.name,
    )


def case_handed(case, by, to_whom, days_left: int) -> bool:
    """ "Case handed to you", at once, to the new owner, on Transfer or Reassign."""
    subject, body = render(
        HANDED,
        name=to_whom.shown_name,
        by=by.shown_name,
        case=case.name,
        days=days_left,
        link=app_url(f"/case/{case.pk}"),
    )
    return send_to_person(
        HANDED,
        to_whom,
        subject,
        body,
        object_type="case",
        object_id=case.pk,
        object_label=case.name,
    )


def batch_finished(batch) -> bool:
    """ "Batch finished", once, when the last Recording in a Batch has ended.

    Only for a Batch whose person ticked the box, and only once: the Batch
    remembers that it was sent. A Batch with nothing left in it (cancelled
    whole) sends nothing.
    """
    from core.jobs import JobState
    from core.recordings import MediaState

    if not batch.email_when_done or batch.mail_sent_at is not None:
        return False
    if not batch.is_finished:
        return False
    recordings = list(batch.recordings.select_related("case").order_by("created"))
    if not recordings:
        return False
    failed_lines = []
    done = 0
    for recording in recordings:
        job = recording.jobs.order_by("-created").first()
        if recording.media_state == MediaState.FAILED:
            why = recording.failure_message or "could not be prepared"
            failed_lines.append(f"- {recording.title}: {why}")
        elif job is not None and job.state == JobState.FAILED:
            failed_lines.append(
                f"- {recording.title}: {job.failure_message or 'transcription failed'}"
            )
        elif job is not None and job.state == JobState.DONE:
            done += 1
    failed = len(failed_lines)
    into = next((one.case for one in recordings if one.case_id), None)
    if into is not None:
        where = f"in the case {into.name}"
        link = app_url(f"/case/{into.pk}")
    else:
        where = "in your recordings until your session ends"
        link = app_url("/recordings")
    subject, body = render(
        BATCH,
        name=batch.user.shown_name,
        count=len(recordings),
        done=done,
        failed=failed,
        failed_list="\n".join(failed_lines),
        where=where,
        time=_when(timezone.now()),
        link=link,
    )
    batch.mail_sent_at = timezone.now()
    batch.save(update_fields=["mail_sent_at"])
    return send_to_person(
        BATCH,
        batch.user,
        subject,
        body,
        object_type="batch",
        object_id=batch.pk,
        object_label=f"{len(recordings)} recordings",
        done=done,
        failed=failed,
    )


def note_batch_progress(recording) -> None:
    """Called wherever a Recording ends: the Batch may have finished with it."""
    try:
        batch = recording.batch
    except Exception:  # noqa: BLE001 - a Recording with no Batch has no mail
        return
    if batch is None or not batch.email_when_done or batch.mail_sent_at:
        return
    batch_finished(batch)


# The Backup chapter's four Operator messages --------------------------------------


def backup_failed(step: str, reason: str) -> bool:
    return send_to_operator(
        OPERATOR,
        "Gideon Transcribe: last night's backup failed",
        (
            f'The backup did not complete. It stopped at the step "{step}" '
            f"({reason}).\n"
            "\n"
            "Nothing was lost: the app is running as before, and the last "
            "good Snapshot is still in the store. Run ./transcribe backup on "
            "the server to try again and see what it says, and check the "
            "Status page's Backup line.\n"
        ),
        about="backup_failed",
        step=step,
        reason=reason,
    )


def backup_overdue(last_good) -> bool:
    when = _when(last_good) if last_good else "never"
    return send_to_operator(
        OPERATOR,
        "Gideon Transcribe: no successful backup in 26 hours",
        (
            f"The last successful Snapshot was at {when}. The nightly backup "
            "has not completed since.\n"
            "\n"
            "Run ./transcribe backup on the server to see what stops it. This "
            "message comes once a day until a Snapshot succeeds.\n"
        ),
        about="backup_overdue",
    )


def drill_failed(step: str) -> bool:
    return send_to_operator(
        OPERATOR,
        "Gideon Transcribe: the restore drill failed",
        (
            f'The monthly restore drill stopped at the step "{step}".\n'
            "\n"
            "The backups may still be sound; the drill is what proves it. Run "
            "./transcribe restore-drill on the server to see what it says.\n"
        ),
        about="drill_failed",
        step=step,
    )


def drill_overdue(last_drill) -> bool:
    return send_to_operator(
        OPERATOR,
        "Gideon Transcribe: the restore drill is overdue",
        (
            f"The last restore drill ran at {_when(last_drill)}, more than a "
            "month and three days ago.\n"
            "\n"
            "Run ./transcribe restore-drill on the server, and check that its "
            "timer is on: systemctl list-timers transcribe-backup-drill.timer\n"
        ),
        about="drill_overdue",
    )


def restore_completed(report: dict) -> bool:
    return send_to_operator(
        OPERATOR,
        "Gideon Transcribe: a restore completed",
        (
            f"The app was restored from Snapshot {report.get('snapshot', '')} "
            f"taken at {report.get('snapshot_at', '')}.\n"
            "\n"
            f"Cases: {report.get('cases', 0)}; recordings in cases: "
            f"{report.get('case_recordings', 0)}; {report.get('case_gigabytes', 0)} "
            "GB. Everybody was signed out, and every workspace was discarded. "
            f"Audit log chain unbroken: {report.get('integrity_unbroken')}.\n"
        ),
        about="restore_completed",
    )
