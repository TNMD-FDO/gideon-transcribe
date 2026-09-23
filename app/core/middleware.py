"""The idle clock, and the rule that a person has one session at a time."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from core import audit, settings_store
from core.models import LoginSession
from core.signin import SIGNED_IN_ELSEWHERE

log = logging.getLogger("transcribe.signin")

# Paths that do not belong to a person, so they neither need a session nor
# move anyone's idle clock.
NOT_A_PERSON = ("/healthz",)

# Paths a signed-in person's page asks about the session itself (Phase 8
# chapter 7): they are checked like any other, so an idle session ends on
# the question, but a question about the clock never moves the clock.
NOT_MOVING = ("/session",)

# How a page's script marks its request, so the app answers it plainly
# rather than with the sign-in page (Phase 8 chapter 7). session.js sets
# it on every same-origin fetch; nothing a browser does by itself sends it.
SCRIPT_HEADER = "X-Requested-With"
SCRIPT_VALUE = "transcribe"

# What the script is told, by the session's end reason: the same causes the
# audit row records, in the words the page's line is composed from.
ENDED_BY_ADMIN = "An Admin ended your session."
CANNOT_SIGN_IN = "This account cannot sign in. Contact IT."

# How stale the idle clock may get before it is written again. The clock's own
# timeout is hours, so a clock that is up to a minute behind ends a session at
# the same minute it would have anyway.
#
# It is throttled because of what a browser does with a video. Every range of
# bytes it asks for is a question to this app, and a person jumping about in a
# recording asks several at once; without this, each one wrote a row to the
# database before a single byte was served.
CLOCK_STEP = timedelta(minutes=1)


def from_a_script(request) -> bool:
    """Whether a page's script asked, rather than the browser following a link."""
    return request.headers.get(SCRIPT_HEADER) == SCRIPT_VALUE


def _why_it_ended(request) -> str:
    """The cause a script is told when the cookie outlived the Login session.

    The commonest is a newer sign-in somewhere else; an Admin's End sessions
    is the other that is worth naming. Anything else reads as gone.
    """
    last = (
        LoginSession.objects.filter(
            user=request.user,
            session_key=request.session.session_key or "",
            ended__isnull=False,
        )
        .order_by("-ended")
        .first()
    )
    if last is None:
        return "gone"
    if last.end_reason == LoginSession.ADMIN_ENDED:
        return "ended"
    if last.end_reason == LoginSession.ELSEWHERE:
        return "elsewhere"
    return "gone"


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
        if request.path in NOT_A_PERSON:
            return self.get_response(request)

        if not request.user.is_authenticated:
            # No session at all. A page's script that asks anyway (a page
            # left open after its session ended, or opened from an old tab)
            # is told so plainly, where the browser would be sent to Sign in.
            response = self.get_response(request)
            if (
                from_a_script(request)
                and response.status_code in (301, 302)
                and response["Location"].startswith(reverse("sign-in"))
            ):
                return self._ended_json("gone")
            return response

        session = LoginSession.objects.filter(
            user=request.user,
            session_key=request.session.session_key or "",
            ended__isnull=True,
        ).first()

        if session is None:
            # The browser still has a cookie, but the Login session behind it
            # has ended. The commonest reason is a newer sign-in somewhere
            # else, and it is the only one worth naming to the person here.
            why = _why_it_ended(request)
            message = ENDED_BY_ADMIN if why == "ended" else SIGNED_IN_ELSEWHERE
            return self._end(request, message, why)

        if session.idle_for() > settings_store.idle_timeout():
            session.end(LoginSession.IDLE)
            audit.write(
                audit.Category.SIGN_IN,
                "sign-out",
                system="sweeper",
                affected_user=request.user,
                login_session=session,
                cause=LoginSession.IDLE,
            )
            log.info("%s was signed out after sitting idle", request.user.username)
            return self._end(request, "You were signed out after a long wait.", "idle")

        if not request.user.is_active:
            reason = (
                LoginSession.BLOCKED
                if request.user.blocked_at
                else LoginSession.DEACTIVATED
            )
            session.end(reason)
            audit.write(
                audit.Category.SIGN_IN,
                "sign-out",
                system="sweeper",
                affected_user=request.user,
                login_session=session,
                cause=reason,
            )
            return self._end(request, CANNOT_SIGN_IN, reason)

        # Only a person's own request moves their clock. An Admin looking at
        # somebody else's Workspace is not that person being here.
        now = timezone.now()
        if request.path not in NOT_MOVING and now - session.last_request >= CLOCK_STEP:
            session.last_request = now
            session.save(update_fields=["last_request"])
        request.login_session = session

        return self.get_response(request)

    def _end(self, request, message: str, why: str):
        from django.contrib.auth import logout

        username = request.user.username
        logout(request)
        # Who it was, kept in the fresh anonymous session so that Sign in
        # again returns the same person to the page and nobody else.
        request.session["ended_user"] = username
        if from_a_script(request):
            return self._ended_json(why)
        messages.info(request, message)
        return redirect(reverse("sign-in"))

    @staticmethod
    def _ended_json(why: str):
        """What a page's script is told: the cause, and whether things stay."""
        return JsonResponse(
            {
                "signed_in": False,
                "why": why,
                "kept": bool(settings_store.get("folder_management")),
            },
            status=401,
        )
