"""The `transcribe` script itself (v1.83.0): it parses, every command in its
usage block is dispatched and every dispatched command is in the usage block,
the pieces it adds are the app's pieces, and the pure profile helpers keep
their rule: adding one profile never removes another. Bash is on the CI
runner and on the office's server; where it is not, these are skipped."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
from core import pieces

HERE = Path(__file__).resolve().parent.parent.parent
SCRIPT = HERE / "transcribe"
BASH = shutil.which("bash")

needs_bash = pytest.mark.skipif(BASH is None, reason="no bash on this machine")


def text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


@needs_bash
def test_the_script_parses():
    done = subprocess.run([BASH, "-n", str(SCRIPT)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


def test_every_usage_line_is_dispatched_and_the_other_way_round():
    usage = set(re.findall(r"^#   \./transcribe ([a-z-]+)", text(), re.M))
    dispatch = set(re.findall(r"^([a-z-]+)\) (?:shift && )?cmd_", text(), re.M))
    # `help` is the usage itself; `status` and the rest are commands.
    assert usage - dispatch == set(), (
        f"in the usage block, not dispatched: {usage - dispatch}"
    )
    # Commands an operator is not told about are allowed only when they are
    # what the timers call or a step of another command.
    quiet = {"backup-weekly", "install-timers", "restore-dump", "upgrade-finish"}
    assert dispatch - usage - quiet == set(), (
        f"dispatched, not in the usage block: {dispatch - usage - quiet}"
    )


def test_the_pieces_the_script_adds_are_the_apps():
    body = text().split("cmd_add() {", 1)[1].split("\n}\n", 1)[0]
    added = re.findall(r"^    ([a-z-]+)\)", body, re.M)
    assert tuple(added) == pieces.PIECES


def test_the_service_and_the_diarizer_are_behind_the_transcription_profile():
    compose = (HERE / "whisperx-service" / "compose.yaml").read_text(encoding="utf-8")
    # The services section alone: the networks section names a `whisperx` too.
    section = compose.split("\nservices:\n", 1)[1].split("\nsecrets:\n", 1)[0]
    services = re.split(r"^  ([a-z-]+):\n", section, flags=re.M)
    # re.split gives [head, name, body, name, body, ...]
    by_name = dict(zip(services[1::2], services[2::2], strict=True))
    for name in ("whisperx", "diarizer"):
        assert 'profiles: ["transcription"]' in by_name[name], name
    assert 'profiles: ["fast"]' in by_name["whisperx-fast"]
    # The card is a default, never a demand, so the stack starts without it.
    assert "WHISPERX_GPU_UUID:?" not in compose
    assert "WHISPERX_GPU_UUID:-unset" in compose
    example = (HERE / ".env.example").read_text(encoding="utf-8")
    assert re.search(r"^COMPOSE_PROFILES=transcription$", example, re.M)


def test_the_upgrade_hands_over_to_the_new_release():
    """v1.85.1: after the checkout the upgrade execs the checked-out script's
    own second half, so a step a release adds to the upgrade runs at the
    upgrade that brings it in; a tag without the subcommand runs the steps
    from the old script as before."""
    body = text()
    upgrade = body.split("cmd_upgrade() {", 1)[1].split("\n}\n", 1)[0]
    assert 'git -C "$HERE" checkout --quiet "$tag"' in upgrade
    assert "grep -q '^upgrade-finish)' \"$HERE/transcribe\"" in upgrade
    assert 'exec "$HERE/transcribe" upgrade-finish "$tag" "$before" "$build"' in upgrade
    assert 'finish_the_upgrade "$tag" "$before" "$build"' in upgrade
    finish = body.split("finish_the_upgrade() {", 1)[1].split("\n}\n", 1)[0]
    steps = ("set_env RELEASE_TAG", "migrate_the_profiles", "compose up -d")
    for step in steps:
        assert step in finish, step
    assert "cmd_check" in finish


@needs_bash
def test_the_card_fitting_rule(tmp_path):
    """v1.84.0: the batch size by the card's memory, and the Local engine's
    share that gives it 20 GB; the office's 96 GB card still yields 16 and
    0.21, so its .env is untouched."""
    source = text()
    wanted = []
    for name in ("fit_the_card", "engine_share_for"):
        match = re.search(rf"^{name}\(\) \{{\n.*?^\}}\n", source, re.M | re.S)
        assert match, name
        wanted.append(match.group(0))
    probe = (
        "set -euo pipefail\n"
        + "\n".join(wanted)
        + "\nfor gb in 8 16 23 24 31 32 48 96; do"
        ' printf "%s:%s:%s\\n" "$gb"'
        ' "$(fit_the_card $gb)" "$(engine_share_for $gb)"; done\n'
    )
    done = subprocess.run([BASH, "-c", probe], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert done.stdout.split() == [
        "8::0.90",
        "16:4:0.90",
        "23:4:0.87",
        "24:8:0.83",
        "31:8:0.65",
        "32:16:0.62",
        "48:16:0.42",
        "96:16:0.21",
    ]


@needs_bash
def test_adding_one_profile_never_removes_another(tmp_path):
    env = tmp_path / ".env"
    env.write_text("COMPOSE_PROFILES=\n", encoding="utf-8")
    # The helpers, sourced out of the script with the pieces they need:
    # env_value and set_env read and write $ENV_FILE.
    source = text()
    wanted = []
    for name in ("env_value", "set_env", "profile_on", "profile_add", "profile_remove"):
        match = re.search(rf"^{name}\(\) \{{\n.*?^\}}\n", source, re.M | re.S)
        assert match, name
        wanted.append(match.group(0))
    probe = (
        "set -euo pipefail\n"
        f'ENV_FILE="{env.as_posix()}"\n'
        + "\n".join(wanted)
        + "\nprofile_add transcription\nprofile_add llm\nprofile_add transcription\n"
        "profile_remove llm\nprofile_add fast\nprofile_remove transcription\n"
        "env_value COMPOSE_PROFILES\n"
    )
    done = subprocess.run([BASH, "-c", probe], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "fast"
