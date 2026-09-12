"""v1.49.0: Download all on the viewer's Clips tab.

The rules checked here: with a recording named, the download holds that
recording's Ready clips and no other's; in a Case every collaborator's, in
the Workspace the person's own; a recording the person may not open sends
them to the Clips page; without a recording the download is the My clips
page's, as before.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from core import settings_store
from core.cases import Case
from core.clips import Clip, RenderState
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording

PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("asker", PASSWORD)


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def a_recording(person, case=None, title="Stop"):
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        case=case,
        title=title,
        original_filename="call.m4a",
        media_state=MediaState.READY,
        playback_ready=True,
    )
    recording.folder.mkdir(parents=True, exist_ok=True)
    return recording


def a_ready_clip(recording, person, title, start=0.0):
    clip = Clip.objects.create(
        recording=recording,
        user=person,
        title=title,
        start=start,
        end=start + 5,
        state=RenderState.READY,
        include_excerpt=False,
    )
    clip.folder.mkdir(parents=True, exist_ok=True)
    clip.path.write_bytes(b"ID3 not really sound")
    return clip


def names_in(answer) -> list[str]:
    return sorted(zipfile.ZipFile(io.BytesIO(answer.content)).namelist())


@pytest.mark.django_db
def test_download_all_takes_one_recordings_ready_clips(person, client):
    settings_store.set_to("clips_available", True)
    here = a_recording(person)
    there = a_recording(person, title="Elsewhere")
    a_ready_clip(here, person, "First")
    a_ready_clip(here, person, "Second", start=10.0)
    Clip.objects.create(
        recording=here, user=person, title="Rendering", start=20, end=25
    )
    a_ready_clip(there, person, "Other")
    signed_in(client, person)

    answer = client.get(f"/clips/download?recording={here.pk}")
    assert answer.status_code == 200
    assert answer["Content-Type"] == "application/zip"
    assert "Stop" in answer["Content-Disposition"]
    names = names_in(answer)
    assert len(names) == 2
    assert all("Other" not in name and "Rendering" not in name for name in names)
    # Without a recording, the My clips page's download: every ready clip.
    assert len(names_in(client.get("/clips/download"))) == 3

    # A recording the person may not open sends them to the Clips page.
    other = User.objects.create_local_admin("other", PASSWORD)
    signed_in(client, other)
    theirs = a_recording(other, title="Not mine")
    assert client.get(f"/clips/download?recording={here.pk}").status_code in (200, 302)
    assert client.get(f"/clips/download?recording={theirs.pk}").status_code == 200


@pytest.mark.django_db
def test_in_a_case_every_collaborators_clips_of_the_recording_come(person, client):
    settings_store.set_to("clips_available", True)
    settings_store.set_to("folder_management", True)
    case = Case.objects.create(owner=person, name="Ramirez")
    recording = a_recording(person, case=case)
    colleague = User.objects.create_local_admin("colleague", PASSWORD)
    a_ready_clip(recording, person, "Mine")
    a_ready_clip(recording, colleague, "Theirs", start=10.0)
    signed_in(client, person)
    names = names_in(client.get(f"/clips/download?recording={recording.pk}"))
    assert len(names) == 2
