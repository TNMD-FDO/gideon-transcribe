"""Consumer tokens: the file, its lines, and how a new one is made.

A token is what makes an application a Consumer of this service. The file holds
one Consumer per line, and the service reloads it when it changes, so adding a
Consumer never means restarting anything.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

# 64 hexadecimal characters, which is 32 bytes of randomness.
TOKEN_BYTES = 32

# The width the name is padded to, so that a person reading the file sees
# columns.
NAME_COLUMN = 16


@dataclass(frozen=True)
class Consumer:
    """One line of the tokens file."""

    name: str
    token: str
    admin: bool = False


def new_token() -> str:
    """A fresh token: 64 hexadecimal characters."""
    return secrets.token_hex(TOKEN_BYTES)


def format_line(consumer: Consumer) -> str:
    """The line to put in the tokens file for this Consumer."""
    line = f"{consumer.name:<{NAME_COLUMN}}{consumer.token}"
    if consumer.admin:
        line += "  admin"
    return line


def parse_line(line: str) -> Consumer | None:
    """One line of the tokens file, or None for a blank line or a comment."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    parts = stripped.split()
    if len(parts) < 2:
        raise ValueError(f"a line with no token: {stripped!r}")

    name, token, *rest = parts
    admin = "admin" in rest
    unknown = [word for word in rest if word != "admin"]
    if unknown:
        raise ValueError(f"unknown word on a token line: {unknown[0]!r}")

    return Consumer(name=name, token=token, admin=admin)


def parse_file(text: str) -> list[Consumer]:
    """Every Consumer in the tokens file, in the order they appear.

    A duplicated name or a duplicated token is refused: both mean somebody
    edited the file by hand and lost track, and a duplicate token would make
    two Consumers indistinguishable.
    """
    consumers: list[Consumer] = []
    for number, line in enumerate(text.splitlines(), start=1):
        try:
            consumer = parse_line(line)
        except ValueError as exc:
            raise ValueError(f"line {number}: {exc}") from None
        if consumer is None:
            continue
        if any(other.name == consumer.name for other in consumers):
            raise ValueError(f"line {number}: the name {consumer.name!r} is used twice")
        if any(other.token == consumer.token for other in consumers):
            raise ValueError(f"line {number}: the same token is used twice")
        consumers.append(consumer)
    return consumers
