"""The prepare step (v1.231.0): `prepare.sh`, which does the install guide's
Steps 0 to 2 for a fresh Ubuntu server and then starts the install.

It changes an operating system, so nothing here runs it for real. Every
system command it could call is replaced by a stand-in that writes down how
it was called and keeps a little state (Docker is installed once apt was
asked for it, the account exists once useradd ran), and each test reads the
record: which commands, in which order, on which shape of server. The
commands themselves are held to the guide's, so the two cannot drift.

It has not been run on a clean server; the script says so itself, and the
guide's Steps 0 to 2, by hand, remain the documented way until it has.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent.parent.parent
SCRIPT = HERE / "prepare.sh"
GUIDE = (HERE / "docs" / "install.md").read_text(encoding="utf-8")
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(BASH is None, reason="no bash on this machine")

STAND_INS = {
    # Writes the call down, then does only what the tests need: marks what a
    # command would have installed or made. Folders are made for real only
    # inside the sandbox.
    "sudo": r"""
while [ "${1:-}" = "-n" ]; do shift; done
echo "sudo $*" >> "$LOG"
if [ -n "${FAIL:-}" ]; then case "$*" in *"$FAIL"*) exit 1 ;; esac; fi
case "$*" in
  "docker "*) shift; exec docker "$@" ;;
  *"apt-get install"*docker-ce*) touch "$STATE/docker" ;;
  *"apt-get install -y git"*) touch "$STATE/git" ;;
  *useradd*) touch "$STATE/account" ;;
  *"ubuntu-drivers install"*) touch "$STATE/driver-installed" ;;
  *"nvidia-ctk cdi generate"*) touch "$STATE/cdi" ;;
  "sed -i"*)
    echo 'root = "/var/lib/docker/containerd"' > "$PREPARE_CONTAINERD_CONFIG"
    ;;
  "tee "*)
    cat > "$STATE/tee-$(basename "$2")"
    if [ "$2" = "$PREPARE_CONTAINERD_CONFIG" ]; then
      echo "root = '/var/lib/containerd'" > "$2"
    fi
    ;;
  "install "*)
    for last in "$@"; do :; done
    case "$last" in "$SANDBOX"/*) mkdir -p "$last" ;; esac
    ;;
esac
exit 0
""",
    "docker": r"""
[ -f "$STATE/docker" ] || exit 127
case "$*" in
  "--version") echo "Docker version 29.0.0, build stand-in" ;;
  "compose version --short") echo "2.40.0" ;;
  "ps -aq" | "images -q") cat "$STATE/docker-in-use" 2>/dev/null ;;
esac
exit 0
""",
    "nvidia-smi": r"""
[ -f "$STATE/driver-live" ] || exit 9
case "$*" in *driver_version*) echo "580.65" ;; esac
exit 0
""",
    "lspci": r"""
[ -f "$STATE/card" ] && echo "01:00.0 VGA controller: NVIDIA Corporation Device"
exit 0
""",
    "nvidia-ctk": r"""
[ -f "$STATE/cdi" ] && echo "nvidia.com/gpu=0"
exit 0
""",
    "id": r"""
case "$*" in
  transcribe) [ -f "$STATE/account" ] || exit 1 ;;
  -u) cat "$STATE/uid" 2>/dev/null || echo 1000 ;;
  -un) echo tester ;;
  -nG) if [ -f "$STATE/in-group" ]; then echo "tester docker"; else echo "tester"; fi ;;
esac
exit 0
""",
    "getent": r"""
if [ "$*" = "passwd transcribe" ] && [ -f "$STATE/account" ]; then
  echo "transcribe:x:990:990::$(cat "$STATE/account-home"):/usr/sbin/nologin"
  exit 0
fi
exit 2
""",
    "mountpoint": "exit 1\n",
    "df": r"""
echo "Avail Mounted on"
echo " 50G /"
[ -f "$STATE/drive" ] && echo "900G /srv/data"
exit 0
""",
    "git": r"""
echo "git $*" >> "$LOG"
[ -f "$STATE/git" ] || exit 127
case "$1" in
  ls-remote)
    printf 'a\trefs/tags/v9.9.8\nb\trefs/tags/v9.9.10\nc\trefs/tags/v9.9.9\n'
    ;;
  clone)
    for last in "$@"; do :; done
    mkdir -p "$last"
    printf '#!/bin/bash\necho "transcribe $*" >> "$LOG"\n' > "$last/transcribe"
    chmod +x "$last/transcribe"
    ;;
  -C) echo "v9.9.10" ;;
esac
exit 0
""",
    "dpkg": 'echo "amd64"\n',
    "containerd": "echo \"root = '/var/lib/containerd'\"\n",
    "sg": 'echo "sg $*" >> "$LOG"\nexit 0\n',
}


class Server:
    """A sandbox that stands for one server: its state, and what was run."""

    def __init__(self, base: Path) -> None:
        self.base = base
        self.bin = base / "bin"
        self.state = base / "state"
        self.log = base / "log.txt"
        self.data = base / "srv" / "data" / "transcribe"
        self.home = base / "opt" / "gideon-transcribe"
        self.bin.mkdir()
        self.state.mkdir()
        self.log.write_text("", encoding="utf-8")
        for name, body in STAND_INS.items():
            one = self.bin / name
            one.write_text("#!/bin/bash\n" + body.lstrip("\n"), encoding="utf-8")
            one.chmod(0o755)
        self.has("git")
        self.release("ubuntu", "24.04")

    def has(self, *marks: str) -> Server:
        for mark in marks:
            (self.state / mark).write_text("yes\n", encoding="utf-8")
        return self

    def release(self, ident: str, version: str) -> Server:
        (self.base / "os-release").write_text(
            f'ID={ident}\nVERSION_ID="{version}"\nUBUNTU_CODENAME=noble\n'
            f'PRETTY_NAME="{ident.title()} {version}"\n',
            encoding="utf-8",
        )
        return self

    def run(self, *arguments: str, answers: str = "\n" * 12, fail: str = ""):
        def unix(path: Path) -> str:
            # Git Bash on Windows wants /c/..., and so does the script's PATH.
            text = str(path).replace("\\", "/")
            if len(text) > 1 and text[1] == ":":
                text = "/" + text[0].lower() + text[2:]
            return text

        env = dict(os.environ)
        env.update(
            # In the machine's own form: Git Bash turns a Windows PATH into its
            # own as it starts.
            PATH=str(self.bin) + os.pathsep + env["PATH"],
            LOG=unix(self.log),
            STATE=unix(self.state),
            SANDBOX=unix(self.base),
            USER="tester",
            FAIL=fail,
            PREPARE_OS_RELEASE=unix(self.base / "os-release"),
            PREPARE_CONTAINERD_CONFIG=unix(self.base / "containerd-config.toml"),
            MSYS2_ARG_CONV_EXCL="*",
        )
        done = subprocess.run(
            [
                BASH,
                unix(SCRIPT),
                "--data",
                unix(self.data),
                "--home",
                unix(self.home),
                *arguments,
            ],
            input=answers,
            capture_output=True,
            text=True,
            env=env,
            timeout=300,
        )
        self.out = done.stdout + done.stderr
        self.code = done.returncode
        self.ran = self.log.read_text(encoding="utf-8").splitlines()
        self.changed = [one for one in self.ran if one.startswith("sudo ")]
        return self

    def in_order(self, *wanted: str) -> None:
        """Each of these was run, and in this order."""
        at = 0
        for want in wanted:
            found = next(
                (n for n in range(at, len(self.ran)) if want in self.ran[n]), None
            )
            assert found is not None, f"not run, or out of order: {want}\n" + "\n".join(
                self.ran
            )
            at = found + 1


@pytest.fixture
def server(tmp_path) -> Server:
    return Server(tmp_path)


def test_the_script_parses():
    done = subprocess.run([BASH, "-n", str(SCRIPT)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


def test_looking_only_changes_nothing_and_counts_what_is_left(server):
    server.run("--check-only")
    assert server.code == 0
    assert server.changed == []
    assert not any(one.startswith("git clone") for one in server.ran)
    assert "Looking only: nothing is changed." in server.out
    assert "to do Docker with the Compose plugin" in server.out
    assert "to do the transcribe account, the data folder" in server.out
    assert "to do the Release v9.9.10 fetched into" in server.out
    assert "note  no NVIDIA card" in server.out
    assert "3 to do." in server.out


def test_a_fresh_server_without_a_card_is_prepared_as_the_guide_says(server):
    server.run()
    assert server.code == 0, server.out
    server.in_order(
        "sudo apt-get update",
        "sudo apt-get install -y ca-certificates curl",
        "sudo install -m 0755 -d /etc/apt/keyrings",
        "sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg "
        "-o /etc/apt/keyrings/docker.asc",
        "sudo chmod a+r /etc/apt/keyrings/docker.asc",
        "sudo tee /etc/apt/sources.list.d/docker.sources",
        "sudo apt-get update",
        "sudo apt-get install -y docker-ce docker-ce-cli containerd.io "
        "docker-buildx-plugin docker-compose-plugin",
        "sudo usermod -aG docker tester",
        "sudo mkdir -p /etc/containerd",
        "sudo tee ",
        'sudo sed -i s|^root = .*|root = "/var/lib/docker/containerd"|',
        "sudo systemctl restart containerd docker",
        "sudo useradd --system --no-create-home --home-dir ",
        "sudo install -d -o transcribe -g transcribe -m 0750 ",
        "sudo install -d -o tester -g tester -m 0755 ",
        "git clone --branch v9.9.10 ",
        # The docker group does not reach this shell yet, so sg carries it.
        "sg docker -c cd ",
    )
    sources = (server.state / "tee-docker.sources").read_text(encoding="utf-8")
    assert "Suites: noble" in sources and "Architectures: amd64" in sources
    assert "Signed-By: /etc/apt/keyrings/docker.asc" in sources
    # No card: nothing of NVIDIA's is touched.
    assert not [one for one in server.changed if "nvidia" in one or "drivers" in one]
    assert "Sign out and in" in server.out
    assert "has not yet been run on a clean server" in server.out


def test_docker_already_holding_something_is_never_restarted(server):
    server.has("docker", "account", "in-group")
    (server.state / "docker-in-use").write_text("0123abcd\n", encoding="utf-8")
    (server.state / "account-home").write_text("/srv/data/app\n", encoding="utf-8")
    server.run()
    assert server.code == 0, server.out
    assert "it is left alone, since it moves only by hand" in server.out
    assert not [one for one in server.changed if "systemctl" in one]
    assert not [one for one in server.changed if "docker-ce" in one]
    assert not [one for one in server.changed if "useradd" in one]


def test_a_card_without_a_driver_gets_one_and_the_run_stops_for_a_restart(server):
    server.has("card")
    server.run()
    assert server.code == 0, server.out
    server.in_order("sudo ubuntu-drivers install --gpgpu")
    assert "sudo reboot" in server.out and "run prepare.sh again" in server.out
    # The toolkit waits for a driver that answers, and the install is not started.
    assert not [one for one in server.changed if "nvidia-container-toolkit" in one]
    assert not [one for one in server.ran if one.startswith(("sg ", "transcribe "))]


def test_a_card_with_its_driver_gets_the_toolkit_and_the_cdi_list(server):
    server.has("card", "driver-live")
    server.run()
    assert server.code == 0, server.out
    server.in_order(
        "sudo curl -fsSL https://developer.download.nvidia.com/compute/cuda/repos/"
        "ubuntu2404/x86_64/cuda-keyring_1.1-1_all.deb",
        "sudo dpkg -i /tmp/cuda-keyring_1.1-1_all.deb",
        "sudo apt-get update",
        "sudo apt-get install -y nvidia-container-toolkit",
        "sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml",
    )
    # A driver that works is never touched, and the ledger's two refusals hold.
    assert not [one for one in server.changed if "ubuntu-drivers" in one]
    assert not [one for one in server.changed if "runtime configure" in one]


def test_no_to_everything_changes_nothing(server):
    server.run(answers="no\n" * 12)
    assert server.code == 0, server.out
    assert server.changed == []
    assert not any(one.startswith("git clone") for one in server.ran)
    assert "The install is not started" in server.out


def test_a_command_that_fails_stops_its_step_and_says_so(server):
    server.run(fail="docker-ce")
    assert server.code == 1
    assert "That did not work: Docker could not be installed" in server.out
    assert not [one for one in server.changed if "usermod" in one]
    assert "1 step(s) stopped part way" in server.out
    assert not [one for one in server.ran if one.startswith(("sg ", "transcribe "))]


def test_anything_but_ubuntu_24_or_newer_is_only_looked_at(server):
    for ident, version in (("debian", "13"), ("ubuntu", "22.04")):
        server.log.write_text("", encoding="utf-8")
        server.release(ident, version).run()
        assert server.code == 0, server.out
        assert "the prepare step changes nothing here" in server.out
        assert server.changed == []


def test_it_refuses_to_run_as_root(server):
    (server.state / "uid").write_text("0\n", encoding="utf-8")
    server.run()
    assert server.code == 1
    assert "not as root" in server.out
    assert server.changed == []


def test_a_prepared_server_goes_straight_to_the_install(server):
    server.has("docker", "account", "in-group")
    (server.base / "containerd-config.toml").write_text(
        "root = '/var/lib/docker/containerd'\n", encoding="utf-8"
    )
    (server.state / "account-home").write_text("/srv/data/app\n", encoding="utf-8")
    server.home.mkdir(parents=True)
    stub = server.home / "transcribe"
    stub.write_text('#!/bin/bash\necho "transcribe $*" >> "$LOG"\n', encoding="utf-8")
    stub.chmod(0o755)
    server.run()
    assert server.code == 0, server.out
    assert server.changed == []
    assert "containerd's image store is at /var/lib/docker/containerd" in server.out
    assert server.ran[-1] == "transcribe install"


def test_its_commands_are_the_guides_and_the_ledgers_refusals_hold():
    script = SCRIPT.read_text(encoding="utf-8")
    steps = GUIDE.split("### Step 0: prepare Ubuntu", 1)[1].split(
        "### Step 3: place the certificate", 1
    )[0]
    for shared in (
        "https://download.docker.com/linux/ubuntu/gpg",
        "/etc/apt/keyrings/docker.asc",
        "/etc/apt/sources.list.d/docker.sources",
        "docker-ce docker-ce-cli containerd.io docker-buildx-plugin "
        "docker-compose-plugin",
        "usermod -aG docker",
        "ubuntu-drivers install --gpgpu",
        "cuda-keyring_1.1-1_all.deb",
        "nvidia-container-toolkit",
        "nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml",
        'root = "/var/lib/docker/containerd"',
        "systemctl restart containerd docker",
        "useradd --system --no-create-home --home-dir",
        "--shell /usr/sbin/nologin --user-group",
        "-m 0750",
        "-m 0755",
        "git clone --branch",
    ):
        assert shared in steps, f"not in the guide's steps: {shared}"
        assert shared in script, f"not in prepare.sh: {shared}"
    # The box ledger's v0.3.135 line 1, as test_box_rules holds the guide to it.
    for refused in (
        "nvidia-ctk runtime configure",
        "libnvidia-container",
        "systemctl restart docker",
    ):
        assert refused not in script, refused
    # It says what it is until it has been proven.
    assert "NOT YET PROVEN ON A CLEAN SERVER" in script
    assert "set -uo pipefail" in script and "set -euo pipefail" not in script
