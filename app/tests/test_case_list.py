"""Fit for 800 (Phase 9 chapter 1): the case page's rows from a handful of
queries, the filter box, the Notes column and Download the list."""

from __future__ import annotations

import csv
import io

import pytest
from core import audit, notes
from core.cases import Case
from core.jobs import Segment, Transcript
from core.models import LoginSession, User
from core.notes import MomentNote
from core.recordings import Batch, MediaState, Recording
from django.urls import reverse

PASSWORD = "a long enough password 1"


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"
    return tmp_path


@pytest.fixture(autouse=True)
def cases_on(db):
    from core import settings_store

    settings_store.set_to("folder_management", True)


@pytest.fixture
def owner(db):
    return User.objects.create_local_admin("list-owner", PASSWORD)


@pytest.fixture
def colleague(db):
    person = User.objects.create_local_admin("list-colleague", PASSWORD)
    person.is_local = False
    person.display_name = "D. Chen"
    person.save()
    return person


@pytest.fixture
def a_case(owner):
    return Case.objects.create(owner=owner, name="Pike matter")


def a_call(owner, case, title, kind="Jail call", words=True):
    batch = Batch.objects.create(user=owner)
    recording = Recording.objects.create(
        batch=batch,
        user=owner,
        case=case,
        title=title,
        original_filename=f"{title}.wav",
        media_state=MediaState.READY,
        recording_type=kind,
        duration_seconds=895,
    )
    if words:
        transcript = Transcript.objects.create(recording=recording, language="en")
        Segment.objects.create(
            transcript=transcript, start=0, end=4, text="Hey. It is me.", speaker="Pike"
        )
        Segment.objects.create(
            transcript=transcript,
            start=5,
            end=9,
            text="Because they came by asking.",
            speaker="Speaker 2",
        )
    return recording


def signed_in(client, person):
    """A browser with a Login session behind it, which the middleware wants."""
    client.force_login(person)
    LoginSession.objects.create(user=person, session_key=client.session.session_key)


# The queries --------------------------------------------------------------------


def test_the_case_page_asks_a_handful_of_questions_whatever_the_count(
    owner, a_case, client, django_assert_max_num_queries
):
    """Eighty recordings with transcripts and notes: the page's query count
    does not grow with the rows."""
    for n in range(80):
        call = a_call(owner, a_case, f"Call {n:04d}")
        if n % 3 == 0:
            line = call.transcript.segments.first()
            line.note = "worth a look"
            line.note_by = owner
            line.save()
    signed_in(client, owner)
    # About a hundred questions draw the page whatever the count: the rows
    # themselves take six (the recordings, the newest jobs, the speakers, the
    # cameras, the notes twice, the clip counts); the rest are the page's own
    # settings and panes. Before Phase 9 this was seven per row.
    with django_assert_max_num_queries(110):
        answer = client.get(reverse("case", args=[a_case.pk]))
    assert answer.status_code == 200
    assert answer.content.count(b'<tr class="pick"') == 80


# The Notes column ----------------------------------------------------------------


def test_the_notes_column_counts_and_names_the_writers(
    owner, colleague, a_case, client
):
    call = a_call(owner, a_case, "Call 0417")
    first, second = call.transcript.segments.order_by("start")
    first.note = "first mention"
    first.note_by = owner
    first.save()
    second.note = "who came by?"
    second.note_by = colleague
    second.save()
    MomentNote.objects.create(
        recording=call, at=7.5, note="a silence", note_by=colleague
    )
    quiet = a_call(owner, a_case, "Call 0418")

    counts = notes.counts_in(a_case)
    assert counts[call.pk]["count"] == 3
    # The busiest writer first.
    assert counts[call.pk]["writers"] == ["D. Chen", owner.shown_name]
    assert quiet.pk not in counts
    assert (
        notes.count_words(counts[call.pk]) == f"3 notes, D. Chen and {owner.shown_name}"
    )
    assert notes.count_words(None) == ""
    assert (
        notes.count_words({"count": 4, "writers": ["A", "B", "C", "D"]})
        == "4 notes, A, B and 2 more"
    )
    assert notes.count_words({"count": 1, "writers": ["A"]}) == "1 note, A"

    signed_in(client, owner)
    page = client.get(reverse("case", args=[a_case.pk])).content.decode()
    assert "<th>Notes</th>" in page
    assert f"3 notes, D. Chen and {owner.shown_name}" in page
    assert ">none<" in page


# The filter box ------------------------------------------------------------------


def test_the_filter_box_and_its_words_are_on_the_page(owner, a_case, client):
    a_call(owner, a_case, "Call 0417")
    signed_in(client, owner)
    page = client.get(reverse("case", args=[a_case.pk])).content.decode()
    assert 'id="recording-filter"' in page
    assert "Filter these recordings" in page
    assert 'data-filter="call 0417 jail call list-owner"' in page
    assert "Download the list" in page
    assert reverse("case-list", args=[a_case.pk]) in page


def test_an_empty_case_offers_no_filter(owner, a_case, client):
    signed_in(client, owner)
    page = client.get(reverse("case", args=[a_case.pk])).content.decode()
    assert 'id="recording-filter"' not in page


# Download the list -----------------------------------------------------------------


def test_the_list_is_a_spreadsheet_of_the_rows_with_one_audit_row(
    owner, colleague, a_case, client
):
    first = a_call(owner, a_case, "Call 0409")
    second = a_call(owner, a_case, "Call 0417", kind="Interview")
    second.description = "the second caller"
    second.save()
    line = second.transcript.segments.first()
    line.note = "first mention"
    line.note_by = colleague
    line.save()
    signed_in(client, owner)
    before = audit.Row.objects.count()

    answer = client.get(reverse("case-list", args=[a_case.pk]))

    assert answer.status_code == 200
    assert answer["Content-Type"].startswith("text/csv")
    assert "recordings.csv" in answer["Content-Disposition"]
    body = answer.content
    assert body.startswith(b"\xef\xbb\xbf"), "a byte order mark for the spreadsheet"
    rows = list(csv.reader(io.StringIO(body.decode("utf-8-sig"))))
    assert rows[0] == [
        "Title",
        "Type",
        "Added on",
        "Added by",
        "Length",
        "State",
        "Speakers",
        "Notes",
        "Note writers",
        "Description",
    ]
    # Oldest added first, so the sheet reads as the case was filled.
    assert [row[0] for row in rows[1:]] == [first.title, second.title]
    assert rows[2][1] == "Interview"
    assert rows[2][4] == "00:14:55"
    assert rows[2][5] == "Ready"
    assert rows[2][6] == "1 named, 1 unnamed"
    assert rows[2][7] == "1"
    assert rows[2][8] == "D. Chen"
    assert rows[2][9] == "the second caller"
    assert rows[1][7] == "0"

    written = audit.Row.objects.order_by("-at").first()
    assert audit.Row.objects.count() == before + 1
    assert written.event == "case list downloaded"
    assert written.details.get("count") == 2
    assert "Call 0417" not in str(written.details)


def test_a_stranger_gets_nothing(owner, colleague, a_case, client):
    a_call(owner, a_case, "Call 0409")
    signed_in(client, colleague)
    assert client.get(reverse("case-list", args=[a_case.pk])).status_code == 404


# The Notes tab's rows ------------------------------------------------------------


def test_the_notes_tab_rows_carry_what_the_notes_page_needs(owner, colleague, a_case):
    call = a_call(owner, a_case, "Call 0417")
    line = call.transcript.segments.order_by("start").last()
    line.note = "who came by?"
    line.note_by = colleague
    line.save()
    MomentNote.objects.create(recording=call, at=7.5, note="a silence", note_by=owner)

    rows = notes.of_case(a_case)["all"]
    by_kind = {row["kind"]: row for row in rows}
    assert by_kind["line"]["recording_id"] == call.pk
    assert by_kind["line"]["type"] == "Jail call"
    assert by_kind["line"]["at"] == 5
    assert by_kind["line"]["by_id"] == colleague.pk
    assert by_kind["line"]["id"] == line.pk
    assert by_kind["line"]["created"] == call.created
    assert by_kind["moment"]["at"] == 7.5
    assert by_kind["moment"]["by_id"] == owner.pk
