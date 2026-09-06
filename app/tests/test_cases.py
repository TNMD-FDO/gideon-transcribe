"""Cases: where the files go, what the Discard leaves alone, and what counts.

The rules checked here are the four that would be expensive to get wrong and
cheap to get wrong: a Recording in a Case must live under that Case, the
Discard must not take it, the quota must count it once, and the days Folder
management was off must be recorded as they pass, because they cannot be
worked out afterwards.
"""

import pytest
from core import cases, lifecycle, settings_store, sweeping, uploads
from core.cases import Case, OffSpell
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording
from django.conf import settings

PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings):
    """A fresh App data folder for each test.

    The database rolls back at the end of a test and the disk does not, so
    without this the folders one test writes are still there for the next one,
    and a sweeper counting orphans counts everybody's.
    """
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"
    return tmp_path


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("case-owner", PASSWORD)


@pytest.fixture
def a_case(person):
    return Case.objects.create(owner=person, name="Ramirez")


def a_recording(person, case=None, size=0):
    batch = Batch.objects.create(user=person)
    recording = Recording.objects.create(
        batch=batch,
        user=person,
        case=case,
        title="an interview",
        original_filename="interview.m4a",
        media_state=MediaState.READY,
    )
    if size:
        recording.folder.mkdir(parents=True, exist_ok=True)
        (recording.folder / "original.m4a").write_bytes(b"x" * size)
    return recording


# Where the bytes live ---------------------------------------------------------


def test_a_workspace_recording_lives_under_scratch(person):
    recording = a_recording(person)
    assert recording.folder.parent == settings.SCRATCH_DIR / str(person.pk)


def test_a_recording_in_a_case_lives_under_that_case(person, a_case):
    recording = a_recording(person, case=a_case)
    assert recording.folder == a_case.folder / str(recording.pk)
    assert recording.folder.parent.parent.name == "cases"


def test_renaming_a_case_moves_nothing(person, a_case):
    recording = a_recording(person, case=a_case)
    was = recording.folder
    cases.rename(a_case, "Ramirez, second file", actor=person)
    recording.refresh_from_db()
    assert recording.folder == was


def test_moving_a_recording_in_renames_its_folder(person, a_case):
    recording = a_recording(person, size=64)
    was = recording.folder
    assert (was / "original.m4a").exists()

    cases.move_recording(recording, a_case, actor=person, description="the jail call")

    recording.refresh_from_db()
    assert not was.exists()
    assert (recording.folder / "original.m4a").read_bytes() == b"x" * 64
    assert recording.description == "the jail call"


# What the Discard leaves alone -------------------------------------------------


def test_the_discard_takes_the_workspace_and_leaves_the_case(person, a_case):
    in_the_workspace = a_recording(person, size=32)
    in_a_case = a_recording(person, case=a_case, size=32)

    removed, _ = lifecycle.discard(person)

    assert removed == 1
    assert not Recording.objects.filter(pk=in_the_workspace.pk).exists()
    assert Recording.objects.filter(pk=in_a_case.pk).exists()
    assert (in_a_case.folder / "original.m4a").exists()


def test_a_case_recording_does_not_make_the_workspace_look_busy(person, a_case):
    a_recording(person, case=a_case)
    assert lifecycle.is_empty(person)


def test_the_sign_out_tally_counts_the_workspace_only(person, a_case):
    a_recording(person)
    a_recording(person, case=a_case)
    assert lifecycle.counts(person)["recordings"] == 1


# What a person's space counts --------------------------------------------------


def test_a_recording_in_a_case_counts_once(person, a_case):
    a_recording(person, case=a_case, size=1000)
    # Counted with the Case, not again with the person who uploaded it.
    assert uploads.used_bytes(person) == 1000


def test_the_workspace_and_the_case_are_added_together(person, a_case):
    a_recording(person, size=1000)
    a_recording(person, case=a_case, size=1000)
    assert uploads.used_bytes(person) == 2000


# The sweeper -------------------------------------------------------------------


def test_a_case_folder_with_no_recording_row_is_swept(person, a_case):
    recording = a_recording(person, case=a_case, size=16)
    orphan = recording.folder
    Recording.objects.filter(pk=recording.pk).delete()

    assert sweeping.folders_without_a_recording() == 1
    assert not orphan.exists()


def test_a_case_folder_with_a_row_is_left(person, a_case):
    recording = a_recording(person, case=a_case, size=16)
    assert sweeping.folders_without_a_recording() == 0
    assert recording.folder.exists()


# The toggle's own record --------------------------------------------------------


def test_turning_it_off_opens_a_spell_and_on_closes_it(db):
    settings_store.set_to("folder_management", False)
    spell = cases.open_spell()
    assert spell is not None and spell.ended is None

    settings_store.set_to("folder_management", True)
    spell.refresh_from_db()
    assert spell.ended is not None
    assert cases.open_spell() is None


def test_turning_it_off_twice_leaves_one_spell(db):
    settings_store.set_to("folder_management", False)
    settings_store.set_to("folder_management", False)
    assert OffSpell.objects.count() == 1


def signed_in(client, person):
    """A browser with a Login session behind it, which the middleware wants."""
    client.force_login(person)
    LoginSession.objects.create(user=person, session_key=client.session.session_key)
    return client


def test_the_pages_are_gone_while_it_is_off(person, a_case, client):
    signed_in(client, person)
    settings_store.set_to("folder_management", False)
    assert client.get("/cases").status_code == 404
    assert client.get(f"/case/{a_case.pk}").status_code == 404

    settings_store.set_to("folder_management", True)
    assert client.get("/cases").status_code == 200
    assert client.get(f"/case/{a_case.pk}").status_code == 200


def test_nothing_is_deleted_while_it_is_off(person, a_case):
    recording = a_recording(person, case=a_case, size=16)
    settings_store.set_to("folder_management", False)

    assert Case.objects.filter(pk=a_case.pk).exists()
    assert recording.folder.exists()
    # The sweeper still runs, and still removes only what no row claims.
    assert sweeping.folders_without_a_recording() == 0
    assert recording.folder.exists()


# What is still the Workspace's, and what has stopped being it -------------------


def a_transcript(recording):
    from core.jobs import Segment, Transcript

    transcript = Transcript.objects.create(recording=recording, language="en")
    Segment.objects.create(
        transcript=transcript, start=0, end=4, text="Good morning.", speaker="Rowe"
    )
    return transcript


def test_the_sign_out_download_leaves_a_case_alone(person, a_case, client):
    import io
    import zipfile

    workspace = a_recording(person, size=8)
    a_transcript(workspace)
    in_a_case = a_recording(person, case=a_case, size=8)
    a_transcript(in_a_case)

    signed_in(client, person)
    answer = client.get("/download/transcripts")
    assert answer.status_code == 200

    inside = zipfile.ZipFile(io.BytesIO(answer.getvalue())).namelist()
    # One transcript in the zip, and it is the one still in the Workspace: what
    # is in a case is kept, so it is not among the things a person is offered
    # before they lose them.
    assert len([one for one in inside if one.endswith(".txt")]) == 1
    assert in_a_case is not None


def test_the_clips_page_is_the_workspaces_own(person, a_case, client):
    from core.clips import Clip

    in_a_case = a_recording(person, case=a_case)
    Clip.objects.create(
        recording=in_a_case, user=person, title="Clip in a case", start=0, end=5
    )
    workspace = a_recording(person)
    Clip.objects.create(
        recording=workspace, user=person, title="Clip in the session", start=0, end=5
    )

    signed_in(client, person)
    page = client.get("/clips").content.decode()
    assert "Clip in the session" in page
    assert "Clip in a case" not in page


# The Retention clock -----------------------------------------------------------


def test_opening_a_recording_in_a_case_counts_as_use(person, a_case, client):
    from datetime import timedelta

    from django.utils import timezone

    recording = a_recording(person, case=a_case)
    a_transcript(recording)

    long_ago = timezone.now() - timedelta(days=40)
    Case.objects.filter(pk=a_case.pk).update(last_activity=long_ago)

    signed_in(client, person)
    settings_store.set_to("folder_management", True)
    client.get(f"/recording/{recording.pk}")

    a_case.refresh_from_db()
    assert a_case.last_activity > long_ago


def test_an_admin_looking_in_is_not_use(person, a_case, client):
    from datetime import timedelta

    from django.utils import timezone

    an_admin = User.objects.create_local_admin("someone-else", PASSWORD)
    long_ago = timezone.now() - timedelta(days=40)
    Case.objects.filter(pk=a_case.pk).update(last_activity=long_ago)

    signed_in(client, an_admin)
    settings_store.set_to("folder_management", True)
    assert client.get(f"/case/{a_case.pk}").status_code == 200

    a_case.refresh_from_db()
    # Down to the second, because the update above set it and nothing since
    # should have moved it.
    assert abs((a_case.last_activity - long_ago).total_seconds()) < 1


# Opening a case, and taking its transcripts away ---------------------------------


def test_a_case_opens_on_its_own_page_whatever_it_holds(person, a_case, client):
    from core.case_pages import opens_at

    # One door: empty, holding something not yet transcribed, or holding
    # transcripts, a case opens on its page, and the page is where a
    # recording is opened from.
    assert opens_at(a_case) == f"/case/{a_case.pk}"
    a_recording(person, case=a_case)
    assert opens_at(a_case) == f"/case/{a_case.pk}"
    newer = a_recording(person, case=a_case)
    a_transcript(newer)
    assert opens_at(a_case) == f"/case/{a_case.pk}"

    signed_in(client, person)
    page = client.get("/cases").content.decode()
    assert f'data-open="/case/{a_case.pk}"' in page
    assert "Case page" not in page and 'id="detail-pane"' not in page
    # The viewer shows the way back to the case beside the title.
    viewer = client.get(f"/recording/{newer.pk}").content.decode()
    assert f'href="/case/{a_case.pk}"' in viewer and "Back to the case" in viewer


def test_the_case_download_holds_every_transcript_in_it(person, a_case, client):
    import io
    import zipfile

    first = a_recording(person, case=a_case, size=8)
    a_transcript(first)
    second = a_recording(person, case=a_case, size=8)
    a_transcript(second)
    # Not yet transcribed, so it is simply left out.
    a_recording(person, case=a_case, size=8)
    # And another case's recording is nothing to do with this zip.
    elsewhere = Case.objects.create(owner=person, name="Delgado")
    a_transcript(a_recording(person, case=elsewhere, size=8))

    signed_in(client, person)
    settings_store.set_to("folder_management", True)
    answer = client.get(f"/case/{a_case.pk}/download")

    assert answer.status_code == 200
    inside = zipfile.ZipFile(io.BytesIO(answer.getvalue())).namelist()
    assert len(inside) == 2
    assert first is not None and second is not None


def test_the_case_download_is_gone_while_folder_management_is_off(
    person, a_case, client
):
    a_transcript(a_recording(person, case=a_case, size=8))
    signed_in(client, person)
    settings_store.set_to("folder_management", False)
    assert client.get(f"/case/{a_case.pk}/download").status_code == 404


# Clips in a case ---------------------------------------------------------------


def a_clip(recording, person, title="Clip 1"):
    from core.clips import Clip

    return Clip.objects.create(
        recording=recording, user=person, title=title, start=0, end=5
    )


def test_the_sheet_shows_the_whole_case_with_this_recording_first(
    person, a_case, client
):
    here = a_recording(person, case=a_case)
    a_transcript(here)
    a_clip(here, person, "Mine")
    elsewhere = a_recording(person, case=a_case)
    a_clip(elsewhere, person, "Theirs")

    signed_in(client, person)
    settings_store.set_to("folder_management", True)
    said = client.get(f"/recording/{here.pk}/clips").json()

    assert said["in_case"] is True
    assert [one["title"] for one in said["clips"]] == ["Mine", "Theirs"]
    assert [one["here"] for one in said["clips"]] == [True, False]
    # A case says who saved a clip and never whether it has been downloaded,
    # because nothing is lost at sign-out there.
    assert said["clips"][0]["saved_by"]
    assert said["clips"][0]["downloaded"] == ""


def test_the_sheet_is_one_recordings_own_in_the_workspace(person, client):
    here = a_recording(person)
    a_transcript(here)
    a_clip(here, person, "Mine")
    a_clip(a_recording(person), person, "Another recording's")

    signed_in(client, person)
    said = client.get(f"/recording/{here.pk}/clips").json()

    assert said["in_case"] is False
    assert [one["title"] for one in said["clips"]] == ["Mine"]
    assert said["clips"][0]["downloaded"] == "Not yet"


def test_a_case_clip_is_not_on_the_workspace_sheet_while_cases_are_off(
    person, a_case, client
):
    here = a_recording(person, case=a_case)
    a_transcript(here)
    a_clip(here, person, "Mine")
    a_clip(a_recording(person, case=a_case), person, "Theirs")

    signed_in(client, person)
    settings_store.set_to("folder_management", False)
    said = client.get(f"/recording/{here.pk}/clips").json()

    # Off hides the case, so the sheet is this recording's own again.
    assert said["in_case"] is False
    assert [one["title"] for one in said["clips"]] == ["Mine"]
