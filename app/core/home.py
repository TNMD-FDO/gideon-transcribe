"""Home (Phase 8 chapter 13): where sign-in lands, and what needs the person.

One page in a fixed order: the greeting; the notices; Ready to download (a
batch of this session that has finished, with its download, so the
transcripts are never only on the batch page); then, side by side on a wide
window (v1.115.0, the maintainer's pick after the October walk), Cases (the
ones with something to settle first under Needs you, then every case by last
activity, each case's incidents on a line under its row with their own
pills) and This session (Running now as its first line, the recordings not
in a case with the keep-or-lose line said once, the clips line last). A
section with nothing in it is not drawn. Nothing here is only a door: the
rail's two actions are the doors, on every page.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse

from core import (
    assistant,
    cases,
    dashboard,
    lifecycle,
    pieces,
    quota_raises,
    settings_store,
    uploads,
    vision,
    whisperx,
)
from core.jobs import Job, JobState, Transcript
from core.recordings import Batch, MediaState


def here_case_for(user, case):
    """The Case the rail's actions carry, when the person is inside one of
    their own: the owner or a collaborator. An Admin looking into somebody's
    case gets none, since the upload and record pages would refuse it."""
    if case is None:
        return None
    if case.role_of(user) in ("owner", "collaborator"):
        return case
    return None


def session_batches(user):
    """This person's batches whose recordings are still theirs and in no
    case: what This session and Ready to download are drawn from."""
    ids = lifecycle.in_the_workspace(user).values_list("batch_id", flat=True).distinct()
    return Batch.objects.filter(pk__in=list(ids), is_live=False).order_by("-created")


def session_state(user) -> dict:
    """This session's batches in one query: "ready", the finished ones with
    at least one transcript, each with its download until Done with these
    takes it; and "running", the batch in hand with its done and total
    counts (v1.173.0, for the rail's Bulk transcription pill), or None."""
    from django.db.models import Count, Q

    from core.jobs import JobState

    out = []
    running = None
    # Every batch's four counts in one query (v1.124.0): each had asked four
    # questions of its own, and an Admin's Home ran 39 batches through them.
    batches = session_batches(user).annotate(
        unfinished=Count(
            "recordings",
            filter=Q(recordings__media_state__in=MediaState.UNFINISHED),
            distinct=True,
        ),
        live=Count("jobs", filter=Q(jobs__state__in=JobState.LIVE), distinct=True),
        total=Count("recordings", distinct=True),
        done_count=Count(
            "recordings",
            filter=Q(
                recordings__case__isnull=True, recordings__transcript__isnull=False
            ),
            distinct=True,
        ),
        failed_count=Count(
            "recordings",
            filter=Q(
                recordings__case__isnull=True,
                recordings__media_state__in=(MediaState.FAILED, MediaState.REJECTED),
            ),
            distinct=True,
        ),
    )
    for batch in batches:
        if batch.unfinished or batch.live:
            if running is None:
                running = {"done": batch.done_count, "total": batch.total}
            continue
        done = batch.done_count
        if not done:
            continue
        failed = batch.failed_count
        out.append(
            {
                "batch": batch,
                "done": done,
                "failed": failed,
                "when": batch.created,
                "download": reverse("batch-download", args=[batch.pk]),
                "url": reverse("batch", args=[batch.pk]),
            }
        )
    return {"ready": out, "running": running}


def ready_batches(user) -> list[dict]:
    """The finished batches of this session with at least one transcript,
    each with its download, until Done with these takes it."""
    return session_state(user)["ready"]


def ready_count(user) -> int:
    """How many batches wait for their download, for the rail's Home item."""
    return len(ready_batches(user))


def bulk_pill(state: dict) -> dict | None:
    """The rail's Bulk transcription pill (v1.173.0), from session_state:
    where this session's batch stands while one runs ("2 of 5"), else
    "Ready" while any waits for its download; nothing otherwise."""
    running = state.get("running")
    if running:
        return {"words": f"{running['done']} of {running['total']}", "tone": ""}
    if state.get("ready"):
        return {"words": "Ready", "tone": "ok"}
    return None


def running_now(user) -> list[dict]:
    """One line of pills for the person's own work in hand: the unfinished
    batch, a Process again, transcripts preparing, tonight's vision; in the
    dashboard line's shape (words, href, tone)."""
    out: list[dict] = []
    unfinished = Batch.unfinished_for(user)
    if unfinished is not None:
        total = unfinished.recordings.count()
        live = Job.objects.filter(batch=unfinished, state__in=JobState.LIVE).count()
        done = unfinished.recordings.filter(transcript__isnull=False).count()
        words = (
            f"{done} of {total} transcribed"
            if total and done
            else dashboard._count(live or total, "transcribing", "transcribing")
        )
        out.append(
            {
                "words": words,
                "href": reverse("batch", args=[unfinished.pk]),
                "tone": dashboard.PLAIN,
            }
        )
    again = Job.objects.filter(
        recording__user=user, state__in=JobState.LIVE, batch__is_reprocessing=True
    ).count()
    if again:
        out.append(
            {
                "words": dashboard._count(
                    again, "processing again", "processing again"
                ),
                "href": reverse("recordings"),
                "tone": dashboard.PLAIN,
            }
        )
    preparing = Transcript.objects.filter(
        recording__user=user,
        prepare_state__in=(assistant.QUEUED, assistant.PREPARING),
    ).count()
    if preparing:
        out.append(
            {
                "words": dashboard._count(preparing, "preparing", "preparing"),
                "href": reverse("recordings"),
                "tone": dashboard.PLAIN,
            }
        )
    if settings_store.get("folder_management"):
        mine = cases.cases_for(user)
        tonight = vision.waiting_tonight().filter(recording__case__in=mine).count()
        if tonight:
            start, _ = settings_store.vision_window()
            out.append(
                {
                    "words": (
                        dashboard._count(tonight, "video")
                        + f" enriched tonight from {start}"
                    ),
                    "href": reverse("cases"),
                    "tone": dashboard.PLAIN,
                }
            )
    return out


def incident_lines(case, counts: dict, incidents_of: list, cameras: dict) -> list[dict]:
    """The case's incidents for the line under its row on Home (v1.115.0):
    each a link to its page with its cameras, where its cameras stand on
    the clock, and its own pills. Everything from what case_rows loaded for
    every case at once (v1.134.0): nothing is asked of the database here."""
    from core import incidents

    if not incidents.on():
        return []
    out = []
    by_incident = counts.get("by_incident", {})
    for incident in incidents_of:
        own = cameras.get(incident.pk, [])
        placed, tone = incidents.placed_words(incident, own)
        out.append(
            {
                "incident": incident,
                "url": incident.url(),
                "cameras": len(own),
                "placed": placed,
                "tone": tone,
                "pills": dashboard.incident_pills(
                    incident,
                    by_incident.get(incident.pk, dict(dashboard.NO_INCIDENT_COUNTS)),
                ),
            }
        )
    return out


def _incidents_in(cases_shown) -> tuple[dict, dict]:
    """Every incident of these cases by case id, and every camera by incident
    id, in two queries (v1.134.0): what the lines under the rows read."""
    from core import incidents

    if not incidents.on() or not cases_shown:
        return {}, {}
    ids = [one.pk for one in cases_shown]
    incidents_of: dict = {}
    for incident in incidents.Incident.objects.filter(case_id__in=ids).select_related(
        "case"
    ):
        incidents_of.setdefault(incident.case_id, []).append(incident)
    cameras: dict = {}
    for camera in incidents.IncidentCamera.objects.filter(incident__case_id__in=ids):
        cameras.setdefault(camera.incident_id, []).append(camera)
    return incidents_of, cameras


def case_rows(user) -> tuple[list[dict], list[dict]]:
    """Every case the person can open, newest activity first, each with its
    dashboard pills and its incidents; and, apart, the ones with something
    to settle (a pill in the warning tone on the case or on one of its
    incidents). The incidents' own pills sit on the incident's line, so the
    case's row keeps only the pills that are the case's. The counts for all
    the cases are asked for at once (v1.134.0): Home had asked about thirty
    questions of each case, and twenty cases made six hundred."""
    from core import case_pages, sharing

    rows, needs = [], []
    mine = list(
        cases.cases_for(user).select_related("owner").order_by("-last_activity")
    )
    counts = dashboard.counts_for(mine, user)
    shares = case_pages.shares_of(user, mine)
    incidents_of, cameras = _incidents_in(mine)
    sharing_on = sharing.on()
    for case in mine:
        row = case_pages._as_row(case, user, counts.get(case.pk), shares.get(case.pk))
        incidents_tab = reverse("case", args=[case.pk]) + "?tab=incidents"
        row["incidents"] = incident_lines(
            case, counts.get(case.pk, {}), incidents_of.get(case.pk, []), cameras
        )
        # The person's role from what is loaded: cases_for gave only their
        # own and the ones shared with them, so a case not theirs is shared.
        if case.owner_id == user.pk:
            role = "owner"
        elif sharing_on and case.pk in shares:
            role = "collaborator"
        else:
            role = case.role_of(user)
        row["pills"] = [
            one
            for one in dashboard.pills(case, role, user, counts.get(case.pk))
            if not (row["incidents"] and one["href"] == incidents_tab)
        ]
        rows.append(row)
        warns = [one for one in row["pills"] if one["tone"] == dashboard.WARN] + [
            one
            for line in row["incidents"]
            for one in line["pills"]
            if one["tone"] == dashboard.WARN
        ]
        if warns:
            needs.append(row)
    return rows, needs


@login_required
def home(request: HttpRequest) -> HttpResponse:
    from core import clip_pages, dictation, pages
    from core.clips import Clip, RenderState

    user = request.user
    cases_on = bool(settings_store.get("folder_management"))
    rows, needs = case_rows(user) if cases_on else ([], [])
    session = pages._with_their_state(
        lifecycle.in_the_workspace(user).order_by("-created")
    )
    recorded_here = dictation.mine(user).count() if dictation.on() else 0
    clips = clip_pages.my_clips(user) if settings_store.get("clips_available") else []
    rendering = (
        Clip.objects.filter(recording__user=user, state=RenderState.RENDERING).count()
        if clips
        else 0
    )
    return render(
        request,
        "home.html",
        {
            "page": "home",
            "greeting": pages.greeting(),
            "service_is_up": whisperx.is_alive(),
            "transcription_installed": pieces.transcription_installed(),
            "storage_warning": uploads.storage_warning(user),
            "quota_notice": quota_raises.notice(user),
            "ready": ready_batches(user),
            "needs": needs,
            "running": running_now(user),
            "session": session,
            "keep_line": keep_line(),
            "recorded_here": recorded_here,
            "cases_on": cases_on,
            "cases_rows": rows,
            # The rest, by last activity: the cases not under Needs you.
            "cases_rest": [row for row in rows if row not in needs],
            "cases_line": pages._cases_line(user) if cases_on else "",
            "clips_count": len(clips),
            "clips_rendering": rendering,
        },
    )


# What This session says, once, plainly: the Workspace's rule.
KEEP_LINE = (
    "These stay until you sign out, or {hours} hours after you stop working. "
    "Put a recording in a case to keep it."
)
KEEP_LINE_NO_CASES = (
    "These stay until you sign out, or {hours} hours after you stop working. "
    "Export anything you want to keep."
)


def keep_line() -> str:
    hours = settings_store.get("idle_timeout_minutes") / 60
    words = KEEP_LINE if settings_store.get("folder_management") else KEEP_LINE_NO_CASES
    return words.format(hours=f"{hours:g}")
