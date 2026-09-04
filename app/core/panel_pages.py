"""The panel's Overview and Server pages: Status, Queue, Users, Installation.

None of these is a settings page, so none of them goes through the tray: the
Users page's actions apply at once, each with its own confirmation and its own
audit row, and the rest only look. Viewing the Status or Queue page writes no
audit row, because looking is not an access to anybody's material.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from django.conf import settings as django_settings
from django.db import models
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core import audit, lifecycle, settings_store, uploads, whisperx
from core.jobs import Job, JobState
from core.models import LoginSession, User
from core.panel import admins_only, furniture
from core.recordings import Recording

log = logging.getLogger("transcribe.panel")


# Status -----------------------------------------------------------------------


@admins_only
def status(request: HttpRequest) -> HttpResponse:
    """One page of lines, asked for again every five seconds."""
    return render(request, "panel/status.html", furniture(request, "panel-status"))


@admins_only
def status_lines(request: HttpRequest) -> JsonResponse:
    """What the Status page reads. Every line the specification names that
    the build has reached; the rest arrive with the features they belong to."""
    free = uploads.free_disk_bytes()
    floor = settings_store.minimum_free_disk_bytes()

    return JsonResponse(
        {
            "services": _services(),
            "service": _whisperx(),
            "storage": {
                "free": uploads.as_gb(free),
                "colour": "red" if free < floor else (
                    "amber" if free < floor * 2 else "plain"
                ),
                "floor": uploads.as_gb(floor),
            },
            "workspaces": _workspaces(),
            "media": _media(),
            "versions": _versions(),
        }
    )


def _services() -> list[dict]:
    """A health row per service, by asking each one rather than asking Docker.

    Reading Docker's own health state means giving the app the Docker socket,
    which is root on the server: too much to hand an app that holds
    privileged material so that a page can print a word (ADR 0009). Each
    service that answers on the network is asked directly, and the two
    workers, which listen on nothing, are read from the work they have done.
    """
    return [
        {"name": "app", "state": "healthy", "says": "answering this page"},
        _listening("caddy", "caddy", 443),
        _reachable("tusd", os.environ.get("TUSD_URL", "http://tusd:1080") + "/metrics"),
        _database(),
        _service_health(),
        _worker("default"),
        _worker("media"),
    ]


def _listening(name: str, host: str, port: int) -> dict:
    """Whether something is accepting connections on that port.

    Caddy answers TLS only, and only for the office's own hostname, so a
    request from inside the project network is turned away before it is a
    request. That the listener accepts a connection is the thing worth
    knowing, and it needs no certificate.
    """
    import socket

    try:
        with socket.create_connection((host, port), timeout=3):
            return {"name": name, "state": "healthy", "says": f"listening on {port}"}
    except OSError as problem:
        return {"name": name, "state": "unreachable", "says": str(problem)[:80]}


def _reachable(name: str, url: str) -> dict:
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(url, timeout=3) as answer:
            said = answer.status
        return {"name": name, "state": "healthy", "says": f"answered {said}"}
    except urllib.error.HTTPError as answer:
        # An answer of any kind means the service is up; what it thought of
        # the request is not this page's business.
        return {"name": name, "state": "healthy", "says": f"answered {answer.code}"}
    except Exception as problem:  # noqa: BLE001 - anything else is not reachable
        return {"name": name, "state": "unreachable", "says": str(problem)[:80]}


def _database() -> dict:
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return {"name": "postgres", "state": "healthy", "says": "answering"}
    except Exception as problem:  # noqa: BLE001
        return {"name": "postgres", "state": "unreachable", "says": str(problem)[:80]}


def _service_health() -> dict:
    if whisperx.is_alive():
        return {"name": "whisperx", "state": "healthy", "says": "answering"}
    return {"name": "whisperx", "state": "unreachable", "says": "no answer"}


def _worker(queue: str) -> dict:
    """A worker is alive if its queue has run something lately.

    Neither worker listens on anything, so this is what there is to read: the
    last job on that queue to succeed. The `default` queue runs something
    every minute, so silence there means the worker is gone. The `media`
    queue runs only when there is media to work on, so silence there means
    nothing more than a quiet afternoon.
    """
    from django.db import connection
    from django.utils import timezone

    # Procrastinate's own event log is what says when, because a periodic
    # job's row carries no time of its own.
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT max(event.at) FROM procrastinate_events event "
            "JOIN procrastinate_jobs job ON job.id = event.job_id "
            "WHERE job.queue_name = %s AND event.type = 'succeeded'",
            [queue],
        )
        row = cursor.fetchone()

    last = row[0] if row else None
    name = "worker" if queue == "default" else "media-worker"

    if queue == "default":
        alive = last is not None and (timezone.now() - last).total_seconds() < 300
        return {
            "name": name,
            "state": "healthy" if alive else "not running",
            "says": f"last ran {last:%H:%M}" if last else "nothing has run yet",
        }
    return {
        "name": name,
        "state": "healthy",
        "says": f"last media job {last:%d %b %H:%M}" if last else "no media job yet",
    }


def _whisperx() -> dict:
    """The service's own status endpoint, rendered for an Admin."""
    try:
        return {"up": True, **whisperx.status()}
    except Exception as problem:  # noqa: BLE001 - any failure is "not reachable"
        return {"up": False, "says": str(problem)}


def _workspaces() -> dict:
    people = User.objects.filter(recordings__isnull=False).distinct()
    open_now = busy = 0
    for person in people:
        if lifecycle.is_open(person):
            open_now += 1
        if lifecycle.is_busy(person):
            busy += 1

    scratch = Path(django_settings.SCRATCH_DIR)
    size = 0
    if scratch.is_dir():
        size = sum(
            path.stat().st_size for path in scratch.rglob("*") if path.is_file()
        )
    return {
        "open": open_now,
        "busy": busy,
        "gigabytes": f"{size / 1024**3:.1f}",
    }


def _media() -> dict:
    from core.recordings import MediaState

    pieces = Path(django_settings.UPLOADS_DIR)
    waiting = len(list(pieces.glob("*.info"))) if pieces.is_dir() else 0
    return {
        "running": Recording.objects.filter(
            media_state__in=(MediaState.CHECKING, MediaState.PREPARING)
        ).count(),
        "pieces": waiting,
    }


def _versions() -> dict:
    from django.db.migrations.recorder import MigrationRecorder

    last = (
        MigrationRecorder.Migration.objects.filter(app="core")
        .order_by("-id")
        .first()
    )
    service = _whisperx()
    versions = service.get("versions") or {}
    return {
        "release": os.environ.get("RELEASE_TAG", "not tagged"),
        "migration": last.name if last else "none",
        "service": versions.get("service", "not reachable"),
    }


# Queue ------------------------------------------------------------------------


@admins_only
def queue_page(request: HttpRequest) -> HttpResponse:
    """Every Job in the queue, with a Cancel. No pause, no reordering."""
    return render(request, "panel/queue.html", furniture(request, "panel-queue"))


@admins_only
def queue_state(request: HttpRequest) -> JsonResponse:
    rows = []
    for job in (
        Job.objects.select_related("recording", "recording__user", "batch")
        .order_by("-created")[:100]
    ):
        run = job.runs.order_by("side__number").first()
        rows.append(
            {
                "id": str(job.pk),
                "user": job.recording.user.username,
                "title": job.recording.title,
                "batch": str(job.batch_id)[:8],
                "started": job.created.isoformat(),
                "minutes": round((job.recording.duration_seconds or 0) / 60, 1),
                "state": job.state,
                "step": job.step,
                "position": run.position if run else None,
                "live": job.is_live,
            }
        )
    return JsonResponse({"jobs": rows})


@admins_only
@require_POST
def cancel_job(request: HttpRequest, job_id) -> JsonResponse:
    """Stop one Job. The Recording stays; it is the work that is cancelled."""
    job = Job.objects.filter(pk=job_id).select_related("recording").first()
    if job is None:
        return JsonResponse({"error": "no such job"}, status=404)

    for run in job.runs.exclude(service_job_id=""):
        whisperx.delete(run.service_job_id)
    job.state = JobState.CANCELLED
    job.finished = timezone.now()
    job.save(update_fields=["state", "finished"])

    audit.write(
        audit.Category.JOBS,
        "Job cancelled",
        actor=request.user,
        request=request,
        affected_user=job.recording.user,
        object_type="recording",
        object_id=job.recording.pk,
        object_label=job.recording.original_filename,
        by="admin",
    )
    return JsonResponse({"cancelled": True})


# Users ------------------------------------------------------------------------


@admins_only
def users(request: HttpRequest) -> HttpResponse:
    """One row per account, and every action on it applies at once."""
    rows = []
    for person in User.objects.order_by("username"):
        theirs = Recording.objects.filter(user=person)
        size = sum(one.disk_bytes() for one in theirs)
        rows.append(
            {
                "user": person,
                "condition": lifecycle.condition(person),
                "recordings": theirs.count(),
                "gigabytes": f"{size / 1024**3:.1f}",
                "quota": (
                    f"{person.quota_gb} GB"
                    if person.quota_gb
                    else f"Default ({settings_store.get('default_quota_gb')} GB)"
                ),
                "admin_source": _admin_source(person),
                "status": person.status.title(),
                "counts": lifecycle.counts(person),
            }
        )

    return render(
        request,
        "panel/users.html",
        {**furniture(request, "panel-users"), "rows": rows},
    )


SOURCES = {"local": "Local", "group": "Admin group", "manual": "Manual"}


def _admin_source(person) -> str:
    return SOURCES.get(person.admin_source, "")


@admins_only
@require_POST
def user_action(request: HttpRequest, username: str) -> HttpResponse:
    """The Users page's actions, each applying at once with its own row."""
    person = User.objects.filter(username=username).first()
    if person is None:
        return redirect(reverse("panel-users"))

    doing = request.POST.get("action", "")

    if doing == "end-sessions":
        ended = _end_sessions(request, person)
        _tell(request, f"{person.username} was signed out ({ended} session(s)).")

    elif doing == "block":
        person.blocked_at = timezone.now()
        person.save(update_fields=["blocked_at"])
        audit.write(
            audit.Category.ACCOUNTS,
            "user blocked",
            actor=request.user,
            request=request,
            affected_user=person,
        )
        _end_sessions(request, person, cause=LoginSession.BLOCKED)
        _tell(request, f"{person.username} is blocked and signed out.")

    elif doing == "unblock":
        person.blocked_at = None
        person.save(update_fields=["blocked_at"])
        audit.write(
            audit.Category.ACCOUNTS,
            "user unblocked",
            actor=request.user,
            request=request,
            affected_user=person,
        )
        _tell(request, f"{person.username} may sign in again.")

    elif doing == "admin-flag":
        # Greyed on the page for a group-held Admin and for a Local admin,
        # and refused here too: the flag only ever adds, and taking it off
        # somebody the directory calls an Admin would do nothing.
        if person.admin_source in (None, "manual"):
            person.admin_flag = not person.admin_flag
            person.save(update_fields=["admin_flag"])
            audit.write(
                audit.Category.ACCOUNTS,
                "admin flag changed",
                actor=request.user,
                request=request,
                affected_user=person,
                now=person.admin_flag,
            )

    elif doing == "quota":
        wanted = request.POST.get("quota_gb", "").strip()
        person.quota_gb = int(wanted) if wanted.isdigit() and int(wanted) else None
        person.save(update_fields=["quota_gb"])
        audit.write(
            audit.Category.ACCOUNTS,
            "quota override set",
            actor=request.user,
            request=request,
            affected_user=person,
            gigabytes=person.quota_gb or "default",
        )

    return redirect(reverse("panel-users"))


def _end_sessions(request, person, cause=LoginSession.ADMIN_ENDED) -> int:
    """End a person's sessions, after which the Discard follows its own rules.

    This is the Phase 1 way to free somebody's space: their Workspace is
    discarded within the minute unless work is still in hand.
    """
    ended = 0
    for session in LoginSession.objects.filter(user=person, ended__isnull=True):
        session.end(cause)
        audit.write(
            audit.Category.SIGN_IN,
            "sign-out",
            actor=request.user,
            request=request,
            affected_user=person,
            login_session=session,
            cause=cause,
        )
        ended += 1
    return ended


@admins_only
@require_POST
def create_local_admin(request: HttpRequest) -> HttpResponse:
    """A Local admin, for when the directory is down."""
    username = request.POST.get("username", "").strip()
    shown_name = request.POST.get("display_name", "").strip()
    password = request.POST.get("password", "")

    if not username or not password:
        _tell(request, "A Local admin needs a username and a password.")
        return redirect(reverse("panel-users"))
    if User.objects.filter(username=username).exists():
        _tell(request, f"There is already an account called {username}.")
        return redirect(reverse("panel-users"))

    person = User.objects.create_local_admin(username, password)
    if shown_name:
        person.display_name = shown_name
        person.save(update_fields=["display_name"])
    audit.write(
        audit.Category.ACCOUNTS,
        "local admin created",
        actor=request.user,
        request=request,
        affected_user=person,
    )
    _tell(request, f"{username} can sign in as a Local admin.")
    return redirect(reverse("panel-users"))


@admins_only
@require_POST
def local_admin_action(request: HttpRequest, username: str) -> HttpResponse:
    """Change a Local admin's password, or delete one that is not the last."""
    person = User.objects.filter(username=username, is_local=True).first()
    if person is None:
        return redirect(reverse("panel-users"))

    doing = request.POST.get("action", "")

    if doing == "password":
        password = request.POST.get("password", "")
        if not password:
            _tell(request, "A password is needed.")
            return redirect(reverse("panel-users"))
        person.set_password(password)
        person.save(update_fields=["password"])
        audit.write(
            audit.Category.ACCOUNTS,
            "local admin password changed",
            actor=request.user,
            request=request,
            affected_user=person,
        )
        _tell(request, f"{person.username}'s password was changed.")

    elif doing == "delete":
        if User.objects.filter(is_local=True).count() <= 1:
            _tell(request, "The last Local admin cannot be deleted.")
            return redirect(reverse("panel-users"))
        audit.write(
            audit.Category.ACCOUNTS,
            "local admin deleted",
            actor=request.user,
            request=request,
            affected_user=person,
        )
        person.delete()
        _tell(request, f"{username} was deleted.")

    return redirect(reverse("panel-users"))


@admins_only
def workspace(request: HttpRequest, username: str) -> HttpResponse:
    """Somebody else's recordings, with the banner and the audit row.

    An Admin acts with the owner's powers here, because IT must be able to
    troubleshoot a stuck Job and recover a leaver's work. The trade is that
    every opening is written down and the screen says whose Workspace this is
    (ADR 0004).
    """
    person = User.objects.filter(username=username).first()
    if person is None:
        return redirect(reverse("panel-users"))

    audit.write(
        audit.Category.ADMIN,
        "another user's Workspace opened",
        actor=request.user,
        request=request,
        affected_user=person,
    )

    from core.pages import standing_line

    return render(
        request,
        "recordings.html",
        {
            "recordings": person.recordings.order_by("-created"),
            "standing_line": standing_line(),
            "storage_warning": "",
            "someone_elses": person,
        },
    )


# Installation -----------------------------------------------------------------


@admins_only
def installation(request: HttpRequest) -> HttpResponse:
    """The read-only environment facts, for checking; never a secret's value."""
    facts = [
        ("Address", os.environ.get("APP_HOSTNAME", "not set")),
        ("Port", os.environ.get("APP_PORT", "not set")),
        ("Bind address", os.environ.get("BIND_ADDRESS", "not set")),
        ("Allowed client networks", os.environ.get("ALLOWED_CLIENTS", "not set")),
        ("Time zone", os.environ.get("TZ", "not set")),
        ("App data folder", str(django_settings.DATA_DIR)),
        ("WhisperX service", os.environ.get("WHISPERX_URL", "not set")),
        ("WhisperX GPU", os.environ.get("WHISPERX_GPU_UUID", "not set")),
        ("Engine network", os.environ.get("ENGINE_NETWORK", "not set")),
        ("Local engine profile", os.environ.get("COMPOSE_PROFILES", "off")),
        ("Media threads per job", os.environ.get("MEDIA_THREADS_PER_JOB", "not set")),
        ("Media jobs at once", os.environ.get("MEDIA_CONCURRENT_JOBS", "not set")),
    ]

    secrets = [
        ("Django key", os.environ.get("DJANGO_SECRET_KEY_FILE", "")),
        ("Database password", os.environ.get("POSTGRES_PASSWORD_FILE", "")),
        ("WhisperX Consumer token", os.environ.get("WHISPERX_TOKEN_FILE", "")),
        ("Engine token", os.environ.get("LLM_API_TOKEN_FILE", "")),
        ("HuggingFace token", os.environ.get("HF_TOKEN_FILE", "")),
    ]

    return render(
        request,
        "panel/installation.html",
        {
            **furniture(request, "panel-installation"),
            "facts": facts,
            "secrets": [
                (name, "set" if _has_something(path) else "missing")
                for name, path in secrets
            ],
            "free_disk": uploads.as_gb(uploads.free_disk_bytes()),
        },
    )


def _has_something(path: str) -> bool:
    try:
        return bool(path) and Path(path).is_file() and Path(path).stat().st_size > 0
    except OSError:
        return False


def _tell(request, message: str) -> None:
    from django.contrib import messages

    messages.info(request, message)


# The audit log ----------------------------------------------------------------

# A page is 100 rows, newest first, as the specification fixes.
A_PAGE = 100


@admins_only
def audit_log(request: HttpRequest) -> HttpResponse:
    """The audit viewer. Opening or filtering it is not itself logged."""
    from core.audit import Category, Row

    rows = Row.objects.order_by("-at", "-id")
    asked = {
        "since": request.GET.get("since", ""),
        "until": request.GET.get("until", ""),
        "actor": request.GET.get("actor", ""),
        "affected": request.GET.get("affected", ""),
        "category": request.GET.get("category", ""),
        "event": request.GET.get("event", ""),
        "outcome": request.GET.get("outcome", ""),
        "object": request.GET.get("object", ""),
        "client": request.GET.get("client", ""),
    }

    if asked["since"]:
        rows = rows.filter(at__date__gte=asked["since"])
    if asked["until"]:
        rows = rows.filter(at__date__lte=asked["until"])
    if asked["actor"]:
        rows = rows.filter(actor_username__icontains=asked["actor"])
    if asked["affected"]:
        rows = rows.filter(affected_username__icontains=asked["affected"])
    if asked["category"]:
        rows = rows.filter(category=asked["category"])
    if asked["event"]:
        rows = rows.filter(event__icontains=asked["event"])
    if asked["outcome"]:
        rows = rows.filter(outcome=asked["outcome"])
    if asked["object"]:
        rows = rows.filter(
            models.Q(object_id__icontains=asked["object"])
            | models.Q(object_label__icontains=asked["object"])
        )
    if asked["client"]:
        rows = rows.filter(client_address=asked["client"])

    found = rows.count()
    page = max(1, int(request.GET.get("page", "1") or 1))
    start = (page - 1) * A_PAGE

    query = request.GET.copy()
    query.pop("page", None)

    return render(
        request,
        "panel/audit.html",
        {
            **furniture(request, "panel-audit"),
            "rows": rows[start : start + A_PAGE],
            "found": found,
            "page": page,
            "pages": max(1, (found + A_PAGE - 1) // A_PAGE),
            "asked": asked,
            "carried": query.urlencode(),
            "categories": [
                value
                for name, value in vars(Category).items()
                if not name.startswith("_")
            ],
        },
    )


@admins_only
@require_POST
def integrity_check(request: HttpRequest) -> JsonResponse:
    """Walk the chain, say what it found, and write that as a row of its own."""
    from core import audit as audit_log_module

    result = audit_log_module.check_integrity()
    audit.write(
        audit.Category.ADMIN,
        "Integrity check run",
        actor=request.user,
        request=request,
        outcome=(
            audit.Outcome.SUCCESS if result["unbroken"] else audit.Outcome.FAILURE
        ),
        rows=result["rows"],
        message=result["message"],
    )
    return JsonResponse(result)
