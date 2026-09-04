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
from django.db.models import Q
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core import audit, cases, exports, retention, settings_store, uploads
from core.cases import Case
from core.jobs import Segment
from core.recordings import Recording

# How many hits one search shows. A person looking for a phrase wants the
# first few; a thousand rows would be a worse answer, not a fuller one.
MOST_HITS = 200


def _on_or_404() -> None:
    if not cases.folder_management_on():
        raise Http404("Folder management is off")


def _their_case(request, case_id) -> Case:
    """The Case, if this person may open it, and the Admin access row if not theirs."""
    case = get_object_or_404(Case, pk=case_id, deleted_on__isnull=True)
    if not case.may_be_opened_by(request.user):
        raise Http404("not this person's case")
    if case.owner_id != request.user.pk:
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


@login_required
def cases_page(request: HttpRequest) -> HttpResponse:
    """Where a person lands when Cases are on: their own, and nothing else.

    Admins see every Case, because they must be able to act on a leaver's.
    The Cases shared with a person are the Sharing chapter's and are not here.
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

    rows = [_as_row(one) for one in mine]
    other_rows = [_as_row(one) for one in others]
    if expiring:
        rows = [one for one in rows if one["warned"]]
        other_rows = [one for one in other_rows if one["warned"]]

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
            "others": other_rows,
            "name_filter": filter_text,
            "expiring": expiring,
            "owner_deactivated": owner_deactivated,
            "binned": binned,
            "storage_warning": uploads.storage_warning(request.user),
        },
    )


def _as_row(case: Case) -> dict:
    left = retention.days_left(case)
    return {
        "case": case,
        "recordings": case.recordings.count(),
        "size": uploads.as_gb(case.disk_bytes()),
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
        "size": uploads.as_gb(case.disk_bytes()),
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
    """Where clicking a Case takes somebody.

    Straight into the player, on the newest Recording with a Transcript, with
    the rest of the Case beside it. A Case with nothing to play yet opens its
    own page instead, which is where Add recordings is.
    """
    for one in case.recordings.order_by("-created"):
        if hasattr(one, "transcript"):
            return reverse("viewer", args=[one.pk])
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

    asked = request.GET.get("q", "").strip()
    # One of the four tabs the chapter gives this page. Speakers and Chat
    # belong to chapters that are not built.
    tab = "clips" if request.GET.get("tab") == "clips" else "recordings"

    return render(
        request,
        "case.html",
        {
            "page": "cases",
            "case": case,
            "tab": tab,
            "clips_here": _clips_in(case, request.user) if tab == "clips" else [],
            "is_owner": case.owner_id == request.user.pk,
            "recordings": _rows_for(case),
            "asked": asked,
            "hits": _search(case, asked) if asked else None,
            "types": cases.recording_types(),
            "size": uploads.as_gb(case.disk_bytes()),
        },
    )


def _clips_in(case: Case, asker) -> list:
    """Every Clip of every Recording in the Case, oldest Recording first.

    The Clips page in the navigation stays the Workspace's own list, so a Clip
    is listed in one place and not two.
    """
    from core.clip_pages import _row
    from core.clips import Clip

    if not settings_store.get("clips_available"):
        return []

    return [
        _row(one, asker=asker)
        for one in Clip.objects.filter(recording__case=case)
        .select_related("recording", "user")
        .order_by("recording__created", "created")
    ]


def _rows_for(case: Case) -> list:
    """Each Recording with the words its row shows about its Speakers and state."""
    rows = []
    for one in case.recordings.order_by("-created"):
        job = one.jobs.order_by("-created").first()
        one.being_replaced = bool(
            job is not None and job.is_live and job.batch.is_reprocessing
        )
        one.in_the_queue = bool(job is not None and job.is_live)
        one.speakers_in_words = _speakers_in_words(one)
        one.length = exports.clock(one.duration_seconds or 0)
        rows.append(one)
    return rows


def _speakers_in_words(recording: Recording) -> str:
    """Reads "2 named, 1 unnamed", and says nothing at all when there are none."""
    transcript = getattr(recording, "transcript", None)
    if transcript is None:
        return ""
    labels = set(
        Segment.objects.filter(transcript=transcript)
        .exclude(speaker="")
        .order_by("speaker")
        .values_list("speaker", flat=True)
        .distinct()
    )
    if not labels:
        return ""
    named = {one for one in labels if not one.upper().startswith("SPEAKER_")}
    unnamed = len(labels) - len(named)
    parts = []
    if named:
        parts.append(f"{len(named)} named")
    if unnamed:
        parts.append(f"{unnamed} unnamed")
    return ", ".join(parts)


def _search(case: Case, asked: str) -> list:
    """Transcript text and Speaker names across one Case.

    Every hit is a Segment, and opening it opens the viewer at that time. The
    term is never written to the audit log, here or anywhere.
    """
    found = (
        Segment.objects.filter(transcript__recording__case=case)
        .filter(Q(text__icontains=asked) | Q(speaker__icontains=asked))
        .select_related("transcript__recording")
        .order_by("transcript__recording__created", "start")[:MOST_HITS]
    )
    return [
        {
            "recording": one.transcript.recording,
            "start": one.start,
            # A timestamp, because that is what a person reading a hit wants
            # and it is the same shape a Citation is written in.
            "at": exports.clock(one.start),
            "speaker": one.speaker,
            "text": one.text,
        }
        for one in found
    ]


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
    case = _their_case(request, case_id)
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
    case = _their_case(request, case_id)
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
        "size": uploads.as_gb(case.disk_bytes()),
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
    if case.owner_id != request.user.pk and not request.user.is_admin:
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
                {"id": str(one.pk), "name": one.name}
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

    may_move = recording.user_id == request.user.pk or (
        recording.case is not None and recording.case.owner_id == request.user.pk
    )
    if not may_move and not request.user.is_admin:
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
    if not case.may_be_opened_by(request.user):
        raise Http404("not this person's case")

    cases.move_recording(
        recording,
        case,
        actor=request.user,
        description=request.POST.get("description", "").strip(),
        request=request,
    )

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


@login_required
def add_recordings(request: HttpRequest, case_id) -> HttpResponse:
    """The Case page's "Add recordings": the Upload page with the Case chosen."""
    _on_or_404()
    case = _their_case(request, case_id)
    return redirect(f"/upload?case={case.pk}")
