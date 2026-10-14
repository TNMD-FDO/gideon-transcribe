"""Fixtures for every test.

The one here makes a deferral that waits for the transaction's commit run at
once (core.deferring, v1.131.0): a test runs inside a transaction that never
commits, so a deferral that waited would never fire, and the tests that watch
a task being queued would see nothing.
"""

from __future__ import annotations

import pytest
from core import deferring


@pytest.fixture(autouse=True)
def deferrals_run_at_once(monkeypatch):
    monkeypatch.setattr(deferring, "after_commit", lambda deferral: deferral())
