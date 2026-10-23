"""A quota raised for a while (Phase 2, "Room: the per-user quota";
v1.155.0; the drawing docs/spec/mockups/phase-5-hearing-window-and-
temporary-quota.html, figure 2).

A person's space is one number at any moment. The usual figure is the
default quota or the Admin's standing override on the users list. An Admin
may raise it for a set time, 45 days as shipped (Temporary quota length):
while the Raise runs the space is the Raise's figure. When its days run out
and more is stored than the usual figure allows, the space becomes what is
stored now, and no more: nothing new fits, nothing is deleted, and as cases
go under the Retention policy or the person deletes, the figure follows the
storage down until it reaches the usual quota, when the Raise closes by
itself. An Admin may end a Raise early (the same wind-down) or give it
another spell. Every place that reads a quota reads effective_bytes().

Each step writes an audit row under Accounts, naming the affected account
and the figures, never a recording.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta

from django.db import models
from django.utils import timezone

from core import audit, settings_store

log = logging.getLogger(__name__)

RAISED = "raised"
WINDING = "winding"
CLOSED = "closed"

# How a Raise closed: its date came with the storage under the usual figure,
# the storage came down to it later, or an Admin ended it.
BY_DATE = "date"
BY_STORAGE = "stored"
BY_ADMIN = "ended"

LEAST_DAYS = 1
MOST_DAYS = 365
LEAST_GB = 1
MOST_GB = 5000


class QuotaRaise(models.Model):
    """One person's space raised for a while: the figure, the days, who
    raised it and why, and how it came back down."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "core.User", on_delete=models.CASCADE, related_name="quota_raises"
    )
    gigabytes = models.IntegerField()
    days = models.IntegerField()
    note = models.CharField(max_length=200, blank=True, default="")
    raised_by = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    raised_at = models.DateTimeField(default=timezone.now)
    ends = models.DateTimeField()
    state = models.CharField(max_length=10, default=RAISED)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_how = models.CharField(max_length=10, blank=True, default="")

    class Meta:
        ordering = ["-raised_at"]

    @property
    def running(self) -> bool:
        return self.state == RAISED and self.ends > timezone.now()

    @property
    def days_left(self) -> int:
        left = self.ends - timezone.now()
        return max(0, (left.days + (1 if left.seconds else 0)))


def default_days() -> int:
    return int(settings_store.get("temporary_quota_days") or 45)


def usual_bytes(user) -> int:
    """The usual figure: the Admin's standing override, else the default."""
    if user.quota_gb:
        return user.quota_gb * settings_store.GB
    return settings_store.default_quota_bytes()


def current(user) -> QuotaRaise | None:
    """The Raise in force, running or coming back down; None when there is
    none."""
    return QuotaRaise.objects.filter(user=user).exclude(state=CLOSED).first()


def effective_bytes(user) -> int:
    """This person's space now, the one number every reader uses."""
    usual = usual_bytes(user)
    one = current(user)
    if one is None:
        return usual
    if one.running:
        return max(usual, one.gigabytes * settings_store.GB)
    # The days ran out (whether or not the sweep has passed yet) or an Admin
    # ended it: what is stored, and no more.
    from core import uploads

    return max(usual, uploads.used_bytes(user))


def _when(moment: datetime) -> str:
    local = timezone.localtime(moment)
    return f"{local.day} {local.strftime('%B %Y')}"


def _gb(figure: int) -> str:
    return f"{figure / settings_store.GB:.0f} GB"


def raise_for(user, gigabytes: int, days: int, note: str, *, by, request=None):
    """Raise this person's space for a while. A Raise already in force is
    replaced by the new one."""
    gigabytes = int(gigabytes)
    days = int(days)
    if not LEAST_GB <= gigabytes <= MOST_GB:
        raise ValueError(f"The raised space must be from {LEAST_GB} to {MOST_GB} GB.")
    if not LEAST_DAYS <= days <= MOST_DAYS:
        raise ValueError(f"The days must be from {LEAST_DAYS} to {MOST_DAYS}.")
    if gigabytes * settings_store.GB <= usual_bytes(user):
        raise ValueError(
            f"{gigabytes} GB is not above their usual {_gb(usual_bytes(user))}; "
            "set the standing quota instead."
        )
    now = timezone.now()
    was = current(user)
    if was is not None:
        was.state = CLOSED
        was.closed_at = now
        was.closed_how = BY_ADMIN
        was.save(update_fields=["state", "closed_at", "closed_how"])
    made = QuotaRaise.objects.create(
        user=user,
        gigabytes=gigabytes,
        days=days,
        note=(note or "").strip()[:200],
        raised_by=by,
        raised_at=now,
        ends=now + timedelta(days=days),
    )
    audit.write(
        audit.Category.ACCOUNTS,
        "temporary quota raised",
        actor=by,
        request=request,
        affected_user=user,
        gigabytes=gigabytes,
        days=days,
        until=made.ends.isoformat(timespec="seconds"),
        note=made.note,
        replaced=str(was.pk) if was is not None else "",
    )
    return made


def extend(one: QuotaRaise, days: int, *, by, request=None) -> QuotaRaise:
    """Another spell on a Raise, running or coming back down: its date moves
    on from today or from its old date, whichever is later, and it runs
    again."""
    days = int(days)
    if not LEAST_DAYS <= days <= MOST_DAYS:
        raise ValueError(f"The days must be from {LEAST_DAYS} to {MOST_DAYS}.")
    now = timezone.now()
    one.ends = max(now, one.ends) + timedelta(days=days)
    one.state = RAISED
    one.save(update_fields=["ends", "state"])
    audit.write(
        audit.Category.ACCOUNTS,
        "temporary quota extended",
        actor=by,
        request=request,
        affected_user=one.user,
        gigabytes=one.gigabytes,
        days=days,
        until=one.ends.isoformat(timespec="seconds"),
    )
    return one


def end_now(one: QuotaRaise, *, by, request=None) -> QuotaRaise:
    """An Admin ends a Raise early: closed at once when the storage is under
    the usual figure, else it comes back down as a run-out Raise does."""
    from core import uploads

    now = timezone.now()
    if uploads.used_bytes(one.user) <= usual_bytes(one.user):
        _close(one, BY_ADMIN, now)
    else:
        one.state = WINDING
        one.ends = min(one.ends, now)
        one.save(update_fields=["state", "ends"])
    audit.write(
        audit.Category.ACCOUNTS,
        "temporary quota ended early",
        actor=by,
        request=request,
        affected_user=one.user,
        gigabytes=one.gigabytes,
        closed=one.state == CLOSED,
    )
    return one


def _close(one: QuotaRaise, how: str, now: datetime) -> None:
    one.state = CLOSED
    one.closed_at = now
    one.closed_how = how
    one.save(update_fields=["state", "closed_at", "closed_how"])


def sweep(now: datetime | None = None) -> dict:
    """The hourly pass: a Raise whose days ran out closes when the storage is
    under the usual figure and otherwise comes back down; one coming back
    down closes when the storage reaches the usual figure."""
    from core import uploads

    now = now or timezone.now()
    ran_out = closed = 0
    for one in QuotaRaise.objects.exclude(state=CLOSED).select_related("user"):
        used = uploads.used_bytes(one.user)
        usual = usual_bytes(one.user)
        if one.state == RAISED and one.ends > now:
            continue
        if used <= usual:
            _close(one, BY_DATE if one.state == RAISED else BY_STORAGE, now)
            closed += 1
            audit.write(
                audit.Category.ACCOUNTS,
                "temporary quota closed",
                system="worker",
                affected_user=one.user,
                gigabytes=one.gigabytes,
                how=one.closed_how,
            )
        elif one.state == RAISED:
            one.state = WINDING
            one.save(update_fields=["state"])
            ran_out += 1
            audit.write(
                audit.Category.ACCOUNTS,
                "temporary quota ran out",
                system="worker",
                affected_user=one.user,
                gigabytes=one.gigabytes,
                stored_gb=round(used / settings_store.GB, 1),
                usual_gb=round(usual / settings_store.GB),
            )
    if ran_out or closed:
        log.info("quota raises: %d ran out, %d closed", ran_out, closed)
    return {"ran_out": ran_out, "closed": closed}


def notice(user) -> str | None:
    """The one quiet line a person reads on Home and the Upload page while a
    Raise runs or comes back down; nothing otherwise."""
    one = current(user)
    if one is None:
        return None
    usual = _gb(usual_bytes(user))
    if one.running:
        return (
            f"Your space is {one.gigabytes} GB until {_when(one.ends)}, "
            f"then {usual} again."
        )
    words = (
        f"Your space was raised to {one.gigabytes} GB until {_when(one.ends)}. "
        f"It is {usual} again once your recordings are under {usual}; until "
        "then nothing new fits."
    )
    from core import cases

    if cases.folder_management_on():
        words += (
            f" Cases unused for {int(settings_store.get('retention_days'))} days "
            "go on their own under the Retention policy."
        )
    return words


def row_for(user) -> dict | None:
    """What the users list shows of this person's Raise, in force or the
    last one closed; None when there has never been one."""
    from core import uploads

    one = current(user) or QuotaRaise.objects.filter(user=user).first()
    if one is None:
        return None
    usual = usual_bytes(user)
    used = uploads.used_bytes(user)
    top = max(one.gigabytes * settings_store.GB, used, usual)
    return {
        "raise": one,
        "state": one.state
        if not (one.state == RAISED and not one.running)
        else WINDING,
        "running": one.running,
        "ends": _when(one.ends),
        "raised_on": _when(one.raised_at),
        "closed_on": _when(one.closed_at) if one.closed_at else "",
        "days_left": one.days_left,
        "by": one.raised_by.username if one.raised_by_id else "",
        "usual_gb": round(usual / settings_store.GB),
        "used_gb": round(used / settings_store.GB, 1),
        "used_share": round(100 * used / top) if top else 0,
        "usual_share": round(100 * usual / top) if top else 0,
    }
