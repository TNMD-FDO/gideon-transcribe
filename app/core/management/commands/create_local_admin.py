"""Make the first Local admin, so that somebody can sign in at all.

    docker compose run --rm app create-local-admin

It asks for the password on the terminal, so the password never sits in .env,
in a command line, or in a log. The password goes into the office's password
manager.
"""

from __future__ import annotations

import getpass
import sys

from django.core.management.base import BaseCommand, CommandError

from core import audit
from core.models import User, normalise_username

DEFAULT_NAME = "transcribe-admin"

# Long enough that guessing is not the way in, and said plainly rather than
# with a rule about characters, which drives people to write passwords down.
LEAST_PASSWORD = 12


class Command(BaseCommand):
    help = "Create a Local admin account, which can sign in without the directory."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--name",
            default=None,
            help=f"the account's name (the default is {DEFAULT_NAME})",
        )

    def handle(self, *args, **options) -> None:
        name = normalise_username(options.get("name") or "")
        if not name:
            typed = input(f"Name for the Local admin [{DEFAULT_NAME}]: ").strip()
            name = normalise_username(typed or DEFAULT_NAME)

        if User.objects.filter(username=name).exists():
            raise CommandError(
                f"There is already an account called {name}. Choose another name."
            )

        # A Local admin whose name matches a directory account would be a way
        # to sign in as that person without the directory ever being asked.
        # The directory is not connected yet, so there is nothing to check
        # against; when it is, this is where that check belongs.

        if not sys.stdin.isatty():
            raise CommandError(
                "This command asks for a password, so it needs a terminal. Run it "
                "with `docker compose run --rm app create-local-admin`."
            )

        password = getpass.getpass("Password: ")
        again = getpass.getpass("Password again: ")
        if password != again:
            raise CommandError("The two passwords are not the same. Nothing was made.")
        if len(password) < LEAST_PASSWORD:
            raise CommandError(
                f"That password is {len(password)} characters. Use at least "
                f"{LEAST_PASSWORD}."
            )

        user = User.objects.create_local_admin(name, password)
        audit.write(
            audit.Category.ACCOUNTS,
            "Local admin created",
            system="create-local-admin",
            affected_user=user,
            object_type="user",
            object_id=user.pk,
            object_label=user.username,
        )

        self.stdout.write(f"\nThe Local admin {name} can now sign in.")
        self.stdout.write("Put its password in the office's password manager.")
        self.stdout.write(
            "It is an Admin, and it does not depend on the directory, which is "
            "the point of it: it is how somebody signs in when the directory "
            "cannot be reached."
        )
