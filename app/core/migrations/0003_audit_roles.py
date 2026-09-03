"""The audit log's two database roles, and what each may do.

The app writes a row by switching to a role that can insert and nothing else,
and the retention sweep removes rows by switching to a role that can delete and
nothing else. The app's own role keeps SELECT, because the Admin viewer reads
the log, and is revoked UPDATE and DELETE.

Both roles are cluster-wide rather than per-database, so this is written to be
run more than once without complaint. See ADR 0008 for why they are reached
with SET ROLE rather than with a second connection and a second password.
"""

from django.db import migrations

CREATE_ROLES = """
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'transcribe_audit') THEN
        CREATE ROLE transcribe_audit NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'transcribe_audit_sweep') THEN
        CREATE ROLE transcribe_audit_sweep NOLOGIN;
    END IF;
END$$;

GRANT transcribe_audit TO CURRENT_USER;
GRANT transcribe_audit_sweep TO CURRENT_USER;

-- The app holds neither role's privileges until it asks for them by name.
ALTER ROLE CURRENT_USER NOINHERIT;

-- The insert-only role. It can add a row and read the sequence that numbers
-- it, and it can do nothing else at all.
GRANT USAGE ON SCHEMA public TO transcribe_audit;
GRANT INSERT, SELECT ON core_row TO transcribe_audit;
GRANT USAGE, SELECT ON SEQUENCE core_row_id_seq TO transcribe_audit;

-- The sweep's role. It is the only thing in the app that can remove an audit
-- row, and removing them is all it can do.
GRANT USAGE ON SCHEMA public TO transcribe_audit_sweep;
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

    operations = [migrations.RunSQL(CREATE_ROLES, reverse_sql=UNDO)]
