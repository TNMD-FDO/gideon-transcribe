"""The audit log's two database roles, and what each may do.

The app writes a row by switching to a role that can insert and nothing else,
and the retention sweep removes rows by switching to a role that can delete and
nothing else. The app's own role keeps SELECT, because the Admin viewer reads
the log, and is revoked UPDATE and DELETE.

The roles themselves are made by `manage.py ensure_roles`, which runs before
the migrations as the account that bootstrapped the database, because making a
role needs a privilege the app's own role does not have and should not have.
The block below makes them anyway when the account running the migrations can,
which is what happens in a test database, where there is one account and it
made everything.

The grants are the other way round: they are on a table the app's role owns, so
the app's role is exactly who should be making them.

See ADR 0008 for why the roles are reached with SET ROLE rather than with a
second connection and a second password.
"""

from django.db import migrations

# Only where the account running this can make a role at all. On a server that
# is the bootstrap account, and ensure_roles has already done this; in a test
# database it is the one account there is.
MAKE_ROLES_IF_ALLOWED = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_roles
        WHERE rolname = CURRENT_USER AND (rolsuper OR rolcreaterole)
    ) THEN
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'transcribe_audit') THEN
            CREATE ROLE transcribe_audit NOLOGIN;
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_roles WHERE rolname = 'transcribe_audit_sweep'
        ) THEN
            CREATE ROLE transcribe_audit_sweep NOLOGIN;
        END IF;

        -- The app holds neither role's privileges until it asks by name.
        -- WITH INHERIT FALSE on the grant as well, because from PostgreSQL 16
        -- a membership carries its own inherit flag, fixed when it is granted.
        EXECUTE format('ALTER ROLE %I NOINHERIT', CURRENT_USER);
        EXECUTE format(
            'GRANT transcribe_audit TO %I WITH INHERIT FALSE', CURRENT_USER
        );
        EXECUTE format(
            'GRANT transcribe_audit_sweep TO %I WITH INHERIT FALSE', CURRENT_USER
        );
    END IF;
END$$;
"""

GRANTS = """
GRANT USAGE ON SCHEMA public TO transcribe_audit;
GRANT USAGE ON SCHEMA public TO transcribe_audit_sweep;

-- The insert-only role. It can add a row and read the sequence that numbers
-- it, and it can do nothing else at all.
GRANT INSERT, SELECT ON core_row TO transcribe_audit;
GRANT USAGE, SELECT ON SEQUENCE core_row_id_seq TO transcribe_audit;

-- The sweep's role. It is the only thing in the app that can remove an audit
-- row, and removing them is all it can do.
GRANT SELECT, DELETE ON core_row TO transcribe_audit_sweep;

-- The app's own role reads the log and cannot change it. It owns the table,
-- so it could grant itself back what is revoked here; that is why the rows are
-- hashed onto one another, and why the specification calls this tamper-evident
-- rather than tamper-proof.
REVOKE UPDATE, DELETE, TRUNCATE ON core_row FROM CURRENT_USER;
"""

UNDO = """
GRANT UPDATE, DELETE, TRUNCATE ON core_row TO CURRENT_USER;
REVOKE ALL ON core_row FROM transcribe_audit;
REVOKE ALL ON core_row FROM transcribe_audit_sweep;
"""


class Migration(migrations.Migration):
    dependencies = [("core", "0002_row")]

    operations = [
        migrations.RunSQL(MAKE_ROLES_IF_ALLOWED, reverse_sql=migrations.RunSQL.noop),
        migrations.RunSQL(GRANTS, reverse_sql=UNDO),
    ]
