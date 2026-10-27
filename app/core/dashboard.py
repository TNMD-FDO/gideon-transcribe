"""The dashboard line (Phase 7 chapter 3): one line of pills under a case's
name for everything in the case that has a state, each a link to where it
is dealt with, absent when nothing is pending.

Drawn from the counters the pages already keep; no new table, no new
setting, no audit row. Every count is asked for all the cases a page shows
at once, grouped by case (v1.134.0): Home had asked about fourteen questions
of each of its cases, and an office's Home showed twenty.
"""

from __future__ import annotations

from django.db.models import Count, Q, Sum
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
from core.incidents import Incident, IncidentCamera
from core.jobs import Job, JobState, Transcript

WARN = "warn"
PLAIN = ""

# One incident's counts when nothing has been counted for it.
NO_INCIDENT_COUNTS = {
    "unsynced": 0,
    "to_check": 0,
    "proposals": 0,
    "writing": 0,
    "stale": 0,
}


def _count(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def _ids(cases) -> list:
    return [getattr(one, "pk", one) for one in cases]


def _grouped(rows, key: str = "incident") -> dict:
    """{id: n} from a values(key).annotate(n=Count) queryset."""
    return {row[key]: row["n"] for row in rows}


def incident_counts_for(cases) -> dict:
    """The counts behind every incident's pills in these cases, in five
    grouped queries whatever the number of cases (v1.134.0), keyed by
    incident id: what the pills would ask of each incident, asked once."""
    ids = _ids(cases)
    counts: dict = {}
    if not ids:
        return counts

    def bump(incident_id, key, n=1):
        counts.setdefault(incident_id, dict(NO_INCIDENT_COUNTS))[key] += n

    for incident_id, n in _grouped(
        IncidentCamera.objects.filter(
            placed__in=(incidents.GUESS, incidents.NOT_PLACED),
            incident__case_id__in=ids,
        )
        .order_by()
        .values("incident")
        .annotate(n=Count("id"))
    ).items():
        bump(incident_id, "unsynced", n)
    for incident_id, n in _grouped(
        Event.objects.filter(proposed=False, to_check=True, incident__case_id__in=ids)
        .order_by()
        .values("incident")
        .annotate(n=Count("id"))
    ).items():
        bump(incident_id, "to_check", n)
    for incident_id, n in _grouped(
        Event.objects.filter(proposed=True, dismissed=False, incident__case_id__in=ids)
        .order_by()
        .values("incident")
        .annotate(n=Count("id"))
    ).items():
        bump(incident_id, "proposals", n)
    for incident_id, n in _grouped(
        incident_assistant.IncidentMemo.objects.filter(
            state__in=(incident_assistant.QUEUED, incident_assistant.RUNNING),
            incident__case_id__in=ids,
        )
        .order_by()
        .values("incident")
        .annotate(n=Count("id"))
    ).items():
        bump(incident_id, "writing", n)
    events_now = _grouped(
        Event.objects.filter(proposed=False, incident__case_id__in=ids)
        .order_by()
        .values("incident")
        .annotate(n=Count("id"))
    )
    for memo in incident_assistant.IncidentMemo.objects.filter(
        state=incident_assistant.DONE, incident__case_id__in=ids
    ).select_related("incident"):
        newer = events_now.get(memo.incident_id, 0) - memo.events_count
        if newer > 0 or incident_assistant.stale_words(memo, memo.incident):
            bump(memo.incident_id, "stale")
    return counts


def incident_counts(case) -> dict:
    """One case's incident counts, keyed by incident id (v1.124.0)."""
    return incident_counts_for([case])


def _case_incident_counts(case_id, incidents_of: dict, by_incident: dict) -> dict:
    """A case's incident pills' figures from its incidents' rows: how many
    incidents are not synced, and the rest summed across them."""
    out = {"incidents": 0, **NO_INCIDENT_COUNTS}
    for incident_id in incidents_of.get(case_id, ()):
        row = by_incident.get(incident_id)
        out["incidents"] += 1
        if row is None:
            continue
        if row["unsynced"]:
            out["unsynced"] += 1
        for key in ("to_check", "proposals", "writing", "stale"):
            out[key] += row[key]
    return out


def counts_for(cases, user=None) -> dict:
    """Everything the pills and a case row read, for all these cases at once,
    keyed by case id (v1.134.0). About a dozen grouped queries for the whole
    page rather than fourteen per case."""
    from core.documents import Document
    from core.recordings import Recording

    ids = _ids(cases)
    out: dict = {}
    if not ids:
        return out
    clips_on = bool(settings_store.get("clips_available"))
    incidents_on = incidents.on()
    for case_id in ids:
        out[case_id] = {
            "recordings": 0,
            "size_bytes": 0,
            "running": 0,
            "queued": 0,
            "preparing": 0,
            "tonight": 0,
            "summaries": 0,
            "translating": 0,
            "clips_rendering": 0,
            "clips_failed": 0,
            "assigned": 0,
            "reviewed": 0,
            "yours_total": 0,
            "yours_left": 0,
            "shares": 0,
            "incidents": {"incidents": 0, **NO_INCIDENT_COUNTS},
            "incident_ids": [],
        }

    # The recordings: how many, their kept sizes, the assignment counts, and
    # the person's own, in one grouped query; the sizes never measured are
    # measured first, once each (the rows from before v1.134.0).
    for one in Recording.objects.filter(case_id__in=ids, on_disk_bytes__isnull=True):
        one.measure_disk()
    # Nobody looking: a condition no row meets, so the two counts read zero.
    mine = Q(assigned_to=user) if user is not None else Q(pk__isnull=True)
    for row in (
        Recording.objects.filter(case_id__in=ids)
        .order_by()
        .values("case_id")
        .annotate(
            n=Count("id"),
            total=Sum("on_disk_bytes"),
            assigned=Count("id", filter=Q(assigned_to__isnull=False)),
            reviewed=Count("id", filter=Q(reviewed_on__isnull=False)),
            yours=Count("id", filter=mine),
            yours_left=Count("id", filter=mine & Q(reviewed_on__isnull=True)),
        )
    ):
        case = out[row["case_id"]]
        case["recordings"] = row["n"]
        case["size_bytes"] = row["total"] or 0
        case["assigned"] = row["assigned"]
        case["reviewed"] = row["reviewed"]
        case["yours_total"] = row["yours"]
        case["yours_left"] = row["yours_left"]
    for row in (
        Document.objects.filter(case_id__in=ids)
        .order_by()
        .values("case_id")
        .annotate(total=Sum("size_bytes"))
    ):
        out[row["case_id"]]["size_bytes"] += row["total"] or 0

    # Transcribing, and in line.
    for row in (
        Job.objects.filter(recording__case_id__in=ids, state__in=JobState.LIVE)
        .order_by()
        .values("recording__case_id", "state")
        .annotate(n=Count("id"))
    ):
        key = "running" if row["state"] == JobState.RUNNING else "queued"
        out[row["recording__case_id"]][key] += row["n"]
    # Preparing for summaries and chat, and tonight's vision.
    for row in (
        Transcript.objects.filter(
            recording__case_id__in=ids,
            prepare_state__in=(assistant.QUEUED, assistant.PREPARING, vision.TONIGHT),
        )
        .order_by()
        .values("recording__case_id", "prepare_state")
        .annotate(n=Count("id"))
    ):
        key = "tonight" if row["prepare_state"] == vision.TONIGHT else "preparing"
        out[row["recording__case_id"]][key] += row["n"]
    # Tonight's summaries (Phase 9 chapter 5).
    for row in (
        summaries_tonight.waiting()
        .filter(recording__case_id__in=ids)
        .order_by()
        .values("recording__case_id")
        .annotate(n=Count("id"))
    ):
        out[row["recording__case_id"]]["summaries"] = row["n"]
    # The English to follow (ADR 0026, v1.162.0).
    from core import translation

    for row in (
        translation.live()
        .filter(transcript__recording__case_id__in=ids)
        .order_by()
        .values("transcript__recording__case_id")
        .annotate(n=Count("id"))
    ):
        out[row["transcript__recording__case_id"]]["translating"] = row["n"]
    # Clips rendering, and failed.
    if clips_on:
        for row in (
            Clip.objects.filter(
                recording__case_id__in=ids,
                state__in=(RenderState.RENDERING, RenderState.FAILED),
            )
            .order_by()
            .values("recording__case_id", "state")
            .annotate(n=Count("id"))
        ):
            key = (
                "clips_rendering"
                if row["state"] == RenderState.RENDERING
                else "clips_failed"
            )
            out[row["recording__case_id"]][key] += row["n"]
    # Shared with.
    if sharing.on():
        for row in (
            sharing.Share.objects.filter(case_id__in=ids)
            .order_by()
            .values("case_id")
            .annotate(n=Count("id"))
        ):
            out[row["case_id"]]["shares"] = row["n"]
    # The incidents, with their own counts.
    if incidents_on:
        incidents_of: dict = {}
        for incident_id, case_id in Incident.objects.filter(
            case_id__in=ids
        ).values_list("id", "case_id"):
            incidents_of.setdefault(case_id, []).append(incident_id)
        by_incident = incident_counts_for(ids)
        for case_id in ids:
            out[case_id]["incident_ids"] = incidents_of.get(case_id, [])
            out[case_id]["incidents"] = _case_incident_counts(
                case_id, incidents_of, by_incident
            )
            out[case_id]["by_incident"] = {
                one: by_incident.get(one, dict(NO_INCIDENT_COUNTS))
                for one in incidents_of.get(case_id, [])
            }
    return out


def _incident_pills(counts: dict, href: str, add, *, for_case: bool) -> None:
    """The incident pills from counted figures: for a case's incidents
    together (the dashboard line) or for one incident alone (Home's line
    under its case, v1.115.0). Every pill links to `href`."""
    if counts["unsynced"]:
        add(
            _count(counts["unsynced"], "incident not synced", "incidents not synced")
            if for_case
            else "not synced",
            href,
            WARN,
        )
    if counts["to_check"]:
        add(_count(counts["to_check"], "event to check", "events to check"), href, WARN)
    # Proposals wait for a person's accept or dismiss: warm, so the case
    # sits under Needs you on Home (v1.86.2, at the maintainer's word).
    if counts["proposals"]:
        add(
            _count(
                counts["proposals"], "proposed event waiting", "proposed events waiting"
            ),
            href,
            WARN,
        )
    if counts["writing"]:
        add(_count(counts["writing"], "memo writing", "memos writing"), href)
    if counts["stale"]:
        add(
            _count(counts["stale"], "memo has newer events", "memos have newer events"),
            href,
            WARN,
        )


def incident_pills(incident, counts: dict | None = None) -> list[dict]:
    """One incident's own pills, each a link to its page (Home, v1.115.0);
    with `counts` from incident_counts_for, from memory (v1.124.0)."""
    out: list[dict] = []

    def add(words: str, href: str, tone: str = PLAIN) -> None:
        out.append({"words": words, "href": href, "tone": tone})

    if counts is None:
        counts = incident_counts_for([incident.case_id]).get(
            incident.pk, dict(NO_INCIDENT_COUNTS)
        )
    _incident_pills(counts, incident.url(), add, for_case=False)
    return out


def pills(
    case, role: str = "owner", user=None, counts: dict | None = None
) -> list[dict]:
    """The line's pills in their order; each has words, a tone and a link.
    With the person looking, their own "left for you" (Phase 9 chapter 3).
    `counts` is this case's row from counts_for when a page has it; else
    it is asked for here, grouped all the same."""
    here = reverse("case", args=[case.pk])
    out: list[dict] = []
    if counts is None:
        counts = counts_for([case], user)[case.pk]

    def add(words: str, href: str, tone: str = PLAIN) -> None:
        out.append({"words": words, "href": href, "tone": tone})

    # Transcribing, and in line.
    if counts["running"]:
        add(_count(counts["running"], "transcribing", "transcribing"), here)
    if counts["queued"]:
        add(_count(counts["queued"], "in line", "in line"), here)

    # Preparing for summaries and chat, or enriched with vision now.
    if counts["preparing"]:
        add(_count(counts["preparing"], "preparing", "preparing"), here)
    # The English to follow (ADR 0026, v1.162.0).
    if counts.get("translating"):
        add(
            _count(counts["translating"], "English to follow", "English to follow"),
            here,
        )

    # Tonight's vision.
    if counts["tonight"]:
        start, _ = settings_store.vision_window()
        add(f"{_count(counts['tonight'], 'video')} enriched tonight from {start}", here)
    # Tonight's summaries (Phase 9 chapter 5), in the plain tone.
    if counts["summaries"]:
        add(f"Summaries tonight: {counts['summaries']}", here)

    if incidents.on():
        _incident_pills(
            counts["incidents"], f"{here}?tab=incidents", add, for_case=True
        )

    # Clips rendering, and failed.
    if settings_store.get("clips_available"):
        clips_tab = f"{here}?tab=clips"
        if counts["clips_rendering"]:
            add(
                _count(counts["clips_rendering"], "clip rendering", "clips rendering"),
                clips_tab,
            )
        if counts["clips_failed"]:
            add(
                _count(counts["clips_failed"], "clip failed", "clips failed"),
                clips_tab,
                WARN,
            )

    # Assigned to and Reviewed (Phase 9 chapter 3): plain, never a warning,
    # since work waiting is not overdue.
    if counts["assigned"]:
        add(
            f"{counts['reviewed']} of {counts['recordings']} reviewed",
            f"{here}?state=reviewed",
        )
    if user is not None and counts["yours_total"]:
        add(
            f"{counts['yours_left']} of {counts['yours_total']} left for you",
            f"{here}?who=me&state=unreviewed",
        )

    # Shared with.
    if sharing.on() and role in ("owner", "admin") and counts["shares"]:
        add(f"shared with {counts['shares']}", f"{here}#shared-with")

    # The retention clock.
    left = retention.days_left(case)
    if retention.is_warned(left):
        add(f"deletes in {_count(left, 'day')}", f"{here}#retention", WARN)
    return out
