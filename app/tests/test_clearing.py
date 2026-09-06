"""Finishing with a batch, and where signing in lands.

An office running batches works in a loop: upload, wait, download, clear,
upload the next lot. The clearing step did not exist. The only ways to remove
twelve recordings were Delete twelve times or signing out, and signing out
takes everything, so somebody keeping one recording from last week had to
choose between it and the room for tomorrow's batch.

It is a quota problem, not a tidiness one. Every Recording counts against its
owner's quota until it goes.
"""

import pytest
from core import audit, cases, lifecycle, settings_store
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording
from django.urls import reverse

PASSWORD = "a-long-enough-password"

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings):
    """A fresh App data folder for each test, as the Cases tests have.

    The database rolls back at the end of a test and the disk does not.
    """
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"
    return tmp_path


def a_person(name="pat"):
    return User.objects.create_local_admin(name, PASSWORD)


def signed_in(client, person):
    """A browser with a Login session behind it, which the middleware wants."""
    client.force_login(person)
    LoginSession.objects.create(user=person, session_key=client.session.session_key)
    return client


def a_recording(person, batch, name="one.mp3", case=None):
    """One Recording with a little on the disk. Every Recording has a Batch."""
    recording = Recording.objects.create(
        user=person,
        batch=batch,
        case=case,
        title=name.rsplit(".", 1)[0],
        original_filename=name,
        media_state=MediaState.READY,
    )
    recording.folder.mkdir(parents=True, exist_ok=True)
    (recording.folder / "original.mp3").write_bytes(b"x" * 1024)
    return recording


def what_is_left():
    return set(Recording.objects.values_list("pk", flat=True))


# What the clearing removes ----------------------------------------------------


def test_clearing_a_batch_takes_that_batch_and_leaves_the_rest(client):
    person = a_person()
    today = Batch.objects.create(user=person)
    a_recording(person, today, "in-the-batch.mp3")
    a_recording(person, today, "also-in-it.mp3")
    last_week = Batch.objects.create(user=person)
    keeping = a_recording(person, last_week, "from-last-week.mp3")

    signed_in(client, person)
    answer = client.post(reverse("clear-recordings"), {"batch": str(today.pk)})

    assert answer.status_code == 200
    assert answer.json()["recordings"] == 2
    assert what_is_left() == {keeping.pk}
    # Somewhere to go next, which is the point of the loop.
    assert answer.json()["where"] == reverse("start")


def test_clearing_without_a_batch_takes_the_whole_workspace(client):
    person = a_person()
    batch = Batch.objects.create(user=person)
    a_recording(person, batch, "one.mp3")
    a_recording(person, batch, "two.mp3")

    signed_in(client, person)
    answer = client.post(reverse("clear-recordings"))

    assert answer.json()["recordings"] == 2
    assert what_is_left() == set()


def test_clearing_never_touches_a_recording_in_a_case():
    # A Case is somewhere a Recording was deliberately put, and a Workspace is
    # not. Clearing a Workspace must not empty a Case by accident.
    settings_store.set_to("folder_management", True)
    person = a_person()
    case = cases.create(person, "Some matter")
    batch = Batch.objects.create(user=person)
    loose = a_recording(person, batch, "loose.mp3")
    filed = a_recording(person, batch, "filed.mp3", case=case)

    gone, _ = lifecycle.clear_out(list(Recording.objects.all()), actor=person)

    assert gone == 1
    assert what_is_left() == {filed.pk}
    assert loose.pk not in what_is_left()


def test_clearing_never_reaches_somebody_elses_recordings(client):
    me = a_person("pat")
    somebody_else = a_person("sam")
    a_recording(me, Batch.objects.create(user=me), "mine.mp3")
    not_mine = a_recording(
        somebody_else, Batch.objects.create(user=somebody_else), "theirs.mp3"
    )

    signed_in(client, me)
    client.post(reverse("clear-recordings"))

    assert what_is_left() == {not_mine.pk}


def test_it_says_what_would_go_before_anything_goes(client):
    person = a_person()
    batch = Batch.objects.create(user=person)
    a_recording(person, batch, "one.mp3")
    a_recording(person, batch, "two.mp3")

    signed_in(client, person)
    told = client.get(reverse("what-would-go"), {"batch": str(batch.pk)}).json()

    assert told["recordings"] == 2
    assert told["size"]
    # Asking changes nothing.
    assert Recording.objects.count() == 2


def test_the_clearing_is_written_down(client):
    person = a_person()
    a_recording(person, Batch.objects.create(user=person), "one.mp3")

    signed_in(client, person)
    client.post(reverse("clear-recordings"))

    rows = audit.Row.objects.filter(event="recordings cleared")
    assert rows.count() == 1
    # The person did it, not the sweeper.
    assert rows.first().actor_user_id == person.pk
    assert rows.first().actor_kind == "user"


def test_a_get_will_not_clear_anything(client):
    person = a_person()
    a_recording(person, Batch.objects.create(user=person), "one.mp3")

    signed_in(client, person)
    assert client.get(reverse("clear-recordings")).status_code == 405
    assert Recording.objects.count() == 1


def test_a_stranger_cannot_clear_anything(client):
    person = a_person()
    a_recording(person, Batch.objects.create(user=person), "one.mp3")

    answer = client.post(reverse("clear-recordings"))

    assert answer.status_code in (302, 403)
    assert Recording.objects.count() == 1


# Where a person lands ---------------------------------------------------------


def test_everybody_lands_on_start():
    from core.views import where_they_land

    # With Cases on, where the specification would send them to Cases.
    settings_store.set_to("folder_management", True)
    person = a_person()
    assert where_they_land(person) == reverse("start")

    # And with Cases off, where there is no Cases page at all.
    settings_store.set_to("folder_management", False)
    assert where_they_land(person) == reverse("start")


def test_signing_in_opens_the_start_page(client):
    settings_store.set_to("folder_management", True)
    person = a_person()

    answer = client.post(
        reverse("sign-in"), {"username": person.username, "password": PASSWORD}
    )

    assert answer.status_code == 302
    assert answer["Location"] == reverse("start")


def test_the_start_page_greets_and_asks_one_question(client):
    settings_store.set_to("folder_management", True)
    person = a_person()
    signed_in(client, person)

    page = client.get(reverse("start")).content.decode()

    assert "Good morning" in page or "Good afternoon" in page or "Good evening" in page
    assert "What do you want to do?" in page
    assert "Upload files" in page and "Open a case" in page
    # Record now waits on the Record now setting; Open a case on Cases.
    assert "Record now" not in page
    settings_store.set_to("folder_management", False)
    assert "Open a case" not in client.get(reverse("start")).content.decode()
    # The bar: Start, My recordings, and never Upload or Record on their own.
    assert ">Start</a>" in page and ">My recordings</a>" in page
    assert ">Upload</a>" not in page and ">Recordings</a>" not in page


def test_the_upload_page_asks_what_and_where(client):
    settings_store.set_to("folder_management", True)
    person = a_person()
    signed_in(client, person)

    page = client.get(reverse("upload")).content.decode()

    assert "<h1>Upload files</h1>" in page
    assert "What are these?" in page and "Where do they go?" in page
    # One card per Recording type the office lists, and Something else.
    assert page.count('name="kind"') == len(cases.recording_types()) + 1
    assert 'value="Jail call" data-diarize="1" data-hint="exactly" data-a="2"' in page
    assert 'value="Dictation" data-diarize="0"' in page
    assert "Something else" in page and "This session only" in page
    # Without Cases there is nowhere else for them to go, so no second question.
    settings_store.set_to("folder_management", False)
    page = client.get(reverse("upload")).content.decode()
    assert "What are these?" in page and "Where do they go?" not in page
    # The line that answers the question every new user of this app has.
    assert "Nothing leaves this building" in page


def test_the_pages_carry_the_way_out():
    # A batch user landing on Cases needs the upload from there, and somebody
    # with recordings needs the way to be finished with them.
    from pathlib import Path

    here = Path(__file__).resolve().parent.parent / "templates"
    assert "'upload'" in (here / "cases.html").read_text(encoding="utf-8")
    assert "clear-recordings" in (here / "recordings.html").read_text(encoding="utf-8")
    assert "clear-recordings" in (here / "batch.html").read_text(encoding="utf-8")


def test_every_document_page_is_centred():
    """An inline max-width with no margin puts the column against the left edge.

    Seven pages did this, so on a wide monitor a third of the screen was
    empty beside every one of them. The widths live in one class now.
    """
    from pathlib import Path

    here = Path(__file__).resolve().parent.parent / "templates"
    loose = []
    for page in ("upload", "batch", "recordings", "cases", "clips", "case"):
        text = (here / f"{page}.html").read_text(encoding="utf-8")
        first = text.index("{% block content %}")
        # The page's own wrapper is the first div after the content block.
        opening = text.index("<div", first)
        line = text[opening : text.index(">", opening) + 1]
        if 'class="page' not in line:
            loose.append(f"{page}.html: {line}")

    assert not loose, (
        "these pages set their own width instead of using the centred .page "
        "class, so each sits against the left edge:\n  " + "\n  ".join(loose)
    )

    css = (Path(__file__).resolve().parent.parent / "static" / "app.css").read_text(
        encoding="utf-8"
    )
    assert ".page { max-width: 52rem; margin: 0 auto; }" in css
