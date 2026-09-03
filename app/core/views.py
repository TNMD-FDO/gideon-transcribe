"""What the app answers."""

from __future__ import annotations

import logging

from django.db import connection
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from core import signin

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


def sign_in(request: HttpRequest) -> HttpResponse:
    """One form for everybody: directory users and Local admins alike."""
    if request.user.is_authenticated:
        return redirect(reverse("home"))

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
                return redirect(reverse("home"))
            except signin.Refused as refusal:
                problem = refusal.message

    return render(
        request,
        "sign-in.html",
        {"problem": problem, "username": username},
        status=400 if problem else 200,
    )


def sign_out(request: HttpRequest) -> HttpResponse:
    signin.sign_out(request)
    return redirect(reverse("sign-in"))
