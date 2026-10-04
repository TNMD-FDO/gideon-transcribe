"""The Team, Assigned to and Reviewed (Phase 9 chapter 3)."""

from __future__ import annotations

import pytest
from core import assignments, audit, dashboard, settings_store, sharing
from core.cases import Case
from core.jobs import Segment, Transcript
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording
from django.urls import reverse
from django.utils import timezone

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


def a_call(owner, case, title, words=True):
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
    if words:
        transcript = Transcript.objects.create(recording=recording, language="en")
        Segment.objects.create(
            transcript=transcript, start=0, end=4, text="Hey.", speaker="Pike"
        )
    return recording


def signed_in(client, person):
    client.force_login(person)
    LoginSession.objects.create(user=person, session_key=client.session.session_key)


def rows(event):
    return audit.Row.objects.filter(event=event)


# The gate --------------------------------------------------------------------------


def test_who_may_direct_and_who_may_run(a_case, owner, friend, third):
    share = sharing.grant(a_case, friend, actor=owner)
    assert a_case.may_direct(owner) and a_case.may_be_run_by(owner)
    assert not a_case.may_direct(friend)
    assignments.set_also_owner(share, True, by=owner)
    assert a_case.may_direct(friend)
    assert not a_case.may_be_run_by(friend)
    assert not a_case.may_direct(third)
    assert rows("case owner added").get().details["collaborator"] == "ben"
    # Sharing off hides the mark with the Share.
    settings_store.set_to("sharing", False)
    assert not a_case.may_direct(friend)


def test_only_the_owner_marks_an_also_owner(a_case, owner, friend, third, client):
    share = sharing.grant(a_case, friend, actor=owner)
    other = sharing.grant(a_case, third, actor=owner)
    assignments.set_also_owner(share, True, by=owner)
    signed_in(client, friend)
    refused = client.post(
        reverse("share-owner", args=[a_case.pk]), {"share": other.pk, "also_owner": "1"}
    )
    assert refused.status_code == 404
    # But an also-owner may add people.
    assert client.get(reverse("share-who", args=[a_case.pk])).status_code == 200
    signed_in(client, owner)
    answer = client.post(
        reverse("share-owner", args=[a_case.pk]), {"share": other.pk, "also_owner": "1"}
    )
    assert answer.json()["also_owner"] is True
    client.post(
        reverse("share-owner", args=[a_case.pk]), {"share": other.pk, "also_owner": ""}
    )
    assert rows("case owner removed").count() == 1


# Assigning ---------------------------------------------------------------------------


def test_one_ticked_and_unassign(a_case, owner, friend, third, client):
    sharing.grant(a_case, friend, actor=owner)
    first = a_call(owner, a_case, "Call 0409")
    second = a_call(owner, a_case, "Call 0417")
    signed_in(client, owner)
    answer = client.post(
        reverse("assign-recordings", args=[a_case.pk]),
        {"recordings": str(first.pk), "who": "Ben Cole"},
    )
    assert answer.json()["changed"] == 1
    first.refresh_from_db()
    assert first.assigned_to == friend and first.assigned_by == owner
    row = rows("recording assigned").get()
    assert row.details == {"to": "ben", "cause": "one"}
    assert "Call 0409" not in str(row.details)

    answer = client.post(
        reverse("assign-recordings", args=[a_case.pk]),
        {"recordings": f"{first.pk},{second.pk}", "who": "ana"},
    )
    assert answer.json()["changed"] == 2
    assert rows("recording assigned").filter(details__cause="ticked").count() == 2

    # Not on the team: refused and nothing changes.
    refused = client.post(
        reverse("assign-recordings", args=[a_case.pk]),
        {"recordings": str(first.pk), "who": "cy"},
    )
    assert refused.status_code == 400

    client.post(
        reverse("assign-recordings", args=[a_case.pk]),
        {"recordings": str(first.pk), "who": ""},
    )
    first.refresh_from_db()
    assert first.assigned_to is None
    assert rows("recording unassigned").get().details["cause"] == "owner"

    # A Collaborator may not assign.
    signed_in(client, friend)
    assert (
        client.post(
            reverse("assign-recordings", args=[a_case.pk]),
            {"recordings": str(first.pk), "who": "ben"},
        ).status_code
        == 404
    )


def test_divide_deals_the_unassigned_evenly_oldest_first(
    a_case, owner, friend, third, client
):
    sharing.grant(a_case, friend, actor=owner)
    sharing.grant(a_case, third, actor=owner)
    calls = [a_call(owner, a_case, f"Call {n:04d}") for n in range(7)]
    # One already given stays where it is.
    assignments.assign(calls[2], owner, by=owner)
    signed_in(client, owner)
    answer = client.post(
        reverse("divide-recordings", args=[a_case.pk]), {"who": "ben,cy,nobody-here"}
    )
    counts = answer.json()["counts"]
    assert counts == {"ben": 3, "cy": 3}
    for call in calls:
        call.refresh_from_db()
    assert calls[2].assigned_to == owner
    # Oldest first, in turn: 0 ben, 1 cy, 3 ben, 4 cy, 5 ben, 6 cy.
    assert [one.assigned_to.username for one in calls] == [
        "ben",
        "cy",
        "ana",
        "ben",
        "cy",
        "ben",
        "cy",
    ]
    divided = rows("recording assigned").filter(details__cause="divided")
    assert divided.count() == 6
    assert len({row.details["divide"] for row in divided}) == 1


def test_removing_a_person_clears_their_assignments_and_transfer_keeps_them(
    a_case, owner, friend, third
):
    share = sharing.grant(a_case, friend, actor=owner)
    sharing.grant(a_case, third, actor=owner)
    first = a_call(owner, a_case, "Call 0409")
    second = a_call(owner, a_case, "Call 0417")
    assignments.assign(first, friend, by=owner)
    assignments.assign(second, third, by=owner)
    sharing.transfer(a_case, third, actor=owner)
    second.refresh_from_db()
    assert second.assigned_to == third
    sharing.revoke(share, actor=owner)
    first.refresh_from_db()
    assert first.assigned_to is None
    assert rows("recording unassigned").get().details["cause"] == "share revoked"


def test_a_move_to_another_case_clears_the_assignment(a_case, owner, friend, client):
    sharing.grant(a_case, friend, actor=owner)
    other = Case.objects.create(owner=owner, name="Other matter")
    call = a_call(owner, a_case, "Call 0409")
    assignments.assign(call, friend, by=owner)
    signed_in(client, owner)
    answer = client.post(reverse("move-to-case", args=[call.pk]), {"case": other.pk})
    assert answer.json()["ok"] is True
    call.refresh_from_db()
    assert call.case == other and call.assigned_to is None
    assert rows("recording unassigned").get().details["cause"] == "moved"


# Reviewed -----------------------------------------------------------------------------


def test_the_assignee_marks_reviewed_after_the_question_and_takes_it_back(
    a_case, owner, friend, third, client
):
    sharing.grant(a_case, friend, actor=owner)
    sharing.grant(a_case, third, actor=owner)
    first = a_call(owner, a_case, "Call 0409")
    second = a_call(owner, a_case, "Call 0417")
    assignments.assign(first, friend, by=owner)
    assignments.assign(second, friend, by=owner)
    signed_in(client, friend)
    page = client.get(reverse("viewer", args=[first.pk])).content.decode()
    assert "Assigned to you" in page and 'id="mark-reviewed"' in page
    assert 'data-notes="0"' in page

    answer = client.post(
        reverse("mark-reviewed", args=[first.pk]), {"action": "mark", "nothing": "1"}
    ).json()
    assert answer["reviewed"] is True
    assert answer["words"].startswith("Reviewed by you, ")
    assert answer["next"]["title"] == "Call 0417"
    first.refresh_from_db()
    assert first.reviewed_by == friend and first.reviewed_nothing_to_note
    row = rows("recording marked reviewed").get()
    assert row.details == {"cause": "assignee", "nothing_to_note": True}

    page = client.get(reverse("viewer", args=[first.pk])).content.decode()
    assert "Reviewed by you," in page

    answer = client.post(
        reverse("mark-reviewed", args=[first.pk]), {"action": "unmark"}
    ).json()
    assert answer["reviewed"] is False
    first.refresh_from_db()
    assert first.reviewed_on is None
    assert rows("recording marked not reviewed").count() == 1

    # Somebody else on the team may not mark; the owner may, for anyone.
    signed_in(client, third)
    assert client.post(reverse("mark-reviewed", args=[first.pk]), {}).status_code == 404
    signed_in(client, owner)
    answer = client.post(reverse("mark-reviewed", args=[first.pk]), {}).json()
    assert answer["reviewed"] is True
    assert rows("recording marked reviewed").latest("at").details["cause"] == "owner"

    # A new assignee clears the mark.
    assignments.assign(first, third, by=owner)
    first.refresh_from_db()
    assert first.reviewed_on is None


def test_the_question_counts_the_persons_own_notes(a_case, owner, friend, client):
    sharing.grant(a_case, friend, actor=owner)
    call = a_call(owner, a_case, "Call 0409")
    assignments.assign(call, friend, by=owner)
    line = call.transcript.segments.first()
    line.note = "worth a look"
    line.note_by = friend
    line.save()
    assert assignments.my_notes_on(call, friend) == 1
    assert assignments.my_notes_on(call, owner) == 0


# The page, Home and the list ----------------------------------------------------------


def test_two_members_with_one_name_are_told_apart_by_the_username(
    a_case, owner, friend, client
):
    """v1.121.3: the username beside the shown name wherever assignment names
    people, when two team members share a name."""
    sharing.grant(a_case, friend, actor=owner)
    friend.display_name = owner.shown_name
    friend.save()
    call = a_call(owner, a_case, "Call 0001")
    assignments.assign(call, friend, by=owner)
    names = assignments.names_for(a_case)
    assert names[friend.pk] == f"{owner.shown_name} ({friend.username})"
    assert names[owner.pk] == f"{owner.shown_name} ({owner.username})"
    signed_in(client, owner)
    page = client.get(reverse("case", args=[a_case.pk])).content.decode()
    assert f"{owner.shown_name} ({friend.username})" in page
    import json
    import re

    team = json.loads(
        re.search(r'id="team-members"[^>]*>(.*?)</script>', page, re.S).group(1)
    )
    assert any(one["name"].endswith(f"({friend.username})") for one in team)
    listed = client.get(reverse("notes-page-list", args=[a_case.pk])).json()
    assert listed["recordings"][0]["assigned"].endswith(f"({friend.username})")


def test_the_tools_fold_away_until_the_case_uses_assignment(
    a_case, owner, friend, client
):
    """v1.121.2: an owner sees one button, Divide the work, and no ticks,
    bar or pills while nothing is assigned; the tools open with the button
    and stay open once a recording is assigned. A collaborator never sees
    the button."""
    sharing.grant(a_case, friend, actor=owner)
    calls = [a_call(owner, a_case, f"Call {n:04d}") for n in range(2)]
    signed_in(client, owner)
    page = client.get(reverse("case", args=[a_case.pk])).content.decode()
    assert 'id="divide-the-work"' in page
    assert 'class="tbl as-cards tools-folded"' in page
    assert 'id="tick-bar" hidden' in page and 'id="assignment-pills" hidden' in page
    # The tools are there for the button to unfold.
    assert 'id="divide-among"' in page and 'class="tick"' in page

    assignments.assign(calls[0], friend, by=owner)
    page = client.get(reverse("case", args=[a_case.pk])).content.decode()
    assert 'id="divide-the-work"' not in page
    assert "tools-folded" not in page
    assert (
        'id="tick-bar" hidden' not in page
        and 'id="assignment-pills" hidden' not in page
    )

    signed_in(client, friend)
    page = client.get(reverse("case", args=[a_case.pk])).content.decode()
    assert 'id="divide-the-work"' not in page and "tools-folded" not in page
    assert "Mine 1" in page


def test_the_team_the_pills_and_the_columns(a_case, owner, friend, third, client):
    share = sharing.grant(a_case, friend, actor=owner)
    sharing.grant(a_case, third, actor=owner)
    assignments.set_also_owner(share, True, by=owner)
    calls = [a_call(owner, a_case, f"Call {n:04d}") for n in range(3)]
    assignments.assign(calls[0], friend, by=owner)
    assignments.assign(calls[1], friend, by=owner)
    assignments.mark_reviewed(calls[0], by=friend)

    signed_in(client, friend)
    page = client.get(reverse("case", args=[a_case.pk])).content.decode()
    assert ">Team <" in page and "Add people" in page
    assert "Also an owner" in page and ">Owner<" in page
    assert "2 assigned</a> &middot; 1 reviewed" in page
    assert "Mine, not reviewed 1" in page and "Unassigned 1" in page
    assert '<th class="col-assigned">Assigned to</th>' in page
    assert "Reviewed " in page and 'class="tick"' in page

    narrowed = client.get(
        reverse("case", args=[a_case.pk]) + "?who=me&state=unreviewed"
    ).content.decode()
    assert narrowed.count('<tr class="pick"') == 1
    theirs = client.get(reverse("case", args=[a_case.pk]) + "?who=ben").content.decode()
    assert theirs.count('<tr class="pick"') == 2

    # A plain Collaborator sees the Team without the controls or the ticks.
    signed_in(client, third)
    page = client.get(reverse("case", args=[a_case.pk])).content.decode()
    assert ">Team <" in page and "Leave this case" in page
    assert "Add people" not in page and 'class="tick"' not in page
    assert 'class="also-owner"' not in page

    pills = dashboard.pills(a_case, "collaborator", friend)
    words = [one["words"] for one in pills]
    assert "1 of 3 reviewed" in words and "1 of 2 left for you" in words
    assert all(
        one["tone"] != dashboard.WARN for one in pills if "for you" in one["words"]
    )

    signed_in(client, owner)
    sheet = client.get(reverse("case-list", args=[a_case.pk])).content.decode(
        "utf-8-sig"
    )
    assert "Assigned to,Reviewed by,Reviewed on" in sheet
    assert "Ben Cole,Ben Cole," in sheet


def test_home_says_what_is_left_for_you(a_case, owner, friend, client):
    sharing.grant(a_case, friend, actor=owner)
    call = a_call(owner, a_case, "Call 0409")
    assignments.assign(call, friend, by=owner)
    signed_in(client, friend)
    page = client.get(reverse("home")).content.decode()
    assert "1 of 1 left for you" in page
