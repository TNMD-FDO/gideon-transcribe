"""What the app answers."""

from __future__ import annotations

import logging
import re

from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseServerError,
    JsonResponse,
)
from django.shortcuts import redirect, render
from django.urls import reverse

from core import lifecycle, settings_store, signin

log = logging.getLogger("transcribe.health")


def healthz(request: HttpRequest) -> HttpResponse:
    """Alive, and able to reach the database.

    The compose file waits on this before it starts Caddy, the workers, and
    the upload sidecar, so it has to mean what it says: an app that cannot
    reach its database is not ready to be given work, whatever else is true
    of it. It takes no token, because a health check is not a secret, and it
    says nothing about what is inside.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        log.exception("the database could not be reached")
        return HttpResponse("the database cannot be reached\n", status=503)

    return HttpResponse("ok\n", content_type="text/plain")


def where_they_land(user=None) -> str:
    """The Start page, whoever it is and whatever the settings say.

    It asks one question, what do you want to do, and offers Upload files,
    Record now, and Open a case; the top bar has the rest. Before it, the
    landing was the Upload page, for the reasons below, which still hold:
    the Start page is the Upload door and the others in one place.

    The specification lands people on Cases when Folder management is on. It
    is right for the office that works in Cases and wrong for the one that
    does not: an office's larger use is batches of recordings that belong to
    no Case, so those people arrived every morning on a page about a feature
    they never open. Landing on Upload is right for both, because it is what
    everybody came to do, and Cases and Recordings are one click away in the
    navigation.

    The argument is kept because the callers pass it and a future rule may
    want it.
    """
    return reverse("start")


def logo(request: HttpRequest) -> HttpResponse:
    """The office logo, served to the sign-in page and the nav; 404 while none."""
    from core import branding

    found = branding.current()
    if found is None:
        return HttpResponse(status=404)
    if request.headers.get("If-None-Match") == found.etag:
        return HttpResponse(status=304)
    answer = HttpResponse(bytes(found.logo), content_type=found.content_type)
    answer["ETag"] = found.etag
    answer["Cache-Control"] = "public, max-age=300"
    return answer


def sign_in(request: HttpRequest) -> HttpResponse:
    """One form for everybody: directory users and Local admins alike."""
    if request.user.is_authenticated:
        return redirect(where_they_land(request.user))

    problem = None
    username = ""
    # Where to return to (Phase 8 chapter 7): the page a session ended
    # under, carried by Sign in again. Honoured for a path inside the app
    # and for the same person alone; anybody else lands on Start.
    wanted = request.POST.get("next") or request.GET.get("next") or ""
    if not _inside(wanted):
        wanted = ""

    if request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        if not password:
            # Refused by the form, before the directory is asked at all.
            problem = "Enter your password."
        else:
            ended_user = request.session.get("ended_user", "")
            try:
                user = signin.sign_in(request, username, password)
            except signin.Refused as refusal:
                problem = refusal.message
            else:
                request.session.pop("ended_user", None)
                if wanted and ended_user and ended_user == user.username:
                    return redirect(wanted)
                return redirect(where_they_land(request.user))

    return render(
        request,
        "sign-in.html",
        {
            "problem": problem,
            "username": username,
            "next": wanted,
            # An office's own line under the form: an authorised-use notice,
            # or where to ring for help. Empty hides it.
            "notice": settings_store.get("sign_in_notice"),
            **_face(),
        },
        status=400 if problem else 200,
    )


def _inside(path: str) -> bool:
    """A path inside the app: one leading slash, no host, nothing odd."""
    return bool(
        path
        and path.startswith("/")
        and not path.startswith("//")
        and "\\" not in path
        and not any(one.isspace() for one in path)
    )


@login_required
def session_state(request: HttpRequest) -> HttpResponse:
    """Whether the session is open and how long it has left, asked by the
    idle warning at nought (Phase 8 chapter 7). The middleware checks the
    session on the way in and does not move the clock for this path, so a
    session that has ended answers 401 and an open one its time left."""
    session = getattr(request, "login_session", None)
    left = 0
    if session is not None:
        left = int((settings_store.idle_timeout() - session.idle_for()).total_seconds())
    return JsonResponse({"signed_in": True, "left": max(left, 0)})


# The pages that fail well (Phase 8 chapter 7) ---------------------------------

CASE_IN_PATH = re.compile(r"^/case/([0-9a-fA-F-]{36})(?:/|$)")


def gone(request: HttpRequest, exception=None) -> HttpResponse:
    """The gone page: the app's own frame for an address with nothing behind
    it, the reasons it might be gone and the way back. The case's name is
    shown only for a case this person may see, so the page never says
    whether a case is there; a script's request keeps a JSON answer."""
    from core import cases as case_rules
    from core.middleware import from_a_script

    if from_a_script(request):
        return JsonResponse({"error": "not found"}, status=404)

    case = None
    ways = []
    user = request.user
    path = request.path
    if user.is_authenticated:
        cases_on = case_rules.folder_management_on()
        found = CASE_IN_PATH.match(path)
        if found and cases_on:
            from core.cases import Case

            try:
                candidate = Case.objects.filter(
                    pk=found.group(1), deleted_on__isnull=True
                ).first()
            except Exception:
                candidate = None
            if candidate is not None and candidate.role_of(user):
                case = candidate
        if path.startswith("/case") and cases_on:
            ways.append({"name": "Cases", "href": reverse("cases")})
        elif path.startswith("/recording"):
            ways.append({"name": "My recordings", "href": reverse("home")})
        elif path.startswith("/panel") and getattr(user, "is_admin", False):
            ways.append({"name": "The Panel", "href": reverse("panel")})
        ways.append({"name": "Start", "href": reverse("start")})
    else:
        ways.append({"name": "Sign in", "href": reverse("sign-in")})
    return render(request, "404.html", {"case": case, "ways": ways}, status=404)


def failed(request: HttpRequest) -> HttpResponse:
    """The server's own failure, in the app's frame; plain text if even the
    frame cannot be drawn."""
    try:
        return render(request, "500.html", status=500)
    except Exception:
        log.exception("the failure page could not be drawn")
        return HttpResponseServerError(
            "Something went wrong on the server. It has been logged; "
            "try again in a moment.\n",
            content_type="text/plain",
        )


def form_refused(request: HttpRequest, reason: str = "") -> HttpResponse:
    """A form sent with a token that no longer holds: after the session
    ended, or after a sign-in in another tab."""
    from core.middleware import from_a_script

    if from_a_script(request):
        return JsonResponse({"error": "the form was open too long"}, status=403)
    return render(request, "403-form.html", status=403)


def _face() -> dict:
    """The office's logo and name for the sign-in page; the app's own when none."""
    from core import branding

    return {
        "has_logo": branding.current() is not None,
        "office_name": branding.office_name(),
    }


def _still_movable(user) -> list:
    """Done Recordings not yet in a Case.

    Only a Done one is offered: a Queued, Running or Failed Recording cannot
    be moved, because a move renames the folder its Job is writing into.
    """
    from core import cases

    if not cases.folder_management_on():
        return []
    return [
        one
        for one in lifecycle.in_the_workspace(user).order_by("-created")
        if hasattr(one, "transcript")
    ]


def sign_out(request: HttpRequest) -> HttpResponse:
    """Say what signing out removes, and offer the two downloads first.

    Signing out is the moment everything goes, so it asks rather than acts:
    the page names the counts, offers the downloads, and only the button
    signs the person out.
    """
    if request.method != "POST":
        return render(
            request,
            "sign-out.html",
            {
                "lines": lifecycle.sign_out_lines(request.user),
                "counts": lifecycle.counts(request.user),
                # The Done Recordings still in the Workspace, so that the last
                # page a person sees offers to keep them rather than only to
                # download them.
                "movable": _still_movable(request.user),
            },
        )

    signin.sign_out(request)
    return redirect(reverse("sign-in"))
