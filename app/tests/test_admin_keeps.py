"""v1.157.0: an Admin keeps a voice for any unit, or several (Phase 5
chapter 2, "Keep for the unit", amended; the drawing
phase-5-admin-keeps-for-any-unit.html). Everyone else keeps for the case
owner's unit only, as before."""

from __future__ import annotations

import pytest
from core import units, voice_book, voice_prints
from core.audit import Row
from core.cases import Case
from core.models import User
from core.people import Person
from core.voice_book import UnitVoice
from tests.helpers import signed_in
from tests.test_people import a_case as _a_case  # noqa: F401
from tests.test_people import owner as _owner  # noqa: F401
from tests.test_voice_book import (
    a_recording,
    an_officer,
    book_on,  # noqa: F401
)
from tests.test_voice_prints import a_check, label_print
from tests.test_voice_prints import remembering as _remembering  # noqa: F401


@pytest.fixture
def owner(_owner):  # noqa: F811
    return _owner


@pytest.fixture
def a_case(_a_case):  # noqa: F811
    return _a_case


@pytest.fixture
def remembering(_remembering):  # noqa: F811
    return _remembering


def nobody_s_unit(owner):  # noqa: F811
    """The Admin who owns the case is in no unit: the drawing's own case."""
    units.set_by_hand(owner, "", by=owner)


def a_colleague(unit="Appeals") -> User:
    return User.objects.from_directory(
        "m.chen", display_name="M. Chen", folder=f"OU={unit},OU=Staff", unit=unit
    )


def test_an_admin_keeps_for_the_units_they_tick(owner, a_case, book_on):  # noqa: F811
    nobody_s_unit(owner)
    recording = a_recording(owner, a_case)
    person = an_officer(a_case, recording)
    # The case's own unit refuses, the Admin's choice does not.
    assert voice_book.may_keep(person) == (False, "no unit")
    assert voice_book.units_offered(person, owner) == ["Appeals", "Trial"]
    books = voice_book.keep_for(person, ["Trial", "Appeals"], by=owner)
    assert sorted(one.unit for one in books) == ["Appeals", "Trial"]
    person.refresh_from_db()
    assert person.kept_for_unit and person.voice_scope == "unit"
    # Held in the Admin's order of units, whatever order was ticked.
    assert voice_book.units_kept(person) == ["Appeals", "Trial"]
    assert Row.objects.filter(event="Voice kept for the unit").count() == 2
    assert voice_book.units_offered(person, owner) == []
    line = voice_book.tab_line(person, owner)
    assert line["state"] == "kept" and line["units"] == ["Appeals", "Trial"]
    assert line["more"] == [] and line["admin"] and line["mine"]
    # A unit already holding them is passed over, not kept twice.
    assert voice_book.keep_for(person, ["Trial"], by=owner) == []
    assert UnitVoice.objects.filter(forgotten_at=None).count() == 2
    # This case teaches both books.
    other = a_recording(owner, a_case, title="a second interview")
    a_check(other, {"Speaker 1": label_print(2, seconds=30.0)})
    assert voice_prints.learn(other, "Speaker 1", person, by=owner)
    for book in UnitVoice.objects.filter(forgotten_at=None):
        assert book.parts[str(person.pk)]["recordings"] == 2
    # Stop keeping for one unit leaves the other holding them, kept still.
    assert voice_book.stop_keeping(person, by=owner, unit="Appeals")
    person.refresh_from_db()
    assert person.kept_for_unit and voice_book.units_kept(person) == ["Trial"]
    appeals = UnitVoice.objects.get(unit="Appeals")
    assert not appeals.live and appeals.forgotten_by == "case-owner"
    assert Row.objects.filter(event="Voice no longer kept for the unit").count() == 1
    assert voice_book.tab_line(person, owner)["more"] == ["Appeals"]
    # Also keep for brings the unit back; stop keeping the last unit ends it.
    assert [one.unit for one in voice_book.keep_for(person, ["Appeals"], by=owner)] == [
        "Appeals"
    ]
    assert voice_book.units_kept(person) == ["Appeals", "Trial"]
    assert voice_book.stop_keeping(person, by=owner)
    person.refresh_from_db()
    assert not person.kept_for_unit and voice_book.units_kept(person) == []
    assert UnitVoice.objects.filter(forgotten_at=None).count() == 0


def test_everyone_else_keeps_for_the_owners_unit_only(owner, a_case, book_on):  # noqa: F811
    recording = a_recording(owner, a_case)
    person = an_officer(a_case, recording)
    colleague = a_colleague()
    assert voice_book.units_offered(person, colleague) == ["Appeals"]
    with pytest.raises(ValueError, match="Only an Admin"):
        voice_book.keep_for(person, ["Trial"], by=colleague)
    with pytest.raises(ValueError, match="not a unit the Admin has listed"):
        voice_book.keep_for(person, ["Capital"], by=owner)
    with pytest.raises(ValueError, match="at least one unit"):
        voice_book.keep_for(person, ["", "  "], by=owner)
    # The person's own rule holds for an Admin too: a print is needed. The
    # role is not (ADR 0024, v1.158.0).
    witness = an_officer(a_case, recording, seed=3, name="Tom Hale", role="Witness")
    assert voice_book.units_offered(witness, owner) == ["Appeals", "Trial"]
    unprinted = Person.objects.create(case=a_case, name="Kim Vale", role="Officer")
    assert voice_book.units_offered(unprinted, owner) == []
    with pytest.raises(ValueError, match="no voice print yet"):
        voice_book.keep_for(unprinted, ["Appeals"], by=owner)
    # A colleague in a unit the person is kept for sees it as theirs; one in
    # another unit sees it kept for a unit they are not in.
    voice_book.keep_for(person, ["Trial"], by=owner)
    assert voice_book.tab_line(person, a_colleague("Trial"))["mine"] is False
    line = voice_book.tab_line(person, colleague)
    assert line["state"] == "kept" and line["units"] == ["Trial"]
    assert line["mine"] is True and line["more"] == []


def test_forget_on_one_unit_leaves_the_other_holding_them(owner, a_case, book_on):  # noqa: F811
    nobody_s_unit(owner)
    recording = a_recording(owner, a_case)
    person = an_officer(a_case, recording)
    voice_book.keep_for(person, ["Appeals", "Trial"], by=owner)
    trial = UnitVoice.objects.get(unit="Trial")
    assert voice_book.forget(trial, by=owner) == 0
    person.refresh_from_db()
    assert person.kept_for_unit and voice_book.units_kept(person) == ["Appeals"]
    appeals = UnitVoice.objects.get(unit="Appeals")
    assert voice_book.forget(appeals, by=owner) == 1
    person.refresh_from_db()
    assert not person.kept_for_unit
    # A rename follows into every book that holds them.
    again = an_officer(a_case, recording, seed=5, name="Dev Kaur")
    voice_book.keep_for(again, ["Appeals", "Trial"], by=owner)
    from core import people

    people.rename(again, "Dev A. Kaur", by=owner)
    assert sorted(
        UnitVoice.objects.filter(forgotten_at=None).values_list("name", flat=True)
    ) == ["Dev A. Kaur", "Dev A. Kaur"]


def test_the_pages_offer_the_chooser_to_an_admin_only(owner, a_case, book_on, client):  # noqa: F811
    nobody_s_unit(owner)
    recording = a_recording(owner, a_case)
    officer = an_officer(a_case, recording)
    signed_in(client, owner)
    tab = client.get(f"/case/{a_case.pk}?tab=speakers").content.decode()
    assert "Keep for a unit..." in tab and "Keep for the Appeals..." not in tab
    assert "data-confirm-choices" in tab and "Keep for {n} unit{s}" in tab
    assert "&quot;value&quot;: &quot;Trial&quot;" in tab
    # No unit of the case's own: nothing is ticked first.
    assert "&quot;checked&quot;: true" not in tab
    assert (
        client.post(
            f"/person/{officer.pk}", {"action": "keep", "unit": ["Appeals", "Trial"]}
        ).status_code
        == 302
    )
    tab = client.get(f"/case/{a_case.pk}?tab=speakers").content.decode()
    assert "Kept for the <b>Appeals</b> and <b>Trial</b> units" in tab
    assert "this case teaches both books" in tab and "Stop keeping, per unit," in tab
    assert "Stop keeping for the Trial unit" in tab and "Also keep for" not in tab
    assert (
        client.post(
            f"/person/{officer.pk}", {"action": "stop-keeping", "unit": "Trial"}
        ).status_code
        == 302
    )
    tab = client.get(f"/case/{a_case.pk}?tab=speakers").content.decode()
    assert "Kept for the <b>Appeals</b> unit since" in tab
    assert "Also keep for the Trial unit" in tab
    assert (
        client.post(
            f"/person/{officer.pk}", {"action": "keep", "unit": "Trial"}
        ).status_code
        == 302
    )
    officer.refresh_from_db()
    assert voice_book.units_kept(officer) == ["Appeals", "Trial"]
    # The Voices place says where else the voice is kept, and who kept it.
    place = client.get("/voices?unit=Trial").content.decode()
    assert "also kept for the Appeals unit" in place and "(Admin)" in place
    # With the owner in a unit, that unit is ticked first.
    units.set_by_hand(owner, "Trial", by=owner)
    another = an_officer(a_case, recording, seed=6, name="Sam Burke", role="")
    tab = client.get(f"/case/{a_case.pk}?tab=speakers").content.decode()
    assert "this case&#x27;s unit" in tab or "this case's unit" in tab
    # A person with no role is offered too (ADR 0024), and the box does not
    # read "Their role, , goes with the voice".
    assert another.name in tab and "role, ," not in tab
    assert "Their notes and this case's name do not go with the voice." in tab
    # Everyone else sees the one button for their own unit.
    colleague = a_colleague()
    theirs = Case.objects.create(owner=colleague, name="Okafor")
    their_recording = a_recording(colleague, theirs, title="body camera")
    an_officer(theirs, their_recording, seed=7, name="Pat Doyle")
    signed_in(client, colleague)
    tab = client.get(f"/case/{theirs.pk}?tab=speakers").content.decode()
    assert "Keep for the Appeals..." in tab and "Keep for a unit" not in tab
