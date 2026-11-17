"""The Preservation copy's pages (Phase 14).

Chapter 1: the part on the case's Details tab, by four addresses: how it
stands (asked again while one is being made), Make, Stop, and Download.
Chapter 2: the copy of a Case in the Recycle bin, and Archived, where the
copies of Cases that are gone for good wait their days.
"""

from __future__ import annotations

from urllib.parse import quote

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from core import audit, cases, exports, preservation, uploads
from core.case_pages import _on_or_404, _their_binned_case, _their_case
from core.cases import Case
from core.preservation import ArchivedCopy


def _told(case) -> dict:
    """The part's state and its drawing, one answer for the page's script."""
    now = preservation.for_page(case)
    return {
        "making": bool(now.get("making")),
        "state": now["state"],
        "html": render_to_string("preservation-part.html", {"p": now, "case": case}),
    }


def _zip(path, name: str) -> FileResponse:
    answer = FileResponse(path.open("rb"), content_type="application/zip")
    answer["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(name)}"
    answer["Cache-Control"] = "private, no-store"
    return answer


def _export_row(request, owner, case_id, case_name: str) -> None:
    """One "export made" row per download, wherever the copy was taken from."""
    audit.write(
        audit.Category.EXPORTS,
        "export made",
        actor=request.user,
        request=request,
        affected_user=(
            owner if owner is not None and owner.pk != request.user.pk else None
        ),
        object_type="case",
        object_id=case_id,
        object_label=case_name,
        kind="preservation copy",
    )


# The Details tab's part (chapter 1) ---------------------------------------------


@login_required
@require_GET
def status(request: HttpRequest, case_id) -> JsonResponse:
    """How the copy stands. Asked every few seconds while one is being made,
    so it writes no Admin access row of its own: the page that asks was
    opened under that rule already. When the Case has gone, by the Delete the
    making was begun for (chapter 2), it says so and where its copy is."""
    _on_or_404()
    case = Case.objects.filter(pk=case_id, deleted_on__isnull=True).first()
    if case is None:
        kept = ArchivedCopy.objects.filter(case_id_was=case_id).first()
        if kept is None or not _is_theirs(request, kept):
            raise Http404("no such case")
        return JsonResponse(
            {"gone": True, "name": kept.case_name, "days": preservation.keep_days()}
        )
    if not preservation.may_make(case, request.user):
        raise Http404("not this person's case")
    return JsonResponse(_told(case))


@login_required
@require_POST
def make(request: HttpRequest, case_id) -> JsonResponse:
    _on_or_404()
    case = _their_case(request, case_id)
    preservation.start(case, request.user, request)
    cases.note_activity(case, by=request.user)
    return JsonResponse(_told(case))


@login_required
@require_POST
def stop(request: HttpRequest, case_id) -> JsonResponse:
    """Stop a making. When it was a Delete's, the Case is kept."""
    _on_or_404()
    case = _their_case(request, case_id)
    preservation.stop(case, request.user, request)
    return JsonResponse(_told(case))


@login_required
@require_GET
def download(request: HttpRequest, case_id) -> FileResponse:
    """The kept copy, streamed from the Case's folder."""
    _on_or_404()
    case = _their_case(request, case_id)
    copy = preservation.ready(case)
    if copy is None or not copy.path.exists():
        raise Http404("no Preservation copy yet")
    _export_row(request, case.owner, case.pk, case.name)
    preservation.downloaded(copy, request.user)
    cases.note_activity(case, by=request.user)
    return _zip(copy.path, preservation.zip_name(case, copy.finished))


# A Case in the Recycle bin (chapter 2) ------------------------------------------


@login_required
@require_GET
def bin_download(request: HttpRequest, case_id) -> FileResponse:
    """The copy made when the Retention policy binned the Case."""
    _on_or_404()
    case, copy = _their_bin_copy(request, case_id)
    if preservation.taken_by_another(copy, request.user) and "again" not in request.GET:
        return _already_taken(
            request, copy, case.name, reverse("archived"), request.path + "?again=1"
        )
    _export_row(request, case.owner, case.pk, case.name)
    preservation.downloaded(copy, request.user)
    return _zip(copy.path, preservation.zip_name(case, copy.finished))


@login_required
@require_POST
def bin_make(request: HttpRequest, case_id) -> JsonResponse:
    """Make the copy of a binned Case that has none: made here and now."""
    _on_or_404()
    case = _their_binned_case(request, case_id)
    copy = preservation.make_now(case, by=request.user)
    if copy.state != preservation.READY:
        return JsonResponse(
            {"error": copy.reason or "It could not be made."}, status=409
        )
    return JsonResponse({"ok": True})


# Archived (chapter 2) ------------------------------------------------------------


def _is_theirs(request, kept: ArchivedCopy) -> bool:
    """A copy's owners (the Case's Owner and whoever was marked Also an
    owner, chapter 3) and Admins."""
    return preservation.is_an_owner(kept, request.user) or request.user.is_admin


def _may_remove(request, kept: ArchivedCopy) -> bool:
    """Remove now stays the Case's Owner's and the Admins'."""
    return kept.owner_id == request.user.pk or request.user.is_admin


def _already_taken(request, copy, case_name: str, where: str, again: str):
    """Asked before a copy somebody else took is given a second time."""
    return render(
        request,
        "copy-taken.html",
        {
            "page": "cases",
            "case_name": case_name,
            "by": copy.downloaded_by_name,
            "when": copy.downloaded_at,
            "saved": copy.taken_how == "saved",
            "where": where,
            "again": again,
        },
    )


def _their_bin_copy(request, case_id):
    """A binned Case's copy, for its owners and Admins: a person marked Also
    an owner reaches it by the link their message carries, though the
    Recycle bin page is not theirs."""
    case = get_object_or_404(Case, pk=case_id, deleted_on__isnull=False)
    people = {one.pk for one in preservation.owners_of(case)}
    if request.user.pk not in people and not request.user.is_admin:
        raise Http404("not this person's case")
    copy = preservation.ready(case)
    if copy is None or not copy.path.exists():
        raise Http404("no Preservation copy")
    return case, copy


def _their_archived(request, copy_id) -> ArchivedCopy:
    """A copy in Archived, if this person may act on it: its owner, and
    Admins. Anybody else is told there is none."""
    kept = get_object_or_404(ArchivedCopy, pk=copy_id)
    if not _is_theirs(request, kept):
        raise Http404("not this person's copy")
    return kept


def _how(kept: ArchivedCopy, viewer) -> str:
    if kept.how == preservation.RETENTION:
        return "by the retention policy"
    if kept.how == preservation.ADMIN:
        return f"by {kept.gone_by_name or 'an Admin'}, an Admin"
    return "by you" if kept.owner_id == viewer.pk else f"by {kept.owner_name}"


def _archived_row(kept: ArchivedCopy, viewer) -> dict:
    from datetime import timedelta

    left = max(0, preservation.days_left(kept))
    others = [one["name"] for one in kept.also_owners or []]
    return {
        "copy": kept,
        # Named only when the copy has more than one owner (chapter 3).
        "owners": [kept.owner_name, *others] if others else [],
        "taken": preservation.taken_words(kept),
        "by_another": preservation.taken_by_another(kept, viewer),
        "may_remove": kept.owner_id == viewer.pk or viewer.is_admin,
        "how": _how(kept, viewer),
        "size": uploads.as_size(kept.size_bytes),
        "days_left": left,
        "until": kept.gone_on + timedelta(days=preservation.keep_days()),
        "owner_gone": kept.owner is None or kept.owner.deactivated_at is not None,
    }


@login_required
def archived(request: HttpRequest) -> HttpResponse:
    """Where the copies of Cases that are gone for good wait their days.

    The owner sees their own; an Admin sees everybody's, with an owner
    filter, as on the Recycle bin. Hidden while Folder management is off.
    """
    _on_or_404()
    owner_filter = request.GET.get("owner", "").strip()
    kept = preservation.archived_for(request.user, owner_filter)
    rows = [_archived_row(one, request.user) for one in kept.select_related("owner")]
    return render(
        request,
        "archived.html",
        {
            "page": "cases",
            "rows": rows,
            "owner_filter": owner_filter,
            "owners": (
                sorted({one["copy"].owner_name for one in rows})
                if request.user.is_admin and not owner_filter
                else []
            ),
            "keep_days": preservation.keep_days(),
            "who": "archived",
            "binned": (
                Case.objects.filter(deleted_on__isnull=False).count()
                if request.user.is_admin
                else cases.binned_for(request.user).count()
            ),
            "archived_waiting": preservation.waiting_count(request.user),
        },
    )


@login_required
@require_GET
def archived_download(request: HttpRequest, copy_id) -> FileResponse:
    _on_or_404()
    kept = _their_archived(request, copy_id)
    if not kept.path.exists():
        raise Http404("the copy's file is gone")
    if preservation.taken_by_another(kept, request.user) and "again" not in request.GET:
        return _already_taken(
            request,
            kept,
            kept.case_name,
            reverse("archived"),
            request.path + "?again=1",
        )
    _export_row(request, kept.owner, kept.case_id_was, kept.case_name)
    preservation.downloaded(kept, request.user)
    name = (
        f"{exports.safe_name(kept.case_name)} - preservation copy "
        f"{kept.made:%Y-%m-%d}.zip"
    )
    return _zip(kept.path, name)


@login_required
@require_POST
def archived_remove(request: HttpRequest, copy_id) -> JsonResponse:
    """Remove now: the owner's, or an Admin's, behind the page's confirmation."""
    _on_or_404()
    kept = _their_archived(request, copy_id)
    if not _may_remove(request, kept):
        raise Http404("not this person's to remove")
    cause = (
        preservation.OWNER if kept.owner_id == request.user.pk else preservation.ADMIN
    )
    preservation.remove(kept, cause, actor=request.user, request=request)
    return JsonResponse({"ok": True})


# Mark as saved (chapter 3) -----------------------------------------------------------


def _saved(request, copy, case_id, case_name: str, owner):
    """Asked once by a page, then marked: the message's link is only ever a
    question, since a mail system may open a link by itself."""
    if request.method == "POST":
        preservation.mark_saved(copy, case_id, case_name, owner, request.user, request)
        return redirect("archived")
    return render(
        request,
        "copy-saved.html",
        {
            "page": "cases",
            "case_name": case_name,
            "taken": preservation.taken_words(copy),
            "where": reverse("archived"),
        },
    )


@login_required
def archived_saved(request: HttpRequest, copy_id) -> HttpResponse:
    _on_or_404()
    kept = _their_archived(request, copy_id)
    return _saved(request, kept, kept.case_id_was, kept.case_name, kept.owner)


@login_required
def bin_saved(request: HttpRequest, case_id) -> HttpResponse:
    _on_or_404()
    case, copy = _their_bin_copy(request, case_id)
    return _saved(request, copy, case.pk, case.name, case.owner)
