"""The digest check in ./transcribe upgrade, run against a fake docker.

The release workflow records what each tag resolves to in the registry and
leaves it as a git note on the tagged commit; the upgrade compares what it
pulled against that record and refuses on a mismatch (ADR 0013). The
comparison is a shell function, so it is exercised here by sourcing the
script and replacing the two things it reaches for: the record, and docker.
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent.parent.parent
SCRIPT = HERE / "transcribe"
WORKFLOW = HERE / ".github" / "workflows" / "release.yml"

APP = "ghcr.io/tnmd-fdo/gideon-transcribe-app"
WHISPERX = "ghcr.io/tnmd-fdo/gideon-transcribe-whisperx"

# The bash that PATH finds, by its full path. On Windows a bare "bash" goes
# through the system's own search order, which reaches System32 before PATH
# and finds the Windows Subsystem for Linux launcher there, whose only output
# is that no distribution is installed. The full path from which() is Git's.
BASH = shutil.which("bash")


def bash_works() -> bool:
    if BASH is None:
        return False
    probe = subprocess.run([BASH, "-c", "echo ok"], capture_output=True, text=True)
    return probe.returncode == 0 and probe.stdout.strip() == "ok"


needs_bash = pytest.mark.skipif(not bash_works(), reason="no working bash here")


def run_the_check(record: str, pulled: dict[str, str], tag: str = "v9.9.9"):
    """Source the script, fake its two dependencies, and run the check.

    `pulled` maps an image name to the digest docker would report for it.
    Sourcing the script with no argument prints its usage and defines every
    function; the fakes are defined afterwards and so win.
    """
    cases = "\n".join(
        f'    *{name.rsplit("/", 1)[1]}:*) echo "{name}@{digest}" ;;'
        for name, digest in pulled.items()
    )
    program = f"""
set +e
source "{SCRIPT.as_posix()}" >/dev/null 2>&1
docker() {{
  case "${{@: -1}}" in
{cases}
    *) return 1 ;;
  esac
}}
digests_recorded_for() {{ printf '%s\\n' "$RECORD"; }}
verify_the_pull "{tag}"
"""
    return subprocess.run(
        [BASH, "-c", program],
        capture_output=True,
        text=True,
        env={**os.environ, "RECORD": record},
        cwd=HERE,
    )


@needs_bash
def test_a_pull_that_matches_the_record_passes():
    record = f"{APP}:v9.9.9@sha256:aaa\n{WHISPERX}:v9.9.9@sha256:bbb\n"
    done = run_the_check(record, {APP: "sha256:aaa", WHISPERX: "sha256:bbb"})

    assert done.returncode == 0, done.stdout + done.stderr
    assert "is the build the release recorded" in done.stdout
    assert "FAIL" not in done.stdout


@needs_bash
def test_a_pull_that_differs_stops_the_upgrade():
    record = f"{APP}:v9.9.9@sha256:aaa\n{WHISPERX}:v9.9.9@sha256:bbb\n"
    done = run_the_check(record, {APP: "sha256:aaa", WHISPERX: "sha256:NOT-bbb"})

    assert done.returncode == 1, done.stdout + done.stderr
    assert "gideon-transcribe-whisperx:v9.9.9 is not the build" in done.stdout
    assert "recorded: sha256:bbb" in done.stdout
    assert "pulled:   " in done.stdout
    # The way out that trusts the source and not the registry.
    assert "--build" in done.stdout
    # The one that matched still says so, so a reader sees which is which.
    assert "gideon-transcribe-app:v9.9.9 is the build" in done.stdout


@needs_bash
def test_a_missing_image_is_a_mismatch_not_a_pass():
    record = f"{APP}:v9.9.9@sha256:aaa\n"
    done = run_the_check(record, {})

    assert done.returncode == 1
    assert "nothing by that name" in done.stdout


@needs_bash
def test_a_release_with_no_record_is_said_so_and_goes_on():
    # Releases before v1.0.0 have no record, and neither does one whose
    # workflow has not finished. The upgrade says which it might be and goes
    # on, because refusing would make every pre-v1.0.0 upgrade build from
    # source for no gain.
    done = run_the_check("", {APP: "sha256:aaa"})

    assert done.returncode == 0, done.stdout + done.stderr
    assert "no digest record" in done.stdout
    assert "--build" in done.stdout


@needs_bash
def test_the_script_parses():
    done = subprocess.run(
        [BASH, "-n", SCRIPT.as_posix()], capture_output=True, text=True
    )
    assert done.returncode == 0, done.stderr


@needs_bash
def test_a_secret_is_written_and_seen_through_one_helper(tmp_path):
    """Every secret goes through write_secret and secret_present.

    After the install, secrets/ belongs to the app account and is mode 700, so
    a plain test says a file is absent whether it is or not, and a plain
    redirection dies on Permission denied, which under set -e ended an upgrade
    silently on 2026-09-04. On a folder the caller owns the helpers take the
    plain path, which is what can be exercised here; the sudo path is the
    same two lines with sudo in front.
    """
    folder = tmp_path / "secrets"
    program = f"""
set +e
source "{SCRIPT.as_posix()}" >/dev/null 2>&1
own_the_secrets() {{ :; }}
write_secret "{folder.as_posix()}/token" "hello there"
secret_present "{folder.as_posix()}/token" && echo "present: yes"
secret_present "{folder.as_posix()}/missing" || echo "present: no"
secret_exists "{folder.as_posix()}/missing" || echo "exists: no"
append_secret_line "{folder.as_posix()}/tokens" "one two"
append_secret_line "{folder.as_posix()}/tokens" "three"
cat "{folder.as_posix()}/token"; echo
cat "{folder.as_posix()}/tokens"
stat -c '%a' "{folder.as_posix()}/token" 2>/dev/null || echo "mode unknown"
"""
    done = subprocess.run(
        [BASH, "-c", program], capture_output=True, text=True, cwd=HERE
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "present: yes" in done.stdout
    assert "present: no" in done.stdout
    assert "exists: no" in done.stdout
    assert "hello there" in done.stdout
    assert "one two\nthree" in done.stdout


def test_no_secret_is_written_by_a_bare_redirection():
    # The only way into a secrets folder is the helper, because the folder is
    # not the caller's after the install and a bare `>` dies there.
    text = SCRIPT.read_text(encoding="utf-8")
    bare = [
        line.strip()
        for line in text.splitlines()
        if re.search(r'>>?\s*"\$(SERVICE_)?SECRETS/', line)
    ]
    assert bare == [], "these write a secret without the helper:\n  " + "\n  ".join(
        bare
    )
    for helper in ("write_secret()", "secret_present()", "secret_exists()"):
        assert helper in text
    # The helpers' own two redirections are the only ones onto "$path": the
    # plain write and the plain append, taken while the folder is the
    # caller's. Anything more is a third way in.
    assert text.count('>"$path"') == 2


def test_the_workflow_and_the_script_agree_on_where_the_record_lives():
    # Two halves of one design. The workflow writes the note and the script
    # reads it; if either moves the ref, the check silently finds nothing and
    # every upgrade says "no digest record".
    script = SCRIPT.read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert 'DIGESTS_REF="refs/notes/digests"' in script
    assert "git notes --ref=refs/notes/digests add" in workflow
    assert "git push origin refs/notes/digests" in workflow
    # And the record is also attached to the Release for a person to read.
    assert "digests.txt" in workflow


def test_the_record_s_line_shape_is_the_one_the_script_splits():
    # `name:tag@sha256:...`: the script takes the digest after the last "@"
    # and the name before the last ":". The workflow writes exactly that.
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert 'echo "$image:$tag@$digest" >> digests.txt' in workflow
