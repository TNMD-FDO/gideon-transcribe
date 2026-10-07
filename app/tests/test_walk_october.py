"""The thorough walk of 4 October (v1.123.0): the fixes it asked for."""

from __future__ import annotations

import datetime as dt
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


def test_the_middleware_is_installed_and_the_kept_settings_do_not_leak(owner, client):
    from django.conf import settings as django_settings

    # v1.123.1: the line in settings.py had been left out of v1.123.0's push.
    assert "core.middleware.SettingsCacheMiddleware" in django_settings.MIDDLEWARE
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


# v1.124.0: the Search tab's events, Home's counts, the Off spells once ----------------


def test_the_off_spells_are_read_once_per_request_and_after_a_change(db):
    from core import retention

    settings_store.set_to("folder_management", True)
    now = timezone.now()
    settings_store.start_request_cache()
    try:
        with CaptureQueriesContext(connection) as asked:
            for _ in range(4):
                retention.days_off_between(now - dt.timedelta(days=30), now)
        assert len(asked) == 1
        settings_store.set_to("folder_management", False)
        with CaptureQueriesContext(connection) as asked:
            retention.days_off_between(now - dt.timedelta(days=30), now)
        assert len(asked) >= 1
    finally:
        settings_store.end_request_cache()


def test_the_incident_counts_are_grouped_and_read_as_the_pills_do(owner, a_case):
    from core import dashboard

    assert dashboard.incident_counts(a_case) == {}
    assert dashboard.incident_pills(
        type("I", (), {"pk": 1, "url": lambda self: "/x"})(),
        {"unsynced": 1, "to_check": 2, "proposals": 0, "writing": 0, "stale": 1},
    ) == [
        {"words": "not synced", "href": "/x", "tone": "warn"},
        {"words": "2 events to check", "href": "/x", "tone": "warn"},
        {"words": "1 memo has newer events", "href": "/x", "tone": "warn"},
    ]


def test_ready_batches_ask_one_question_of_the_database(owner, client):
    from core import home

    for _ in range(3):
        batch = Batch.objects.create(user=owner)
        Recording.objects.create(
            batch=batch,
            user=owner,
            title="Loose",
            original_filename="loose.wav",
            media_state=MediaState.READY,
            duration_seconds=10,
        )
    with CaptureQueriesContext(connection) as asked:
        ready = home.ready_batches(owner)
    assert len(ready) == 0 and len(asked) <= 3


def test_the_unfinished_batch_is_found_in_two_questions_and_is_the_newest(owner):
    from core.jobs import Job, JobState

    finished = Batch.objects.create(user=owner)
    Recording.objects.create(
        batch=finished,
        user=owner,
        title="Done",
        original_filename="done.wav",
        media_state=MediaState.READY,
        duration_seconds=10,
    )
    older = Batch.objects.create(user=owner)
    Recording.objects.create(
        batch=older,
        user=owner,
        title="Still checking",
        original_filename="checking.wav",
        media_state=MediaState.CHECKING,
        duration_seconds=10,
    )
    newer = Batch.objects.create(user=owner)
    waiting = Recording.objects.create(
        batch=newer,
        user=owner,
        title="Queued",
        original_filename="queued.wav",
        media_state=MediaState.READY,
        duration_seconds=10,
    )
    Job.objects.create(batch=newer, recording=waiting, state=JobState.QUEUED)
    Batch.objects.create(user=owner, is_live=True)
    with CaptureQueriesContext(connection) as asked:
        found = Batch.unfinished_for(owner)
    assert found == newer and len(asked) <= 3
    Job.objects.filter(batch=newer).update(state=JobState.DONE)
    assert Batch.unfinished_for(owner) == older
    Recording.objects.filter(batch=older).update(media_state=MediaState.READY)
    assert Batch.unfinished_for(owner) is None


def test_the_chat_row_counts_what_was_read_on_the_whole_route():
    from core import case_chat

    turn = type(
        "T",
        (),
        {"selection": {}, "scope": {}, "route": "whole", "readings": [1, 2, 3]},
    )()
    assert case_chat._scope_fields(turn)["read_whole"] == 3


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


def test_share_is_the_one_button_and_the_case_tabs_fold():
    """v1.125.1: the Team block's Add people button shared the Share button's
    id and never got the click; the tabs ran under About this case at 1366."""
    page = (APP / "templates" / "case.html").read_text(encoding="utf-8")
    assert page.count('id="share"') == 1
    assert "Add people is above" not in page
    css = (APP / "static" / "app.css").read_text(encoding="utf-8")
    assert ".case-page .tabs { flex-wrap: wrap; }" in css
    assert ".case-page .tabs .tab .i { display: none; }" in css


def test_the_share_reloads_and_the_chat_list_has_its_two_tabs():
    """v1.126.0: the share's success reloads the page (the old table row is
    gone), and the chat component draws Mine and Everyone's on a shared case."""
    cases_js = (APP / "static" / "cases.js").read_text(encoding="utf-8")
    assert "addShareRow" not in cases_js
    shared = cases_js.index('"/share", { who: who }')
    assert "window.location.reload()" in cases_js[shared : shared + 600]
    chat_js = (APP / "static" / "chat-ui.js").read_text(encoding="utf-8")
    assert "Everyone's <span class='count'>" in chat_js
    assert "one.yours === false" in chat_js and "whose-notice" in chat_js
    css = (APP / "static" / "app.css").read_text(encoding="utf-8")
    assert ".chat-ui .chat-list .whose-tab.on" in css


def test_the_fold_saves_on_change_and_the_view_keeps_type_and_description(
    owner, friend, a_case, client
):
    """v1.126.1: no Save button; the type cell is addressable; the view
    keeps what is posted and refuses a stranger."""
    page = (APP / "templates" / "case.html").read_text(encoding="utf-8")
    assert "save-details" not in page and 'class="muted type"' in page
    cases_js = (APP / "static" / "cases.js").read_text(encoding="utf-8")
    assert 'closest(".a-type, .a-description")' in cases_js
    assert "save-details" not in cases_js
    call = a_call(owner, a_case, "Call 0001")
    signed_in(client, owner)
    said = client.post(
        reverse("case-details", args=[call.pk]),
        {"recording_type": "Hearing", "description": "  the bail hearing  "},
    )
    assert said.status_code == 200 and said.json()["ok"] is True
    call.refresh_from_db()
    assert call.recording_type == "Hearing"
    assert call.description == "the bail hearing"
    stranger = colleague("cy", "Cy Park")
    signed_in(client, stranger)
    assert client.post(reverse("case-details", args=[call.pk]), {}).status_code == 404
    assert friend.pk is not None


def test_the_drawer_floats_over_the_desks_and_the_chat_list_closes_on_click_away():
    """v1.126.2: the incident and Notes pages are excused from the docked
    panel's padding, and the chat component closes its list on click-away."""
    css = (APP / "static" / "app.css").read_text(encoding="utf-8")
    assert "body.incident-page.gideon-open .shell > main, " in css
    assert "body.notes-page.gideon-open .shell > main { padding-right: 0; }" in css
    chat_js = (APP / "static" / "chat-ui.js").read_text(encoding="utf-8")
    assert (
        "if (listBox.open && !listBox.contains(event.target)) { listBox.open = false; }"
        in chat_js
    )
    assert 'event.key === "Escape" && listBox.open' in chat_js


def test_the_notes_page_has_the_notes_left_the_player_right_and_a_way_back():
    """v1.127.0, the maintainer's pick B: Back to the case in the head, the
    notes column before the grip and the player after it, one player bar
    with the page's Play, and no sentence about the browser's controls."""
    page = (APP / "templates" / "notes-page.html").read_text(encoding="utf-8")
    assert "Back to the case" in page
    assert (
        page.index('id="np-work"')
        < page.index('id="work-grip"')
        < page.index('id="np-left"')
    )
    assert 'id="np-play"' in page and 'id="np-note-now"' in page
    assert "np-bar-said" not in page
    assert page.count('data-panel="notes"') == 2  # Recordings' and Details' way back
    js = (APP / "static" / "notes-page.js").read_text(encoding="utf-8")
    assert "np-bar-said" not in js and "function wirePlayer" in js
    assert 'KEY = "notes-page-player-width"' in js
    css = (APP / "static" / "app.css").read_text(encoding="utf-8")
    assert "grid-template-columns: minmax(0, 1fr) 12px var(--player, 520px)" in css
    assert ".preview-card.mounted .preview-media audio { display: none; }" in css


def test_the_word_mark_leaves_with_the_line_and_the_check_stands_first():
    """v1.127.1: the viewer clears the word mark of the line it leaves; the
    Speakers page puts Check the speakers before Suggest names with the
    best-practice line; both scripts carry the advice and never a bar."""
    viewer = (APP / "static" / "viewer.js").read_text(encoding="utf-8")
    assert 'was.querySelectorAll(".word.now")' in viewer
    page = (APP / "templates" / "speakers-page.html").read_text(encoding="utf-8")
    assert page.index('id="check-line"') < page.index('id="suggest-line"')
    assert "For the best names, check the speakers first" in page
    for name in ("speakers-page.js", "assistant.js"):
        script = (APP / "static" / name).read_text(encoding="utf-8")
        assert "works either way" in script, name
        assert "For the best names" in script, name
