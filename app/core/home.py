"""Home (Phase 8 chapter 13): where sign-in lands, and what needs the person.

One page in a fixed order: the greeting; the notices; Ready to download (a
batch of this session that has finished, with its download, so the
transcripts are never only on the batch page); Needs you (the cases with
something to settle); Running now; This session (the recordings not in a
case, with the keep-or-lose line said once); Recent cases (every case). A
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


def ready_batches(user) -> list[dict]:
    """The finished batches of this session with at least one transcript,
    each with its download, until Done with these takes it."""
    out = []
    for batch in session_batches(user):
        if not batch.is_finished:
            continue
        done = batch.recordings.filter(
            case__isnull=True, transcript__isnull=False
        ).count()
        if not done:
            continue
        failed = (
            batch.recordings.filter(case__isnull=True)
            .filter(media_state__in=(MediaState.FAILED, MediaState.REJECTED))
            .count()
        )
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
    return out


def ready_count(user) -> int:
    """How many batches wait for their download, for the rail's Home item."""
    return len(ready_batches(user))


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


def case_rows(user) -> tuple[list[dict], list[dict]]:
    """Every case the person can open, newest activity first, each with its
    dashboard pills; and, apart, the ones with something to settle (a pill
    in the warning tone)."""
    from core import case_pages

    rows, needs = [], []
    mine = cases.cases_for(user).select_related("owner").order_by("-last_activity")
    for case in mine:
        row = case_pages._as_row(case, user)
        row["pills"] = dashboard.pills(case, case.role_of(user))
        rows.append(row)
        warns = [one for one in row["pills"] if one["tone"] == dashboard.WARN]
        if warns:
            needs.append({**row, "pills": warns})
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
            "ready": ready_batches(user),
            "needs": needs,
            "running": running_now(user),
            "session": session,
            "keep_line": keep_line(),
            "recorded_here": recorded_here,
            "cases_on": cases_on,
            "cases_rows": rows,
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
