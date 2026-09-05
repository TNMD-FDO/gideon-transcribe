"""The Templates page of the Panel: the AI assistant's editable instructions.

Ground rules, Chat and Speaker suggestions are prompt templates, plain text
with Reset to default and a version that rises by one on every save. Summary
templates have a name, a one-line description, the instruction text, Enabled
and Default; exactly one Default exists among the Enabled; the built-in
Standard summary is editable and resettable but never deleted. All of it
applies at once, outside the tray, and each act writes an audit row naming
the template and its new version or flag, never the text.
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core import audit, prompts
from core.assistant import PromptTemplate, SummaryTemplate
from core.panel import admins_only, furniture

PAGE = "panel-templates"


def _row(request, event: str, **details) -> None:
    audit.write(
        audit.Category.ADMIN,
        event,
        actor=request.user,
        request=request,
        object_type="template",
        **details,
    )


@admins_only
def templates(request: HttpRequest) -> HttpResponse:
    SummaryTemplate.standard()
    return render(
        request,
        "panel/templates.html",
        {
            **furniture(request, PAGE),
            "here": PAGE,
            "prompt_templates": [
                PromptTemplate.named(key) for key in PromptTemplate.DEFAULTS
            ],
            "summary_templates": list(SummaryTemplate.objects.all()),
            "standard_text": prompts.STANDARD_SUMMARY,
        },
    )


@admins_only
@require_POST
def prompt_template(request: HttpRequest, key: str) -> HttpResponse:
    if key not in PromptTemplate.DEFAULTS:
        return redirect(reverse(PAGE))
    row = PromptTemplate.named(key)
    if request.POST.get("action") == "reset":
        row.reset()
        _row(
            request,
            "template reset",
            object_id=key,
            object_label=row.name,
            version=row.version,
        )
    else:
        text = request.POST.get("text", "").strip()
        if text and text != row.text:
            row.save_text(text)
            _row(
                request,
                "template saved",
                object_id=key,
                object_label=row.name,
                version=row.version,
            )
    return redirect(reverse(PAGE))


@admins_only
@require_POST
def add_summary_template(request: HttpRequest) -> HttpResponse:
    name = request.POST.get("name", "").strip()[:80]
    text = request.POST.get("text", "").strip()
    if name and text:
        row = SummaryTemplate.objects.create(
            name=name,
            description=request.POST.get("description", "").strip()[:200],
            text=text,
        )
        _row(
            request,
            "summary template added",
            object_id=row.pk,
            object_label=row.name,
            version=1,
        )
    return redirect(reverse(PAGE))


@admins_only
@require_POST
def summary_template(request: HttpRequest, template_id) -> HttpResponse:
    row = get_object_or_404(SummaryTemplate, pk=template_id)
    action = request.POST.get("action", "save")
    if action == "delete" and not row.built_in:
        name = row.name
        was_default = row.is_default
        row.delete()
        _row(
            request,
            "summary template deleted",
            object_id=template_id,
            object_label=name,
        )
        if was_default:
            SummaryTemplate.the_default()
    elif action == "default":
        row.make_default()
        _row(
            request,
            "summary template made default",
            object_id=row.pk,
            object_label=row.name,
        )
    elif action == "enable":
        row.enabled = True
        row.save(update_fields=["enabled"])
        _row(
            request, "summary template enabled", object_id=row.pk, object_label=row.name
        )
    elif action == "disable":
        if row.is_default:
            # The Default must stay among the Enabled; the built-in one takes over.
            row.is_default = False
        row.enabled = False
        row.save(update_fields=["enabled", "is_default"])
        SummaryTemplate.the_default()
        _row(
            request,
            "summary template disabled",
            object_id=row.pk,
            object_label=row.name,
        )
    elif action == "reset" and row.built_in:
        row.save_text(prompts.STANDARD_SUMMARY)
        _row(
            request,
            "summary template reset",
            object_id=row.pk,
            object_label=row.name,
            version=row.version,
        )
    else:
        name = request.POST.get("name", "").strip()[:80]
        description = request.POST.get("description", "").strip()[:200]
        text = request.POST.get("text", "").strip()
        changed = False
        if name and name != row.name and not row.built_in:
            row.name = name
            changed = True
        if description != row.description:
            row.description = description
            changed = True
        if changed:
            row.save(update_fields=["name", "description"])
        if text and text != row.text:
            row.save_text(text)
            changed = True
        if changed:
            _row(
                request,
                "summary template saved",
                object_id=row.pk,
                object_label=row.name,
                version=row.version,
            )
    return redirect(reverse(PAGE))
