"""The Preservation copy's part of the case's Details tab (Phase 14 chapter 1).

Four addresses: how it stands (the part as the page draws it, asked again
while one is being made), Make, Stop, and Download.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET, require_POST

from core import audit, cases, pdf_maker, preservation
from core.case_pages import _on_or_404, _their_case
from core.cases import Case


def _told(case) -> dict:
    """The part's state and its drawing, one answer for the page's script."""
    now = preservation.for_page(case)
    return {
        "making": bool(now.get("making")),
        "state": now["state"],
        "html": render_to_string("preservation-part.html", {"p": now, "case": case}),
    }


@login_required
@require_GET
def status(request: HttpRequest, case_id) -> JsonResponse:
    """How the copy stands. Asked every few seconds while one is being made,
    so it writes no Admin access row of its own: the page that asks was
    opened under that rule already."""
    _on_or_404()
    case = get_object_or_404(Case, pk=case_id, deleted_on__isnull=True)
    if not preservation.may_make(case, request.user):
        raise Http404("not this person's case")
    return JsonResponse(_told(case))


@login_required
@require_POST
def make(request: HttpRequest, case_id) -> JsonResponse:
    _on_or_404()
    case = _their_case(request, case_id)
    try:
        preservation.start(case, request.user, request)
    except pdf_maker.Failed as error:
        return JsonResponse({"error": str(error)}, status=409)
    cases.note_activity(case, by=request.user)
    return JsonResponse(_told(case))


@login_required
@require_POST
def stop(request: HttpRequest, case_id) -> JsonResponse:
    _on_or_404()
    case = _their_case(request, case_id)
    preservation.stop(case, request.user, request)
    return JsonResponse(_told(case))


@login_required
@require_GET
def download(request: HttpRequest, case_id) -> FileResponse:
    """The kept copy, streamed from the Case's folder."""
    from urllib.parse import quote

    _on_or_404()
    case = _their_case(request, case_id)
    copy = preservation.ready(case)
    if copy is None or not copy.path.exists():
        raise Http404("no Preservation copy yet")
    audit.write(
        audit.Category.EXPORTS,
        "export made",
        actor=request.user,
        request=request,
        affected_user=case.owner if case.owner_id != request.user.pk else None,
        object_type="case",
        object_id=case.pk,
        object_label=case.name,
        kind="preservation copy",
    )
    cases.note_activity(case, by=request.user)
    answer = FileResponse(copy.path.open("rb"), content_type="application/zip")
    name = preservation.zip_name(case, copy.finished)
    answer["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(name)}"
    answer["Cache-Control"] = "private, no-store"
    return answer
