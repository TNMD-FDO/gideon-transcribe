"""The Pieces of an installation (v1.83.0).

A Piece is one optional part of an installation an office adds when it has
what the part needs: Transcription (a card), the Fast lane, an Engine (Local
or Shared), the Directory, Mail, the Backup. This module says which are on,
off, not installed or not answering, for the Status page's Pieces card and
for the pages that must cope with a piece being absent. It never runs
anything: the app is not given the Docker socket (ADR 0009), so each row
carries the one command IT runs on the server to add the piece.

What it reads: the environment Compose passes the app (`COMPOSE_PROFILES`,
the same list `./transcribe` keeps in `.env`), the app's settings, and the
services that answer on the network.
"""

from __future__ import annotations

import os

from django.conf import settings as django_settings

# The pieces, in the order the Status page and `./transcribe pieces` list
# them; a test keeps this list and the script's `add` dispatch the same.
PIECES = ("transcription", "fast-lane", "engine", "directory", "mail", "backup")

TITLES = {
    "transcription": "Transcription",
    "fast-lane": "Fast lane",
    "engine": "Engine",
    "directory": "Directory",
    "mail": "Mail",
    "backup": "Backup",
}

# The states a row may be in.
ON = "on"
OFF = "off"
NOT_INSTALLED = "not installed"
NOT_ANSWERING = "not answering"


def profiles() -> set[str]:
    """The Compose profiles in force, from the list Compose passes."""
    given = os.environ.get("COMPOSE_PROFILES", "")
    return {one.strip() for one in given.split(",") if one.strip()}


def transcription_installed() -> bool:
    """Whether the transcription piece is part of this installation.

    The piece is the `transcription` Compose profile, which the install
    writes when the office names a card and `./transcribe add transcription`
    writes later. A process that is not given the list at all (the test
    suite, a management command run outside Compose) is read as having the
    piece, since every installation before v1.83.0 had it.
    """
    if "COMPOSE_PROFILES" not in os.environ:
        return True
    return "transcription" in profiles()


def command(piece: str) -> str:
    return f"./transcribe add {piece}"


def _row(piece: str, state: str, says: str) -> dict:
    return {
        "name": piece,
        "title": TITLES[piece],
        "state": state,
        "says": says,
        # What IT runs on the server; the page never runs it.
        "command": command(piece),
    }


def listed() -> list[dict]:
    """One row per Piece, for the Status page and for `./transcribe pieces`."""
    from core import backups, engine, mail, whisperx

    rows = []

    if not transcription_installed():
        rows.append(
            _row(
                "transcription",
                NOT_INSTALLED,
                "no card yet; recordings uploaded wait for it",
            )
        )
    elif whisperx.is_alive():
        rows.append(_row("transcription", ON, "the service answers"))
    else:
        rows.append(
            _row(
                "transcription",
                NOT_ANSWERING,
                "installed, but the service does not answer; "
                "./transcribe logs whisperx",
            )
        )

    if not transcription_installed():
        rows.append(_row("fast-lane", NOT_INSTALLED, "needs transcription first"))
    elif not whisperx.fast_lane_configured():
        rows.append(
            _row("fast-lane", OFF, "recordings made in the app wait their turn")
        )
    elif whisperx.is_alive(whisperx.FAST):
        rows.append(_row("fast-lane", ON, "the lane answers"))
    else:
        rows.append(
            _row(
                "fast-lane",
                NOT_ANSWERING,
                "on, but the lane does not answer; ./transcribe logs whisperx-fast",
            )
        )

    if not engine.configured():
        rows.append(_row("engine", OFF, "no engine, so the AI assistant is off"))
    else:
        kind = "the Local engine" if "llm" in profiles() else "a shared engine"
        told = engine.status_for_the_panel()
        if told["state"] in ("reachable", "unknown"):
            rows.append(_row("engine", ON, f"{kind}; {told['says']}"))
        else:
            rows.append(_row("engine", NOT_ANSWERING, f"{kind}; {told['says']}"))

    if django_settings.LDAP_ENABLED:
        rows.append(_row("directory", ON, "sign-in is against the directory"))
    else:
        rows.append(_row("directory", OFF, "local admins only"))

    if mail.configured():
        rows.append(_row("mail", ON, "a relay and a sender are named"))
    else:
        rows.append(_row("mail", OFF, "no relay, so nothing is sent"))

    if backups.is_on():
        rows.append(_row("backup", ON, "a backup target is named"))
    else:
        rows.append(_row("backup", OFF, "no target, so nothing is backed up"))

    return rows


# The words the pages use when the transcription piece is absent.
WAITING = "Waiting for the card"
NOT_INSTALLED_NOTICE = (
    "Transcription is not installed on this server yet. Recordings you upload "
    "are kept and transcribed when the card arrives."
)
NEEDS_THE_PIECE = (
    "Recording needs the transcription piece, which is not installed on this "
    "server yet. Ask IT."
)
