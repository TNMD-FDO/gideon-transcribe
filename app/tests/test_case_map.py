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
    keys = [t["key"] for t in case_bar.bar(a_case, on="map")["tabs"]]
    assert keys.index("map") == keys.index("incidents") + 1
    by_key = {t["key"]: t for t in case_bar.bar(a_case, on="map")["tabs"]}
    assert by_key["map"]["name"] == "Map" and by_key["map"]["on"] is True
    settings_store.set_to("maps", False)
    assert "map" not in [t["key"] for t in case_bar.bar(a_case, on="map")["tabs"]]


def test_the_case_page_draws_the_host_and_the_scripts_on_the_map_tab_alone(
    client, person, a_case
):
    video(person, a_case, "BWC2-1")
    signed_in(client, person)
    page = client.get(reverse("case", args=[a_case.pk]) + "?tab=map").content.decode()
    assert 'id="case-map"' in page and "vendor/maplibre-gl.js" in page
    assert "vendor/pmtiles.js" in page and "map.js" in page
    assert "No camera has a path file yet." in page
    assert "No street map is installed" in page
    assert "Add path files" in page
    assert f'data-json="{reverse("case-map", args=[a_case.pk])}"' in page
    other = client.get(reverse("case", args=[a_case.pk])).content.decode()
    assert 'id="case-map"' not in other and "maplibre-gl.js" not in other
    settings_store.set_to("maps", False)
    page = client.get(reverse("case", args=[a_case.pk]) + "?tab=map").content.decode()
    assert 'id="case-map"' not in page


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
    assert ".map-evcard" in css and ".map-tab.large" in css and ".map-tab.full" in css
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
    assert 'remember("map-large"' in script
    assert "maplibregl.FullscreenControl" in script
    assert 'data-act="note"' in script.replace("'", '"')


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
