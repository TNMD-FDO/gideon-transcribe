"""Ask the server for part of a recording, the way a browser jumping about does.

A browser plays a video from the start by asking for the whole file, and jumps
about in it by asking for a range of bytes out of the middle. A server that
answers the whole file to a request for a range plays the video perfectly and
cannot scrub it, which looks from the page like a broken page and is not one.

This asks both questions over the network, through Caddy, exactly as a browser
would: the same address, the same route, the same access check. It signs in as
the Recording's owner for the length of the test and signs out again, because
Caddy asks the app before it serves a byte and an unauthenticated request
would only ever be told no.

    docker compose run --rm app can_it_be_scrubbed 06-camera
"""

from __future__ import annotations

import os
import ssl
import urllib.error
import urllib.request

from django.contrib.sessions.backends.db import SessionStore
from django.core.management.base import BaseCommand

from core.models import LoginSession
from core.recordings import Recording

# Far enough in that no browser would have it already, and small enough that
# what comes back can be counted.
FROM_BYTE = 400_000_000
HOW_MANY = 100


def address_of(recording) -> str:
    # The port matters. The app is not on 443: another reverse proxy on the
    # server may already own that, and the address the office uses carries the
    # port. Asking 443 reaches whatever else is there, which is what happened
    # the first time this was run.
    host = os.environ.get("APP_HOSTNAME", "")
    port = os.environ.get("HTTPS_PORT", "8443")
    if port and port != "443":
        host = f"{host}:{port}"
    if recording.case_id:
        where = f"case-media/{recording.case_id}/{recording.pk}"
    else:
        where = f"media/{recording.user_id}/{recording.pk}"
    return f"https://{host}/{where}/playback.mp4"


def as_that_person(user) -> tuple[str, LoginSession]:
    """A Login session the test can use, made here and taken away after.

    The app owns its own sessions, so the check does not need anybody's
    password and never sees one. It is ended the moment the test is over.
    """
    store = SessionStore()
    store["_auth_user_id"] = str(user.pk)
    store["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
    store["_auth_user_hash"] = user.get_session_auth_hash()
    store.create()
    session = LoginSession.objects.create(user=user, session_key=store.session_key)
    return store.session_key, session


def ask(url: str, cookie: str, byte_range: str | None) -> dict:
    """One request, and what came back. The body is read but not kept."""
    request = urllib.request.Request(url)
    request.add_header("Cookie", f"sessionid={cookie}")
    if byte_range:
        request.add_header("Range", byte_range)

    # The office's own certificate authority. What is being checked here is
    # the range, not the trust, and the app is talking to itself.
    loose = ssl.create_default_context()
    loose.check_hostname = False
    loose.verify_mode = ssl.CERT_NONE

    try:
        with urllib.request.urlopen(request, timeout=30, context=loose) as answer:
            body = answer.read(HOW_MANY * 100)
            return {
                "status": answer.status,
                "length": answer.headers.get("Content-Length"),
                "range": answer.headers.get("Content-Range"),
                "accepts": answer.headers.get("Accept-Ranges"),
                "encoding": answer.headers.get("Content-Encoding"),
                "type": answer.headers.get("Content-Type"),
                "read": len(body),
            }
    except urllib.error.HTTPError as refused:
        return {"status": refused.code, "why": refused.reason}
    except Exception as trouble:  # noqa: BLE001 - anything here is the answer
        return {"status": None, "why": str(trouble)}


class Command(BaseCommand):
    help = "Ask the server for part of a recording, as a browser jumping about does."

    def add_arguments(self, parser):
        parser.add_argument("which", help="part of the Recording's title, or its id")

    def handle(self, *arguments, **options):
        which = options["which"]
        recording = (
            Recording.objects.filter(pk=which).first()
            if len(which) == 36
            else Recording.objects.filter(title__icontains=which)
            .order_by("-created")
            .first()
        )
        if recording is None:
            self.stderr.write(f"No recording whose title holds {which!r}.")
            return

        playback = recording.playback_path()
        if playback is None:
            self.stderr.write("That recording has no playback copy.")
            return

        url = address_of(recording)
        print(f"{recording.title}")
        print(f"  asking      {url}")
        print(f"  the file is {playback.stat().st_size} bytes on disk")

        if not os.environ.get("APP_HOSTNAME"):
            self.stderr.write("APP_HOSTNAME is not set, so there is no address to ask.")
            return

        cookie, session = as_that_person(recording.user)
        try:
            whole = ask(url, cookie, None)
            print("\nAsking for the whole file, as a browser does to start playing")
            for name, value in whole.items():
                print(f"  {name:<9} {value}")

            part = ask(url, cookie, f"bytes={FROM_BYTE}-{FROM_BYTE + HOW_MANY - 1}")
            print(
                f"\nAsking for {HOW_MANY} bytes from {FROM_BYTE}, "
                "as a browser does to jump"
            )
            for name, value in part.items():
                print(f"  {name:<9} {value}")
        finally:
            session.delete()
            SessionStore(session_key=cookie).delete()

        print("\nWhat that says")
        self.verdict(whole, part)

    def verdict(self, whole, part):
        if whole.get("status") != 200:
            print(
                f"  the whole file came back as {whole.get('status')}"
                f" ({whole.get('why', '')}), so nothing else here means anything"
            )
            return

        if whole.get("accepts") != "bytes":
            print(
                "  the server did not say it accepts ranges, so no browser will "
                "try to jump about in this"
            )

        if whole.get("encoding"):
            print(
                f"  the whole file came back {whole['encoding']}-encoded, which "
                "makes jumping about impossible whatever else is right"
            )

        if part.get("status") == 206:
            print(f"  ranges are served: {part.get('range')}")
            if part.get("read") == HOW_MANY:
                print("  -> the server does its part. A browser can jump about.")
            else:
                print(f"  -> but {part.get('read')} bytes came back, not {HOW_MANY}")
        elif part.get("status") == 200:
            print(
                "  -> asked for 100 bytes and got the whole file. This is why "
                "the video will not scrub: a browser cannot jump about when "
                "every request is answered from the beginning."
            )
        else:
            print(
                f"  -> the range was refused with {part.get('status')} "
                f"({part.get('why', '')})"
            )
