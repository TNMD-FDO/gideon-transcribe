"""The no-type line (v1.147.1): on a recording in a case with no type, while
the Speaker check is on and Voices help the check lists some types, the
recording page and the Speakers page say so with the type picker in the
line; not on a typed recording, not out of a case, not with the voice off."""

from pathlib import Path

import pytest
from core import settings_store, viewer
from tests.helpers import signed_in
from tests.test_people import a_case as _a_case  # noqa: F401
from tests.test_people import a_recording
from tests.test_people import owner as _owner  # noqa: F401

HERE = Path(__file__).resolve().parents[1]
LINE = "This recording has no type, so the check reads the words alone"


@pytest.fixture
def owner(_owner):  # noqa: F811
    return _owner


@pytest.fixture
def a_case(_a_case):  # noqa: F811
    return _a_case


@pytest.fixture
def check_on(db):
    settings_store.set_to("speaker_check_available", True)
    settings_store.set_to("voices_types", "Jail call")
    yield
    settings_store.set_to("speaker_check_available", False)


def test_the_line_shows_on_both_pages_for_an_untyped_recording_in_a_case(
    owner, a_case, check_on, client
):
    recording = a_recording(owner, a_case)
    hint = viewer.type_hint(recording)
    assert hint["listed"] == ["Jail call"] and hint["listed_text"] == "Jail call"
    assert "Jail call" in hint["types"]
    signed_in(client, owner)
    for url in (f"/recording/{recording.pk}", f"/recording/{recording.pk}/speakers"):
        page = client.get(url).content.decode()
        assert LINE in page, url
        assert "The voice listens on: Jail call" in page
        assert 'class="type-hint small muted"' in page and "type-hint.js" in page
        assert f'data-recording="{recording.pk}"' in page
    # The pick saves through the case page's endpoint, description kept.
    recording.description = "kept"
    recording.save(update_fields=["description"])
    answer = client.post(
        f"/recording/{recording.pk}/case-details",
        {"recording_type": "Jail call", "description": "kept"},
    )
    assert answer.status_code == 200 and answer.json()["ok"]
    recording.refresh_from_db()
    assert recording.recording_type == "Jail call" and recording.description == "kept"
    # Typed, the line is gone from both pages.
    assert viewer.type_hint(recording) is None
    for url in (f"/recording/{recording.pk}", f"/recording/{recording.pk}/speakers"):
        assert LINE not in client.get(url).content.decode(), url


def test_the_line_stays_away_where_it_does_not_apply(owner, a_case, check_on):
    recording = a_recording(owner, a_case)
    # The voice listens on no type: nothing to point at.
    settings_store.set_to("voices_types", "")
    assert viewer.type_hint(recording) is None
    settings_store.set_to("voices_types", "Jail call")
    # The check itself off.
    settings_store.set_to("speaker_check_available", False)
    assert viewer.type_hint(recording) is None
    settings_store.set_to("speaker_check_available", True)
    # Out of a case there is no type to give.
    recording.case = None
    recording.save(update_fields=["case"])
    assert viewer.type_hint(recording) is None


def test_the_script_saves_and_rewrites_the_line():
    script = (HERE / "static" / "type-hint.js").read_text(encoding="utf-8")
    assert "/case-details" in script and "recording_type" in script
    assert "description: box.dataset.description" in script
    assert "The voice listens on this type" in script
    assert "does not listen on this type" in script
    # One button sets the jail-call type (v1.149.0) through the same save.
    assert ".type-hint button[data-type]" in script and "function save(" in script
    css = (HERE / "static" / "app.css").read_text(encoding="utf-8")
    assert ".type-hint {" in css and ".type-hint button {" in css
    # One include carries the line on the three pages.
    for name in ("viewer.html", "speakers-page.html", "speakers-guided.html"):
        template = (HERE / "templates" / name).read_text(encoding="utf-8")
        assert '{% include "type-hint.html" %}' in template, name


def test_the_line_says_the_call_system_was_heard_and_offers_the_type(
    owner, a_case, check_on, client
):
    """v1.149.0: when the Call system's pass found an untyped recording by
    its phrases, the line says how many lines carried them and offers the
    jail-call type in one press; the button saves through the same endpoint."""
    recording = a_recording(owner, a_case)
    transcript = recording.transcript
    transcript.provenance = {
        "call_system": {"lines": 14, "phrases": 33, "found_by": "phrases", "heard": 13}
    }
    transcript.save(update_fields=["provenance"])
    hint = viewer.type_hint(recording)
    assert hint["heard"] == 13 and hint["suggested"] == "Jail call"
    signed_in(client, owner)
    for url in (f"/recording/{recording.pk}", f"/recording/{recording.pk}/speakers"):
        page = client.get(url).content.decode()
        assert "announcements were heard on 13 lines" in page, url
        assert 'data-type="Jail call"' in page and "Set the type to Jail call" in page
        assert LINE not in page
    # Found by the type, or never found: the plain line and no button.
    transcript.provenance = {
        "call_system": {"lines": 3, "found_by": "type", "heard": 3}
    }
    transcript.save(update_fields=["provenance"])
    hint = viewer.type_hint(recording)
    assert hint["heard"] == 0 and hint["suggested"] == ""
    page = client.get(f"/recording/{recording.pk}").content.decode()
    assert LINE in page and "data-type=" not in page
    # The office's list without a jail-call type: the words, no button.
    transcript.provenance = {"call_system": {"found_by": "phrases", "heard": 4}}
    transcript.save(update_fields=["provenance"])
    was = settings_store.get("recording_types")
    settings_store.set_to("recording_types", "Interview\nHearing")
    hint = viewer.type_hint(recording)
    assert hint["heard"] == 4 and hint["suggested"] == ""
    page = client.get(f"/recording/{recording.pk}").content.decode()
    assert "announcements were heard on 4 lines" in page and "data-type=" not in page
    settings_store.set_to("recording_types", was)
