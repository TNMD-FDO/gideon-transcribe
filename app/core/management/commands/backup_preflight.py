"""Step 1 of the nightly job: may a Snapshot be taken tonight?

    docker compose run --rm app backup_preflight

Exits 0 when the App data folder has room above the floor, BACKUP_TARGET is
set, and the two backup secrets are present; otherwise prints the reason on
one line and exits 1, and `./transcribe backup` records it as the failure.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from core import backups


class Command(BaseCommand):
    help = "The nightly backup's preflight: room, a target, the two secrets."

    def handle(self, *args, **options) -> None:
        ok, why = backups.preflight()
        self.stdout.write(why)
        if not ok:
            raise SystemExit(1)
