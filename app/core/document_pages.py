"""The pages of Documents (Phase 8 chapter 4, part 1): Add the report, the
document page with its pictures beside its words, the pictures themselves,
the download, and Re-link and Remove from the case's Documents tab."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core import documents, incidents
from core.case_pages import _on_or_404, _their_case
from core.documents import READY, Document
from core.recordings import Recording


def _documents_on_or_404() -> None:
    if not documents.on():
        raise Http404("Documents are off.")


def _home_from(request: HttpRequest, case, source) -> dict:
    """The incident or recording named in the request, checked to be the case's."""
    incident = None
    recording = None
    if source.get("incident"):
        incident = incidents.Incident.objects.filter(pk=source.get("incident")).first()
    if source.get("recording"):
        recording = Recording.objects.filter(pk=source.get("recording")).first()
    return documents.home_of(case, incident=incident, recording=recording)


@login_required
def add(request: HttpRequest, case_id) -> HttpResponse:
    """Add the report: the upload page for one document, headed for the
    incident or the recording it is about, saying what fits first."""
    _on_or_404()
    _documents_on_or_404()
    case = _their_case(request, case_id)
    source = request.POST if request.method == "POST" else request.GET
    try:
        home = _home_from(request, case, source)
    except documents.Refused as why:
        messages.error(request, str(why))
        return redirect(f"/case/{case.pk}?tab=documents")
    about = home.get("incident") or home.get("recording")
    context = {
        "page": "cases",
        "case": case,
        "home_kind": "incident" if "incident" in home else "recording",
        "home_name": about.name if "incident" in home else about.title,
        "home_url": about.url()
        if "incident" in home
        else f"/recording/{about.pk}?panel=details",
        "home_id": str(about.pk),
        "most_pages": documents.most_pages(),
        "per_home": documents.per_home(),
        "here": documents.count_at(home),
        "ocr": documents.ocr_on() and documents.ocr_installed(),
        "ocr_missing": documents.ocr_on() and not documents.ocr_installed(),
        "refused": "",
    }
    if request.method == "POST":
        upload = request.FILES.get("file")
        if upload is None:
            context["refused"] = "Choose a PDF first."
            return render(request, "document-add.html", context)
        try:
            document = documents.add(
                case,
                home=home,
                data=upload.read(),
                filename=upload.name,
                title=request.POST.get("title", ""),
                by=request.user,
                request=request,
            )
        except documents.Refused as why:
            context["refused"] = str(why)
            return render(request, "document-add.html", context)
        messages.success(
            request,
            f"{document.title} was added and is being read; it appears on the "
            f"{'incident' if 'incident' in home else 'recording'}'s Details and on "
            "the case's Documents tab.",
        )
        return redirect(context["home_url"])
    return render(request, "document-add.html", context)


def _their_document(request: HttpRequest, case_id, document_id) -> Document:
    _on_or_404()
    case = _their_case(request, case_id)
    return get_object_or_404(
        Document.objects.select_related("case", "incident", "recording", "added_by"),
        pk=document_id,
        case=case,
    )


@login_required
def page(request: HttpRequest, case_id, document_id) -> HttpResponse:
    """The document page: the page pictures down the middle, the words read
    from the open page beside them, a citation lighting its paragraph."""
    document = _their_document(request, case_id, document_id)
    rows = list(document.page_rows.order_by("number"))
    for row in rows:
        # Each paragraph's box as percentages of the page, for the overlay.
        row.boxes = [
            {
                "n": one["n"],
                "left": round(100 * one["box"][0] / row.width, 2),
                "top": round(100 * one["box"][1] / row.height, 2),
                "width": round(100 * (one["box"][2] - one["box"][0]) / row.width, 2),
                "height": round(100 * (one["box"][3] - one["box"][1]) / row.height, 2),
            }
            for one in row.paragraphs
            if row.width and row.height
        ]
    try:
        open_page = max(1, min(int(request.GET.get("page", 1)), max(1, len(rows))))
    except ValueError:
        open_page = 1
    try:
        lit = int(request.GET.get("para", 0))
    except ValueError:
        lit = 0
    return render(
        request,
        "document.html",
        {
            "page": "cases",
            "case": document.case,
            "document": document,
            "rows": rows,
            "open_page": open_page,
            "lit": lit,
            "asked": request.GET.get("q", "").strip(),
        },
    )


@login_required
def picture(request: HttpRequest, case_id, document_id, number: int) -> HttpResponse:
    """One page's picture, off the disk, for whoever may open the case."""
    document = _their_document(request, case_id, document_id)
    path = document.picture_path(number)
    if document.state != READY or not path.exists():
        raise Http404("no such page")
    # FileResponse closes the file itself once the picture has gone out.
    answer = FileResponse(open(path, "rb"), content_type="image/png")  # noqa: SIM115
    answer["Cache-Control"] = "private, max-age=3600"
    return answer


@login_required
def download(request: HttpRequest, case_id, document_id) -> HttpResponse:
    """The PDF as it arrived."""
    from urllib.parse import quote

    document = _their_document(request, case_id, document_id)
    if not document.original_path.exists():
        raise Http404("no such file")
    answer = FileResponse(
        open(document.original_path, "rb"),  # noqa: SIM115 - closed by the response
        content_type="application/pdf",
    )
    name = quote(document.original_filename or f"{document.title}.pdf")
    answer["Content-Disposition"] = f"attachment; filename*=UTF-8''{name}"
    return answer


@login_required
@require_POST
def act(request: HttpRequest, case_id, document_id) -> HttpResponse:
    """Re-link or Remove, from the case's Documents tab; back to it after."""
    document = _their_document(request, case_id, document_id)
    action = request.POST.get("action", "")
    try:
        if action == "relink":
            home = _home_from(request, document.case, request.POST)
            documents.relink(document, home, by=request.user, request=request)
            messages.success(
                request,
                f"{document.title} is now the report for {document.home_name()}.",
            )
        elif action == "remove":
            title = document.title
            documents.remove(document, by=request.user, request=request)
            messages.success(request, f"{title} was removed.")
        else:
            raise Http404("no such action")
    except documents.Refused as why:
        messages.error(request, str(why))
    return redirect(f"/case/{case_id}?tab=documents")
