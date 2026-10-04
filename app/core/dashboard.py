"""The dashboard line (Phase 7 chapter 3): one line of pills under a case's
name for everything in the case that has a state, each a link to where it
is dealt with, absent when nothing is pending.

Drawn from the counters the pages already keep; no new table, no new
setting, no audit row.
"""

from __future__ import annotations

from django.urls import reverse

from core import (
    assistant,
    incident_assistant,
    incidents,
    retention,
    settings_store,
    sharing,
    summaries_tonight,
    vision,
)
from core.chronology import Event
from core.clips import Clip, RenderState
from core.incidents import IncidentCamera
from core.jobs import Job, JobState, Transcript

WARN = "warn"
PLAIN = ""


def _count(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def _incident_pills(where: dict, href: str, add) -> None:
    """The incident pills, for a case's incidents together (the dashboard
    line) or for one incident alone (Home's line under its case, v1.115.0):
    `where` narrows the cameras, events and memos to the case or the
    incident, and every pill links to `href`."""
    # Not synced: an incident with a camera still at the app's guess.
    unsynced = (
        IncidentCamera.objects.filter(
            placed__in=(incidents.GUESS, incidents.NOT_PLACED), **where
        )
        .values("incident")
        .distinct()
        .count()
    )
    if unsynced:
        add(
            _count(unsynced, "incident not synced", "incidents not synced")
            if "incident__case" in where
            else "not synced",
            href,
            WARN,
        )
    to_check = Event.objects.filter(proposed=False, to_check=True, **where).count()
    if to_check:
        add(_count(to_check, "event to check", "events to check"), href, WARN)
    proposals = Event.objects.filter(proposed=True, dismissed=False, **where).count()
    # Proposals wait for a person's accept or dismiss: warm, so the case
    # sits under Needs you on Home (v1.86.2, at the maintainer's word).
    if proposals:
        add(
            _count(proposals, "proposed event waiting", "proposed events waiting"),
            href,
            WARN,
        )
    # Memos being written, and memos with newer events.
    writing = incident_assistant.IncidentMemo.objects.filter(
        state__in=(incident_assistant.QUEUED, incident_assistant.RUNNING), **where
    ).count()
    if writing:
        add(_count(writing, "memo writing", "memos writing"), href)
    stale = 0
    for memo in incident_assistant.IncidentMemo.objects.filter(
        state=incident_assistant.DONE, **where
    ).select_related("incident"):
        newer = memo.incident.events.filter(proposed=False).count() - memo.events_count
        if newer > 0 or incident_assistant.stale_words(memo, memo.incident):
            stale += 1
    if stale:
        add(
            _count(stale, "memo has newer events", "memos have newer events"),
            href,
            WARN,
        )


def incident_pills(incident) -> list[dict]:
    """One incident's own pills, each a link to its page (Home, v1.115.0)."""
    out: list[dict] = []

    def add(words: str, href: str, tone: str = PLAIN) -> None:
        out.append({"words": words, "href": href, "tone": tone})

    _incident_pills({"incident": incident}, incident.url(), add)
    return out


def pills(case, role: str = "owner", user=None) -> list[dict]:
    """The line's pills in their order; each has words, a tone and a link.
    With the person looking, their own "left for you" (Phase 9 chapter 3)."""
    from core import assignments

    here = reverse("case", args=[case.pk])
    out: list[dict] = []

    def add(words: str, href: str, tone: str = PLAIN) -> None:
        out.append({"words": words, "href": href, "tone": tone})

    # Transcribing, and in line.
    live = Job.objects.filter(recording__case=case, state__in=JobState.LIVE)
    running = live.filter(state=JobState.RUNNING).count()
    queued = live.filter(state=JobState.QUEUED).count()
    if running:
        add(_count(running, "transcribing", "transcribing"), here)
    if queued:
        add(_count(queued, "in line", "in line"), here)

    # Preparing for summaries and chat, or enriched with vision now.
    preparing = Transcript.objects.filter(
        recording__case=case,
        prepare_state__in=(assistant.QUEUED, assistant.PREPARING),
    ).count()
    if preparing:
        add(_count(preparing, "preparing", "preparing"), here)

    # Tonight's vision.
    tonight = vision.waiting_tonight().filter(recording__case=case).count()
    if tonight:
        start, _ = settings_store.vision_window()
        add(f"{_count(tonight, 'video')} enriched tonight from {start}", here)
    # Tonight's summaries (Phase 9 chapter 5), in the plain tone.
    summaries = summaries_tonight.count_tonight(case)
    if summaries:
        add(f"Summaries tonight: {summaries}", here)

    if incidents.on():
        _incident_pills({"incident__case": case}, f"{here}?tab=incidents", add)

    # Clips rendering, and failed.
    if settings_store.get("clips_available"):
        clips_tab = f"{here}?tab=clips"
        rendering = Clip.objects.filter(
            recording__case=case, state=RenderState.RENDERING
        ).count()
        failed = Clip.objects.filter(
            recording__case=case, state=RenderState.FAILED
        ).count()
        if rendering:
            add(_count(rendering, "clip rendering", "clips rendering"), clips_tab)
        if failed:
            add(_count(failed, "clip failed", "clips failed"), clips_tab, WARN)

    # Assigned to and Reviewed (Phase 9 chapter 3): plain, never a warning,
    # since work waiting is not overdue.
    counts = assignments.case_counts(case)
    if counts["assigned"]:
        add(
            f"{counts['reviewed']} of {counts['recordings']} reviewed",
            f"{here}?state=reviewed",
        )
    if user is not None:
        mine = assignments.yours(case, user)
        if mine["total"]:
            add(
                f"{mine['left']} of {mine['total']} left for you",
                f"{here}?who=me&state=unreviewed",
            )

    # Shared with.
    if sharing.on() and role in ("owner", "admin"):
        shares = len(list(sharing.collaborators(case)))
        if shares:
            add(f"shared with {shares}", f"{here}#shared-with")

    # The retention clock.
    left = retention.days_left(case)
    if retention.is_warned(left):
        add(f"deletes in {_count(left, 'day')}", f"{here}#retention", WARN)
    return out
