"""The three columns from 2200 wide (Phase 13 chapter 2, release 4,
v1.224.0; the drawing phase-13-recording-page.html, figure 4): the case
column at the left, the words in the middle, the stage at the right with
its grip on the left edge."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from core import settings_store
from core.cases import Case
from core.jobs import Transcript
from core.models import User
from core.recordings import Batch, MediaState, Recording
from tests.helpers import signed_in

APP = Path(__file__).resolve().parent.parent
PAGE = (APP / "templates" / "viewer.html").read_text(encoding="utf-8")
CSS = (APP / "static" / "app.css").read_text(encoding="utf-8")
VIEWER = (APP / "static" / "viewer.js").read_text(encoding="utf-8")


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("asker", "a-long-enough-password")


@pytest.fixture
def a_case(person):
    settings_store.set_to("folder_management", True)
    return Case.objects.create(owner=person, name="Traffic stop")


def a_recording(person, a_case, title, *, ready=True, on_clock=True):
    one = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        case=a_case,
        title=title,
        original_filename=f"{title}.mp4",
        media_state=MediaState.READY,
        duration_seconds=600.0,
        playback_ready=True,
        probe={},
        clock_date=dt.date(2025, 11, 6) if on_clock else None,
        clock_start=51600.0 if on_clock else None,
    )
    one.folder.mkdir(parents=True, exist_ok=True)
    (one.folder / "playback.mp4").write_bytes(b"x")
    if ready:
        Transcript.objects.create(recording=one, language="en")
    return one


def test_the_case_column_lists_the_case_with_the_moment_on_each_row(
    person, a_case, client
):
    first = a_recording(person, a_case, "BWC-1")
    here = a_recording(person, a_case, "BWC-2")
    later = a_recording(person, a_case, "BWC-3", ready=False, on_clock=False)
    signed_in(client, person)
    page = client.get(f"/recording/{here.pk}").content.decode()
    assert '<div class="desk in-case">' in page
    assert '<aside class="case-column" id="case-column"' in page
    assert "This case &middot; 3 recordings" in page
    # The column marks the one in hand (the walker's list marks it too).
    assert page.count('aria-current="page"') == 1
    assert (
        f'href="/recording/{first.pk}" data-start="63898122000.0" data-length="600.0"'
        in page
    )
    current = f'href="/recording/{here.pk}" data-start="63898122000.0"'
    current += ' data-length="600.0" aria-current="page"'
    assert current in page
    assert later.title in page and "not ready" in page
    assert f'href="/case/{a_case.pk}/download"' in page or "Download all" in page


def test_the_rules_the_scripts_and_the_grip_hold():
    assert ".case-column { display: none; }" in CSS
    assert "@media (min-width: 2200px) {\n  .desk.in-case:not(.sound) {" in CSS
    assert '"case body stage";' in CSS and '"case body";' in CSS
    assert ".desk.in-case:not(.sound) .stagegrip { right: auto; left: -5px; }" in CSS
    # The map beside the words of v1.224.0 went with v1.225.0 (the map in the
    # stage); nothing of the two-panel work area is left.
    assert ".panels.two" not in CSS and "THREE_COLUMNS" not in VIEWER
    assert "function momentHref(link)" in VIEWER
    assert ".case-column-list a[data-start]" in VIEWER
    assert "(onTheRight ? -1 : 1) * (event.clientX - stageFromX)" in VIEWER
