"""Django settings, read from the environment and from secret files.

Nothing office-specific is written down here. Every value an office has to
supply is an environment key, and every secret is a file whose path the
environment names, because a secret in an environment variable ends up in
`docker inspect` and in a process list.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def secret(name: str, default: str | None = None) -> str:
    """Read a secret from the file the environment names.

    Compose mounts each secret at /run/secrets/<name>, which is where the
    environment points. A missing secret is a stopping problem in production
    and a nuisance in a test run, so a default is allowed but never invented.
    """
    path = os.environ.get(name)
    if path:
        try:
            return Path(path).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeError(f"{name} names {path}, which cannot be read") from exc
    if default is not None:
        return default
    raise RuntimeError(f"{name} is not set, and there is no secret to fall back on")


def flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# The app answers on one hostname, the office's own, and Caddy in front of it
# is the only thing that talks to it.
APP_HOSTNAME = os.environ.get("APP_HOSTNAME", "localhost")
ALLOWED_HOSTS = [APP_HOSTNAME, "localhost", "127.0.0.1"]

# Debug is never on. There is no setting for it: an office that could turn it
# on would eventually turn it on, and this app holds privileged material.
DEBUG = False

SECRET_KEY = secret("DJANGO_SECRET_KEY_FILE", default=None if not DEBUG else "insecure")

# Caddy terminates TLS and is the only client, so the app trusts its forwarded
# scheme and no other proxy header.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
CSRF_TRUSTED_ORIGINS = [f"https://{APP_HOSTNAME}", f"https://{APP_HOSTNAME}:8443"]

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

# The app's own account model, and no permission framework beside it. There
# are two roles and admin status has exactly three sources; a second system of
# groups and permissions would be a way for the two to disagree.
AUTH_USER_MODEL = "core.User"
LOGIN_URL = "/sign-in"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "procrastinate.contrib.django",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # After authentication, because it works on the signed-in person: it ends
    # a session that has sat idle, tells somebody who signed in elsewhere, and
    # otherwise moves their idle clock on.
    "core.middleware.LoginSessionMiddleware",
]

ROOT_URLCONF = "transcribe.urls"
WSGI_APPLICATION = "transcribe.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "transcribe"),
        "USER": os.environ.get("POSTGRES_USER", "transcribe"),
        "PASSWORD": secret("POSTGRES_PASSWORD_FILE", default=""),
        "HOST": os.environ.get("POSTGRES_HOST", "postgres"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        # Kept open between requests. The app is one process group talking to
        # one database on the same machine, and reconnecting for every request
        # is a cost with nothing to show for it.
        "CONN_MAX_AGE": 60,
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# The App data folder, mounted at the same place in every container that has
# it. Bytes live here; text lives in the database.
DATA_DIR = Path(os.environ.get("APP_DATA_DIR", "/srv/data"))
UPLOADS_DIR = DATA_DIR / "uploads"
SCRATCH_DIR = DATA_DIR / "scratch"

# The WhisperX service, on its own Docker network. The token makes this app a
# Consumer of it.
WHISPERX_URL = os.environ.get("WHISPERX_URL", "http://whisperx:8000")
WHISPERX_TOKEN = secret("WHISPERX_TOKEN_FILE", default="")

# Directory sign-in over LDAPS. Off until the office's bind account and the two
# groups are configured; with it off, only Local admins can sign in, and a
# directory user is told what they are told whenever the directory cannot be
# reached, which is the truth.
LDAP_ENABLED = flag("LDAP_ENABLED", default=False)

LANGUAGE_CODE = "en-gb"
TIME_ZONE = os.environ.get("TZ", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "static-collected"

# The journal is the only log, and it is never the record: no content, and no
# file names.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "plain"},
    },
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
    "loggers": {
        # Django logs every 4xx and 5xx with the full path. Paths here carry
        # ids, never file names, but the request log adds nothing the Caddy
        # access log does not already have.
        "django.request": {"handlers": ["console"], "level": "ERROR"},
    },
}
