"""Every key the app reads is one an office can set, and one compose passes.

Three lists have to agree and nothing made them: the keys the code reads, the
keys `.env.example` offers an office, and the keys `compose.yaml` puts into a
container. When they drift the app does not fail, it quietly uses a default:
`MEDIA_CONCURRENT_JOBS` was read by the media worker's own start-up line and
never passed by compose, so an office setting it got the default and no
warning, and `MEDIA_THREADS_PER_JOB` was in the specification, in nobody's
code, and in no container.

Nothing here reads the office's own `.env`, which is not in the repository and
never will be.
"""

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent.parent
COMPOSE = HERE / "compose.yaml"
EXAMPLE = HERE / ".env.example"
CODE = HERE / "app"

# Read by Django, by the test settings, or by the container's own start-up,
# and not the office's to set in .env.
NOT_THE_OFFICE_S = {
    "APP_DATA_DIR",
    "DJANGO_SETTINGS_MODULE",
    "GUNICORN_TIMEOUT",
    "GUNICORN_WORKERS",
    "HTTPS_PORT",
    "PATH",
    "POSTGRES_APP_USER",
    "POSTGRES_HOST",
    "POSTGRES_PASSWORD",
    "POSTGRES_PORT",
}

ASKED_FOR = re.compile(r"""environ(?:\.get)?[(\[]\s*["']([A-Z][A-Z0-9_]+)["']""")


def keys_the_code_reads() -> set[str]:
    found = set()
    for source in CODE.rglob("*.py"):
        if "/tests/" in source.as_posix() or "/migrations/" in source.as_posix():
            continue
        found |= set(ASKED_FOR.findall(source.read_text(encoding="utf-8")))
    for source in CODE.rglob("*.sh"):
        found |= set(
            re.findall(r"\$\{([A-Z][A-Z0-9_]+)[:}]", source.read_text(encoding="utf-8"))
        )
    return {one for one in found if one not in NOT_THE_OFFICE_S}


def keys_compose_passes() -> set[str]:
    text = COMPOSE.read_text(encoding="utf-8")
    # Both halves: the name a container is given, and the .env name it is
    # taken from.
    given = set(re.findall(r"^\s{6}([A-Z][A-Z0-9_]+):", text, re.M))
    taken = set(re.findall(r"\$\{([A-Z][A-Z0-9_]+)[:?}]", text))
    return given | taken


def keys_the_example_offers() -> set[str]:
    return set(
        re.findall(r"^([A-Z][A-Z0-9_]+)=", EXAMPLE.read_text(encoding="utf-8"), re.M)
    )


def test_the_files_are_where_they_are_expected():
    assert COMPOSE.is_file() and EXAMPLE.is_file()


def test_every_key_the_code_reads_reaches_a_container():
    missing = sorted(keys_the_code_reads() - keys_compose_passes())
    assert not missing, (
        "the app reads these and compose never passes them, so a container "
        "sees nothing and quietly uses a default:\n  " + "\n  ".join(missing)
    )


def test_every_key_an_office_may_set_is_offered_by_the_example():
    # What compose takes from .env is what an office can change, so the
    # example must name it. Anything else is a key nobody knows exists.
    from_env = set(
        re.findall(r"\$\{([A-Z][A-Z0-9_]+)[:?}]", COMPOSE.read_text(encoding="utf-8"))
    )
    missing = sorted(from_env - keys_the_example_offers() - NOT_THE_OFFICE_S)
    assert not missing, (
        "compose takes these from .env and .env.example does not name them, "
        "so an office has no way to know they exist:\n  " + "\n  ".join(missing)
    )
