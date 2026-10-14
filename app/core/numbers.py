"""A number from a request, taken only when it is one (v1.132.0).

Python's float() accepts "nan" and "inf", PostgreSQL stores them, and a JSON
answer then carries bare NaN, which no browser can parse: one such number
posted as a camera's start had broken the incident page for everyone. Every
view that takes a number from a request takes it through here.
"""

from __future__ import annotations

import math

# A day and a bit: longer than any recording the app accepts, and long
# enough for an incident's clock to reach past midnight.
A_DAY_AND_MORE = 26 * 3600.0


def finite(value, *, least: float | None = None, most: float | None = None):
    """The value as a float, or None when it is not a finite number within
    the range given."""
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    if least is not None and number < least:
        return None
    if most is not None and number > most:
        return None
    return number
