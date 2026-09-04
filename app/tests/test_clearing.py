"""Finishing with a batch, and landing on the page you work on.

An office running batches works in a loop: upload, wait, download, clear,
upload the next lot. The clearing step did not exist. The only ways to remove
twelve recordings were Delete twelve times or signing out, and signing out
takes everything, so somebody keeping one recording from last week had to
choose between it and the room for tomorrow's batch.

It is a quota problem, not a tidiness one. Every Recording counts against its
owner's quota until it goes.
"""

import pytest
from core import lifecycle, settings_store
from core.models import User
from core.recordings import Batch, MediaState, Recording
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings):
    """A fresh App data folder for each test, as the Cases tests do."""
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"
    return tmp_path


def a_person(name="pat"):
    return User.objects.create_local_admin(name, "a-long-enough-password")


def a_recording(user, batch=None, name="one.mp3"):
    recording = Recording.objects.create(
        user=user,
        batch=batch,
        original_filename=name,
        media_state=MediaState.READY,
    )
    recording.folder.mkdir(parents=True, exist_ok=True)
    (recording.folder / "original.mp3").write_bytes(b"x" * 1024)
    return recording


def signed_in(client, user):
    client.force_login(user)
    return client


# What the clearing removes


def test_clearing_a_batch_takes_that_batch_and_leaves_the_rest(client):
    person = a_person()
    batch = Batch.objects.create(user=person)
    a_recording(person, batch, "in-the-batch.mp3")
    a_recording(person, batch, "also-in-it.mp3")
    keeping = a_recording(person, None, "from-last-week.mp3")

    signed_in(client, person)
    answer = client.post(reverse("clear-recordings"), {"batch": str(batch.pk)})

    assert answer.status_code == 200
    assert answer.json()["recordings"] == 2
    assert set(Recording.objects.values_list("pk", flat=True)) == {keeping.pk}


def test_clearing_without_a_batch_takes_the_whole_workspace(client):
    person = a_person()
    a_recording(person, None, "one.mp3")
    a_recording(person, None, "two.mp3")

    signed_in(client, person)
    answer = client.post(reverse("clear-recordings"))

    assert answer.json()["recordings"] == 2
    assert not Recording.objects.exists()


def test_clearing_never_touches_a_recording_in_a_case():
    # A Case is somewhere a Recording was deliberately put, and the Workspace
    # is not. Clearing the Workspace must not empty a Case by accident.
    from core import cases

    settings_store.set_to("folder_management", True)
    person = a_person()
    case = cases.create(person, "Some matter")
    loose = a_recording(person, None, "loose.mp3")
    in_a_case = a_recording(person, None, "filed.mp3")
    in_a_case.case = case
    in_a_case.save()

    gone, _ = lifecycle.clear_out(list(Recording.objects.all()), actor=person)

    assert gone == 1
    assert set(Recording.objects.values_list("pk", flat=True)) == {in_a_case.pk}
    assert loose.pk not in set(Recording.objects.values_list("pk", flat=True))


def test_clearing_never_reaches_somebody_elses_recordings(client):
    me = a_person("pat")
    somebody_else = a_person("sam")
    a_recording(me, None, "mine.mp3")
    not_mine = a_recording(somebody_else, None, "theirs.mp3")

    signed_in(client, me)
    client.post(reverse("clear-recordings"))

    assert set(Recording.objects.values_list("pk", flat=True)) == {not_mine.pk}


def test_it_says_what_would_go_before_anything_goes(client):
    person = a_person()
    batch = Batch.objects.create(user=person)
    a_recording(person, batch, "one.mp3")
    a_recording(person, batch, "two.mp3")

    signed_in(client, person)
    told = client.get(reverse("what-would-go"), {"batch": str(batch.pk)}).json()

    assert told["recordings"] == 2
    assert "GB" in told["size"] or "MB" in told["size"] or "KB" in told["size"]
    # Asking changes nothing.
    assert Recording.objects.count() == 2


def test_the_clearing_is_written_down(client):
    from core import audit

    person = a_person()
    a_recording(person, None, "one.mp3")

    signed_in(client, person)
    client.post(reverse("clear-recordings"))

    rows = audit.Row.objects.filter(event="recordings cleared")
    assert rows.count() == 1
    # The person did it, not the sweeper.
    assert rows.first().actor_user_id == person.pk
    assert rows.first().actor_kind == "user"


def test_a_get_will_not_clear_anything(client):
    person = a_person()
    a_recording(person, None, "one.mp3")

    signed_in(client, person)
    assert client.get(reverse("clear-recordings")).status_code == 405
    assert Recording.objects.count() == 1


def test_a_stranger_cannot_clear_anything(client):
    person = a_person()
    a_recording(person, None, "one.mp3")

    answer = client.post(reverse("clear-recordings"))

    assert answer.status_code in (302, 403)
    assert Recording.objects.count() == 1


# Where a person lands


def test_the_specified_page_stands_until_somebody_shows_otherwise():
    from core.views import where_they_land

    settings_store.set_to("folder_management", True)
    person = a_person()

    assert where_they_land(person) == reverse("cases")


def test_somebody_who_works_in_recordings_lands_there(client):
    from core.views import where_they_land

    settings_store.set_to("folder_management", True)
    person = a_person()

    signed_in(client, person)
    client.get(reverse("home"))

    person.refresh_from_db()
    assert where_they_land(person) == reverse("home")


def test_opening_cases_again_puts_them_back(client):
    from core.views import where_they_land

    settings_store.set_to("folder_management", True)
    person = a_person()

    signed_in(client, person)
    client.get(reverse("home"))
    client.get(reverse("cases"))

    person.refresh_from_db()
    assert where_they_land(person) == reverse("cases")


def test_with_cases_off_there_is_only_one_page():
    from core.views import where_they_land

    settings_store.set_to("folder_management", False)
    person = a_person()
    person.lands_on = User.LANDS_CASES
    person.save()

    assert where_they_land(person) == reverse("home")


def test_the_pages_carry_the_way_out():
    # A batch user landing on Cases needs the upload from there, and somebody
    # with recordings needs the way to be finished with them.
    from pathlib import Path

    here = Path(__file__).resolve().parent.parent / "templates"
    assert "'upload'" in (here / "cases.html").read_text(encoding="utf-8")
    assert "clear-recordings" in (here / "recordings.html").read_text(encoding="utf-8")
    assert "clear-recordings" in (here / "batch.html").read_text(encoding="utf-8")
