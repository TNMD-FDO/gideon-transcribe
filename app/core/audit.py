"""The audit log: what happened, who did it, and to whose material.

Every row is metadata. Nothing on the never-logged list ever reaches it:
transcript text, the two sides of a correction, chat questions and answers,
summaries, vocabulary, search terms, file contents, passwords, tokens, speaker
names, clip titles, and clip notes. A recording's original file name is kept,
because it is the only way to recognise a recording after it is discarded.

Rows are written through a role that can insert and do nothing else, and are
removed only by the retention sweep's own role. Each row is hashed onto the one
before it, so a row that is changed or removed can be found. See ADR 0008.
"""

from __future__ import annotations

import hashlib
import json
import logging
from contextlib import contextmanager
from typing import Any

from django.db import connection, models, transaction
from django.utils import timezone

log = logging.getLogger("transcribe.audit")

# The roles the migration creates. The app's own role is a member of both and
# holds neither's privileges until it asks by name.
WRITER_ROLE = "transcribe_audit"
SWEEPER_ROLE = "transcribe_audit_sweep"

# Sixty-four zeros: what the first row of a chain points back at.
FIRST_LINK = "0" * 64

# Which fields go into the hash, and in what order. Adding a field means a new
# version, kept on the row, so that an old row is always checked the way it was
# written (ADR 0008).
CHAIN_VERSION = 1
CHAINED_FIELDS = (
    "at",
    "actor_kind",
    "actor_user_id",
    "actor_username",
    "actor_directory_address",
    "category",
    "event",
    "outcome",
    "reason_class",
    "affected_user_id",
    "affected_username",
    "object_type",
    "object_id",
    "object_label",
    "login_session_id",
    "client_address",
    "client_browser",
    "details",
)


class Category:
    SIGN_IN = "sign-in"
    ACCOUNTS = "accounts"
    RECORDINGS = "recordings"
    JOBS = "jobs"
    EDITS = "edits"
    EXPORTS = "exports"
    CLIPS = "clips"
    CASES = "cases"
    LLM = "llm"
    ADMIN = "admin"
    SYSTEM = "system"


class Outcome:
    SUCCESS = "success"
    FAILURE = "failure"


# The identifiers for the reason classes the specification named in words. One
# per class, never free text.
class Reason:
    WRONG_PASSWORD = "wrong_password"
    NOT_IN_A_GROUP = "not_in_a_group"
    DEACTIVATED = "deactivated"
    BLOCKED = "blocked"
    DIRECTORY_UNREACHABLE = "directory_unreachable"
    THROTTLED = "throttled"


class Row(models.Model):
    """One thing that happened. Insert-only: nothing here is ever updated."""

    at = models.DateTimeField(default=timezone.now, db_index=True)

    # Who acted. A person, or the app itself with the name of the job.
    actor_kind = models.CharField(max_length=10, default="user")
    actor_user_id = models.BigIntegerField(null=True, blank=True)
    actor_username = models.CharField(max_length=150, blank=True, default="")
    actor_directory_address = models.CharField(max_length=320, blank=True, default="")

    category = models.CharField(max_length=20, db_index=True)
    event = models.CharField(max_length=60, db_index=True)

    outcome = models.CharField(max_length=10, default=Outcome.SUCCESS)
    reason_class = models.CharField(max_length=40, blank=True, default="")

    # Whose material this was about, when that is not the person who acted.
    # Always filled on the Admin category's access rows: it is the field that
    # answers whose material was opened, and by whom.
    affected_user_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    affected_username = models.CharField(max_length=150, blank=True, default="")

    # What it was about, with a label that outlives the thing itself.
    object_type = models.CharField(max_length=30, blank=True, default="")
    object_id = models.CharField(max_length=64, blank=True, default="")
    object_label = models.CharField(max_length=400, blank=True, default="")

    login_session_id = models.BigIntegerField(null=True, blank=True)

    client_address = models.GenericIPAddressField(null=True, blank=True)
    client_browser = models.CharField(max_length=20, blank=True, default="")

    details = models.JSONField(default=dict, blank=True)

    chain_version = models.IntegerField(default=CHAIN_VERSION)
    previous_hash = models.CharField(max_length=64)
    row_hash = models.CharField(max_length=64)

    class Meta:
        ordering = ["-at", "-id"]
        indexes = [
            models.Index(fields=["category", "event"]),
            models.Index(fields=["actor_user_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.at:%Y-%m-%d %H:%M} {self.category}/{self.event}"

    def hashed_content(self) -> str:
        """The row as it is hashed: fixed fields, fixed order, one form."""
        content = {}
        for field in CHAINED_FIELDS:
            value = getattr(self, field)
            if field == "at":
                value = value.isoformat()
            elif field == "details":
                value = json.dumps(value, sort_keys=True, separators=(",", ":"))
            elif value is None:
                value = ""
            content[field] = str(value)
        return json.dumps(content, sort_keys=True, separators=(",", ":"))

    def compute_hash(self) -> str:
        joined = f"{self.previous_hash}{self.hashed_content()}"
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def browser_family(user_agent: str) -> str:
    """Edge, Chrome, or other. Nothing more of the browser is kept.

    The specification leaves how this is detected to the build, and asks for
    three answers only, so the test is the smallest one that gives them: Edge
    says Edg, Chrome says Chrome and not Edg, and everything else is other.
    """
    agent = (user_agent or "").lower()
    if "edg" in agent:
        return "Edge"
    if "chrome" in agent or "chromium" in agent:
        return "Chrome"
    return "other"


@contextmanager
def acting_as(role: str):
    """Do one thing as another database role, and switch back straight after.

    SET LOCAL lasts until the end of the transaction, not until the end of the
    block, and a savepoint does not undo it. Inside an outer transaction, which
    is what a test and any request-wide transaction give, the connection would
    otherwise stay switched to the insert-only role and every write after it
    would be refused. So the switch back is explicit and happens whatever the
    write does.
    """
    with connection.cursor() as cursor:
        cursor.execute(f"SET LOCAL ROLE {role}")
        try:
            yield
        finally:
            cursor.execute("SET LOCAL ROLE NONE")


def _previous() -> tuple[str, int]:
    """The hash of the newest row, and how many rows there are."""
    newest = Row.objects.order_by("-id").values("row_hash").first()
    return (newest["row_hash"] if newest else FIRST_LINK), Row.objects.count()


@transaction.atomic
def write(
    category: str,
    event: str,
    *,
    actor=None,
    system: str | None = None,
    outcome: str = Outcome.SUCCESS,
    reason_class: str = "",
    affected_user=None,
    object_type: str = "",
    object_id: str = "",
    object_label: str = "",
    request=None,
    login_session=None,
    **details: Any,
) -> Row:
    """Write one row, chained onto the last.

    Called for the thing that happened, never for the page that showed it:
    opening or filtering the audit viewer is not itself logged.
    """
    from core.signin import address_of

    row = Row(
        category=category,
        event=event,
        outcome=outcome,
        reason_class=reason_class,
        object_type=object_type,
        object_id=str(object_id or ""),
        object_label=object_label,
        details=details,
    )

    if system:
        row.actor_kind = "system"
        row.actor_username = system
    elif actor is not None:
        row.actor_kind = "user"
        row.actor_user_id = actor.pk
        row.actor_username = actor.username
        row.actor_directory_address = actor.directory_address
    else:
        # A failed sign-in for a name with no account behind it. The
        # specification leaves this open; the name that was typed is what a
        # person troubleshooting needs, and it is not a claim that the account
        # exists.
        row.actor_kind = "unknown"

    if affected_user is not None:
        row.affected_user_id = affected_user.pk
        row.affected_username = affected_user.username

    if login_session is not None:
        row.login_session_id = login_session.pk

    if request is not None:
        row.client_address = address_of(request)
        row.client_browser = browser_family(request.META.get("HTTP_USER_AGENT", ""))

    row.previous_hash, _ = _previous()
    row.row_hash = row.compute_hash()

    with acting_as(WRITER_ROLE):
        row.save()

    return row


def sign_in_failed(username: str, reason: str, request=None, actor=None) -> Row:
    """A refused sign-in, with the name that was typed either way."""
    row = write(
        Category.SIGN_IN,
        "sign-in failed",
        actor=actor,
        outcome=Outcome.FAILURE,
        reason_class=reason,
        request=request,
        typed_username=username,
    )
    return row


def check_integrity() -> dict[str, Any]:
    """Walk the chain and report, as the status page button and IT's command do.

    The retention sweep removes the oldest rows, which cuts the chain where it
    cuts, so the walk starts at the oldest row that is still here and says so.
    That is not a break; a row whose hash does not match its content, or whose
    link does not match the row before it, is.
    """
    rows = Row.objects.order_by("id").iterator(chunk_size=500)

    checked = 0
    expected: str | None = None
    for row in rows:
        if expected is not None and row.previous_hash != expected:
            return _result(False, checked, row, "the link to the row before it")
        if row.compute_hash() != row.row_hash:
            return _result(False, checked, row, "its own contents")
        expected = row.row_hash
        checked += 1

    return {
        "unbroken": True,
        "rows": checked,
        "message": (
            "Unbroken since the first row kept."
            if checked
            else "There is nothing in the log yet."
        ),
    }


def _result(unbroken: bool, checked: int, row: Row, what: str) -> dict[str, Any]:
    return {
        "unbroken": unbroken,
        "rows": checked,
        "first_break_id": row.pk,
        "first_break_at": row.at,
        "message": (
            f"The chain breaks at row {row.pk}, written at "
            f"{row.at:%Y-%m-%d %H:%M}, which does not match {what}."
        ),
    }


def months_ago(months: int, from_when=None):
    """The same day of the month, that many months back.

    A month is not a fixed number of days, and the retention setting is in
    whole months, so the arithmetic is on the calendar rather than on 30-day
    lumps. The 31st of a month lands on the last day of a shorter one.
    """
    import calendar

    when = from_when or timezone.now()
    month = when.month - months
    year = when.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    day = min(when.day, calendar.monthrange(year, month)[1])
    return when.replace(year=year, month=month, day=day)


def sweep(keep_months: int) -> int:
    """Remove rows older than the retention setting, under the sweeper's role.

    This is the one thing that removes an audit row, and it is why the sweeper
    has a role of its own: nothing else in the app can delete from this table.
    Cutting the oldest rows breaks the chain at the cut, which the integrity
    check knows about and reports as the oldest row kept rather than as damage.
    """
    cutoff = months_ago(keep_months)
    old = Row.objects.filter(at__lt=cutoff)
    count = old.count()

    if count:
        with transaction.atomic(), acting_as(SWEEPER_ROLE):
            old.delete()

    write(
        Category.SYSTEM,
        "audit retention sweep ran",
        system="retention sweep",
        rows_removed=count,
        kept_months=keep_months,
    )
    log.info("the audit retention sweep removed %d rows", count)
    return count
