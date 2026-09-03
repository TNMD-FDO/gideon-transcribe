"""The idle clock, and the rule that a person has one session at a time."""

from __future__ import annotations

import logging

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from core import settings_store
from core.models import LoginSession
from core.signin import SIGNED_IN_ELSEWHERE

log = logging.getLogger("transcribe.signin")

# Paths that do not belong to a person, so they neither need a session nor
# move anyone's idle clock.
NOT_A_PERSON = ("/healthz",)


class LoginSessionMiddleware:
    """Keeps the Login session in step with what the person is doing.

    Three things happen here on every request a signed-in person makes: the
    session is ended if it has sat idle for longer than the timeout, the person
    is told if they have signed in somewhere else since, and otherwise the idle
    clock is moved on.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in NOT_A_PERSON or not request.user.is_authenticated:
            return self.get_response(request)

        session = LoginSession.objects.filter(
            user=request.user,
            session_key=request.session.session_key or "",
            ended__isnull=True,
        ).first()

        if session is None:
            # The browser still has a cookie, but the Login session behind it
            # has ended. The commonest reason is a newer sign-in somewhere
            # else, and it is the only one worth naming to the person here.
            return self._end(request, SIGNED_IN_ELSEWHERE)

        if session.idle_for() > settings_store.idle_timeout():
            session.end(LoginSession.IDLE)
            log.info("%s was signed out after sitting idle", request.user.username)
            return self._end(request, "You were signed out after a long wait.")

        if not request.user.is_active:
            reason = (
                LoginSession.BLOCKED
                if request.user.blocked_at
                else LoginSession.DEACTIVATED
            )
            session.end(reason)
            return self._end(request, "This account cannot sign in. Contact IT.")

        # Only a person's own request moves their clock. An Admin looking at
        # somebody else's Workspace is not that person being here.
        session.last_request = timezone.now()
        session.save(update_fields=["last_request"])
        request.login_session = session

        return self.get_response(request)

    def _end(self, request, message: str):
        from django.contrib.auth import logout

        logout(request)
        messages.info(request, message)
        return redirect(reverse("sign-in"))
