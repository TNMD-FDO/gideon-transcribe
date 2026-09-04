"""Render the two guides from Markdown, when the image is built.

    python manage.py render_guides

Run by the Dockerfile after collectstatic. A guide that is missing or will not
render fails the build, which is the point: what the app serves is exactly
this Release's text, and a Release with a broken guide never reaches a server.
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core import guides


class Command(BaseCommand):
    help = "Render the user and admin guides from Markdown to HTML."

    def handle(self, *arguments, **options):
        folder = settings.GUIDES_DIR
        for name in guides.NAMES:
            source = guides.source_of(name)
            if not source.is_file():
                raise CommandError(
                    f"There is no {source.name} in {folder}. The guides are "
                    "docs/user-guide.md and docs/admin-guide.md in the "
                    "repository, copied into the image by the Dockerfile."
                )
            out = guides.write_rendered(name)
            self.stdout.write(f"rendered {source.name} -> {out.name}")
