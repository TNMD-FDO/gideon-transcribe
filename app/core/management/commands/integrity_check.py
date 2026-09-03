"""Walk the audit log's chain and report, for IT at a terminal.

    docker compose run --rm app integrity-check

The Admin panel's status page has a button that does the same thing and shows
the last result. Both write their own row, which is itself chained, so the
question "when was this last checked" is answered by the log.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from core import audit


class Command(BaseCommand):
    help = "Check that the audit log's chain is unbroken."

    def handle(self, *args, **options) -> None:
        result = audit.check_integrity()

        audit.write(
            audit.Category.SYSTEM,
            "Integrity check ran",
            system="integrity check",
            outcome=(
                audit.Outcome.SUCCESS if result["unbroken"] else audit.Outcome.FAILURE
            ),
            reason_class="" if result["unbroken"] else "chain_broken",
            rows_checked=result["rows"],
            first_break_id=result.get("first_break_id"),
        )

        self.stdout.write(result["message"])
        self.stdout.write(f"{result['rows']} rows checked.")

        if not result["unbroken"]:
            self.stdout.write(
                "\nA break means a row was changed or removed after it was "
                "written. The rows before the break are still trustworthy; "
                "the ones after it cannot be told apart from rows written by "
                "whoever made the break."
            )
            raise SystemExit(1)
