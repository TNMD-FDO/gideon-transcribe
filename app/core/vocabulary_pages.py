"""The Case vocabulary's pages (Phase 9 chapter 2): plain forms on the case
page and the Speakers tab, each going back where it came from."""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from core import cases, people, vocabulary
from core.case_pages import _case_they_run, _on_or_404, _their_case
from core.people import CaseTerm, Person


def _back(case, tab: str = "") -> HttpResponse:
    url = reverse("case", args=[case.pk])
    return redirect(f"{url}?tab={tab}" if tab else url)


@login_required
@require_POST
def term_action(request: HttpRequest, case_id) -> HttpResponse:
    """Add a term, change a term's or a Person's spellings, or remove a term.
    Anyone with the case adds or changes; the owner and an Admin remove."""
    _on_or_404()
    case = _their_case(request, case_id)
    action = request.POST.get("action", "")
    if action == "add":
        vocabulary.add_term(
            case,
            request.POST.get("term", ""),
            request.POST.get("spellings", ""),
            by=request.user,
            request=request,
        )
    elif action == "spellings":
        kind = request.POST.get("kind", "")
        if kind == "person":
            person = get_object_or_404(Person, pk=request.POST.get("id", ""), case=case)
            vocabulary.set_person_spellings(
                person,
                request.POST.get("spellings", ""),
                by=request.user,
                request=request,
            )
        else:
            term = get_object_or_404(CaseTerm, pk=request.POST.get("id", ""), case=case)
            vocabulary.set_term_spellings(
                term,
                request.POST.get("spellings", ""),
                by=request.user,
                request=request,
            )
    elif action == "remove":
        # Removing is the owner's, as removing a person from the Team is.
        case = _case_they_run(request, case_id)
        term = get_object_or_404(CaseTerm, pk=request.POST.get("id", ""), case=case)
        vocabulary.remove_term(term, by=request.user, request=request)
    cases.note_activity(case, by=request.user)
    return _back(case)


@login_required
@require_POST
def side_rule(request: HttpRequest, case_id) -> HttpResponse:
    """The Speakers tab's one sentence: on every call in this case, Side n is
    a Person; or the rule removed."""
    _on_or_404()
    case = _their_case(request, case_id)
    if request.POST.get("action") == "remove":
        vocabulary.clear_side_rule(case, by=request.user, request=request)
        request.session["people_said"] = (
            "The rule is removed; the names stay as they are."
        )
        return _back(case, "speakers")
    try:
        side = int(request.POST.get("side", "1"))
    except ValueError:
        side = 1
    side = 1 if side not in (1, 2) else side
    name = " ".join(request.POST.get("name", "").split())
    chosen = request.POST.get("person", "")
    person = None
    if chosen:
        person = get_object_or_404(Person, pk=chosen, case=case)
    elif name:
        person, _ = people.join_or_create(
            case, name, by=request.user, how="side rule", request=request
        )
    if person is None:
        request.session["people_said"] = "Pick a person, or type a name, for the side."
        return _back(case, "speakers")
    named = vocabulary.set_side_rule(
        case, side, person, by=request.user, request=request
    )
    request.session["people_said"] = (
        f"Side {side} is {person.name} on every call in this case: "
        f"{named} call{'' if named == 1 else 's'} named now, and each new one "
        "as it lands."
    )
    cases.note_activity(case, by=request.user)
    return _back(case, "speakers")
