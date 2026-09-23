"""The pages that fail well (Phase 8 chapter 7): a script told plainly when
the session has ended, the session question that does not move the clock,
Sign in again returning the same person, the gone page, the failure page,
the form page, and the Admin band become a pill."""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path

import pytest
from core import settings_store, views
from core.cases import Case
from core.models import LoginSession, User
from django.contrib.auth.models import AnonymousUser
from django.test import Client, RequestFactory
from django.utils import timezone

PASSWORD = "a-long-enough-password"
SCRIPT = {"HTTP_X_REQUESTED_WITH": "transcribe"}
TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


@pytest.fixture
def admin(db):
    return User.objects.create_local_admin("asker", PASSWORD)


@pytest.fixture
def someone(db):
    return User.objects.from_directory("colleague", display_name="A Colleague")


def sign_in(client, username="asker", **more):
    return client.post("/sign-in", {"username": username, "password": PASSWORD, **more})


def idle_out(user, hours=9):
    session = LoginSession.objects.get(user=user, ended__isnull=True)
    session.last_request = timezone.now() - timedelta(hours=hours)
    session.save(update_fields=["last_request"])


# A session that ends under an open page -----------------------------------------


def test_a_script_is_told_plainly_when_the_session_sat_idle(client, admin):
    settings_store.set_to("folder_management", True)
    sign_in(client)
    idle_out(admin)

    answer = client.get("/", **SCRIPT)

    assert answer.status_code == 401
    assert answer.json() == {"signed_in": False, "why": "idle", "kept": True}
    assert LoginSession.objects.get(user=admin).end_reason == LoginSession.IDLE


def test_the_script_is_told_what_goes_when_there_are_no_cases(client, admin):
    settings_store.set_to("folder_management", False)
    sign_in(client)
    idle_out(admin)
    assert client.get("/", **SCRIPT).json()["kept"] is False


def test_a_link_is_still_sent_to_sign_in(client, admin):
    sign_in(client)
    idle_out(admin)
    answer = client.get("/")
    assert answer.status_code == 302 and answer["Location"].startswith("/sign-in")
    assert "signed out after a long wait" in client.get("/sign-in").text


def test_a_script_with_no_session_is_told_gone(client, db):
    answer = client.get("/", **SCRIPT)
    assert answer.status_code == 401
    assert answer.json()["why"] == "gone"
    # The browser following a link is sent to Sign in as it always was.
    assert client.get("/").status_code == 302


def test_the_older_session_is_told_it_signed_in_elsewhere(client, admin):
    sign_in(client)
    sign_in(Client())
    answer = client.get("/", **SCRIPT)
    assert answer.status_code == 401
    assert answer.json()["why"] == "elsewhere"


def test_the_session_question_answers_the_time_left_and_moves_nothing(client, admin):
    sign_in(client)
    idle_out(admin, hours=1)
    before = LoginSession.objects.get(user=admin).last_request

    answer = client.get("/session", **SCRIPT)

    assert answer.status_code == 200
    body = answer.json()
    assert body["signed_in"] is True
    assert 7 * 3600 - 60 <= body["left"] <= 7 * 3600
    assert LoginSession.objects.get(user=admin).last_request == before


def test_the_session_question_ends_an_idle_session(client, admin):
    sign_in(client)
    idle_out(admin)
    answer = client.get("/session", **SCRIPT)
    assert answer.status_code == 401 and answer.json()["why"] == "idle"


def test_sign_in_again_returns_the_same_person_to_the_page(client, admin):
    sign_in(client)
    idle_out(admin)
    client.get("/")  # the ending, which remembers who it was

    answer = sign_in(client, next="/upload?step=2")

    assert answer.status_code == 302
    assert answer["Location"] == "/upload?step=2"


def test_somebody_else_signing_in_lands_on_start(client, admin, db):
    User.objects.create_local_admin("other", PASSWORD)
    sign_in(client)
    idle_out(admin)
    client.get("/")

    answer = sign_in(client, username="other", next="/upload")

    assert answer["Location"] == "/start"


def test_a_next_outside_the_app_is_ignored(client, admin):
    sign_in(client)
    idle_out(admin)
    client.get("/")
    for wanted in ("https://elsewhere.example/x", "//elsewhere.example", "upload", ""):
        client.post("/sign-out")
        answer = sign_in(client, next=wanted)
        assert answer["Location"] == "/start", wanted


def test_a_fresh_sign_in_ignores_next(client, admin):
    assert sign_in(client, next="/upload")["Location"] == "/start"


# The gone page -----------------------------------------------------------------------


def test_the_gone_page_is_the_apps_own(client, admin, someone):
    settings_store.set_to("folder_management", True)
    sign_in(client)
    theirs = Case.objects.create(owner=someone, name="Theirs")

    answer = client.get(f"/case/{theirs.pk}/nothing-here")

    assert answer.status_code == 404
    assert "There is no page at this address." in answer.text
    assert "Gideon Transcribe" in answer.text  # the app's frame, not the server's
    # An Admin may see the case, so its name is the way back.
    assert "Back to the case Theirs" in answer.text
    assert 'href="/cases"' in answer.text
    assert 'href="/start"' in answer.text


def test_the_gone_page_never_says_whether_a_case_is_there(db, someone):
    settings_store.set_to("folder_management", True)
    theirs = Case.objects.create(owner=someone, name="Theirs")
    stranger = User.objects.from_directory("stranger", display_name="A Stranger")
    request = RequestFactory().get(f"/case/{theirs.pk}/nothing-here")
    request.user = stranger

    answer = views.gone(request)

    assert answer.status_code == 404
    assert "Theirs" not in answer.content.decode()
    assert "There is no page at this address." in answer.content.decode()


def test_the_gone_page_offers_my_recordings_for_a_recording_address(client, admin):
    sign_in(client)
    answer = client.get("/recording/00000000-0000-0000-0000-000000000000/no-such-thing")
    assert answer.status_code == 404
    assert "My recordings" in answer.text


def test_a_script_meeting_a_gone_address_keeps_json(client, admin):
    sign_in(client)
    answer = client.get(
        "/recording/00000000-0000-0000-0000-000000000000/no-such-thing", **SCRIPT
    )
    assert answer.status_code == 404
    assert answer.json() == {"error": "not found"}


def test_a_stranger_to_the_app_is_offered_sign_in(client, db):
    answer = client.get("/no-such-page")
    assert answer.status_code == 404
    assert 'href="/sign-in"' in answer.text


def test_the_failure_page_draws_in_the_frame(db):
    request = RequestFactory().get("/anything")
    request.user = AnonymousUser()
    answer = views.failed(request)
    assert answer.status_code == 500
    assert "Something went wrong on the server." in answer.content.decode()


def test_a_form_whose_token_no_longer_holds_gets_the_apps_page(db, admin):
    strict = Client(enforce_csrf_checks=True)
    answer = strict.post("/sign-in", {"username": "asker", "password": PASSWORD})
    assert answer.status_code == 403
    assert "The form was open too long" in answer.text
    assert (
        strict.post("/sign-in", {"username": "asker"}, **SCRIPT).json()["error"]
        == "the form was open too long"
    )


# The Admin pill ------------------------------------------------------------


def test_the_admin_band_is_a_pill_now():
    for name in ("viewer", "case", "recordings", "incident", "speakers-page"):
        text = (TEMPLATES / f"{name}.html").read_text(encoding="utf-8")
        assert 'include "admin-pill.html"' in text, name
        assert not re.search(r'class="banner"[^<]*as an Admin', text, re.S), name
    pill = (TEMPLATES / "admin-pill.html").read_text(encoding="utf-8")
    assert "recorded in the audit log" in pill
    assert "does not count as the owner having used the case" in pill


def test_the_body_says_admin_without_a_backslash():
    base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    assert 'data-admin="1"' in base
    assert 'data-admin=\\"1\\"' not in base


def test_the_pill_on_the_speakers_page_is_drawn_from_its_context():
    from inspect import getsource

    from core import speakers_page

    assert '"is_someone_elses"' in getsource(speakers_page.context)
