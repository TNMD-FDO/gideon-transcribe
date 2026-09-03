"""The health check, which is what everything else in the stack waits on."""

import pytest
from django.test import Client


@pytest.mark.django_db
def test_healthz_is_ok_when_the_database_answers():
    answer = Client().get("/healthz")
    assert answer.status_code == 200
    assert answer.content == b"ok\n"


@pytest.mark.django_db
def test_healthz_needs_no_sign_in():
    """Compose asks this question before anybody has signed in at all."""
    answer = Client().get("/healthz")
    assert answer.status_code == 200


def test_healthz_says_503_when_the_database_is_unreachable(monkeypatch):
    """An app that cannot reach its database is not ready to be given work.

    The compose file waits on this before it starts Caddy, the workers, and
    the upload sidecar, so it has to fail when the database is down rather
    than reporting that the web server is up, which nobody asked.
    """
    from django.db import connection

    def refuse():
        raise RuntimeError("the database is not there")

    monkeypatch.setattr(connection, "cursor", refuse)
    answer = Client().get("/healthz")
    assert answer.status_code == 503
