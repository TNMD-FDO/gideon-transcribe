"""The audit log: what a row holds, and what the chain catches."""

from datetime import UTC, datetime, timedelta

import pytest
from core import audit
from core.models import LoginSession, User
from django.test import Client
from django.utils import timezone

PASSWORD = "a-long-enough-password"


@pytest.fixture
def admin(db):
    return User.objects.create_local_admin("transcribe-admin", PASSWORD)


def sign_in(client, username="transcribe-admin", password=PASSWORD):
    return client.post("/sign-in", {"username": username, "password": password})


def rows(event=None):
    found = audit.Row.objects.order_by("id")
    return list(found.filter(event=event) if event else found)


# The chain -------------------------------------------------------------------


def test_the_first_row_points_at_nothing(db):
    row = audit.write(audit.Category.SYSTEM, "daily sweeper ran", system="sweeper")
    assert row.previous_hash == audit.FIRST_LINK
    assert row.row_hash


def test_each_row_points_at_the_one_before(db):
    first = audit.write(audit.Category.SYSTEM, "daily sweeper ran", system="sweeper")
    second = audit.write(audit.Category.SYSTEM, "daily sweeper ran", system="sweeper")
    assert second.previous_hash == first.row_hash


def test_an_untouched_chain_is_unbroken(db):
    for _ in range(5):
        audit.write(audit.Category.SYSTEM, "daily sweeper ran", system="sweeper")
    result = audit.check_integrity()
    assert result["unbroken"] is True
    assert result["rows"] == 5


def test_an_empty_log_is_not_a_break(db):
    result = audit.check_integrity()
    assert result["unbroken"] is True
    assert "nothing in the log" in result["message"]


def test_an_edited_row_is_found(db):
    audit.write(audit.Category.SYSTEM, "daily sweeper ran", system="sweeper")
    middle = audit.write(audit.Category.ADMIN, "setting changed", system="sweeper")
    audit.write(audit.Category.SYSTEM, "daily sweeper ran", system="sweeper")

    # Somebody rewrites what a row says happened. The row's own hash no longer
    # describes its contents.
    audit.Row.objects.filter(pk=middle.pk).update(event="something harmless")

    result = audit.check_integrity()
    assert result["unbroken"] is False
    assert result["first_break_id"] == middle.pk
    assert "its own contents" in result["message"]


def test_a_removed_row_is_found(db):
    audit.write(audit.Category.SYSTEM, "daily sweeper ran", system="sweeper")
    middle = audit.write(audit.Category.ADMIN, "setting changed", system="sweeper")
    last = audit.write(audit.Category.SYSTEM, "daily sweeper ran", system="sweeper")

    audit.Row.objects.filter(pk=middle.pk).delete()

    result = audit.check_integrity()
    assert result["unbroken"] is False
    assert result["first_break_id"] == last.pk
    assert "the row before it" in result["message"]


def test_an_edited_details_block_is_found(db):
    """The whole row is hashed, not a few fields of it."""
    row = audit.write(
        audit.Category.RECORDINGS, "upload accepted", system="sweeper", size=1000
    )
    audit.Row.objects.filter(pk=row.pk).update(details={"size": 1})
    assert audit.check_integrity()["unbroken"] is False


# What a row holds ------------------------------------------------------------


def test_signing_in_writes_a_row(client, admin):
    sign_in(client)
    row = rows("sign-in succeeded")[0]
    assert row.actor_username == "transcribe-admin"
    assert row.category == audit.Category.SIGN_IN
    assert row.outcome == audit.Outcome.SUCCESS
    assert row.details["source"] == "local"
    assert row.login_session_id is not None


def test_a_wrong_password_writes_a_row_with_its_reason(client, admin):
    sign_in(client, password="wrong")
    row = rows("sign-in failed")[0]
    assert row.outcome == audit.Outcome.FAILURE
    assert row.reason_class == audit.Reason.WRONG_PASSWORD


def test_a_name_with_no_account_still_writes_a_row(client, db):
    sign_in(client, username="nobody-here")
    row = rows("sign-in failed")[0]
    assert row.actor_kind == "unknown"
    assert row.reason_class == audit.Reason.DIRECTORY_UNREACHABLE
    assert row.details["typed_username"] == "nobody-here"


def test_being_throttled_writes_a_row(client, admin):
    for _ in range(5):
        sign_in(client, password="wrong")
    sign_in(client)
    assert any(row.reason_class == audit.Reason.THROTTLED for row in rows())


def test_a_blocked_account_says_so(client, admin):
    admin.blocked_at = timezone.now()
    admin.save()
    sign_in(client)
    assert rows("sign-in failed")[0].reason_class == audit.Reason.BLOCKED


def test_signing_out_writes_a_row(client, admin):
    sign_in(client)
    client.get("/sign-out")
    row = rows("sign-out")[0]
    assert row.details["cause"] == LoginSession.LOGOUT


def test_signing_in_elsewhere_writes_the_older_sessions_row(client, admin):
    sign_in(client)
    sign_in(Client())
    causes = [row.details.get("cause") for row in rows("sign-out")]
    assert LoginSession.ELSEWHERE in causes


def test_the_idle_timeout_is_the_systems_doing_not_the_persons(client, admin):
    sign_in(client)
    session = LoginSession.objects.get(user=admin)
    session.last_request = timezone.now() - timedelta(hours=9)
    session.save()
    client.get("/", follow=True)

    idle = [r for r in rows("sign-out") if r.details.get("cause") == LoginSession.IDLE]
    row = idle[0]
    assert row.actor_kind == "system"
    assert row.actor_username == "sweeper"
    assert row.affected_user_id == admin.pk


def test_a_row_keeps_the_client_address_and_browser(client, admin):
    client.post(
        "/sign-in",
        {"username": "transcribe-admin", "password": PASSWORD},
        HTTP_X_FORWARDED_FOR="192.0.2.7",
        HTTP_USER_AGENT="Mozilla/5.0 (Windows NT 10.0) Chrome/141 Edg/141",
    )
    row = rows("sign-in succeeded")[0]
    assert row.client_address == "192.0.2.7"
    assert row.client_browser == "Edge"


@pytest.mark.parametrize(
    "agent,family",
    [
        ("Mozilla/5.0 Chrome/141.0 Safari/537", "Chrome"),
        ("Mozilla/5.0 Chrome/141.0 Edg/141.0", "Edge"),
        ("Mozilla/5.0 Firefox/140.0", "other"),
        ("", "other"),
    ],
)
def test_the_browser_family_is_one_of_three(agent, family):
    assert audit.browser_family(agent) == family


def test_a_password_never_reaches_a_row(client, admin):
    sign_in(client, password="hunter2-and-then-some")
    for row in rows():
        assert "hunter2" not in str(row.details)
        assert "hunter2" not in row.object_label


# Retention -------------------------------------------------------------------


def test_the_sweep_removes_what_is_older_than_the_setting(db):
    old = audit.write(audit.Category.SYSTEM, "daily sweeper ran", system="sweeper")
    audit.Row.objects.filter(pk=old.pk).update(at=timezone.now() - timedelta(days=200))
    kept = audit.write(audit.Category.SYSTEM, "daily sweeper ran", system="sweeper")

    removed = audit.sweep(keep_months=3)

    assert removed == 1
    assert not audit.Row.objects.filter(pk=old.pk).exists()
    assert audit.Row.objects.filter(pk=kept.pk).exists()


def test_the_sweep_writes_its_own_row(db):
    audit.sweep(keep_months=3)
    row = rows("audit retention sweep ran")[0]
    assert row.actor_username == "retention sweep"
    assert row.details["rows_removed"] == 0


def test_months_are_calendar_months(db):
    when = datetime(2026, 3, 31, 12, 0, tzinfo=UTC)
    # February has no 31st, so it lands on the last day it has.
    assert audit.months_ago(1, when).day == 28
    assert audit.months_ago(3, when).month == 12
    assert audit.months_ago(3, when).year == 2025
