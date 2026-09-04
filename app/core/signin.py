"""Signing in and out, and what keeps a Login session alive.

A username that matches a Local admin is checked here, against the password
this app holds. Anything else is a directory account and goes to the office
directory (see core.directory). Nobody else can sign in: there is no
self-signup and no local account that is not an Admin.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.utils import timezone

from core import audit, directory, settings_store
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
        audit.sign_in_failed(username, audit.Reason.THROTTLED, request)
        minutes = max(1, round(waiting.total_seconds() / 60))
        raise Refused(
            f"Too many attempts. Try again in {minutes} minute"
            f"{'s' if minutes != 1 else ''}."
        )

    user = User.objects.filter(username=username, is_local=True).first()
    if user is None:
        user = _from_the_directory(request, username, password, address)
        session = begin_session(request, user, address)
        audit.write(
            audit.Category.SIGN_IN,
            "sign-in succeeded",
            actor=user,
            request=request,
            login_session=session,
            source="directory",
        )
        return user

    if not user.check_password(password):
        SignInAttempt.record(username, address)
        audit.sign_in_failed(username, audit.Reason.WRONG_PASSWORD, request, actor=user)
        log.info("sign-in refused for a local account: wrong password")
        raise Refused(WRONG)

    if not user.is_active:
        reason = audit.Reason.BLOCKED if user.blocked_at else audit.Reason.DEACTIVATED
        audit.sign_in_failed(username, reason, request, actor=user)
        log.info("sign-in refused for a local account: %s", user.status)
        raise Refused(NOT_ALLOWED)

    session = begin_session(request, user, address)
    audit.write(
        audit.Category.SIGN_IN,
        "sign-in succeeded",
        actor=user,
        request=request,
        login_session=session,
        source="local" if user.is_local else "directory",
    )
    return user


def _from_the_directory(request, username: str, password: str, address) -> User:
    """Ask the directory, and make or update the account it describes.

    An account is made at the first successful sign-in and never before, so
    nobody pre-provisions users and nothing here changes when the office adds
    somebody to the Sign-in group.
    """
    if not directory.is_on():
        audit.sign_in_failed(username, audit.Reason.DIRECTORY_UNREACHABLE, request)
        raise Refused(DIRECTORY_UNAVAILABLE)

    try:
        answer = directory.sign_in(username, password)
    except directory.Unreachable as problem:
        log.warning("the directory could not be reached: %s", problem)
        audit.sign_in_failed(username, audit.Reason.DIRECTORY_UNREACHABLE, request)
        raise Refused(DIRECTORY_UNAVAILABLE) from problem

    known = User.objects.filter(username=username).first()

    if not answer["ok"]:
        why = answer["why"]
        if why == "wrong_password":
            SignInAttempt.record(username, address)
            audit.sign_in_failed(
                username, audit.Reason.WRONG_PASSWORD, request, actor=known
            )
            raise Refused(WRONG)
        if why == "not_in_a_group":
            audit.sign_in_failed(
                username, audit.Reason.NOT_IN_A_GROUP, request, actor=known
            )
            raise Refused(NOT_ALLOWED)
        if why in ("disabled", "no_such_account"):
            audit.sign_in_failed(
                username, audit.Reason.DEACTIVATED, request, actor=known
            )
            raise Refused(NOT_ALLOWED)
        audit.sign_in_failed(username, audit.Reason.WRONG_PASSWORD, request)
        raise Refused(WRONG)

    # An Admin's Block is the app's own and the directory never lifts it.
    if known is not None and known.blocked_at is not None:
        audit.sign_in_failed(username, audit.Reason.BLOCKED, request, actor=known)
        raise Refused(NOT_ALLOWED)

    user = User.objects.from_directory(
        answer["username"],
        directory_address=answer["directory_address"],
        display_name=answer["display_name"],
        email=answer["email"],
        in_admin_group=answer["in_admin_group"],
        # The directory admits them, so a deactivation the check made is
        # lifted here rather than waiting for the night.
        deactivated_at=None,
    )
    return user


def begin_session(request, user: User, address: str | None) -> LoginSession:
    """Start this person's session, ending the one they had elsewhere.

    A person has one Login session at a time and the newest wins. Nothing in
    the Workspace is lost by the switch: it belongs to the user, not to the
    session, so a Batch that is running carries on.
    """
    for older in LoginSession.objects.filter(user=user, ended__isnull=True):
        older.end(LoginSession.ELSEWHERE)
        audit.write(
            audit.Category.SIGN_IN,
            "sign-out",
            actor=user,
            login_session=older,
            cause=LoginSession.ELSEWHERE,
        )

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
        audit.write(
            audit.Category.SIGN_IN,
            "sign-out",
            actor=session.user,
            request=request,
            login_session=session,
            cause=reason,
        )
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
