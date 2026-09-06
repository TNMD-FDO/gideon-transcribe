"""The two mail lines of `./transcribe check`, run inside the app container.

    python manage.py mail_check test      one test message to the Operator address
    python manage.py mail_check count     the Sign-in group's members without mail

Each prints one line the script shows as a pass, a note, or a failure:
"OK: ...", "NOTE: ...", or "FAIL: ...". The script never sees a secret.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from core import mail


class Command(BaseCommand):
    help = "The mail relay test and the count of people without an Email address."

    def add_arguments(self, parser) -> None:
        parser.add_argument("what", choices=["test", "count"])

    def handle(self, *args, **options) -> None:
        if options["what"] == "test":
            self._test()
        else:
            self._count()

    def _test(self) -> None:
        if not mail.configured():
            self.stdout.write(
                "NOTE: SMTP_HOST or MAIL_FROM is empty, so the app sends no mail"
            )
            return
        to_address = mail.operator_email()
        if not to_address:
            self.stdout.write(
                "NOTE: OPERATOR_EMAIL is empty, so there is nobody to send the test to"
            )
            return
        try:
            reply = mail.send_test(to_address)
        except mail.MailFailure as why:
            self.stdout.write(
                f"FAIL: the relay {mail.host()} would not take a message "
                f"({why.reason_class}): {why.detail or 'no detail'}"
            )
            raise SystemExit(1) from why
        self.stdout.write(
            f"OK: the relay {mail.host()} accepted a test message to "
            f"{to_address}: {reply}"
        )

    def _count(self) -> None:
        """Members of the Sign-in group with no `mail` value, as a warning."""
        from core import directory

        where = directory.facts()
        if not where["enabled"]:
            self.stdout.write("NOTE: the directory is switched off; nobody to count")
            return
        try:
            held = directory.connect()
            members = directory.members_of(held, where["signin_group"])
        except directory.Unreachable as problem:
            self.stdout.write(f"NOTE: the directory could not be asked: {problem}")
            return
        missing = []
        for dn in members:
            found = directory._by_dn(held, dn)
            if found is not None and not found.get("mail"):
                missing.append(found.get("sAMAccountName") or dn)
        if missing:
            shown = ", ".join(sorted(missing)[:8])
            more = f" and {len(missing) - 8} more" if len(missing) > 8 else ""
            self.stdout.write(
                f"NOTE: {len(missing)} member(s) of the Sign-in group have no mail "
                f"value in the directory, so they get no email: {shown}{more}"
            )
        else:
            self.stdout.write(
                f"OK: every one of the Sign-in group's {len(members)} members has a "
                "mail value"
            )
