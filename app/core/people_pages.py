"""The Speakers tab of a Case page, and its acts.

The tab lists the Case's People, where each appears, and the Recordings whose
Speakers are still unnamed. Rename, Edit, Merge into and Delete act on a
Person across the whole Case; every act is a form that posts and comes back to
the tab, and each writes its own audit row through core/people.py, never with
a name in it. Hidden, like every Cases page, while Folder management is Off.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from core import cases, people
from core.case_pages import _on_or_404, _their_case
from core.people import Person


def tab_context(case) -> dict:
    """What the tab shows: the People with where they appear, and the unnamed."""
    rows = []
    for person in case.people.all():
        where = person.recordings()
        rows.append(
            {
                "person": person,
                "first_line": (person.notes or "").strip().splitlines()[0]
                if (person.notes or "").strip()
                else "",
                "recordings": where,
                "others": [one for one in case.people.all() if one.pk != person.pk],
            }
        )
    unnamed = people.unnamed_by_recording(case)
    return {
        "people": rows,
        "unnamed": unnamed,
        "roles": people.roles(),
        "people_line": (
            f"{len(rows)} {'person' if len(rows) == 1 else 'people'}, "
            f"{len(unnamed)} recording{'' if len(unnamed) == 1 else 's'} "
            "with unnamed speakers"
        ),
    }


def _back(case) -> HttpResponse:
    return redirect(reverse("case", args=[case.pk]) + "?tab=speakers")


@login_required
@require_POST
def add_person(request: HttpRequest, case_id) -> HttpResponse:
    _on_or_404()
    case = _their_case(request, case_id)
    name = request.POST.get("name", "").strip()
    if not name:
        return _back(case)
    if people.find(case, name) is not None:
        request.session["people_said"] = f"{name} is already in this case."
        return _back(case)
    people.join_or_create(
        case,
        name,
        by=request.user,
        how="typed on the tab",
        request=request,
        role=request.POST.get("role", "").strip(),
        notes=request.POST.get("notes", "").strip(),
    )
    cases.note_activity(case, by=request.user)
    return _back(case)


@login_required
@require_POST
def person_action(request: HttpRequest, person_id) -> HttpResponse:
    _on_or_404()
    person = get_object_or_404(Person, pk=person_id)
    case = _their_case(request, person.case_id)
    action = request.POST.get("action", "")
    try:
        if action == "rename":
            people.rename(
                person, request.POST.get("name", ""), by=request.user, request=request
            )
        elif action == "edit":
            people.edit(
                person,
                role=request.POST.get("role", ""),
                notes=request.POST.get("notes", ""),
                by=request.user,
                request=request,
            )
        elif action == "merge":
            survivor = get_object_or_404(
                Person, pk=request.POST.get("into", ""), case=case
            )
            people.merge(person, survivor, by=request.user, request=request)
        elif action == "delete":
            people.delete(person, by=request.user, request=request)
        else:
            return _back(case)
    except ValueError as refused:
        request.session["people_said"] = str(refused)
        return _back(case)
    cases.note_activity(case, by=request.user)
    return _back(case)
