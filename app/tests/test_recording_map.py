"""The Map tab on the recording page (Phase 13 chapter 2, release 3,
v1.223.0; the drawing phase-13-recording-page.html, figures 6 and 9): the
tab's four shapes by what the recording holds, the panel and its host, the
shape endpoint, the Details row, and the scripts' and stylesheet's pieces."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from core import camera_paths, settings_store, viewer
from core.cases import Case
from core.jobs import Transcript
from core.models import User
from core.recordings import Batch, MediaState, Recording
from tests.helpers import signed_in

APP = Path(__file__).resolve().parent.parent
STATIC = APP / "static"
PAGE = (APP / "templates" / "viewer.html").read_text(encoding="utf-8")
HOST = (APP / "templates" / "map-host.html").read_text(encoding="utf-8")
CSS = (STATIC / "app.css").read_text(encoding="utf-8")
MAP = (STATIC / "map.js").read_text(encoding="utf-8")
REC = (STATIC / "recording-map.js").read_text(encoding="utf-8")
VIEWER = (STATIC / "viewer.js").read_text(encoding="utf-8")

DAY = dt.date(2025, 11, 6)


def a_recording(person, a_case, title, *, picture=True, on_clock=True):
    one = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        case=a_case,
        title=title,
        original_filename=f"{title}.mp4" if picture else f"{title}.m4a",
        media_state=MediaState.READY,
        duration_seconds=600.0,
        playback_ready=True,
        probe={},
        clock_date=DAY if on_clock else None,
        clock_start=51600.0 if on_clock else None,
        clock_how="hand" if on_clock else "",
    )
    one.folder.mkdir(parents=True, exist_ok=True)
    (one.folder / ("playback.mp4" if picture else "playback.m4a")).write_bytes(b"x")
    Transcript.objects.create(recording=one, language="en")
    return one


def a_path(recording, fixes=1):
    return camera_paths.CameraPath.objects.create(
        recording=recording,
        fixes=[[float(i), 41.8 + i * 0.0001, -87.6] for i in range(fixes)],
        fix_count=fixes,
        length=600.0,
        original_filename=f"{recording.title}.vtt",
    )


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("asker", "a-long-enough-password")


@pytest.fixture
def a_case(person):
    return Case.objects.create(owner=person, name="Traffic stop")


@pytest.fixture
def maps_on():
    settings_store.set_to("maps", True)
    settings_store.set_to("folder_management", True)


def test_the_four_shapes_by_what_the_recording_holds(person, a_case, maps_on):
    own = a_recording(person, a_case, "BWC-own")
    a_path(own)
    assert viewer.map_tab(own, True)["shape"] == "own"
    # A camera with no file of its own, on a day another camera has fixes.
    around = a_recording(person, a_case, "BWC-around")
    told = viewer.map_tab(around, True)
    assert told["shape"] == "around" and told["own"] is False
    assert told["day"] == "2025-11-06" and told["second"] == 51600.0
    # Not on the clock and no file: no tab.
    alone = a_recording(person, a_case, "BWC-alone", on_clock=False)
    assert viewer.map_tab(alone, True) == {}
    # A file waiting on the case for it: the waiting shape, clock or not.
    camera_paths.WaitingPathFile.objects.create(
        case=a_case,
        original_filename="BWC-alone.vtt",
        stem="BWC-alone",
        source=camera_paths.CAR,
        cues=12,
        flagged="named like this video, which came later",
        flagged_recording=alone,
    )
    told = viewer.map_tab(alone, True)
    assert told["shape"] == "waiting"
    assert told["waiting"]["file"] == "BWC-alone.vtt"
    assert told["waiting"]["kind"] == "in-car" and told["waiting"]["cues"] == 12
    # No picture: never a tab, whatever the case holds.
    call = a_recording(person, a_case, "Call", picture=False)
    assert viewer.map_tab(call, False) == {}
    # Maps off: nothing.
    settings_store.set_to("maps", False)
    assert viewer.map_tab(own, True) == {}


def test_the_shape_is_placed_as_the_map_places_it(person, a_case, maps_on):
    # v1.224.1: a camera whose recording carries no clock fields but whose
    # in-car file has its own clock is on the map, so it has the tab; and a
    # camera with no file beside it that day is "around" by the same rule.
    import datetime as dt

    from django.utils import timezone

    own = a_recording(person, a_case, "Unit-9082", on_clock=False)
    path = a_path(own)
    path.clock_start = timezone.make_aware(dt.datetime(2025, 11, 6, 14, 20, 0))
    path.save(update_fields=["clock_start"])
    told = viewer.map_tab(own, True)
    assert told["shape"] == "own" and told["day"] == "2025-11-06"
    assert told["second"] == 14 * 3600 + 20 * 60
    # The other camera, placed by the app's clock, finds this one on its day.
    beside = a_recording(person, a_case, "BWC-beside")
    assert viewer.map_tab(beside, True)["shape"] == "around"


def test_the_page_carries_the_tab_the_panel_and_the_host(
    person, a_case, client, maps_on
):
    own = a_recording(person, a_case, "BWC-own")
    a_path(own)
    around = a_recording(person, a_case, "BWC-around")
    signed_in(client, person)
    page = client.get(f"/recording/{own.pk}").content.decode()
    # The map in the stage (v1.225.0): no Map tab; the stage's map and switch.
    assert 'data-panel="map"' not in page
    assert 'id="stage-map" data-shape="own"' in page and 'id="stage-switch"' in page
    assert (
        'data-clock-start="51600.0" data-clock-date="2025-11-06" data-own="1"' in page
    )
    assert 'data-clock="recording"' in page and 'data-day="2025-11-06"' in page
    assert f'data-recording="{own.pk}"' in page
    assert 'id="map-now"' in page and "said-list" not in page
    assert "recording-map.js" in page and "map.js" in page
    assert 'class="pill small tab-mark"' not in page
    # The around shape: the mark on the tab and the notice above the map.
    page = client.get(f"/recording/{around.pk}").content.decode()
    assert 'data-shape="around"' in page and ">around</span>" in page
    assert "its own place is not known" in page
    assert f'href="/case/{a_case.pk}?tab=map"' in page
    # The shape endpoint, for the page's watcher.
    assert client.get(f"/recording/{own.pk}/map-shape").json() == {"shape": "own"}
    assert client.get(f"/recording/{around.pk}/map-shape").json() == {"shape": "around"}


def test_no_tab_without_a_map_and_the_details_offer(person, a_case, client, maps_on):
    alone = a_recording(person, a_case, "BWC-alone", on_clock=False)
    call = a_recording(person, a_case, "Call", picture=False)
    signed_in(client, person)
    page = client.get(f"/recording/{alone.pk}").content.decode()
    assert "stage-map" not in page and 'id="stage-switch"' not in page
    # The watcher still runs, so a file that lands brings the tab.
    assert 'id="recording-map-script"' in page and 'data-shape=""' in page
    assert client.get(f"/recording/{alone.pk}/map-shape").json() == {"shape": ""}
    told = client.get(f"/recording/{alone.pk}/details").json()["camera_file"]
    assert told["words"] == "none yet · not on the case's clock"
    assert told["url"] == f"/case/{a_case.pk}?tab=map"
    page = client.get(f"/recording/{call.pk}").content.decode()
    assert "stage-map" not in page
    assert client.get(f"/recording/{call.pk}/details").json()["camera_file"] == {}


def test_the_waiting_card_stands_above_the_map(person, a_case, client, maps_on):
    alone = a_recording(person, a_case, "BWC-alone", on_clock=False)
    # Named like the video, so it matches by stem alone, as match_files keeps it.
    waiting = camera_paths.WaitingPathFile.objects.create(
        case=a_case,
        original_filename="BWC-alone.vtt",
        stem=camera_paths.stem_of("BWC-alone.vtt"),
        cues=3,
    )
    signed_in(client, person)
    page = client.get(f"/recording/{alone.pk}").content.decode()
    assert 'data-shape="waiting"' in page and ">file waiting</span>" in page
    assert 'id="rec-map-waiting"' in page
    assert f"/paths/waiting/{waiting.pk}/add-anyway" in page
    assert f"/paths/waiting/{waiting.pk}/remove" in page
    assert 'data-waiting="add"' in page and 'data-waiting="remove"' in page


def test_the_scripts_and_the_stylesheet_hold_the_pieces():
    # map.js: the recording mode beside the incident's.
    assert 'var REC = host.dataset.clock === "recording";' in MAP
    assert "var CLOCKED = INC || REC;" in MAP
    assert "if (REC && window.RecordingClock) { return window.RecordingClock; }" in MAP
    assert 'map.addSource("map-said"' in MAP and 'map.on("click", "map-said-hit"' in MAP
    assert "if (REC) { recStart(); }" in MAP and "if (REC) { recTick(m); }" in MAP
    assert "function goToCamera(cam)" in MAP and "window.CaseMap = {" in MAP
    assert "data-act='here'" in MAP
    # This camera alone or all the cameras of the day (v1.225.1), remembered
    # for the case as one word; no menu of ticks to fall off a short stage.
    assert "function recHidden()" in MAP and 'remember("map-rec-cams-" + CASE' in MAP
    assert "data-cams='own'" in MAP and "data-cams='all'" in MAP
    assert "data-other" not in MAP and "map-others" not in MAP
    # recording-map.js: the clock, the switch, the card, the watcher.
    assert "window.RecordingClock = {" in REC
    assert "start + player.currentTime" in REC and "lineIndex: hereIndex" in REC
    assert 'document.getElementById("stage-switch")' in REC
    assert 'window.localStorage.setItem("stage-mode", mode)' in REC
    assert 'document.getElementById("rec-map-waiting")' in REC
    assert "script.dataset.shapeUrl" in REC and "}, 30000);" in REC
    # The host include takes the recording and the day from the page.
    assert "{% if map_recording %}{{ map_recording }}" in HOST
    assert "{% if map_day %}{{ map_day }}" in HOST
    # viewer.js: the tab stays on the page, the timeline's ticks, the row.
    assert "height - 3, 1, 3);" in VIEWER
    assert "function drawCameraFile(told)" in VIEWER
    for rule in (
        ".desk:not(.sound) .stage-map { display: flex; flex-direction: column;",
        ".stage-map .map-foot { position: absolute; top: 0; left: 0; right: 0;",
        '.stage[data-mode="picture"] .stage-map { display: none; }',
        '.stage[data-mode="map"] .thumb { display: none; }',
        ".map-now { position: absolute; left: 8px; right: 8px; bottom: 44px;",
        ".rec-map-waiting { display: flex;",
        ".tab-mark { height: 16px;",
    ):
        assert rule in CSS, rule
