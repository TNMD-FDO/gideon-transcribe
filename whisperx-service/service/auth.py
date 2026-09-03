"""Who is calling: the tokens file, read again whenever it changes.

A token is compared in constant time and never written to a log. Adding a
Consumer is a line in a file, which the service picks up on its own, so nobody
has to restart a service to let a new application in.
"""

from __future__ import annotations

import hmac
from pathlib import Path

from service.tokens import Consumer, parse_file


class Tokens:
    """The tokens file, kept in step with what is on disk."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._consumers: list[Consumer] = []
        self._read_at: float | None = None

    def _reload_if_changed(self) -> None:
        try:
            changed_at = self.path.stat().st_mtime
        except OSError:
            # No file at all means no Consumer may call, which is the safe way
            # for this to fail.
            self._consumers = []
            self._read_at = None
            return

        if self._read_at == changed_at:
            return

        try:
            self._consumers = parse_file(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # A file somebody is part way through editing should not lock every
            # Consumer out, so the last good reading stands until it parses.
            return
        self._read_at = changed_at

    def consumer_for(self, token: str | None) -> Consumer | None:
        """The Consumer that holds this token, or None.

        Every line is compared even after a match, so that the time this takes
        says nothing about which token was right or how much of it was.
        """
        self._reload_if_changed()
        if not token:
            return None

        found: Consumer | None = None
        for consumer in self._consumers:
            if hmac.compare_digest(consumer.token, token):
                found = consumer
        return found

    def names(self) -> list[str]:
        """The Consumer names, for the status page. Never the tokens."""
        self._reload_if_changed()
        return [consumer.name for consumer in self._consumers]


def bearer(header: str | None) -> str | None:
    """The token out of an Authorization header, or None."""
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None
