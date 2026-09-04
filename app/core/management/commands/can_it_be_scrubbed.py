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

import contextlib
import http.client
import os
import socket
import ssl

from django.contrib.sessions.backends.db import SessionStore
from django.core.management.base import BaseCommand

from core.models import LoginSession
from core.recordings import Recording

# Far enough in that no browser would have it already, and small enough that
# what comes back can be counted.
FROM_BYTE = 400_000_000
HOW_MANY = 100


def path_of(recording) -> str:
    """The route Caddy serves this Recording's playback copy from."""
    if recording.case_id:
        where = f"case-media/{recording.case_id}/{recording.pk}"
    else:
        where = f"media/{recording.user_id}/{recording.pk}"
    return f"/{where}/playback.mp4"


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


def ask(path: str, cookie: str, byte_range: str | None) -> dict:
    """One request to Caddy, and what came back. The body is read, not kept.

    Straight to the Caddy container over the network the two of them share,
    rather than out to the address the office uses and back in. The office's
    own firewall stands between a container and the host's published port,
    which is right, and it also means the app cannot ask itself a question
    that way.

    The name the office uses is still what is presented, in the TLS handshake
    and in the Host header, because that is what Caddy answers to.
    """
    host = os.environ.get("APP_HOSTNAME", "")

    # What is checked here is what Caddy does with a range, not whether this
    # certificate is trusted: the app is talking to the container beside it.
    loose = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    loose.check_hostname = False
    loose.verify_mode = ssl.CERT_NONE

    headers = {"Cookie": f"sessionid={cookie}", "Host": host}
    if byte_range:
        headers["Range"] = byte_range

    raw = None
    try:
        raw = socket.create_connection(("caddy", 443), timeout=30)
        secured = loose.wrap_socket(raw, server_hostname=host)
        talk = http.client.HTTPSConnection(host, 443, timeout=30, context=loose)
        talk.sock = secured
        talk.request("GET", path, headers=headers)
        answer = talk.getresponse()
        body = answer.read(HOW_MANY * 100)
        told = {
            "status": answer.status,
            "length": answer.getheader("Content-Length"),
            "range": answer.getheader("Content-Range"),
            "accepts": answer.getheader("Accept-Ranges"),
            "encoding": answer.getheader("Content-Encoding"),
            "type": answer.getheader("Content-Type"),
            "read": len(body),
        }
        talk.close()
        return told
    except Exception as trouble:  # noqa: BLE001 - anything here is the answer
        return {"status": None, "why": f"{type(trouble).__name__}: {trouble}"}
    finally:
        if raw is not None:
            with contextlib.suppress(OSError):
                raw.close()


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

        path = path_of(recording)
        host = os.environ.get("APP_HOSTNAME", "")
        print(f"{recording.title}")
        print(f"  asking      caddy:443 as {host}{path}")
        print(f"  the file is {playback.stat().st_size} bytes on disk")

        if not host:
            self.stderr.write("APP_HOSTNAME is not set, so there is no name to ask as.")
            return

        cookie, session = as_that_person(recording.user)
        try:
            whole = ask(path, cookie, None)
            print("\nAsking for the whole file, as a browser does to start playing")
            for name, value in whole.items():
                print(f"  {name:<9} {value}")

            part = ask(path, cookie, f"bytes={FROM_BYTE}-{FROM_BYTE + HOW_MANY - 1}")
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
        if whole.get("status") == 403:
            print(
                "  Caddy refused this as coming from outside the office's own "
                "networks, which is the client allow-list doing its job. The "
                "app's own container is not on one of them, so this check "
                "cannot run from here."
            )
            return

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
