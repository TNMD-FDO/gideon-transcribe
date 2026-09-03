"""Admin settings: the ones an Admin changes in the panel, not in a file.

`.env` holds what an office cannot change without a restart, such as the
hostname and the folders. These are the other kind: an Admin changes them while
the app runs and they take effect on the next thing that reads them.

Every setting the admin settings catalogue defines will end up here. It starts
with the ones the build has reached.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.db import models


@dataclass(frozen=True)
class Definition:
    """One setting: what it is, what it may be, and what it starts as."""

    key: str
    name: str
    default: int
    least: int
    most: int
    unit: str
    what_it_does: str


# The idle timeout's range is one of the things the specification leaves to the
# build: it fixes the default at 8 hours and that there is no absolute cap on a
# session, but not how far an Admin may move the timeout.
#
# The bottom is 15 minutes, because the warning comes 15 minutes before the
# timeout and a shorter setting would warn people about something that had
# already happened. The top is 24 hours, because a Workspace is discarded when
# its session ends and a timeout longer than a day would keep a person's
# recordings on disk across a night and a weekend without them being here.
DEFINITIONS = {
    definition.key: definition
    for definition in [
        Definition(
            key="idle_timeout_minutes",
            name="Idle timeout",
            default=8 * 60,
            least=15,
            most=24 * 60,
            unit="minutes",
            what_it_does=(
                "How long a Login session may sit idle before it ends. A "
                "warning comes 15 minutes before. A running Batch counts as "
                "activity."
            ),
        ),
        Definition(
            key="audit_retention_months",
            name="Audit log retention",
            default=3,
            least=1,
            most=120,
            unit="months",
            what_it_does=(
                "How long an audit row is kept. Three months is enough to "
                "troubleshoot with. An office that wants a longer record of "
                "who opened whose material raises it, and the admin guide "
                "says plainly that an Admin access is forgotten after this."
            ),
        ),
    ]
}


class Setting(models.Model):
    """One stored value. Anything not stored is at its default."""

    key = models.CharField(max_length=100, unique=True)
    value = models.IntegerField()
    changed = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self) -> str:
        return f"{self.key} = {self.value}"


def definition(key: str) -> Definition:
    try:
        return DEFINITIONS[key]
    except KeyError:
        raise KeyError(f"there is no setting called {key!r}") from None


def get(key: str) -> int:
    """What this setting is now, which is its default until somebody moves it."""
    known = definition(key)
    stored = Setting.objects.filter(key=key).first()
    return known.default if stored is None else stored.value


def set_to(key: str, value: int) -> None:
    """Move a setting, refusing anything outside its range.

    An out-of-range setting is refused here rather than in a form, so that
    every way of reaching it, panel or command line or test, is held to the
    same rule.
    """
    known = definition(key)
    if not known.least <= value <= known.most:
        raise ValueError(
            f"{known.name} may be from {known.least} to {known.most} "
            f"{known.unit}, and {value} is outside that"
        )
    Setting.objects.update_or_create(key=key, defaults={"value": value})


def idle_timeout() -> timedelta:
    return timedelta(minutes=get("idle_timeout_minutes"))


def audit_retention_months() -> int:
    return get("audit_retention_months")
