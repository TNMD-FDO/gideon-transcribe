"""The thorough walk of 4 October (v1.123.0): the fixes it asked for."""

from __future__ import annotations

import json

import pytest
from core import close, lifecycle, notes, people, settings_store, sharing, vocabulary
from core.cases import Case
from core.jobs import Segment, Transcript
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

PASSWORD = "a long enough password 1"
APP = __import__("pathlib").Path(__file__).resolve().parent.parent


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


def colleague(username: str, name: str = "") -> User:
    person = User.objects.create_local_admin(username, PASSWORD)
    person.is_local = False
    person.display_name = name or username
    person.last_sign_in = timezone.now()
    person.save()
    return person


@pytest.fixture
def owner(db):
    return colleague("ana", "Ana Ruiz")


@pytest.fixture
def friend(db):
    return colleague("ben", "Ben Cole")


@pytest.fixture
def third(db):
    return colleague("cy", "Cy Dale")


@pytest.fixture
def a_case(owner):
    return Case.objects.create(owner=owner, name="Pike matter")


def a_call(owner, case, title, lines=()):
    batch = Batch.objects.create(user=owner)
    recording = Recording.objects.create(
        batch=batch,
        user=owner,
        case=case,
        title=title,
        original_filename=f"{title}.wav",
        media_state=MediaState.READY,
        recording_type="Jail call",
        duration_seconds=600,
    )
    transcript = Transcript.objects.create(recording=recording, language="en")
    for n, text in enumerate(lines or ("Hey.",)):
        Segment.objects.create(
            transcript=transcript,
            start=n * 10,
            end=n * 10 + 4,
            text=text,
            speaker="Pike",
        )
    return recording


def signed_in(client, person):
    client.force_login(person)
    LoginSession.objects.create(user=person, session_key=client.session.session_key)


# Settings read once per request ------------------------------------------------------


def test_a_setting_is_read_once_inside_a_request_and_afresh_after_a_change(db):
    settings_store.set_to("sharing", True)
    settings_store.start_request_cache()
    try:
        with CaptureQueriesContext(connection) as asked:
            for _ in range(5):
                assert settings_store.get("sharing") is True
        assert len(asked) == 1
        settings_store.set_to("sharing", False)
        assert settings_store.get("sharing") is False
    finally:
        settings_store.end_request_cache()
    # Outside a request every read is its own query again.
    with CaptureQueriesContext(connection) as asked:
        settings_store.get("sharing")
        settings_store.get("sharing")
    assert len(asked) == 2


def test_the_kept_settings_do_not_leak_between_requests(owner, client):
    signed_in(client, owner)
    settings_store.set_to("sharing", True)
    assert "Cases" in client.get("/").content.decode()
    settings_store.set_to("folder_management", False)
    page = client.get("/").content.decode()
    assert 'href="/cases"' not in page


# Transfer to a collaborator ----------------------------------------------------------


def test_a_case_is_handed_to_a_collaborator_and_the_list_offers_the_team_first(
    a_case, owner, friend, third, client
):
    sharing.grant(a_case, friend, actor=owner)
    signed_in(client, owner)
    listed = client.get(
        reverse("share-who", args=[a_case.pk]) + "?for=transfer"
    ).json()["people"]
    assert [one["username"] for one in listed] == ["ben", "cy"]
    plain = client.get(reverse("share-who", args=[a_case.pk])).json()["people"]
    assert [one["username"] for one in plain] == ["cy"]
    answer = client.post(reverse("transfer-case", args=[a_case.pk]), {"who": "ben"})
    assert answer.status_code == 200, answer.content
    a_case.refresh_from_db()
    assert a_case.owner == friend


# A surname reaches the spellings; a term joins its Person ----------------------


def test_the_surname_alone_reaches_the_names_spellings(owner, a_case):
    vocabulary.add_term(a_case, "Jordyn Pike", "jordan", by=owner)
    assert "jordan" in vocabulary.heard_as(a_case, ["pike"])
    assert "jordan" in vocabulary.heard_as(a_case, ["jordyn"])
    assert vocabulary.heard_as(a_case, ["pi"]) == []


def test_a_term_typed_before_the_speaker_was_named_joins_the_person(owner, a_case):
    vocabulary.add_term(a_case, "Jordyn Pike", "jordan, jordon", by=owner)
    person, made = people.join_or_create(a_case, "Jordyn Pike", by=owner, how="named")
    assert made and person.also_heard_as == ["jordan", "jordon"]
    entries = vocabulary.entries(a_case)
    assert [one["name"] for one in entries] == ["Jordyn Pike"]
    assert entries[0]["spellings"] == ["jordan", "jordon"]


# A short word one letter off is a close match ----------------------------------------


def test_a_short_word_one_letter_off_is_close(owner, a_case):
    call = a_call(owner, a_case, "Call 1", lines=("There was no knife in the bag.",))
    found = close.forms(
        ["knive"],
        sources=[(Segment.objects.filter(transcript__recording=call), "text")],
    )
    assert "knife" in found.get("knive", [])
    assert close.FLOORS[0] == (5, 0.3) and close.LEAST == 0.6


# Nobody's note is replaced unseen ----------------------------------------------------


def test_a_note_changed_while_the_box_was_open_is_not_replaced(
    owner, friend, a_case, client
):
    sharing.grant(a_case, friend, actor=owner)
    call = a_call(owner, a_case, "Call 1")
    line = call.transcript.segments.get()
    notes.set_note(line, "Ana's words.", by=owner)
    signed_in(client, friend)
    url = reverse("line-note", args=[call.pk, line.pk])
    stale = client.post(
        url,
        json.dumps({"note": "Ben's words.", "was": ""}),
        content_type="application/json",
    )
    assert stale.status_code == 409
    assert "changed by Ana Ruiz" in stale.json()["error"]
    assert stale.json()["note"] == "Ana's words."
    line.refresh_from_db()
    assert line.note == "Ana's words."
    fresh = client.post(
        url,
        json.dumps({"note": "Ben's words.", "was": "Ana's words."}),
        content_type="application/json",
    )
    assert fresh.status_code == 200 and fresh.json()["note_by"] == "Ben Cole"


# The sign-out page counts the session's clips alone ----------------------------------


def test_the_sign_out_tally_leaves_a_cases_clips_out(owner, a_case):
    from core.clips import Clip

    call = a_call(owner, a_case, "Call 1")
    Clip.objects.create(
        recording=call, user=owner, title="Kept", start=0, end=2, state="ready"
    )
    assert lifecycle.counts(owner)["clips_not_downloaded"] == 0


# The audit row names the recording and the time --------------------------------------


def test_a_notes_audit_row_names_the_recording_and_the_time(owner, a_case):
    from core import audit

    call = a_call(owner, a_case, "Call 0409")
    notes.set_note(call.transcript.segments.get(), "A word.", by=owner)
    row = audit.Row.objects.filter(event="Note added").get()
    assert row.object_label == "Call 0409 at 00:00:00"


# The page's own files ----------------------------------------------------------------


def test_the_case_page_fits_the_room_main_has_and_the_button_covers_no_row():
    css = (APP / "static" / "app.css").read_text(encoding="utf-8")
    assert "container-type: inline-size" in css
    assert "@container (max-width: 1000px)" in css
    assert "body:has(.gideon-button) .shell > main { padding-bottom: 84px; }" in css
    js = (APP / "static" / "notes-page.js").read_text(encoding="utf-8")
    assert "function callWord()" in js
    preview = (APP / "static" / "preview.js").read_text(encoding="utf-8")
    assert (
        "was: box.dataset.was" in preview and "saving replaces their words" in preview
    )
    assert "Back to the case" in (APP / "templates" / "incident.html").read_text(
        encoding="utf-8"
    )
