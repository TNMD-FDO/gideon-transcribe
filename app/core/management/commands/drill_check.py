"""Step 4 of the Restore drill, inside the throwaway project.

    docker compose -p transcribe-drill run --rm app drill_check <manifest> <cases>

Checks the restored copy against the manifest: a row count per table, a
sha256 per file under cases/, every Recording in a Case has its folder, and
the audit log's chain is unbroken. Prints each failure on a line and exits 1
when there is any.
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand

from core import backups


class Command(BaseCommand):
    help = "Check a restored copy against its manifest."

    def add_arguments(self, parser) -> None:
        parser.add_argument("manifest")
        parser.add_argument("cases")

    def handle(self, *args, **options) -> None:
        manifest = backups.read_manifest(Path(options["manifest"]))
        failures = backups.drill_check(manifest, Path(options["cases"]))
        for line in failures:
            self.stdout.write(line)
        if failures:
            raise SystemExit(1)
        self.stdout.write("the restored copy matches its manifest")
