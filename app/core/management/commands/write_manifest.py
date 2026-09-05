"""Step 3 of the nightly job: backup/manifest.json.

    docker compose run --rm app write_manifest

The release tag, the migration, the WhisperX service's version, the time, the
dump's name and size, a row count per table, and a sha256 per file under
cases/, so the drill checks a restored copy with the same code that wrote it.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from core import backups


class Command(BaseCommand):
    help = "Write backup/manifest.json for tonight's Snapshot."

    def handle(self, *args, **options) -> None:
        manifest = backups.write_manifest()
        self.stdout.write(
            f"manifest written: {len(manifest['tables'])} tables, "
            f"{len(manifest['files'])} files, dump {manifest['dump'] or 'none'}"
        )
