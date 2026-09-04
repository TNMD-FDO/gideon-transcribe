"""The Retention policy: one clock per Case, a warning, and the Recycle bin.

The policy counts days of neglect. A Case whose Last activity is at least
Retention-period days old goes, whole, to the Recycle bin the night the sweep
finds it so, waits there for the bin period, and is then wiped for good. In the
last days before deletion its row on the Cases page turns amber, with Keep
beside it. Nothing in a Case is timed on its own, and nothing anywhere can
exempt a Case: the way to keep one is to use it, or press Keep.

Days nobody could reach a Case are not neglect. Every span during which Folder
management was off is an Off spell, and every count here leaves those days
out. Last activity and deleted-on dates are never moved to do that, so the
dates a person reads stay true.

The sweep runs at half past three, works from database state so a restart
never skips or doubles anything, and does nothing at all while Folder
management is off: no marks, no deletions, no wipes, no row.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time

from django.utils import timezone

from core import audit, cases, settings_store
from core.cases import Case, OffSpell

log = logging.getLogger("transcribe.retention")

SYSTEM = "retention"


# The three settings -----------------------------------------------------------


def retention_days() -> int:
    return int(settings_store.get("retention_days"))


def warning_days() -> int:
    return int(settings_store.get("warning_days"))


def recycle_bin_days() -> int:
    return int(settings_store.get("recycle_bin_days"))


# Counting days ----------------------------------------------------------------


def _at_midnight(day: date) -> datetime:
    """A date as the moment the office's day began, for counting from."""
    return timezone.make_aware(datetime.combine(day, time.min))


def whole_days(start: datetime, end: datetime) -> int:
    """Whole days between two moments, by the office's calendar, never negative."""
    return max(0, (timezone.localdate(end) - timezone.localdate(start)).days)


def days_off_between(start: datetime, end: datetime) -> int:
    """The whole days of every Off spell that overlaps the span, added up.

    A spell still open runs to `end`. Both causes count the same way: the
    setting being off, and the outage a restore covers.
    """
    total = 0
    for spell in OffSpell.objects.filter(started__lt=end).exclude(ended__lt=start):
        began = max(spell.started, start)
        ended = min(spell.ended or end, end)
        if ended > began:
            total += whole_days(began, ended)
    return total


def days_unused(case: Case, now: datetime | None = None) -> int:
    """Whole days since the Case's Last activity, the Off spells left out."""
    now = now or timezone.now()
    since = case.last_activity
    return max(0, whole_days(since, now) - days_off_between(since, now))


def days_left(case: Case, now: datetime | None = None) -> int:
    """Days until the clock takes the Case. Zero or less means tonight."""
    return retention_days() - days_unused(case, now)


def is_warned(left: int) -> bool:
    """Inside the warning window: fewer than Warning-before-deletion days remain."""
    return left < warning_days()


def deletes_line(left: int) -> str:
    """The amber line the Cases page shows, and the digest repeats."""
    if left <= 0:
        return "Deletes tonight unless used"
    return f"Deletes in {left} day{'' if left == 1 else 's'} unless used"


def days_in_bin(case: Case, now: datetime | None = None) -> int:
    """Whole days since the sweep binned the Case, the Off spells left out."""
    now = now or timezone.now()
    since = _at_midnight(case.deleted_on)
    return max(0, whole_days(since, now) - days_off_between(since, now))


def bin_days_left(case: Case, now: datetime | None = None) -> int:
    """Days until the bin wipes the Case. Zero or less means tonight."""
    return recycle_bin_days() - days_in_bin(case, now)


# The nightly sweep ------------------------------------------------------------


def sweep(now: datetime | None = None) -> dict | None:
    """Mark, delete, wipe, and write the row. Nothing at all while Cases are off.

    In the chapter's order: the warning on every Case newly inside its window,
    then every Case that is due into the bin, then every binned Case past the
    bin period wiped, then one row with the counts. A Case that is due tonight
    goes to the bin without a warning row: the warning is for Cases with days
    left, and this one has none.
    """
    if not cases.folder_management_on():
        return None
    now = now or timezone.now()
    today = timezone.localdate(now)

    warned = deleted = wiped = 0
    freed = 0.0
    in_the_window: list[tuple[Case, int]] = []

    for case in Case.objects.filter(deleted_on__isnull=True).select_related("owner"):
        left = days_left(case, now)
        if left <= 0:
            cases.put_in_the_bin(case, on=today)
            deleted += 1
            continue
        if is_warned(left):
            in_the_window.append((case, left))
            if case.warned_on is None:
                case.warned_on = today
                case.save(update_fields=["warned_on"])
                audit.write(
                    cases.CATEGORY,
                    "retention warning",
                    system=SYSTEM,
                    affected_user=case.owner,
                    object_type="case",
                    object_id=case.pk,
                    object_label=case.name,
                    days_left=left,
                )
                warned += 1

    for case in Case.objects.filter(deleted_on__isnull=False).select_related("owner"):
        if bin_days_left(case, now) <= 0:
            _, gigabytes = cases.wipe(case, cause=cases.WIPED_BY_THE_BIN)
            wiped += 1
            freed += gigabytes

    counts = {
        "warned": warned,
        "deleted": deleted,
        "wiped": wiped,
        "gigabytes_freed": round(freed, 1),
    }
    audit.write(cases.CATEGORY, "retention sweep ran", system=SYSTEM, **counts)
    log.info("the retention sweep ran: %s", counts)

    # Once it has marked and deleted, the sweep hands the worker the night's
    # digests. The Email notifications chapter owns sending them and is not
    # built, so tonight they are counted and go no further.
    digests = digests_for_tonight(in_the_window)
    if digests:
        log.info("%d retention digest(s) would go out tonight", len(digests))
    return counts


def digests_for_tonight(in_the_window: list[tuple[Case, int]]) -> dict:
    """One digest per person who owns a warned Case: their lines for the mail.

    The shape the Email notifications chapter will send. Each line is the one
    the Cases page shows, with when the Case was last used and how many
    Recordings it holds. Cases whose owner is deactivated or blocked are the
    Operator address's, which that chapter names.
    """
    by_person: dict = {}
    for case, left in in_the_window:
        by_person.setdefault(case.owner_id, []).append(
            {
                "case": case.name,
                "line": deletes_line(left),
                "days_left": left,
                "last_used": case.last_activity,
                "recordings": case.recordings.count(),
                "owner_active": case.owner.is_active,
            }
        )
    return by_person
