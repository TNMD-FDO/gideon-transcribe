"""Summary templates by Recording type.

The app ships a template per Recording type; a template says which types it
is for; the viewer chooses the type's template and lists it first; an
Admin's own template joins in for its types from the moment it is added; a
shipped template resets to its own wording; a type that leaves the setting
stays on the template.
"""

from __future__ import annotations

import pytest
from core import assistant, prompts, settings_store
from core.assistant import SummaryTemplate
from core.audit import Row
from core.cases import Case
from core.jobs import Segment, Transcript
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording

PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"


@pytest.fixture
def admin(db):
    return User.objects.create_local_admin("asker", PASSWORD)


@pytest.fixture
def on(db):
    settings_store.set_to("assistant_available", True)
    settings_store.set_to("folder_management", True)


def a_recording(person, recording_type="", case=None):
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        case=case,
        title="A call",
        original_filename="call.m4a",
        media_state=MediaState.READY,
        recording_type=recording_type,
    )
    transcript = Transcript.objects.create(recording=recording, language="en")
    Segment.objects.create(
        transcript=transcript, start=0, end=1, text="Hi", speaker="A"
    )
    return recording


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def test_the_shipped_templates_are_there_enabled_and_for_their_types(db):
    SummaryTemplate.shipped()
    keys = dict(SummaryTemplate.objects.values_list("key", "recording_types"))
    assert keys == {
        "standard": [],
        "jail_call": ["Jail call"],
        "body_camera": ["Body camera"],
        "interview": ["Interview"],
        "phone_call": ["Phone call"],
        "hearing": ["Hearing"],
        "dictation": ["Dictation"],
    }
    assert SummaryTemplate.objects.filter(built_in=True, enabled=True).count() == 7
    assert SummaryTemplate.the_default().key == "standard"
    # Made once: asking again makes nothing.
    SummaryTemplate.shipped()
    assert SummaryTemplate.objects.count() == 7
    for one in SummaryTemplate.objects.exclude(key="standard"):
        assert one.text == prompts.SHIPPED_SUMMARIES[one.key]
        assert "Unclear parts" in one.text and "Overview" in one.text


def test_the_type_chooses_the_template_and_no_type_keeps_the_default(db, admin):
    case = Case.objects.create(owner=admin, name="Ramirez")
    jail = a_recording(admin, "Jail call", case)
    plain = a_recording(admin)
    assert SummaryTemplate.chosen_for(jail).key == "jail_call"
    assert SummaryTemplate.chosen_for(plain).key == "standard"
    # Matching is by name, whatever the case of the letters.
    jail.recording_type = "JAIL CALL"
    assert SummaryTemplate.chosen_for(jail).key == "jail_call"
    # A Disabled template is not chosen.
    row = SummaryTemplate.objects.get(key="jail_call")
    row.enabled = False
    row.save()
    assert SummaryTemplate.chosen_for(jail).key == "standard"
    # Two for one type: the Default first, else by name.
    row.enabled = True
    row.save()
    SummaryTemplate.objects.create(
        name="Alpha jail brief", text="Three lines.", recording_types=["Jail call"]
    )
    assert [one.name for one in SummaryTemplate.for_type("Jail call")] == [
        "Alpha jail brief",
        "Jail call summary",
    ]
    row.make_default()
    assert SummaryTemplate.for_type("Jail call")[0].key == "jail_call"


def test_the_viewer_lists_the_types_template_first_and_says_why(on, admin, client):
    case = Case.objects.create(owner=admin, name="Ramirez")
    jail = a_recording(admin, "Jail call", case)
    signed_in(client, admin)
    state = client.get(f"/recording/{jail.pk}/assistant").json()
    first = state["templates"][0]
    assert first["name"] == "Jail call summary" and first["for_type"] is True
    assert state["default_template"] == first["id"]
    assert (
        state["type_line"] == "This is a jail call, so the Jail call summary is chosen."
    )
    assert sum(1 for one in state["templates"] if one["for_type"]) == 1

    plain = a_recording(admin)
    state = client.get(f"/recording/{plain.pk}/assistant").json()
    assert state["type_line"] == ""
    assert state["default_template"] == str(SummaryTemplate.the_default().pk)


def test_an_admins_template_joins_for_its_types_at_once(on, admin, client):
    signed_in(client, admin)
    client.post(
        "/panel/templates/summary",
        {
            "name": "Hearing brief",
            "description": "Rulings only",
            "text": "List every ruling with its time.",
            "types": ["Hearing", "Interview"],
        },
    )
    added = SummaryTemplate.objects.get(name="Hearing brief")
    # Kept in the Recording types list's own order.
    assert added.recording_types == ["Interview", "Hearing"]
    assert added in SummaryTemplate.for_type("Hearing")
    assert added in SummaryTemplate.for_type("Interview")
    row = Row.objects.filter(event="summary template added").get()
    assert row.details["types"] == ["Interview", "Hearing"]
    assert "ruling" not in str(row.details)

    # Saving with other ticks changes what it is for, and says so.
    client.post(
        f"/panel/templates/summary/{added.pk}",
        {
            "action": "save",
            "name": "Hearing brief",
            "description": "Rulings only",
            "text": "List every ruling with its time.",
            "types": ["Hearing"],
        },
    )
    added.refresh_from_db()
    assert added.recording_types == ["Hearing"]
    assert Row.objects.filter(event="summary template saved").get().details[
        "types"
    ] == ["Hearing"]

    # The page offers the ticks, from the setting's list.
    page = client.get("/panel/templates").content.decode()
    assert 'name="types" value="Jail call"' in page
    assert "For recording types" in page


def test_a_type_that_leaves_the_setting_stays_on_the_template(on, admin, client):
    SummaryTemplate.shipped()
    settings_store.set_to("recording_types", "Interview\nHearing")
    hearing = SummaryTemplate.objects.get(key="jail_call")
    assert hearing.recording_types == ["Jail call"]
    signed_in(client, admin)
    page = client.get("/panel/templates").content.decode()
    assert "no longer listed" in page
    # Saving the row keeps the greyed type, because the page still sent it.
    client.post(
        f"/panel/templates/summary/{hearing.pk}",
        {
            "action": "save",
            "description": hearing.description,
            "text": hearing.text,
            "types": ["Jail call"],
        },
    )
    hearing.refresh_from_db()
    assert hearing.recording_types == ["Jail call"]


def test_a_shipped_template_resets_to_its_own_wording(on, admin, client):
    SummaryTemplate.shipped()
    row = SummaryTemplate.objects.get(key="body_camera")
    signed_in(client, admin)
    client.post(
        f"/panel/templates/summary/{row.pk}",
        {
            "action": "save",
            "description": row.description,
            "text": "Something else.",
            "types": ["Body camera"],
        },
    )
    row.refresh_from_db()
    assert row.text == "Something else." and row.version == 2
    client.post(f"/panel/templates/summary/{row.pk}", {"action": "reset"})
    row.refresh_from_db()
    assert row.text == prompts.SHIPPED_SUMMARIES["body_camera"] and row.version == 3
    # Never deleted.
    client.post(f"/panel/templates/summary/{row.pk}", {"action": "delete"})
    assert SummaryTemplate.objects.filter(pk=row.pk).exists()
    assert assistant.SummaryTemplate.standard().key == "standard"
