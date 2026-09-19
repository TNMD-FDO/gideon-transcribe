"""Report a problem (Phase 8 chapter 3).

A Report is a person's own account, sent from any page, of a problem they
hit or an idea that would help, kept for the Admins with where they were
when they ticked to include it. The Panel's Reports page is the record; the
mail to the Operator address is the second copy. Never a transcript's words,
never a screenshot, nothing that leaves the building.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import models
from django.http import HttpRequest, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core import audit, settings_store

PROBLEM = "problem"
IDEA = "idea"
KINDS = {PROBLEM: "A problem", IDEA: "An idea"}

NEW = "new"
SEEN = "seen"
DONE = "done"
STATES = (NEW, SEEN, DONE)
STATE_WORDS = {NEW: "New", SEEN: "Seen", DONE: "Done"}

WORDS_MOST = 4000
PAGE_MOST = 300
# A Done report is kept ninety days from its mark, then swept.
DONE_KEPT = timedelta(days=90)
MAIL_KIND = "report"


class Report(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=10, default=PROBLEM)
    happened = models.TextField(max_length=WORDS_MOST)
    expected = models.TextField(max_length=WORDS_MOST, blank=True, default="")
    # Where the person was, added only with their tick: the page's path
    # (never its query), the Release, the browser, the window's size.
    page = models.CharField(max_length=PAGE_MOST, blank=True, default="")
    release = models.CharField(max_length=60, blank=True, default="")
    browser = models.CharField(max_length=80, blank=True, default="")
    window = models.CharField(max_length=30, blank=True, default="")
    # Who sent it, and their name as it was, so a leaver's report stays named.
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    sent_by_name = models.CharField(max_length=150, blank=True, default="")
    made = models.DateTimeField(default=timezone.now)
    state = models.CharField(max_length=8, default=NEW)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    marked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-made"]

    def __str__(self) -> str:
        return f"{KINDS.get(self.kind, self.kind)} from {self.sent_by_name}"

    def first_line(self) -> str:
        line = self.happened.strip().splitlines()[0] if self.happened.strip() else ""
        return line if len(line) <= 90 else line[:87].rstrip() + "..."

    def where_line(self) -> str:
        """The line the person saw before sending, as kept."""
        parts = []
        if self.page:
            parts.append(f"This page ({self.page})")
        if self.release:
            parts.append(f"Release {self.release}")
        if self.browser:
            parts.append(self.browser)
        if self.window:
            parts.append(f"a window of {self.window}")
        parts.append(f"sent by {self.sent_by_name or 'somebody'}")
        return ", ".join(parts) + "."


def on() -> bool:
    return bool(settings_store.get("reports"))


def release() -> str:
    return os.environ.get("RELEASE_TAG", "").strip() or "not tagged"


def new_count() -> int:
    return Report.objects.filter(state=NEW).count()


# The browser, short -------------------------------------------------------------------

_BROWSERS = (
    ("Edg/", "Edge"),
    ("OPR/", "Opera"),
    ("Firefox/", "Firefox"),
    ("Chrome/", "Chrome"),
    ("Safari/", "Safari"),
)
_SYSTEMS = (
    ("Windows", "Windows"),
    ("Mac OS", "macOS"),
    ("CrOS", "ChromeOS"),
    ("Android", "Android"),
    ("iPhone", "iOS"),
    ("iPad", "iPadOS"),
    ("Linux", "Linux"),
)


def browser_of(user_agent: str) -> str:
    """ "Chrome 129 on Windows" from the User-Agent header; "a browser" when
    it is none the office uses."""
    agent = user_agent or ""
    name = ""
    version = ""
    for token, shown in _BROWSERS:
        found = re.search(re.escape(token) + r"(\d+)", agent)
        if found:
            name, version = shown, found.group(1)
            if shown == "Safari":
                found = re.search(r"Version/(\d+)", agent)
                version = found.group(1) if found else version
            break
    system = next((shown for token, shown in _SYSTEMS if token in agent), "")
    if not name:
        return "a browser" + (f" on {system}" if system else "")
    return f"{name} {version}" + (f" on {system}" if system else "")


# Sending ------------------------------------------------------------------------------


def _path_only(page: str) -> str:
    page = str(page or "").strip().split("?", 1)[0].split("#", 1)[0]
    return page[:PAGE_MOST] if page.startswith("/") else ""


def make(
    *, by, kind: str, happened: str, expected: str = "", where=None, request=None
) -> Report:
    """Keep the Report, write its row, and queue the Operator's copy."""
    where = where or {}
    report = Report.objects.create(
        kind=kind if kind in KINDS else PROBLEM,
        happened=happened.strip()[:WORDS_MOST],
        expected=(expected or "").strip()[:WORDS_MOST] if kind != IDEA else "",
        page=_path_only(where.get("page", "")),
        release=str(where.get("release", ""))[:60],
        browser=str(where.get("browser", ""))[:80],
        window=str(where.get("window", ""))[:30],
        sent_by=by,
        sent_by_name=by.shown_name,
    )
    audit.write(
        audit.Category.SYSTEM,
        "Report made",
        actor=by,
        request=request,
        object_type="report",
        object_id=report.pk,
        object_label=KINDS[report.kind],
        kind=report.kind,
        page=report.page,
        release=report.release,
    )
    _mail(report, request)
    return report


def _mail(report: Report, request=None) -> bool:
    from core import mail

    who = report.sent_by_name or "somebody"
    head = "Report" if report.kind == PROBLEM else "Idea"
    subject = f"{head} from {who}: {report.first_line()}"
    when = f"{timezone.localtime(report.made):%d %B %Y %H:%M}"
    lines = [f"{KINDS[report.kind]}, sent by {who} on {when}.", ""]
    lines.append(
        ("What happened:" if report.kind == PROBLEM else "What would help:")
        + "\n"
        + report.happened
    )
    if report.expected:
        lines.append("What was expected:\n" + report.expected)
    lines.append("Where: " + report.where_line())
    where = reverse("panel-reports")
    if request is not None:
        where = request.build_absolute_uri(where)
    lines.append(f"Seen and marked on the Panel's Reports page at {where}")
    return mail.send_to_operator(MAIL_KIND, subject, "\n\n".join(lines))


@login_required
@require_POST
def send(request: HttpRequest) -> JsonResponse:
    """The box's Send: one Report, refused while the setting is Off."""
    if not on():
        return JsonResponse({"error": "Reports are off."}, status=403)
    try:
        wanted = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "that could not be read"}, status=400)
    happened = str(wanted.get("happened", "")).strip()
    if not happened:
        return JsonResponse({"error": "Say what happened first."}, status=400)
    where = {}
    if wanted.get("include"):
        where = {
            "page": wanted.get("page", ""),
            "release": release(),
            "browser": browser_of(request.META.get("HTTP_USER_AGENT", "")),
            "window": str(wanted.get("window", ""))[:30],
        }
    else:
        where = {"release": release()}
    report = make(
        by=request.user,
        kind=str(wanted.get("kind", PROBLEM)),
        happened=happened,
        expected=str(wanted.get("expected", "")),
        where=where,
        request=request,
    )
    return JsonResponse({"sent": True, "id": str(report.pk)})


# The Panel ----------------------------------------------------------------------------

_ORDER = {NEW: 0, SEEN: 1, DONE: 2}


def listed(state: str = "") -> dict:
    """The Reports page: newest first, New before Seen before Done."""
    rows = list(Report.objects.select_related("sent_by", "marked_by"))
    counts = {one: 0 for one in STATES}
    for report in rows:
        counts[report.state] = counts.get(report.state, 0) + 1
    if state in STATES:
        rows = [one for one in rows if one.state == state]
    rows.sort(key=lambda one: (_ORDER.get(one.state, 3), -one.made.timestamp()))
    return {
        "rows": rows,
        "state": state if state in STATES else "",
        "counts": counts,
        "total": sum(counts.values()),
    }


def mark(report: Report, state: str, *, by, request=None) -> None:
    """Seen on a New report, Done on a New or Seen one; one row each."""
    if state not in (SEEN, DONE) or report.state == state or report.state == DONE:
        return
    report.state = state
    report.marked_by = by
    report.marked_at = timezone.now()
    report.save(update_fields=["state", "marked_by", "marked_at"])
    audit.write(
        audit.Category.SYSTEM,
        "Report seen" if state == SEEN else "Report done",
        actor=by,
        request=request,
        object_type="report",
        object_id=report.pk,
        object_label=KINDS[report.kind],
    )


def sweep() -> int:
    """Done reports past their ninety days go; one row says how many."""
    gone, _ = Report.objects.filter(
        state=DONE, marked_at__lt=timezone.now() - DONE_KEPT
    ).delete()
    if gone:
        audit.write(
            audit.Category.SYSTEM, "Reports swept", system="sweeper", count=gone
        )
    return gone
