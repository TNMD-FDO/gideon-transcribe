"""Move one admin setting from the server's command line.

    docker compose exec -T app python manage.py set_setting engine_address http://vllm:8000/v1

The same rule as the panel: the value is checked against the setting's
definition, and a row is written to the audit log with the old and new value,
as the system, naming the command. `./transcribe engine local on` uses it to
point the AI assistant at the Local engine it has just started; it is not
meant as a way round the panel's tray for anything else.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from core import audit, settings_store


class Command(BaseCommand):
    help = "Set one admin setting, checked as the panel checks it, with an audit row."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "key", help="the setting's key, as core/settings_store.py names it"
        )
        parser.add_argument("value", help="the new value")

    def handle(self, *args, **options) -> None:
        key, value = options["key"], options["value"]
        try:
            known = settings_store.definition(key)
        except KeyError:
            raise CommandError(f"there is no setting called {key!r}") from None
        was = settings_store.shown(key)
        try:
            settings_store.set_to(key, value)
        except ValueError as refused:
            raise CommandError(str(refused)) from None
        audit.write(
            audit.Category.ADMIN,
            "Setting changed",
            system="transcribe engine",
            object_type="setting",
            object_id=key,
            object_label=known.name,
            was=was,
            now=settings_store.shown(key),
            note="set from the server's command line",
        )
        self.stdout.write(f"{known.name}: {was} -> {settings_store.shown(key)}")
