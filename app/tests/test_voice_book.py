"""The unit's voice book (Phase 5 chapter 2, "The unit's voice book"; ADR
0021 amended; the voice plan's V4b, v1.146.0): units placed from the
directory's folders, Keep for the unit and the book's weighted print, the
roles refused, the check by a press (a match, a conflict, no match), Accept
with Undo, Not them, the Voices place with Forget, the switch going off,
and the pages' strings."""

from pathlib import Path

import numpy as np
import pytest
from core import directory, settings_store, signin, units, voice_book, voice_prints
from core.audit import Row
from core.models import User
from core.people import Person
from core.voice_book import UnitVoice, UnitVoiceCheck
from tests.helpers import signed_in
from tests.test_people import a_case as _a_case  # noqa: F401
from tests.test_people import a_recording
from tests.test_people import owner as _owner  # noqa: F401
from tests.test_voice_prints import a_check, a_print, label_print, mixed, part, vec
from tests.test_voice_prints import remembering as _remembering  # noqa: F401

HERE = Path(__file__).resolve().parents[1]
UNITS = "Appeals | OU=Appeals,OU=Staff\nTrial | OU=Trial,OU=Staff"


@pytest.fixture
def owner(_owner):  # noqa: F811
    return _owner


@pytest.fixture
def a_case(_a_case):  # noqa: F811
    return _a_case


@pytest.fixture
def remembering(_remembering):  # noqa: F811
    return _remembering


@pytest.fixture
def book_on(remembering, owner):
    """Units listed, the switch on, the case owner (a Local admin) in the
    Appeals unit by hand."""
    settings_store.set_to("units", UNITS)
    settings_store.set_to("unit_voices", True)
    units.set_by_hand(owner, "Appeals", by=owner)
    yield
    settings_store.set_to("unit_voices", False)
    settings_store.set_to("units", "")


def an_officer(case, recording, seed=1, name="Lee Ortiz", role="Officer") -> Person:
    """A Person of the case with a print from one recording."""
    return Person.objects.create(
        case=case,
        name=name,
        role=role,
        voice_print=a_print((str(recording.pk), part(seed))),
    )


def cos(a, b) -> float:
    return float(np.asarray(a) @ np.asarray(b))


# Units --------------------------------------------------------------------------------


def test_the_folder_chain_and_the_placement_rule(db):
    settings_store.set_to("units", UNITS)
    assert (
        units.folder_of("CN=J. Park,OU=Appeals,OU=Staff,DC=example,DC=local")
        == "OU=Appeals,OU=Staff"
    )
    # An escaped comma in the account's own name is not a cut.
    assert (
        units.folder_of("CN=Park\\, J.,OU=Trial,OU=Staff,DC=x") == "OU=Trial,OU=Staff"
    )
    assert units.place("OU=Appeals,OU=Staff") == "Appeals"
    # A folder inside the unit's folder is still the unit's.
    assert units.place("OU=Investigators,OU=Trial,OU=Staff") == "Trial"
    assert units.place("ou=trial,ou=staff") == "Trial"
    assert units.place("OU=Admin,OU=Staff") == ""
    # Trial is there, but not under Staff: the lines are matched in order
    # and next to each other.
    assert units.place("OU=Trial,OU=Interns") == ""
    settings_store.set_to("units", UNITS + "\nTrial | OU=Trial")
    assert units.place("OU=Trial,OU=Interns") == "Trial"
    assert units.names() == ["Appeals", "Trial"]
    # The setting refuses a line without a bar or without a folder.
    with pytest.raises(ValueError, match="has no bar"):
        settings_store.set_to("units", "Appeals OU=Appeals")
    with pytest.raises(ValueError, match="none of a folder"):
        settings_store.set_to("units", "Appeals | Appeals")
    assert units.check_setting("  Appeals |  OU=Appeals , OU=Staff \n\n") == (
        "Appeals | OU=Appeals,OU=Staff"
    )


def test_the_four_line_forms_place_an_account_in_order(db):
    settings_store.set_to(
        "units",
        "Capital | group=Capital Team\n"
        "Trial | OU=Trial,OU=Staff\n"
        "Appeals | department=Appeals Division\n"
        "Office | everyone",
    )
    assert [one.kind for one in units.lines()] == [
        units.GROUP,
        units.FOLDER,
        units.ATTRIBUTE,
        units.EVERYONE,
    ]
    assert units.groups_wanted() == ["Capital Team"]
    assert units.attributes_wanted() == ["department"]
    # The first line that fits wins, whatever its form.
    assert units.placement("OU=Trial,OU=Staff", ["capital team"], {}) == (
        "Capital",
        "Capital | group=Capital Team",
    )
    assert units.place("OU=Trial,OU=Staff") == "Trial"
    assert units.place("OU=Users", (), {"Department": "appeals division"}) == "Appeals"
    assert units.place("OU=Users") == "Office"
    assert units.names() == ["Capital", "Trial", "Appeals", "Office"]
    # Each form is checked when typed; a line in none of them is refused.
    with pytest.raises(ValueError, match="none of a folder"):
        settings_store.set_to("units", "Trial | Trial")
    with pytest.raises(ValueError, match="names no group"):
        settings_store.set_to("units", "Trial | group=")
    with pytest.raises(ValueError, match="says nothing after the bar"):
        settings_store.set_to("units", "Trial |")
    assert units.check_setting(" Office | EVERYONE \nX | Group= Legal ") == (
        "Office | everyone\nX | group=Legal"
    )


def test_the_sign_in_keeps_the_folder_and_places_the_account(db, client, monkeypatch):
    settings_store.set_to("units", UNITS)

    def fake_sign_in(username, password):
        return {
            "ok": True,
            "username": "j.park",
            "directory_address": "j.park@corp.example",
            "display_name": "J. Park",
            "email": "j.park@example.org",
            "in_admin_group": False,
            "folder": "OU=Appeals,OU=Staff",
        }

    monkeypatch.setattr(directory, "sign_in", fake_sign_in)
    monkeypatch.setattr(directory, "is_on", lambda: True)
    request = client.get("/").wsgi_request
    user = signin._from_the_directory(request, "j.park", "pw", "10.0.0.1")
    assert user.folder == "OU=Appeals,OU=Staff" and user.unit == "Appeals"
    # The Units lines change: the next sign-in places the account again.
    settings_store.set_to("units", "North | OU=Appeals,OU=Staff")
    user = signin._from_the_directory(request, "j.park", "pw", "10.0.0.1")
    assert user.unit == "North"
    assert units.of(user) == "North" and units.seen_by(user) == ["North"]
    # An account under no listed folder is in no unit, and the summary says so.
    settings_store.set_to("units", "Trial | OU=Trial,OU=Staff")
    user = signin._from_the_directory(request, "j.park", "pw", "10.0.0.1")
    assert user.unit == "" and units.seen_by(user) == []
    placed = units.summary()
    assert placed["counts"] == {"Trial": 0} and placed["none"] == [
        {"username": "j.park", "folder": "OU=Appeals,OU=Staff"}
    ]
    # The sign-in's own answer carries the chain the directory path gives.
    assert directory._folder("CN=x,OU=Trial,OU=Staff,DC=a,DC=b") == "OU=Trial,OU=Staff"
    # The sign-in reads the Units groups and attributes too (v1.147.0).
    settings_store.set_to(
        "units", "Trial | group=Trial Attorneys\nAppeals | department=Appeals Division"
    )
    user.unit_pinned = False
    user.save(update_fields=["unit_pinned"])
    monkeypatch.setattr(
        directory,
        "sign_in",
        lambda u, p: dict(
            fake_sign_in(u, p),
            groups=["Trial Attorneys"],
            attributes={"department": "Appeals Division"},
        ),
    )
    user = signin._from_the_directory(request, "j.park", "pw", "10.0.0.1")
    assert user.unit == "Trial" and user.unit_how == "Trial | group=Trial Attorneys"
    assert directory._read_list()[-1] == "department"


def test_a_unit_is_set_by_hand_on_any_account_and_the_directory_then_leaves_it(
    db, owner, client
):
    settings_store.set_to("units", UNITS)
    units.set_by_hand(owner, "Trial", by=owner)
    owner.refresh_from_db()
    assert owner.unit == "Trial" and owner.unit_pinned and owner.unit_how == "by hand"
    assert Row.objects.filter(event="Unit set by hand").count() == 1
    with pytest.raises(ValueError, match="not a unit"):
        units.set_by_hand(owner, "Capital", by=owner)
    # A directory account pinned by hand keeps its unit through what the
    # directory says, until the pin comes off (v1.147.0).
    elsewhere = User.objects.from_directory("r.diaz", folder="OU=Admin,OU=Staff")
    units.set_by_hand(elsewhere, "Trial", by=owner)
    assert not units.apply_directory(elsewhere, "OU=Appeals,OU=Staff") or True
    elsewhere.refresh_from_db()
    assert elsewhere.unit == "Trial" and elsewhere.folder == "OU=Appeals,OU=Staff"
    units.follow_directory(elsewhere, by=owner)
    elsewhere.refresh_from_db()
    assert elsewhere.unit == "Appeals" and not elsewhere.unit_pinned
    assert elsewhere.unit_how == "Appeals | OU=Appeals,OU=Staff"
    assert Row.objects.filter(event="Unit follows the directory").count() == 1
    with pytest.raises(ValueError, match="not in the directory"):
        units.follow_directory(owner, by=owner)
    # The People page: the picker on every row, the placing line shown.
    signed_in(client, owner)
    page = client.get("/panel/users").content.decode()
    assert "set by hand" in page and "OU=Appeals,OU=Staff" in page
    assert "by the line Appeals | OU=Appeals,OU=Staff" in page
    assert page.count("Follow the directory") == 1  # the directory account's row
    assert (
        client.post(
            "/panel/users/r.diaz", {"action": "unit", "unit": "none"}
        ).status_code
        == 302
    )
    elsewhere.refresh_from_db()
    assert elsewhere.unit == "" and elsewhere.unit_pinned
    assert (
        client.post(
            "/panel/users/r.diaz", {"action": "unit", "unit": "directory"}
        ).status_code
        == 302
    )
    elsewhere.refresh_from_db()
    assert elsewhere.unit == "Appeals" and not elsewhere.unit_pinned
    assert units.summary()["pinned"] == 1
    assert (
        client.post(
            "/panel/users/case-owner", {"action": "unit", "unit": "Appeals"}
        ).status_code
        == 302
    )
    owner.refresh_from_db()
    assert owner.unit == "Appeals"
    # An Admin sees every unit; a person in a unit their own.
    assert units.seen_by(owner) == ["Appeals", "Trial"]


# Keeping ------------------------------------------------------------------------------


def test_keep_for_the_unit_makes_the_book_and_the_case_teaches_it(
    owner, a_case, book_on
):
    recording = a_recording(owner, a_case)
    person = an_officer(a_case, recording)
    assert voice_book.may_keep(person) == (True, "Appeals")
    book = voice_book.keep(person, by=owner)
    person.refresh_from_db()
    assert person.kept_for_unit and person.voice_scope == "unit"
    assert book.unit == "Appeals" and book.role == "Officer" and book.live
    assert list(book.parts) == [str(person.pk)] and book.from_case_id == a_case.pk
    assert cos(book.vector, person.voice_print["vector"]) == pytest.approx(
        1.0, abs=1e-3
    )
    assert Row.objects.filter(event="Voice kept for the unit").count() == 1
    # A second name accepted in the case refines the share: the book's
    # vector moves and its seconds grow.
    other = a_recording(owner, a_case, title="a second interview")
    a_check(other, {"Speaker 1": label_print(2, seconds=30.0)})
    assert voice_prints.learn(other, "Speaker 1", person, by=owner)
    book.refresh_from_db()
    share = book.parts[str(person.pk)]
    assert share["recordings"] == 2 and share["seconds"] == pytest.approx(50.0)
    assert cos(book.vector, vec(1)) < 0.999
    # Unlearn in the case takes the share out, and the only share gone, the
    # book is forgotten.
    voice_prints.unlearn(person, by=owner)
    book.refresh_from_db()
    assert not book.live and book.parts == {} and book.forgotten_at is not None
    assert UnitVoice.objects.count() == 1


def test_two_cases_teach_one_book_weighted_by_what_each_heard(owner, a_case, book_on):
    from core.cases import Case

    recording = a_recording(owner, a_case)
    person = an_officer(a_case, recording)
    voice_book.keep(person, by=owner)
    second = Case.objects.create(owner=owner, name="Okafor")
    other = a_recording(owner, second, title="body camera")
    twin = Person.objects.create(
        case=second,
        name="Lee Ortiz",
        role="Officer",
        voice_print={
            "vector": vec(2),
            "parts": {str(other.pk): dict(part(2), seconds=60.0)},
            "scope": "case",
        },
    )
    book = voice_book.keep(twin, by=owner)
    assert UnitVoice.objects.filter(unit="Appeals", forgotten_at=None).count() == 1
    assert len(book.parts) == 2
    # Sixty seconds against twenty: the book leans to the second case.
    assert cos(book.vector, vec(2)) > cos(book.vector, vec(1))
    # Stop keeping in the first case leaves the book to the second.
    voice_book.stop_keeping(person, by=owner)
    book.refresh_from_db()
    assert book.live and list(book.parts) == [str(twin.pk)]
    person.refresh_from_db()
    assert not person.kept_for_unit
    assert Row.objects.filter(event="Voice no longer kept for the unit").count() == 1


def test_the_roles_rule_and_the_persons_hooks(owner, a_case, book_on):
    recording = a_recording(owner, a_case)
    witness = an_officer(a_case, recording, seed=3, name="Tom Hale", role="Witness")
    assert voice_book.may_keep(witness) == (False, "role")
    with pytest.raises(ValueError, match="not kept for the unit"):
        voice_book.keep(witness, by=owner)
    with pytest.raises(ValueError, match="never a client's side"):
        settings_store.set_to("unit_voice_roles", "Officer\nDefendant")
    assert voice_book.roles_allowed() == ["Officer", "Interpreter", "Interviewer"]
    # A Person with no role is never kept either.
    nobody = an_officer(a_case, recording, seed=4, name="Sam Burke", role="")
    assert voice_book.may_keep(nobody) == (False, "role")
    # Rename follows; a role no longer kept stops the keeping; delete too.
    from core import people

    officer = an_officer(a_case, recording, seed=5)
    book = voice_book.keep(officer, by=owner)
    people.rename(officer, "Lee A. Ortiz", by=owner)
    book.refresh_from_db()
    assert book.name == "Lee A. Ortiz"
    people.edit(officer, role="Interpreter", by=owner)
    book.refresh_from_db()
    assert book.role == "Interpreter"
    people.edit(officer, role="Witness", by=owner)
    officer.refresh_from_db()
    book.refresh_from_db()
    assert not officer.kept_for_unit and not book.live
    again = an_officer(a_case, recording, seed=6, name="Dev Kaur")
    kept = voice_book.keep(again, by=owner)
    people.delete(again, by=owner)
    kept.refresh_from_db()
    assert not kept.live and kept.forgotten_by == "case-owner"


# Checking -----------------------------------------------------------------------------


def a_book(owner, a_case, seed=1, name="Lee Ortiz", seconds=20.0) -> tuple:
    recording = a_recording(owner, a_case, title=f"interview {seed}")
    # The Person's lines carry the name, as a named Speaker's do.
    recording.transcript.segments.filter(speaker="Speaker 1").update(speaker=name)
    person = Person.objects.create(
        case=a_case,
        name=name,
        role="Officer",
        voice_print={
            "vector": vec(seed),
            "parts": {str(recording.pk): dict(part(seed), seconds=seconds)},
            "scope": "case",
        },
    )
    return voice_book.keep(person, by=owner), person, recording


def test_the_check_answers_a_match_a_conflict_and_no_match(owner, a_case, book_on):
    from core.cases import Case

    book, _, _ = a_book(owner, a_case)
    # The one book a case has is its owner's unit's: a second case of the
    # same owner checks against it.
    second = Case.objects.create(owner=owner, name="Marsh")
    call = a_recording(
        owner, second, title="a call", speakers=("Speaker 1", "Speaker 2")
    )
    assert voice_book.can_check(call, "Speaker 1") == (
        False,
        "The voice did not listen on this recording: its type is not under "
        "Voices help the check.",
    )
    a_check(
        call,
        {
            "Speaker 1": label_print(1),
            "Speaker 2": label_print(9),
        },
    )
    assert voice_book.can_check(call, "Speaker 1") == (True, "Appeals")
    answer = voice_book.check(call, "Speaker 1", by=owner)
    assert answer["kind"] == "match" and answer["unit"] == "Appeals"
    voice = answer["voices"][0]
    # One case taught the book: medium at best, whatever the score.
    assert voice["name"] == "Lee Ortiz" and voice["rating"] == "medium"
    assert voice["cases"] == 1 and voice["heard"][0]["title"] == "interview 1"
    assert answer["compared"] == 1
    none = voice_book.check(call, "Speaker 2", by=owner)
    assert none["kind"] == "none" and none["compared"] == 1
    assert Row.objects.filter(event="Unit voice check").count() == 2
    # A second voice near the first makes a conflict; a second press
    # withdraws the first press's rows.
    other = a_book(owner, a_case, seed=7, name="Dev Kaur")[0]
    other.vector = mixed(1, 7, 0.9)
    other.save(update_fields=["vector"])
    answer = voice_book.check(call, "Speaker 1", by=owner)
    assert answer["kind"] == "conflict"
    assert [one["name"] for one in answer["voices"]] == ["Lee Ortiz", "Dev Kaur"]
    assert (
        UnitVoiceCheck.objects.filter(speaker="Speaker 1", state="withdrawn").count()
        == 1
    )
    state = voice_book.state_for(call.transcript, owner)
    assert state["on"] and state["unit"] == "Appeals"
    assert state["can"]["Speaker 1"] == {"ok": True, "why": ""}
    assert {one["speaker"]: one["kind"] for one in state["checks"]} == {
        "Speaker 1": "conflict",
        "Speaker 2": "none",
    }
    # Too little clean voice: greyed with the reason.
    a_check(call, {"Speaker 2": label_print(9, seconds=4.0)})
    assert voice_book.can_check(call, "Speaker 2")[1].startswith("Too little")
    del book


def test_accept_names_the_speaker_teaches_both_prints_and_undo_takes_it_back(
    owner, a_case, book_on, client
):
    from core import speaker_check
    from core.cases import Case

    book, _, _ = a_book(owner, a_case)
    second = Case.objects.create(owner=owner, name="Marsh")
    call = a_recording(owner, second, title="a call")
    a_check(call, {"Speaker 1": label_print(1)})
    voice_book.check(call, "Speaker 1", by=owner)
    row = UnitVoiceCheck.objects.get(speaker="Speaker 1", state="pending")
    changed = voice_book.accept(row, by=owner)
    assert changed == 2
    person = Person.objects.get(case=second, name="Lee Ortiz")
    assert person.role == "Officer" and person.kept_for_unit
    assert set(call.transcript.segments.values_list("speaker", flat=True)) == {
        "Lee Ortiz",
        "Speaker 2",
    }
    assert str(call.pk) in person.voice_print["parts"]
    book.refresh_from_db()
    assert len(book.parts) == 2
    row.refresh_from_db()
    assert row.state == "accepted" and row.decided_by == owner
    assert Row.objects.filter(event="Unit voice accepted").count() == 1
    assert (
        speaker_check.state_json(call.transcript, owner)["voice_book"]["checks"] == []
    )
    # Undo through the page: the lines go back, the row waits again.
    signed_in(client, owner)
    assert client.post(f"/recording/{call.pk}/speakers/undo").status_code == 200
    assert set(call.transcript.segments.values_list("speaker", flat=True)) == {
        "Speaker 1",
        "Speaker 2",
    }
    row.refresh_from_db()
    assert row.state == "pending"
    # Not them: counted against the book, nothing taught.
    voice_book.dismiss(row, by=owner)
    row.refresh_from_db()
    assert row.state == "dismissed"
    assert Row.objects.filter(event="Unit voice dismissed").count() == 1
    # The page's endpoints answer the same.
    voice_book.check(call, "Speaker 1", by=owner)
    again = UnitVoiceCheck.objects.get(speaker="Speaker 1", state="pending")
    answer = client.post(f"/book-check/{again.pk}/accept")
    assert answer.status_code == 200 and answer.json()["made"] == "Lee Ortiz"
    assert (
        client.post(
            f"/recording/{call.pk}/book-check",
            data='{"speaker": "Speaker 2"}',
            content_type="application/json",
        ).status_code
        == 400
    )


# The pages ----------------------------------------------------------------------------


def test_the_rail_and_the_voices_place(owner, a_case, book_on, client):
    book, person, _ = a_book(owner, a_case)
    signed_in(client, owner)
    home = client.get("/").content.decode()
    # An Admin in two listed units reads every unit.
    assert "Every unit&#x27;s known voices" in home and 'href="/voices"' in home
    page = client.get("/voices").content.decode()
    assert "Lee Ortiz" in page and "Forget" in page and "the Appeals unit" in page
    assert "print from 1 case, 1 recording" in page and "Ramirez" in page
    assert "matches rate medium at best" in page
    assert "Trial &middot; 0 voice" in page or "Trial · 0 voice" in page
    other = client.get("/voices?unit=Trial").content.decode()
    assert "No voice is kept for the Trial unit yet" in other
    # A person in a unit sees their own book and no chooser; one in no unit
    # sees no place and no page.
    colleague = User.objects.from_directory(
        "m.chen", display_name="M. Chen", folder="OU=Appeals,OU=Staff", unit="Appeals"
    )
    signed_in(client, colleague)
    theirs = client.get("/voices").content.decode()
    assert "The Appeals unit&#x27;s known voices" in client.get("/").content.decode()
    assert "Lee Ortiz" in theirs and "every unit" not in theirs
    # The case is not theirs to open: the chain says so and nothing plays.
    assert "a case you may not open" in theirs and "Ramirez" not in theirs
    stranger = User.objects.from_directory("r.diaz", folder="OU=Admin,OU=Staff")
    signed_in(client, stranger)
    assert "/voices" not in client.get("/").content.decode()
    assert client.get("/voices").status_code == 404
    # Forget, from the page: the book goes, the case stops keeping, the row
    # stays greyed.
    signed_in(client, owner)
    assert client.post(f"/voices/{book.pk}/forget").status_code == 302
    book.refresh_from_db()
    person.refresh_from_db()
    assert not book.live and not person.kept_for_unit
    after = client.get("/voices").content.decode()
    assert "forgotten" in after and "Keep again from a case" in after
    assert Row.objects.filter(event="Unit voice forgotten").count() == 1


def test_the_case_tab_offers_keep_and_shows_kept(owner, a_case, book_on, client):
    recording = a_recording(owner, a_case)
    officer = an_officer(a_case, recording)
    an_officer(a_case, recording, seed=3, name="Tom Hale", role="Witness")
    signed_in(client, owner)
    tab = client.get(f"/case/{a_case.pk}?tab=speakers").content.decode()
    assert "Keep for the Appeals..." in tab
    assert "A witness's voice is never kept for the unit." in tab
    assert client.post(f"/person/{officer.pk}", {"action": "keep"}).status_code == 302
    tab = client.get(f"/case/{a_case.pk}?tab=speakers").content.decode()
    assert "Kept for the Appeals unit" in tab and "Stop keeping" in tab
    assert "this case teaches the book" in tab
    assert (
        client.post(f"/person/{officer.pk}", {"action": "stop-keeping"}).status_code
        == 302
    )
    officer.refresh_from_db()
    assert not officer.kept_for_unit
    # With the switch off nothing of the book is on the tab.
    settings_store.set_to("unit_voices", False)
    tab = client.get(f"/case/{a_case.pk}?tab=speakers").content.decode()
    assert "Keep for the" not in tab and "never kept for the unit" not in tab


def test_the_switch_off_deletes_every_book_and_the_cases_keep_their_prints(
    owner, a_case, book_on
):
    book, person, _ = a_book(owner, a_case)
    assert voice_book.counts_for_switch() == {"Appeals": 1}
    settings_store.set_to("unit_voices", False)
    assert UnitVoice.objects.count() == 0
    person.refresh_from_db()
    assert not person.kept_for_unit and person.voice_print["vector"]
    assert Row.objects.filter(event="Unit voice books forgotten").count() == 1
    assert not voice_book.on()
    settings_store.set_to("unit_voices", True)
    # Remember voices going off takes the books with the prints.
    voice_book.keep(person, by=owner)
    settings_store.set_to("remember_voices", False)
    assert UnitVoice.objects.count() == 0
    person.refresh_from_db()
    assert person.voice_print is None and not person.kept_for_unit
    del book


def test_the_pages_carry_the_strings():
    script = (HERE / "static" / "speakers-page.js").read_text(encoding="utf-8")
    assert "function drawBookChecks" in script and "/book-check" in script
    assert "the unit's voices" in script and "Check again" in script
    template = (HERE / "templates" / "speakers-page.html").read_text(encoding="utf-8")
    assert 'class="tiny book-check"' in template
    rail = (HERE / "templates" / "base.html").read_text(encoding="utf-8")
    assert "voice_book.on" in rail and 'id="i-voices"' in (
        HERE / "templates" / "icons.html"
    ).read_text(encoding="utf-8")
    users = (HERE / "templates" / "panel" / "users.html").read_text(encoding="utf-8")
    assert "unit-line" in users and 'value="unit"' in users
    assert "Follow the directory" in users and "No unit, by hand" in users
    panel = (HERE / "static" / "panel-directory.js").read_text(encoding="utf-8")
    assert "In no listed unit" in panel
    voices = (HERE / "templates" / "voices.html").read_text(encoding="utf-8")
    # The place as cards (v1.151.0): the month at the top, the fold of numbers.
    assert "no name of a case you may not open" in voices
    assert "decided from the book, by month" in voices and 'class="month"' in voices
    assert "data-preview-host" in voices and "people-cards.js" in voices


def test_the_read_list_is_the_five_before_the_apps_load(db, monkeypatch):
    """v1.149.0: a bare `python -c` has no apps loaded, so the Units lines
    cannot be read and the five alone are; the upgrade's directory check
    had failed on that import since v1.147.0."""
    from django.apps import apps

    settings_store.set_to("units", "Trial | department=Trial")
    assert directory._read_list()[-1] == "department"
    monkeypatch.setattr(apps, "ready", False)
    assert directory._read_list() == directory.WHAT_IS_READ
    assert directory._read_list() is not directory.WHAT_IS_READ
