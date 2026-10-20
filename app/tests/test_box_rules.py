"""Transcribe's half of the shared box's rules (v1.137.0): the directions in
the box ledger's v0.3.135 and v0.3.141 entries, each pinned where the code
or the guide carries it."""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import pytest
from core.models import User
from django.core.management import call_command

HERE = Path(__file__).resolve().parent.parent.parent
SCRIPT = (HERE / "transcribe").read_text(encoding="utf-8")
COMPOSE = (HERE / "compose.yaml").read_text(encoding="utf-8")
EXAMPLE = (HERE / ".env.example").read_text(encoding="utf-8")
GUIDE = (HERE / "docs" / "install.md").read_text(encoding="utf-8")


def between(source: str, start: str, end: str = "\n}\n") -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


def test_step_zero_follows_the_shared_recipe():
    # v0.3.135 line 1: no runtime configure, no Docker restart, the toolkit from
    # the CUDA repository, containerd's root on the Docker volume first.
    assert "sudo nvidia-ctk runtime configure" not in GUIDE
    assert "systemctl restart docker" not in GUIDE
    assert "libnvidia-container" not in GUIDE
    assert "cuda-keyring_1.1-1_all.deb" in GUIDE
    assert 'root = "/var/lib/docker/containerd"' in GUIDE
    assert "check_the_containerd_root" in between(SCRIPT, "cmd_check() {")
    assert "check_the_containerd_root" in between(SCRIPT, "prerequisites() {")


def test_the_data_folder_refuses_the_os_drive_beside_a_data_volume():
    # v0.3.135 line 2.
    asked = between(SCRIPT, "ask_the_office_facts() {")
    assert (
        "data_volume_present" in asked and 'ask_yes_no "  Use it anyway?" no' in asked
    )
    assert "mountpoint -q /data" in between(SCRIPT, "data_volume_present() {")
    check = between(SCRIPT, "cmd_check() {")
    assert "move it under /data" in check


def test_the_stack_starts_without_the_engine_network():
    # v0.3.135 line 3.
    wrapper = between(SCRIPT, "compose() {")
    assert "overlay_without_its_network" in wrapper
    assert "COMPOSE_FILE=compose.yaml docker compose" in wrapper
    assert "rejoins it" in between(SCRIPT, "cmd_check() {")
    assert "starts the stack without it" in GUIDE


def test_the_images_build_and_prune_through_our_own_builder():
    # v0.3.135 line 4.
    assert 'BUILDER="transcribe"' in SCRIPT
    assert "moby/buildkit:v0.34.0@sha256:" in SCRIPT
    assert "BUILD_CACHE_WORDS" not in SCRIPT
    assert SCRIPT.count('build --builder "$BUILDER"') >= 3
    assert "compose build ||" not in SCRIPT


def test_the_build_cache_is_kept_up_to_a_ceiling():
    # v1.137.2: the newest records stay between upgrades; `--reserved-space`
    # is a floor, not a ceiling, and `prune -a` on our builder emptied it.
    tidy = between(SCRIPT, "tidy_the_images() {")
    assert (
        'docker buildx prune -f --builder "$BUILDER" --max-used-space "${ceiling}gb"'
        in tidy
    )
    assert 'docker buildx prune -a -f --builder "$BUILDER"' not in SCRIPT
    assert not re.search(r"^\s*docker .*--reserved-space", SCRIPT, re.M)
    assert 'ceiling="$(env_value BUILD_CACHE_GB)"' in tidy
    assert "BUILD_CACHE_GB_DEFAULT=60" in SCRIPT
    assert "\nBUILD_CACHE_GB=60\n" in EXAMPLE
    assert "| `BUILD_CACHE_GB` |" in GUIDE


def test_the_old_records_are_pruned_once_by_our_own_strings():
    # v1.137.2: the records left on the daemon's builder before v1.137.0 go
    # once, by strings from our Dockerfiles, and the filter never runs again.
    assert "prune_the_old_records" in between(SCRIPT, "tidy_the_images() {")
    once = between(SCRIPT, "prune_the_old_records() {")
    assert 'OLD_CACHE_PRUNE_ROUND="2"' in SCRIPT
    assert (
        '[ "$(env_value OLD_CACHE_PRUNED)" = "$OLD_CACHE_PRUNE_ROUND" ] && return 0'
        in once
    )
    assert 'set_env OLD_CACHE_PRUNED "$OLD_CACHE_PRUNE_ROUND"' in once
    # Twice: a record goes only once nothing later points to it (v1.137.3).
    assert once.count("docker buildx prune -a -f --builder default --filter") == 2
    assert "docker buildx prune -a -f --builder default --filter" in once
    assert '--filter "description~=\\"$OLD_CACHE_STRINGS\\""' in once
    assert "\nOLD_CACHE_PRUNED=\n" in EXAMPLE
    strings = between(SCRIPT, 'OLD_CACHE_STRINGS="', '"\n').split("|")
    ours = "".join(
        (HERE / path).read_text(encoding="utf-8")
        for path in (
            "app/Dockerfile",
            "whisperx-service/Dockerfile",
            "whisperx-service/diarizer/Dockerfile",
        )
    )
    # Three are from the diarizer's install line before v1.135.0.
    gone_from_the_files = {"nemo-toolkit", "download.pytorch.org", "Cython packaging"}
    assert len(strings) == 24
    # The two links v1.137.2's list left out, which held the chains in place.
    assert "/tmp/requirements" in strings and "libsndfile1" in strings
    for one in strings:
        assert one in gone_from_the_files or one in ours, one


def test_the_check_reads_the_timers_for_the_zone():
    # v1.137.2: the upgrade runs without sudo and never rewrites the units.
    assert "check_the_timers" in between(SCRIPT, "cmd_check() {")
    check = between(SCRIPT, "check_the_timers() {")
    assert "./transcribe install-timers" in check and '*" $zone")' in check
    assert "install_timers" not in between(SCRIPT, "finish_the_upgrade() {")


def test_the_card_is_checked_for_room_and_for_its_cdi_name():
    # v0.3.135 line 5.
    assert "memory.free" in between(SCRIPT, "card_free_gb() {")
    configure = between(SCRIPT, "configure_transcription() {")
    assert "card_free_gb" in configure and "card_in_the_cdi_spec" in configure
    assert "the CDI spec does not name" in between(SCRIPT, "cmd_check() {")


@pytest.mark.parametrize(
    "unit", ["transcribe-backup", "transcribe-backup-weekly", "transcribe-backup-drill"]
)
def test_every_timer_states_the_zone(unit):
    # v0.3.135 line 6.
    timer = (HERE / "systemd" / f"{unit}.timer").read_text(encoding="utf-8")
    line = next(one for one in timer.splitlines() if one.startswith("OnCalendar="))
    assert line.endswith(" __TZ__")
    assert "s|__TZ__|$zone|g" in between(SCRIPT, "install_timers() {")


def test_caddy_binds_the_lan_address_and_never_every_interface():
    # v0.3.135 line 7.
    published = next(one for one in COMPOSE.splitlines() if ':443"' in one)
    assert "0.0.0.0" not in published and "${BIND_ADDRESS:?" in published
    assert COMPOSE.count("${BIND_ADDRESS:?") == 2
    assert "\nBIND_ADDRESS=\n" in EXAMPLE
    asked = between(SCRIPT, "ask_the_office_facts() {")
    assert "hostname -I" in asked and '""|0.0.0.0|::)' in asked


def test_the_pair_proof_s_install_defects_are_closed():
    # v0.3.141 lines 1, 2, 4, 5, 6, 7.
    certificate = between(SCRIPT, "make_a_self_signed_certificate() {")
    assert '"/CN=Transcribe root ($hostname)"' in certificate
    assert '[ "${#hostname}" -gt 46 ]' in certificate
    assert 'sudo chmod 400 "$HERE/tls/key.pem"' in certificate
    card = between(SCRIPT, "ask_the_card() {")
    assert card.count("profile_remove transcription") == 2
    assert 'gb="$(card_memory_gb "$gpu" || true)"' in between(
        SCRIPT, "ask_the_engine() {"
    )
    assert 'cpus: "${MEDIA_WORKER_CPUS:-4}"' in COMPOSE
    assert "\nMEDIA_WORKER_CPUS=" in EXAMPLE
    assert "write_the_cpu_limit" in between(SCRIPT, "finish_the_upgrade() {")
    install = between(SCRIPT, "cmd_install() {")
    assert 'git -C "$HERE" describe --tags --exact-match' in install
    assert "backup_on || install_timers" in install


def test_the_directory_files_exist_when_sign_in_is_off():
    # v0.3.141 line 3.
    directory = between(SCRIPT, "cmd_directory() {")
    assert "ensure_the_directory_files" in directory
    ensure = between(SCRIPT, "ensure_the_directory_files() {")
    assert "office-root.pem" in ensure and "ldap_bind_password" in ensure
    assert "ensure_the_directory_files" in between(SCRIPT, "make_the_secrets() {")


@pytest.mark.django_db
def test_the_local_admin_takes_its_password_from_a_pipe(monkeypatch):
    # v0.3.141 line 8: an automated install hands the password on stdin.
    monkeypatch.setattr(sys, "stdin", io.StringIO("a-long-enough-password\n"))
    call_command("create_local_admin", name="piped-admin")
    made = User.objects.get(username="piped-admin")
    assert made.is_local and made.check_password("a-long-enough-password")


def test_the_ledger_answers_the_directions_by_number():
    ledger = (HERE / "docs" / "box-ledger.md").read_text(encoding="utf-8")
    # The rules version moves at every merge; the entries below are ours.
    assert "**Rules version:** 2026-10-18.1" in ledger
    ours = ledger.split("### Gideon Transcribe", 1)[1]
    assert "at v1.143.0 (the voice plan's releases v1.138.0 to v1.143.0" in ours
    assert "Your v0.3.178 line 1 and your ticket 25 line 1: done at this fetch" in ours
    assert "Your **v0.3.135**: 1. Done" in ours and "10. Done at this fetch." in ours
    assert "Your **v0.3.141**: 1. Done" in ours
    assert "its named Docker builder `transcribe`" in ledger
    assert "at v1.137.2 (the build cache kept to a ceiling" in ours
    assert "at v1.137.3 (the one-time prune's second round" in ours
    assert "written at install and at every upgrade" not in (
        HERE / "CHANGELOG.md"
    ).read_text(encoding="utf-8")
