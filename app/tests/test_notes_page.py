"""The Notes page (Phase 9 chapter 4)."""

from __future__ import annotations

import json

import pytest
from core import assignments, assistant, case_search, settings_store, sharing
from core.assistant import DONE, Summary
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
def on(db):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("sharing", True)


def person(username: str, name: str) -> User:
    one = User.objects.create_local_admin(username, PASSWORD)
    one.is_local = False
    one.display_name = name
    one.save()
    return one


@pytest.fixture
def owner(db):
    return person("np-owner", "Ana Ruiz")


@pytest.fixture
def friend(db):
    return person("np-friend", "Ben Cole")


@pytest.fixture
def admin(db):
    one = User.objects.create_local_admin("np-admin", PASSWORD)
    one.display_name = "The Admin"
    one.save()
    return one


@pytest.fixture
def a_case(owner):
    return Case.objects.create(owner=owner, name="Pike matter")


def a_call(owner, case, title, lines=3):
    batch = Batch.objects.create(user=owner)
    recording = Recording.objects.create(
        batch=batch,
        user=owner,
        case=case,
        title=title,
        original_filename=f"{title}.wav",
        media_state=MediaState.READY,
        recording_type="Jail call",
        duration_seconds=300,
    )
    transcript = Transcript.objects.create(recording=recording, language="en")
    for n in range(lines):
        Segment.objects.create(
            transcript=transcript,
            start=n * 10,
            end=n * 10 + 4,
            text=f"Line {n} of {title}, about the storage unit."
            if n == 1
            else f"Line {n}.",
            speaker="Pike" if n % 2 == 0 else "Caller",
        )
    return recording


def note_on(recording, index, words, by):
    line = list(recording.transcript.segments.order_by("start"))[index]
    line.note = words
    line.note_by = by
    from django.utils import timezone

    line.note_changed = timezone.now()
    line.save()
    return line


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)


# Who may open it, and the door -------------------------------------------------------


def test_the_page_opens_for_the_team_and_an_admin_with_its_row(
    owner, friend, admin, a_case, client
):
    sharing.grant(a_case, friend, actor=owner)
    a_call(owner, a_case, "Call 0409")
    for who in (owner, friend):
        signed_in(client, who)
        page = client.get(reverse("notes-page", args=[a_case.pk]))
        assert page.status_code == 200
        assert 'id="notes-desk"' in page.content.decode()
    from core import audit

    before = audit.Row.objects.filter(event="admin access").count()
    signed_in(client, admin)
    assert client.get(reverse("notes-page", args=[a_case.pk])).status_code == 200
    assert audit.Row.objects.filter(event="admin access").count() == before + 1
    # A stranger is told nothing.
    stranger = person("np-stranger", "Cy Dale")
    signed_in(client, stranger)
    assert client.get(reverse("notes-page", args=[a_case.pk])).status_code == 404


def test_the_notes_tab_offers_the_page_and_a_row_opens_on_its_note(
    owner, a_case, client
):
    call = a_call(owner, a_case, "Call 0409")
    line = note_on(call, 1, "worth a look", owner)
    signed_in(client, owner)
    page = client.get(reverse("case", args=[a_case.pk]) + "?tab=notes").content.decode()
    assert "Open as a page" in page
    assert f"?note=line:{line.pk}" in page
    page = client.get(
        reverse("notes-page", args=[a_case.pk]) + f"?note=line:{line.pk}"
    ).content.decode()
    assert f'data-opening="line:{line.pk}"' in page


def test_the_page_is_gone_with_folder_management(owner, a_case, client):
    settings_store.set_to("folder_management", False)
    signed_in(client, owner)
    assert client.get(reverse("notes-page", args=[a_case.pk])).status_code == 404


# The reading -------------------------------------------------------------------------


def test_the_list_is_grouped_in_call_order_with_the_fields_the_page_draws(
    owner, friend, a_case, client
):
    sharing.grant(a_case, friend, actor=owner)
    first = a_call(owner, a_case, "Call 0409")
    second = a_call(owner, a_case, "Call 0417")
    quiet = a_call(owner, a_case, "Call 0418")
    note_on(second, 2, "later line first in time", owner)
    note_on(second, 0, "earlier line", friend)
    note_on(first, 1, "the first call's note", friend)
    MomentNote.objects.create(recording=first, at=7.5, note="a silence", note_by=owner)
    assignments.assign(second, friend, by=owner)
    assignments.mark_reviewed(second, by=friend)
    Summary.objects.create(recording=first, state=DONE, text="Overview:\nA short call.")

    signed_in(client, friend)
    got = client.get(reverse("notes-page-list", args=[a_case.pk])).json()

    assert [one["title"] for one in got["recordings"]] == [
        "Call 0409",
        "Call 0417",
        "Call 0418",
    ]
    assert [one["key"].split(":")[0] for one in got["notes"]] == [
        "moment",
        "line",
        "line",
        "line",
    ]
    assert [one["at"] for one in got["notes"]] == [7.5, 10.0, 0.0, 20.0]
    assert got["no_note"] == 1
    assert got["me"] == friend.pk and got["may_direct"] is False
    assert [one["name"] for one in got["writers"]] == ["Ana Ruiz", "Ben Cole"]
    assert got["types"] == [{"name": "Jail call", "count": 3}]
    row = got["recordings"][1]
    assert row["assigned"] == "Ben Cole" and row["assigned_id"] == friend.pk
    assert row["reviewed"].startswith("Reviewed by you, ")
    assert row["notes"] == 2 and set(row["writers"]) == {"Ana Ruiz", "Ben Cole"}
    assert got["recordings"][0]["summarised"] is True
    assert got["recordings"][2]["notes"] == 0 and quiet.title == "Call 0418"
    first_note = got["notes"][1]
    assert first_note["said"].startswith("Line 1 of Call 0409")
    assert first_note["who"] == "Caller" and first_note["by"] == "Ben Cole"


def test_the_list_asks_a_handful_of_questions(
    owner, a_case, client, django_assert_max_num_queries
):
    for n in range(40):
        call = a_call(owner, a_case, f"Call {n:04d}", lines=2)
        if n % 2 == 0:
            note_on(call, 1, "a note", owner)
    signed_in(client, owner)
    # Eleven at the time of writing: the session, the case, the recordings,
    # the summaries, the transcripts' words, the notes on lines and at
    # moments; none per row.
    with django_assert_max_num_queries(20):
        got = client.get(reverse("notes-page-list", args=[a_case.pk])).json()
    assert len(got["recordings"]) == 40 and len(got["notes"]) == 20


# The Overview and the whole recording ------------------------------------------------


def test_the_overview_is_the_summarys_first_part(owner, a_case):
    call = a_call(owner, a_case, "Call 0409")
    assert assistant.overview_of(call) == ""
    Summary.objects.create(
        recording=call,
        state=DONE,
        transcript_created=call.transcript.created,
        text=(
            "Overview:\nPike and a caller talk about the letter.\nIt matters.\n\n"
            "What is discussed:\nThe letter (00:00:10)."
        ),
    )
    assert (
        assistant.overview_of(call)
        == "Pike and a caller talk about the letter. It matters."
    )
    Summary.objects.filter(recording=call).update(
        text="**Summary**\nA memo's first paragraph.\n\nPeople:\nPike."
    )
    assert assistant.overview_of(call) == "A memo's first paragraph."
    Summary.objects.filter(recording=call).update(text="No heading at all. " * 60)
    taken = assistant.overview_of(call)
    assert len(taken) <= assistant.OVERVIEW_MOST + 3 and taken.endswith(".")
    Summary.objects.filter(recording=call).update(
        text="Background:\nOnly an odd heading."
    )
    assert assistant.overview_of(call) == "Only an odd heading."


def test_around_reads_the_whole_recording_and_the_pages_facts(owner, a_case, client):
    call = a_call(owner, a_case, "Call 0409", lines=30)
    Summary.objects.create(recording=call, state=DONE, text="Overview:\nShort.")
    assignments.assign(call, owner, by=owner)
    signed_in(client, owner)
    told = client.get(reverse("recording-around", args=[call.pk]) + "?t=100").json()
    assert len(told["lines"]) < 30 and told["whole"] is False
    assert told["overview"] == "Short." and told["summarised"] is True
    assert told["length"] == "00:05:00" and told["type"] == "Jail call"
    assert told["assigned"] == "Ana Ruiz" and told["may_mark"] is True
    whole = client.get(
        reverse("recording-around", args=[call.pk]) + "?t=100&whole=1"
    ).json()
    assert len(whole["lines"]) == 30 and whole["whole"] is True


# Find --------------------------------------------------------------------------------


def test_find_reads_the_notes_and_the_words_and_is_never_logged(
    owner, friend, a_case, client
):
    from core import audit

    first = a_call(owner, a_case, "Call 0409")
    second = a_call(owner, a_case, "Call 0417")
    note_on(first, 0, "the storage unit again", friend)
    MomentNote.objects.create(
        recording=second, at=3.0, note="storage mentioned", note_by=owner
    )
    found = case_search.find_notes(a_case, "storage")
    kinds = [(one["kind"], one["recording"]) for one in found["hits"]]
    assert ("note", str(first.pk)) in kinds and ("note", str(second.pk)) in kinds
    assert ("words", str(first.pk)) in kinds
    assert all("<mark>" in one["html"] for one in found["hits"])
    assert case_search.find_notes(a_case, "x")["hits"] == []

    signed_in(client, owner)
    before = audit.Row.objects.count()
    got = client.get(reverse("notes-page-find", args=[a_case.pk]) + "?q=storage").json()
    assert len(got["hits"]) >= 3
    assert audit.Row.objects.count() == before
    assert not any(
        "storage" in json.dumps(row.details) for row in audit.Row.objects.all()
    )
