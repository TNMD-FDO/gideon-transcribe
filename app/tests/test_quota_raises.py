"""A quota raised for a while (v1.155.0; Phase 2, Room): the one number a
person's space is in each state, the hourly pass and its rows, the users
list's form and actions, the person's own line, and the upload check
reading the raised figure."""

from __future__ import annotations

from datetime import timedelta

import pytest
from core import audit, quota_raises, settings_store, uploads
from core.models import User
from django.utils import timezone
from tests.helpers import signed_in

PASSWORD = "a-long-enough-password"
GB = settings_store.GB


@pytest.fixture
def admin(db):
    return User.objects.create_local_admin("adm", PASSWORD)


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("jlopez", PASSWORD)


def stored(monkeypatch, gigabytes):
    monkeypatch.setattr(uploads, "used_bytes", lambda user: int(gigabytes * GB))


def test_the_space_is_one_number_in_each_state(admin, person, monkeypatch):
    settings_store.set_to("default_quota_gb", 50)
    stored(monkeypatch, 20)
    assert uploads.quota_bytes(person) == 50 * GB
    assert quota_raises.notice(person) is None
    # Raised: the raise's figure, and the person's line says so.
    made = quota_raises.raise_for(person, 100, 45, "Discovery dump", by=admin)
    assert made.running and made.days_left == 45
    assert uploads.quota_bytes(person) == 100 * GB
    assert quota_raises.notice(person).startswith("Your space is 100 GB until ")
    assert quota_raises.notice(person).endswith(", then 50 GB again.")
    # The days run out with more stored than the usual figure: what is
    # stored, and no more; the person reads why.
    stored(monkeypatch, 70.5)
    made.ends = timezone.now() - timedelta(minutes=1)
    made.save(update_fields=["ends"])
    assert uploads.quota_bytes(person) == int(70.5 * GB)
    assert uploads.room_left(person) == 0
    words = quota_raises.notice(person)
    assert words.startswith("Your space was raised to 100 GB until ")
    assert "once your recordings are under 50 GB" in words
    # The storage comes down: the figure follows it to the usual quota.
    stored(monkeypatch, 60)
    assert uploads.quota_bytes(person) == 60 * GB
    stored(monkeypatch, 40)
    assert uploads.quota_bytes(person) == 50 * GB
    # A standing override is the usual figure under the raise.
    person.quota_gb = 80
    person.save(update_fields=["quota_gb"])
    stored(monkeypatch, 70)
    assert uploads.quota_bytes(person) == 80 * GB
    # A raise never lowers a space below the usual figure.
    with pytest.raises(ValueError):
        quota_raises.raise_for(person, 60, 45, "", by=admin)
    with pytest.raises(ValueError):
        quota_raises.raise_for(person, 200, 0, "", by=admin)


def test_the_hourly_pass_moves_the_states_and_writes_the_rows(
    admin, person, monkeypatch
):
    settings_store.set_to("default_quota_gb", 50)
    stored(monkeypatch, 70)
    made = quota_raises.raise_for(person, 100, 10, "note", by=admin)
    row = audit.Row.objects.get(event="temporary quota raised")
    assert row.details["gigabytes"] == 100 and row.details["days"] == 10
    assert row.details["note"] == "note" and row.affected_user_id == person.pk
    # Still running: nothing moves.
    assert quota_raises.sweep() == {"ran_out": 0, "closed": 0}
    # Ran out with more stored: coming back down.
    made.ends = timezone.now() - timedelta(hours=1)
    made.save(update_fields=["ends"])
    assert quota_raises.sweep() == {"ran_out": 1, "closed": 0}
    made.refresh_from_db()
    assert made.state == quota_raises.WINDING
    ran = audit.Row.objects.get(event="temporary quota ran out")
    assert ran.details["stored_gb"] == 70.0 and ran.details["usual_gb"] == 50
    assert uploads.quota_bytes(person) == 70 * GB
    # The storage reaches the usual figure: closed by the storage.
    stored(monkeypatch, 49)
    assert quota_raises.sweep() == {"ran_out": 0, "closed": 1}
    made.refresh_from_db()
    assert made.state == quota_raises.CLOSED
    assert made.closed_how == quota_raises.BY_STORAGE
    closed = audit.Row.objects.get(event="temporary quota closed")
    assert closed.details["how"] == "stored"
    assert quota_raises.current(person) is None
    assert uploads.quota_bytes(person) == 50 * GB
    # The row for the users list keeps the last raise as one closed line.
    shown = quota_raises.row_for(person)
    assert shown["state"] == quota_raises.CLOSED and shown["closed_on"]
    # Ran out with the storage already under: closed by its date.
    other = quota_raises.raise_for(person, 100, 10, "", by=admin)
    other.ends = timezone.now() - timedelta(hours=1)
    other.save(update_fields=["ends"])
    assert quota_raises.sweep() == {"ran_out": 0, "closed": 1}
    other.refresh_from_db()
    assert other.closed_how == quota_raises.BY_DATE


def test_ending_early_extending_and_replacing(admin, person, monkeypatch):
    settings_store.set_to("default_quota_gb", 50)
    stored(monkeypatch, 70)
    made = quota_raises.raise_for(person, 100, 45, "", by=admin)
    # Another spell moves the date on from the old one.
    quota_raises.extend(made, 45, by=admin)
    made.refresh_from_db()
    assert made.days_left >= 89
    assert audit.Row.objects.filter(event="temporary quota extended").count() == 1
    # Ended early with more stored: coming back down, not cut.
    quota_raises.end_now(made, by=admin)
    made.refresh_from_db()
    assert made.state == quota_raises.WINDING
    assert uploads.quota_bytes(person) == 70 * GB
    ended = audit.Row.objects.get(event="temporary quota ended early")
    assert ended.details["closed"] is False
    # Another spell on one coming back down runs it again from today.
    quota_raises.extend(made, 10, by=admin)
    made.refresh_from_db()
    assert made.running and 9 <= made.days_left <= 10
    # A new raise replaces the one in force.
    new = quota_raises.raise_for(person, 120, 20, "", by=admin)
    made.refresh_from_db()
    assert (
        made.state == quota_raises.CLOSED and made.closed_how == quota_raises.BY_ADMIN
    )
    assert quota_raises.current(person) == new
    assert audit.Row.objects.get(
        event="temporary quota raised", details__replaced=str(made.pk)
    )
    # Ended early with the storage under: closed at once.
    stored(monkeypatch, 10)
    quota_raises.end_now(new, by=admin)
    new.refresh_from_db()
    assert new.state == quota_raises.CLOSED


def test_the_users_page_raises_ends_and_extends(admin, person, monkeypatch, client):
    settings_store.set_to("default_quota_gb", 50)
    settings_store.set_to("temporary_quota_days", 30)
    stored(monkeypatch, 20)
    signed_in(client, admin)
    body = client.get("/panel/users").content.decode()
    assert "Raise for a while..." in body and 'name="raise_gb"' in body
    assert 'value="30"' in body  # the setting is the form's default
    answer = client.post(
        f"/panel/users/{person.username}",
        {"action": "raise", "raise_gb": "100", "raise_days": "", "raise_note": "Reyes"},
    )
    assert answer.status_code == 302
    made = quota_raises.current(person)
    assert made.gigabytes == 100 and made.days == 30 and made.note == "Reyes"
    body = client.get("/panel/users").content.decode()
    assert "Raised to 100 GB until" in body and "30 days left" in body
    assert "End now" in body and "Another 30 days" in body
    assert (
        "Raise for a while..."
        not in body.split(person.username, 1)[1].split("</tr>", 1)[0]
    )
    # Extend from the row.
    client.post(
        f"/panel/users/{person.username}",
        {"action": "raise-extend", "raise_days": "30"},
    )
    made.refresh_from_db()
    assert made.days_left >= 59
    # Below the usual figure: refused with a reason, nothing made.
    answer = client.post(
        f"/panel/users/{person.username}",
        {"action": "raise", "raise_gb": "40", "raise_days": "30"},
    )
    assert answer.status_code == 302
    assert quota_raises.current(person) == made
    # End now with more stored: coming back down on the page.
    stored(monkeypatch, 70)
    client.post(f"/panel/users/{person.username}", {"action": "raise-end"})
    made.refresh_from_db()
    assert made.state == quota_raises.WINDING
    body = client.get("/panel/users").content.decode()
    assert (
        "coming back down" in body
        and "nothing new fits until it is under 50 GB" in body
    )
    # Nothing in force: the form is back once the storage comes down.
    stored(monkeypatch, 10)
    quota_raises.sweep()
    body = client.get("/panel/users").content.decode()
    assert "Raise for a while..." in body and "back to 50 GB on" in body


def test_the_upload_check_and_the_pages_read_the_raise(
    admin, person, monkeypatch, client
):
    from core.recordings import Batch

    settings_store.set_to("default_quota_gb", 50)
    stored(monkeypatch, 45)
    monkeypatch.setattr(uploads, "free_disk_bytes", lambda: 10_000 * GB)
    batch = Batch.objects.create(user=person)
    # Over the usual figure: refused; raised: allowed.
    refused = uploads.check_before_upload(person, batch, 10 * GB, 1)
    assert refused is not None and refused.reason_class == "quota_exceeded"
    quota_raises.raise_for(person, 100, 45, "", by=admin)
    assert uploads.check_before_upload(person, batch, 10 * GB, 1) is None
    # The person's line on Home and the Upload page.
    signed_in(client, person)
    assert "Your space is 100 GB until" in client.get("/").content.decode()
    assert "Your space is 100 GB until" in client.get("/upload").content.decode()
    # The setting sits in the catalogue and the task is scheduled hourly.
    from pathlib import Path

    here = Path(__file__).resolve().parents[1]
    catalogue = (
        here.parent / "docs" / "spec" / "ADMIN-SETTINGS-CATALOGUE.md"
    ).read_text(encoding="utf-8")
    assert "| Temporary quota length | days, 1 to 365 | 45 days |" in catalogue
    tasks = (here / "core" / "tasks.py").read_text(encoding="utf-8")
    assert 'name="sweep_quota_raises"' in tasks and "quota_raises.sweep()" in tasks
