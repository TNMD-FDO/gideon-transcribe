"""What the app answers."""

from __future__ import annotations

import logging

from django.db import connection
from django.http import HttpRequest, HttpResponse
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


def where_they_land() -> str:
    """The Cases page when Cases are on, and the Recordings page when they are not.

    Both pages carry a link to the other, so this decides only what opens
    first. Turning the setting off puts everybody back on the Phase 1 landing
    page at their next sign-in.
    """
    from core import cases

    return reverse("cases") if cases.folder_management_on() else reverse("home")


def sign_in(request: HttpRequest) -> HttpResponse:
    """One form for everybody: directory users and Local admins alike."""
    if request.user.is_authenticated:
        return redirect(where_they_land())

    problem = None
    username = ""

    if request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        if not password:
            # Refused by the form, before the directory is asked at all.
            problem = "Enter your password."
        else:
            try:
                signin.sign_in(request, username, password)
                return redirect(where_they_land())
            except signin.Refused as refusal:
                problem = refusal.message

    return render(
        request,
        "sign-in.html",
        {
            "problem": problem,
            "username": username,
            # An office's own line under the form: an authorised-use notice,
            # or where to ring for help. Empty hides it.
            "notice": settings_store.get("sign_in_notice"),
        },
        status=400 if problem else 200,
    )


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
