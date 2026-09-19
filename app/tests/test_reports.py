"""v1.70.0: Report a problem (Phase 8, chapter 3).

The rules checked here: the link and the box are on every page a signed-in
person sees while Reports is on, and nowhere while it is off or before
sign-in; a Report keeps the person's words, their name and, only with the
tick, where they were (the page's path without its query, the Release, the
browser short, the window), with one audit row that never holds the words;
the Operator's copy goes as the app's own mail; the Panel's Reports page
lists them New before Seen before Done with the marks, the rail and the
Status page count the New ones; a Done report is swept after ninety days.
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest
from core import mail, reports, settings_store, sweeping
from core.audit import Row
from core.models import LoginSession, User
from core.reports import Report
from django.utils import timezone

PASSWORD = "a-long-enough-password"
CHROME = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like "
    "Gecko) Chrome/129.0.0.0 Safari/537.36"
)
EDGE = CHROME + " Edg/128.0.0.0"


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"


@pytest.fixture
def admin(db):
    return User.objects.create_local_admin("asker", PASSWORD)


@pytest.fixture
def person(db):
    return User.objects.create(username="ana", display_name="Ana Alvarez")


@pytest.fixture
def operator_mail(monkeypatch):
    sent = []
    monkeypatch.setattr(
        mail,
        "send_to_operator",
        lambda kind, subject, body, **d: sent.append((kind, subject, body)) or True,
    )
    return sent


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def send(client, **fields):
    return client.post(
        "/report",
        json.dumps(fields),
        content_type="application/json",
        HTTP_USER_AGENT=CHROME,
    )


# The link and the box -----------------------------------------------------------------


def test_the_link_and_the_box_are_on_every_page_while_reports_are_on(
    person, admin, client, monkeypatch
):
    assert 'id="report-open"' not in client.get("/sign-in").content.decode()
    signed_in(client, person)
    monkeypatch.setenv("RELEASE_TAG", "v1.70.0")
    page = client.get("/").content.decode()
    assert 'id="report-open"' in page and 'id="report-dialog"' in page
    assert 'data-release="v1.70.0"' in page and 'data-name="Ana Alvarez"' in page
    assert "report.js" in page and "Include where I was" in page
    assert "A problem" in page and "An idea" in page
    settings_store.set_to("reports", False)
    page = client.get("/").content.decode()
    assert 'id="report-open"' not in page and "report.js" not in page
    assert send(client, happened="Nothing").status_code == 403
    assert Report.objects.count() == 0
    # The setting is a Features row.
    definition = settings_store.definition("reports")
    assert definition.page == "features" and definition.default is True


def test_a_report_keeps_the_words_and_where_only_with_the_tick(
    person, client, operator_mail, monkeypatch
):
    signed_in(client, person)
    monkeypatch.setenv("RELEASE_TAG", "v1.70.0")
    told = send(
        client,
        kind="problem",
        happened="The Clips tab said 3 and there were 4.\nSecond line.",
        expected="The same number.",
        include=True,
        page="/case/abc?tab=clips&q=secret%20words",
        window="1920 by 1080",
    )
    assert told.status_code == 200 and told.json()["sent"]
    report = Report.objects.get()
    assert report.kind == "problem" and report.state == "new"
    assert report.happened.startswith("The Clips tab said 3")
    assert report.expected == "The same number."
    # The path alone, never the query; the browser short; the release.
    assert report.page == "/case/abc"
    assert report.browser == "Chrome 129 on Windows"
    assert report.release == "v1.70.0" and report.window == "1920 by 1080"
    assert report.sent_by == person and report.sent_by_name == "Ana Alvarez"
    assert report.where_line() == (
        "This page (/case/abc), Release v1.70.0, Chrome 129 on Windows, "
        "a window of 1920 by 1080, sent by Ana Alvarez."
    )
    assert report.first_line() == "The Clips tab said 3 and there were 4."
    # One row, never the words.
    row = Row.objects.get(event="Report made")
    assert row.category == "system" and row.details["page"] == "/case/abc"
    blob = json.dumps(row.details).lower()
    assert "clips tab" not in blob and "secret" not in blob
    # The Operator's copy.
    kind, subject, body = operator_mail[0]
    assert kind == "report"
    assert subject == "Report from Ana Alvarez: The Clips tab said 3 and there were 4."
    assert "What happened:\nThe Clips tab said 3" in body
    assert "What was expected:\nThe same number." in body
    assert "Where: This page (/case/abc), Release v1.70.0" in body
    assert "/panel/reports" in body and "secret" not in body
    # Unticked: the name and the Release only. An idea has no "expected".
    told = send(
        client,
        kind="idea",
        happened="A button to sort clips.",
        expected="ignored",
        include=False,
        page="/clips",
        window="800 by 600",
    )
    assert told.status_code == 200
    idea = Report.objects.get(kind="idea")
    assert idea.page == "" and idea.browser == "" and idea.window == ""
    assert idea.release == "v1.70.0" and idea.expected == ""
    assert idea.where_line() == "Release v1.70.0, sent by Ana Alvarez."
    assert operator_mail[1][1] == "Idea from Ana Alvarez: A button to sort clips."
    assert "What would help:\nA button to sort clips." in operator_mail[1][2]
    # Nothing to say is refused; a stray kind is a problem.
    assert send(client, happened="   ").status_code == 400
    send(client, kind="odd", happened="x" * 5000, include=False)
    odd = Report.objects.get(happened__startswith="xxx")
    assert odd.kind == "problem" and len(odd.happened) == 4000


def test_the_browser_is_named_short():
    assert reports.browser_of(CHROME) == "Chrome 129 on Windows"
    assert reports.browser_of(EDGE) == "Edge 128 on Windows"
    assert (
        reports.browser_of(
            "Mozilla/5.0 (Windows NT 10.0; rv:130.0) Gecko/20100101 Firefox/130.0"
        )
        == "Firefox 130 on Windows"
    )
    assert (
        reports.browser_of(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.4 Safari/605.1.15"
        )
        == "Safari 17 on macOS"
    )
    assert reports.browser_of("curl/8.0") == "a browser"
    assert reports.browser_of("") == "a browser"


# The Panel ----------------------------------------------------------------------------


def test_the_reports_page_lists_and_marks_them_and_the_rail_counts_the_new(
    person, admin, client, operator_mail
):
    first = reports.make(by=person, kind="problem", happened="First problem.")
    second = reports.make(
        by=person,
        kind="idea",
        happened="An idea.",
        where={"page": "/clips", "release": "v1.70.0"},
    )
    third = reports.make(by=admin, kind="problem", happened="Third, marked done.")
    reports.mark(third, "done", by=admin)
    # A person never sees the Panel.
    signed_in(client, person)
    assert client.get("/panel/reports").status_code in (302, 403)
    client.logout()
    signed_in(client, admin)
    page = client.get("/panel/reports").content.decode()
    assert "All (3)" in page and "New (2)" in page and "Done (1)" in page
    assert (
        page.index("An idea.")
        < page.index("First problem.")
        < page.index("Third, marked done.")
    )
    assert "This page (/clips), Release v1.70.0, sent by Ana Alvarez." in page
    assert f"/panel/reports/{first.pk}/seen" in page
    assert f"/panel/reports/{third.pk}/done" not in page
    # The rail's badge and the Status page's line count the New ones.
    assert 'title="Reports not yet seen">2</span>' in page
    status = client.get("/panel/status").content.decode()
    assert "2 reports not yet seen" in status and 'id="reports-line"' in status
    # Seen, then Done; Done is not undone; one row each.
    assert (
        client.post(
            f"/panel/reports/{first.pk}/seen", {"back": "/panel/reports?state=new"}
        ).url
        == "/panel/reports?state=new"
    )
    first.refresh_from_db()
    assert first.state == "seen" and first.marked_by == admin and first.marked_at
    client.post(f"/panel/reports/{first.pk}/done", {"back": "https://elsewhere/"})
    first.refresh_from_db()
    assert first.state == "done"
    client.post(f"/panel/reports/{first.pk}/seen")
    first.refresh_from_db()
    assert first.state == "done"
    events = list(
        Row.objects.filter(event__startswith="Report ")
        .order_by("at")
        .values_list("event", flat=True)
    )
    assert events == [
        "Report made",
        "Report made",
        "Report made",
        "Report done",
        "Report seen",
        "Report done",
    ]
    for row in Row.objects.filter(event__startswith="Report "):
        assert "problem." not in json.dumps(row.details).lower()
    only = client.get("/panel/reports?state=new").content.decode()
    assert "An idea." in only and "First problem." not in only
    status = client.get("/panel/status").content.decode()
    assert "1 report not yet seen" in status
    assert second.state == "new"


def test_done_reports_are_swept_after_ninety_days(person, admin, operator_mail):
    old = reports.make(by=person, kind="problem", happened="Old and done.")
    reports.mark(old, "done", by=admin)
    Report.objects.filter(pk=old.pk).update(
        marked_at=timezone.now() - timedelta(days=91)
    )
    fresh = reports.make(by=person, kind="problem", happened="Done last week.")
    reports.mark(fresh, "done", by=admin)
    Report.objects.filter(pk=fresh.pk).update(
        marked_at=timezone.now() - timedelta(days=7)
    )
    waiting = reports.make(by=person, kind="problem", happened="Still new.")
    Report.objects.filter(pk=waiting.pk).update(
        made=timezone.now() - timedelta(days=400)
    )
    counts = sweeping.sweep()
    assert counts["done_reports"] == 1
    assert set(Report.objects.values_list("happened", flat=True)) == {
        "Done last week.",
        "Still new.",
    }
    swept = Row.objects.get(event="Reports swept")
    assert swept.details["count"] == 1
    assert sweeping.sweep()["done_reports"] == 0
