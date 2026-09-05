"""Step 5 of the Restore drill: the result, in the live app.

    record_drill ok --duration 300
    record_drill failed --step "table core_case: 3 rows, manifest says 4"

Run inside the live app container by ./transcribe restore-drill.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from core import backups


class Command(BaseCommand):
    help = "Record the end of a Restore drill, ok or failed."

    def add_arguments(self, parser) -> None:
        parser.add_argument("result", choices=["ok", "failed"])
        parser.add_argument("--step", default="")
        parser.add_argument("--duration", type=float, default=0.0)

    def handle(self, *args, **options) -> None:
        backups.record_drill(
            ok=options["result"] == "ok",
            step=options["step"],
            duration=options["duration"],
        )
        self.stdout.write("recorded: " + options["result"])
