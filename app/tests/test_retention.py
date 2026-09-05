"""The Retention policy: one clock per Case, the warning, the sweep, the bin.

The rules checked here are the ones that would be expensive to get wrong: a
Case is taken by neglect and by nothing else; the days Folder management was
off never count; the warning is written once and lifts on any use; a binned
Case is unreachable by anybody and keeps its bytes; the wipe leaves nothing;
and the sweep does nothing at all while Folder management is off.
"""

from datetime import timedelta

import pytest
from core import audit, cases, retention, settings_store
from core.cases import Case, OffSpell
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording
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
def cases_on(db):
    settings_store.set_to("folder_management", True)


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("case-owner", PASSWORD)


@pytest.fixture
def somebody_else(db):
    other = User.objects.create_local_admin("bystander", PASSWORD)
    other.is_local = False
    other.save()
    return other


@pytest.fixture
def admin(db):
    return User.objects.create_local_admin("the-admin", PASSWORD)


@pytest.fixture
def a_case(person):
    return Case.objects.create(owner=person, name="Ramirez")


def a_recording(person, case, size=16):
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
    return recording


def aged(case: Case, days: int) -> Case:
    """Move a Case's Last activity back, as the dates on the page would show."""
    Case.objects.filter(pk=case.pk).update(
        last_activity=timezone.now() - timedelta(days=days)
    )
    case.refresh_from_db()
    return case


def binned_for(case: Case, days: int) -> Case:
    Case.objects.filter(pk=case.pk).update(
        deleted_on=timezone.localdate() - timedelta(days=days)
    )
    case.refresh_from_db()
    return case


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def rows(event: str):
    return audit.Row.objects.filter(event=event)


# Counting days ----------------------------------------------------------------


def test_whole_days_are_by_the_calendar():
    now = timezone.now()
    assert retention.whole_days(now - timedelta(days=3), now) == 3
    assert retention.whole_days(now, now - timedelta(days=3)) == 0


def test_the_days_off_inside_a_span_are_left_out(db):
    now = timezone.now()
    since = now - timedelta(days=30)
    OffSpell.objects.create(
        started=now - timedelta(days=20), ended=now - timedelta(days=10)
    )
    assert retention.days_off_between(since, now) == 10


def test_a_spell_still_open_runs_to_now(db):
    now = timezone.now()
    since = now - timedelta(days=30)
    OffSpell.objects.create(started=now - timedelta(days=4))
    assert retention.days_off_between(since, now) == 4


def test_days_unused_subtracts_the_off_spells(a_case):
    aged(a_case, 30)
    now = timezone.now()
    OffSpell.objects.create(
        started=now - timedelta(days=25), ended=now - timedelta(days=5)
    )
    # Thirty days ago, of which twenty the office had cases off.
    assert retention.days_unused(a_case) == 10
    assert retention.days_left(a_case) == 20


def test_the_line_the_page_shows():
    assert retention.deletes_line(3) == "Deletes in 3 days unless used"
    assert retention.deletes_line(1) == "Deletes in 1 day unless used"
    assert retention.deletes_line(0) == "Deletes tonight unless used"


# The sweep --------------------------------------------------------------------


def test_the_sweep_does_nothing_at_all_while_cases_are_off(a_case):
    aged(a_case, 400)
    settings_store.set_to("folder_management", False)

    assert retention.sweep() is None

    a_case.refresh_from_db()
    assert a_case.deleted_on is None and a_case.warned_on is None
    assert not rows("retention sweep ran").exists()


def test_a_case_in_its_last_days_is_warned_once(a_case):
    aged(a_case, 25)  # five days left under the default thirty and seven

    first = retention.sweep()
    a_case.refresh_from_db()
    assert first["warned"] == 1
    assert a_case.warned_on == timezone.localdate()
    assert rows("retention warning").count() == 1
    assert rows("retention warning").first().affected_user_id == a_case.owner_id

    second = retention.sweep()
    assert second["warned"] == 0
    assert rows("retention warning").count() == 1


def test_any_use_lifts_the_warning_so_the_next_approach_is_warned_again(a_case):
    aged(a_case, 25)
    retention.sweep()
    a_case.refresh_from_db()
    assert a_case.warned_on is not None

    cases.note_activity(a_case, by=a_case.owner)
    a_case.refresh_from_db()
    assert a_case.warned_on is None
    assert retention.days_left(a_case) == 30

    aged(a_case, 25)
    retention.sweep()
    assert rows("retention warning").count() == 2


def test_an_admin_looking_in_does_not_move_the_clock(a_case, admin):
    aged(a_case, 25)
    cases.note_activity(a_case, by=admin)
    a_case.refresh_from_db()
    assert retention.days_left(a_case) == 5


def test_a_due_case_goes_to_the_bin_whole_and_keeps_its_bytes(a_case, person):
    recording = a_recording(person, a_case)
    aged(a_case, 30)

    counts = retention.sweep()
    a_case.refresh_from_db()

    assert counts["deleted"] == 1
    assert a_case.deleted_on == timezone.localdate()
    # Rows and files both stay: this is the bin, not the wipe.
    assert Recording.objects.filter(pk=recording.pk).exists()
    assert recording.folder.exists()
    row = rows("case deleted").first()
    assert row.details["cause"] == "retention"
    assert row.details["recordings"] == 1
    assert row.actor_kind != "user"


def test_a_due_case_is_not_warned_the_night_it_goes(a_case):
    aged(a_case, 30)
    retention.sweep()
    assert not rows("retention warning").exists()


def test_shortening_the_period_deletes_that_night(a_case):
    aged(a_case, 10)
    settings_store.set_to("retention_days", 7)

    retention.sweep()
    a_case.refresh_from_db()
    assert a_case.deleted_on is not None


def test_the_days_off_do_not_count_towards_deletion(a_case):
    aged(a_case, 40)
    now = timezone.now()
    OffSpell.objects.create(
        started=now - timedelta(days=35), ended=now - timedelta(days=5)
    )

    retention.sweep()
    a_case.refresh_from_db()
    # Forty days ago, thirty of them off: ten used, twenty left.
    assert a_case.deleted_on is None
    assert retention.days_left(a_case) == 20


def test_a_binned_case_past_the_bin_period_is_wiped(a_case, person):
    recording = a_recording(person, a_case)
    binned_for(a_case, 31)

    counts = retention.sweep()

    assert counts["wiped"] == 1
    assert not Case.objects.filter(pk=a_case.pk).exists()
    assert not Recording.objects.filter(pk=recording.pk).exists()
    assert not a_case.folder.exists()
    wiped = rows("case permanently deleted").first()
    assert wiped.details["cause"] == cases.WIPED_BY_THE_BIN
    assert wiped.affected_user_id == person.pk
    # One row per Recording, as Case delete writes.
    assert rows("Recording deleted").filter(details__cause="retention").count() == 1


def test_the_bins_wait_pauses_while_cases_are_off(a_case):
    binned_for(a_case, 31)
    now = timezone.now()
    OffSpell.objects.create(
        started=now - timedelta(days=20), ended=now - timedelta(days=10)
    )

    retention.sweep()
    assert Case.objects.filter(pk=a_case.pk).exists()
    assert retention.bin_days_left(a_case) == 9


def test_the_sweep_writes_one_row_with_the_counts(a_case):
    aged(a_case, 25)
    retention.sweep()
    ran = rows("retention sweep ran").first()
    assert ran.details == {
        "warned": 1,
        "deleted": 0,
        "wiped": 0,
        "gigabytes_freed": 0.0,
    }


def test_the_digests_are_gathered_per_owner(a_case, person):
    aged(a_case, 25)
    a_recording(person, a_case)
    digests = retention.digests_for_tonight([(a_case, 5)])
    assert list(digests) == [person.pk]
    line = digests[person.pk][0]
    assert line["case"] == "Ramirez"
    assert line["line"] == "Deletes in 5 days unless used"
    assert line["recordings"] == 1


# A binned Case is out of reach --------------------------------------------------


def test_a_binned_case_leaves_every_list(a_case, person):
    binned_for(a_case, 1)
    assert list(cases.cases_for(person)) == []
    assert list(cases.binned_for(person)) == [a_case]
    assert not a_case.may_be_opened_by(person)


def test_nobody_opens_a_recording_in_a_binned_case(a_case, person, admin, client):
    recording = a_recording(person, a_case)
    binned_for(a_case, 1)
    assert not cases.reachable(recording)

    signed_in(client, person)
    assert client.get(reverse("viewer", args=[recording.pk])).status_code == 302
    assert client.get(reverse("export", args=[recording.pk, "text"])).status_code == 404
    assert client.get(reverse("case", args=[a_case.pk])).status_code == 404

    signed_in(client, admin)
    assert client.get(reverse("viewer", args=[recording.pk])).status_code == 302


def test_a_binned_case_is_not_offered_as_somewhere_to_move_to(a_case, person, client):
    binned_for(a_case, 1)
    signed_in(client, person)
    told = client.get(reverse("where-it-could-go")).json()
    assert told["cases"] == []


# Keep ---------------------------------------------------------------------------


def test_keep_starts_the_clock_over_and_lifts_the_warning(a_case, person, client):
    aged(a_case, 25)
    retention.sweep()

    signed_in(client, person)
    answer = client.post(reverse("keep-case", args=[a_case.pk]))

    assert answer.status_code == 200
    assert answer.json()["days_left"] == 30
    a_case.refresh_from_db()
    assert a_case.warned_on is None
    kept = rows("case kept").first()
    assert kept.actor_user_id == person.pk
    assert kept.affected_user_id is None


def test_an_admins_keep_counts_and_names_the_owner(a_case, admin, client):
    aged(a_case, 25)
    signed_in(client, admin)

    client.post(reverse("keep-case", args=[a_case.pk]))

    a_case.refresh_from_db()
    assert retention.days_left(a_case) == 30
    kept = rows("case kept").first()
    assert kept.actor_user_id == admin.pk
    assert kept.affected_user_id == a_case.owner_id


def test_a_bystander_cannot_keep_somebody_elses_case(a_case, somebody_else, client):
    aged(a_case, 25)
    signed_in(client, somebody_else)
    assert client.post(reverse("keep-case", args=[a_case.pk])).status_code == 404


# The Cases page -----------------------------------------------------------------


def test_the_cases_page_marks_a_case_in_its_last_days(a_case, person, client):
    aged(a_case, 25)
    signed_in(client, person)

    page = client.get(reverse("cases")).content.decode()

    assert "Deletes in 5 days unless used" in page
    assert 'class="small keep"' in page
    # The amber row: the chooser's class first, then the warning's.
    assert 'class="pick expiring"' in page


def test_the_expiring_filter_shows_only_the_warned(a_case, person, client):
    Case.objects.create(owner=person, name="Fresh one")
    aged(a_case, 25)
    signed_in(client, person)

    page = client.get(reverse("cases") + "?expiring=1").content.decode()

    assert "Ramirez" in page
    assert "Fresh one" not in page


# The Recycle bin page -----------------------------------------------------------


def test_the_owner_sees_their_own_bin_and_nobody_elses(
    a_case, person, somebody_else, client
):
    # The bystander is the one non-admin here: the person fixture is a Local
    # admin, and an Admin sees everybody's bin by design.
    binned_for(a_case, 3)
    theirs = Case.objects.create(owner=somebody_else, name="Not mine")
    binned_for(theirs, 3)

    signed_in(client, somebody_else)
    page = client.get(reverse("recycle-bin")).content.decode()

    assert "Not mine" in page
    assert "Ramirez" not in page
    assert "Empty recycle bin" in page


def test_an_admin_sees_everybodys_bin_with_an_owner_filter(
    a_case, person, somebody_else, admin, client
):
    binned_for(a_case, 3)
    theirs = Case.objects.create(owner=somebody_else, name="Not mine")
    binned_for(theirs, 3)

    signed_in(client, admin)
    everyone = client.get(reverse("recycle-bin")).content.decode()
    assert "Ramirez" in everyone and "Not mine" in everyone

    just_one = client.get(
        reverse("recycle-bin") + f"?owner={somebody_else.username}"
    ).content.decode()
    assert "Not mine" in just_one and "Ramirez" not in just_one


def test_the_bin_page_is_gone_while_cases_are_off(person, client):
    signed_in(client, person)
    settings_store.set_to("folder_management", False)
    assert client.get(reverse("recycle-bin")).status_code == 404


def test_restore_puts_the_case_back_and_starts_its_clock_over(a_case, person, client):
    recording = a_recording(person, a_case)
    aged(a_case, 40)
    binned_for(a_case, 3)
    signed_in(client, person)

    answer = client.post(reverse("restore-case", args=[a_case.pk]))

    assert answer.status_code == 200
    a_case.refresh_from_db()
    assert a_case.deleted_on is None
    assert retention.days_left(a_case) == 30
    assert cases.reachable(recording)
    assert rows("case restored").count() == 1


def test_delete_permanently_wipes_at_once_with_the_owner_as_cause(
    a_case, person, client
):
    recording = a_recording(person, a_case)
    binned_for(a_case, 3)
    signed_in(client, person)

    counts = client.get(reverse("what-would-go", args=[a_case.pk])).json()
    assert counts["recordings"] == 1

    answer = client.post(reverse("wipe-case", args=[a_case.pk]))

    assert answer.status_code == 200
    assert not Case.objects.filter(pk=a_case.pk).exists()
    assert not recording.folder.exists()
    assert rows("case permanently deleted").first().details["cause"] == "owner"


def test_empty_recycle_bin_takes_only_ones_own(a_case, person, somebody_else, client):
    binned_for(a_case, 3)
    theirs = Case.objects.create(owner=somebody_else, name="Not mine")
    binned_for(theirs, 3)
    signed_in(client, person)

    told = client.get(reverse("bin-what-would-go")).json()
    assert told["cases"] == 1

    answer = client.post(reverse("empty-bin"))

    assert answer.json()["cases"] == 1
    assert not Case.objects.filter(pk=a_case.pk).exists()
    assert Case.objects.filter(pk=theirs.pk).exists()


def test_a_bystander_cannot_touch_somebody_elses_bin(a_case, somebody_else, client):
    binned_for(a_case, 3)
    signed_in(client, somebody_else)
    assert client.post(reverse("restore-case", args=[a_case.pk])).status_code == 404
    assert client.post(reverse("wipe-case", args=[a_case.pk])).status_code == 404


# The settings -------------------------------------------------------------------


def test_the_warning_must_be_shorter_than_the_period(db):
    with pytest.raises(ValueError):
        settings_store.check_together({"warning_days": 30, "retention_days": 30})
    with pytest.raises(ValueError):
        settings_store.check_together({"retention_days": 7})  # warning is 7
    settings_store.check_together({"retention_days": 8})


def test_the_three_settings_are_greyed_while_cases_are_off():
    for key in ("retention_days", "warning_days", "recycle_bin_days"):
        assert settings_store.definition(key).needs == "folder_management"


def test_the_tray_refuses_a_pair_that_is_wrong_together(admin, client):
    from core.panel import TRAY

    signed_in(client, admin)
    session = client.session
    session[TRAY] = {"retention_days": 7}
    session.save()

    client.post(reverse("panel-apply"), {"back": "/panel/settings/cases"})

    # Nothing applied, and the value is still the default.
    assert settings_store.get("retention_days") == 30


# Elsewhere in the panel ---------------------------------------------------------


def test_the_status_line_counts_live_expiring_and_binned(a_case, person):
    from core.panel_pages import _workspaces

    Case.objects.create(owner=person, name="Fresh one")
    aged(a_case, 25)
    gone = Case.objects.create(owner=person, name="Gone")
    binned_for(gone, 2)

    told = _workspaces()
    assert told["cases"] == 2
    assert told["expiring"] == 1
    assert told["binned"] == 1


def test_delete_data_wipes_a_leavers_binned_cases_too(a_case, person, admin, client):
    a_recording(person, a_case)
    binned_for(a_case, 3)
    signed_in(client, admin)

    client.post(
        reverse("panel-user", args=[person.username]), {"action": "delete-data"}
    )

    assert not Case.objects.filter(pk=a_case.pk).exists()
    assert rows("case permanently deleted").first().details["cause"] == "admin"
