"""Signing in and out, and what keeps a Login session alive.

Directory sign-in over LDAPS is its own piece of work and is not here yet. Until
it is, a username that is not a Local admin is told what a directory user is
told when the directory cannot be reached, which is the truth: there is no
directory connection.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.utils import timezone

from core import settings_store
from core.models import LoginSession, SignInAttempt, User, normalise_username

log = logging.getLogger("transcribe.signin")

DIRECTORY_UNAVAILABLE = (
    "Sign-in is unavailable because the office directory cannot be reached. Contact IT."
)
WRONG = "That username and password do not match."
NOT_ALLOWED = "This account cannot sign in. Contact IT."
SIGNED_IN_ELSEWHERE = "You signed in from another place; this session has ended"


class Refused(Exception):
    """A sign-in that will not happen, with the words to say so."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def address_of(request) -> str | None:
    """The client's address, from the app's own Caddy and nowhere else.

    Caddy is the only thing that talks to the app, so its forwarded-for header
    is the one source. Trusting the header on its own would let a client name
    its own address, which is why nothing else is consulted and why the app
    publishes no port of its own.
    """
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def sign_in(request, typed_username: str, password: str) -> User:
    """Check who this is, or refuse with a reason a person can act on."""
    username = normalise_username(typed_username)
    address = address_of(request)

    if not username or not password:
        raise Refused(WRONG)

    waiting = SignInAttempt.wait_for(username, address)
    if waiting is not None:
        minutes = max(1, round(waiting.total_seconds() / 60))
        raise Refused(
            f"Too many attempts. Try again in {minutes} minute"
            f"{'s' if minutes != 1 else ''}."
        )

    user = User.objects.filter(username=username, is_local=True).first()
    if user is None:
        # Not a Local admin, so this is a directory account. Asking the
        # directory is the next piece of work; until it exists, there is no
        # directory connection, and that is what the person is told. The same
        # words serve when the directory is configured and unreachable, which
        # is why they say what is true rather than what went wrong.
        raise Refused(DIRECTORY_UNAVAILABLE)

    if not user.check_password(password):
        SignInAttempt.record(username, address)
        log.info("sign-in refused for a local account: wrong password")
        raise Refused(WRONG)

    if not user.is_active:
        log.info("sign-in refused for a local account: %s", user.status)
        raise Refused(NOT_ALLOWED)

    begin_session(request, user, address)
    return user


def begin_session(request, user: User, address: str | None) -> LoginSession:
    """Start this person's session, ending the one they had elsewhere.

    A person has one Login session at a time and the newest wins. Nothing in
    the Workspace is lost by the switch: it belongs to the user, not to the
    session, so a Batch that is running carries on.
    """
    for older in LoginSession.objects.filter(user=user, ended__isnull=True):
        older.end(LoginSession.ELSEWHERE)

    django_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    user.last_sign_in = timezone.now()
    user.save(update_fields=["last_sign_in"])

    SignInAttempt.objects.filter(username=user.username).delete()
    log.info("%s signed in", user.username)

    return LoginSession.objects.create(
        user=user,
        session_key=request.session.session_key or "",
        address=address,
    )


def sign_out(request, reason: str = LoginSession.LOGOUT) -> None:
    session = current_session(request)
    if session is not None:
        session.end(reason)
        log.info("%s signed out (%s)", session.user.username, reason)
    django_logout(request)


def current_session(request) -> LoginSession | None:
    if not request.user.is_authenticated:
        return None
    return LoginSession.objects.filter(
        user=request.user,
        session_key=request.session.session_key or "",
        ended__isnull=True,
    ).first()


def warning_due(session: LoginSession) -> bool:
    """Whether this session is inside the last fifteen minutes of its patience."""
    left = settings_store.idle_timeout() - session.idle_for()
    return timedelta() < left <= timedelta(minutes=15)
