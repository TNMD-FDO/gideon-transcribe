"""Sharing: a Case's owner lets named colleagues in.

What would be expensive to get wrong: who may be shared with; that a
Collaborator works in the Case as the owner does and no further (no share,
rename, transfer, delete, and only their own Recordings thrown away); that
their use moves the clock and an Admin's looking in does not; that Off hides
every Share and deletes none; that the rows name the Collaborator and the
owner; that Transfer keeps the old owner on; and that room in somebody
else's Case is that person's.
"""

from datetime import timedelta

import pytest
from core import audit, cases, retention, settings_store, sharing, uploads
from core.cases import Case
from core.jobs import Segment, Transcript
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording, Refusal
from core.sharing import Share
from django.urls import reverse
from django.utils import timezone

PASSWORD = "a-long-enough-password"


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


def colleague(username: str, name: str = "", admin: bool = False) -> User:
    """A directory account that has signed in once: what a Share may name."""
    person = User.objects.create_local_admin(username, PASSWORD)
    person.is_local = admin
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
def admin(db):
    return User.objects.create_local_admin("the-admin", PASSWORD)


@pytest.fixture
def a_case(owner):
    return Case.objects.create(owner=owner, name="Ramirez")


def a_recording(person, case, size=16, with_transcript=True):
    batch = Batch.objects.create(user=person)
    recording = Recording.objects.create(
        batch=batch,
        user=person,
        case=case,
        title="an interview",
        original_filename="interview.m4a",
        media_state=MediaState.READY,
    )
    recording.folder.mkdir(parents=True, exist_ok=True)
    (recording.folder / "original.m4a").write_bytes(b"x" * size)
    if with_transcript:
        transcript = Transcript.objects.create(recording=recording, language="en")
        Segment.objects.create(
            transcript=transcript, start=0, end=1, text="Hi", speaker="A"
        )
    return recording


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def rows(event: str):
    return audit.Row.objects.filter(event=event)


# The setting ------------------------------------------------------------------------


def test_the_setting_sits_under_folder_management():
    told = settings_store.definition("sharing")
    assert told.needs == "folder_management" and told.default is False


def test_off_hides_every_share_and_keeps_it(a_case, owner, friend, client):
    sharing.grant(a_case, friend, actor=owner)
    settings_store.set_to("sharing", False)
    assert not sharing.on()
    assert not a_case.may_be_opened_by(friend)
    assert list(cases.cases_for(friend)) == []
    assert Share.objects.filter(case=a_case, person=friend).exists()

    signed_in(client, friend)
    assert client.get(reverse("case", args=[a_case.pk])).status_code == 404

    settings_store.set_to("sharing", True)
    assert a_case.may_be_opened_by(friend)
    assert list(cases.cases_for(friend)) == [a_case]


# Who may be shared with -------------------------------------------------------------


def test_who_is_offered(a_case, owner, friend, admin):
    never = colleague("never-yet")
    never.last_sign_in = None
    never.save()
    gone = colleague("gone")
    gone.deactivated_at = timezone.now()
    gone.save()
    offered = [one.username for one in sharing.candidates(a_case)]
    # Not the owner, not a local admin, not somebody who has never signed in
    # or is deactivated; the friend is.
    assert offered == ["ben"]

    sharing.grant(a_case, friend, actor=owner)
    assert list(sharing.candidates(a_case)) == []


def test_a_typed_name_finds_one_person_or_asks_back(a_case, friend):
    colleague("bea", "Bea Cole")
    assert sharing.find(a_case, "ben") == friend
    assert sharing.find(a_case, "Ben Cole") == friend
    assert sharing.find(a_case, "ben c") == friend
    with pytest.raises(sharing.NotFound):
        sharing.find(a_case, "Cole")  # two people
    with pytest.raises(sharing.NotFound):
        sharing.find(a_case, "nobody")
    with pytest.raises(sharing.NotFound):
        sharing.find(a_case, "")


# Sharing and its rows ---------------------------------------------------------------


def test_the_owner_shares_and_the_row_names_the_colleague(
    a_case, owner, friend, client
):
    signed_in(client, owner)
    told = client.get(reverse("share-who", args=[a_case.pk])).json()
    assert [one["username"] for one in told["people"]] == ["ben"]

    answer = client.post(reverse("share-case", args=[a_case.pk]), {"who": "Ben Cole"})
    assert answer.status_code == 200 and answer.json()["share"]["name"] == "Ben Cole"
    row = rows("Share granted").get()
    assert row.details["collaborator"] == "ben" and row.affected_user is None
    assert a_case.member(friend) == "collaborator"

    # Sharing again changes nothing and writes nothing.
    client.post(reverse("share-case", args=[a_case.pk]), {"who": "ben"})
    assert rows("Share granted").count() == 1


def test_an_admin_shares_somebody_elses_case_naming_the_owner(
    a_case, owner, friend, admin, client
):
    signed_in(client, admin)
    answer = client.post(reverse("share-case", args=[a_case.pk]), {"who": "ben"})
    assert answer.status_code == 200
    assert rows("Share granted").get().affected_user == owner


def test_a_bystander_cannot_share_or_see_the_list(a_case, friend, client):
    signed_in(client, friend)
    assert client.get(reverse("share-who", args=[a_case.pk])).status_code == 404
    assert (
        client.post(reverse("share-case", args=[a_case.pk]), {"who": "ben"}).status_code
        == 404
    )


def test_removing_a_share_and_leaving(a_case, owner, friend, client):
    share = sharing.grant(a_case, friend, actor=owner)
    signed_in(client, friend)
    # A Collaborator may not remove somebody else's Share, but may leave.
    other = sharing.grant(a_case, colleague("cy"), actor=owner)
    assert (
        client.post(
            reverse("unshare-case", args=[a_case.pk]), {"share": other.pk}
        ).status_code
        == 404
    )
    answer = client.post(reverse("unshare-case", args=[a_case.pk]), {"share": share.pk})
    assert answer.json()["left"] is True
    assert not Share.objects.filter(pk=share.pk).exists()
    assert rows("Share revoked").get().details["collaborator"] == "ben"

    signed_in(client, owner)
    assert (
        client.post(
            reverse("unshare-case", args=[a_case.pk]), {"share": other.pk}
        ).status_code
        == 200
    )
    assert rows("Share revoked").count() == 2


# What a Collaborator may do ---------------------------------------------------------


def test_a_collaborator_works_in_the_case_as_their_own(a_case, owner, friend, client):
    recording = a_recording(owner, a_case)
    sharing.grant(a_case, friend, actor=owner)
    signed_in(client, friend)

    # The Cases page lists it, New until opened.
    page = client.get(reverse("cases")).content.decode()
    assert "Shared by Ana Ruiz" in page and ">New<" in page

    # The Case page opens as a colleague's, with no Admin banner and no Admin
    # access row, and the Share remembers the opening.
    page = client.get(reverse("case", args=[a_case.pk]))
    assert page.status_code == 200
    body = page.content.decode()
    assert "as an Admin" not in body and "Shared by" in body
    assert "Leave this case" in body and 'id="rename"' not in body
    assert rows("admin access").count() == 0
    share = Share.objects.get(case=a_case, person=friend)
    assert share.last_opened is not None
    assert ">New<" not in client.get(reverse("cases")).content.decode()

    # The Recording opens, its Transcript and its facts are served, and the
    # "Recording opened" row names the owner, so the log's access filter
    # shows it beside Admins' openings.
    assert client.get(reverse("viewer", args=[recording.pk])).status_code == 200
    opened = rows("Recording opened").get()
    assert opened.actor == friend and opened.affected_user == owner
    assert rows("another user's item opened").count() == 0
    assert client.get(reverse("segments", args=[recording.pk])).status_code == 200
    assert client.get(reverse("details", args=[recording.pk])).status_code == 200
    assert client.get(reverse("export", args=[recording.pk, "text"])).status_code == 200
    assert cases.standing(recording, friend) == "own"


def test_a_collaborator_may_not_run_the_case(a_case, owner, friend, client):
    sharing.grant(a_case, friend, actor=owner)
    signed_in(client, friend)
    assert (
        client.post(reverse("rename-case", args=[a_case.pk]), {"name": "X"}).status_code
        == 404
    )
    assert client.post(reverse("delete-case", args=[a_case.pk])).status_code == 404
    assert (
        client.post(
            reverse("transfer-case", args=[a_case.pk]), {"who": "ben"}
        ).status_code
        == 404
    )
    assert Case.objects.filter(pk=a_case.pk, name="Ramirez").exists()


def test_a_collaborator_throws_away_only_what_they_added(a_case, owner, friend, client):
    theirs = a_recording(owner, a_case)
    mine = a_recording(friend, a_case)
    sharing.grant(a_case, friend, actor=owner)
    assert cases.may_throw_away(mine, friend) and not cases.may_throw_away(
        theirs, friend
    )
    assert cases.may_throw_away(mine, owner) and cases.may_throw_away(theirs, owner)

    signed_in(client, friend)
    assert client.post(reverse("delete-recording", args=[theirs.pk])).status_code == 404
    assert client.post(reverse("delete-recording", args=[mine.pk])).status_code == 200
    assert not Recording.objects.filter(pk=mine.pk).exists()

    # The owner deleting a Collaborator's Recording says so.
    another = a_recording(friend, a_case)
    signed_in(client, owner)
    assert (
        client.post(reverse("delete-recording", args=[another.pk])).status_code == 200
    )
    assert rows("Recording deleted").order_by("-at").first().details["cause"] == (
        "case owner"
    )


def test_a_collaborator_moves_between_the_cases_they_are_in(
    a_case, owner, friend, client
):
    mine = a_recording(friend, a_case)
    sharing.grant(a_case, friend, actor=owner)
    own_case = Case.objects.create(owner=friend, name="Mine")
    somebody_elses = Case.objects.create(owner=colleague("cy"), name="Not mine")
    signed_in(client, friend)

    told = client.get(reverse("where-it-could-go")).json()
    assert {one["name"]: one["shared_by"] for one in told["cases"]} == {
        "Mine": "",
        "Ramirez": "Ana Ruiz",
    }
    assert (
        client.post(
            reverse("move-to-case", args=[mine.pk]), {"case": somebody_elses.pk}
        ).status_code
        == 404
    )
    assert (
        client.post(
            reverse("move-to-case", args=[mine.pk]), {"case": own_case.pk}
        ).status_code
        == 200
    )


def test_clips_in_a_shared_case_are_everybodys(a_case, owner, friend):
    from core.clip_pages import _may_change
    from core.clips import Clip

    recording = a_recording(owner, a_case)
    clip = Clip.objects.create(
        recording=recording, user=owner, title="a clip", start=0, end=1
    )
    assert not _may_change(clip, friend)
    sharing.grant(a_case, friend, actor=owner)
    assert _may_change(clip, friend)


def test_keep_and_the_clock_are_a_collaborators_too(
    a_case, owner, friend, admin, client
):
    sharing.grant(a_case, friend, actor=owner)
    ago = timezone.now() - timedelta(days=20)
    Case.objects.filter(pk=a_case.pk).update(last_activity=ago)
    a_case.refresh_from_db()

    # An Admin who is not on the Case is not use; a Collaborator is.
    cases.note_activity(a_case, by=admin)
    a_case.refresh_from_db()
    assert a_case.last_activity == ago
    cases.note_activity(a_case, by=friend)
    a_case.refresh_from_db()
    assert a_case.last_activity > ago

    Case.objects.filter(pk=a_case.pk).update(last_activity=ago)
    signed_in(client, friend)
    assert client.post(reverse("keep-case", args=[a_case.pk])).status_code == 200
    assert rows("case kept").get().affected_user == owner


def test_an_admin_on_the_case_is_a_colleague_there(a_case, owner, admin, client):
    admin.last_sign_in = timezone.now()
    admin.is_local = False
    admin.admin_flag = True
    admin.save()
    assert admin.is_admin
    recording = a_recording(owner, a_case)
    signed_in(client, admin)
    client.get(reverse("case", args=[a_case.pk]))
    assert rows("admin access").count() == 1
    assert cases.standing(recording, admin) == "admin"

    sharing.grant(a_case, admin, actor=owner)
    assert a_case.role_of(admin) == "collaborator"
    client.get(reverse("case", args=[a_case.pk]))
    assert rows("admin access").count() == 1
    assert cases.standing(recording, admin) == "own"


# Room and Transfer --------------------------------------------------------------------


def test_room_in_somebody_elses_case_is_theirs(a_case, owner, friend, monkeypatch):
    # The runner's disk is not the question here.
    monkeypatch.setattr(uploads, "free_disk_bytes", lambda: 10**15)
    owner.quota_gb = 1
    owner.save()
    batch = Batch.objects.create(user=friend)
    told = uploads.check_before_upload(
        friend, batch, 2 * settings_store.GB, 1, into=a_case
    )
    assert told is not None and told.reason_class == Refusal.QUOTA_EXCEEDED
    assert "Ana Ruiz's storage space" in told.message
    assert uploads.check_before_upload(friend, batch, 16, 1, into=a_case) is None


def test_transfer_keeps_the_old_owner_on(a_case, owner, friend, client):
    signed_in(client, owner)
    answer = client.post(reverse("transfer-case", args=[a_case.pk]), {"who": "ben"})
    assert answer.status_code == 200
    a_case.refresh_from_db()
    assert a_case.owner == friend
    assert a_case.member(owner) == "collaborator" and a_case.member(friend) == "owner"
    handed = rows("case reassigned").get()
    assert handed.affected_user == owner and handed.details["to"] == "ben"
    assert handed.details["cause"] == "transfer"
    assert rows("Share granted").get().details["collaborator"] == "ana"

    # The new owner runs the case; the old owner no longer does.
    assert (
        client.post(reverse("rename-case", args=[a_case.pk]), {"name": "X"}).status_code
        == 404
    )


# Leaving, the bin, deletion ------------------------------------------------------


def test_the_bin_and_deletion_take_the_shares_with_them(a_case, owner, friend):
    sharing.grant(a_case, friend, actor=owner)
    a_case.deleted_on = timezone.localdate()
    a_case.save()
    assert list(sharing.shared_with(friend)) == []
    assert not a_case.may_be_opened_by(friend)
    a_case.deleted_on = None
    a_case.save()
    assert list(sharing.shared_with(friend)) == [a_case]

    cases.delete(a_case, actor=owner)
    assert Share.objects.count() == 0


def test_a_deactivated_collaborator_is_shown_greyed(a_case, owner, friend, client):
    share = sharing.grant(a_case, friend, actor=owner)
    friend.deactivated_at = timezone.now()
    friend.save()
    assert share.status == "deactivated"
    signed_in(client, owner)
    body = client.get(reverse("case", args=[a_case.pk])).content.decode()
    assert "deactivated" in body and "Ben Cole" in body


def test_the_digest_warns_collaborators_in_their_own(a_case, owner, friend):
    sharing.grant(a_case, friend, actor=owner)
    digests = retention.digests_for_tonight([(a_case, 3)])
    assert set(digests) == {owner.pk, friend.pk}
    assert digests[friend.pk][0]["shared_by"] == "Ana Ruiz"
    assert "shared_by" not in digests[owner.pk][0]
