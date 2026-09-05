"""The AI assistant's endpoints: what the viewer's Summary and Chat tabs and the
Speakers panel ask for, and what they send.

One state answer covers everything on a Recording, polled every two seconds
while a call is in progress. Every action is one POST. Nothing here logs a
question, an answer, a Summary, or a name; the rows that are written are the
chapter's, metadata only.
"""

from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from core import assistant, audit, cases, exports, tasks
from core.assistant import (
    Chat,
    ChatTurn,
    Suggestion,
    SuggestionRun,
    Summary,
    SummaryTemplate,
)
from core.recordings import Recording

LENGTHS = ("short", "standard", "detailed")


def _recording(request, recording_id) -> Recording | None:
    recording = Recording.objects.filter(pk=recording_id).select_related("user").first()
    if recording is None or not cases.reachable(recording):
        return None
    if recording.user_id != request.user.pk and not request.user.is_admin:
        return None
    return recording


def _body(request) -> dict:
    try:
        return json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return {}


def _role_of(recording, name: str) -> str:
    from core import people

    return people.role_of(recording, name)


def _affected(request, recording):
    return recording.user if recording.user_id != request.user.pk else None


def _summary_json(summary: Summary, transcript) -> dict:
    earlier = (
        transcript is not None
        and summary.transcript_created is not None
        and summary.transcript_created < transcript.created
    )
    return {
        "id": str(summary.pk),
        "state": summary.state,
        "reason": summary.reason_class,
        "said": assistant.what_to_say(summary.reason_class)
        if summary.reason_class
        else "",
        "template": summary.template_name,
        "focus": summary.focus,
        "length": summary.length,
        "text": summary.text,
        "citations": summary.citations,
        "cut_short": summary.cut_short,
        "notice": assistant.notice(summary.model, summary.written_at)
        if summary.text
        else "",
        "when": timezone.localtime(summary.written_at or summary.created).strftime(
            "%H:%M"
        ),
        "earlier": (
            f"Based on an earlier transcript of this recording (processed "
            f"{timezone.localtime(summary.transcript_created):%H:%M})"
            if earlier
            else ""
        ),
    }


def _chat_json(chat: Chat, transcript) -> dict:
    turns = list(chat.turns.all())
    earlier = transcript is not None and any(
        one.transcript_created is not None
        and one.transcript_created < transcript.created
        for one in turns
        if one.state == assistant.DONE
    )
    first_model = next((one.model for one in turns if one.model), "")
    first_when = next((one.answered_at for one in turns if one.answered_at), None)
    return {
        "id": str(chat.pk),
        "name": chat.name or "New chat",
        "busy": any(
            one.state in (assistant.QUEUED, assistant.RUNNING) for one in turns
        ),
        "notice": assistant.notice(first_model, first_when) if first_when else "",
        "earlier": (
            "Earlier answers are based on a previous transcript of this recording; "
            "new questions use the current one"
            if earlier
            else ""
        ),
        "turns": [
            {
                "id": str(one.pk),
                "number": one.number,
                "question": one.question,
                "answer": one.answer,
                "citations": one.citations,
                "state": one.state,
                "said": assistant.what_to_say(one.reason_class)
                if one.reason_class
                else "",
                "cut_short": one.cut_short,
            }
            for one in turns
        ],
    }


@login_required
def state(request: HttpRequest, recording_id) -> JsonResponse:
    """Everything the tabs and the Speakers panel show, in one answer."""
    recording = _recording(request, recording_id)
    if recording is None:
        return JsonResponse({"error": "no such recording"}, status=404)
    transcript = getattr(recording, "transcript", None)
    features = assistant.features()

    summaries = [_summary_json(one, transcript) for one in recording.summaries.all()]
    chats = [_chat_json(one, transcript) for one in recording.chats.all()]

    suggestions, run = [], None
    unnamed: list[str] = []
    if transcript is not None:
        unnamed = assistant.unnamed_speakers(transcript)
        suggestions = [
            {
                "id": str(one.pk),
                "speaker": one.speaker,
                "name": one.name,
                "kind": one.kind,
                "confidence": one.confidence,
                "quote": one.quote,
                "start": one.start,
                "clock": exports.clock(one.start),
                # The Role, when the suggested name is one of the Case's People.
                "role": _role_of(recording, one.name),
            }
            for one in transcript.suggestions.filter(state=Suggestion.PENDING)
        ]
        last = transcript.suggestion_runs.first()
        if last is not None:
            run = {
                "state": last.state,
                "found": last.found,
                "said": assistant.what_to_say(last.reason_class)
                if last.reason_class
                else "",
            }

    templates = SummaryTemplate.enabled_ones() if features["summary"] else []
    default = SummaryTemplate.the_default() if features["summary"] else None
    busy = any(
        one["state"] in (assistant.QUEUED, assistant.RUNNING) for one in summaries
    )
    busy = busy or any(one["busy"] for one in chats)
    busy = busy or (
        run is not None and run["state"] in (assistant.QUEUED, assistant.RUNNING)
    )

    return JsonResponse(
        {
            **features,
            "busy": busy,
            "summaries": summaries,
            "chats": chats,
            "templates": [
                {"id": str(one.pk), "name": one.name, "description": one.description}
                for one in templates
            ],
            "default_template": str(default.pk) if default else "",
            "unnamed": unnamed,
            # "pending", not "suggestions": that word is the feature's own flag above.
            "pending": suggestions,
            "suggestion_run": run,
        }
    )


# Summaries -------------------------------------------------------------------------


@login_required
@require_POST
def new_summary(request: HttpRequest, recording_id) -> JsonResponse:
    recording = _recording(request, recording_id)
    if recording is None:
        return JsonResponse({"error": "no such recording"}, status=404)
    if not assistant.features()["summary"]:
        return JsonResponse({"error": "Summary is off"}, status=404)
    if getattr(recording, "transcript", None) is None:
        return JsonResponse({"error": "there is no transcript yet"}, status=409)
    wanted = _body(request)
    template = None
    if wanted.get("template"):
        template = SummaryTemplate.objects.filter(
            pk=wanted["template"], enabled=True
        ).first()
    template = template or SummaryTemplate.the_default()
    length = wanted.get("length") if wanted.get("length") in LENGTHS else "standard"
    cases.used(recording, by=request.user)
    summary = Summary.objects.create(
        recording=recording,
        asked_by=request.user,
        template=template,
        template_name=template.name,
        template_version=template.version,
        focus=str(wanted.get("focus", ""))[:200],
        length=length,
    )
    tasks.write_summary.defer(summary_id=str(summary.pk))
    return JsonResponse({"id": str(summary.pk)})


@login_required
@require_POST
def regenerate_summary(request: HttpRequest, summary_id) -> JsonResponse:
    summary = get_object_or_404(Summary, pk=summary_id)
    if _recording(request, summary.recording_id) is None:
        return JsonResponse({"error": "no such recording"}, status=404)
    template = summary.template or SummaryTemplate.the_default()
    summary.template = template
    summary.template_name = template.name
    summary.template_version = template.version
    summary.state = assistant.QUEUED
    summary.reason_class = ""
    summary.text = ""
    summary.citations = {}
    summary.cut_short = False
    summary.asked_by = request.user
    summary.save()
    tasks.write_summary.defer(summary_id=str(summary.pk))
    return JsonResponse({"id": str(summary.pk)})


@login_required
@require_POST
def delete_summary(request: HttpRequest, summary_id) -> JsonResponse:
    summary = get_object_or_404(Summary, pk=summary_id)
    recording = _recording(request, summary.recording_id)
    if recording is None:
        return JsonResponse({"error": "no such recording"}, status=404)
    summary.delete()
    audit.write(
        audit.Category.EDITS,
        "Summary deleted",
        actor=request.user,
        request=request,
        affected_user=_affected(request, recording),
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
    )
    return JsonResponse({"ok": True})


# Chats --------------------------------------------------------------------------------


@login_required
@require_POST
def new_chat(request: HttpRequest, recording_id) -> JsonResponse:
    recording = _recording(request, recording_id)
    if recording is None:
        return JsonResponse({"error": "no such recording"}, status=404)
    if not assistant.features()["chat"]:
        return JsonResponse({"error": "Chat is off"}, status=404)
    chat = Chat.objects.create(recording=recording, asked_by=request.user)
    return JsonResponse({"id": str(chat.pk)})


@login_required
@require_POST
def ask(request: HttpRequest, chat_id) -> JsonResponse:
    chat = get_object_or_404(Chat, pk=chat_id)
    recording = _recording(request, chat.recording_id)
    if recording is None:
        return JsonResponse({"error": "no such recording"}, status=404)
    if getattr(recording, "transcript", None) is None:
        return JsonResponse({"error": "there is no transcript yet"}, status=409)
    question = str(_body(request).get("question", "")).strip()
    if not question:
        return JsonResponse({"error": "ask something"}, status=400)
    if chat.turns.filter(state__in=(assistant.QUEUED, assistant.RUNNING)).exists():
        return JsonResponse(
            {"error": "the last question is still being answered"}, status=409
        )
    cases.used(recording, by=request.user)
    number = chat.turns.count() + 1
    if not chat.name:
        chat.name = Chat.name_from(question)
        chat.save(update_fields=["name"])
    turn = ChatTurn.objects.create(chat=chat, number=number, question=question[:4000])
    tasks.answer_turn.defer(turn_id=str(turn.pk))
    return JsonResponse({"id": str(turn.pk)})


@login_required
@require_POST
def delete_chat(request: HttpRequest, chat_id) -> JsonResponse:
    chat = get_object_or_404(Chat, pk=chat_id)
    recording = _recording(request, chat.recording_id)
    if recording is None:
        return JsonResponse({"error": "no such recording"}, status=404)
    chat.delete()
    audit.write(
        audit.Category.EDITS,
        "Chat deleted",
        actor=request.user,
        request=request,
        affected_user=_affected(request, recording),
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
    )
    return JsonResponse({"ok": True})


# Speaker suggestions ------------------------------------------------------------------


@login_required
@require_POST
def suggest(request: HttpRequest, recording_id) -> JsonResponse:
    recording = _recording(request, recording_id)
    if recording is None:
        return JsonResponse({"error": "no such recording"}, status=404)
    if not assistant.features()["suggestions"]:
        return JsonResponse({"error": "Speaker suggestions are off"}, status=404)
    transcript = getattr(recording, "transcript", None)
    if transcript is None:
        return JsonResponse({"error": "there is no transcript yet"}, status=409)
    if len(assistant.unnamed_speakers(transcript)) < 2:
        return JsonResponse(
            {"error": "fewer than two speakers are unnamed"}, status=409
        )
    if transcript.suggestion_runs.filter(
        state__in=(assistant.QUEUED, assistant.RUNNING)
    ).exists():
        return JsonResponse({"error": "a run is already in progress"}, status=409)
    cases.used(recording, by=request.user)
    run = SuggestionRun.objects.create(transcript=transcript, asked_by=request.user)
    tasks.suggest_names.defer(run_id=str(run.pk))
    return JsonResponse({"id": str(run.pk)})


@login_required
@require_POST
def decide(request: HttpRequest, suggestion_id, verdict: str) -> JsonResponse:
    """Accept renames every Segment of that Speaker; Reject dismisses it."""
    suggestion = get_object_or_404(
        Suggestion, pk=suggestion_id, state=Suggestion.PENDING
    )
    recording = _recording(request, suggestion.transcript.recording_id)
    if recording is None:
        return JsonResponse({"error": "no such recording"}, status=404)
    changed = 0
    if verdict == "accept":
        changed = suggestion.transcript.segments.filter(
            speaker=suggestion.speaker
        ).update(speaker=suggestion.name)
        suggestion.state = Suggestion.ACCEPTED
        # Inside a Case the accepted name joins or makes a Person.
        from core import people

        people.on_named(
            recording,
            suggestion.name,
            by=request.user,
            how="suggestion accepted",
            request=request,
        )
    else:
        suggestion.state = Suggestion.REJECTED
    suggestion.save(update_fields=["state"])
    audit.write(
        audit.Category.EDITS,
        "Suggestion accepted" if verdict == "accept" else "Suggestion rejected",
        actor=request.user,
        request=request,
        affected_user=_affected(request, recording),
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.original_filename,
        segments_changed=changed,
    )
    return JsonResponse({"ok": True, "changed": changed})


# Exports ------------------------------------------------------------------------------


@login_required
def export_summary(request: HttpRequest, summary_id) -> HttpResponse:
    summary = get_object_or_404(Summary, pk=summary_id)
    recording = _recording(request, summary.recording_id)
    if recording is None or summary.state != assistant.DONE:
        return HttpResponse(status=404)
    exports.record_export(request, recording, "summary")
    return _docx(
        exports.summary_word(summary, request.user.username),
        exports.summary_name(summary),
    )


@login_required
def export_chat(request: HttpRequest, chat_id) -> HttpResponse:
    chat = get_object_or_404(Chat, pk=chat_id)
    recording = _recording(request, chat.recording_id)
    if recording is None:
        return HttpResponse(status=404)
    exports.record_export(request, recording, "chat")
    return _docx(
        exports.chat_word(chat, request.user.username), exports.chat_name(chat)
    )


def _docx(content: bytes, name: str) -> HttpResponse:
    answer = HttpResponse(
        content,
        content_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
    )
    answer["Content-Disposition"] = f'attachment; filename="{name}"'
    return answer
