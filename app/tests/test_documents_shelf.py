"""v1.213.0: the Documents tab as the shelf (Phase 12 chapter 11).

The rules checked here: a document belongs to the case and may be about an
incident, a camera or nothing; the shelf lists each report with every
comparison made of it and the records it can still be read against, the
pictures as a gallery, and the chips' counts; Compare against from the shelf
asks for the run and lands on the Comparison page, which is a page of its
own under the case bar and refuses what is not the case's; Compare when it is
read waits for the reading; Gideon reads the reports about a record and the
reports compared with it; the cap is the case's; a typed moment is read on
the record's clock.
"""

from __future__ import annotations

import io

import pytest
from core import comparison, document_pages, documents, incidents, settings_store, tasks
from core.cases import Case
from core.comparison import Comparison
from core.documents import Document
from core.models import User
from django.utils import timezone
from tests.helpers import signed_in, stamp
from tests.test_documents import REPORT, make_pdf
from tests.test_documents_read import LINES, video

PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def switched_on(db, monkeypatch):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("incidents", True)
    settings_store.set_to("documents", True)
    settings_store.set_to("documents_compare", True)
    monkeypatch.setattr(
        tasks.read_document, "defer", lambda **f: documents.read(f["document_id"])
    )
    monkeypatch.setattr(tasks.compare_report, "defer", lambda **f: None)
    monkeypatch.setattr(tasks.compare_report_case, "defer", lambda **f: None)
    monkeypatch.setattr(comparison, "on", lambda: True)


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("asker", PASSWORD)


@pytest.fixture
def a_case(person):
    return Case.objects.create(owner=person, name="Traffic stop")


def a_report(person, case, *, incident=None, recording=None, title="Incident report"):
    about = documents.about_of(case, incident=incident, recording=recording)
    report = documents.add(
        case,
        about=about,
        data=make_pdf(REPORT),
        filename="report.pdf",
        title=title,
        by=person,
    )
    report.refresh_from_db()
    return report


def a_done_comparison(report, home, *, findings=None):
    """A comparison written already, the engine left out of it."""
    fields = (
        {"incident": home}
        if isinstance(home, incidents.Incident)
        else ({"case": home} if isinstance(home, Case) else {"recording": home})
    )
    # The signatures as the run would keep them, so the row is not stale.
    signatures = {}
    if isinstance(home, incidents.Incident):
        from core.incident_assistant import cameras_signature, events_signature

        signatures = {
            "events_signature": events_signature(home),
            "cameras_signature": cameras_signature(home),
        }
    return Comparison.objects.create(
        document=report,
        state=comparison.DONE,
        written_at=timezone.now(),
        cameras_used=["first"],
        **signatures,
        findings=findings
        or [
            {
                "id": "f1",
                "mark": "agrees",
                "page": 1,
                "n": 3,
                "paragraph": "A small bag was found in the driver's jacket pocket.",
                "claim": "A bag was found",
                "at": 30.0,
                "why": "Seen at thirty seconds.",
            },
            {
                "id": "f2",
                "mark": "differs",
                "page": 1,
                "n": 4,
                "paragraph": "The driver stated that the bag was not his.",
                "claim": "The driver said the bag was his",
                "at": 60.0,
                "why": "The words say otherwise.",
            },
            {
                "id": "f3",
                "mark": "not_on_camera",
                "page": 2,
                "n": 2,
                "paragraph": "Officer Reyes arrived at 21:58.",
                "claim": "Reyes arrived",
                "at": None,
                "why": "",
            },
        ],
        **fields,
    )


def an_incident(person, a_case):
    first = video(
        person, a_case, "first", stamp=stamp("21:56:19", "BWC2-1"), lines=LINES
    )
    second = video(person, a_case, "second", stamp=stamp("22:01:00", "BWC2-2"))
    return incidents.make(a_case, "Stop", [first, second], by=person), first, second


def a_png() -> bytes:
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (64, 40), (200, 210, 220)).save(out, format="PNG")
    return out.getvalue()


# The shelf ----------------------------------------------------------------------------


def test_the_shelf_lists_reports_with_their_comparisons_and_the_pictures(
    person, a_case, client
):
    incident, first, second = an_incident(person, a_case)
    report = a_report(person, a_case, incident=incident)
    loose = a_report(person, a_case, title="Supplement")
    a_done_comparison(report, incident)
    picture = documents.add_picture(
        a_case,
        about={},
        data=a_png(),
        filename="map.png",
        title="Map at 21:57:00, 7 Jun 2025",
        by=person,
    )
    shelf = documents.shelf(a_case)
    assert shelf["counts"] == {
        "all": 3,
        "reports": 2,
        "pictures": 1,
        "compared": 1,
        "not_yet": 1,
        "stale": 0,
    }
    assert shelf["most"] == 12 and shelf["room"] == 9
    rows = {row["document"].pk: row for row in shelf["reports"]}
    compared = rows[report.pk]["comparisons"]
    assert len(compared) == 1 and compared[0]["against_words"] == "Stop"
    assert compared[0]["kind"] == "incident" and compared[0]["total"] == 3
    assert compared[0]["words"].startswith("3 findings: 1 agree, 1 differ, 1 not on")
    assert [part["key"] for part in compared[0]["bar"]] == [
        "agrees",
        "differs",
        "not_on_camera",
    ]
    assert sum(part["pct"] for part in compared[0]["bar"]) > 99
    assert compared[0]["url"].endswith(
        f"/document/{report.pk}/comparison/page?against=incident:{incident.pk}"
    )
    assert rows[report.pk]["about_pill"] == "about Stop"
    # The records a report can still be read against: the case first, the
    # about marked, a camera with a transcript, and the one already compared.
    targets = rows[report.pk]["targets"]
    assert targets[0]["key"] == "case" and targets[0]["possible"]
    by_key = {one["key"]: one for one in targets}
    assert by_key[f"incident:{incident.pk}"]["first"] is True
    assert by_key[f"incident:{incident.pk}"]["exists"] is True
    assert by_key[f"recording:{first.pk}"]["possible"] is True
    assert f"recording:{second.pk}" not in by_key  # no transcript
    assert rows[loose.pk]["comparisons"] == [] and rows[loose.pk]["about_pill"] == ""
    assert shelf["pictures"][0]["document"] == picture
    assert shelf["pictures"][0]["map_url"].endswith("?day=2025-06-07&from=79020")
    # The page.
    signed_in(client, person)
    page = client.get(f"/case/{a_case.pk}?tab=documents").content.decode()
    assert 'id="shelf-chips"' in page and "Compared (1)" in page
    assert "Not yet compared (1)" in page and "Pictures (1)" in page
    assert 'id="documents"' in page and 'id="pictures"' in page
    assert ">Stop<" in page and 'data-compare-against="case"' in page
    assert f'data-compare-against="recording:{first.pk}"' in page
    assert "about nothing in particular" in page
    assert 'id="document-drop"' in page and "documents-shelf.js" in page
    assert "Pictures of the map" in page and "On the map" in page
    assert 'class="menu document-more"' in page


def test_compare_against_from_the_shelf_lands_on_the_page(person, a_case, client):
    incident, first, second = an_incident(person, a_case)
    report = a_report(person, a_case)
    signed_in(client, person)
    base = f"/case/{a_case.pk}/document/{report.pk}"
    told = client.post(
        f"{base}/compare", {"against": f"incident:{incident.pk}", "next": "page"}
    )
    assert told.status_code == 302
    assert told.url == f"{base}/comparison/page?against=incident:{incident.pk}"
    made = Comparison.objects.get()
    assert made.incident == incident and made.state == "queued"
    page = client.get(told.url).content.decode()
    assert 'id="comparison"' in page and "comparison-page.js" in page
    assert 'data-home="incident"' in page and f'data-home-id="{incident.pk}"' in page
    assert "Compare against the case" in page and ">Stop" in page
    # Against a camera with a transcript, and the case.
    assert (
        client.get(f"{base}/comparison/page?against=recording:{first.pk}").status_code
        == 200
    )
    assert client.get(f"{base}/comparison/page?against=case").status_code == 200
    got = client.get(f"{base}/comparison?against=recording:{first.pk}").json()
    assert got["home"] == "recording" and got["against_words"] == "first"
    assert got["page_url"].endswith(f"?against=recording:{first.pk}")
    # Not the case's: refused.
    other = Case.objects.create(owner=person, name="Other")
    elsewhere = video(person, other, "elsewhere", lines=LINES)
    assert (
        client.get(
            f"{base}/comparison/page?against=recording:{elsewhere.pk}"
        ).status_code
        == 404
    )
    assert client.get(f"{base}/comparison/page?against=nonsense").status_code == 404
    # A camera without a transcript cannot be compared against: the form
    # lands back on the shelf with the reason.
    told = client.post(
        f"{base}/compare", {"against": f"recording:{second.pk}", "next": "page"}
    )
    assert told.status_code == 302 and told.url == f"/case/{a_case.pk}?tab=documents"
    # A picture has no page.
    picture = documents.add_picture(
        a_case, about={}, data=a_png(), filename="map.png", title="Map", by=person
    )
    assert (
        client.get(
            f"/case/{a_case.pk}/document/{picture.pk}/comparison/page?against=case"
        ).status_code
        == 404
    )


def test_compare_when_it_is_read_waits_for_the_reading(
    person, a_case, client, monkeypatch
):
    incident, first, second = an_incident(person, a_case)
    deferred = []

    class Configured:
        def defer(self, **fields):
            deferred.append(fields)

    monkeypatch.setattr(
        tasks.compare_when_read, "configure", lambda **options: Configured()
    )
    signed_in(client, person)
    fields = {
        "title": "R",
        "file": io.BytesIO(make_pdf(REPORT)),
        "about": "incident",
        "incident": str(incident.pk),
        "compare": "about",
    }
    fields["file"].name = "r.pdf"
    told = client.post(f"/case/{a_case.pk}/documents/add", fields)
    assert told.status_code == 302
    document = Document.objects.get()
    assert deferred == [
        {
            "document_id": str(document.pk),
            "against": f"incident:{incident.pk}",
            "user_id": person.pk,
            "attempt": 1,
        }
    ]
    # The task's step: the document is ready (the fixture read it at once),
    # so the comparison is asked for.
    document_pages.compare_when_read(
        str(document.pk), f"incident:{incident.pk}", person.pk, 1
    )
    assert comparison.of(document, incident) is not None
    # Still being read: asked again later, up to the limit; failed: given up.
    deferred.clear()
    Document.objects.filter(pk=document.pk).update(state=documents.READING)
    document_pages.compare_when_read(str(document.pk), "case", person.pk, 1)
    assert deferred and deferred[0]["attempt"] == 2
    deferred.clear()
    document_pages.compare_when_read(
        str(document.pk), "case", person.pk, document_pages.COMPARE_WHEN_READ_TRIES
    )
    assert deferred == []
    Document.objects.filter(pk=document.pk).update(state=documents.FAILED)
    document_pages.compare_when_read(str(document.pk), "case", person.pk, 1)
    assert deferred == [] and comparison.of(document, a_case) is None
    # Not yet: nothing deferred.
    fields = {"title": "S", "file": io.BytesIO(make_pdf(REPORT)), "compare": "none"}
    fields["file"].name = "s.pdf"
    client.post(f"/case/{a_case.pk}/documents/add", fields)
    assert deferred == []


def test_gideon_reads_what_is_about_a_record_and_what_was_compared_with_it(
    person, a_case
):
    incident, first, second = an_incident(person, a_case)
    about = a_report(person, a_case, incident=incident, title="About it")
    compared = a_report(person, a_case, title="Compared with it")
    neither = a_report(person, a_case, title="Neither")
    a_done_comparison(compared, incident)
    read = [one.title for one in documents.read_with(incident)]
    assert read == ["About it", "Compared with it"]
    assert neither.title not in read
    # A picture is never read.
    documents.add_picture(
        a_case,
        about={"incident": incident},
        data=a_png(),
        filename="map.png",
        title="Map",
        by=person,
    )
    assert len(documents.read_with(incident)) == 2
    # The Reports line on Details.
    line = comparison.details_line(incident)
    assert [one["title"] for one in line["compared"]] == ["Compared with it"]
    assert line["compared"][0]["against_words"] == "Stop"
    assert [one["title"] for one in line["about"]] == ["Map", "About it"]
    assert line["compare_url"].endswith(
        f"?tab=documents&against=incident:{incident.pk}"
    )
    # A recording's line the same way.
    a_done_comparison(about, first)
    line = comparison.details_line(first)
    assert [one["title"] for one in line["compared"]] == ["About it"]
    assert line["words"] == "this camera"
    assert [one.title for one in documents.read_with(first)] == ["About it"]


def test_the_cap_is_the_cases_and_a_typed_moment_is_read_on_the_clock(person, a_case):
    incident, first, second = an_incident(person, a_case)
    settings_store.set_to("documents_per_case", 1)
    a_report(person, a_case)
    with pytest.raises(documents.Refused, match="This case already has 1 documents"):
        a_report(person, a_case, title="Another")
    with pytest.raises(documents.Refused, match="already has 1 documents"):
        documents.add_picture(
            a_case, about={}, data=a_png(), filename="map.png", title="Map", by=person
        )
    assert settings_store.definition("documents_per_case").default == 12
    with pytest.raises(KeyError):
        settings_store.definition("documents_per_home")
    # A moment typed in words for a Not on camera finding.
    assert document_pages._moment_from_words("01:30", first) == 90.0
    assert document_pages._moment_from_words("00:01:30", first) == 90.0
    assert document_pages._moment_from_words("nonsense", first) is None
    assert document_pages._moment_from_words("1:2:3:4", first) is None
    # On the incident's clock: the words come back as the same time of day.
    at = document_pages._moment_from_words("21:57:19", incident)
    assert at is not None and incidents.time_of_day(incident, at) == "21:57:19"
