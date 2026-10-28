"""The Preview as a window from the Notes tab (v1.166.0).

A row's time carries the recording and the moment, so the Preview's one
click handler plays it without leaving the tab; the note's words still open
the recording page with the box ready. The floating Preview on a wide window
with no column takes the hearing window's frame, without the dim; under
900 px the sheet stays.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from core import settings_store
from core.cases import Case
from core.jobs import Segment, Transcript
from core.models import User
from core.recordings import Batch, MediaState, Recording
from django.urls import reverse
from tests.helpers import signed_in

HERE = Path(__file__).resolve().parents[1]
PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def switches(db):
    settings_store.set_to("folder_management", True)


@pytest.fixture
def owner(db):
    return User.objects.create_local_admin("window-owner", PASSWORD)


@pytest.fixture
def noted(owner):
    case = Case.objects.create(owner=owner, name="Harbour Street stop")
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=owner),
        user=owner,
        case=case,
        title="BWC2-1",
        original_filename="bwc2-1.mp4",
        media_state=MediaState.READY,
        duration_seconds=600.0,
    )
    transcript = Transcript.objects.create(recording=recording, language="en")
    line = Segment.objects.create(
        transcript=transcript,
        start=386.2,
        end=389.0,
        text="What's in the bag?",
        speaker="Speaker 1",
        note="Passenger side: second officer sees the bag on the floor.",
        note_by=owner,
    )
    return case, recording, line


def test_a_rows_time_opens_the_preview_and_its_words_still_leave(owner, noted, client):
    case, recording, line = noted
    signed_in(client, owner)
    page = client.get(reverse("case", args=[case.pk]) + "?tab=notes").content.decode()
    viewer = reverse("viewer", args=[recording.pk])
    # The time: the recording and the moment for the Preview, the recording
    # page as its address for a press without script.
    assert (
        f'href="{viewer}?t=386.2&amp;note=1" class="mono" '
        f'data-preview-recording="{recording.pk}" data-preview-at="386.2"'
    ) in page
    # The words: the recording page with the box ready, as before.
    assert (
        f'<a class="note-text" href="{viewer}?t=386.2&amp;note=1" '
        'title="Open where this note was written">'
    ) in page
    assert page.count("data-preview-recording=") == 1


def test_the_preview_takes_the_window_shape_without_the_dim():
    script = (HERE / "static" / "preview.js").read_text(encoding="utf-8")
    for piece in (
        "var windowed = !host && !column && !isSnippet() && window.innerWidth >= 900;",
        '(windowed ? " window" : " sheet")',
        '(isSnippet() || windowed ? "Close ✕" : "Close")',
        'if (card.classList.contains("window")) {',
        "windowPlace = { left: card.style.left, top: card.style.top };",
    ):
        assert piece in script, piece
    # The dim belongs to the hearing window alone.
    assert script.count('document.body.classList.add("hearing-open")') == 1
    css = (HERE / "static" / "app.css").read_text(encoding="utf-8")
    for rule in (
        ".preview-card.window {",
        "body.gideon-open .preview-card.window {",
        ".preview-card.hearing .preview-head, .preview-card.window .preview-head {",
        ".preview-card.window .noted {",
        ".note-row a[data-preview-recording]::before {",
        ".note-row:has(.previewing) {",
    ):
        assert rule in css, rule
    assert "body.window-open" not in css
    # The sheet under 900 px is the rule it was.
    assert (
        "@media (max-width: 899px) { .preview-card, body.gideon-open .preview-card {"
        in css
    )


def test_the_glossary_and_the_spec_say_where_the_preview_opens():
    glossary = (HERE.parent / "CONTEXT.md").read_text(encoding="utf-8")
    assert (
        "a window of its own at the bottom right on a wide screen (v1.166.0" in glossary
    )
    phase_8 = (HERE.parent / "docs" / "spec" / "SPEC-PHASE-8.md").read_text(
        encoding="utf-8"
    )
    assert "phase-8-notes-window.html" in phase_8
    assert (
        HERE.parent / "docs" / "spec" / "mockups" / "phase-8-notes-window.html"
    ).exists()
