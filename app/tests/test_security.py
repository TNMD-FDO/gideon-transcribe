"""The security pass of 14 October 2026 (v1.130.0): the rules it fixed, kept.

Each test here is a finding of that pass turned into a rule the suite keeps:
an upload id is never a path, a clip name never climbs, every page script
escapes both quotes, the loggers that print what they are handed are held at
WARNING, the front door refuses the sidecar's hook and keeps no query string,
a blank allow-list stops the stack, the directory connection demands a
certificate, the engine address stays in the building, a spreadsheet cell is
never a formula, and the script's dumps are born private.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from core import chronology, directory, settings_store, uploads
from django.conf import settings as django_settings

HERE = Path(__file__).resolve().parent.parent.parent
STATIC = HERE / "app" / "static"


# Upload ids ------------------------------------------------------------------


def test_an_upload_id_is_the_sidecars_shape_and_nothing_else(tmp_path, settings):
    settings.UPLOADS_DIR = tmp_path / "uploads"
    (tmp_path / "uploads").mkdir()
    (tmp_path / "uploads" / "abc123").write_bytes(b"x")
    (tmp_path / "other").mkdir()
    (tmp_path / "other" / "theirs.mp4").write_bytes(b"y")
    (tmp_path / "uploads" / "folder").mkdir()
    assert uploads.arrived_file("abc123") == tmp_path / "uploads" / "abc123"
    assert uploads.arrived_file("../other/theirs.mp4") is None
    assert uploads.arrived_file(str(tmp_path / "other" / "theirs.mp4")) is None
    assert uploads.arrived_file("folder") is None
    assert uploads.arrived_file("") is None
    assert uploads.arrived_file("missing") is None
    assert uploads.arrived_file("a/b") is None
    assert (tmp_path / "other" / "theirs.mp4").exists()


# Page scripts ----------------------------------------------------------------

TRICK = re.compile(r"\.textContent = text[^;]*;\s*return \w+\.innerHTML")
FULL = 'replace(/"/g, "&quot;").replace(/\'/g, "&#39;")'


def test_every_page_script_escapes_both_quotes():
    """The span trick escaped angle brackets and ampersands and left both
    quotes alone, while titles and document text went inside single-quoted
    attributes."""
    for script in sorted(STATIC.glob("*.js")):
        text = script.read_text(encoding="utf-8")
        assert not TRICK.search(text), script.name
        if "function escape" in text or "function escaped" in text:
            assert "&#39;" in text and "&quot;" in text, script.name


# The journal -----------------------------------------------------------------


def test_the_libraries_that_print_what_they_are_handed_are_held_at_warning():
    loggers = django_settings.LOGGING["loggers"]
    for name in ("procrastinate", "openai", "httpx", "httpcore"):
        assert loggers[name]["level"] == "WARNING", name
        assert loggers[name]["propagate"] is False, name


def test_the_workers_forget_a_finished_jobs_arguments():
    entrypoint = (HERE / "app" / "entrypoint.sh").read_text(encoding="utf-8")
    assert entrypoint.count("--delete-jobs=successful") == 3


# The front door --------------------------------------------------------------


def test_the_front_door_refuses_the_hook_and_keeps_no_query_string():
    caddyfile = (HERE / "caddy" / "Caddyfile").read_text(encoding="utf-8")
    hook = caddyfile.index("handle /upload-hook*")
    catch_all = caddyfile.index("handle {\n\t\trequest_body")
    assert hook < catch_all
    assert "respond 404" in caddyfile[hook:catch_all]
    assert 'request>uri regexp "[?].*" "?"' in caddyfile


def test_a_blank_allow_list_stops_the_stack():
    compose = (HERE / "compose.yaml").read_text(encoding="utf-8")
    assert "${ALLOWED_CLIENT_CIDRS:?set ALLOWED_CLIENT_CIDRS in .env}" in compose
    assert "0.0.0.0/0" not in compose


# The directory ---------------------------------------------------------------


def test_the_directory_connection_demands_a_certificate(monkeypatch, tmp_path):
    import ldap

    asked = []
    monkeypatch.setattr(
        ldap, "set_option", lambda key, value: asked.append((key, value))
    )
    monkeypatch.setattr(
        directory,
        "facts",
        lambda: {
            "server_uri": "ldaps://directory.example.internal",
            "bind_user": "cn=reader",
            "ca_file": str(tmp_path / "empty.pem"),
        },
    )
    (tmp_path / "empty.pem").write_bytes(b"")
    monkeypatch.setattr(directory, "bind_password", lambda: "x")
    try:  # noqa: SIM105
        directory.connect()
    except directory.Unreachable:
        pass
    assert (ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_DEMAND) in asked
    assert (ldap.OPT_X_TLS_NEWCTX, 0) in asked
    # With an empty CA file the system store is used and the demand stands.
    assert not any(key == ldap.OPT_X_TLS_CACERTFILE for key, _ in asked)


# The engine ------------------------------------------------------------------


@pytest.mark.parametrize(
    "address",
    [
        "http://vllm:8000/v1",
        "http://gideon-generator:8000/v1",
        "http://10.20.30.40:8000/v1",
        "http://192.168.1.9:8000/v1",
        "https://engine.office.internal/v1",
        "https://engine.office.lan/v1",
        "http://localhost:8000/v1",
        "http://127.0.0.1:8000/v1",
    ],
)
def test_an_engine_in_the_building_is_accepted(address):
    assert settings_store.outside_the_building(address) == ""


@pytest.mark.parametrize(
    "address",
    [
        "https://api.openai.com/v1",
        "https://example.com/v1",
        "http://8.8.8.8/v1",
        "http://93.184.216.34:8000/v1",
        "ftp://vllm:8000/v1",
        "vllm:8000",
    ],
)
def test_an_engine_outside_is_refused(address):
    assert settings_store.outside_the_building(address)


@pytest.mark.django_db
def test_the_engine_address_setting_holds_the_rule():
    with pytest.raises(ValueError, match="public"):
        settings_store.check("engine_address", "https://api.openai.com/v1")
    assert settings_store.check("engine_address", " http://vllm:8000/v1 ") == (
        "http://vllm:8000/v1"
    )


# Spreadsheets ----------------------------------------------------------------


def test_a_spreadsheet_cell_is_text_and_never_a_formula():
    assert chronology.cell("=1+1") == "'=1+1"
    assert chronology.cell("+HYPERLINK") == "'+HYPERLINK"
    assert chronology.cell("-2") == "'-2"
    assert chronology.cell("@SUM") == "'@SUM"
    assert chronology.cell("\tcmd") == "'\tcmd"
    assert chronology.cell("Gun found") == "Gun found"
    assert chronology.cell(12) == "12"
    assert chronology.cell(None) == ""


# The script ------------------------------------------------------------------


def test_the_scripts_files_are_born_private():
    script = (HERE / "transcribe").read_text(encoding="utf-8")
    assert "\numask 077\n" in script
    assert '>"/tmp/' not in script
    assert 'tar -cf "/tmp/' not in script
    assert script.count('work="$(private_folder)"') == 3
    assert "trap forget_private_folders EXIT" in script
