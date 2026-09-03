"""Settings for a test run: the real ones, with the secrets a run needs.

The app reads its secrets from files, because a secret in an environment
variable turns up in `docker inspect` and in a process list. That is right in
production and a nuisance in a test run, so this module writes the files a run
needs into a temporary folder and then loads the real settings, unchanged.

Nothing here relaxes a rule. The database is a real PostgreSQL, because the
app is a database application and testing it against anything else would be
pretence.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_secrets = Path(tempfile.mkdtemp(prefix="transcribe-test-secrets-"))


def _write(name: str, value: str) -> str:
    path = _secrets / name
    path.write_text(value, encoding="utf-8")
    return str(path)


os.environ.setdefault("DJANGO_SECRET_KEY_FILE", _write("secret_key", "for-tests-only"))
os.environ.setdefault(
    "POSTGRES_PASSWORD_FILE",
    _write("postgres_password", os.environ.get("POSTGRES_PASSWORD", "postgres")),
)
os.environ.setdefault("WHISPERX_TOKEN_FILE", _write("whisperx_token", "0" * 64))
os.environ.setdefault("POSTGRES_HOST", "127.0.0.1")
os.environ.setdefault("POSTGRES_USER", "postgres")
os.environ.setdefault("POSTGRES_APP_USER", os.environ.get("POSTGRES_USER", "postgres"))
os.environ.setdefault("POSTGRES_DB", "postgres")
os.environ.setdefault("APP_DATA_DIR", tempfile.mkdtemp(prefix="transcribe-test-data-"))

from transcribe.settings import *  # noqa: E402, F403
