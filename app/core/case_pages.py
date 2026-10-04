"""The Cases page, one Case's page, and the ways in and out of a Case.

Every page here answers "not found" while Folder management is off, so that
turning the setting off makes the app look like Phase 1 again rather than
leaving a link that half works. Nothing is deleted by that: the rows and the
files stay, and turning it back on brings the pages back over them.
"""

from __future__ import annotations

import io
import zipfile

from django.contrib.auth.decorators import login_required
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseForbidden,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core import (
    assignments,
    audit,
    case_search,
    cases,
    dashboard,
    documents,
    engine,
    exports,
    home,
    live,
    notes,
    pages,
    retention,
    settings_store,
    sharing,
    sitting,
    summaries_tonight,
    uploads,
    vision,
    vocabulary,
)
from core.cases import Case
from core.jobs import Segment
from core.recordings import Recording


def _on_or_404() -> None:
    if not cases.folder_management_on():
        raise Http404("Folder management is off")


def _their_case(request, case_id) -> Case:
    """The Case, if this person may open it, and the Admin access row if not theirs.

    The owner and a Collaborator open it as their own. An Admin who is
    neither opens it under the Admin access rule.
    """
    case = get_object_or_404(Case, pk=case_id, deleted_on__isnull=True)
    role = case.role_of(request.user)
    if not role:
        raise Http404("not this person's case")
    if role == "admin":
        # ADR 0004: an Admin opening somebody else's work is recorded, and it
        # is not use, so the Retention clock does not move.
        audit.write(
            audit.Category.ADMIN,
            "admin access",
            actor=request.user,
            affected_user=case.owner,
            object_type="case",
            object_id=case.pk,
            object_label=case.name,
            request=request,
        )
    return case


def _case_they_run(request, case_id) -> Case:
    """The Case, if this person may rename, share, transfer, or delete it.

    The owner and Admins. A Collaborator is told it is not there, as they
    are told about anybody else's Case: the page never offers them the button.
    """
    case = get_object_or_404(Case, pk=case_id, deleted_on__isnull=True)
    if not case.may_be_run_by(request.user):
        raise Http404("not this person's case")
    return case


@login_required
def cases_page(request: HttpRequest) -> HttpResponse:
    """Where a person lands when Cases are on: their own, and the ones shared with them.

    Admins see every Case, because they must be able to act on a leaver's.
    """
    _on_or_404()

    mine = cases.cases_for(request.user)
    others = Case.objects.none()
    if request.user.is_admin:
        others = Case.objects.filter(deleted_on__isnull=True).exclude(
            owner=request.user
        )

    filter_text = request.GET.get("name", "").strip()
    if filter_text:
        mine = mine.filter(name__icontains=filter_text)
        others = others.filter(name__icontains=filter_text)

    # The Admin's two filters from the panel chapter. "Owner deactivated" is a
    # database question; "Expiring" is a count of days with the Off spells
    # left out, so it is asked of each row after it is built.
    owner_deactivated = bool(request.GET.get("owner_deactivated"))
    expiring = bool(request.GET.get("expiring"))
    if owner_deactivated:
        others = others.filter(owner__deactivated_at__isnull=False)

    # Three views of one page: the person's own cases, everyone's (an Admin's
    # alone), and the Recycle bin, which is its own view. Everyone's is the
    # chapter's "every Case" for an Admin, shown apart from their own so a
    # leaver's case is found without wading through one's own.
    who = (
        "everyone"
        if request.GET.get("who") == "everyone" and request.user.is_admin
        else "mine"
    )
    rows = [
        _as_row(one, request.user) for one in (others if who == "everyone" else mine)
    ]
    if expiring:
        rows = [one for one in rows if one["warned"]]

    if request.user.is_admin:
        binned = Case.objects.filter(deleted_on__isnull=False).count()
    else:
        binned = cases.binned_for(request.user).count()

    return render(
        request,
        "cases.html",
        {
            "page": "cases",
            "cases": rows,
            "who": who,
            "name_filter": filter_text,
            "expiring": expiring,
            "owner_deactivated": owner_deactivated,
            "binned": binned,
            "storage_warning": uploads.storage_warning(request.user),
        },
    )


def _as_row(case: Case, viewer=None) -> dict:
    left = retention.days_left(case)
    # A Case shared with the person carries its owner's name and is New until
    # they first open it; the Share remembers.
    share = None
    if viewer is not None and case.owner_id != viewer.pk and sharing.on():
        share = case.shares.filter(person=viewer).first()
    return {
        "case": case,
        "shared_by": case.owner.shown_name if share is not None else "",
        "is_new": share is not None and share.last_opened is None,
        "recordings": case.recordings.count(),
        "size": uploads.as_size(case.disk_bytes()),
        "opens_at": opens_at(case),
        # The Retention warning: the amber mark and its line, computed at
        # every page load so the Warning setting takes effect at once, and
        # matching what the digest will say.
        "days_left": left,
        "warned": retention.is_warned(left),
        "deletes_line": retention.deletes_line(left),
        "owner_deactivated": case.owner.deactivated_at is not None,
    }


def _bin_row(case: Case) -> dict:
    return {
        "case": case,
        "recordings": case.recordings.count(),
        "size": uploads.as_size(case.disk_bytes()),
        "days_left": max(0, retention.bin_days_left(case)),
        "owner_deactivated": case.owner.deactivated_at is not None,
    }


def _their_binned_case(request, case_id) -> Case:
    """A Case in the Recycle bin, if this person may act on it there.

    The owner and Admins. Collaborators see nothing of the bin. No Admin
    access row: nothing in a binned Case can be opened from here, only
    restored or wiped, and both write their own rows.
    """
    case = get_object_or_404(Case, pk=case_id, deleted_on__isnull=False)
    if case.owner_id != request.user.pk and not request.user.is_admin:
        raise Http404("not this person's case")
    return case


def opens_at(case: Case) -> str:
    """Where clicking a Case takes somebody: its own page, always.

    It used to open the newest Recording in the viewer, with a rail of the
    Case beside it, and keep the Case page behind a quieter link; people
    landed in a player when they expected the case, and the page with the
    Case's recordings, search, clips, speakers, chat and sharing was one
    they might never find. One door: the page is the case, and a Recording
    opens from it.
    """
    return reverse("case", args=[case.pk])


@login_required
def case_page(request: HttpRequest, case_id) -> HttpResponse:
    """One Case: its Recordings, and one box that searches them.

    The chapter gives this page four tabs. Three of them are other chapters'
    (Speakers, Clips in cases, and Case Chat) and are not built, so this page
    shows the one tab that is.
    """
    _on_or_404()
    case = _their_case(request, case_id)
    cases.note_activity(case, by=request.user)
    role = case.role_of(request.user)
    if role == "collaborator":
        sharing.note_opened(case, request.user)

    asked = request.GET.get("q", "").strip()
    # The four tabs the chapter gives this page; Chat only while the Case
    # Chat exists.
    from core import case_chat, incidents

    chat_here = case_chat.available()
    # The Gideon tab went with Phase 8 chapter 1: the panel is Gideon's place.
    tabs = (
        ("search", "clips", "notes", "speakers")
        + (("incidents",) if incidents.on() else ())
        + (("documents",) if documents.on() else ())
    )
    tab = request.GET.get("tab") if request.GET.get("tab") in tabs else "recordings"
    # Phase 2's ?q= on the case URL opens the Search tab (Phase 7 chapter 3).
    if asked and not request.GET.get("tab"):
        tab = "search"

    # The pane about the case says where its clock stands, as its row on the
    # Cases page does.
    left = retention.days_left(case)
    # The rows once, from a handful of queries (Phase 9 chapter 1).
    names = assignments.names_for(case)
    rows = _rows_for(case, names)
    # The pills over the Recordings tab (Phase 9 chapter 3): All, Mine,
    # Mine not reviewed, Reviewed, Unassigned, and one person by username.
    may_direct = case.may_direct(request.user)
    who = request.GET.get("who", "")
    state = request.GET.get("state", "")
    shown_rows = assignments.filtered(rows, who, state, request.user)
    assignment_pills = _assignment_pills(case, rows, who, state, request.user)
    # The tools fold away until the case uses assignment (v1.121.2): an
    # incident reviewed by one person never sees ticks, a bar and five pills.
    tools_open = any(one.assigned_to_id for one in rows) or bool(who or state)

    return render(
        request,
        "case.html",
        {
            "page": "cases",
            "case": case,
            "here_case": home.here_case_for(request.user, case),
            "tab": tab,
            "warned": retention.is_warned(left),
            "deletes_line": retention.deletes_line(left),
            # The Speakers tab: the Case's People and the Recordings still unnamed.
            **(
                _speakers_tab(case)
                if tab == "speakers"
                else {"people_count": case.people.count()}
            ),
            "people_said": request.session.pop("people_said", ""),
            "case_chat_available": chat_here,
            # Ask Gideon (Phase 7 chapter 5): on while the case chat is and the
            # engine answers; greyed with the reason otherwise.
            "gideon_on": bool(chat_here and engine.is_reachable()),
            "gideon_why": ""
            if engine.is_reachable()
            else engine.WHAT_TO_SAY[engine.UNREACHABLE],
            "add_recordings_url": reverse("add-recordings", args=[case.pk]),
            "clips_here": _clips_in(case, request.user) if tab == "clips" else [],
            # The tab says how many on every tab, as Recordings and Speakers do
            # (v1.63.2); the rows themselves are built only on the Clips tab.
            "clips_count": _clips_count(case),
            # The Notes tab (Phase 8 chapter 2): every note in the case.
            "notes_count": notes.count(case),
            "notes": (
                notes.of_case(case, request.GET.get("kind", ""))
                if tab == "notes"
                else None
            ),
            # Documents beside the cameras (Phase 8 chapter 4, part 1).
            "documents_on": documents.on(),
            "documents_count": documents.count(case) if documents.on() else 0,
            "documents": _documents_with_exports(case) if tab == "documents" else [],
            "document_homes": documents.homes_of(case) if tab == "documents" else [],
            "add_document_url": documents.add_url(case),
            "is_owner": role == "owner",
            "role": role,
            # The Case vocabulary block (Phase 9 chapter 2).
            "vocabulary": vocabulary.entries(case),
            "may_remove_terms": role != "collaborator",
            **_sharing_context(case, role, request.user, names),
            "recordings": shown_rows,
            # The Type column only when a row has a type (v1.75.1).
            "any_type": any(getattr(one, "recording_type", "") for one in rows),
            "list_url": reverse("case-list", args=[case.pk]),
            # Assigned to and Reviewed (Phase 9 chapter 3): the pills over
            # the table, the tick column for those who may assign, the team
            # for the Assign to prompt and the fold's select.
            "may_direct": may_direct,
            "tools_open": tools_open,
            "who": who,
            "state": state,
            "assignment_pills": assignment_pills,
            "team_members": (
                [
                    {"username": one.username, "name": names[one.pk]}
                    for one in assignments.team_members(case)
                ]
                if may_direct
                else []
            ),
            "vision_line": vision.line(case),
            "vision_pending": vision.pending(case),
            "vision_offers": vision.offers(case, user=request.user),
            # Summaries tonight (Phase 9 chapter 5): the line and the offer.
            "summaries_line": summaries_tonight.line(case),
            "summaries_missing": (
                len(summaries_tonight.missing_in(case)) if summaries_tonight.on() else 0
            ),
            "asked": asked,
            "search": (
                case_search.search(case, asked, request.GET.get("kind", ""))
                if tab == "search" and asked
                else None
            ),
            # The dashboard line (Phase 7 chapter 3).
            "pills": dashboard.pills(case, role, request.user),
            "types": cases.recording_types(),
            "size": uploads.as_size(case.disk_bytes()),
            # Incidents (Phase 6 chapter 1): the strip under the case name,
            # the offers, and the videos New incident lists.
            **_incidents_context(case),
        },
    )


@login_required
def notes_export(request: HttpRequest, case_id) -> HttpResponse:
    """Download notes (Phase 8 chapter 2): every note in the case as a Word
    document, for the office's own reading. One audit row, never a word."""
    from core import audit, exports

    _on_or_404()
    case = _their_case(request, case_id)
    cases.note_activity(case, by=request.user)
    body = notes.word(case, request.user.shown_name)
    audit.write(
        audit.Category.EXPORTS,
        "notes exported",
        actor=request.user,
        request=request,
        affected_user=case.owner if case.owner_id != request.user.pk else None,
        object_type="case",
        object_id=case.pk,
        object_label=case.name,
        kind="notes",
    )
    return exports.hand_over(body, notes.export_name(case), exports.WORD_TYPE)


def _incidents_context(case: Case) -> dict:
    from core import incidents

    if not incidents.on():
        return {"incidents_on": False}
    videos = []
    # One camera lookup for the case (v1.123.0), not one per video.
    cameras: dict = {}
    for camera in incidents.IncidentCamera.objects.filter(
        incident__case=case
    ).select_related("incident"):
        cameras.setdefault(camera.recording_id, camera)
    for recording in case.recordings.order_by("created"):
        if not incidents.is_video(recording):
            continue
        words, tone = incidents.stamp_words(recording)
        elsewhere = cameras.get(recording.pk)
        videos.append(
            {
                "recording": recording,
                "clock": words,
                "tone": tone,
                "elsewhere": elsewhere.incident.name if elsewhere else "",
            }
        )
    return {
        "incidents_on": True,
        "incident_rows": incidents.strip_rows(case),
        "incident_offers": incidents.offers(case),
        "incident_videos": videos,
        # The sitting's column and the offer's bar (Phase 8 chapter 10).
        "sitting_on": sitting.available(),
        "incident_most": incidents.most_cameras(),
        "incident_wall": incidents.wall_size(),
    }


def _sharing_context(
    case: Case, role: str, viewer=None, names: dict | None = None
) -> dict:
    """What the Case page says about its Team (Phase 9 chapter 3), by who is
    looking: everyone with the case sees the list; the owner, an Admin and an
    also-owner may add people; the owner and an Admin may mark an also-owner.
    Nothing while Sharing is off: the Shares are kept and not shown."""
    if not sharing.on():
        return {"sharing_on": False, "shares": [], "colleagues": [], "team": []}
    shares = list(sharing.collaborators(case))
    may_direct = viewer is not None and case.may_direct(viewer)
    return {
        "sharing_on": True,
        "may_share": may_direct,
        "may_mark_owner": role in ("owner", "admin"),
        "may_transfer": role == "owner",
        "shares": shares,
        "colleagues": [one for one in shares],
        "team": assignments.team(case, viewer, names),
        "share_words": sharing.WORDS,
        "transfer_words": sharing.TRANSFER_WORDS,
    }


def _clips_count(case: Case) -> int:
    from core.clips import Clip

    if not settings_store.get("clips_available"):
        return 0
    return Clip.objects.filter(recording__case=case).count()


def _clips_in(case: Case, asker) -> list:
    """Every Clip of every Recording in the Case, oldest Recording first.

    Colleagues' Clips included: this is the Case's list. My clips in the
    navigation lists the person's own, under the Case's name, and links here.
    """
    from core.clip_pages import _row
    from core.clips import Clip

    if not settings_store.get("clips_available"):
        return []

    return [
        _row(one, asker=asker)
        for one in Clip.objects.filter(recording__case=case)
        .select_related("recording", "user", "event", "incident")
        .order_by("recording__created", "created")
    ]


def _speakers_tab(case: Case) -> dict:
    from core import people_pages

    shown = people_pages.tab_context(case)
    shown["people_count"] = len(shown["people"])
    # A voice named across the case (Phase 9 chapter 2).
    shown["side_rule"] = vocabulary.side_rule(case)
    shown["two_channel_count"] = case.recordings.filter(
        is_two_channel_call=True
    ).count()
    # The calls the rule cannot reach: a single track with both voices in it
    # has no Sides, and which voice is which is not fixed by position.
    shown["single_channel_calls"] = case.recordings.filter(
        is_two_channel_call=False, recording_type__iexact="Jail call"
    ).count()
    # The recordings with unnamed speakers, the longest talkers first, each
    # with its minutes of talk (v1.89.0, from the walk): a person naming
    # twelve cameras starts where the naming pays most.
    ordered = []
    for recording, count in shown["unnamed"]:
        transcript = getattr(recording, "transcript", None)
        seconds = 0.0
        if transcript is not None:
            seconds = sum(
                float(one.end) - float(one.start)
                for one in transcript.segments.only("start", "end")
            )
        ordered.append((recording, count, int(round(seconds / 60))))
    ordered.sort(key=lambda one: (-one[2], -one[1]))
    shown["unnamed"] = ordered
    return shown


def _assignment_pills(case, rows, who, state, viewer) -> list[dict]:
    """The filter pills and their counts, shown once the case has a single
    assignment or the person may make one."""
    if not rows:
        return []
    any_assigned = any(one.assigned_to_id for one in rows)
    if not any_assigned and not case.may_direct(viewer):
        return []
    here = reverse("case", args=[case.pk])
    mine = [one for one in rows if one.assigned_to_id == viewer.pk]
    mine_left = len([one for one in mine if one.reviewed_on is None])
    reviewed = len([one for one in rows if one.reviewed_on is not None])
    nobody = len([one for one in rows if one.assigned_to_id is None])
    pills = [
        {"words": f"All {len(rows)}", "href": here, "on": not who and not state},
        {
            "words": f"Mine {len(mine)}",
            "href": f"{here}?who=me",
            "on": who == "me" and not state,
        },
        {
            "words": f"Mine, not reviewed {mine_left}",
            "href": f"{here}?who=me&state=unreviewed",
            "on": who == "me" and state == "unreviewed",
        },
        {
            "words": f"Reviewed {reviewed}",
            "href": f"{here}?state=reviewed",
            "on": state == "reviewed" and not who,
        },
        {
            "words": f"Unassigned {nobody}",
            "href": f"{here}?who=nobody",
            "on": who == "nobody",
        },
    ]
    if who and who not in ("me", "nobody"):
        theirs = [
            one
            for one in rows
            if one.assigned_to_id is not None and one.assigned_to.username == who
        ]
        name = theirs[0].assigned_to.shown_name if theirs else who
        pills.append(
            {
                "words": f"{name} {len(theirs)}",
                "href": f"{here}?who={who}",
                "on": not state,
            }
        )
        pills.append(
            {
                "words": (
                    f"{name}, not reviewed "
                    f"{len([one for one in theirs if one.reviewed_on is None])}"
                ),
                "href": f"{here}?who={who}&state=unreviewed",
                "on": state == "unreviewed",
            }
        )
    return pills


def _rows_for(case: Case, names: dict | None = None) -> list:
    """Each Recording with the words its row shows about its Speakers, its
    state and its notes.

    A handful of queries for the whole case, not a few per row (Phase 9
    chapter 1, for a case of 800 calls): the recordings with their transcript
    and uploader, the newest job each, the speakers, the cameras, the notes
    and the clip counts, each in one query and joined here.
    """
    from collections import defaultdict

    from django.db.models import Count

    from core import assistant, incidents
    from core.clips import Clip
    from core.jobs import Job

    # The settings once, not once per row: each read is a query.
    incidents_on = incidents.on()
    vision_on = assistant.record_on()
    recordings = list(
        case.recordings.select_related(
            "transcript", "user", "assigned_to", "reviewed_by"
        ).order_by("-created")
    )
    ids = [one.pk for one in recordings]
    newest: dict = {}
    for job in (
        Job.objects.filter(recording_id__in=ids)
        .select_related("batch")
        .order_by("recording_id", "-created")
    ):
        newest.setdefault(job.recording_id, job)
    labels = defaultdict(set)
    for recording_id, speaker in (
        Segment.objects.filter(transcript__recording_id__in=ids)
        .exclude(speaker="")
        .values_list("transcript__recording_id", "speaker")
        .distinct()
    ):
        labels[recording_id].add(speaker)
    cameras: dict = {}
    if incidents_on:
        for camera in incidents.IncidentCamera.objects.filter(
            recording_id__in=ids
        ).select_related("incident"):
            cameras.setdefault(camera.recording_id, camera)
    note_counts = notes.counts_in(case)
    # The team's names once per page (v1.121.4): the view hands them in.
    if names is None:
        names = assignments.names_for(case)
    # Summaries waiting for tonight (Phase 9 chapter 5), one query.
    tonight = {
        one.recording_id: one
        for one in summaries_tonight.waiting().filter(recording_id__in=ids)
    }
    clip_counts = dict(
        Clip.objects.filter(recording_id__in=ids)
        .values_list("recording_id")
        .annotate(n=Count("id"))
        .values_list("recording_id", "n")
    )

    rows = []
    for one in recordings:
        job = newest.get(one.pk)
        one.being_replaced = bool(
            job is not None and job.is_live and job.batch.is_reprocessing
        )
        one.in_the_queue = bool(job is not None and job.is_live)
        # A Live recording on its way says where it stands, in words.
        one.queue_line = (
            live.line_for(one)["says"]
            if one.is_live and not hasattr(one, "transcript")
            else ""
        )
        one.speakers_in_words = _speakers_in_words(labels.get(one.pk, set()))
        one.notes_words = notes.count_words(note_counts.get(one.pk))
        one.clips_count = clip_counts.get(one.pk, 0)
        # Assigned to and Reviewed (Phase 9 chapter 3), in words.
        one.assigned_words = (
            names.get(one.assigned_to_id, one.assigned_to.shown_name)
            if one.assigned_to_id
            else ""
        )
        one.reviewed_words = (
            f"Reviewed {one.reviewed_on:%d %b}" if one.reviewed_on else ""
        )
        one.length = exports.clock(one.duration_seconds or 0)
        one.state_word, one.state_tone = pages.state_words(one)
        one.summary_tonight_word = summaries_tonight.words(tonight.get(one.pk))
        # The Vision column (Phase 4 chapter 5), for a video.
        transcript = getattr(one, "transcript", None)
        if transcript is not None:
            # The transcript came with the recording; spare its way back.
            transcript.recording = one
        is_eligible = bool(
            vision_on and transcript is not None and assistant.has_picture(one)
        )
        one.prepare_word, one.prepare_tone = vision.words(transcript, is_eligible)
        one.vision_state = getattr(transcript, "prepare_state", "")
        one.vision_offered = is_eligible
        # The Clock in the picture and Incident columns (Phase 6 chapter 1).
        one.is_video_for_incidents = incidents_on and incidents.is_video(one)
        camera = cameras.get(one.pk)
        one.incident_name = camera.incident.name if camera else ""
        one.incident_url = camera.incident.url() if camera else ""
        # What the filter box matches (Phase 9 chapter 1): the title, the type
        # and who added it.
        one.filter_words = " ".join(
            part
            for part in (one.title, one.recording_type, one.user.shown_name)
            if part
        ).lower()
        rows.append(one)
    return rows


@login_required
def recordings_csv(request: HttpRequest, case_id) -> HttpResponse:
    """Download the list (Phase 9 chapter 1): the case's recordings as a CSV
    for the office's own spreadsheet, oldest added first, UTF-8 with a byte
    order mark so a desktop spreadsheet keeps the accents. One audit row with
    the count, never a title."""
    import csv

    from django.utils import timezone

    _on_or_404()
    case = _their_case(request, case_id)
    rows = list(reversed(_rows_for(case)))
    holder = io.StringIO()
    writer = csv.writer(holder)
    writer.writerow(
        [
            "Title",
            "Type",
            "Added on",
            "Added by",
            "Length",
            "State",
            "Speakers",
            "Notes",
            "Note writers",
            "Assigned to",
            "Reviewed by",
            "Reviewed on",
            "Description",
        ]
    )
    counts = notes.counts_in(case)
    for one in rows:
        found = counts.get(one.pk) or {"count": 0, "writers": []}
        writer.writerow(
            [
                one.title,
                one.recording_type,
                f"{timezone.localtime(one.created):%Y-%m-%d %H:%M}",
                one.user.shown_name,
                one.length if one.duration_seconds else "",
                one.state_word,
                one.speakers_in_words,
                found["count"],
                ", ".join(found["writers"]),
                one.assigned_to.shown_name if one.assigned_to_id else "",
                one.reviewed_by.shown_name if one.reviewed_by_id else "",
                f"{timezone.localtime(one.reviewed_on):%Y-%m-%d}"
                if one.reviewed_on
                else "",
                one.description,
            ]
        )
    audit.write(
        audit.Category.EXPORTS,
        "case list downloaded",
        actor=request.user,
        request=request,
        object_type="case",
        object_id=case.pk,
        object_label=case.name,
        count=len(rows),
    )
    cases.note_activity(case, by=request.user)
    return exports.hand_over(
        holder.getvalue().encode("utf-8-sig"),
        f"{case.name} recordings {timezone.localtime():%Y-%m-%d %H%M}.csv",
        "text/csv; charset=utf-8",
    )


@login_required
@require_POST
def vision_case(request: HttpRequest, case_id) -> HttpResponse:
    """Enrich tonight (anyone with the case), Ask for it now (a request an
    Admin decides), or Enrich now (an Admin's): for the case's videos, or
    for one recording named in the form (Phase 4 chapter 5)."""
    _on_or_404()
    case = _their_case(request, case_id)
    cases.note_activity(case, by=request.user)
    action = request.POST.get("action", "")
    recording = None
    if request.POST.get("recording"):
        recording = case.recordings.filter(pk=request.POST["recording"]).first()
        if recording is None:
            raise Http404("no such recording in this case")
    offers = vision.offers(case, user=request.user)
    if action == "tonight" and offers["tonight"]:
        vision.enrich_tonight(case, by=request.user, recording=recording)
    elif action == "ask" and offers["ask"]:
        vision.ask(
            case, by=request.user, recording=recording, why=request.POST.get("why", "")
        )
    elif action == "now" and offers["now"]:
        vision.enrich_now(case, by=request.user, recording=recording)
    else:
        return HttpResponseForbidden("not offered")
    return redirect(reverse("case", args=[case.pk]))


@login_required
@require_POST
def summaries_tonight_case(request: HttpRequest, case_id) -> HttpResponse:
    """Write the missing summaries tonight (Phase 9 chapter 5): anyone with
    the case marks every recording without a summary of its transcript."""
    _on_or_404()
    case = _their_case(request, case_id)
    if not summaries_tonight.on():
        return HttpResponseForbidden("not offered")
    cases.note_activity(case, by=request.user)
    summaries_tonight.schedule_missing(case, by=request.user, request=request)
    return redirect(reverse("case", args=[case.pk]))


def _speakers_in_words(labels: set) -> str:
    """Reads "2 named, 1 unnamed" from a transcript's speaker labels, and says
    nothing at all when there are none."""
    if not labels:
        return ""
    # The app's own labels are Speaker 1 and Side 1 Speaker 1; the rest are names.
    from core.assistant import _is_a_label

    named = {one for one in labels if not _is_a_label(one)}
    unnamed = len(labels) - len(named)
    parts = []
    if named:
        parts.append(f"{len(named)} named")
    if unnamed:
        parts.append(f"{unnamed} unnamed")
    return ", ".join(parts)


# Making, renaming, and deleting -----------------------------------------------


@login_required
@require_POST
def new_case(request: HttpRequest) -> JsonResponse:
    _on_or_404()
    name = request.POST.get("name", "").strip()
    if not name:
        return JsonResponse({"ok": False, "why": "A case needs a name."}, status=400)

    warn = cases.name_already_used(request.user, name)
    case = cases.create(request.user, name, request=request)
    return JsonResponse(
        {
            "ok": True,
            "id": str(case.pk),
            "name": case.name,
            "where": f"/case/{case.pk}",
            # A warning, never a refusal: two cases may carry the same name.
            "warning": (
                f'You already have a case called "{case.name}".' if warn else ""
            ),
        }
    )


@login_required
@require_POST
def rename_case(request: HttpRequest, case_id) -> JsonResponse:
    _on_or_404()
    case = _case_they_run(request, case_id)
    name = request.POST.get("name", "").strip()
    if not name:
        return JsonResponse({"ok": False, "why": "A case needs a name."}, status=400)

    warn = cases.name_already_used(request.user, name, besides=case)
    cases.rename(case, name, actor=request.user, request=request)
    return JsonResponse(
        {
            "ok": True,
            "name": case.name,
            "warning": (
                f'You already have a case called "{case.name}".' if warn else ""
            ),
        }
    )


@login_required
@require_POST
def delete_case(request: HttpRequest, case_id) -> JsonResponse:
    """Final. There is no recycle bin for a person's own delete."""
    _on_or_404()
    case = _case_they_run(request, case_id)
    recordings, gigabytes = cases.delete(case, actor=request.user, request=request)
    return JsonResponse(
        {
            "ok": True,
            "recordings": recordings,
            "gigabytes": gigabytes,
            "where": "/cases",
        }
    )


@login_required
def what_would_go(request: HttpRequest, case_id) -> JsonResponse:
    """The counts a Delete or Delete permanently confirmation names.

    For a live Case and for one in the Recycle bin alike, so both
    confirmations say what they are taking.
    """
    _on_or_404()
    if Case.objects.filter(pk=case_id, deleted_on__isnull=False).exists():
        case = _their_binned_case(request, case_id)
    else:
        case = _their_case(request, case_id)
    return JsonResponse(_counts_of(case))


def _counts_of(case: Case) -> dict:
    recordings = case.recordings.all()
    return {
        "name": case.name,
        "recordings": recordings.count(),
        "transcripts": sum(1 for one in recordings if hasattr(one, "transcript")),
        "clips": sum(one.clips.count() for one in recordings),
        "chats": case.chats.count(),
        "size": uploads.as_size(case.disk_bytes()),
    }


# The Retention policy: Keep, and the Recycle bin ---------------------------------


@login_required
@require_POST
def keep_case(request: HttpRequest, case_id) -> JsonResponse:
    """Keep: start the clock over without opening anything.

    Whoever sees the amber mark may press it, an Admin included; an Admin's
    Keep is audited with the owner as the affected user.
    """
    _on_or_404()
    case = get_object_or_404(Case, pk=case_id, deleted_on__isnull=True)
    if not case.may_be_opened_by(request.user):
        raise Http404("not this person's case")
    cases.keep(case, actor=request.user, request=request)
    return JsonResponse({"ok": True, "days_left": retention.days_left(case)})


@login_required
def recycle_bin(request: HttpRequest) -> HttpResponse:
    """Where a Case the clock deleted waits, restorable, until it is wiped.

    The owner sees their own; an Admin sees everybody's, with an owner filter
    and the "Owner deactivated" mark. Hidden while Folder management is off,
    like every other Cases page.
    """
    _on_or_404()
    owner_filter = request.GET.get("owner", "").strip()
    if request.user.is_admin:
        binned = Case.objects.filter(deleted_on__isnull=False).select_related("owner")
        if owner_filter:
            binned = binned.filter(owner__username=owner_filter)
    else:
        binned = cases.binned_for(request.user).select_related("owner")

    rows = [_bin_row(one) for one in binned.order_by("deleted_on", "name")]
    return render(
        request,
        "recycle-bin.html",
        {
            "page": "cases",
            "rows": rows,
            "owner_filter": owner_filter,
            "owners": (
                sorted({one["case"].owner.username for one in rows})
                if request.user.is_admin and not owner_filter
                else []
            ),
            "bin_days": retention.recycle_bin_days(),
            # The strip above the page: the bin is the third view of Cases.
            "who": "bin",
            "binned": len(rows),
            "mine": sum(1 for one in rows if one["case"].owner_id == request.user.pk),
        },
    )


@login_required
@require_POST
def restore_case(request: HttpRequest, case_id) -> JsonResponse:
    _on_or_404()
    case = _their_binned_case(request, case_id)
    cases.restore(case, actor=request.user, request=request)
    return JsonResponse({"ok": True, "where": reverse("case", args=[case.pk])})


@login_required
@require_POST
def wipe_case(request: HttpRequest, case_id) -> JsonResponse:
    """Delete permanently: gone for good, files and rows."""
    _on_or_404()
    case = _their_binned_case(request, case_id)
    cause = (
        cases.WIPED_BY_OWNER
        if case.owner_id == request.user.pk
        else cases.WIPED_BY_ADMIN
    )
    count, gigabytes = cases.wipe(
        case, cause=cause, actor=request.user, request=request
    )
    return JsonResponse({"ok": True, "recordings": count, "gigabytes": gigabytes})


@login_required
def bin_what_would_go(request: HttpRequest) -> JsonResponse:
    """What Empty recycle bin would take: this person's own binned Cases."""
    _on_or_404()
    mine = list(cases.binned_for(request.user))
    return JsonResponse(
        {
            "cases": len(mine),
            "recordings": sum(one.recordings.count() for one in mine),
            "size": uploads.as_gb(sum(one.disk_bytes() for one in mine)),
        }
    )


@login_required
@require_POST
def empty_bin(request: HttpRequest) -> JsonResponse:
    """Empty recycle bin: every binned Case of this person's, wiped at once.

    A person's own, Admin or not: an Admin empties their own bin here and
    wipes somebody else's Cases one at a time, so nothing of a leaver's goes
    in one unconsidered click.
    """
    _on_or_404()
    gone = 0
    for case in list(cases.binned_for(request.user)):
        cases.wipe(
            case, cause=cases.WIPED_BY_OWNER, actor=request.user, request=request
        )
        gone += 1
    return JsonResponse({"ok": True, "cases": gone})


# Moving a Recording in --------------------------------------------------------


@login_required
def where_it_could_go(request: HttpRequest) -> JsonResponse:
    """The picker's list: the Cases this person may put a Recording into."""
    _on_or_404()
    return JsonResponse(
        {
            "cases": [
                {
                    "id": str(one.pk),
                    "name": one.name,
                    "shared_by": (
                        one.owner.shown_name if one.owner_id != request.user.pk else ""
                    ),
                }
                for one in cases.cases_for(request.user)
            ],
            "types": cases.recording_types(),
        }
    )


@login_required
@require_POST
def move_to_case(request: HttpRequest, recording_id) -> JsonResponse:
    """Move a Done Recording into a Case, or from one Case to another.

    Only a Done Recording is offered: a Queued, Running or Failed one is
    retried or deleted first, because a move renames the folder its Job is
    writing into.
    """
    _on_or_404()
    recording = get_object_or_404(Recording, pk=recording_id)

    if not cases.may_throw_away(recording, request.user):
        raise Http404("not this person's recording")

    if not hasattr(recording, "transcript"):
        return JsonResponse(
            {
                "ok": False,
                "why": (
                    "Only a recording with a transcript can be moved. Retry or "
                    "delete this one first."
                ),
            },
            status=400,
        )

    case = get_object_or_404(
        Case, pk=request.POST.get("case", ""), deleted_on__isnull=True
    )
    if not case.member(request.user) and not request.user.is_admin:
        raise Http404("not this person's case")

    if recording.case_id and recording.case_id != case.pk:
        # A clip cut from an incident stays with the incident's case
        # (Phase 7 chapter 1).
        from core.incident_clips import keeps_in_case

        held = keeps_in_case(recording)
        if held:
            return JsonResponse({"ok": False, "why": held}, status=400)

    was_in = recording.case_id
    cases.move_recording(
        recording,
        case,
        actor=request.user,
        description=request.POST.get("description", "").strip(),
        request=request,
    )
    if was_in and was_in != case.pk and recording.assigned_to_id:
        # The assignment was the old case's (Phase 9 chapter 3).
        assignments.unassign(recording, by=request.user, request=request, cause="moved")

    wanted_type = request.POST.get("recording_type", "").strip()
    if wanted_type:
        recording.recording_type = wanted_type[:60]
        recording.save(update_fields=["recording_type"])

    return JsonResponse({"ok": True, "case": case.name, "where": f"/case/{case.pk}"})


@login_required
@require_POST
def set_details(request: HttpRequest, recording_id) -> JsonResponse:
    """The Recording type and the Description, edited in the Details panel."""
    _on_or_404()
    recording = get_object_or_404(Recording, pk=recording_id)
    if recording.case is None:
        raise Http404("not in a case")
    if not recording.case.may_be_opened_by(request.user):
        raise Http404("not this person's case")

    recording.recording_type = request.POST.get("recording_type", "").strip()[:60]
    recording.description = request.POST.get("description", "").strip()[:2000]
    recording.save(update_fields=["recording_type", "description"])
    cases.note_activity(recording.case, by=request.user)
    return JsonResponse({"ok": True})


@login_required
def download_case(request: HttpRequest, case_id) -> HttpResponse:
    """Every Transcript in one Case, as plain text, in one zip.

    Transcripts only, and not the media: a Workspace is bounded by a Login
    session and a Case is not, so "everything" for a Case could be hundreds of
    gigabytes. What a person wants the recordings themselves for, they take as
    Clips.
    """
    _on_or_404()
    case = _their_case(request, case_id)

    body, included = exports.transcripts_zip(
        case.recordings.select_related("transcript", "user").order_by("created")
    )
    for one in included:
        exports.record_export(request, one, "transcript text")

    cases.note_activity(case, by=request.user)
    return exports.hand_over(
        body, exports.zip_name(f"{case.name} transcripts"), "application/zip"
    )


@login_required
def download_case_clips(request: HttpRequest, case_id) -> HttpResponse:
    """Every Ready Clip in one Case, flat, as the Clips page's zip is."""
    _on_or_404()
    case = _their_case(request, case_id)
    if not settings_store.get("clips_available"):
        raise Http404("clips are off")

    from core import clip_work
    from core.clip_pages import _record
    from core.clips import Clip, RenderState

    clips = [
        one
        for one in Clip.objects.filter(recording__case=case).select_related(
            "recording", "recording__user"
        )
        if one.state == RenderState.READY and one.path.exists()
    ]

    holder = io.BytesIO()
    taken: set[str] = set()
    with zipfile.ZipFile(holder, "w", zipfile.ZIP_DEFLATED) as bundle:
        for clip in clips:
            clip_work.add_to_zip(bundle, clip, taken)
            _record(request, clip, "Clip downloaded")

    cases.note_activity(case, by=request.user)
    return exports.hand_over(
        holder.getvalue(),
        exports.zip_name(f"{case.name} clips"),
        "application/zip",
    )


# Sharing: who may be shared with, Share, Remove, Transfer ---------------------------


def _case_they_direct(request, case_id) -> Case:
    """The Case, if this person may add people to it and assign (Phase 9
    chapter 3): the owner, an Admin, and an also-owner."""
    case = get_object_or_404(Case, pk=case_id, deleted_on__isnull=True)
    if not case.may_direct(request.user):
        raise Http404("not this person's case")
    return case


@login_required
@require_POST
def assign_recordings(request: HttpRequest, case_id) -> JsonResponse:
    """Assigned to (Phase 9 chapter 3): the recordings named go to the team
    member named, or to nobody."""
    _on_or_404()
    case = _case_they_direct(request, case_id)
    ids = [one for one in request.POST.get("recordings", "").split(",") if one]
    rows = list(case.recordings.filter(pk__in=ids))
    typed = request.POST.get("who", "").strip()
    person = None
    if typed:
        person = assignments.find_member(case, typed)
        if person is None:
            return JsonResponse(
                {"ok": False, "why": "That person is not on this case's team."},
                status=400,
            )
    cause = assignments.TICKED if len(rows) > 1 else assignments.ONE
    changed = 0
    for one in rows:
        if assignments.assign(
            one, person, by=request.user, request=request, cause=cause
        ):
            changed += 1
    cases.note_activity(case, by=request.user)
    return JsonResponse(
        {"ok": True, "changed": changed, "who": person.shown_name if person else ""}
    )


@login_required
@require_POST
def divide_recordings(request: HttpRequest, case_id) -> JsonResponse:
    """Divide among (Phase 9 chapter 3): the unassigned recordings dealt
    evenly, oldest first, among the people ticked."""
    _on_or_404()
    case = _case_they_direct(request, case_id)
    people = []
    for username in request.POST.get("who", "").split(","):
        person = assignments.find_member(case, username)
        if person is not None and person not in people:
            people.append(person)
    if not people:
        return JsonResponse(
            {"ok": False, "why": "Tick at least one person."}, status=400
        )
    counts = assignments.divide(case, people, by=request.user, request=request)
    cases.note_activity(case, by=request.user)
    return JsonResponse({"ok": True, "counts": counts})


@login_required
@require_POST
def mark_owner(request: HttpRequest, case_id) -> JsonResponse:
    """Also an owner (Phase 9 chapter 3): the one mark on a Share, the
    owner's and an Admin's to set."""
    _on_or_404()
    case = _case_they_run(request, case_id)
    if not sharing.on():
        raise Http404("Sharing is off")
    share = get_object_or_404(
        sharing.Share, pk=request.POST.get("share", ""), case=case
    )
    wanted = request.POST.get("also_owner", "") in ("1", "yes", "true", "on")
    assignments.set_also_owner(share, wanted, by=request.user, request=request)
    cases.note_activity(case, by=request.user)
    return JsonResponse({"ok": True, "also_owner": share.also_owner})


@login_required
@require_POST
def mark_reviewed(request: HttpRequest, recording_id) -> JsonResponse:
    """Reviewed (Phase 9 chapter 3): the assignee's mark, made after the
    page's question, or taken back; and the person's next recording to do."""
    _on_or_404()
    recording = get_object_or_404(
        Recording.objects.select_related("case", "assigned_to"), pk=recording_id
    )
    if recording.case is None or not recording.case.may_be_opened_by(request.user):
        raise Http404("not this person's recording")
    if not assignments.may_mark(recording, request.user):
        raise Http404("not this person's to mark")
    if request.POST.get("action", "mark") == "unmark":
        assignments.unmark_reviewed(recording, by=request.user, request=request)
    else:
        assignments.mark_reviewed(
            recording,
            by=request.user,
            request=request,
            nothing_to_note=request.POST.get("nothing", "") in ("1", "yes", "true"),
        )
    cases.note_activity(recording.case, by=request.user)
    recording.refresh_from_db()
    following = assignments.next_for(request.user, recording)
    return JsonResponse(
        {
            "ok": True,
            "reviewed": recording.reviewed_on is not None,
            "words": assignments.reviewed_words(recording, request.user),
            "next": (
                {
                    "title": following.title,
                    "url": reverse("viewer", args=[following.pk]),
                }
                if following is not None
                else None
            ),
        }
    )


@login_required
def share_who(request: HttpRequest, case_id) -> JsonResponse:
    """The colleagues this Case may be shared with, for the dialog's list."""
    _on_or_404()
    case = _case_they_direct(request, case_id)
    if not sharing.on():
        raise Http404("Sharing is off")
    for_transfer = request.GET.get("for") == "transfer"
    people = list(sharing.candidates(case, with_team=for_transfer))
    if for_transfer:
        # The team first (v1.123.0).
        team = {share.person_id for share in sharing.collaborators(case)}
        people.sort(key=lambda one: (one.pk not in team, one.shown_name.casefold()))
    return JsonResponse(
        {
            "people": [
                {"username": one.username, "name": one.shown_name} for one in people
            ]
        }
    )


@login_required
@require_POST
def share_case(request: HttpRequest, case_id) -> JsonResponse:
    """Share the Case with the person named. The dialog said what that means."""
    _on_or_404()
    case = _case_they_direct(request, case_id)
    if not sharing.on():
        raise Http404("Sharing is off")
    try:
        person = sharing.find(case, request.POST.get("who", ""))
    except sharing.NotFound as why:
        return JsonResponse({"ok": False, "why": str(why)}, status=400)
    share = sharing.grant(case, person, actor=request.user, request=request)
    return JsonResponse({"ok": True, "share": _share_json(share)})


@login_required
@require_POST
def unshare_case(request: HttpRequest, case_id) -> JsonResponse:
    """Remove one Share. What the Collaborator added stays in the Case.

    The owner or an Admin removes anybody's; a Collaborator may remove their
    own, which is how the old owner leaves a Case they handed over.
    """
    _on_or_404()
    case = get_object_or_404(Case, pk=case_id, deleted_on__isnull=True)
    if not sharing.on():
        raise Http404("Sharing is off")
    share = get_object_or_404(
        sharing.Share, pk=request.POST.get("share", ""), case=case
    )
    if not case.may_direct(request.user) and share.person_id != request.user.pk:
        raise Http404("not this person's share")
    sharing.revoke(share, actor=request.user, request=request)
    return JsonResponse(
        {"ok": True, "left": share.person_id == request.user.pk, "where": "/cases"}
    )


@login_required
@require_POST
def transfer_case(request: HttpRequest, case_id) -> JsonResponse:
    """The owner hands the Case to a colleague and stays on it as a Collaborator."""
    _on_or_404()
    case = get_object_or_404(Case, pk=case_id, deleted_on__isnull=True)
    if case.owner_id != request.user.pk:
        raise Http404("not this person's case")
    if not sharing.on():
        raise Http404("Sharing is off")
    try:
        # The team is offered too (v1.123.0): a case is handed to the people
        # on it far more often than to a stranger.
        person = sharing.find(case, request.POST.get("who", ""), with_team=True)
    except sharing.NotFound as why:
        return JsonResponse({"ok": False, "why": str(why)}, status=400)
    sharing.transfer(case, person, actor=request.user, request=request)
    return JsonResponse({"ok": True, "owner": person.shown_name})


def _share_json(share) -> dict:
    return {
        "id": share.pk,
        "name": share.person.shown_name,
        "username": share.person.username,
        "status": share.status,
        "added_on": share.added_on.strftime("%d %b %Y"),
        "last_opened": (
            share.last_opened.strftime("%d %b %Y %H:%M") if share.last_opened else ""
        ),
        "also_owner": share.also_owner,
    }


@login_required
def add_recordings(request: HttpRequest, case_id) -> HttpResponse:
    """The Case page's "Add recordings": the Upload page with the Case chosen."""
    _on_or_404()
    case = _their_case(request, case_id)
    return redirect(f"/upload?case={case.pk}")


def _documents_with_exports(case) -> list:
    """The case's documents, each carrying the address of its comparison's
    Word export when one is done (Phase 8 chapter 6)."""
    from core import comparison

    rows = documents.of_case(case)
    for document in rows:
        document.comparison_export = ""
        home = document.incident or document.recording
        if home is None:
            continue
        made = comparison.of(document, home)
        if made is not None and made.state == comparison.DONE:
            kind = "incident" if document.incident_id else "recording"
            document.comparison_export = (
                reverse(
                    "document-comparison-export", args=[document.case_id, document.pk]
                )
                + f"?{kind}={home.pk}"
            )
    return rows
