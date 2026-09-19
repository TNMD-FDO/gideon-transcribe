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
    # The home may be given (from a Details tab) or picked here (from the
    # Documents tab): an incident, a recording, or both.
    home: dict = {}
    refused = ""
    try:
        home = _home_from(request, case, source)
    except documents.Refused as why:
        if request.method == "POST":
            refused = str(why)
    back = f"/case/{case.pk}?tab=documents"
    if "incident" in home:
        back = home["incident"].url()
    elif "recording" in home:
        back = f"/recording/{home['recording'].pk}?panel=details"
    context = {
        "page": "cases",
        "case": case,
        "home_kind": documents.home_words(home) if home else "",
        "home_name": " and ".join(
            one.name if kind == "incident" else one.title for kind, one in home.items()
        ),
        "home_url": back,
        "picked_incident": str(home["incident"].pk) if "incident" in home else "",
        "picked_recording": str(home["recording"].pk) if "recording" in home else "",
        "given": bool(source.get("incident") or source.get("recording"))
        and request.method != "POST",
        "homes": documents.homes_of(case),
        "most_pages": documents.most_pages(),
        "per_home": documents.per_home(),
        "here": documents.count_at(home) if home else 0,
        "ocr": documents.ocr_on() and documents.ocr_installed(),
        "ocr_missing": documents.ocr_on() and not documents.ocr_installed(),
        "refused": refused,
    }
    if request.method == "POST":
        upload = request.FILES.get("file")
        if refused:
            return render(request, "document-add.html", context)
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
            f"{document.title} was added and is being read; it appears on "
            f"{documents.home_words(home)}'s Details and on the case's Documents tab.",
        )
        return redirect(back)
    return render(request, "document-add.html", context)


def _compare_home(request: HttpRequest, document: Document, source):
    """The incident or recording a comparison is against: one the document
    is linked to, named in the request."""
    if source.get("incident") and str(document.incident_id) == str(
        source.get("incident")
    ):
        return document.incident
    if source.get("recording") and str(document.recording_id) == str(
        source.get("recording")
    ):
        return document.recording
    raise Http404(
        "the comparison is against the incident or recording the report is for"
    )


@login_required
def comparison_state(request: HttpRequest, case_id, document_id) -> HttpResponse:
    """The comparison for the layer: its state and its findings."""
    from django.http import JsonResponse

    from core import comparison

    document = _their_document(request, case_id, document_id)
    home = _compare_home(request, document, request.GET)
    return JsonResponse(
        comparison.as_json(comparison.of(document, home), document, home)
    )


@login_required
@require_POST
def compare(request: HttpRequest, case_id, document_id) -> HttpResponse:
    """Compare with the report: one run, on the llm queue."""
    from django.http import JsonResponse

    from core import comparison

    document = _their_document(request, case_id, document_id)
    home = _compare_home(request, document, request.POST)
    made = comparison.ask_for(document, home, by=request.user)
    if made is None:
        _, why = comparison.possible(document, home)
        return JsonResponse({"error": why or "The comparison cannot run."}, status=400)
    return JsonResponse(comparison.as_json(made, document, home))


@login_required
@require_POST
def comparison_act(request: HttpRequest, case_id, document_id) -> HttpResponse:
    """Dismiss, undo, a note, Make it an event, on one finding."""
    from django.http import JsonResponse

    from core import comparison

    document = _their_document(request, case_id, document_id)
    home = _compare_home(request, document, request.POST)
    made = comparison.of(document, home)
    if made is None:
        raise Http404("no comparison yet")
    action = request.POST.get("action", "")
    finding = request.POST.get("finding", "")
    ok = True
    if action == "dismiss":
        ok = comparison.set_dismissed(made, finding, True)
    elif action == "undismiss":
        ok = comparison.set_dismissed(made, finding, False)
    elif action == "note":
        ok = comparison.set_note(made, finding, request.POST.get("note", ""))
    elif action == "make_event":
        at = request.POST.get("at", "")
        try:
            comparison.make_event(
                made,
                finding,
                at=float(at) if at not in ("", None) else None,
                by=request.user,
                request=request,
            )
        except ValueError as why:
            return JsonResponse({"error": str(why)}, status=400)
    else:
        raise Http404("no such action")
    if not ok:
        raise Http404("no such finding")
    return JsonResponse(comparison.as_json(made, document, home))


@login_required
def comparison_export(request: HttpRequest, case_id, document_id) -> HttpResponse:
    """Comparison to Word."""
    from urllib.parse import quote

    from core import audit, comparison

    document = _their_document(request, case_id, document_id)
    home = _compare_home(request, document, request.GET)
    made = comparison.of(document, home)
    if made is None or made.state != "done":
        raise Http404("no comparison yet")
    body = comparison.word(made, request.user.shown_name)
    audit.write(
        audit.Category.EXPORTS,
        "comparison exported",
        actor=request.user,
        request=request,
        affected_user=document.case.owner
        if document.case.owner_id != request.user.pk
        else None,
        object_type="document",
        object_id=document.pk,
        object_label=document.title,
        kind="comparison",
    )
    from core import exports

    answer = HttpResponse(body, content_type=exports.WORD_TYPE)
    answer["Content-Disposition"] = (
        f"attachment; filename*=UTF-8''{quote(comparison.export_name(made))}"
    )
    return answer


@login_required
def state(request: HttpRequest, case_id, document_id) -> HttpResponse:
    """The document for the Report tab: every page's picture and words."""
    from django.http import JsonResponse

    document = _their_document(request, case_id, document_id)
    return JsonResponse(documents.state_json(document))


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
            # The ways back (part 2): the case, and the incident or recording.
            "back_incident": document.incident,
            "back_recording": document.recording,
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
