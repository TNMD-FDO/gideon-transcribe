"""v1.212.0: the Incidents tab as a desk (Phase 12 chapter 10).

The strip's lanes in a box that scrolls with the ticked held at its top and
the names' row held above it; the wall of ticked cameras playing in step
with one transport, one sound, Grid and Focus and the said line; the map
beside with every camera drawn and a marker's press ticking; Your incident
as a panel sized for eight and Built on this day under it; the ticks, the
clock and the layout remembered on the browser; the playback copy's
address on the strip's rows; the local media route wired only by its
switch; the words in the glossary, the guide and the changelog.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from core import settings_store
from core.cases import Case
from core.models import User
from tests.helpers import signed_in, stamp
from tests.test_incidents_tidy import PASSWORD, video

APP = Path(__file__).resolve().parent.parent
ROOT = APP.parent


def static(name: str) -> str:
    return (APP / "static" / name).read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def incidents_on(db):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("incidents", True)


def test_the_tab_is_the_desk_and_the_reader_is_gone(client, db):
    person = User.objects.create_local_admin("desk", PASSWORD)
    case = Case.objects.create(owner=person, name="Harbour Street stop")
    browser = signed_in(client, person)
    page = browser.get(f"/case/{case.pk}?tab=incidents").content.decode()
    for wanted in (
        'id="incident-desk"',
        'class="builder-left"',
        'class="builder-right"',
        'id="desk-wall"',
        'id="desk-yours"',
        'id="desk-built"',
        'id="desk-make"',
        'id="desk-clear"',
        "incident-desk.",
    ):
        assert wanted in page, wanted
    assert 'id="strip-reader"' not in page and "building-words" not in page
    assert "map-pick-empty" not in page


def test_the_strip_scrolls_with_the_ticked_held_and_the_names_row_above():
    strip = static("chronology.js")
    for wanted in (
        "id='chron-tags'",
        "id='chron-scroll'",
        "var LANE_STEP = 19;",
        "on held",
        "function sizeDesk()",
        "function moveClock(at)",
        "class='clock-rule' data-rule",
        "function wireBuild(tags, box, d)",
        "function yoursHtml(d)",
        "function builtHtml(d)",
        "function spanHtml(d)",
        "function tellWallCams(d)",
        "data-act='every-day'",
        "data-act='add-ticked'",
        "data-act='tick-running'",
        "data-act='tick-near'",
    ):
        assert wanted in strip, wanted
    # The lanes' cap, the pictures and the Reader left with the desk.
    for gone in (
        "LANES_SHOWN",
        "class='film",
        "function readerDraw",
        "function stillUrl",
        "function readerBuilder",
        "data-act='toggle-all'>Show all",
    ):
        assert gone not in strip, gone
    # A camera's name is a press on the wall; an incident's name lights its lanes.
    assert 'tellWall("desk-focus", { id: sel.id })' in strip
    assert 'litIds[b.id] ? " lit"' in strip


def test_the_desk_is_remembered_on_the_browser_per_day():
    strip = static("chronology.js")
    assert 'return "desk:" + caseId + ":" + date;' in strip
    assert "function remember(d)" in strip and "function restore(date)" in strip
    assert "if (stripMode && !quiet && state.day) { restore(state.day.date); }" in strip
    wall = static("incident-desk.js")
    assert 'recall("desk-layout:" + CASE)' in wall
    assert 'remember("desk-layout:" + CASE, layout)' in wall


def test_the_wall_plays_the_ticked_in_step_with_one_transport_and_one_sound():
    wall = static("incident-desk.js")
    for wanted in (
        'window.addEventListener("desk-cams"',
        'tell("desk-clock", { at: m, playing: true })',
        'tell("desk-clock-set", { at: W.at, from: "wall" })',
        'tell("desk-untick", { id: cam.id })',
        'tell("desk-tick", { id: b.dataset.near })',
        "function follow(p, m)",
        "if (video.seeking) { return; }",
        "Math.abs(drift) > 0.5",
        "function setSound(id)",
        "function setFocus(id)",
        "function setLayout(layout)",
        "/segments?words=0",
        "function drawSaid(m)",
        "data-act='play'",
        "data-act='speed'",
        "type='range'",
        "Near at the clock line:",
        "Not on the clock: it joins the incident unplaced",
    ):
        assert wanted in wall, wanted
    # The strip hears the wall and moves its clock line in place.
    strip = static("chronology.js")
    for heard in ("desk-clock", "desk-clock-set", "desk-untick", "desk-tick"):
        assert 'window.addEventListener("' + heard + '"' in strip, heard


def test_the_map_draws_every_camera_in_pick_mode_and_a_press_ticks():
    script = static("map.js")
    assert "function pickedSet()" in script
    assert 'node.classList.toggle("faint", !picked[cam.id])' in script
    assert 'new CustomEvent("desk-tick", { detail: { id: cam.id } })' in script
    assert "if (PICK) { S.hidden = {}; }" in script
    css = static("app.css")
    assert ".map-pick .map-head.faint {" in css


def test_the_stylesheet_holds_the_desk_on_the_tokens():
    css = static("app.css")
    for wanted in (
        ".builder {",
        ".builder-left, .builder-right {",
        ".chron .tags-row {",
        ".chron .tags .clock-line {",
        ".chron .lanes-scroll {",
        ".chron .lane-row.held {",
        ".chron .cols .clock-rule {",
        ".desk-wall {",
        ".desk-wall .wtile {",
        ".desk-wall .wtransport {",
        '.desk-wall[data-layout="focus"] .wgrid {',
        ".desk-wall .wsaid {",
        ".desk-wall .wnear {",
        ".desk-panel {",
        ".desk-panel .two {",
        ".desk-built .built-row {",
    ):
        assert wanted in css, wanted
    assert ".chron .lane-row .film {" not in css and ".strip-wrap {" not in css


def test_the_strip_rows_carry_the_playback_copy_and_the_heads_own_run(db):
    from core import case_chronology

    person = User.objects.create_local_admin("rows", PASSWORD)
    case = Case.objects.create(owner=person, name="Harbour Street stop")
    one = video(person, case, "BWC2-1", stamp=stamp("20:25:10", "BWC2-1"))
    when = dt.date(2025, 6, 7)  # the helper's stamp date
    day = case_chronology.day_of(case, when, strip=True)
    bar = [b for b in day["bars"] if b["id"] == str(one.pk)][0]
    assert bar["media"] == f"/case-media/{case.pk}/{one.pk}/playback.mp4"
    assert bar["run"] == [bar["from"], bar["to"]]
    # The Notes tab's chronology carries no address: the wall is the desk's.
    plain = case_chronology.day_of(case, when)
    assert [b for b in plain["bars"] if b["id"] == str(one.pk)][0]["media"] == ""


def test_the_local_media_route_is_wired_only_by_its_switch(monkeypatch):
    source = (APP / "core" / "urls.py").read_text(encoding="utf-8")
    assert 'os.environ.get("APP_LOCAL_MEDIA") == "1"' in source
    assert "local_media.serve" in source
    from core import local_media

    assert local_media.RANGE.match("bytes=100-199").groups() == ("100", "199")


def test_the_words_are_in_the_glossary_the_guide_the_spec_and_the_changelog():
    glossary = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    assert "**Built on this day**" in glossary and "v1.212.0" in glossary
    guide = (ROOT / "docs" / "user-guide.md").read_text(encoding="utf-8")
    assert "**Built on this day**" in guide and "plays on the wall" in guide
    spec = (ROOT / "docs" / "spec" / "SPEC-PHASE-12.md").read_text(encoding="utf-8")
    assert "## 10. The Incidents tab as a desk" in spec
    assert "phase-12-incident-builder-desk.html" in spec
    log = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## v1.212.0" in log and "Built on this day" in log
    walk = (ROOT / "docs" / "local-walk.md").read_text(encoding="utf-8")
    assert "APP_LOCAL_MEDIA" in walk
