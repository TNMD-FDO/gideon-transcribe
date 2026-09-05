"""Step 5 of a restore: what the restored app does first.

    docker compose run --rm app after_restore <snapshot id> <snapshot time, ISO 8601>

Ends every Login session and discards every Workspace, fails the Case-bound
Jobs that were in flight at the Snapshot as `restored`, records the outage as
an Off spell, runs the Integrity check, writes "Restore completed", and prints
the report.
"""

from __future__ import annotations

from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core import backups


class Command(BaseCommand):
    help = (
        "The after-restore step: sessions, Workspaces, Jobs, the Off spell, the report."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("snapshot")
        parser.add_argument("snapshot_at", help="the Snapshot's time, ISO 8601")

    def handle(self, *args, **options) -> None:
        try:
            when = datetime.fromisoformat(options["snapshot_at"])
        except ValueError:
            raise CommandError("the Snapshot time must be ISO 8601") from None
        if timezone.is_naive(when):
            when = timezone.make_aware(when)
        report = backups.after_restore(options["snapshot"], when)
        for key, value in report.items():
            self.stdout.write(f"{key}: {value}")
