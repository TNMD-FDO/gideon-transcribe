"""The Admin panel: the settings pages, and the tray that applies them.

A setting never applies as it is edited. Edits collect in a tray at the foot
of the panel, kept across pages, and Apply writes them all in one step with
one audit row each. That is the whole point of the tray: an Admin changing
four things changes them together, and the log says why, once, in their own
words.

The tray lives in the Admin's own browser session rather than in the
database, because a half-made set of edits is not office configuration and
should not outlive the person who is making it.
"""

from __future__ import annotations

import logging

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from core import audit, settings_store

log = logging.getLogger("transcribe.panel")

TRAY = "settings_tray"
TRAY_NOTE = "settings_tray_note"

# The rail, in three groups. Only pages that exist are listed: a page that is
# not built is absent rather than greyed, as Phase 2's rows are.
RAIL = [
    (
        "Overview",
        [
            ("Status", "panel-status"),
            ("Queue", "panel-queue"),
            ("Users", "panel-users"),
            ("Audit log", "panel-audit"),
        ],
    ),
    (
        "Settings",
        # The settings pages, then the AI assistant's templates, which are
        # edited outside the tray and so have a page of their own.
        [(name, key) for key, name in settings_store.PAGES]
        + [("Templates", "panel-templates")],
    ),
    ("Server", [("Installation", "panel-installation")]),
]


def admins_only(view):
    """Users never see any of this, and an Admin is the only one who does."""
    return login_required(user_passes_test(lambda user: user.is_admin)(view))


# The tray ---------------------------------------------------------------------


def tray_of(request) -> dict:
    return request.session.get(TRAY, {})


def waiting_on(page: str, tray: dict) -> int:
    """How many edits are waiting for one settings page, for the rail."""
    return sum(1 for key in tray if settings_store.definition(key).page == page)


def tray_rows(tray: dict) -> list[dict]:
    """Each waiting edit, as the setting's name with its old and new value."""
    rows = []
    for key, wanted in tray.items():
        known = settings_store.definition(key)
        rows.append(
            {
                "key": key,
                "name": known.name,
                "page": known.page,
                "was": settings_store.shown(key),
                "now": settings_store.shown(key, wanted),
            }
        )
    return sorted(rows, key=lambda one: one["name"])


def furniture(request, page: str = "") -> dict:
    """What every panel page is drawn with."""
    tray = tray_of(request)
    return {
        "rail": [
            (
                group,
                [
                    {
                        "name": name,
                        "url": (
                            reverse("panel-settings", args=[key])
                            if key in dict(settings_store.PAGES)
                            else reverse(key)
                        ),
                        "here": key == page,
                        "waiting": (
                            waiting_on(key, tray)
                            if key in dict(settings_store.PAGES)
                            else 0
                        ),
                    }
                    for name, key in pages
                ],
            )
            for group, pages in RAIL
        ],
        "tray": tray_rows(tray),
        "tray_note": request.session.get(TRAY_NOTE, ""),
        "here": page,
        "page": "panel",
    }


# The settings pages -----------------------------------------------------------

# Listed at the foot of every settings page, so that nobody looks for them
# among the settings. Each one is fixed in code and named in the chapter that
# fixes it.
FIXED_RULES = [
    "One unfinished Batch per person, Admins included.",
    "One sign-in per person at a time; the newest wins.",
    "The grace period after a session's last Job equals the idle timeout.",
    "No Queue priority and no Pause.",
    "The Discard runs within a minute, and the sweeper at 03:30.",
    "Spoken language starts at Automatic, with Whisper's own list.",
    "The AI assistant's sampling, answer caps, and time limits.",
    "Pages ask again every five seconds and the worker every three.",
    "Three uploads at once per browser; leaving the Upload page abandons them.",
    "The Two-channel call detection thresholds.",
    "Export layouts, file names, and formats, and the Clip caption style.",
    "The WhisperX service's own settings, in its environment file: batch size, "
    "voice activity, limits, timeouts, alignment languages, the model cache.",
    "The audit log's field set and the list of what is never logged.",
    "Five sign-in failures, then a fifteen-minute wait.",
    "The storage warning past 80% of a person's space.",
    "No Workspace retention setting, because nothing in a Workspace survives "
    "the Login session; and no bulk-upload switch, because Files per Batch set "
    "to 1 does it.",
]


@admins_only
def _appearance() -> dict:
    from core import branding

    row = branding.current()
    return {
        "logo": row is not None,
        "kind": row.content_type if row else "",
        "uploaded_at": row.uploaded_at if row else None,
        "uploaded_by": row.uploaded_by.username if row and row.uploaded_by else "",
        "said": "",
    }


@admins_only
@require_POST
def logo(request: HttpRequest) -> HttpResponse:
    """Upload or remove the office logo, at once, with its audit row."""
    from core import branding

    back = reverse("panel-settings", args=[settings_store.APPEARANCE])
    if request.POST.get("action") == "remove":
        branding.remove(by=request.user, request=request)
        return redirect(back)
    sent = request.FILES.get("logo")
    try:
        branding.upload(sent.read() if sent else b"", by=request.user, request=request)
    except branding.Refused as refused:
        request.session["appearance_said"] = str(refused)
    return redirect(back)


def settings_page(request: HttpRequest, page: str) -> HttpResponse:
    """One settings page: name and help on the left, the control on the right."""
    if page not in dict(settings_store.PAGES):
        return redirect(reverse("panel-settings", args=[settings_store.FEATURES]))

    tray = tray_of(request)
    rows = []
    for known in settings_store.page_settings(page):
        waiting = known.key in tray
        rows.append(
            {
                "key": known.key,
                "name": known.name,
                "kind": known.kind,
                "help": known.what_it_does,
                "when_changed": known.when_changed,
                "unit": known.unit,
                "least": known.least,
                "most": known.most,
                "choices": known.choices,
                "lines": known.lines,
                "value": tray[known.key] if waiting else settings_store.get(known.key),
                "waiting": waiting,
                # Not through shown(): that redacts a content setting to
                # "(changed)", which says nothing about what it starts as.
                "default": (
                    settings_store.shown(known.key, known.default)
                    if not known.content
                    else (known.default or "(empty)")
                ),
                "changed": not settings_store.is_at_default(known.key),
                # Greyed under a toggle that is off: the value is kept and
                # shown, the control is closed, and the row says why.
                "greyed": bool(known.needs) and not settings_store.get(known.needs),
                "needs_name": (
                    settings_store.definition(known.needs).name if known.needs else ""
                ),
            }
        )

    # The AI assistant page shows the engine's token as set or missing and
    # nothing more: it lives in a file on the server, never in the panel or
    # the database, and changing it is a file change and a restart.
    token = None
    if page == settings_store.ASSISTANT:
        import os

        from core import engine

        token = {
            "set": engine.token_is_set(),
            "file": os.environ.get("LLM_API_TOKEN_FILE", "./secrets/llm_api_token"),
        }

    return render(
        request,
        "panel/settings.html",
        {
            **furniture(request, page),
            "title": dict(settings_store.PAGES)[page],
            "rows": rows,
            "token": token,
            "fixed_rules": FIXED_RULES,
            "directory": _directory_facts() if page == settings_store.SIGN_IN else None,
            # The Appearance page carries the logo, which is a file and not a
            # setting: uploaded and removed at once, outside the tray.
            "appearance": _appearance() if page == settings_store.APPEARANCE else None,
            "appearance_said": request.session.pop("appearance_said", ""),
            "limits_cross_reference": page == settings_store.LIMITS,
        },
    )


@admins_only
@require_POST
def edit(request: HttpRequest, page: str) -> HttpResponse:
    """Put one page's changes in the tray. Nothing is applied here."""
    tray = tray_of(request)
    problems = []

    for known in settings_store.page_settings(page):
        if known.kind == settings_store.TOGGLE:
            wanted = known.key in request.POST
        elif known.key not in request.POST:
            continue
        else:
            wanted = request.POST[known.key]

        try:
            wanted = settings_store.check(known.key, wanted)
        except ValueError as refusal:
            problems.append(str(refusal))
            continue

        if wanted == settings_store.get(known.key):
            tray.pop(known.key, None)
        else:
            tray[known.key] = wanted

    request.session[TRAY] = tray
    request.session[TRAY_NOTE] = request.POST.get("note", "")
    for problem in problems:
        _tell(request, problem)
    return redirect(reverse("panel-settings", args=[page]))


@admins_only
@require_POST
def apply(request: HttpRequest) -> HttpResponse:
    """Write every waiting change in one step, one audit row each."""
    tray = tray_of(request)
    note = request.POST.get("note", request.session.get(TRAY_NOTE, ""))

    # The one rule that spans two settings is judged on the whole tray before
    # anything is written, so a pair that is wrong together is refused
    # together and nothing is half applied.
    try:
        settings_store.check_together(tray)
    except ValueError as problem:
        _tell(request, f"Nothing was applied. {problem}")
        return redirect(request.POST.get("back") or reverse("panel"))

    for key, wanted in tray.items():
        known = settings_store.definition(key)
        was = settings_store.shown(key)
        settings_store.set_to(key, wanted)
        audit.write(
            audit.Category.ADMIN,
            "Setting changed",
            actor=request.user,
            request=request,
            object_type="setting",
            object_id=key,
            object_label=known.name,
            # A Vocabulary is content, so its row says only that it changed.
            was=was,
            now=settings_store.shown(key),
            note=note,
        )
        log.info("%s changed %s", request.user.username, known.name)

    request.session[TRAY] = {}
    request.session[TRAY_NOTE] = ""
    _tell(request, f"{len(tray)} setting{'' if len(tray) == 1 else 's'} applied.")
    return redirect(request.POST.get("back") or reverse("panel"))


@admins_only
@require_POST
def cancel_all(request: HttpRequest) -> HttpResponse:
    """Drop every waiting change."""
    request.session[TRAY] = {}
    request.session[TRAY_NOTE] = ""
    return redirect(request.POST.get("back") or reverse("panel"))


@admins_only
def panel(request: HttpRequest) -> HttpResponse:
    """The panel's front door, which is the Status page."""
    return redirect(reverse("panel-status"))


def _tell(request, message: str) -> None:
    from django.contrib import messages

    messages.info(request, message)


def _directory_facts() -> list[tuple[str, str]]:
    """The eight directory keys, read-only, and never a password's value."""
    import os

    keys = [
        "LDAP_ENABLED",
        "LDAP_SERVER_URI",
        "LDAP_CA_FILE",
        "LDAP_BIND_USER",
        "LDAP_SEARCH_BASE",
        "LDAP_SIGNIN_GROUP",
        "LDAP_ADMIN_GROUP",
    ]
    facts = [(key, os.environ.get(key, "") or "not set") for key in keys]
    password = os.environ.get("LDAP_BIND_PASSWORD_FILE", "")
    facts.append(
        (
            "LDAP_BIND_PASSWORD_FILE",
            f"{password} (set)" if _file_has_something(password) else "missing",
        )
    )
    return facts


def _file_has_something(path: str) -> bool:
    from pathlib import Path

    try:
        return bool(path) and Path(path).is_file() and Path(path).stat().st_size > 0
    except OSError:
        return False
