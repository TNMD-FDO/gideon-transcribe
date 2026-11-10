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


@needs_bash
def test_the_help_prints_every_command_in_the_header():
    """v1.133.0: the help had printed the header's first 32 lines while the
    command list ran to 41, so six commands never showed."""
    done = subprocess.run(
        [BASH, str(SCRIPT), "help"], capture_output=True, text=True, cwd=HERE
    )
    shown = set(re.findall(r"^\s*\./transcribe ([a-z-]+)", done.stdout, re.M))
    listed = set(re.findall(r"^#   \./transcribe ([a-z-]+)", text(), re.M))
    assert listed - shown == set(), f"in the header, not in the help: {listed - shown}"


def test_every_usage_line_is_dispatched_and_the_other_way_round():
    usage = set(re.findall(r"^#   \./transcribe ([a-z-]+)", text(), re.M))
    dispatch = set(re.findall(r"^([a-z-]+)\) (?:shift && )?cmd_", text(), re.M))
    # `help` is the usage itself; `status` and the rest are commands.
    assert usage - dispatch == set(), (
        f"in the usage block, not dispatched: {usage - dispatch}"
    )
    # Commands an operator is not told about are allowed only when they are
    # what the timers call or a step of another command.
    quiet = {"backup-weekly", "upgrade-finish"}
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


def test_the_scripts_budgets_are_the_apps():
    """v1.92.0: the four card budgets the install fits by are the four the
    app draws the Installation page from."""
    source = text()
    for name, value in (
        ("TRANSCRIPTION_GB", pieces.TRANSCRIPTION_GB),
        ("DIARIZER_GB", pieces.DIARIZER_GB),
        ("ENGINE_GB", pieces.ENGINE_GB),
        ("FAST_LANE_GB", pieces.FAST_LANE_GB),
        ("LEAST_CARD_GB", pieces.LEAST_CARD_GB),
    ):
        assert re.search(rf"^{name}={value}$", source, re.M), name


def _sourced(names: list[str], extra: str = "") -> str:
    source = text()
    wanted = [extra] if extra else []
    for name in names:
        match = re.search(rf"^{name}\(\) \{{\n.*?^\}}\n", source, re.M | re.S)
        assert match, name
        wanted.append(match.group(0))
    budgets = "\n".join(
        re.findall(
            r"^(?:TRANSCRIPTION|DIARIZER|ENGINE|FAST_LANE|LEAST_CARD)_GB=\d+$",
            source,
            re.M,
        )
    )
    return "set -euo pipefail\n" + budgets + "\n" + "\n".join(wanted)


@needs_bash
def test_a_fixed_answer_takes_its_first_letter_and_asks_again_on_no_match():
    """v1.92.0: one rule for every question with fixed answers."""
    probe = _sourced(["ask", "ask_choice", "ask_yes_no"]) + (
        '\nprintf "%s|" "$(ask_choice "The engine" none "local|shared|none")"'
        '\nprintf "%s|" "$(ask_choice "The certificate" own "own|self-signed")"'
        '\nask_yes_no "Go on?" yes && printf "yes|" || printf "no|"'
        '\nask_yes_no "Go on?" yes && printf "yes|" || printf "no|"'
        "\n"
    )
    # "S" is shared; "maybe" then "self" is asked again then taken; Enter is
    # the default; "N" is no.
    done = subprocess.run(
        [BASH, "-c", probe],
        input="S\nmaybe\nself\n\nN\n",
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout == "shared|self-signed|yes|no|"
    assert "Please answer one of: own self-signed" in done.stderr


@needs_bash
def test_the_ladder_says_where_this_server_sits():
    """v1.92.0: the row for a server with no card, a small card, a card with
    room for the engine, and a card with room for everything."""
    probe = _sourced(["fit_the_card", "this_server_line", "print_the_ladder"]) + (
        '\nfor gb in "" 12 24 48 96; do this_server_line "$gb"; echo ---; done'
        "\nprint_the_ladder 24 | head -3\n"
    )
    done = subprocess.run([BASH, "-c", probe], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    out = done.stdout
    rows = out.split("---\n")
    assert "This server: no card." in rows[0] and "an engine on the LAN" in rows[0]
    assert "a 12 GB card, under the 16 GB" in rows[1]
    assert (
        "a 24 GB card. Transcription at batch size 8, recordings up to about two hours."
        in rows[2]
    )
    assert (
        "The Local engine needs 44 GB in all" in rows[2]
        and "No room for the fast lane" in rows[2]
    )
    assert (
        "a 48 GB card. Transcription at batch size 16, the measured speed." in rows[3]
    )
    assert (
        "Room for the Local engine" in rows[3]
        and "No room left for the fast lane" in rows[3]
    )
    assert "Room for the fast lane too." in rows[4]
    assert "What a server has, and what that opens:" in rows[5]


@needs_bash
def test_the_cards_memory_is_read_to_the_nearest_gigabyte():
    """v1.92.1: a 96 GB card reports 97,887 MiB and read as 95 GB."""
    probe = _sourced(["mib_to_gb"]) + (
        "\nfor mb in 97887 98304 24576 24000 16380 8192; do"
        ' printf "%s:%s " "$mb" "$(mib_to_gb $mb)"; done\n'
    )
    done = subprocess.run([BASH, "-c", probe], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert done.stdout.split() == [
        "97887:96",
        "98304:96",
        "24576:24",
        "24000:23",
        "16380:16",
        "8192:8",
    ]
    body = text()
    prerequisites = body.split("prerequisites() {", 1)[1].split("\n}\n", 1)[0]
    assert "DRIVER_FLOOR" in prerequisites and re.search(
        r"^DRIVER_FLOOR=570$", body, re.M
    )
    migrate = body.split("migrate_the_card_memory() {", 1)[1].split("\n}\n", 1)[0]
    assert '[ "$gb" != "$(env_value CARD_MEMORY_GB)" ]' in migrate


def test_every_prerequisite_failure_names_its_step():
    """v1.93.1: a stranger on a bare machine reads which step of the guide
    puts each missing thing right, and the guide's failure table has a row
    for each failure in the script's own words."""
    body = text()
    prerequisites = body.split("prerequisites() {", 1)[1].split("\n}\n", 1)[0]
    guide = (HERE / "docs" / "install.md").read_text(encoding="utf-8")
    for words in (
        "there is no docker on this server; the install guide's Step 0 installs it",
        "the docker compose plugin is not installed, or this account is not in "
        "the docker group yet; the install guide's Step 0 has both",
        "account; the install guide's Step 1 makes it",
    ):
        assert words in prerequisites, words
        assert words in guide, words
    assert "server preparation" not in prerequisites


def test_the_install_prints_the_ladder_checks_cdi_and_offers_the_rest():
    body = text()
    install = body.split("cmd_install() {", 1)[1].split("\n}\n", 1)[0]
    assert 'print_the_ladder "$(largest_card_gb)"' in install
    assert "ask_the_engine" in install and install.index(
        "ask_the_card"
    ) < install.index("ask_the_engine")
    assert 'ask_yes_no "Do the rest now, in that order?" yes' in install
    prerequisites = body.split("prerequisites() {", 1)[1].split("\n}\n", 1)[0]
    assert "nvidia-ctk cdi list" in prerequisites
    bring_up = body.split("cmd_bring_up() {", 1)[1].split("\n}\n", 1)[0]
    for step in (
        "compose pull --quiet",
        "whisperx selftest",
        "whisperx pull",
        "compose up -d",
        "create-local-admin",
        "cmd_check",
    ):
        assert step in bring_up, step
    check = body.split("cmd_check() {", 1)[1].split("\n}\n", 1)[0]
    assert "refits it" in check
    finish = body.split("finish_the_upgrade() {", 1)[1].split("\n}\n", 1)[0]
    assert "migrate_the_card_memory" in finish


@needs_bash
def test_the_os_drive_helper_judges_by_the_nearest_folder_that_exists():
    """v1.125.0: the root is the OS drive, a folder not made yet is judged by
    the nearest parent that exists, and the install's question and the
    check both call the helper."""
    source = text()
    match = re.search(r"^on_the_os_drive\(\) \{\n.*?^\}\n", source, re.M | re.S)
    assert match
    probe = (
        "set -uo pipefail\n" + match.group(0) + "\nfor p in / /no/such/folder/yet; do"
        ' if on_the_os_drive "$p"; then echo "$p:os"; else echo "$p:own"; fi; done\n'
    )
    done = subprocess.run([BASH, "-c", probe], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert done.stdout.split() == ["/:os", "/no/such/folder/yet:os"]
    asked = source.index('ask "The app data folder')
    assert 'on_the_os_drive "$value"' in source[asked : asked + 400]
    assert 'ask_yes_no "  Use it anyway?" no' in source[asked : asked + 800]
    assert source.count("on_the_os_drive") == 4


def test_the_check_sends_one_test_message_and_never_counts_mailboxes():
    """v1.129.1: the check's Email section proves the relay with one test
    message and no more; the count of Sign-in members without a mail value
    is gone at the maintainer's word. And the backup section says it could
    not read the secrets without sudo rather than calling them empty."""
    source = text()
    mail = source.split("check_the_mail() {", 1)[1].split("\n}\n", 1)[0]
    assert "mail_check test" in mail and "mail_check count" not in mail
    assert source.count("mail_check count") == 0
    backup = source.split("check_the_backup() {", 1)[1].split("\n}\n", 1)[0]
    sudo_note = backup.index("could not read the secrets folder without sudo")
    assert sudo_note < backup.index("secrets/backup_ssh_key is empty")
    assert "sudo -n true 2>/dev/null" in backup[:sudo_note]


def test_the_directory_check_runs_inside_django():
    """v1.149.0: the check's directory section had run a bare `python -c`
    that imported the Units lines before Django loaded, and printed FAIL on
    every upgrade since v1.147.0; it runs through manage.py shell now."""
    source = text()
    after = source.split('echo "The directory"', 1)[1]
    section = after.split('echo "The WhisperX service"', 1)[0]
    assert 'python manage.py shell -v 0 -c "' in section
    assert "directory.test_connection()" in section
    assert 'python -c "' not in section


# The wider check (v1.229.0) ---------------------------------------------------

_SAYS = (
    'pass() { echo "  pass  $1"; }\n'
    'note() { echo "  note  $1"; }\n'
    'green() { echo "$1"; }\n'
    'amber() { echo "$1"; }\n'
)


def _figures() -> str:
    """The wider check's own numbers, as the script sets them."""
    found = re.findall(
        r"^(?:LEAST_CORES|LEAST_MEMORY_GB|DOCKER_GB_TO_KEEP|DATA_GB_TO_KEEP"
        r"|USUAL_PORT|ROOT_GB_TO_BUILD)=\d+$|^REACH_HOSTS=.*$",
        text(),
        re.M,
    )
    assert len(found) == 7, found
    return "\n".join(found) + "\n"


def test_the_install_still_stops_for_three_things_and_no_more():
    """v1.229.0: the opening checks say much more, and what stops an install
    is what stopped it before: Docker, the Compose plugin and the account."""
    body = text()
    prerequisites = body.split("prerequisites() {", 1)[1].split("\n}\n", 1)[0]
    assert prerequisites.count("ok=no") == 3
    for called in (
        "check_the_system",
        "check_the_room",
        "check_the_port",
        "check_the_reach",
    ):
        assert f"\n  {called}\n" in prerequisites, called
    for name in ("check_the_system", "check_the_room", "check_the_reach"):
        one = body.split(f"{name}() {{", 1)[1].split("\n}\n", 1)[0]
        assert "fail " not in one and "ok=no" not in one, name
    preflight = body.split("cmd_preflight() {", 1)[1].split("\n}\n", 1)[0]
    assert "if prerequisites; then" in preflight
    assert "need_env" not in preflight
    # The name is judged right after it is typed.
    facts = body.split("ask_the_address() {", 1)[1].split("\n}\n", 1)[0]
    assert (
        'set_env APP_HOSTNAME "$value"\n  say_whether_the_name_resolves "$value"'
        in facts
    )


@needs_bash
def test_the_room_where_docker_keeps_its_images_is_said_three_ways():
    probe = (
        _sourced(
            ["check_the_room"],
            _SAYS
            + _figures()
            + "ENV_FILE=/nowhere/.env\ndata_volume_present() { return 1; }\n"
            + 'largest_other_drive() { echo "$DRIVE"; }\n'
            + 'root_gb_free() { echo "$ROOM"; }\n',
        )
        + "\nROOM=150 DRIVE='900 /srv/data' check_the_room"
        + "\nROOM=60 DRIVE='' check_the_room"
        + "\nROOM=30 DRIVE='' check_the_room"
        + "\necho went-on\n"
    )
    done = subprocess.run([BASH, "-c", probe], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    out = done.stdout
    assert "pass  150 GB free where Docker keeps its images" in out
    assert (
        "note  60 GB free where Docker keeps its images; the guide asks for 100" in out
    )
    assert "note  only 30 GB free where Docker keeps its images" in out
    assert (
        "pass  a drive apart from the operating system's at /srv/data with 900" in out
    )
    assert "note  no drive apart from the operating system's was found" in out
    assert out.rstrip().endswith("went-on")


@needs_bash
def test_a_host_that_does_not_answer_is_a_note_that_says_what_it_is_for():
    probe = (
        _sourced(
            ["what_a_host_is_for", "check_the_reach"],
            _SAYS + _figures() + 'answers_from_here() { [ "$1" != "$SILENT" ]; }\n',
        )
        + "\nSILENT=none check_the_reach"
        + "\nSILENT=huggingface.co check_the_reach"
        + "\necho went-on\n"
    )
    done = subprocess.run([BASH, "-c", probe], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    out = done.stdout
    assert (
        "pass  github.com, ghcr.io, registry-1.docker.io and huggingface.co "
        "answer from here" in out
    )
    assert "note  huggingface.co does not answer from here: the models" in out
    assert out.rstrip().endswith("went-on")


@needs_bash
def test_the_system_line_passes_ubuntu_24_and_notes_anything_else():
    def run(ident: str, version: str) -> str:
        probe = (
            _sourced(
                ["check_the_system"],
                _SAYS
                + _figures()
                + 'os_release_value() { case "$1" in '
                + f"ID) echo {ident} ;; VERSION_ID) echo {version} ;; "
                + "*) echo 'Some System 9' ;; esac; }\n",
            )
            + "\ncheck_the_system\n"
        )
        done = subprocess.run([BASH, "-c", probe], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return done.stdout

    assert "pass  Ubuntu 24.04" in run("ubuntu", "24.04")
    assert "pass  Ubuntu 26.04" in run("ubuntu", "26.04")
    assert "note  this is Ubuntu 22.04" in run("ubuntu", "22.04")
    assert "note  this is Some System 9" in run("debian", "13")


@needs_bash
def test_the_image_store_check_goes_on_where_the_config_has_no_root_line():
    """v1.229.0: called plainly, as ./transcribe check calls it, a config
    with no root line (the file the package ships) or no config at all made
    the search fail under the script's strict mode and ended the script
    there, silently. And containerd 2 writes the path in single quotes."""
    probe = (
        _sourced(["check_the_containerd_root"], _SAYS)
        + "\ncheck_the_containerd_root\necho went-on\n"
    )
    done = subprocess.run([BASH, "-c", probe], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert done.stdout.rstrip().endswith("went-on")
    one = text().split("check_the_containerd_root() {", 1)[1].split("\n}\n", 1)[0]
    assert '| tr -d "\\"\'" |' in one and "|| true)" in one


def test_the_guide_has_a_row_for_every_note_of_the_wider_check():
    """Each row is in the guide in full, and its fixed words are the
    script's own (the figures in a line come from the script's numbers)."""
    guide = (HERE / "docs" / "install.md").read_text(encoding="utf-8")
    table = guide.split("## 6. When it fails", 1)[1].split("## 7. Upgrade", 1)[0]
    for in_the_guide, in_the_script in (
        (
            "the install guide is written for Ubuntu Server 24.04 or newer",
            "the install guide is written for Ubuntu Server 24.04 or newer",
        ),
        ("the app wants about 4 cores and 16 GB", "the app wants about"),
        (
            "an image cannot be built here with under 40 GB",
            "an image cannot be built here with under",
        ),
        ("the guide asks for 100 GB there", "the guide asks for"),
        (
            "no drive apart from the operating system's was found",
            "no drive apart from the operating system's was found",
        ),
        (
            "port 8443 is already in use on this server",
            "is already in use on this server",
        ),
        ("does not answer from here", "does not answer from here"),
        (
            "is not in DNS yet, as seen from this server.",
            "is not in DNS yet, as seen from this server.",
        ),
    ):
        assert in_the_guide in table, in_the_guide
        assert in_the_script in text(), in_the_script
    assert "`./transcribe preflight`" in guide


# The one screen (v1.230.0) ----------------------------------------------------

_SCREEN = [
    "is_unset",
    "asked_for",
    "needs_a_person",
    "mark_or_unmark",
    "card_usual_answer",
    "screen_label",
    "screen_value",
    "the_screen",
]

_SCREEN_STANDS_IN = (
    'HERE=/nowhere\nASK_PIECES=""\nASK_ALL=no\nNETWORK_PROPOSED=yes\n'
    'env_value() { case "$1" in APP_HOSTNAME) echo app.example.internal ;; '
    "HTTPS_PORT) echo 8443 ;; BIND_ADDRESS) echo 10.0.0.12 ;; "
    "ALLOWED_CLIENT_CIDRS) echo 10.0.0.0/24 ;; APP_DATA_DIR) echo /data/app ;; "
    "TZ) echo Europe/London ;; esac; }\n"
    "folder_gb_free() { echo 900; }\n"
    "certificate_is_self_signed() { return 1; }\n"
    'card_count() { echo "$CARDS"; }\n'
    'largest_card_gb() { echo "$CARD_GB"; }\n'
)


def test_a_first_install_asks_the_address_then_shows_the_screen():
    """v1.230.0: one typed answer, one screen, then the same pieces in the
    same order, each asked or taken as proposed; a reconfigure asks every
    question as it always did."""
    body = text()
    install = body.split("cmd_install() {", 1)[1].split("\n}\n", 1)[0]
    first = install.split('if [ "$reconfigure" = "yes" ]; then', 1)[1]
    again, first = first.split("  else\n", 1)
    assert "ASK_ALL=yes" in again and "ask_the_office_facts" in again
    order = [
        "ask_the_address",
        "propose_the_office_facts",
        "choose_on_the_screen",
        "write_what_the_server_decides",
        'piece certificate "The certificate" ask_the_certificate',
        'piece directory "Sign-in" cmd_directory',
        "make_the_secrets",
        'piece card "Transcription" ask_the_card',
        'piece engine "The AI assistant" ask_the_engine',
        'piece fast-lane "The fast lane" ask_the_fast_lane',
        'piece backup "Backup" ask_the_backup',
        "backup_on || install_timers",
        'piece mail "Mail" ask_the_mail',
    ]
    places = [first.index(one) for one in order]
    assert places == sorted(places)
    # Every question the reconfigure asks is still one question each.
    facts = body.split("ask_the_office_facts() {", 1)[1].split("\n}\n", 1)[0]
    for one in (
        "ask_the_address",
        "ask_the_port",
        "ask_the_lan_address",
        "ask_who_may_connect",
        "ask_the_data_folder",
        "ask_the_time_zone",
        "write_what_the_server_decides",
    ):
        assert f"\n  {one}" in facts, one


@needs_bash
def test_a_piece_taken_as_proposed_answers_with_what_is_there_and_never_a_placeholder():
    probe = _sourced(["ask", "ask_choice", "ask_yes_no"]) + (
        "\nTAKE_DEFAULTS=1"
        '\nprintf "%s|" "$(ask "The port" 8443)"'
        '\nprintf "%s|" "$(ask "The backup target" "")"'
        '\nprintf "%s|" "$(ask "The address" "<hostname>")"'
        '\nprintf "%s|" "$(ask_choice "The engine" none "local|shared|none")"'
        '\nprintf "%s|" "$(ask_choice "The certificate" nothing "own|self-signed")"'
        "\n"
    )
    # Only two answers are read: the placeholder's, and the choice whose
    # usual answer matched nothing.
    done = subprocess.run(
        [BASH, "-c", probe],
        input="typed.example.internal\nself\n",
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout == "8443||typed.example.internal|none|self-signed|"


@needs_bash
def test_the_screen_says_what_is_proposed_for_the_server_it_is_on():
    def screen(cards: str, gb: str, then: str = "") -> str:
        probe = (
            _sourced(_SCREEN, _SCREEN_STANDS_IN + f"CARDS={cards}\nCARD_GB={gb}\n")
            + f"\n{then}\nthe_screen\n"
        )
        done = subprocess.run(
            [BASH, "-c", probe], capture_output=True, text=True, timeout=120
        )
        assert done.returncode == 0, done.stderr
        return done.stdout

    none = screen("0", "")
    assert "Enter to go on, or a number to change a line." in none
    assert " 1  The address       app.example.internal" in none
    assert " 4  Who may connect   10.0.0.0/24  (this server's own network" in none
    assert " 5  The data folder   /data/app  (900 GB free)" in none
    assert " 7  The certificate   self-signed, made now" in none
    assert " 8  Sign-in           Local admins only" in none
    assert " 9  Transcription     not installed, no card" in none
    assert "10  The AI assistant  off, no engine" in none
    assert "The fast lane" not in none
    assert "12  Mail              none" in none and "13  " not in none

    one = screen("1", "48")
    assert " 9  Transcription     on, with this server's card  (48 GB)" in one
    assert "10  The AI assistant  the Local engine, on the same card" in one
    assert "11  The fast lane     off" in one and "13  Mail" in one

    # 24 GB carries transcription and not the engine beside it.
    assert "10  The AI assistant  off, no engine" in screen("1", "24")

    small = screen("1", "12")
    assert "not installed: the card has 12 GB, under the 16 GB it needs" in small
    assert "The fast lane" not in small

    two = screen("2", "48")
    assert " 9  Transcription     asked when you go on: 2 cards here" in two

    marked = screen("0", "", "mark_or_unmark directory; mark_or_unmark backup")
    assert " 8  Sign-in           asked when you go on" in marked
    assert "11  Backup            asked when you go on" in marked
    again = screen("0", "", "mark_or_unmark directory; mark_or_unmark directory")
    assert " 8  Sign-in           Local admins only" in again


@needs_bash
def test_a_piece_is_asked_when_marked_and_otherwise_says_one_line():
    probe = (
        _sourced(
            ["asked_for", "needs_a_person", "piece"],
            'ASK_PIECES=""\nASK_ALL=no\n'
            "card_count() { echo 0; }\n"
            'green() { printf "%s\\n" "$1"; }\n'
            'amber() { printf "\\033[33m%s\\033[0m\\n" "$1"; }\n'
            'state_words() { echo "as it stands"; }\n'
            'a_piece() { echo "A long explanation."; amber "A warning."; '
            'echo "mode:${TAKE_DEFAULTS:-asked}"; }\n'
            'a_failing_piece() { echo "What went wrong."; return 3; }\n',
        )
        + '\npiece backup "Backup" a_piece'
        + '\nASK_PIECES=" backup"\npiece backup "Backup" a_piece'
        + '\nASK_PIECES=""\nASK_ALL=yes\npiece backup "Backup" a_piece'
        + '\nASK_ALL=no\npiece mail "Mail" a_failing_piece || echo "stopped:$?"\n'
    )
    done = subprocess.run(
        [BASH, "-c", probe], capture_output=True, text=True, timeout=60
    )
    assert done.returncode == 0, done.stderr
    lines = [re.sub(r"\x1b\[[0-9;]*m", "", one) for one in done.stdout.splitlines()]
    assert lines == [
        # Taken as proposed: the warning and one line, no explanation.
        "A warning.",
        "  set   Backup: as it stands",
        # Marked on the screen: its own words, in full, and it is asked.
        "A long explanation.",
        "A warning.",
        "mode:asked",
        # A reconfigure asks everything.
        "A long explanation.",
        "A warning.",
        "mode:asked",
        # A piece that fails says everything it said, and the failure stands.
        "What went wrong.",
        "stopped:3",
    ]


@needs_bash
def test_who_may_connect_is_proposed_as_the_servers_own_network():
    probe = (
        _sourced(
            ["own_network_of"],
            "ip() { "
            'echo "10.0.0.0/24 dev eth0 proto kernel scope link src 10.0.0.12 x"; '
            'echo "172.17.0.0/16 dev docker0 scope link src 172.17.0.1"; }\n',
        )
        + '\nprintf "%s|" "$(own_network_of 10.0.0.12)"'
        + '\nprintf "%s|" "$(own_network_of 10.0.0.1)"'
        + '\nprintf "%s|" "$(own_network_of 172.17.0.1)"\n'
    )
    done = subprocess.run(
        [BASH, "-c", probe], capture_output=True, text=True, timeout=60
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout == "10.0.0.0/24||172.17.0.0/16|"


@needs_bash
def test_the_free_space_of_a_value_that_is_no_path_does_not_spin():
    """Found by a trial install on a Windows shell, where a path came back
    as a drive letter with no folder above it: the climb to the nearest
    folder that exists has to end."""
    probe = (
        _sourced(["folder_gb_free"])
        + '\ndirname() { echo "$1"; }\n'
        + "folder_gb_free no-such-thing-anywhere; echo ended\n"
    )
    done = subprocess.run(
        [BASH, "-c", probe], capture_output=True, text=True, timeout=30
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == "ended"
