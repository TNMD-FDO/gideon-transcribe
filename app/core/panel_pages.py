"""The panel's Overview and Server pages: Status, Queue, Users, Installation.

None of these is a settings page, so none of them goes through the tray: the
Users page's actions apply at once, each with its own confirmation and its own
audit row, and the rest only look. Viewing the Status or Queue page writes no
audit row, because looking is not an access to anybody's material.
"""

from __future__ import annotations

import contextlib
import logging
import os
from datetime import timedelta
from pathlib import Path

from django.conf import settings as django_settings
from django.db import models
from django.db.models.functions import Cast
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core import (
    audit,
    backups,
    cases,
    guides,
    lifecycle,
    mail,
    pieces,
    settings_store,
    uploads,
    whisperx,
)
from core.cases import Case
from core.jobs import Job, JobState
from core.models import LoginSession, User
from core.panel import admins_only, furniture
from core.recordings import Recording

log = logging.getLogger("transcribe.panel")


# Status -----------------------------------------------------------------------


@admins_only
def status(request: HttpRequest) -> HttpResponse:
    """One page of lines, asked for again every five seconds."""
    from core import reports

    return render(
        request,
        "panel/status.html",
        {**furniture(request, "panel-status"), "reports_new": reports.new_count()},
    )


@admins_only
def reports_page(request: HttpRequest) -> HttpResponse:
    """The Reports page (Phase 8 chapter 3): every Report, newest first, New
    before Seen before Done, with a filter and the marks."""
    from core import reports

    listed = reports.listed(request.GET.get("state", ""))
    return render(
        request,
        "panel/reports.html",
        {
            **furniture(request, "panel-reports"),
            **listed,
            "kinds": reports.KINDS,
            "state_words": reports.STATE_WORDS,
            "reports_on": reports.on(),
        },
    )


@admins_only
@require_POST
def report_mark(request: HttpRequest, report_id, state: str) -> HttpResponse:
    """Seen or Done on one Report, then back to the list as it was."""
    from django.shortcuts import get_object_or_404

    from core import reports

    report = get_object_or_404(reports.Report, pk=report_id)
    reports.mark(report, state, by=request.user, request=request)
    back = request.POST.get("back", "")
    if not back.startswith(reverse("panel-reports")):
        back = reverse("panel-reports")
    return redirect(back)


@admins_only
@require_POST
def test_engine(request: HttpRequest) -> JsonResponse:
    """Test connection: list the engine's models, then one tiny completion.

    Handed to llm-worker, because only it can reach the engine. The result
    lands on the status row a few seconds later and the page shows it on its
    next poll. Testing writes an audit row, because an Admin reaching out to
    an engine is an act, and its outcome is worth knowing later.
    """
    from core import tasks

    tasks.test_the_engine.defer()
    audit.write(
        audit.Category.ADMIN,
        "engine tested",
        actor=request.user,
        request=request,
        object_type="setting",
        object_id="engine_address",
        object_label=str(settings_store.get("engine_address") or ""),
    )
    return JsonResponse(
        {"ok": True, "says": "Testing. The answer appears here in a moment."}
    )


@admins_only
def admin_guide(request: HttpRequest) -> HttpResponse:
    """The admin guide, inside the panel, rendered from docs/admin-guide.md.

    Behind the Help link in the rail, so an Admin reads about the panel from
    inside it, and always this Release's text (ADR 0012).
    """
    return render(
        request,
        "panel/guide.html",
        {**furniture(request, "panel-help"), "guide": guides.load(guides.ADMIN)},
    )


def _refused_words() -> str:
    """The AI assistant calls refused as too long today and this week, from
    the audit log's rows (Phase 8 chapter 9)."""
    from datetime import timedelta

    from core import audit

    now = timezone.now()
    day = timezone.localtime(now).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = audit.Row.objects.filter(
        category=audit.Category.LLM, reason_class="llm_too_long"
    )
    today = rows.filter(at__gte=day).count()
    week = rows.filter(at__gte=day - timedelta(days=6)).count()
    if not week:
        return ""
    return (
        f"Readings refused as too long: {today} today, {week} in the last seven days."
    )


@admins_only
def status_lines(request: HttpRequest) -> JsonResponse:
    """What the Status page reads. Every line the specification names that
    the build has reached; the rest arrive with the features they belong to."""
    free = uploads.free_disk_bytes()
    floor = settings_store.minimum_free_disk_bytes()

    from core import engine

    return JsonResponse(
        {
            # The Pieces of this installation (v1.83.0): each on, off, not
            # installed or not answering, with the command IT runs to add it.
            "pieces": pieces.listed(),
            "services": _services(),
            "service": _whisperx(),
            # The fast lane, when the office turned it on at install.
            "fast_lane": _fast_lane(),
            # The AI assistant's line: what llm-worker's last check found,
            # and the last Test connection. Read from the status row; this
            # container is not on the engine's network and never asks it.
            "assistant": {
                **engine.status_for_the_panel(),
                # One sitting (Phase 8 chapter 9): the readings refused.
                "refused_words": _refused_words(),
            },
            # The Backup line: the last Snapshot and the last drill, from the
            # row the nightly job's record commands write.
            "backup": backups.status_for_the_panel(),
            # The Email line: not configured, or last sent and last failure,
            # with the count of people who get no mail.
            "email": mail.status_for_the_panel(),
            "storage": {
                "free": uploads.as_gb(free),
                "colour": "red"
                if free < floor
                else ("amber" if free < floor * 2 else "plain"),
                "floor": uploads.as_gb(floor),
            },
            "workspaces": _workspaces(),
            "media": _media(),
            "directory": _directory(),
            "versions": _versions(),
        }
    )


# A reachability check's answer, kept for thirty seconds in the process
# (v1.134.0): the Status page polls every five, and each poll had opened a
# socket to Caddy, the sidecar, the service and the directory. Keyed by the
# check and by the function that answers it, so a test that stands another
# function in is not told the last one's answer.
CHECK_EVERY_SECONDS = 30
_checked: dict = {}


def _remembered(key: str, ask, who=None):
    """`ask()`'s answer, asked at most once every CHECK_EVERY_SECONDS."""
    import time

    now = time.monotonic()
    held = _checked.get(key)
    if held is not None and held[2] is who and now - held[0] < CHECK_EVERY_SECONDS:
        return held[1]
    answer = ask()
    _checked[key] = (now, answer, who)
    return answer


def forget_checks() -> None:
    """Every kept answer dropped, so the next poll asks afresh."""
    _checked.clear()


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
        _remembered("caddy", lambda: _listening("caddy", "caddy", 443)),
        _remembered(
            "tusd",
            lambda: _reachable(
                "tusd", os.environ.get("TUSD_URL", "http://tusd:1080") + "/metrics"
            ),
        ),
        _database(),
        _service_health(),
        _workers(),
    ]


EXPECTED_WORKERS = 3


def _workers() -> dict:
    """The three workers from the queue's own heartbeat table (v1.132.0).

    Each worker writes a heartbeat every ten seconds and a stalled one is
    pruned when another starts. The row had read the newest "succeeded"
    event, which stopped existing when v1.130.0 began deleting successful
    jobs, so it said "not running" of a worker that was fine, and would have
    said the same of one that died.
    """
    from django.db import connection
    from django.utils import timezone

    with connection.cursor() as cursor:
        cursor.execute("SELECT last_heartbeat FROM procrastinate_workers")
        beats = [row[0] for row in cursor.fetchall() if row[0] is not None]
    now = timezone.now()
    alive = [one for one in beats if (now - one).total_seconds() < 60]
    newest = max(beats) if beats else None
    says = f"{len(alive)} of {EXPECTED_WORKERS} alive"
    if newest is not None:
        says += f", newest heartbeat {_when(newest)}"
    else:
        says += ", no heartbeat yet"
    return {
        "name": "workers",
        "state": "healthy" if len(alive) >= EXPECTED_WORKERS else "not running",
        "says": says,
    }


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
    if not pieces.transcription_installed():
        # Not a fault: the office has no card yet (v1.83.0).
        return {
            "name": "whisperx",
            "state": "not installed",
            "says": "no card yet; ./transcribe add transcription",
        }
    if _remembered("whisperx-alive", whisperx.is_alive, whisperx.is_alive):
        return {"name": "whisperx", "state": "healthy", "says": "answering"}
    return {"name": "whisperx", "state": "unreachable", "says": "no answer"}


def _a_date(text: str):
    """An ISO date from a filter, or None (v1.132.0)."""
    import datetime as dt

    try:
        return dt.date.fromisoformat(text.strip())
    except ValueError:
        return None


def _when(moment) -> str:
    """A moment in the office's time: the hour today, the day and hour otherwise."""
    local = timezone.localtime(moment)
    if local.date() == timezone.localdate():
        return f"{local:%H:%M}"
    return f"{local:%d %b %H:%M}"


def _whisperx(lane: str = "") -> dict:
    """The service's own status endpoint, rendered for an Admin."""
    if not pieces.transcription_installed():
        return {"up": False, "installed": False, "says": "not installed"}

    # Asked once per answer and kept for thirty seconds (v1.134.0): three
    # lines of the page read the same status.
    def ask() -> dict:
        try:
            return {"up": True, **whisperx.status(lane)}
        except Exception as problem:  # noqa: BLE001 - any failure is "not reachable"
            return {"up": False, "says": str(problem)}

    return _remembered(f"whisperx-status-{lane}", ask, whisperx.status)


def _fast_lane() -> dict:
    """The fast lane's line on the Status page: off, up, or not answering."""
    if not whisperx.fast_lane_configured():
        return {"configured": False}
    return {"configured": True, **_whisperx(whisperx.FAST)}


def _workspaces() -> dict:
    from core import retention
    from core.recordings import summed_disk_bytes

    # Who is open and who is busy, for everyone at once (v1.134.0): the page
    # had asked four questions of each person with a recording.
    people = set(
        Recording.objects.order_by().values_list("user_id", flat=True).distinct()
    )
    open_now = len(
        people
        & set(
            LoginSession.objects.filter(ended__isnull=True)
            .order_by()
            .values_list("user_id", flat=True)
            .distinct()
        )
    )
    busy = len(people & _busy_people())

    # The session folder's size from the kept figures, never a walk
    # (v1.134.0): every recording in no case.
    size = summed_disk_bytes(Recording.objects.filter(case__isnull=True))
    # The panel chapter's Cases line: "Cases: N, X GB; M expiring; K in the
    # recycle bin, Y GB". The live ones and the binned ones are counted apart,
    # because the bin is disk an owner can free at once.
    live = Case.objects.filter(deleted_on__isnull=True)
    binned = Case.objects.filter(deleted_on__isnull=False)
    cases_size = _cases_disk_bytes(live)
    binned_size = _cases_disk_bytes(binned)
    expiring = sum(1 for one in live if retention.is_warned(retention.days_left(one)))
    since = cases.off_since()
    return {
        "open": open_now,
        "busy": busy,
        "gigabytes": f"{size / 1024**3:.1f}",
        "cases": live.count(),
        "cases_gigabytes": f"{cases_size / 1024**3:.1f}",
        "expiring": expiring,
        "binned": binned.count(),
        "binned_gigabytes": f"{binned_size / 1024**3:.1f}",
        # Kept while Folder management is off, so IT can see what is parked
        # and for how long it has been out of reach.
        "cases_off_since": f"{since:%d %B %Y}" if since else "",
    }


def _busy_people() -> set:
    """The ids of everyone whose Workspace is busy, in three grouped
    queries: lifecycle.is_busy's three questions, asked of everyone."""
    from core.recordings import MediaState

    workspace = Recording.objects.filter(case__isnull=True, is_dictation=False)
    found = set(
        workspace.filter(media_state__in=lifecycle.BUSY_MEDIA)
        .order_by()
        .values_list("user_id", flat=True)
        .distinct()
    )
    found |= set(
        Job.objects.filter(
            recording__case__isnull=True,
            recording__is_dictation=False,
            state__in=JobState.LIVE,
        )
        .order_by()
        .values_list("recording__user_id", flat=True)
        .distinct()
    )
    found |= set(
        workspace.filter(media_state=MediaState.READY, jobs__isnull=True)
        .order_by()
        .values_list("user_id", flat=True)
        .distinct()
    )
    return found


def _cases_disk_bytes(these) -> int:
    """These cases' recordings' kept sizes and their documents', in three
    queries for all of them (v1.134.0)."""
    from core.documents import Document
    from core.recordings import summed_disk_bytes

    recordings = summed_disk_bytes(Recording.objects.filter(case__in=these))
    documents = Document.objects.filter(case__in=these).aggregate(
        total=models.Sum("size_bytes")
    )["total"]
    return recordings + (documents or 0)


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


def _directory() -> dict:
    """Whether the directory answers, without asking it anything about anybody.

    A bind and nothing more: the four checks are a button, because they read
    two groups and resolve members and have no business running every five
    seconds.
    """
    from core import audit, directory

    if not directory.is_on():
        return {"on": False, "says": "switched off: local admins only"}

    def bind() -> str:
        """ "" when the bind works, else what went wrong."""
        try:
            held = directory.connect()
        except directory.Unreachable as problem:
            return str(problem) or "unreachable"
        with contextlib.suppress(Exception):
            held.unbind_s()
        return ""

    problem = _remembered("directory", bind, directory.connect)
    if problem:
        return {"on": True, "reachable": False, "says": problem}

    last = (
        audit.Row.objects.filter(event__startswith="Directory check")
        .order_by("-at")
        .first()
    )
    return {
        "on": True,
        "reachable": True,
        "says": "reachable",
        "last_check": (
            f"{timezone.localtime(last.at):%d %b %H:%M} {last.event.lower()}, "
            f"{last.outcome}"
            if last
            else "no check has run yet"
        ),
    }


def _versions() -> dict:
    from django.db.migrations.recorder import MigrationRecorder

    last = (
        MigrationRecorder.Migration.objects.filter(app="core").order_by("-id").first()
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
    from django.db.models import Prefetch

    from core import pages
    from core.jobs import Run

    rows = []
    # The Runs with their Sides in one query for the hundred Jobs (v1.134.0),
    # and the step read from them: the poll had asked three per Job.
    for job in (
        Job.objects.select_related("recording", "recording__user")
        .prefetch_related(
            Prefetch(
                "runs", Run.objects.select_related("side").order_by("side__number")
            )
        )
        .order_by("-created")[:100]
    ):
        run = pages._first_run(job)
        rows.append(
            {
                "id": str(job.pk),
                "user": job.recording.user.shown_name,
                "title": job.recording.title,
                "batch": str(job.batch_id)[:8],
                "started": job.created.isoformat(),
                "minutes": round((job.recording.duration_seconds or 0) / 60, 1),
                "state": job.state,
                "step": pages.step_of(job),
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
        whisperx.delete(run.service_job_id, run.lane)
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


def _reassign(person, to_whom, request) -> int:
    """Give every Case one person owns to another, and say how many.

    The audit row names the old owner as the affected user and the new one in
    its details, because the person losing the Case is the one the row is
    about.
    """
    moved = 0
    from core import mail, retention

    for case in list(Case.objects.filter(owner=person)):
        case.owner = to_whom
        case.save(update_fields=["owner"])
        # "Case handed to you", one per Case, naming the Admin who did it.
        mail.case_handed(case, request.user, to_whom, retention.days_left(case))
        audit.write(
            cases.CATEGORY,
            "case reassigned",
            actor=request.user,
            affected_user=person,
            object_type="case",
            object_id=case.pk,
            object_label=case.name,
            request=request,
            to=to_whom.username,
        )
        moved += 1
    return moved


# Users ------------------------------------------------------------------------


@admins_only
def users(request: HttpRequest) -> HttpResponse:
    """One row per account, and every action on it applies at once."""
    rows = []
    # The one filter: people without an Email address, who get no mail and
    # are fixed in the directory, never here.
    no_email = bool(request.GET.get("no_email"))
    people = User.objects.order_by("username")
    if no_email:
        people = people.filter(email="")
    # Everyone's figures in a few grouped queries (v1.134.0): the page had
    # walked each person's folders and asked a handful of questions per row.
    figures = _people_figures()
    for person in people:
        mine = figures["workspace"].get(person.pk, (0, 0))
        theirs = figures["cases"].get(person.pk, (0, 0))
        cases_size = theirs[1] + figures["documents"].get(person.pk, 0)
        rows.append(
            {
                "user": person,
                "condition": lifecycle.condition(person),
                "recordings": mine[0],
                # Reads "3 in session, 41 in cases". The Cases half is kept
                # even while Folder management is off, so IT can see what is
                # parked.
                "in_session": mine[0],
                "in_cases": theirs[0],
                "cases_gigabytes": f"{cases_size / 1024**3:.1f}",
                "gigabytes": f"{mine[1] / 1024**3:.1f}",
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

    from core import mail, units

    return render(
        request,
        "panel/users.html",
        {
            **furniture(request, "panel-users"),
            "rows": rows,
            "no_email": no_email,
            "without_email": mail.people_without_email(),
            # The unit's voice book (v1.146.0): the Unit column's picker.
            "units": units.names(),
        },
    )


def _people_figures() -> dict:
    """Every person's recordings in no case (how many, their kept bytes) by
    user id, the recordings in the cases they own by owner id, and their
    cases' documents' bytes, in four queries for the whole page."""
    from core.documents import Document

    for one in Recording.objects.filter(on_disk_bytes__isnull=True):
        one.measure_disk()
    workspace = {
        row["user_id"]: (row["n"], row["total"] or 0)
        for row in Recording.objects.filter(case__isnull=True)
        .order_by()
        .values("user_id")
        .annotate(n=models.Count("id"), total=models.Sum("on_disk_bytes"))
    }
    in_cases = {
        row["case__owner_id"]: (row["n"], row["total"] or 0)
        for row in Recording.objects.filter(case__isnull=False)
        .order_by()
        .values("case__owner_id")
        .annotate(n=models.Count("id"), total=models.Sum("on_disk_bytes"))
    }
    documents = {
        row["case__owner_id"]: row["total"] or 0
        for row in Document.objects.order_by()
        .values("case__owner_id")
        .annotate(total=models.Sum("size_bytes"))
    }
    return {"workspace": workspace, "cases": in_cases, "documents": documents}


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

    elif doing == "unit":
        # A Local admin's unit, by hand (v1.146.0); a directory account's is
        # the directory's to decide.
        from core import units

        try:
            units.set_by_hand(
                person, request.POST.get("unit", ""), by=request.user, request=request
            )
            _tell(
                request,
                f"{person.username} is in the {person.unit} unit."
                if person.unit
                else f"{person.username} is in no unit.",
            )
        except ValueError as refused:
            _tell(request, str(refused))

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

    elif doing == "reassign":
        # Every Case this person owns, given to one named colleague. Nothing
        # else changes: the Retention clock is not started over, and the new
        # owner inherits the days left.
        if not cases.folder_management_on():
            _tell(request, "Cases are turned off.")
        else:
            to_whom = User.objects.filter(
                username=request.POST.get("to", "").strip()
            ).first()
            if to_whom is None:
                _tell(request, "No account by that name.")
            else:
                moved = _reassign(person, to_whom, request)
                _tell(
                    request,
                    f"{moved} case{'' if moved == 1 else 's'} now belong to "
                    f"{to_whom.username}.",
                )

    elif doing == "delete-data":
        if not cases.folder_management_on():
            _tell(request, "Cases are turned off.")
        else:
            # A leaver's binned Cases go too, as the Retention chapter fixes,
            # with an Admin as the cause of the wipe.
            gone = 0
            for case in list(Case.objects.filter(owner=person)):
                if case.is_binned:
                    cases.wipe(
                        case,
                        cause=cases.WIPED_BY_ADMIN,
                        actor=request.user,
                        request=request,
                    )
                else:
                    cases.delete(case, actor=request.user, request=request)
                gone += 1
            _tell(
                request,
                f"{gone} case{'' if gone == 1 else 's'} of "
                f"{person.username}'s deleted. This cannot be undone.",
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
    email = request.POST.get("email", "").strip()[:254]

    if not username or not password:
        _tell(request, "A Local admin needs a username and a password.")
        return redirect(reverse("panel-users"))
    if User.objects.filter(username=username).exists():
        _tell(request, f"There is already an account called {username}.")
        return redirect(reverse("panel-users"))

    person = User.objects.create_local_admin(username, password)
    if shown_name:
        person.display_name = shown_name
    # A Local admin has no directory record, so their Email address is the
    # one typed address in the app; optional, and none by default.
    person.email = email
    person.save(update_fields=["display_name", "email"])
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

    elif doing == "email":
        address = request.POST.get("email", "").strip()[:254]
        if address != person.email:
            person.email = address
            person.save(update_fields=["email"])
            audit.email_address_updated(person, address, actor=request.user)
        _tell(
            request,
            f"{person.username}'s email address is "
            f"{'now ' + address if address else 'removed'}.",
        )

    elif doing == "delete":
        if User.objects.filter(is_local=True).count() <= 1:
            _tell(request, "The last Local admin cannot be deleted.")
            return redirect(reverse("panel-users"))
        # Not while they own a case or hold a recording (v1.131.0): the delete
        # had crashed on a case, and taken a Workspace silently.
        from core.cases import Case
        from core.recordings import Recording

        owned = Case.objects.filter(owner=person).count()
        held = Recording.objects.filter(user=person).count()
        if owned or held:
            _tell(
                request,
                f"{username} owns {owned} case(s) and {held} recording(s). "
                "Transfer the cases and delete or move the recordings first.",
            )
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

    from core.pages import _with_their_state, batch_groups, standing_line

    # The Workspace: what is in no case. The table is grouped by batch
    # (Phase 8 chapter 13), so the groups come too; without them, from
    # v1.86.0 to v1.86.1, this view showed the headings and no rows.
    rows = _with_their_state(
        person.recordings.filter(case__isnull=True).order_by("-created")
    )
    return render(
        request,
        "recordings.html",
        {
            "recordings": rows,
            "groups": batch_groups(rows),
            "standing_line": standing_line(),
            "someone_elses": person,
        },
    )


# Installation -----------------------------------------------------------------


def _the_services_gpu() -> str:
    """Which card the WhisperX service reserved, asked of the service itself.

    It is set in the service's own .env, which this container does not read
    and should not: the service is a separate thing with its own settings.
    """
    try:
        told = whisperx.status()
    except Exception:  # noqa: BLE001 - a service that will not answer says so
        return "the service did not answer"
    gpu = (told or {}).get("gpu") or {}
    return gpu.get("uuid") or gpu.get("name") or "the service did not say"


@admins_only
@require_POST
def test_mail(request: HttpRequest) -> HttpResponse:
    """Test message: one message through the relay, now, and the relay's reply.

    To the signed-in Admin, or to the Operator address when they have no
    Email address. Sent within the request rather than through the queue, so
    the reply is on the page when it comes back; one try, no retries.
    """
    to_address = request.user.email or mail.operator_email()
    if not mail.configured() or not to_address:
        request.session["email_said"] = (
            "Nothing was sent: mail is not configured, or there is nobody to send to."
        )
        return redirect(reverse("panel-settings", args=[settings_store.EMAIL]))
    try:
        reply = mail.send_test(to_address, actor=request.user, request=request)
    except mail.MailFailure as why:
        request.session["email_said"] = (
            f"The relay would not take the message ({why.reason_class}): "
            f"{why.detail or 'no detail'}."
        )
    else:
        request.session["email_said"] = f"Sent to {to_address}. The relay said: {reply}"
    return redirect(reverse("panel-settings", args=[settings_store.EMAIL]))


@admins_only
def installation(request: HttpRequest) -> HttpResponse:
    """The read-only environment facts, for checking; never a secret's value."""
    # The names here are the specification's own. Four of them were not:
    # this page asked for APP_PORT, ALLOWED_CLIENTS, ENGINE_NETWORK and
    # HF_TOKEN_FILE, and no such keys exist, so the one page an Admin opens to
    # check an installation answered "not set" to half of it however carefully
    # the office had filled in .env.
    facts = [
        ("Address", os.environ.get("APP_HOSTNAME", "not set")),
        ("Port", os.environ.get("HTTPS_PORT", "not set")),
        ("Bind address", os.environ.get("BIND_ADDRESS", "not set")),
        (
            "Allowed client networks",
            os.environ.get("ALLOWED_CLIENT_CIDRS", "not set"),
        ),
        ("Time zone", os.environ.get("TZ", "not set")),
        ("App data folder", str(django_settings.DATA_DIR)),
        ("WhisperX service", os.environ.get("WHISPERX_URL", "not set")),
        ("Engine network", os.environ.get("LLM_NETWORK", "not set")),
        (
            "Compose profiles",
            os.environ.get("COMPOSE_PROFILES") or "none",
        ),
        ("Media threads per job", os.environ.get("MEDIA_THREADS_PER_JOB", "not set")),
        ("Media jobs at once", os.environ.get("MEDIA_CONCURRENT_JOBS", "not set")),
    ]

    # The service's own facts, which are in the service's .env and not this
    # app's, so they are asked of the service rather than guessed at from an
    # environment this container cannot see. The HuggingFace token is the
    # service's too, and this app has never had it.
    facts += [
        ("WhisperX GPU", _the_services_gpu()),
    ]
    # Where this server sits on the ladder (v1.92.0): from the card's memory
    # the install recorded, never asked of the card here.
    fit = pieces.fitment(pieces.card_memory_gb(), engine_on_lan=pieces._engine_on_lan())
    facts += [("Card memory", f"{fit['gb']} GB" if fit["gb"] else "no card recorded")]
    # The Backup's read-only rows: the target as account and host, the
    # schedule, the keep rule, and whether its two secrets are set.
    facts += backups.installation_rows()
    # The mail keys, read-only; the password is a secret shown set or missing.
    facts += [
        ("Mail relay", mail.host() or "not set (no mail)"),
        ("Mail relay port", os.environ.get("SMTP_PORT", "25")),
        ("Mail TLS", mail.starttls_mode()),
        ("Mail sign-in name", mail.user() or "none"),
        ("Mail sender", mail.mail_from() or "not set"),
        ("Operator address (mail)", mail.operator_email() or "not set"),
    ]

    secrets = [
        ("Django key", os.environ.get("DJANGO_SECRET_KEY_FILE", "")),
        ("Database password", os.environ.get("POSTGRES_PASSWORD_FILE", "")),
        ("WhisperX Consumer token", os.environ.get("WHISPERX_TOKEN_FILE", "")),
        ("Engine token", os.environ.get("LLM_API_TOKEN_FILE", "")),
        ("Mail relay password", os.environ.get("SMTP_PASSWORD_FILE", "")),
    ]

    return render(
        request,
        "panel/installation.html",
        {
            **furniture(request, "panel-installation"),
            "facts": facts,
            "fit": fit,
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
# How many rows the audit viewer counts before it says "more than".
COUNTED_MOST = 10_000


def _local_midnight(day):
    """The start of that day in the office's own zone, as an aware moment."""
    import datetime as dt

    return timezone.make_aware(dt.datetime.combine(day, dt.time.min))


def group_divides(rows) -> list[dict]:
    """The page's rows as entries, a Divide's rows folded under one line
    (Phase 9 chapter 3, v1.122.0): "recording assigned" rows that follow one
    another and carry the same divide key become one entry, "Recordings
    divided among 4 people: 240", opened to the rows. Every other row is an
    entry of its own. Nothing is dropped and nothing is rewritten: the rows
    are the record, the line is how the page reads them."""
    entries: list[dict] = []
    for row in rows:
        details = row.details or {}
        key = details.get("divide") if row.event == "recording assigned" else None
        last = entries[-1] if entries else None
        if key and last is not None and last.get("divide") == key:
            last["rows"].append(row)
            last["people"].add(details.get("to", ""))
            continue
        if key:
            entries.append(
                {
                    "divide": key,
                    "first": row,
                    "rows": [row],
                    "people": {details.get("to", "")},
                }
            )
        else:
            entries.append({"row": row})
    for entry in entries:
        if "divide" in entry:
            count, people = len(entry["rows"]), len(entry["people"])
            who = "1 person" if people == 1 else f"{people} people"
            entry["line"] = f"Recordings divided among {who}: {count}"
    return entries


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

    # A date typed or pasted in another form is dropped rather than crashing
    # the page (v1.132.0).
    for key in ("since", "until"):
        if asked[key] and _a_date(asked[key]) is None:
            asked[key] = ""
    # Filtered on moments, not on dates (v1.134.0): a date comparison made
    # PostgreSQL cast every row's moment to the office's day before it
    # could compare, past the index; local midnight of since to local
    # midnight after until compares the column as it is.
    if asked["since"]:
        rows = rows.filter(at__gte=_local_midnight(_a_date(asked["since"])))
    if asked["until"]:
        rows = rows.filter(
            at__lt=_local_midnight(_a_date(asked["until"]) + timedelta(days=1))
        )
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
        # The column is an inet, and anything that is not a whole address
        # would raise rather than simply match nothing. Compared as text, a
        # partial address finds a subnet, which is what somebody typing one
        # wants.
        rows = rows.annotate(
            client_text=Cast("client_address", models.CharField())
        ).filter(client_text__icontains=asked["client"])

    # Counted up to the first ten thousand and one (v1.134.0): the page says
    # "more than 10,000 rows" past that rather than count a year's rows for
    # every page turn, and the deepest page offered is the last counted.
    found = len(rows.values_list("pk", flat=True)[: COUNTED_MOST + 1])
    more = found > COUNTED_MOST
    found = min(found, COUNTED_MOST)
    pages = max(1, (found + A_PAGE - 1) // A_PAGE)
    try:
        page = max(1, min(pages, int(request.GET.get("page", "1") or 1)))
    except ValueError:
        page = 1
    start = (page - 1) * A_PAGE

    query = request.GET.copy()
    query.pop("page", None)

    return render(
        request,
        "panel/audit.html",
        {
            **furniture(request, "panel-audit"),
            "entries": group_divides(rows[start : start + A_PAGE]),
            "found": found,
            # Past the counted rows, "more than 10,000"; the template prints
            # the figure as a number, so the words wait on the template.
            "more_than_counted": more,
            # Not "page": the nav uses that word for which page of the app
            # this is.
            "page_number": page,
            "pages": pages,
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
    """Start the walk of the chain on the worker (v1.134.0) and say so; the
    result lands in the audit log as a row of its own, in this Admin's name.
    The walk used to run inside the request, which read the whole log."""
    from core import tasks

    tasks.check_audit_integrity.defer(by_id=str(request.user.pk))
    return JsonResponse(
        {
            "ok": True,
            "queued": True,
            "says": (
                "The check is running; its result lands in the audit log "
                "within a few minutes."
            ),
        }
    )


# The directory ----------------------------------------------------------------


@admins_only
@require_POST
def test_directory(request: HttpRequest) -> JsonResponse:
    """The four checks, from the Status page or the Sign-in and directory page."""
    from core import directory

    results = directory.test_connection()
    failed = [one for one in results if not one["ok"]]
    audit.write(
        audit.Category.ADMIN,
        "Directory tested",
        actor=request.user,
        request=request,
        outcome=audit.Outcome.SUCCESS if not failed else audit.Outcome.FAILURE,
        reason_class="" if not failed else "directory_unreachable",
        checks=len(results),
        failed=len(failed),
    )
    return JsonResponse({"checks": results, "ok": not failed})


@admins_only
@require_POST
def check_directory_now(request: HttpRequest) -> JsonResponse:
    """Run the nightly check now, and say what it did."""
    from core import directory

    return JsonResponse(directory.check_accounts(actor=request.user))
