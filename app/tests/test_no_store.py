"""What a browser may keep, and where a non-Admin lands (v1.93.1).

Every page and answer says private, no-store unless it set its own header;
a signed-in person who is not an Admin is sent from a Panel address to Home
with a word, not through the sign-in page.
"""

from __future__ import annotations

import pytest
from core.middleware import NO_STORE, NoStoreMiddleware
from core.models import LoginSession, User
from django.http import HttpResponse
from django.test import Client, RequestFactory


def signed_in(user) -> Client:
    """A client with the person signed in and their Login session begun."""
    client = Client()
    client.force_login(user, backend="django.contrib.auth.backends.ModelBackend")
    LoginSession.objects.create(
        user=user, session_key=client.session.session_key, address="127.0.0.1"
    )
    return client


@pytest.fixture
def colleague(db):
    return User.objects.from_directory("colleague", display_name="A Colleague")


@pytest.fixture
def admin(db):
    return User.objects.create_local_admin("asker", "a-long-enough-password")


def test_the_middleware_marks_an_answer_that_said_nothing():
    made = NoStoreMiddleware(lambda request: HttpResponse("a page"))
    answer = made(RequestFactory().get("/"))
    assert answer["Cache-Control"] == NO_STORE


def test_an_answer_that_set_its_own_header_keeps_it():
    def its_own(request):
        answer = HttpResponse(b"logo", content_type="image/png")
        answer["Cache-Control"] = "public, max-age=300"
        return answer

    answer = NoStoreMiddleware(its_own)(RequestFactory().get("/logo"))
    assert answer["Cache-Control"] == "public, max-age=300"


def test_home_and_the_working_pages_are_never_kept(colleague):
    client = signed_in(colleague)
    for url in ("/", "/recordings", "/help/"):
        answer = client.get(url, secure=True)
        assert answer.status_code == 200, url
        assert answer["Cache-Control"] == NO_STORE, url


def test_the_sign_in_page_is_never_kept_either(db):
    answer = Client().get("/sign-in", secure=True)
    assert answer.status_code == 200
    assert answer["Cache-Control"] == NO_STORE


def test_a_non_admin_at_a_panel_address_lands_on_home_with_a_word(colleague):
    client = signed_in(colleague)
    for url in ("/panel/", "/panel/status", "/panel/users"):
        answer = client.get(url, secure=True)
        assert answer.status_code == 302, url
        assert answer["Location"] == "/", url
    home = client.get("/", secure=True).content.decode()
    assert "That page is for Admins." in home


def test_an_admin_still_reaches_the_panel(admin):
    client = signed_in(admin)
    answer = client.get("/panel/status", secure=True)
    assert answer.status_code == 200
    assert answer["Cache-Control"] == NO_STORE
