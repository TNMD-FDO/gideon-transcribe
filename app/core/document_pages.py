"""The pages of Documents (Phase 8 chapter 4, part 1; the shelf of Phase 12
chapter 11): Add a document, the document page with its pictures beside its
words, the pictures themselves, the download, the Comparison page, and
About, Rename and Remove from the case's Documents tab."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core import audit, case_bar, chronology, documents, incidents
from core import home as home_page
from core.case_pages import _on_or_404, _their_case
from core.documents import READY, Document
from core.recordings import Recording

# How long Compare when it is read keeps asking after a document, before it
# gives up quietly (the reading of a long scan can take minutes).
COMPARE_WHEN_READ_WAIT_SECONDS = 30
COMPARE_WHEN_READ_TRIES = 120
MOMENT_WORDS = "Say the moment as hh:mm:ss (or mm:ss into a recording)."


def _documents_on_or_404() -> None:
    if not documents.on():
        raise Http404("Documents are off.")


def _about_from(request: HttpRequest, case, source) -> dict:
    """The incident or recording the request names as what the document is
    about, checked to be the case's; nothing when it names nothing."""
    incident = None
    recording = None
    # One choice since v1.213.0, "About": nothing, an incident, or a camera;
    # a request without it (an older form, a Details tab's address) is read
    # from whichever field is filled, as the form of v1.129.2 was.
    about = (source.get("about") or "").strip()
    # The shelf's More menu (v1.213.0) picks the about as one choice,
    # "nothing", "incident:<id>" or "recording:<id>".
    pick = (source.get("about_pick") or "").strip()
    if pick:
        kind, _, pk = pick.partition(":")
        if kind == "incident" and pk:
            incident = incidents.Incident.objects.filter(pk=pk).first()
        elif kind == "recording" and pk:
            recording = Recording.objects.filter(pk=pk).first()
        return documents.about_of(case, incident=incident, recording=recording)
    if about == "nothing":
        return {}
    if source.get("incident") and about != "recording":
        incident = incidents.Incident.objects.filter(pk=source.get("incident")).first()
    if source.get("recording") and about != "incident":
        recording = Recording.objects.filter(pk=source.get("recording")).first()
    return documents.about_of(case, incident=incident, recording=recording)


@login_required
def add(request: HttpRequest, case_id) -> HttpResponse:
    """Add a document (v1.213.0; Add the report until then): the one page for
    a PDF, its title, an optional about and whether to compare when read."""
    _on_or_404()
    _documents_on_or_404()
    case = _their_case(request, case_id)
    source = request.POST if request.method == "POST" else request.GET
    about: dict = {}
    refused = ""
    try:
        about = _about_from(request, case, source)
    except documents.Refused as why:
        if request.method == "POST":
            refused = str(why)
    shelf = f"/case/{case.pk}?tab=documents"
    picked = ""
    if "incident" in about:
        picked = "incident"
    elif "recording" in about:
        picked = "recording"
    context = {
        "page": "cases",
        "here_case": home_page.here_case_for(request.user, case),
        "case": case,
        "case_bar": case_bar.bar(case, on="documents", here="Add a document"),
        "about_words": documents.about_words(about),
        "picked": picked,
        "picked_incident": str(about["incident"].pk) if "incident" in about else "",
        "picked_recording": (
            str(about["recording"].pk) if "recording" in about else ""
        ),
        "abouts": documents.abouts_of(case),
        "incidents_on": incidents.on(),
        "most_pages": documents.most_pages(),
        "per_case": documents.per_case(),
        "here": documents.count_in(case),
        "ocr": documents.ocr_on() and documents.ocr_installed(),
        "ocr_missing": documents.ocr_on() and not documents.ocr_installed(),
        "compare_on": _compare_on(),
        "compare_choice": (source.get("compare") or "none").strip(),
        "shelf_url": shelf,
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
                about=about,
                data=upload.read(),
                filename=upload.name,
                title=request.POST.get("title", ""),
                by=request.user,
                request=request,
            )
        except documents.Refused as why:
            context["refused"] = str(why)
            return render(request, "document-add.html", context)
        said = f"{document.title} was added and is being read."
        wanted = _compare_wanted(request.POST.get("compare", ""), about, case)
        if wanted:
            from core import comparison, tasks

            tasks.compare_when_read.configure(
                schedule_in={"seconds": COMPARE_WHEN_READ_WAIT_SECONDS}
            ).defer(
                document_id=str(document.pk),
                against=comparison.against_key(wanted),
                user_id=request.user.pk,
                attempt=1,
            )
            said += (
                f" It will be compared against {comparison.against_words(wanted)} "
                "once it is read; the comparison appears under it on this tab."
            )
        messages.success(request, said)
        return redirect(shelf)
    return render(request, "document-add.html", context)


def _compare_on() -> bool:
    from core import comparison

    return comparison.on()


def _compare_wanted(choice: str, about: dict, case):
    """Compare when it is read: the record the add page asked for, or None."""
    if not _compare_on():
        return None
    choice = (choice or "").strip()
    if choice == "case":
        return case
    if choice == "about":
        return about.get("incident") or about.get("recording")
    return None


def compare_when_read(document_id: str, against: str, user_id, attempt: int) -> None:
    """The task's step: ask for the comparison once the document is read;
    while it is still being read, ask again later; give up quietly on a
    document that failed or went."""
    from core import comparison, tasks
    from core.models import User

    document = Document.objects.filter(pk=document_id).select_related("case").first()
    if document is None or document.state == documents.FAILED:
        return
    if document.state != READY:
        if attempt < COMPARE_WHEN_READ_TRIES:
            tasks.compare_when_read.configure(
                schedule_in={"seconds": COMPARE_WHEN_READ_WAIT_SECONDS}
            ).defer(
                document_id=document_id,
                against=against,
                user_id=user_id,
                attempt=attempt + 1,
            )
        return
    home = comparison.home_from_key(document.case, against)
    by = User.objects.filter(pk=user_id).first()
    if home is None or by is None:
        return
    comparison.ask_for(document, home, by=by)


def _compare_home(request: HttpRequest, document: Document, source):
    """The record a comparison is against: the case, or any incident or
    recording of the document's case (v1.213.0; until then only the
    document's own home), named in the request by field or by `against`."""
    from core import comparison

    case = document.case
    if source.get("against"):
        home = comparison.home_from_key(case, source.get("against"))
        if home is None:
            raise Http404("the comparison is against the case or something of it")
        return home
    if source.get("incident"):
        found = incidents.Incident.objects.filter(
            pk=source.get("incident"), case=case
        ).first()
        if found is None:
            raise Http404("that incident is not this case's")
        return found
    if source.get("recording"):
        found = Recording.objects.filter(pk=source.get("recording"), case=case).first()
        if found is None:
            raise Http404("that recording is not this case's")
        return found
    if source.get("case") and str(case.pk) == str(source.get("case")):
        return case
    raise Http404("the comparison is against the case or something of it")


@login_required
def comparison_state(request: HttpRequest, case_id, document_id) -> HttpResponse:
    """The comparison for the page: its state and its findings."""
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
    """Compare against a record: one run, on the llm queue."""
    from django.http import JsonResponse

    from core import comparison

    document = _their_document(request, case_id, document_id)
    home = _compare_home(request, document, request.POST)
    made = comparison.ask_for(document, home, by=request.user)
    # From the shelf's Compare against menu (v1.213.0), a plain form: the
    # person lands on the Comparison page, which shows the run going.
    to_page = request.POST.get("next") == "page"
    if made is None:
        _, why = comparison.possible(document, home)
        if to_page:
            messages.error(request, why or "The comparison cannot run.")
            return redirect(f"/case/{document.case_id}?tab=documents")
        return JsonResponse({"error": why or "The comparison cannot run."}, status=400)
    if to_page:
        return redirect(comparison.page_url(document, home))
    return JsonResponse(comparison.as_json(made, document, home))


@login_required
@require_POST
def comparison_act(request: HttpRequest, case_id, document_id) -> HttpResponse:
    """Dismiss, undo, a note, Make it a note, on one finding."""
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
    elif action == "make_note":
        at = request.POST.get("at", "")
        moment = chronology.a_moment(at) if at not in ("", None) else None
        # A moment typed in words (v1.213.0) for a Not on camera finding: a
        # time of day on an incident's clock, or a time into a recording.
        typed = request.POST.get("at_words", "").strip()
        if moment is None and typed:
            moment = _moment_from_words(typed, home)
            if moment is None:
                return JsonResponse({"error": MOMENT_WORDS}, status=400)
        try:
            comparison.make_note(
                made,
                finding,
                at=moment,
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


def _moment_from_words(typed: str, home) -> float | None:
    """ "hh:mm:ss" on an incident's clock as seconds into the incident, or
    "mm:ss" / "hh:mm:ss" as seconds into a recording; None when unreadable."""
    parts = typed.replace(".", ":").split(":")
    try:
        numbers = [int(one) for one in parts]
    except ValueError:
        return None
    if not 2 <= len(numbers) <= 3 or any(one < 0 for one in numbers):
        return None
    if len(numbers) == 2:
        numbers = [0, *numbers]
    seconds = numbers[0] * 3600 + numbers[1] * 60 + numbers[2]
    if isinstance(home, incidents.Incident):
        if home.clock_zero is None:
            return float(seconds)
        # The short way round midnight, as the incident's own clock reads.
        return float(incidents._wrapped(seconds - home.clock_zero))
    return float(seconds)


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
def comparison_page(request: HttpRequest, case_id, document_id) -> HttpResponse:
    """The Comparison page (Phase 12 chapter 11, v1.213.0): a page of its own
    under the case bar with Documents lit, the report against its record,
    the findings in the wide column and the report's page beside them."""
    from core import comparison

    document = _their_document(request, case_id, document_id)
    if not comparison.on():
        raise Http404("the comparison is off")
    if document.is_picture:
        raise Http404("a picture of the map has no words to compare")
    home = _compare_home(request, document, request.GET)
    made = comparison.of(document, home)
    told = comparison.as_json(made, document, home)
    others = [
        one
        for one in comparison.shelf_rows(document)
        if one["against"] != comparison.against_key(home)
    ]
    targets = [
        one
        for one in comparison.targets_of(document)
        if not one["exists"] and one["key"] != comparison.against_key(home)
    ]
    return render(
        request,
        "comparison.html",
        {
            "page": "cases",
            "case": document.case,
            "case_bar": case_bar.bar(document.case, on="documents", here="Comparison"),
            "here_case": home_page.here_case_for(request.user, document.case),
            "document": document,
            "against_key": comparison.against_key(home),
            "against_words": told["against_words"],
            "home_kind": told["home"],
            "home_id": told["home_id"],
            "state_url": (
                f"/case/{document.case_id}/document/{document.pk}/comparison"
                f"?against={comparison.against_key(home)}"
            ),
            "document_state_url": (
                f"/case/{document.case_id}/document/{document.pk}/state"
            ),
            "others": others,
            "targets": targets,
            "shelf_url": f"/case/{document.case_id}?tab=documents",
            "told": told,
        },
    )


@login_required
def state(request: HttpRequest, case_id, document_id) -> HttpResponse:
    """The document for the Comparison page and the paragraph card: every
    page's picture and words."""
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
    from core import comparison

    return render(
        request,
        "document.html",
        {
            "page": "cases",
            "case": document.case,
            "case_bar": case_bar.bar(
                document.case, on="documents", here=document.title
            ),
            "here_case": home_page.here_case_for(request.user, document.case),
            "document": document,
            "rows": rows,
            "open_page": open_page,
            "lit": lit,
            "asked": request.GET.get("q", "").strip(),
            # The ways on (v1.213.0): what it is about, and its comparisons.
            "about_incident": document.incident,
            "about_recording": document.recording,
            "comparisons": (
                comparison.shelf_rows(document) if not document.is_picture else []
            ),
        },
    )


@login_required
def picture(request: HttpRequest, case_id, document_id, number: int) -> HttpResponse:
    """One page's picture, off the disk, for whoever may open the case."""
    document = _their_document(request, case_id, document_id)
    path = document.picture_path(number)
    kind = "image/png"
    # A timelapse's page moves when it is asked to (v1.241.0): the Document
    # page shows the GIF itself, the shelf's small picture its first frame.
    if document.is_timelapse and request.GET.get("moving"):
        path, kind = document.original_path, "image/gif"
    if document.state != READY or not path.exists():
        raise Http404("no such page")
    # FileResponse closes the file itself once the picture has gone out.
    answer = FileResponse(open(path, "rb"), content_type=kind)  # noqa: SIM115
    # Never kept on the disk of the machine that looked (v1.130.0): a report's
    # pages are privileged, like every playback copy.
    answer["Cache-Control"] = "private, no-store"
    return answer


@login_required
def download(request: HttpRequest, case_id, document_id) -> HttpResponse:
    """The PDF as it arrived."""
    from urllib.parse import quote

    document = _their_document(request, case_id, document_id)
    if not document.original_path.exists():
        raise Http404("no such file")
    kind, ending = "application/pdf", "pdf"
    if document.is_timelapse:
        kind, ending = "image/gif", "gif"
    elif document.is_picture:
        kind, ending = "image/png", "png"
    if document.is_timelapse:
        # A timelapse is a file the app made to be taken away, as a Clip is
        # (v1.241.0): its download is a row. A report's own PDF and a
        # picture's PNG write none, as before.
        audit.write(
            audit.Category.EXPORTS,
            "Timelapse downloaded",
            actor=request.user,
            request=request,
            affected_user=document.case.owner
            if document.case.owner_id != request.user.pk
            else None,
            object_type="document",
            object_id=document.pk,
            object_label=document.title,
            kind=documents.TIMELAPSE,
        )
    answer = FileResponse(
        open(document.original_path, "rb"),  # noqa: SIM115 - closed by the response
        content_type=kind,
    )
    name = quote(document.original_filename or f"{document.title}.{ending}")
    answer["Content-Disposition"] = f"attachment; filename*=UTF-8''{name}"
    return answer


@login_required
@require_POST
def act(request: HttpRequest, case_id, document_id) -> HttpResponse:
    """About, Rename or Remove, from the case's Documents tab; back to it after."""
    document = _their_document(request, case_id, document_id)
    action = request.POST.get("action", "")
    try:
        if action in ("about", "relink"):
            about = _about_from(request, document.case, request.POST)
            documents.set_about(document, about, by=request.user, request=request)
            words = documents.about_words(about)
            messages.success(
                request,
                f"{document.title} is now {words}."
                if words
                else f"{document.title} is about nothing in particular now.",
            )
        elif action == "rename":
            was = document.title
            documents.rename(
                document,
                request.POST.get("title", ""),
                by=request.user,
                request=request,
            )
            messages.success(request, f"{was} is now called {document.title}.")
        elif action == "remove":
            title = document.title
            documents.remove(document, by=request.user, request=request)
            messages.success(request, f"{title} was removed.")
        else:
            raise Http404("no such action")
    except documents.Refused as why:
        messages.error(request, str(why))
    return redirect(f"/case/{case_id}?tab=documents")
