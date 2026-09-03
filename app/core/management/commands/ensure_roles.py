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
            self._audit_roles(connection, app_role)

        self.stdout.write(
            f"The app connects as {app_role}"
            + (", which was made just now." if made else ", which was already there.")
        )

    def _ensure_role(self, connection, role: str, password: str) -> bool:
        """Make the role, or set its password again if it is already there.

        CREATE ROLE and ALTER ROLE are utility statements and take no
        parameters, so the password cannot be passed the ordinary way. It is
        composed as a quoted literal instead, which psycopg escapes, rather
        than pasted into a string.
        """
        from psycopg import sql

        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
            already = cursor.fetchone() is not None

            # The password is set again on every start, so that changing the
            # database password in secrets/ reaches both accounts.
            statement = sql.SQL(
                "ALTER ROLE {name} WITH LOGIN PASSWORD {password}"
                if already
                else "CREATE ROLE {name} LOGIN PASSWORD {password}"
            ).format(name=sql.Identifier(role), password=sql.Literal(password))
            cursor.execute(statement)
            return not already

    def _audit_roles(self, connection, app_role: str) -> None:
        """The audit log's two roles, and the app's membership of both.

        Made here rather than in a migration because making a role needs a
        privilege the app's own role does not have and should not have. The
        migration grants them what they may do on the audit table, which is
        the app role's business, because it owns that table.

        NOINHERIT is what makes the membership mean something: the app holds
        neither role's privileges until it asks for one by name.
        """
        from psycopg import sql

        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("ALTER ROLE {} NOINHERIT").format(sql.Identifier(app_role))
            )
            for role in ("transcribe_audit", "transcribe_audit_sweep"):
                cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
                if not cursor.fetchone():
                    cursor.execute(
                        sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role))
                    )
                # WITH INHERIT FALSE on the grant itself, not only NOINHERIT on
                # the role. From PostgreSQL 16 a membership carries its own
                # inherit flag, fixed when it is granted, so changing the role
                # afterwards leaves an older membership inheriting. Without
                # this the app quietly inherited DELETE from the sweeper and
                # could remove audit rows.
                cursor.execute(
                    sql.SQL("GRANT {} TO {} WITH INHERIT FALSE").format(
                        sql.Identifier(role), sql.Identifier(app_role)
                    )
                )

    def _hand_over(self, connection, bootstrap: str, role: str, database: str) -> None:
        """Give the app role what it needs, and the tables already there.

        On a database that has been running, the tables were made by the
        bootstrap account, and the app's own role has to own them to migrate
        them from here on.

        The tables and sequences are moved one by one rather than with REASSIGN
        OWNED, which sweeps up everything a role owns and refuses when some of
        it is pinned by the database system, which is what the database itself
        and the public schema are.
        """
        from psycopg import sql

        name = sql.Identifier(role)
        with connection.cursor() as cursor:
            cursor.execute(
                sql.SQL("GRANT CREATE, USAGE ON SCHEMA public TO {}").format(name)
            )
            cursor.execute(
                sql.SQL("GRANT ALL ON DATABASE {} TO {}").format(
                    sql.Identifier(database), name
                )
            )

            cursor.execute(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND tableowner = %s",
                (bootstrap,),
            )
            for (table,) in cursor.fetchall():
                cursor.execute(
                    sql.SQL("ALTER TABLE public.{} OWNER TO {}").format(
                        sql.Identifier(table), name
                    )
                )

            cursor.execute(
                "SELECT sequencename FROM pg_sequences "
                "WHERE schemaname = 'public' AND sequenceowner = %s",
                (bootstrap,),
            )
            for (sequence,) in cursor.fetchall():
                cursor.execute(
                    sql.SQL("ALTER SEQUENCE public.{} OWNER TO {}").format(
                        sql.Identifier(sequence), name
                    )
                )
