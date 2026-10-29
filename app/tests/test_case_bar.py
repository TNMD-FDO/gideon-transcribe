"""v1.171.0: the case bar (Phase 8 chapter 1 amended).

Checked here: the case page's bar is drawn from the helper with the tabs
in order and the open tab lit; the recording page, the incident page, the
document page, the Notes page and the Speakers page carry the same bar
with their tab lit and their own name after it, and their old ways back
are gone; a recording in no case and a Speakers page in a window show no
bar; the tabs the office has off are absent.
"""

from __future__ import annotations

import pytest
from core import case_bar, documents, incidents, settings_store, tasks
from core.cases import Case
from core.jobs import Segment, Transcript
from core.models import User
from core.recordings import Batch, MediaState, Recording
from tests.helpers import signed_in
from tests.test_documents import REPORT, make_pdf

PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def switched_on(db, monkeypatch):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("incidents", True)
    settings_store.set_to("documents", True)
    settings_store.set_to("clips_available", True)
    settings_store.set_to("assistant_available", True)
    settings_store.set_to("incidents_propose", True)
    monkeypatch.setattr(tasks.read_document, "defer", lambda **f: None)


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("asker", PASSWORD)


@pytest.fixture
def a_case(person):
    return Case.objects.create(owner=person, name="Harbour Street stop")


def video(person, case, title, lines=((0.0, "Step out."),)):
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        case=case,
        title=title,
        original_filename=f"{title}.mp4",
        media_state=MediaState.READY,
        duration_seconds=600.0,
        playback_ready=True,
        probe={},
    )
    recording.folder.mkdir(parents=True, exist_ok=True)
    (recording.folder / "playback.mp4").write_bytes(b"not really media")
    transcript = Transcript.objects.create(recording=recording, language="en")
    for start, text in lines:
        Segment.objects.create(
            transcript=transcript,
            start=start,
            end=start + 4,
            text=text,
            speaker="Speaker 1",
            speaker_label="SPEAKER_1",
        )
    return recording


ORDER = [
    "recordings",
    "search",
    "proposed",
    "notes",
    "documents",
    "incidents",
    "clips",
    "speakers",
    "details",
]


def test_the_helper_gives_the_tabs_in_order_with_their_counts(person, a_case):
    video(person, a_case, "BWC2-1")
    bar = case_bar.bar(a_case, on="notes", here="Notes page")
    assert [t["key"] for t in bar["tabs"]] == ORDER
    assert bar["name"] == "Harbour Street stop" and bar["here"] == "Notes page"
    assert bar["url"].endswith(f"/case/{a_case.pk}")
    by_key = {t["key"]: t for t in bar["tabs"]}
    assert (
        by_key["recordings"]["count"] == 1 and by_key["recordings"]["url"] == bar["url"]
    )
    assert by_key["notes"]["on"] is True and by_key["recordings"]["on"] is False
    assert by_key["search"]["count_shown"] is False
    assert by_key["speakers"]["count"] == "0 named"
    assert by_key["notes"]["url"].endswith("?tab=notes")
    # The tabs the office has off are absent.
    settings_store.set_to("documents", False)
    settings_store.set_to("clips_available", False)
    settings_store.set_to("incidents_propose", False)
    settings_store.set_to("incidents_watch_phrases", "")
    keys = [t["key"] for t in case_bar.bar(a_case, on="recordings")["tabs"]]
    assert keys == ["recordings", "search", "notes", "incidents", "speakers", "details"]


def _lit(page: str) -> str:
    """The lit tab's name on a page, from the bar's markup."""
    import re

    found = re.search(
        r'class="tab on">(?:<svg.*?</svg>)?\s*([A-Za-z ]+?)(?:\s*<span| </a>|</a>)',
        page,
        re.S,
    )
    return found.group(1).strip() if found else ""


def test_every_page_in_the_case_carries_the_bar_with_its_tab_lit(
    person, a_case, client
):
    cam = video(person, a_case, "BWC2-1")
    made = incidents.make(a_case, "Stop", [cam], by=person)
    report = documents.add(
        a_case,
        home={"recording": cam},
        data=make_pdf(REPORT),
        filename="report.pdf",
        title="Incident report",
        by=person,
    )
    signed_in(client, person)
    # The case page: its own bar, no name line above it.
    page = client.get(f"/case/{a_case.pk}?tab=notes").content.decode()
    assert 'id="case-tabs"' in page and 'id="case-bar"' not in page
    assert _lit(page) == "Notes"
    # The recording page: Recordings lit, the recording's name after; the
    # arrow and the crumb gone.
    page = client.get(f"/recording/{cam.pk}").content.decode()
    assert 'id="case-bar"' in page and _lit(page) == "Recordings"
    assert "&rsaquo; BWC2-1" in page and "Harbour Street stop" in page
    # The head's arrow went; the "This case" link under the video stays.
    assert (
        'title="Back to the case Harbour Street stop" class="btn ghost icon"'
        not in page
    )
    assert "This case: Harbour Street stop" in page
    # The incident page: Incidents lit; "in the case" and Back to the case gone.
    page = client.get(made.url()).content.decode()
    assert 'id="case-bar"' in page and _lit(page) == "Incidents"
    assert "&rsaquo; Stop" in page
    assert "in the case <a" not in page and "Back to the case" not in page
    # The document page: Documents lit; Back to the recording stays.
    page = client.get(f"/case/{a_case.pk}/document/{report.pk}").content.decode()
    assert 'id="case-bar"' in page and _lit(page) == "Documents"
    assert "Back to the recording" in page
    assert 'title="Back to the case&#x27;s Documents tab"' not in page
    # The Notes page: Notes lit; Back to the case gone.
    page = client.get(f"/case/{a_case.pk}/notes-page").content.decode()
    assert 'id="case-bar"' in page and _lit(page) == "Notes"
    assert "Back to the case" not in page
    # The Speakers page: under the recording; none in a window.
    page = client.get(f"/recording/{cam.pk}/speakers").content.decode()
    assert 'id="case-bar"' in page and _lit(page) == "Recordings"
    assert "BWC2-1 › Speakers" in page or "BWC2-1 &rsaquo; Speakers" in page
    page = client.get(f"/recording/{cam.pk}/window/speakers").content.decode()
    assert 'id="case-bar"' not in page


def test_a_recording_in_no_case_shows_no_bar(person, client):
    loose = video(person, None, "Dictation")
    signed_in(client, person)
    page = client.get(f"/recording/{loose.pk}").content.decode()
    assert (
        'id="case-bar"' not in page
        and "My recordings" in page
        or "Back to your recordings" in page
    )
