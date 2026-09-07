"""Signing in: who gets in, who does not, and what ends a session."""

from datetime import timedelta

import pytest
from core import settings_store, signin
from core.models import LoginSession, SignInAttempt, User, normalise_username
from django.test import Client
from django.utils import timezone

PASSWORD = "a-long-enough-password"


@pytest.fixture
def admin(db):
    return User.objects.create_local_admin("transcribe-admin", PASSWORD)


def sign_in(client, username=None, password=PASSWORD):
    return client.post(
        "/sign-in",
        {"username": username or "transcribe-admin", "password": password},
    )


# What a person may type ------------------------------------------------------


@pytest.mark.parametrize(
    "typed",
    ["jsmith", "JSmith", "jsmith@office.example", "OFFICE\\jsmith", "  jsmith  "],
)
def test_every_way_of_typing_a_username_means_the_same_person(typed):
    assert normalise_username(typed) == "jsmith"


def test_a_username_with_both_a_domain_and_a_prefix():
    assert normalise_username("OFFICE\\jsmith@office.example") == "jsmith"


def test_nothing_typed_is_nobody():
    assert normalise_username("") == ""
    assert normalise_username("   ") == ""


# Signing in ------------------------------------------------------------------


def test_a_local_admin_signs_in(client, admin):
    answer = sign_in(client)
    assert answer.status_code == 302
    # Signing in opens the Start page, whoever it is: one question, what do
    # you want to do, and the other pages are one click away.
    assert answer.url == "/start"


def test_a_local_admin_is_an_admin(admin):
    assert admin.is_admin is True
    assert admin.admin_source == "local"


def test_the_wrong_password_is_refused(client, admin):
    answer = sign_in(client, password="not-the-password")
    assert answer.status_code == 400
    assert signin.WRONG in answer.text


def test_an_empty_password_never_reaches_the_directory(client, admin):
    answer = client.post("/sign-in", {"username": "somebody", "password": ""})
    assert answer.status_code == 400
    assert "Enter your password" in answer.text
    # Nothing was tried, so nothing counts against the throttle.
    assert SignInAttempt.objects.count() == 0


def test_a_directory_user_is_told_the_directory_cannot_be_reached(client, db):
    """The truth, while there is no directory connection to make."""
    answer = sign_in(client, username="jsmith")
    assert answer.status_code == 400
    assert signin.DIRECTORY_UNAVAILABLE in answer.text


def test_a_deactivated_local_admin_cannot_sign_in(client, admin):
    admin.deactivated_at = timezone.now()
    admin.save()
    answer = sign_in(client)
    assert answer.status_code == 400
    assert signin.NOT_ALLOWED in answer.text


def test_a_blocked_local_admin_cannot_sign_in(client, admin):
    admin.blocked_at = timezone.now()
    admin.save()
    assert sign_in(client).status_code == 400
    assert admin.status == "blocked"


# The throttle ----------------------------------------------------------------


def test_five_failures_from_one_place_impose_a_wait(client, admin):
    for _ in range(5):
        sign_in(client, password="wrong")
    answer = sign_in(client)
    assert answer.status_code == 400
    assert "Too many attempts" in answer.text


def test_the_wait_counts_a_username_from_anywhere(db):
    """Two addresses must not be able to lock a directory account between them.

    The domain locks an account after six wrong passwords in thirty minutes, so
    a per-address count alone would let two addresses reach that between them
    while each stayed under its own limit.
    """
    for number in range(5):
        SignInAttempt.record("jsmith", f"192.0.2.{number}")
    assert SignInAttempt.wait_for("jsmith", "192.0.2.99") is not None


def test_a_different_username_is_not_held_up(db):
    for _ in range(5):
        SignInAttempt.record("jsmith", "192.0.2.1")
    assert SignInAttempt.wait_for("someone-else", "192.0.2.1") is None


def test_the_wait_runs_out(db):
    for _ in range(5):
        SignInAttempt.record("jsmith", "192.0.2.1")
    SignInAttempt.objects.update(at=timezone.now() - timedelta(minutes=16))
    assert SignInAttempt.wait_for("jsmith", "192.0.2.1") is None


def test_signing_in_clears_what_was_counted_against_you(client, admin):
    for _ in range(3):
        sign_in(client, password="wrong")
    sign_in(client)
    assert SignInAttempt.objects.filter(username="transcribe-admin").count() == 0


# Login sessions --------------------------------------------------------------


def test_signing_in_starts_a_session(client, admin):
    sign_in(client)
    session = LoginSession.objects.get(user=admin)
    assert session.is_open


def test_a_newer_sign_in_ends_the_older_session(client, admin):
    sign_in(client)
    sign_in(Client())

    sessions = LoginSession.objects.filter(user=admin).order_by("started")
    assert sessions[0].end_reason == LoginSession.ELSEWHERE
    assert sessions[1].is_open


def test_the_older_session_is_told_why_on_its_next_request(client, admin):
    sign_in(client)
    sign_in(Client())

    answer = client.get("/", follow=True)
    assert signin.SIGNED_IN_ELSEWHERE in answer.text


def test_signing_out_ends_the_session(client, admin):
    sign_in(client)
    # A GET shows the dialog and signs nobody out: the page names what
    # is about to go and only the button acts.
    client.get("/sign-out")
    assert LoginSession.objects.get(user=admin).end_reason == ""

    client.post("/sign-out")
    assert LoginSession.objects.get(user=admin).end_reason == LoginSession.LOGOUT


def test_a_session_that_has_sat_idle_ends(client, admin):
    sign_in(client)
    session = LoginSession.objects.get(user=admin)
    session.last_request = timezone.now() - timedelta(hours=9)
    session.save()

    answer = client.get("/", follow=True)
    assert "signed out after a long wait" in answer.text
    assert LoginSession.objects.get(user=admin).end_reason == LoginSession.IDLE


def test_a_session_within_the_timeout_carries_on(client, admin):
    sign_in(client)
    session = LoginSession.objects.get(user=admin)
    session.last_request = timezone.now() - timedelta(hours=7)
    session.save()

    assert client.get("/").status_code == 200
    assert LoginSession.objects.get(user=admin).is_open


def test_the_warning_comes_a_quarter_of_an_hour_before(client, admin):
    sign_in(client)
    session = LoginSession.objects.get(user=admin)
    session.last_request = timezone.now() - timedelta(hours=7, minutes=50)
    session.save()
    assert signin.warning_due(session) is True

    session.last_request = timezone.now() - timedelta(hours=7)
    assert signin.warning_due(session) is False


def test_a_health_check_does_not_move_anybodys_idle_clock(client, admin):
    sign_in(client)
    session = LoginSession.objects.get(user=admin)
    session.last_request = timezone.now() - timedelta(hours=1)
    session.save(update_fields=["last_request"])
    before = LoginSession.objects.get(pk=session.pk).last_request

    client.get("/healthz")

    assert LoginSession.objects.get(pk=session.pk).last_request == before


# The pages -------------------------------------------------------------------


def test_the_home_page_needs_a_sign_in(client, db):
    answer = client.get("/")
    assert answer.status_code == 302
    assert "/sign-in" in answer.url


def test_the_home_page_says_who_you_are(client, admin):
    sign_in(client)
    answer = client.get("/")
    assert "transcribe-admin" in answer.text
    assert "Admin" in answer.text


# Settings --------------------------------------------------------------------


def test_the_idle_timeout_starts_at_eight_hours(db):
    assert settings_store.idle_timeout() == timedelta(hours=8)


def test_a_setting_can_be_moved(db):
    settings_store.set_to("idle_timeout_minutes", 60)
    assert settings_store.idle_timeout() == timedelta(hours=1)


def test_a_setting_outside_its_range_is_refused(db):
    with pytest.raises(ValueError, match="outside that"):
        settings_store.set_to("idle_timeout_minutes", 5)
    with pytest.raises(ValueError, match="outside that"):
        settings_store.set_to("idle_timeout_minutes", 40 * 60)


def test_a_setting_that_does_not_exist_is_refused(db):
    with pytest.raises(KeyError, match="no setting called"):
        settings_store.get("colour_of_the_bikeshed")


# Local admins ----------------------------------------------------------------


def test_a_local_admin_needs_a_name_and_a_password(db):
    with pytest.raises(ValueError, match="needs a name"):
        User.objects.create_local_admin("", PASSWORD)
    with pytest.raises(ValueError, match="needs a password"):
        User.objects.create_local_admin("someone", "")


def test_a_local_admin_has_no_directory_record(admin):
    assert admin.directory_address == ""
    assert admin.is_local is True


def test_nobody_is_an_admin_by_default(db):
    user = User.objects.from_directory("jsmith", display_name="J Smith")
    assert user.is_admin is False
    assert user.admin_source is None


def test_the_admin_group_makes_an_admin(db):
    user = User.objects.from_directory("jsmith", in_admin_group=True)
    assert user.is_admin is True
    assert user.admin_source == "group"


def test_the_manual_flag_makes_an_admin(db):
    user = User.objects.from_directory("jsmith", admin_flag=True)
    assert user.is_admin is True
    assert user.admin_source == "manual"


def test_the_group_outranks_the_manual_flag_as_a_source(db):
    """A manual flag cannot demote a member of the Admin group.

    The group only ever adds, so removing a group member's admin status means
    removing them from the group in the directory, and the users list has to
    say that is where it comes from.
    """
    user = User.objects.from_directory("jsmith", in_admin_group=True, admin_flag=True)
    assert user.admin_source == "group"


def test_a_directory_account_is_updated_at_every_sign_in(db):
    User.objects.from_directory("jsmith", display_name="J Smith")
    user = User.objects.from_directory("jsmith", display_name="Jane Smith")
    assert User.objects.filter(username="jsmith").count() == 1
    assert user.display_name == "Jane Smith"


def test_the_idle_clock_is_not_written_on_every_request(client, admin):
    """A browser asks for a video in ranges, and each one is a request here.

    Somebody jumping about in a recording asks for several at once. Writing a
    row for each before a byte is served made the app the slowest part of
    watching a video, which is the last thing it should be.
    """
    sign_in(client)
    session = LoginSession.objects.get(user=admin)
    was = session.last_request

    for _ in range(5):
        client.get("/")

    session.refresh_from_db()
    assert session.last_request == was


def test_the_idle_clock_still_moves(client, admin):
    from core.middleware import CLOCK_STEP

    sign_in(client)
    session = LoginSession.objects.get(user=admin)
    # As it would be after a minute of watching.
    LoginSession.objects.filter(pk=session.pk).update(
        last_request=timezone.now() - CLOCK_STEP - timedelta(seconds=1)
    )

    client.get("/")

    session.refresh_from_db()
    assert timezone.now() - session.last_request < timedelta(seconds=5)
