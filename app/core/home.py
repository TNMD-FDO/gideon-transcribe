"""Home (Phase 8 chapter 13; the desk, Phase 13 chapter 1): where sign-in
lands, and what is the person's.

One page in a fixed order: the greeting with the person's name; the notices;
Ready to download (a batch of this session that has finished, with its
download, so the transcripts are never only on the batch page); Your work
(what is assigned to the person and not yet reviewed, by case, with Next);
then, side by side on a wide window, Cases (every case the person can open,
by last activity, each a plain row saying what it holds and whom it is shared
with) over Your team, lately (what colleagues did in the shared cases, from
the records the app already keeps), and This session (Running now as its
first line, the recordings not in a case, the keep-or-lose line at the foot,
the clips line last). A section with nothing in it is not drawn. Nothing
here is only a door: the rail's two actions are the doors, on every page.
Nothing on Home is amber: a case's state is on its own page.
"""

from __future__ import annotations

import datetime as dt

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

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
from core.recordings import Batch, MediaState, Recording

# Your team, lately: the window it reads and the most lines it draws.
LATELY_DAYS = 30
LATELY_MOST = 20
QUESTION_MOST = 80


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
    from django.db.models import Q

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


# Your work (Phase 13 chapter 1) -------------------------------------------------------


def your_work(user) -> list[dict]:
    """One row per case in which something is assigned to the person and not
    yet reviewed: the counts, Next (the oldest by when it was added) and the
    way to all of them (the Recordings tab, Mine, not reviewed). Drawn only
    when something is left."""
    if not settings_store.get("folder_management"):
        return []
    by_case: dict = {}
    for one in (
        Recording.objects.filter(case__in=cases.cases_for(user), assigned_to=user)
        .select_related("case")
        .order_by("created")
    ):
        row = by_case.setdefault(
            one.case_id, {"case": one.case, "assigned": 0, "left": 0, "next": None}
        )
        row["assigned"] += 1
        if one.reviewed_on is None:
            row["left"] += 1
            if row["next"] is None:
                row["next"] = one
    out = []
    for row in by_case.values():
        if not row["left"]:
            continue
        here = reverse("case", args=[row["case"].pk])
        row["all_url"] = f"{here}?who=me&state=unreviewed"
        row["next_url"] = reverse("viewer", args=[row["next"].pk])
        row["next_title"] = row["next"].title or row["next"].original_filename
        row["words"] = f"{row['left']} of {row['assigned']} left for you"
        out.append(row)
    out.sort(key=lambda row: row["case"].name.lower())
    return out


# The cases as rows (Phase 13 chapter 1) -----------------------------------------------


def first_name(person) -> str:
    """A colleague by their first name, as the rows name them."""
    words = (person.shown_name or "").split()
    return words[0] if words else person.username


def _team_words(case, user, shares: list) -> str:
    """ "shared with Pat and Sam", "shared with you by Sam", or ""."""
    if case.owner_id != user.pk:
        return f"shared with you by {case.owner.shown_name}"
    others = [first_name(one.person) for one in shares if one.person_id != user.pk]
    if not others:
        return ""
    if len(others) <= 3:
        return "shared with " + (
            " and ".join(others)
            if len(others) < 3
            else f"{others[0]}, {others[1]} and {others[2]}"
        )
    return f"shared with {others[0]}, {others[1]} and {len(others) - 2} more"


def case_rows(user) -> list[dict]:
    """Every case the person can open, newest activity first, each a plain
    row: the name, what it holds (recordings, incidents) and whom it is shared
    with, the last activity's date, and whether a share is still new. No
    pills: a case's state is on its own page."""
    from core import incidents, sharing

    mine = list(
        cases.cases_for(user)
        .select_related("owner")
        .annotate(recordings_count=Count("recordings", distinct=True))
        .order_by("-last_activity")
    )
    ids = [one.pk for one in mine]
    incident_counts: dict = {}
    if incidents.on() and ids:
        for row in (
            incidents.Incident.objects.filter(case_id__in=ids)
            .values("case_id")
            .annotate(n=Count("id"))
        ):
            incident_counts[row["case_id"]] = row["n"]
    shares_by_case: dict = {}
    if sharing.on() and ids:
        for one in sharing.Share.objects.filter(case_id__in=ids).select_related(
            "person"
        ):
            shares_by_case.setdefault(one.case_id, []).append(one)
    rows = []
    for case in mine:
        shares = shares_by_case.get(case.pk, [])
        own_share = next((one for one in shares if one.person_id == user.pk), None)
        rows.append(
            {
                "case": case,
                "url": reverse("case", args=[case.pk]),
                "recordings": case.recordings_count,
                "incidents": incident_counts.get(case.pk, 0),
                "team_words": _team_words(case, user, shares),
                "is_new": own_share is not None and own_share.last_opened is None,
                "when": case.last_activity,
            }
        )
    return rows


# Your team, lately (Phase 13 chapter 1) -----------------------------------------------


def when_words(moment) -> str:
    """ "today, 14:10", "yesterday, 09:32", or "4 Nov"."""
    local = timezone.localtime(moment)
    today = timezone.localtime().date()
    if local.date() == today:
        return f"today, {local:%H:%M}"
    if local.date() == today - dt.timedelta(days=1):
        return f"yesterday, {local:%H:%M}"
    return f"{local.day} {local:%b}"


def initials(person) -> str:
    words = (person.shown_name or person.username or "?").split()
    return "".join(word[0] for word in words[:2]).upper()


def _line(person, case, when, words: str, url: str, kind: str) -> dict:
    return {
        "who": person.shown_name,
        "initials": initials(person),
        "case": case.name if case is not None else "",
        "case_url": reverse("case", args=[case.pk]) if case is not None else "",
        "words": words,
        "url": url,
        "when": when,
        "when_words": when_words(when),
        "kind": kind,
    }


def _grouped_lines(user, by_case: dict, since) -> list[dict]:
    """Reviewed, noted and added, by one person in one case on one day,
    folded into one line each."""
    from core.jobs import Segment
    from core.notes import MomentNote

    ids = list(by_case)
    groups: dict = {}

    def bump(person, case_id, when, key):
        if person is None or person.pk == user.pk or case_id not in by_case:
            return
        day = timezone.localtime(when).date()
        group = groups.setdefault(
            (person.pk, case_id, day),
            {"person": person, "case": by_case[case_id], "when": when, "n": {}},
        )
        group["n"][key] = group["n"].get(key, 0) + 1
        if when > group["when"]:
            group["when"] = when

    for one in Recording.objects.filter(
        case_id__in=ids, reviewed_on__gte=since
    ).select_related("reviewed_by"):
        bump(one.reviewed_by, one.case_id, one.reviewed_on, "reviewed")
    for one in (
        Segment.objects.filter(
            transcript__recording__case_id__in=ids, note_changed__gte=since
        )
        .exclude(note="")
        .select_related("note_by", "transcript__recording")
    ):
        bump(one.note_by, one.transcript.recording.case_id, one.note_changed, "noted")
    for one in MomentNote.objects.filter(
        recording__case_id__in=ids, note_changed__gte=since
    ).select_related("note_by", "recording"):
        bump(one.note_by, one.recording.case_id, one.note_changed, "noted")
    for one in Recording.objects.filter(
        case_id__in=ids, created__gte=since
    ).select_related("user"):
        bump(one.user, one.case_id, one.created, "added")

    out = []
    for group in groups.values():
        n = group["n"]
        # "reviewed 3 recordings", "left 2 notes", "added 2 recordings",
        # joined with "and"; the case follows with "in", or "to" for added
        # alone.
        parts = []
        if n.get("reviewed"):
            parts.append("reviewed " + dashboard._count(n["reviewed"], "recording"))
        if n.get("noted"):
            parts.append("left " + dashboard._count(n["noted"], "note"))
        if n.get("added"):
            parts.append("added " + dashboard._count(n["added"], "recording"))
        joined = " and ".join(parts)
        words = f"{joined} to" if list(n) == ["added"] else f"{joined} in"
        case = group["case"]
        out.append(
            _line(
                group["person"],
                case,
                group["when"],
                words,
                reverse("case", args=[case.pk]),
                "work",
            )
        )
    return out


def team_lately(user) -> dict:
    """What colleagues did in the cases the person shares, newest first,
    from the records the app already keeps, LATELY_MOST lines at most over
    LATELY_DAYS; whether anything is newer than the person's last Seen."""
    from core import dictation, sharing
    from core.case_chat import CaseChatTurn

    since = timezone.now() - dt.timedelta(days=LATELY_DAYS)
    lines: list[dict] = []
    if settings_store.get("folder_management"):
        by_case = {one.pk: one for one in cases.cases_for(user).select_related("owner")}
        if by_case:
            lines += _grouped_lines(user, by_case, since)
            if sharing.on():
                for one in sharing.Share.objects.filter(
                    person=user, case_id__in=list(by_case), added_on__gte=since
                ).select_related("added_by", "case"):
                    if one.added_by is None:
                        continue
                    lines.append(
                        _line(
                            one.added_by,
                            one.case,
                            one.added_on,
                            "shared",
                            reverse("case", args=[one.case_id]),
                            "shared",
                        )
                    )
            # A turn keeps no time of its own: the chat's is the question's,
            # and a chat with several turns by one colleague is one line, its
            # latest question.
            latest: dict = {}
            for one in (
                CaseChatTurn.objects.filter(
                    chat__case_id__in=list(by_case), chat__created__gte=since
                )
                .exclude(asked_by=user)
                .exclude(asked_by=None)
                .select_related("asked_by", "chat", "chat__case")
                .order_by("chat_id", "number")
            ):
                latest[one.chat_id] = one
            for one in latest.values():
                question = " ".join(one.question.split())
                if len(question) > QUESTION_MOST:
                    question = question[: QUESTION_MOST - 3].rstrip() + "..."
                lines.append(
                    {
                        **_line(
                            one.asked_by,
                            one.chat.case,
                            one.chat.created,
                            "asked Gideon about",
                            reverse("case", args=[one.chat.case_id]) + "?tab=chat",
                            "asked",
                        ),
                        "question": question,
                    }
                )
    if dictation.on():
        for one in dictation.sent_to(user).filter(sent_on__gte=since):
            if one.sent_by is None:
                continue
            lines.append(
                {
                    **_line(
                        one.sent_by,
                        None,
                        one.sent_on,
                        "sent you a dictation,",
                        reverse("viewer", args=[one.recording_id]),
                        "dictation",
                    ),
                    "title": one.recording.title or one.recording.original_filename,
                }
            )
    lines.sort(key=lambda one: one["when"], reverse=True)
    lines = lines[:LATELY_MOST]
    seen = getattr(user, "team_seen_on", None)
    new = bool(lines) and (seen is None or lines[0]["when"] > seen)
    return {"lines": lines, "new": new, "seen": seen}


@login_required
@require_POST
def team_seen(request: HttpRequest) -> HttpResponse:
    """Seen on Your team, lately: the section folds until something newer
    happens. Kept on the person's account; no audit row."""
    request.user.team_seen_on = timezone.now()
    request.user.save(update_fields=["team_seen_on"])
    return redirect(reverse("home"))


@login_required
def home(request: HttpRequest) -> HttpResponse:
    from core import clip_pages, dictation, pages
    from core.clips import Clip, RenderState

    user = request.user
    cases_on = bool(settings_store.get("folder_management"))
    rows = case_rows(user) if cases_on else []
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
            "person": first_name(user),
            "service_is_up": whisperx.alive_lately(),
            "transcription_installed": pieces.transcription_installed(),
            "storage_warning": uploads.storage_warning(user),
            "quota_notice": quota_raises.notice(user),
            "ready": ready_batches(user),
            "work": your_work(user),
            "running": running_now(user),
            "session": session,
            "keep_line": keep_line(),
            "recorded_here": recorded_here,
            "cases_on": cases_on,
            "cases_rows": rows,
            "cases_line": pages._cases_line(user) if cases_on else "",
            "team": team_lately(user),
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
