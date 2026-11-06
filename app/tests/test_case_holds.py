"""v1.214.0: what the case holds decides its tabs (Phase 12 chapter 12).

The rules checked here: an audio-only case carries six tabs and no Add path
files, and its Proposed events, Documents, Incidents and Map addresses fall
to Recordings with a notice; a video shows the three tabs and offers Add
path files; the first path file read unlocks the Map tab, the pill and the
desk's small map; the Map page sends to the case until then; the take-in
refuses a case with no video; the pills follow; one helper answers it all.
"""

from __future__ import annotations

import io

import pytest
from core import camera_paths, case_bar, cases, dashboard, settings_store
from core.cases import Case
from core.models import User
from core.recordings import Batch, MediaState, Recording
from tests.helpers import signed_in, stamp
from tests.test_camera_paths import body_file

PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def switched_on(db):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("incidents", True)
    settings_store.set_to("documents", True)
    settings_store.set_to("maps", True)


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("asker", PASSWORD)


@pytest.fixture
def a_case(person):
    return Case.objects.create(owner=person, name="Pike calls")


def recording(person, case, title, *, video: bool):
    """A sound recording (an .m4a copy, a probe with an audio stream alone)
    or a video (an .mp4 copy, a video stream in the probe)."""
    streams = [{"codec_type": "audio"}] + ([{"codec_type": "video"}] if video else [])
    one = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        case=case,
        title=title,
        original_filename=f"{title}.{'mp4' if video else 'm4a'}",
        media_state=MediaState.READY,
        duration_seconds=600.0,
        playback_ready=True,
        stamp=stamp("21:56:19", "BWC2-1") if video else None,
        probe={"streams": streams},
    )
    one.folder.mkdir(parents=True, exist_ok=True)
    (one.folder / f"playback.{'mp4' if video else 'm4a'}").write_bytes(b"not media")
    return one


def keys(case, **more):
    return [t["key"] for t in case_bar.bar(case, on="recordings", **more)["tabs"]]


AUDIO_ONLY = ["recordings", "search", "notes", "clips", "speakers", "details"]
VIDEO = [
    "recordings",
    "search",
    "proposed",
    "notes",
    "documents",
    "incidents",
    "clips",
    "speakers",
    "details",
]


def test_the_helper_reads_the_three_states(person, a_case):
    assert cases.holds(a_case) == {"has_video": False, "has_path": False, "waiting": 0}
    recording(person, a_case, "Call 1", video=False)
    assert cases.holds(a_case)["has_video"] is False
    camera = recording(person, a_case, "BWC2-1", video=True)
    held = cases.holds(a_case)
    assert held["has_video"] is True and held["has_path"] is False
    camera_paths.add(
        camera, data=PATH_FILE, filename="BWC2-1.vtt", by=person, request=None
    )
    held = cases.holds(a_case)
    assert held["has_path"] is True
    # Maps off: no path counts, whatever the case holds.
    settings_store.set_to("maps", False)
    assert cases.holds(a_case)["has_path"] is False


def test_the_tabs_follow_what_the_case_holds(person, a_case, client):
    signed_in(client, person)
    # Audio only: six tabs, no Add path files, hidden addresses fall to
    # Recordings with a notice.
    recording(person, a_case, "Call 1", video=False)
    assert keys(a_case) == AUDIO_ONLY
    page = client.get(f"/case/{a_case.pk}").content.decode()
    assert 'id="case-add-paths"' not in page and "?tab=incidents" not in page
    page = client.get(f"/case/{a_case.pk}?tab=details").content.decode()
    assert "sound recordings only" in page
    for tab, name in (
        ("incidents", "Incidents"),
        ("documents", "Documents"),
        ("proposed", "Proposed events"),
    ):
        got = client.get(f"/case/{a_case.pk}?tab={tab}", follow=True)
        text = got.content.decode()
        assert f"it has no {name} tab" in text and 'class="tab on"' in text
    got = client.get(f"/case/{a_case.pk}?tab=map", follow=True)
    assert "No camera in this case has a path file yet" in got.content.decode()
    assert client.get(f"/case/{a_case.pk}/map", follow=True).redirect_chain
    # A video: the three tabs, Add path files, no Map yet.
    camera = recording(person, a_case, "BWC2-1", video=True)
    assert keys(a_case) == VIDEO
    page = client.get(f"/case/{a_case.pk}?tab=details").content.decode()
    assert 'id="case-add-paths"' in page
    assert f'href="/case/{a_case.pk}/map" class="tab"' not in page
    assert "none yet" in page and "the Map tab appears" in page
    page = client.get(f"/case/{a_case.pk}?tab=incidents").content.decode()
    assert 'id="strip-map"' not in page and 'id="desk-yours"' in page
    # The first path file read unlocks the Map.
    camera_paths.add(
        camera, data=PATH_FILE, filename="BWC2-1.vtt", by=person, request=None
    )
    assert keys(a_case) == VIDEO[:6] + ["map"] + VIDEO[6:]
    page = client.get(f"/case/{a_case.pk}?tab=incidents").content.decode()
    assert 'id="strip-map"' in page
    assert client.get(f"/case/{a_case.pk}/map").status_code == 200
    page = client.get(f"/case/{a_case.pk}?tab=details").content.decode()
    assert "1 camera with a path file" in page
    # The helper handed in is honoured as given.
    assert "map" not in keys(a_case, holds={"has_video": True, "has_path": False})
    assert keys(a_case, holds={"has_video": False, "has_path": False}) == AUDIO_ONLY


def test_the_take_in_refuses_a_case_with_no_video_and_the_pills_follow(
    person, a_case, client
):
    signed_in(client, person)
    recording(person, a_case, "Call 1", video=False)
    upload = io.BytesIO(PATH_FILE)
    upload.name = "Call 1.vtt"
    told = client.post(f"/case/{a_case.pk}/paths/add", {"files": [upload]})
    assert told.status_code == 400
    assert told.json()["error"].startswith("Add a video to the case first")
    assert camera_paths.waiting_count(a_case) == 0
    # The pills: an audio-only case draws no incident pill.
    counts = dashboard.counts_for([a_case], person)[a_case.pk]
    assert counts["videos"] == 0
    counts["incidents"]["unsynced"] = 1
    assert all(
        "not synced" not in one["words"]
        for one in dashboard.pills(a_case, "owner", person, counts)
    )
    recording(person, a_case, "BWC2-1", video=True)
    counts = dashboard.counts_for([a_case], person)[a_case.pk]
    assert counts["videos"] == 1
    counts["incidents"]["unsynced"] = 1
    assert any(
        "not synced" in one["words"]
        for one in dashboard.pills(a_case, "owner", person, counts)
    )
    # With a video the take-in takes the file.
    upload = io.BytesIO(PATH_FILE)
    upload.name = "BWC2-1.vtt"
    told = client.post(f"/case/{a_case.pk}/paths/add", {"files": [upload]})
    assert told.status_code == 200, told.content


PATH_FILE = body_file()
