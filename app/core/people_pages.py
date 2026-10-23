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


def tab_context(case, user=None) -> dict:
    """What the tab shows: the People with where they appear, and the
    unnamed. A handful of queries for the case (v1.134.0): the People, every
    Speaker's recordings grouped, the recordings' rows once."""
    from core.recordings import Recording

    everyone = list(case.people.all())
    spoken = people.speakers_in(case)
    wanted = {
        recording_id
        for person in everyone
        for recording_id in spoken.get(person.name.strip().casefold(), {})
    }
    recordings = {one.pk: one for one in Recording.objects.filter(pk__in=list(wanted))}
    rows = []
    for person in everyone:
        rows.append(
            {
                "person": person,
                "first_line": (person.notes or "").strip().splitlines()[0]
                if (person.notes or "").strip()
                else "",
                "recordings": person.recordings(spoken, recordings),
                "others": [one for one in everyone if one.pk != person.pk],
            }
        )
    unnamed = people.unnamed_by_recording(case, spoken)
    # The Case remembers (v1.144.0): the Voice column, the alarms, the counts.
    from core import voice_prints

    voice = voice_prints.tab_rows(case, everyone)
    from core import voice_book

    for row in rows:
        row["voice"] = voice["per_person"].get(row["person"].pk)
        # The unit's voice book (v1.146.0): kept, an offer, or a role not kept.
        row["book"] = voice_book.tab_line(row["person"], user) if user else None
        # The card's facts (v1.151.0, the tab as people): what waits on this
        # person, and the kinds the filter chips sort by.
        v = row["voice"] or {}
        row["waiting_count"] = len(v.get("waiting") or [])
        kinds = []
        if v.get("has_print"):
            kinds.append("voice")
        else:
            kinds.append("novoice")
        if (row["book"] or {}).get("state") == "kept":
            kinds.append("kept")
        if row["waiting_count"]:
            kinds.append("waiting")
        row["kinds"] = " ".join(kinds)
        row["lines_heard"] = len(row["recordings"])
    # Anyone with something waiting first, then by how much they are heard,
    # the same order every time.
    rows.sort(
        key=lambda row: (-row["waiting_count"], -row["lines_heard"], row["person"].name)
    )
    counts = {
        "all": len(rows),
        "voice": sum(1 for row in rows if "voice" in row["kinds"].split()),
        "novoice": sum(1 for row in rows if "novoice" in row["kinds"].split()),
        "kept": sum(1 for row in rows if "kept" in row["kinds"].split()),
        "waiting": sum(1 for row in rows if "waiting" in row["kinds"].split()),
    }
    # What needs you (v1.151.0): the review workflow in a strip of cards,
    # each pointing at the place that decides.
    # (`unnamed` is (recording, count) here; the case page adds each one's
    # minutes of talk and fills unnamed_minutes in.)
    needs = {
        "unnamed_voices": sum(one[1] for one in unnamed),
        "unnamed_recordings": len(unnamed),
        "unnamed_minutes": 0,
        "first_unnamed": unnamed[0][0] if unnamed else None,
        "waiting": voice["waiting"],
        # One button per call and speaker, though two people may claim it.
        "waiting_rows": list(
            {
                (one["recording"].pk, one["speaker"]): one
                for row in rows
                for one in ((row["voice"] or {}).get("waiting") or [])
            }.values()
        )[:3],
        "alarms": len(voice["side_alarms"]),
    }
    line = (
        f"{len(rows)} {'person' if len(rows) == 1 else 'people'}, "
        f"{len(unnamed)} recording{'' if len(unnamed) == 1 else 's'} "
        "with unnamed speakers"
    )
    if voice["remember"] and voice["any_voice"]:
        line += (
            f". Voices are remembered for this case: {voice['with_print']} "
            f"{'person has' if voice['with_print'] == 1 else 'people have'} a voice "
            f"print, and {voice['waiting']} "
            f"voice{'' if voice['waiting'] == 1 else 's'} "
            f"wait{'s' if voice['waiting'] == 1 else ''} to be decided on "
            f"{'its call' if voice['waiting'] == 1 else 'their calls'}"
        )
    return {
        "people": rows,
        "unnamed": unnamed,
        "roles": people.roles(),
        "people_line": line,
        "voice": voice,
        "people_counts": counts,
        "needs": needs,
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
            # Also called and Also heard as (v1.156.0), on the person's card.
            if "called" in request.POST or "spellings" in request.POST:
                from core import vocabulary

                vocabulary.set_person_spellings(
                    person,
                    request.POST.get("spellings", ""),
                    called=request.POST.get("called", ""),
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
        elif action in ("keep", "stop-keeping"):
            # The unit's voice book (v1.146.0).
            from core import voice_book

            if action == "keep":
                book = voice_book.keep(person, by=request.user, request=request)
                request.session["people_said"] = (
                    f"{person.name}'s voice is kept for the {book.unit} unit. "
                    "Anyone in the unit can now check an unnamed speaker against it "
                    "by hand; nothing is named by it on its own."
                )
            else:
                voice_book.stop_keeping(person, by=request.user, request=request)
                request.session["people_said"] = (
                    f"{person.name}'s voice is no longer kept for the unit from this "
                    "case. The case's own print stays."
                )
        elif action == "unlearn":
            from core import voice_prints

            done = voice_prints.unlearn(person, by=request.user, request=request)
            request.session["people_said"] = (
                f"{person.name}'s voice is unlearnt: "
                f"{done['segments_returned']} line"
                f"{'' if done['segments_returned'] == 1 else 's'} on "
                f"{done['recordings_returned']} recording"
                f"{'' if done['recordings_returned'] == 1 else 's'} returned to "
                f"unnamed and marked; {done['matches_withdrawn']} waiting match"
                f"{'' if done['matches_withdrawn'] == 1 else 'es'} withdrawn. "
                "The names given by hand stay."
            )
        else:
            return _back(case)
    except ValueError as refused:
        request.session["people_said"] = str(refused)
        return _back(case)
    cases.note_activity(case, by=request.user)
    return _back(case)
