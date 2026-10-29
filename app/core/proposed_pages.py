"""The Proposed events tab's addresses (Phase 10 chapter 4, v1.169.0)."""

from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, JsonResponse
from django.views.decorators.http import require_POST

from core import case_chronology, proposals
from core.case_chronology_pages import _date, _span
from core.case_pages import _their_case


@login_required
def tab(request: HttpRequest, case_id) -> JsonResponse:
    """The tab's reading: the days, the day asked for, the run's state."""
    case = _their_case(request, case_id)
    told = case_chronology.proposed_day_of(
        case, _date(request.GET.get("day", "")), _span(request)
    )
    told["me"] = request.user.pk
    told["on"] = proposals.tab_offered()
    return JsonResponse(told)


def _body(request) -> dict:
    try:
        body = json.loads(request.body or b"{}")
    except ValueError:
        body = {}
    return body if isinstance(body, dict) else {}


@login_required
@require_POST
def act(request: HttpRequest, case_id) -> JsonResponse:
    """Propose, Accept, Accept and edit, Dismiss, Accept all, Dismiss all."""
    case = _their_case(request, case_id)
    body = _body(request)
    action = str(body.get("action", ""))
    said = ""
    run = proposals.ProposalRun.objects.filter(case=case).first()
    busy = run is not None and run.state in ("queued", "running")
    if action == "propose":
        if not proposals.ask_for_run(
            case, by=request.user, look_for=str(body.get("look_for", ""))
        ):
            return JsonResponse(
                {"error": "Nothing to read yet: no recording has a transcript."},
                status=400,
            )
    elif action in ("accept", "accept_edit", "dismiss", "accept_all", "dismiss_all"):
        if busy:
            return JsonResponse(
                {"error": "The assistant is still proposing. Wait for it to finish."},
                status=409,
            )
        if action in ("accept_all", "dismiss_all"):
            count = proposals.decide_all(
                case,
                "accept" if action == "accept_all" else "dismiss",
                by=request.user,
                request=request,
            )
            said = (
                f"{count} note{'' if count == 1 else 's'} written."
                if action == "accept_all"
                else f"{count} proposed event{'' if count == 1 else 's'} dismissed."
            )
        else:
            one = proposals.Proposal.objects.filter(
                pk=str(body.get("id", "")), case=case, state=proposals.WAITING
            ).first()
            if one is None:
                raise Http404("no such proposal")
            if action == "dismiss":
                proposals.dismiss(one, by=request.user, request=request)
            else:
                text = str(body.get("text", "")) if action == "accept_edit" else None
                if action == "accept_edit" and not " ".join(text.split()):
                    return JsonResponse({"error": "Write the note first."}, status=400)
                proposals.accept(one, by=request.user, request=request, text=text)
                said = "A note is written on " + proposals._title(one.recording) + "."
    else:
        raise Http404("no such action")
    return JsonResponse({"ok": True, "said": said, "run": proposals.run_json(case)})
