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


def pills(case, role: str = "owner") -> list[dict]:
    """The line's pills in their order; each has words, a tone and a link."""
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

    if incidents.on():
        incidents_tab = f"{here}?tab=incidents"
        # Not synced: an incident with a camera still at the app's guess.
        unsynced = (
            IncidentCamera.objects.filter(
                incident__case=case, placed__in=(incidents.GUESS, incidents.NOT_PLACED)
            )
            .values("incident")
            .distinct()
            .count()
        )
        if unsynced:
            add(
                _count(unsynced, "incident not synced", "incidents not synced"),
                incidents_tab,
                WARN,
            )
        to_check = Event.objects.filter(
            incident__case=case, proposed=False, to_check=True
        ).count()
        if to_check:
            add(
                _count(to_check, "event to check", "events to check"),
                incidents_tab,
                WARN,
            )
        proposals = Event.objects.filter(
            incident__case=case, proposed=True, dismissed=False
        ).count()
        if proposals:
            add(
                _count(proposals, "proposed event waiting", "proposed events waiting"),
                incidents_tab,
            )
        # Memos being written, and memos with newer events.
        writing = incident_assistant.IncidentMemo.objects.filter(
            incident__case=case,
            state__in=(incident_assistant.QUEUED, incident_assistant.RUNNING),
        ).count()
        if writing:
            add(_count(writing, "memo writing", "memos writing"), incidents_tab)
        stale = 0
        for memo in incident_assistant.IncidentMemo.objects.filter(
            incident__case=case, state=incident_assistant.DONE
        ).select_related("incident"):
            newer = (
                memo.incident.events.filter(proposed=False).count() - memo.events_count
            )
            if newer > 0 or incident_assistant.stale_words(memo, memo.incident):
                stale += 1
        if stale:
            add(
                _count(stale, "memo has newer events", "memos have newer events"),
                incidents_tab,
                WARN,
            )

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
