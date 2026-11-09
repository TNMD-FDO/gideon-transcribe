"""The Map tab's page, script and styles (Phase 12 chapter 1, v1.187.0).

The tab is in the bar after Incidents while maps are on and gone when off;
the case page draws the map's host and its scripts on that tab alone; the
script runs the incident page's clock pattern, follows the Preview and lets
go when it closes, paints the cameras in the page's own tokens, and steps a
second with the arrows and ten with shift; the Preview exposes its player;
the stylesheet carries the tab's rules on the tokens; the vendored files
match the hashes the README records and the licences list them; the words
are in the glossary; the street map's route, mount and command are in place.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest
from core import case_bar, settings_store
from core.cases import Case
from core.models import User
from core.recordings import Batch, MediaState, Recording
from django.urls import reverse
from tests.helpers import signed_in

PASSWORD = "a-long-enough-password"
HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent


@pytest.fixture(autouse=True)
def switched_on(db, settings, tmp_path):
    settings.DATA_DIR = tmp_path
    settings_store.set_to("folder_management", True)
    settings_store.set_to("incidents", True)
    settings_store.set_to("maps", True)


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("walker", PASSWORD)


@pytest.fixture
def a_case(person):
    return Case.objects.create(owner=person, name="Harbour Street stop")


def video(person, case, title):
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        case=case,
        title=title,
        original_filename=f"{title}.mp4",
        media_state=MediaState.READY,
        duration_seconds=600.0,
        playback_ready=True,
        probe={},
    )
    recording.folder.mkdir(parents=True, exist_ok=True)
    (recording.folder / "playback.mp4").write_bytes(b"not really media")
    return recording


def static(name: str) -> str:
    return (HERE / "static" / name).read_text(encoding="utf-8")


def test_the_map_tab_is_in_the_bar_after_incidents_while_maps_are_on(person, a_case):
    from core import camera_paths
    from tests.test_camera_paths import body_file

    # Only once the case holds a path file (chapter 12, v1.214.0).
    camera = video(person, a_case, "BWC2-1")
    assert "map" not in [t["key"] for t in case_bar.bar(a_case, on="map")["tabs"]]
    camera_paths.add(camera, data=body_file(), filename="BWC2-1.vtt", by=person)
    keys = [t["key"] for t in case_bar.bar(a_case, on="map")["tabs"]]
    assert keys.index("map") == keys.index("incidents") + 1
    by_key = {t["key"]: t for t in case_bar.bar(a_case, on="map")["tabs"]}
    assert by_key["map"]["name"] == "Map" and by_key["map"]["on"] is True
    settings_store.set_to("maps", False)
    assert "map" not in [t["key"] for t in case_bar.bar(a_case, on="map")["tabs"]]


def test_the_map_is_a_page_of_its_own_and_the_tab_sends_there(client, person, a_case):
    """Chapter 6.10 (v1.210.0): the case bar's Map tab opens the page; the
    old tab address goes there with its query, so every On the map address
    keeps landing at its moment. Since chapter 12 (v1.214.0) the page
    answers only once the case holds a path file; until then it sends to
    the case with a notice."""
    from core import camera_paths
    from tests.test_camera_paths import body_file

    camera = video(person, a_case, "BWC2-1")
    signed_in(client, person)
    page_url = reverse("case-map-page", args=[a_case.pk])
    sent = client.get(page_url, follow=True)
    assert 'id="case-map"' not in sent.content.decode()
    assert "No camera in this case has a path file yet" in sent.content.decode()
    camera_paths.add(camera, data=body_file(), filename="BWC2-1.vtt", by=person)
    asked = "?tab=map&recording=x&at=12.0"
    sent = client.get(reverse("case", args=[a_case.pk]) + asked)
    assert sent.status_code == 302
    assert sent["Location"] == page_url + asked
    page = client.get(page_url).content.decode()
    assert 'id="case-map"' in page and "vendor/maplibre-gl.js" in page
    assert "vendor/pmtiles.js" in page and "map.js" in page and "preview.js" in page
    assert "1 with a path file" in page
    assert "No street map is installed" in page
    assert 'id="case-add-paths"' in page and "path-files.js" in page
    assert f'data-json="{reverse("case-map", args=[a_case.pk])}"' in page
    # The case bar stands above with the Map tab lit, and the case page
    # itself draws no map any more.
    assert 'id="case-bar"' in page and 'href="' + page_url + '"' in page
    other = client.get(reverse("case", args=[a_case.pk])).content.decode()
    assert 'id="case-map"' not in other and "maplibre-gl.js" not in other
    assert 'href="' + page_url + '"' in other
    settings_store.set_to("maps", False)
    assert client.get(page_url).status_code == 404
    sent = client.get(reverse("case", args=[a_case.pk]) + "?tab=map", follow=True)
    assert 'id="case-map"' not in sent.content.decode()


def test_the_map_script_runs_the_incidents_clock_pattern():
    script = static("map.js")
    assert (
        "S.anchorMoment + ((performance.now() - S.anchorNow) / 1000) * S.speed"
        in script
    )
    assert "window.setInterval(tickIfMoved, STEP)" in script
    assert "document.hidden" in script
    assert "function positionAt(cam, local)" in script
    assert "function flagsAt(cam, local)" in script


def test_the_map_script_follows_the_preview_and_lets_go_when_it_closes():
    script = static("map.js")
    assert "window.Preview.media()" in script and "window.Preview.asked()" in script
    assert "window.Preview.seek(" in script
    assert "if (!window.Preview.isOpen()) { S.following = null;" in script
    assert "exact: true" in script


def test_the_map_paints_the_cameras_in_the_pages_tokens():
    script = static("map.js")
    assert 'return n ? "var(--sp" + n + ")" : "var(--muted)"' in script
    assert 'token("--warn")' in script and 'token("--danger")' in script
    assert "#1f6fb2" in script  # the chronology's palette, mapped to tokens
    css = static("app.css")
    assert ".map-tab {" in css and ".map-strip" in css and ".map-head" in css
    # The tab's own Larger map went with the frame (v1.208.0); the incident
    # page's stays as .inc-map-large.
    assert ".map-evcard" in css and ".inc-map-large" in css and ".map-tab.full" in css
    rules = css[css.index("/* The Map tab (Phase 12") :]
    assert "font-size: 1" not in rules.replace("font-size: var(", "")


def test_the_preview_exposes_its_player_for_the_map():
    preview = static("preview.js")
    assert "media: floating.media," in preview
    assert "asked: floating.asked," in preview and "seek: floating.seek," in preview
    assert "asked.exact ? 0 : 10" in preview


def test_the_map_keys_step_a_second_and_ten_with_shift():
    script = static("map.js")
    assert 'e.key === "ArrowLeft"' in script and "(e.shiftKey ? 10 : 1)" in script
    assert 'e.key === " "' in script and 'e.key === "Escape"' in script


def test_the_events_show_control_and_larger_map_are_remembered_per_person():
    script = static("map.js")
    assert 'remember("map-show", S.show)' in script
    assert 'remember("map-ev-" + t.dataset.ev' in script
    # Larger map left the tab (v1.208.0): the frame has the window; what is
    # remembered now is the list panel's fold and the Show box.
    assert 'remember("map-large"' not in script
    assert 'remember("map-band-h"' in script
    assert "maplibregl.FullscreenControl" in script
    assert 'data-act="note"' in script.replace("'", '"')


def test_the_map_takes_the_window_and_the_lanes_carry_the_names():
    """Chapter 6.10 (v1.210.0; the drawing phase-12-map-page.html, K and B
    together): the band on the map's top edge holds the play controls and
    Show for good, the lanes band under the map carries every camera as a
    lane whose head is its row, the split between them is the person's,
    and the map's height is the window's."""
    script = static("map.js")
    for wanted in (
        "function sizeFrame()",
        "var PANE_LEAST = 320, BAND_LEAST = 120, SPLIT = 8;",
        "Math.round(frame * 0.38)",
        "el.pane.style.height = (frame - band - SPLIT)",
        "el.lanes.style.height = band",
        'window.addEventListener("resize"',
        "class='map-frame' id='map-wrap'",
        "class='map-top' id='map-top'",
        "class='map-show' id='map-showrow'",
        "class='map-split' id='map-split'",
        "class='map-lanes' id='map-lanes'",
        "class='map-lanes-head' id='map-lanes-head'",
        "class='map-folds' id='map-list'",
        "class='menu map-more' id='map-more'",
        "class='menu map-days-menu'",
        "function helpHtml()",
        'getElementById("map-help-words")',
        "function laneCams()",
        "function laneHead(cam)",
        "function drawCamCard()",
        "r.bottom - e.clientY",
    ):
        assert wanted in script, wanted
    # Gone: the names panel, the Show box, the lane limit, the folded case head.
    for gone in (
        "map-showbox",
        "STRIP_SHOWN",
        "map-reader",
        "data-act='fold'",
        "data-act='strip-all'",
        "function foldHead()",
        "map-lanes-w",
    ):
        assert gone not in script, gone
    bar = script.split("function drawTransport()")[1].split("function helpHtml()")[0]
    assert "data-act='large'" not in bar.split("var scope = ")[1]
    assert "Note here" in bar and "Save a picture" in bar and "Tidy names" in bar
    css = static("app.css")
    for wanted in (
        ".map-frame { position: relative; display: flex; flex-direction: column;",
        ".map-frame .map-lanes {",
        ".map-frame .map-split {",
        "cursor: row-resize",
        ".map-lanes-head {",
        ".map-lanes .map-strip .map-lane .head .tk {",
        ".map-top {",
        ".map-camcard {",
        ".map-days-menu .menu-body",
        ".map-page-lead {",
        ".map-tab.full .map-frame {",
    ):
        assert wanted in css, wanted
    for gone in (
        ".map-showbox",
        ".map-reader",
        ".map-tab.folded",
        # The Map page's own 2200 rule went with v1.210.0; the recording
        # page's three columns (v1.224.0) have a 2200 query of their own.
        "2200px) { .map-tab",
        ".map-tab-page",
    ):
        assert gone not in css, gone
    page = (HERE / "templates" / "case-map.html").read_text(encoding="utf-8")
    assert 'id="map-help-words"' in page and "map-host.html" in page
    case_page = (HERE / "templates" / "case.html").read_text(encoding="utf-8")
    assert "map-tab-page" not in case_page and "head-fold" not in case_page
    glossary = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    assert "a page of its own" in glossary and "the lanes band" in glossary
    guide = (ROOT / "docs" / "user-guide.md").read_text(encoding="utf-8")
    assert "**The Map page**" in guide and "**More**" in guide
    spec = (ROOT / "docs" / "spec" / "SPEC-PHASE-12.md").read_text(encoding="utf-8")
    assert "### 6.10 The map as a page of its own" in spec


def test_the_vendored_map_files_match_the_hashes_the_readme_records():
    readme = (HERE / "static" / "vendor" / "README.md").read_text(encoding="utf-8")
    listed = dict(re.findall(r"- `([\w.-]+)`: `([0-9a-f]{64})`", readme))
    assert set(listed) == {"maplibre-gl.js", "maplibre-gl.css", "pmtiles.js"}
    for name, digest in listed.items():
        data = (HERE / "static" / "vendor" / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest, name
        assert b"sourceMappingURL" not in data
    for flavour in ("light", "dark"):
        style = (HERE / "static" / "maps" / f"style-{flavour}.json").read_text()
        assert '"glyphs": "/static/maps/fonts/{fontstack}/{range}.pbf"' in style
        assert f'"sprite": "/static/maps/sprites/{flavour}"' in style
        assert (HERE / "static" / "maps" / "sprites" / f"{flavour}.json").exists()
    for stack in ("Noto Sans Regular", "Noto Sans Medium", "Noto Sans Italic"):
        assert (HERE / "static" / "maps" / "fonts" / stack / "0-255.pbf").exists()


def test_the_licences_list_the_map_library_and_its_parts():
    licences = (ROOT / "THIRD_PARTY_LICENSES.md").read_text(encoding="utf-8")
    for name in (
        "MapLibre GL JS",
        "pmtiles (JavaScript)",
        "Protomaps basemaps",
        "Noto Sans",
        "OpenStreetMap data",
    ):
        assert name in licences, name


def test_the_map_words_are_in_the_glossary():
    glossary = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    for word in ("**Path**:", "**Fix**:", "**Path file**:", "**Map**:", "**Basemap**:"):
        assert word in glossary, word


def test_the_street_map_is_served_from_a_third_root_and_placed_by_the_command():
    caddy = (ROOT / "caddy" / "Caddyfile").read_text(encoding="utf-8")
    assert "handle /maps/*" in caddy and "uri /maps-auth" in caddy
    assert "root * /srv/maps" in caddy and "private, max-age=604800" in caddy
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert '"${APP_DATA_DIR}/maps:/srv/maps:ro"' in compose
    script = (ROOT / "transcribe").read_text(encoding="utf-8")
    assert "basemap) shift && cmd_basemap" in script
    assert 'head -c 7 "$file"' in script and "PMTiles" in script
    assert "./transcribe basemap FILE" in script
    assert 'if ! sudo test -d "$data/$folder"; then' in script
    check = (ROOT / "caddy" / "check-ranges.sh").read_text(encoding="utf-8")
    assert "/maps/basemap.pmtiles" in check
    assert chr(0x2014) not in caddy + compose + check


def test_the_status_page_says_whether_the_street_map_is_there(client, person):
    from core import panel_pages

    signed_in(client, person)
    told = client.get(reverse("panel-status-lines")).json()
    assert told["maps"] == {
        "on": True,
        "present": False,
        "words": "none; see the admin guide, Maps",
    }
    assert "_maps" in dir(panel_pages)
    status = (HERE / "static" / "panel-status.js").read_text(encoding="utf-8")
    assert '"Street map: " + state.maps.words' in status


# Chapter 5: the map pane on the incident page, and Save a picture ------------------


def an_incident_with_a_path(person, case):
    from core.incidents import Incident, IncidentCamera
    from tests.test_camera_paths import added, body_file

    camera = video(person, case, "BWC2-1")
    without = video(person, case, "Cell-5")
    incident = Incident.objects.create(case=case, name="Stop", created_by=person)
    IncidentCamera.objects.create(incident=incident, recording=camera)
    IncidentCamera.objects.create(incident=incident, recording=without)
    added(camera, body_file(), by=person)
    return incident, camera


def test_the_incident_page_carries_the_map_panel_when_a_camera_has_a_path_file(
    client, person, a_case
):
    from core.incidents import Incident, IncidentCamera

    signed_in(client, person)
    bare = Incident.objects.create(case=a_case, name="Bare", created_by=person)
    IncidentCamera.objects.create(incident=bare, recording=video(person, a_case, "A"))
    page = client.get(bare.url()).content.decode()
    assert 'data-panel="map"' not in page and "map.js" not in page
    incident, camera = an_incident_with_a_path(person, a_case)
    page = client.get(incident.url()).content.decode()
    assert 'data-panel="map"' in page and 'id="panel-map"' in page
    assert 'data-clock="incident"' in page
    assert f'data-incident="{incident.pk}"' in page
    assert f'data-picture="{reverse("case-map-picture", args=[a_case.pk])}"' in page
    assert "vendor/maplibre-gl.js" in page and "map.js" in page
    assert "The map has the wall" in page
    # The page's own address can open on the Map panel.
    assert 'openTab: "map"' in client.get(incident.url() + "?tab=map").content.decode()
    settings_store.set_to("maps", False)
    page = client.get(incident.url()).content.decode()
    assert 'data-panel="map"' not in page and "map.js" not in page


def test_the_incident_script_publishes_its_clock_and_the_map_follows_it():
    incident = static("incident.js")
    assert "window.IncidentClock = {" in incident
    assert "S.incident.clock_zero + now()" in incident
    assert "seek(timeOfDaySeconds - S.incident.clock_zero)" in incident
    assert '"map"].forEach' in incident
    script = static("map.js")
    assert 'var INC = host.dataset.clock === "incident";' in script
    assert "ic.seek(at); tick(); return;" in script
    assert "ic.focus(cam.id); ic.play();" in script
    assert "stage.insertBefore(host, wall)" in script
    assert 'remember("map-inc-large"' in script
    assert "new ResizeObserver" in script
    # CLOCKED since v1.223.0: the incident page's pane and the recording
    # page's tab both follow their page's clock.
    assert 'if (CLOCKED && e.key !== "Escape") { return; }' in script
    assert "function savePicture()" in script
    assert 'map.once("render"' in script and "out.toBlob(" in script
    assert "host.dataset.attribution" in script
    css = static("app.css")
    assert ".inc-desk.inc-map-large .inc-wall { display: none; }" in css
    assert ".map-tab.map-inc .map-pane" in css


def a_png(width=64, height=48) -> bytes:
    import io

    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (width, height), (40, 80, 120)).save(out, format="PNG")
    return out.getvalue()


def test_a_picture_of_the_map_is_kept_as_a_document_on_the_incident(
    client, person, a_case
):
    import io

    from core import comparison, documents
    from core.audit import Row

    settings_store.set_to("documents", True)
    signed_in(client, person)
    incident, camera = an_incident_with_a_path(person, a_case)
    url = reverse("case-map-picture", args=[a_case.pk])
    picture = io.BytesIO(a_png())
    picture.name = "map.png"
    told = client.post(
        url,
        {
            "file": picture,
            "title": "Map at 14:21:50, 2 Nov 2026, Stop",
            "incident": str(incident.pk),
        },
    )
    assert told.status_code == 200, told.content
    assert told.json()["words"].startswith("Saved to the case's Documents tab, about ")
    document = incident.documents.get()
    assert document.kind == documents.PICTURE and document.is_picture
    assert document.state == documents.READY and document.pages == 1
    assert document.pages_line() == "A picture of the map"
    assert document.original_path.name == "original.png"
    assert document.picture_path(1).exists()
    page = document.page_rows.get()
    assert page.text == "" and page.paragraphs == [] and not page.ocr
    row = Row.objects.get(event="Document added")
    assert row.details["kind"] == "picture" and row.details["about"] == "incident"
    # Served as the one page it is, downloaded as the PNG it is.
    assert client.get(told.json()["url"]).status_code == 200
    got = client.get(reverse("document-download", args=[a_case.pk, document.pk]))
    assert got["Content-Type"] == "image/png"
    assert (
        client.get(reverse("document-picture", args=[a_case.pk, document.pk, 1]))[
            "Content-Type"
        ]
        == "image/png"
    )
    # Listed in the shelf's gallery, never compared.
    tab = client.get(reverse("case", args=[a_case.pk]) + "?tab=documents")
    assert "Pictures of the map" in tab.content.decode()
    assert 'id="pictures"' in tab.content.decode()
    settings_store.set_to("documents_compare", True)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(comparison, "on", lambda: True)
    can, why = comparison.possible(document, incident)
    monkeypatch.undo()
    assert not can and why == "A picture of the map has no words to compare."
    assert documents.as_json(document)["kind"] == "picture"
    # A picture on a camera instead, and the refusals.
    picture = io.BytesIO(a_png())
    picture.name = "map.png"
    told = client.post(url, {"file": picture, "recording": str(camera.pk)})
    assert told.status_code == 200
    assert camera.documents.get().title == "Map"
    # A picture about nothing is the case's (v1.213.0).
    nothing = io.BytesIO(a_png())
    nothing.name = "map.png"
    told = client.post(url, {"file": nothing, "title": "Map at 14:21:50, 2 Nov 2026"})
    assert told.status_code == 200
    assert told.json()["words"] == "Saved to the case's Documents tab."
    loose = documents.Document.objects.get(title="Map at 14:21:50, 2 Nov 2026")
    assert loose.incident is None and loose.recording is None
    assert documents.picture_map_url(loose).endswith("?day=2026-11-02&from=51710")
    not_png = io.BytesIO(b"%PDF-1.4 not a picture")
    not_png.name = "map.png"
    told = client.post(url, {"file": not_png, "incident": str(incident.pk)})
    assert told.status_code == 400
    assert told.json()["error"] == "Only a picture of the map can be saved here."
    settings_store.set_to("documents", False)
    picture = io.BytesIO(a_png())
    picture.name = "map.png"
    told = client.post(url, {"file": picture, "incident": str(incident.pk)})
    assert told.status_code == 400 and "Documents are off" in told.json()["error"]
    # A picture is never put back in the reading line.
    settings_store.set_to("documents", True)
    document.read_version = 0
    document.save(update_fields=["read_version"])
    assert documents.read_again_the_old() == 0


# The Map tab refined (chapter 6, v1.192.0) ------------------------------------------
# Ticks, the names first, the row opened, trails off entirely, the leaders,
# the speed beside a vehicle, Within a circle.


def test_the_list_ticks_cameras_and_remembers_them_per_person_per_case():
    script = static("map.js")
    assert "data-tick='" in script and 'id="map-tick-all"' in script.replace("'", '"')
    assert 'remember("map-hidden-" + CASE' in script
    # INC alone since v1.225.0: the recording page ticks its own others.
    assert "function shown(cam) { return INC || !S.hidden[cam.id]; }" in script
    # The strip, the events and Fit shown follow the ticks; the clock's span does not.
    assert "var range = span(), cams = laneCams();" in script
    assert "shownCams().forEach(function (cam) {" in script
    assert "Fit shown" in script
    assert "data-act='tick-all'" in script and "data-act='tick-none'" in script
    # A press on the name shows that camera alone; Shift adds it.
    assert "only(c, e.shiftKey)" in script


def test_the_rows_say_the_name_first_and_open_to_the_rest():
    script = static("map.js")
    assert "return cam.wearer || cam.unit || cam.title; }" in script
    assert "function openOf(cam)" in script and "data-act='open'" in script
    assert "class='map-open'" in script
    # The lane heads say the same names as the rows.
    # The lane's head is the camera's row (v1.209.0): the name and the speed.
    assert "nameHtml(cam) + words + \"</span><span class='spd mono'>" in script
    # The ⋯ menu went with the row's facts into the opened part.
    assert "function more(" not in script and "data-replace-one='" in script
    assert "function whereWords(cam, local, p)" in script
    css = static("app.css")
    assert ".map-open {" in css and ".map-row .tk" in css


def test_trails_can_go_off_entirely():
    script = static("map.js")
    assert 'faint: recall("map-faint") !== "0"' in script
    assert 'id="map-faint"' in script.replace("'", '"')
    assert 'return S.show === "whole" ? 0.9 : (S.faint ? 0.35 : 0);' in script
    assert "function hiddenFilter()" in script


def test_the_leaders_and_the_speed_beside_a_vehicle():
    script = static("map.js")
    # Amended 2026-11-04: every marker carries a draggable name; nothing overlaps.
    assert "function layoutNames()" in script and "function freePlace(" in script
    assert "function rectsTouch(a, b)" in script and "TAG_GAP" in script
    assert 'node.className = "map-tag"' in script and "function wireDrag(" in script
    assert 'map.on("move", function () { drawLeaders(); });' in script
    assert "flags.speed > 3" in script
    assert "<span class='spd mono' hidden></span>" in script
    css = static("app.css")
    assert ".map-leaders" in css and ".map-tag" in css and ".map-tag .spd" in css
    # v1.196.0: dots for markers, the speed chip in the tag, the release chip,
    # the pip hit ring, and a vehicle's stream chooser.
    assert ".map-head b" not in css and "pinned · release" in script
    assert "map-events-hit" in script and "PIP_R" in script
    assert (
        "function showChooser(cam, under)" in script
        and "function switchStream(" in script
    )
    assert "function pinnedCount()" in script and ".map-chooser" in css
    # v1.196.1: pips for the day's ticked cameras alone, and no riding name
    # for a marker out of view.
    assert script.count("shownCams().forEach(function (cam) {") >= 2
    assert "if (away && !tag.pinned)" in script
    assert ".map-tag.pinned .pinmark" in css and ".map-tile .grip" in css


def test_within_a_circle_is_answered_in_the_browser_and_kept_nowhere():
    script = static("map.js")
    assert "data-act='circle'" in script and "Within a circle" in script
    assert "draggable: true" in script and "function radiusWords()" in script
    # The head reads "N cameras passed inside · N of 8 ticked" (v1.203.0).
    assert "data-act='tick-inside'" in script and "passed inside" in script
    assert "class='in'" in script  # the lanes' inside bands
    start = script.index("function placeCircle")
    circle = script[start : script.index("function clearCircle")]
    assert "remember(" not in circle and "fetch(" not in circle
    css = static("app.css")
    assert ".map-circle-centre" in css and "i.in" in css


def test_the_map_tab_words_of_chapter_six_are_in_the_glossary():
    words = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    assert "**Tile**" in words
    assert "Within a circle" in words


# Tiles and the notes (chapter 6, v1.193.0) --------------------------------------------


def two_cameras_with_paths(person, case):
    from tests.test_camera_paths import added, body_file

    first = video(person, case, "BWC1-1")
    second = video(person, case, "BWC2-1")
    added(first, body_file(), by=person)
    added(second, body_file(), by=person)
    return first, second


def test_note_on_all_shown_writes_one_note_per_camera_with_one_mark(
    client, person, a_case
):
    import json

    from core import notes
    from core.audit import Row
    from core.notes import MomentNote

    signed_in(client, person)
    first, second = two_cameras_with_paths(person, a_case)
    url = reverse("case-map-note-all", args=[a_case.pk])
    body = {
        "note": "All units at the corner",
        "at": {str(first.pk): 30, str(second.pk): 41.5},
    }
    told = client.post(url, json.dumps(body), content_type="application/json")
    assert told.status_code == 200, told.content
    assert told.json()["count"] == 2 and "2 cameras" in told.json()["words"]
    kept = list(MomentNote.objects.filter(recording__case=a_case).order_by("at"))
    assert [one.at for one in kept] == [30.0, 41.5]
    assert kept[0].note_from["group"] == kept[1].note_from["group"]
    assert kept[0].note_from["words"] == "from the map, on 2 cameras"
    # The Notes tab lists the copies once, naming every camera.
    rows = notes.of_case(a_case)["rows"]
    assert len(rows) == 1 and rows[0]["where"].startswith("on 2 cameras: ")
    assert "BWC1-1" in rows[0]["where"] and "BWC2-1" in rows[0]["where"]
    assert len(rows[0]["others"]) == 1
    # Two ordinary audit rows, never the words.
    added_rows = Row.objects.filter(event="Note added")
    assert added_rows.count() == 2
    assert not any("corner" in json.dumps(r.details) for r in added_rows)
    # Refusals: an empty note, a camera of another case, maps off.
    empty = client.post(
        url,
        json.dumps({"note": " ", "at": body["at"]}),
        content_type="application/json",
    )
    assert empty.status_code == 400
    other = Case.objects.create(owner=person, name="Elsewhere")
    stranger = video(person, other, "BWC9-1")
    wrong = client.post(
        url,
        json.dumps({"note": "x", "at": {str(stranger.pk): 1}}),
        content_type="application/json",
    )
    assert wrong.status_code == 400 and "not in this case" in wrong.json()["error"]
    settings_store.set_to("maps", False)
    assert (
        client.post(url, json.dumps(body), content_type="application/json").status_code
        == 404
    )


def test_a_note_from_the_map_says_so(client, person, a_case):
    import json

    from core.notes import MomentNote

    signed_in(client, person)
    first, _ = two_cameras_with_paths(person, a_case)
    url = reverse("recording-note-at", args=[first.pk])
    told = client.post(
        url,
        json.dumps({"at": 12, "note": "Here", "from": "map"}),
        content_type="application/json",
    )
    assert (
        told.status_code == 200 and told.json()["moment"]["note_from"] == "from the map"
    )
    assert MomentNote.objects.get(recording=first).note_from == {
        "kind": "map",
        "words": "from the map",
    }
    # Anything else the page claims as its origin is not kept.
    plain = client.post(
        url,
        json.dumps({"at": 50, "note": "There", "from": "somewhere"}),
        content_type="application/json",
    )
    assert plain.status_code == 200 and plain.json()["moment"]["note_from"] == ""


def test_the_tiles_ride_pin_and_play_in_step():
    script = static("map.js")
    assert "function openTile(cam, stream)" in script and "TILES_MOST = 6" in script
    assert "TILE_PLAYS_TO = 4" in script and "function syncTiles(m)" in script
    assert "teth" in script and "pointerdown" in script
    # The tile takes the name's place, and gives it back; the grip resizes.
    assert "var tag = S.tags[cam.id] || { x: 0, y: 0, pinned: false };" in script
    assert "tag.x = tile.x; tag.y = tile.y; tag.pinned = tile.pinned;" in script
    assert "function wireResize(tile)" in script and "TILE_W_LEAST = 120" in script
    assert 'remember("map-tile-w"' in script and "function tidyNames()" in script
    assert "data-act='tidy'" in script and "function pictureNames(" in script
    assert "v.muted = S.sound !== id" in script
    assert "data-act='tile-note'" in script and "data-act='note-all'" in script
    assert "data-act='close-tiles'" in script
    # A tag's press opens the tile; a note from the map says so.
    assert "showChooser(cam, node); } else { openTile(cam, 0); }" in script
    assert 'from: "map"' in script and "function noteAll()" in script
    assert "postJson(host.dataset.noteAll" in script
    host = (HERE / "templates" / "map-host.html").read_text(encoding="utf-8")
    assert "data-note-all=" in host
    css = static("app.css")
    assert ".map-tile {" in css and ".map-tile.pinned" in css and "line.teth" in css
    assert ".map-tile.away" in css


# Path files that wait, and the head's door (chapter 6, v1.194.0) ---------------------


def test_an_unmatched_path_file_waits_on_the_case_and_is_read_by_nothing(
    client, person, a_case
):
    import io

    from core import camera_paths
    from core.audit import Row
    from core.camera_paths import WaitingPathFile
    from tests.test_camera_paths import body_file

    signed_in(client, person)
    video(person, a_case, "BWC1-1")
    url = reverse("case-paths-add", args=[a_case.pk])
    matched = io.BytesIO(body_file(600))  # as long as the video, so not flagged
    matched.name = "BWC1-1.vtt"
    stranger = io.BytesIO(body_file())
    stranger.name = "BWC7-2_202511062031_0001.vtt"
    told = client.post(url, {"files": [matched, stranger], "chosen": ["", ""]})
    assert told.status_code == 200, told.content
    assert len(told.json()["landed"]) == 1, told.json()
    assert told.json()["leftovers"] == []
    assert [w["file"] for w in told.json()["waiting"]] == [stranger.name]
    kept = WaitingPathFile.objects.get(case=a_case)
    assert kept.stem == camera_paths.stem_of(stranger.name)
    assert kept.file_path.exists() and kept.source == "body" and kept.cues > 0
    assert kept.file_path.parent == a_case.folder / "waiting"
    # Read by nothing: one Path, one camera on the map, one in the readings.
    assert camera_paths.count(a_case) == 1
    told = camera_paths.map_of(a_case, viewer=person)
    assert len(told["cameras"]) == 1 and len(told["waiting"]) == 1
    assert told["waiting"][0]["remove_url"].endswith("/remove")
    assert "waiting_remove_all_url" in told
    assert len(camera_paths.ids_with_path(a_case)) == 1
    # The row says the case and the kind, never the names inside the file.
    row = Row.objects.get(event="Path file kept waiting")
    assert row.details["source"] == "body" and "officer" not in str(row.details).lower()
    assert "Pat" not in str(row.details)
    # The same name is not kept twice.
    again = io.BytesIO(body_file())
    again.name = stranger.name
    told = client.post(url, {"files": [again], "chosen": [""]})
    assert told.json()["waiting"][0].get("again") is True
    assert WaitingPathFile.objects.filter(case=a_case).count() == 1


def test_a_waiting_file_is_paired_when_its_video_lands(client, person, a_case):
    from core import camera_paths, cases
    from core.audit import Row
    from core.camera_paths import WaitingPathFile
    from tests.test_camera_paths import body_file, car_file

    settings_store.set_to("maps", True)
    camera_paths.keep_waiting(
        a_case, data=body_file(600), filename="BWC7-2.vtt", by=person
    )
    camera_paths.keep_waiting(a_case, data=car_file(), filename="Dash-9.vtt", by=person)
    elsewhere = Case.objects.create(owner=person, name="Elsewhere")
    arriving = video(person, elsewhere, "BWC7-2")
    cases.move_recording(arriving, a_case, person)
    path = camera_paths.of(arriving)
    assert path is not None and path.fix_count > 0
    assert not WaitingPathFile.objects.filter(case=a_case, stem="bwc7-2").exists()
    row = Row.objects.filter(event="Path file added").latest("at")
    assert row.details.get("paired_from_waiting") is True
    # A file that disagrees with its video stays waiting and says why.
    dash = video(person, elsewhere, "Dash-9")
    dash.stamp = {"camera": "UNIT-77"}
    dash.save(update_fields=["stamp"])
    cases.move_recording(dash, a_case, person)
    assert camera_paths.of(dash) is None
    waiting = WaitingPathFile.objects.get(case=a_case, stem="dash-9")
    assert waiting.flagged and waiting.flagged_recording_id == dash.pk
    rows = camera_paths.map_of(a_case, viewer=person)["waiting"]
    assert rows[0]["flagged_title"] == "Dash-9" and rows[0]["add_anyway_url"]
    # Add anyway pairs it after all.
    signed_in(client, person)
    told = client.post(rows[0]["add_anyway_url"])
    assert told.status_code == 200, told.content
    assert camera_paths.of(dash) is not None
    assert not WaitingPathFile.objects.filter(case=a_case).exists()
    # The pipeline pairs too, once the upload is Ready; a move pairs at once.
    pipeline = (HERE / "core" / "pipeline.py").read_text(encoding="utf-8")
    assert "camera_paths.pair_waiting(recording)" in pipeline
    # A recording that already has a path keeps it.
    camera_paths.keep_waiting(
        a_case, data=body_file(), filename="BWC7-2.vtt", by=person
    )
    assert camera_paths.pair_waiting(arriving) is None
    assert WaitingPathFile.objects.filter(case=a_case).count() == 1


def test_waiting_files_can_be_removed_one_or_all(client, person, a_case):
    from core import camera_paths
    from core.audit import Row
    from core.camera_paths import WaitingPathFile
    from tests.test_camera_paths import body_file

    signed_in(client, person)
    first = camera_paths.keep_waiting(
        a_case, data=body_file(), filename="A.vtt", by=person
    )
    camera_paths.keep_waiting(a_case, data=body_file(), filename="B.vtt", by=person)
    camera_paths.keep_waiting(a_case, data=body_file(), filename="C.vtt", by=person)
    gone = client.post(reverse("case-paths-waiting-remove", args=[a_case.pk, first.pk]))
    assert gone.status_code == 200 and not first.file_path.exists()
    assert WaitingPathFile.objects.filter(case=a_case).count() == 2
    assert (
        client.post(
            reverse("case-paths-waiting-remove", args=[a_case.pk, first.pk])
        ).status_code
        == 404
    )
    told = client.post(reverse("case-paths-waiting-remove-all", args=[a_case.pk]))
    assert (
        told.json()["count"] == 2
        and not WaitingPathFile.objects.filter(case=a_case).exists()
    )
    assert (
        Row.objects.filter(event="Waiting path files removed").get().details["count"]
        == 2
    )
    settings_store.set_to("maps", False)
    assert (
        client.post(
            reverse("case-paths-waiting-remove-all", args=[a_case.pk])
        ).status_code
        == 404
    )


def test_add_path_files_stands_in_the_case_head_on_every_tab(client, person, a_case):
    from core import camera_paths
    from tests.test_camera_paths import body_file

    signed_in(client, person)
    camera = video(person, a_case, "BWC1-1")
    # The Map page needs a path file read (chapter 12); the waiting one is
    # not that.
    camera_paths.add(camera, data=body_file(), filename="BWC1-1.vtt", by=person)
    camera_paths.keep_waiting(a_case, data=body_file(), filename="Z.vtt", by=person)
    for tab in ("", "?tab=notes", "?tab=map", "?tab=details"):
        got = client.get(reverse("case", args=[a_case.pk]) + tab, follow=True)
        page = got.content.decode()
        assert 'id="case-add-paths"' in page and "path-files.js" in page, tab
        assert 'id="map-add-files"' not in page
        if tab == "?tab=map":
            # The Map page (v1.210.0) has it in its own slim row.
            assert "Add path files" in page[: page.index('id="case-map"')]
            continue
        head = page[: page.index("Add recordings")]
        assert "Add path files" in head  # to the left of Add recordings
    details = client.get(
        reverse("case", args=[a_case.pk]) + "?tab=details"
    ).content.decode()
    assert "1 path file waiting for its video" in details
    settings_store.set_to("maps", False)
    page = client.get(reverse("case", args=[a_case.pk])).content.decode()
    assert 'id="case-add-paths"' not in page


def test_the_heads_script_posts_in_batches_and_the_map_lists_the_waiting():
    door = static("path-files.js")
    assert "BATCH = 20" in door and "window.PathFiles" in door
    assert "Waiting for their video" in door and "layer-go" in door
    # v1.195.1: the layer opens at once with the count, and leaving is guarded.
    assert "Keep this page open until it finishes" in door
    assert '"beforeunload"' in door and "data-act='stop'" in door
    assert "of the files were not sent" in door
    script = static("map.js")
    assert "window.MapTab = { reload:" in script
    assert (
        "function waitingFold()" in script and "data-act='waiting-remove-all'" in script
    )
    assert "data-act='waiting-add-anyway'" in script and "map-waiting-find" in script
    assert "function addMany" not in script and "function settle" not in script


# The circle's incident and the suggestions (chapter 6, v1.197.0) -------------------


def test_the_circle_moves_and_makes_an_incident_and_the_strip_suggests():
    script = static("map.js")
    assert (
        'map.on("mousedown", "map-circle-fill"' in script
        and "dragPan.disable()" in script
    )
    assert "data-act='circle-incident'" in script and "function incidentBox(" in script
    assert "function circleSpan(cams)" in script and "function streetWords()" in script
    # The map draws no circle of its own (v1.198.0): no suggestion circles or
    # chips; On the map from a card shows the cameras where they were.
    assert "function askedCameras()" in script and "drawSuggestions" not in script
    assert "suggest-make" not in script and "map-suggest" not in script
    assert "S.told.new_incident_url" in script
    strip = static("chronology.js")
    # The day as the page (Phase 12 chapter 7): lanes, columns and a reader
    # in place of the Suggested row and the cards.
    # The Reader left in v1.212.0 (chapter 10): Your incident is a panel.
    assert "function columns(d)" in strip and "function yoursHtml(d)" in strip
    assert "function yoursDraw(d)" in strip and "formingLane(" not in strip
    assert "suggestedLane" not in strip and "cardHtml" not in strip
    assert "On the map" in strip and '"from their notes"' not in strip
    assert "&show=" in strip and "&circle=" not in strip and "data-tick='" in strip
    page = (HERE / "templates" / "case.html").read_text(encoding="utf-8")
    assert "data-map=\"{% url 'case' case.pk %}?tab=map\"" in page
    css = static("app.css")
    assert ".chron .lanes {" in css and ".map-circle-make" in css
    assert ".map-suggest" not in css and ".chron .col .n {" in css
    assert ".chron .legend { margin-top" in css
    # The strip is the day chips, the ruler, the named lanes and a foot; the
    # same day is read in the day's reading, never a column.
    assert "dayChips() + ruler(d) + " in strip and "+ lanes(d) + " in strip
    # The builder (chapter 8): ticks, Your incident, no suggestions.
    assert "function tickSpan(d)" in strip and "suggestions(" not in strip
    assert "incident-ticks" in strip and "var PICK = host.dataset.pick" in script
    # The span and the clock line (chapter 9, v1.201.0): the handles and the
    # line beside the column, the lanes by overlap, a picture per lane, the
    # map following the line, the span posted with Make the incident.
    assert "function spanOf(d)" in strip and "function clockLine(d)" in strip
    assert "data-hdl='0'" in strip and "data-clock" in strip
    assert "incident-clock" in strip and "function settleTags(box)" in strip
    assert "function wireBuild(tags, box, d)" in strip
    assert "overlap(b, span) - overlap(a, span)" in strip and "class='film" not in strip
    assert '["date", state.day.date]' in strip
    assert 'addEventListener("incident-clock"' in script and "S.pickAt" in script
    assert ".chron .tags .clock-line {" in css and ".chron .tags .hdl {" in css
    assert ".chron .lanes-scroll {" in css and ".chron .lane-row.held {" in css
    assert ".chron .tags .tag.foot {" in css
    # The near marks (v1.202.0): the map answers from the paths it holds, the
    # strip rings the boxes in place.
    assert "function tellNear()" in script and "incident-near" in script
    assert "function nearMarks()" in strip and "data-near-words" in strip
    assert ".chron .lane-row.near .lane-name input.tk {" in css
    # The circle under the cap (v1.203.0): the longest inside ticked up to
    # the cap, hollow markers, a marker's press toggling, the box's budget,
    # and the ticks carried to the strip.
    assert "function circleOrder()" in script and "data-ctick='" in script
    assert "function toggleCircleTick(cam)" in script and '"hollow"' in script
    assert "?tab=incidents&day=" in script and "&tick=" in script
    assert "function budget()" in script and "#map-inc-count" in script
    assert "state.askedTicks" in strip and 'getElementById("strip-map-open")' in strip
    assert 'id="strip-map-open"' in page and ".map-head.hollow {" in css
    # The wall at eight (v1.204.0): the setting's default is the cap, the
    # work panel folds to its rail at seven or more, the tiles drop their
    # lines, the said band follows the focus in every layout, the film strip
    # fits the stage.
    from core import settings_store

    assert settings_store.definition("incidents_wall").default == 8
    incident_js = static("incident.js")
    assert "var MANY = 7;" in incident_js and "function foldWanted()" in incident_js
    assert "incident-work-folded" in incident_js
    assert 'classList.toggle("many"' in incident_js
    incident_page = (HERE / "templates" / "incident.html").read_text(encoding="utf-8")
    assert 'id="work-toggle"' in incident_page and 'id="layout-hint"' in incident_page
    assert ".inc-desk.folded {" in css and ".inc-desk.folded .inc-work.over {" in css
    assert ".inc-film .inc-tile { flex: 1 1 0;" in css
    assert '.inc-desk.many:not([data-layout="focus"]) .inc-tile .inc-lines' in css
    # Stacked pips (v1.206.0): a press on a stack opens the list, and the
    # card steps through the stack.
    assert "function openStack(keys, point)" in script and "at this spot" in script
    assert "data-act='stack-pick'" in script and ".map-stack {" in css
    # The two tools and the streams as one (v1.205.0).
    assert "data-act='tick-running'" in strip and "data-act='tick-near'" in strip
    assert "function tickMany(ids)" in strip and "function streamsOf(bars)" in strip
    assert "c.streams.forEach(function (s) { ids.push(s.id); })" in script
    assert "S.incident.pictures" in incident_js
    # The hidden New incident dialog left the page (v1.201.0).
    assert 'id="incident-box"' not in page and "choose-myself" not in static("cases.js")
