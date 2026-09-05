"""Step 7 of the nightly job: the Status line and the audit row.

    record_backup ok --duration 41 --dump-bytes N --snapshot-bytes N --held 30
    record_backup failed --step snapshot --reason snapshot_failed

Run inside the app container by ./transcribe backup.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from core import backups


class Command(BaseCommand):
    help = "Record the end of a nightly backup, ok or failed."

    def add_arguments(self, parser) -> None:
        parser.add_argument("result", choices=["ok", "failed"])
        parser.add_argument("--step", default="")
        parser.add_argument("--reason", default="")
        parser.add_argument("--duration", type=float, default=0.0)
        parser.add_argument("--dump-bytes", type=int, default=0)
        parser.add_argument("--snapshot-bytes", type=int, default=0)
        parser.add_argument("--held", type=int, default=0)

    def handle(self, *args, **options) -> None:
        status = backups.record_backup(
            ok=options["result"] == "ok",
            step=options["step"],
            reason=options["reason"],
            duration=options["duration"],
            dump_size=options["dump_bytes"],
            snapshot_size=options["snapshot_bytes"],
            held=options["held"],
        )
        self.stdout.write(
            "recorded: "
            + (
                "ok"
                if status.last_snapshot_ok
                else f"failed ({status.last_snapshot_reason})"
            )
        )
