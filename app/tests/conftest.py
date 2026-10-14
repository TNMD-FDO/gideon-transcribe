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


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings):
    """A fresh App data folder for each test.

    The database rolls back at the end of a test and the disk does not, so
    without this the folders one test writes are still there for the next
    one, and a sweeper counting orphans counts everybody's. Forty-seven test
    files carried their own copy before v1.133.0; the few that also stub the
    free-disk reading keep a local one, which overrides this by its name.
    """
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"
    (tmp_path / "uploads").mkdir()
    return tmp_path
