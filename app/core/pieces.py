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


# The card budgets in GB (ADR 0015, docs/research/graphics-cards.md), the
# same four numbers `./transcribe` fits by; a test keeps the two the same
# (v1.92.0). Every figure is an estimate until an office measures its card.
TRANSCRIPTION_GB = 20
DIARIZER_GB = 4
ENGINE_GB = 20
FAST_LANE_GB = 8
LEAST_CARD_GB = 16


def card_memory_gb() -> int | None:
    """The transcription card's memory, as the install recorded it in .env;
    None on a server with no card or an install from before v1.92.0 that has
    not been upgraded since."""
    given = os.environ.get("CARD_MEMORY_GB", "").strip()
    try:
        gb = int(given)
    except ValueError:
        return None
    return gb if gb > 0 else None


def batch_size_for(gb: int) -> int:
    """The batch size the install sets by the card (the script's rule)."""
    if gb >= 32:
        return 16
    if gb >= 24:
        return 8
    if gb >= LEAST_CARD_GB:
        return 4
    return 0


def fitment(gb: int | None, *, engine_on_lan: bool = False) -> dict:
    """Where this server sits on the ladder (v1.92.0): what its card gives,
    the pieces that fit beside transcription, and what the next size up
    would open. In words for the Installation page and the Pieces card, and
    as segments for the page's bar, each a share of the card."""
    segments: list[dict] = []
    if gb is None:
        return {
            "gb": None,
            "batch": 0,
            "words": (
                "No card: cases, incidents, notes, clips and documents run, and "
                "recordings people upload wait for a card."
            ),
            "next": (
                "A card of 24 GB adds transcription for recordings up to about two "
                "hours, and one of 44 GB the AI assistant on the Local engine; an "
                "engine on the LAN adds the assistant without a card."
            ),
            "engine_room": False,
            "fast_lane_room": False,
            "segments": segments,
        }
    if gb < LEAST_CARD_GB:
        return {
            "gb": gb,
            "batch": 0,
            "words": (
                f"A {gb} GB card, under the {LEAST_CARD_GB} GB the service and the "
                "diarizer need: this server runs as one with no card."
            ),
            "next": (
                "A card of 24 GB adds transcription for recordings up to about two "
                "hours."
            ),
            "engine_room": False,
            "fast_lane_room": False,
            "segments": segments,
        }
    batch = batch_size_for(gb)
    used = TRANSCRIPTION_GB + DIARIZER_GB
    segments.append({"name": "Transcription", "gb": TRANSCRIPTION_GB, "kind": "t"})
    segments.append({"name": "Diarizer", "gb": DIARIZER_GB, "kind": "d"})
    engine_room = gb - used >= ENGINE_GB
    if engine_room and not engine_on_lan:
        segments.append({"name": "Local engine", "gb": ENGINE_GB, "kind": "e"})
        used += ENGINE_GB
    fast_lane_room = gb - used >= FAST_LANE_GB
    if fast_lane_room:
        segments.append({"name": "Fast lane", "gb": FAST_LANE_GB, "kind": "f"})
        used += FAST_LANE_GB
    if gb - used > 0:
        segments.append({"name": "Room", "gb": gb - used, "kind": "room"})
    for one in segments:
        one["share"] = round(one["gb"] / gb * 100, 1)
        # A label needs room; under this share the legend alone names it.
        one["narrow"] = one["share"] < 12
    reach = (
        "short recordings"
        if gb < 24
        else "recordings up to about two hours"
        if gb < 32
        else "the measured speed"
    )
    words = f"A {gb} GB card: transcription at batch size {batch}, {reach}."
    if engine_on_lan:
        words += " The AI assistant runs through the office's engine on the LAN."
    elif engine_room:
        words += (
            " Room for the Local engine beside it: the AI assistant, vision included."
        )
    steps = []
    if gb < 24:
        steps.append("24 GB opens recordings up to about two hours")
    elif gb < 32:
        steps.append("32 GB opens the measured speed")
    if not engine_room and not engine_on_lan:
        steps.append(
            f"the Local engine needs {TRANSCRIPTION_GB + DIARIZER_GB + ENGINE_GB} GB "
            "in all, or an engine on the LAN needs no card"
        )
    if not fast_lane_room:
        steps.append(f"the fast lane needs {FAST_LANE_GB} GB more")
    nxt = (
        ("Next: " + "; ".join(steps) + ".")
        if steps
        else (
            "Nothing left to open on this card; the directory, mail and the backup "
            "need no hardware."
        )
    )
    return {
        "gb": gb,
        "batch": batch,
        "words": words,
        "next": nxt,
        "engine_room": engine_room,
        "fast_lane_room": fast_lane_room,
        "segments": segments,
    }


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


def _engine_on_lan() -> bool:
    """A shared engine: an engine network that is not the Local engine's."""
    network = os.environ.get("LLM_NETWORK", "").strip()
    return bool(network) and network != "transcribe-llm"


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

    # What the card has room for, on the rows that are off (v1.92.0).
    fit = fitment(card_memory_gb(), engine_on_lan=_engine_on_lan())
    if not transcription_installed():
        rows.append(_row("fast-lane", NOT_INSTALLED, "needs transcription first"))
    elif not whisperx.fast_lane_configured():
        rows.append(
            _row(
                "fast-lane",
                OFF,
                "recordings made in the app wait their turn"
                + (
                    "; the card has room for it"
                    if fit["fast_lane_room"]
                    else f"; it needs {FAST_LANE_GB} GB more on the card"
                    if fit["gb"]
                    else ""
                ),
            )
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
        rows.append(
            _row(
                "engine",
                OFF,
                "no engine, so the AI assistant is off"
                + (
                    "; the card has room for the Local engine"
                    if fit["engine_room"]
                    else f"; the Local engine needs a card of "
                    f"{TRANSCRIPTION_GB + DIARIZER_GB + ENGINE_GB} GB, and an engine "
                    "the office runs on the LAN needs no card"
                ),
            )
        )
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
