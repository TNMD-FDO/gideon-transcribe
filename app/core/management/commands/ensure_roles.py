"""Give the app a database role of its own, below the one that made the database.

The PostgreSQL image makes the account it bootstraps with a superuser, and a
superuser ignores every permission rule, so the audit log's insert-only role
would be decoration while the app connected as one. Chapter 1 names three
roles, the app's among them, which is this.

It runs before the migrations, as the bootstrap account, and it is safe to run
again: it makes the role if it is not there, hands it what the bootstrap
account owns, and stops.

The two accounts share the one database password. An office that would rather
they did not can give the app role its own; the argument for one is that a
second password only guards against somebody who can already read `secrets/`
on the server, and by then they have the database itself.
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand

APP_ROLE = "transcribe_app"


class Command(BaseCommand):
    help = "Make the app's own database role and give it what it needs."

    def handle(self, *args, **options) -> None:
        import psycopg

        database = settings.DATABASES["default"]
        bootstrap = settings.POSTGRES_SUPERUSER
        app_role = database["USER"]

        if app_role == bootstrap:
            self.stdout.write(
                f"The app connects as {app_role}, which is the account that "
                "made the database. Nothing to do."
            )
            return

        with psycopg.connect(
            host=database["HOST"],
            port=database["PORT"],
            dbname=database["NAME"],
            user=bootstrap,
            password=database["PASSWORD"],
            autocommit=True,
        ) as connection:
            made = self._ensure_role(connection, app_role, database["PASSWORD"])
            self._hand_over(connection, bootstrap, app_role, database["NAME"])

        self.stdout.write(
            f"The app connects as {app_role}"
            + (", which was made just now." if made else ", which was already there.")
        )

    def _ensure_role(self, connection, role: str, password: str) -> bool:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
            if cursor.fetchone():
                # The password is set again on every start, so that changing
                # the database password in secrets/ reaches both accounts.
                cursor.execute(
                    f'ALTER ROLE "{role}" WITH LOGIN PASSWORD %s', (password,)
                )
                return False
            cursor.execute(f'CREATE ROLE "{role}" LOGIN PASSWORD %s', (password,))
            return True

    def _hand_over(self, connection, bootstrap: str, role: str, database: str) -> None:
        """Give the app role the database and everything already in it.

        On a database that has been running, the tables were made by the
        bootstrap account. Reassigning them is what lets the app's own role
        migrate its own tables from here on.
        """
        with connection.cursor() as cursor:
            cursor.execute(f'GRANT CREATE, USAGE ON SCHEMA public TO "{role}"')
            cursor.execute(f'GRANT ALL ON DATABASE "{database}" TO "{role}"')
            cursor.execute(f'REASSIGN OWNED BY "{bootstrap}" TO "{role}"')
