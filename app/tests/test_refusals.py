"""v1.44.0: the incomplete-file refusal, the duplicate's link, and back to the case.

The rules checked here: an MP4 whose index was never written is refused as
incomplete, by ffprobe's own words, with a message that says what to do,
and any other probe failure stays undecodable; a duplicate's refusal on the
Batch page links to the recording it already is; a Batch every Recording of
which went to one Case carries that Case in its state and on its page, and
a Batch that went elsewhere does not.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from core import media, settings_store
from core.cases import Case
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording, Refusal

PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"


@pytest.fixture
def admin(db):
    return User.objects.create_local_admin("asker", PASSWORD)


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def a_probe_that_fails(monkeypatch, stderr):
    def run(arguments, timeout):
        return subprocess.CompletedProcess(arguments, 1, stdout="", stderr=stderr)

    monkeypatch.setattr(media, "_run", run)


# Without a database ------------------------------------------------------------------


def test_a_file_without_its_index_is_refused_as_incomplete(monkeypatch):
    a_probe_that_fails(
        monkeypatch,
        "[mov,mp4,m4a,3gp,3g2,mj2 @ 0x63cd3cea1f40] moov atom not found\n"
        "/srv/data/x/original.mp4: Invalid data found when processing input\n",
    )
    with pytest.raises(media.MediaError) as refused:
        media.probe(Path("original.mp4"))
    assert refused.value.reason_class == Refusal.INCOMPLETE_FILE == "incomplete_file"
    assert refused.value.message.startswith("This file is incomplete")
    assert "export it again" in refused.value.message
    assert Refusal.INCOMPLETE_FILE in Refusal.ALL
    # The test decode says the same when it is the one that meets it.
    with pytest.raises(media.MediaError) as again:
        media.test_decode(Path("original.mp4"), None)
    assert again.value.reason_class == Refusal.INCOMPLETE_FILE


def test_any_other_probe_failure_stays_undecodable(monkeypatch):
    a_probe_that_fails(
        monkeypatch, "original.wav: Invalid data found when processing input\n"
    )
    with pytest.raises(media.MediaError) as refused:
        media.probe(Path("original.wav"))
    assert refused.value.reason_class == Refusal.UNDECODABLE
    assert refused.value.message == Refusal.MESSAGES[Refusal.UNDECODABLE]
    assert media.refusal_for("") == (
        Refusal.MESSAGES[Refusal.UNDECODABLE],
        Refusal.UNDECODABLE,
    )
    assert media.refusal_for(None)[1] == Refusal.UNDECODABLE


# With a database ----------------------------------------------------------------------


def a_recording(person, batch, case=None, **fields):
    wanted = {
        "title": "A call",
        "original_filename": "call.m4a",
        "media_state": MediaState.READY,
    }
    wanted.update(fields)
    return Recording.objects.create(batch=batch, user=person, case=case, **wanted)


@pytest.mark.django_db
def test_a_duplicate_refusal_links_to_the_recording_it_already_is(admin, client):
    settings_store.set_to("folder_management", True)
    case = Case.objects.create(owner=admin, name="Ramirez")
    earlier = a_recording(
        admin,
        Batch.objects.create(user=admin),
        case,
        title="EthanWilson_202506072133_BWC2098679-0",
        sha256="66345e91",
    )
    batch = Batch.objects.create(user=admin)
    twin = a_recording(
        admin,
        batch,
        case,
        title="01-bodycam",
        sha256="66345e91",
        media_state=MediaState.REJECTED,
        refusal_class=Refusal.ALREADY_UPLOADED,
        failure_message=Refusal.MESSAGES[Refusal.ALREADY_UPLOADED].format(
            title=earlier.title
        ),
    )
    signed_in(client, admin)
    state = client.get(f"/batch/{batch.pk}/state").json()
    row = state["recordings"][0]
    assert row["id"] == str(twin.pk) and row["state"] == "rejected"
    assert row["already"] == {
        "id": str(earlier.pk),
        "title": earlier.title,
        "url": f"/recording/{earlier.pk}",
    }
    assert earlier.title in row["message"]
    # Any other refusal, and a duplicate whose twin has gone, carry no link.
    twin.refusal_class = Refusal.INCOMPLETE_FILE
    twin.save()
    assert (
        client.get(f"/batch/{batch.pk}/state").json()["recordings"][0]["already"]
        is None
    )
    twin.refusal_class = Refusal.ALREADY_UPLOADED
    twin.save()
    earlier.delete()
    assert (
        client.get(f"/batch/{batch.pk}/state").json()["recordings"][0]["already"]
        is None
    )


@pytest.mark.django_db
def test_a_batch_added_to_a_case_knows_the_way_back(admin, client):
    settings_store.set_to("folder_management", True)
    case = Case.objects.create(owner=admin, name="Ramirez")
    batch = Batch.objects.create(user=admin)
    a_recording(admin, batch, case)
    a_recording(admin, batch, case, title="Another")
    signed_in(client, admin)
    state = client.get(f"/batch/{batch.pk}/state").json()
    assert state["finished"] is True
    assert state["case"] == {
        "id": str(case.pk),
        "name": "Ramirez",
        "url": f"/case/{case.pk}",
    }
    page = client.get(f"/batch/{batch.pk}").content.decode()
    assert "Back to Ramirez" in page and 'id="stay-here"' in page
    assert 'window.BATCH_CASE = { name: "Ramirez"' in page

    # Files that went to several places, or to the person's own recordings,
    # have no one place to go back to.
    a_recording(admin, batch, None, title="Loose")
    assert client.get(f"/batch/{batch.pk}/state").json()["case"] is None
    page = client.get(f"/batch/{batch.pk}").content.decode()
    assert "Back to Ramirez" not in page and "window.BATCH_CASE = null" in page

    own = Batch.objects.create(user=admin)
    a_recording(admin, own, None)
    assert client.get(f"/batch/{own.pk}/state").json()["case"] is None

    # Cases off: the way back is hidden with the case.
    settings_store.set_to("folder_management", False)
    only = Batch.objects.create(user=admin)
    a_recording(admin, only, case)
    assert client.get(f"/batch/{only.pk}/state").json()["case"] is None
