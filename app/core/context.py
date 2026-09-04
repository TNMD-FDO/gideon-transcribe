"""What every page is given without asking for it."""

from __future__ import annotations

from core import settings_store


def workspace(request) -> dict:
    """The idle timeout, which the countdown on every page is worked out from.

    The clock moves on every request a person makes, so the time left at the
    moment a page loads is the whole timeout. The browser counts down from
    there and warns fifteen minutes before the end, rather than the server
    telling a page something it can only tell it once.
    """
    if not request.user.is_authenticated:
        return {}
    return {
        "idle_timeout_seconds": int(settings_store.idle_timeout().total_seconds()),
        # Off hides the Clips page and every way to reach it.
        "clips_available": settings_store.get("clips_available"),
    }
