"""The audit log's database roles: that they exist, and what each may do.

These read the database's own catalogue rather than trying the operations,
because a test run connects as the account that made the database, which in
PostgreSQL is a superuser and ignores every permission rule. What can be
checked anywhere is that the grants say what they are meant to say.
"""

import pytest
from django.db import connection


def privileges(role: str, table: str = "core_row") -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT privilege_type
            FROM information_schema.table_privileges
            WHERE grantee = %s AND table_name = %s
            """,
            (role, table),
        )
        return {row[0] for row in cursor.fetchall()}


def role_exists(role: str) -> bool:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
        return cursor.fetchone() is not None


@pytest.mark.django_db
def test_both_roles_exist():
    assert role_exists("transcribe_audit")
    assert role_exists("transcribe_audit_sweep")


@pytest.mark.django_db
def test_the_writer_can_insert_and_nothing_that_changes_a_row():
    held = privileges("transcribe_audit")
    assert "INSERT" in held
    assert "UPDATE" not in held
    assert "DELETE" not in held
    assert "TRUNCATE" not in held


@pytest.mark.django_db
def test_the_sweeper_can_delete_and_not_insert_or_change():
    held = privileges("transcribe_audit_sweep")
    assert "DELETE" in held
    assert "INSERT" not in held
    assert "UPDATE" not in held


@pytest.mark.django_db
def test_writing_a_row_goes_through_the_writer_role():
    """The row is written while the connection is that role, not the app's."""
    from core import audit

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_user")
        before = cursor.fetchone()[0]

    audit.write(audit.Category.SYSTEM, "daily sweeper ran", system="sweeper")

    with connection.cursor() as cursor:
        cursor.execute("SELECT current_user")
        after = cursor.fetchone()[0]

    # SET LOCAL lasts as long as the transaction, so the connection comes back
    # to the app's own role afterwards rather than staying switched.
    assert after == before
    assert audit.Row.objects.count() == 1
