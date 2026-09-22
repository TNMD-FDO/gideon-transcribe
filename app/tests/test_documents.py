"""v1.71.0: Documents beside the cameras, part 1 (Phase 8, chapter 4).

The rules checked here: a PDF is added from an incident or a recording and
never loose, refused over the page ceiling or the count or when it is not a
PDF, with the reason; the reading on the media queue keeps each page's
words as numbered paragraphs by the gaps on the page, marks a page read by
OCR or poorly read, and draws every page; the case's Documents tab lists
them with Re-link and Remove, the two Details tabs carry the report and Add
the report, the document page opens at a cited paragraph, the pictures are
served to whoever may open the case; Search's Documents kind hits a
paragraph; a document goes with its case; the settings are the chapter's;
one audit row each, never a word.
"""

from __future__ import annotations

import io
import json

import pytest
from core import case_search, documents, incidents, settings_store, tasks
from core.audit import Row
from core.cases import Case
from core.documents import Document, DocumentPage
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording

PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"


@pytest.fixture(autouse=True)
def switched_on(db, monkeypatch):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("incidents", True)
    # The reading runs at once, in the test, instead of on the media queue.
    monkeypatch.setattr(
        tasks.read_document, "defer", lambda **f: documents.read(f["document_id"])
    )


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("asker", PASSWORD)


@pytest.fixture
def a_case(person):
    return Case.objects.create(owner=person, name="Traffic stop")


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def stamp(time: str, camera: str):
    return {
        "date": "06/07/2025",
        "time": time,
        "camera": camera,
        "at": 2.0,
        "checked": True,
    }


def video(person, case, title, *, stamp=None):
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        case=case,
        title=title,
        original_filename=f"{title}.mp4",
        media_state=MediaState.READY,
        duration_seconds=600.0,
        playback_ready=True,
        stamp=stamp,
        probe={},
    )
    recording.folder.mkdir(parents=True, exist_ok=True)
    (recording.folder / "playback.mp4").write_bytes(b"not really media")
    return recording


# A PDF made by hand: Helvetica text, one content stream per page, so the
# reader finds real words with positions. `pages` is a list of pages, each a
# list of (y, text) lines; a blank line's gap makes a new paragraph.
def make_pdf(pages: list[list[tuple[int, str]]]) -> bytes:
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids = []
    for lines in pages:
        content = b"BT /F1 11 Tf\n"
        for y, text in lines:
            safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            content += f"1 0 0 1 72 {y} Tm ({safe}) Tj\n".encode("latin-1")
        content += b"ET"
        stream = add(
            b"<< /Length "
            + str(len(content)).encode()
            + b" >>\nstream\n"
            + content
            + b"\nendstream"
        )
        page_ids.append(len(objects) + 1)
        add(b"")  # placeholder for the page, filled below
        objects[-1] = (
            b"<< /Type /Page /Parent PAGES /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 "
            + str(font).encode()
            + b" 0 R >> >> /Contents "
            + str(stream).encode()
            + b" 0 R >>"
        )
    kids = b" ".join(f"{pid} 0 R".encode() for pid in page_ids)
    pages_id = add(
        b"<< /Type /Pages /Kids ["
        + kids
        + b"] /Count "
        + str(len(page_ids)).encode()
        + b" >>"
    )
    objects = [one.replace(b"PAGES", f"{pages_id} 0 R".encode()) for one in objects]
    catalog = add(b"<< /Type /Catalog /Pages " + str(pages_id).encode() + b" 0 R >>")
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    trailer = f"trailer\n<< /Size {len(objects) + 1} /Root {catalog} 0 R >>\n"
    out.write((trailer + f"startxref\n{xref}\n%%EOF\n").encode())
    return out.getvalue()


REPORT = [
    [
        (728, "INCIDENT REPORT"),
        (700, "On 7 June 2025 at about 21:56 hours I stopped a grey sedan on Route 9."),
        (686, "The driver was asked to step out of the vehicle for a pat-down."),
        (650, "A small bag was found in the driver's jacket pocket."),
        (636, "The driver stated that the bag was not his."),
    ],
    [
        (728, "SUPPLEMENT"),
        (700, "Officer Reyes arrived at 21:58 and stood by the passenger door."),
        (660, "A tow truck was requested at 22:11 hours."),
    ],
]


def add_report(
    client,
    case,
    *,
    incident=None,
    recording=None,
    pages=REPORT,
    title="Incident report",
):
    data = make_pdf(pages)
    fields = {"title": title, "file": io.BytesIO(data)}
    fields["file"].name = "report.pdf"
    if incident is not None:
        fields["incident"] = str(incident.pk)
    if recording is not None:
        fields["recording"] = str(recording.pk)
    return client.post(f"/case/{case.pk}/documents/add", fields)


# Adding and reading -------------------------------------------------------------------


def test_a_report_is_added_to_an_incident_read_split_and_drawn(person, a_case, client):
    first = video(person, a_case, "first", stamp=stamp("21:56:19", "BWC2-1"))
    second = video(person, a_case, "second", stamp=stamp("22:01:00", "BWC2-2"))
    incident = incidents.make(a_case, "Stop", [first, second], by=person)
    signed_in(client, person)
    page = client.get(
        f"/case/{a_case.pk}/documents/add?incident={incident.pk}"
    ).content.decode()
    assert "Add the report" in page and "PDFs only" in page and "Up to 60 pages" in page
    assert "Nothing leaves the building" in page and "Stop" in page
    told = add_report(client, a_case, incident=incident)
    assert told.status_code == 302 and told.url == incident.url()
    document = Document.objects.get()
    assert document.state == "ready" and document.pages == 2
    assert document.incident == incident and document.case == a_case
    assert document.title == "Incident report" and document.ocr_pages == 0
    assert document.pages_line() == "2 pages"
    assert document.original_path.exists() and document.picture_path(2).exists()
    rows = list(document.page_rows.order_by("number"))
    assert [row.number for row in rows] == [1, 2]
    # The gaps on the page make the paragraphs; the numbers start on each page.
    texts = [one["text"] for one in rows[0].paragraphs]
    assert texts[0] == "INCIDENT REPORT"
    assert texts[1].startswith("On 7 June 2025") and "pat-down." in texts[1]
    assert texts[2].startswith("A small bag") and texts[2].endswith("not his.")
    assert [one["n"] for one in rows[0].paragraphs] == [1, 2, 3]
    assert rows[1].paragraphs[1]["text"].startswith("Officer Reyes")
    box = rows[0].paragraphs[1]["box"]
    assert 60 < box[0] < 80 and box[1] < box[3] and rows[0].width == 612.0
    assert rows[0].text.count("\n") == 2 and not rows[0].ocr and not rows[0].poor
    # The row, never the words.
    row = Row.objects.get(event="Document added")
    assert row.object_label == "Incident report" and row.details["pages"] == 2
    assert row.details["home"] == "incident"
    assert "sedan" not in json.dumps(row.details).lower()
    # The incident's state carries it for the Details tab.
    state = client.get(f"{incident.url()}/state").json()
    assert state["incident"]["documents"][0]["title"] == "Incident report"
    assert state["incident"]["documents"][0]["pages_line"] == "2 pages"
    assert state["incident"]["add_document_url"].endswith(f"?incident={incident.pk}")


def test_a_report_is_added_to_a_recording_and_shown_on_its_details(
    person, a_case, client
):
    recording = video(person, a_case, "first")
    signed_in(client, person)
    page = client.get(f"/recording/{recording.pk}").content.decode()
    assert "No report yet for this recording" in page and "Add the report" in page
    assert f"/case/{a_case.pk}/documents/add?recording={recording.pk}" in page
    told = add_report(client, a_case, recording=recording, title="  ")
    assert told.status_code == 302 and told.url.startswith(f"/recording/{recording.pk}")
    document = Document.objects.get()
    assert document.recording == recording and document.title == "report"
    page = client.get(f"/recording/{recording.pk}").content.decode()
    assert f'href="{document.url()}"' in page and "2 pages" in page


def test_what_does_not_fit_is_refused_with_the_reason(person, a_case, client):
    recording = video(person, a_case, "first")
    other = Case.objects.create(owner=person, name="Other")
    elsewhere = video(person, other, "elsewhere")
    signed_in(client, person)
    # Not a PDF.
    fields = {"recording": str(recording.pk), "file": io.BytesIO(b"hello")}
    fields["file"].name = "notes.docx"
    page = client.post(f"/case/{a_case.pk}/documents/add", fields).content.decode()
    assert "Only a PDF can be added" in page and Document.objects.count() == 0
    # Over the page ceiling.
    settings_store.set_to("documents_pages_most", 1)
    page = add_report(client, a_case, recording=recording).content.decode()
    assert "has 2 pages; the most is 1" in page and Document.objects.count() == 0
    settings_store.set_to("documents_pages_most", 60)
    # Over the count.
    settings_store.set_to("documents_per_home", 1)
    assert add_report(client, a_case, recording=recording).status_code == 302
    page = add_report(client, a_case, recording=recording).content.decode()
    assert "already has 1 documents" in page and Document.objects.count() == 1
    # Never loose, and never to another case's recording: the page says why.
    page = client.post(
        f"/case/{a_case.pk}/documents/add", {"title": "x"}
    ).content.decode()
    assert "Say which incident or recording" in page
    fields = {"recording": str(elsewhere.pk), "file": io.BytesIO(make_pdf(REPORT))}
    fields["file"].name = "r.pdf"
    page = client.post(f"/case/{a_case.pk}/documents/add", fields).content.decode()
    assert "Say which incident or recording" in page and Document.objects.count() == 1
    # Off: the tab, the link and the page are gone; the document stays.
    settings_store.set_to("documents", False)
    page = client.get(f"/case/{a_case.pk}").content.decode()
    assert "?tab=documents" not in page
    assert (
        client.get(
            f"/case/{a_case.pk}/documents/add?recording={recording.pk}"
        ).status_code
        == 404
    )
    assert (
        "Add the report"
        not in client.get(f"/recording/{recording.pk}").content.decode()
    )
    assert Document.objects.count() == 1
    # The settings are the chapter's, on a Documents page.
    for key in (
        "documents",
        "documents_pages_most",
        "documents_per_home",
        "documents_ocr",
    ):
        assert settings_store.definition(key).page == "documents"


def test_a_scan_is_read_by_ocr_and_marked_and_a_poor_page_says_so(
    person, a_case, client, monkeypatch
):
    recording = video(person, a_case, "first")
    signed_in(client, person)
    import pytesseract

    def fake_ocr(picture, lang, output_type):
        # One good page of words, then one the engine barely read.
        fake_ocr.calls += 1
        if fake_ocr.calls == 1:
            words = [
                "The",
                "driver",
                "was",
                "asked",
                "to",
                "step",
                "out",
                "of",
                "the",
                "vehicle",
                "for",
                "a",
                "pat",
                "down",
                "by",
                "the",
                "officer",
                "at",
                "the",
                "scene",
            ]
            return {
                "text": words,
                "left": [30 + 40 * n for n in range(len(words))],
                "top": [100] * len(words),
                "width": [36] * len(words),
                "height": [14] * len(words),
                "conf": [91.0] * len(words),
            }
        return {
            "text": ["xq", ""],
            "left": [10, 0],
            "top": [10, 0],
            "width": [20, 0],
            "height": [10, 0],
            "conf": [31.0, -1],
        }

    fake_ocr.calls = 0
    monkeypatch.setattr(pytesseract, "image_to_data", fake_ocr)
    monkeypatch.setattr(pytesseract, "Output", type("O", (), {"DICT": "dict"}))
    monkeypatch.setattr(documents, "ocr_installed", lambda: True)
    # Two pages with no words of their own: a scan.
    told = add_report(client, a_case, recording=recording, pages=[[], []], title="Scan")
    assert told.status_code == 302
    document = Document.objects.get()
    assert (
        document.state == "ready"
        and document.ocr_pages == 2
        and document.poor_pages == 1
    )
    assert document.pages_line() == "2 pages, read by OCR, 1 poorly read"
    first, second = document.page_rows.order_by("number")
    assert first.ocr and not first.poor and "step out of the vehicle" in first.text
    assert second.ocr and second.poor
    # With OCR off, a scan is kept and shown and its words are not read.
    settings_store.set_to("documents_ocr", False)
    add_report(client, a_case, recording=recording, pages=[[]], title="Scan two")
    two = Document.objects.get(title="Scan two")
    assert two.ocr_pages == 0 and two.poor_pages == 1 and two.page_rows.get().text == ""
    page = client.get(two.url()).content.decode()
    assert "poorly read" in page and "No words were read from this page" in page


# The tab, the page, the pictures ------------------------------------------------------


def test_the_documents_tab_lists_relinks_and_removes(person, a_case, client):
    first = video(person, a_case, "first", stamp=stamp("21:56:19", "BWC2-1"))
    second = video(person, a_case, "second", stamp=stamp("22:01:00", "BWC2-2"))
    incident = incidents.make(a_case, "Stop", [first, second], by=person)
    signed_in(client, person)
    page = client.get(f"/case/{a_case.pk}?tab=documents").content.decode()
    assert 'Documents <span class="count">0</span>' in page and "None yet" in page
    add_report(client, a_case, incident=incident)
    document = Document.objects.get()
    page = client.get(f"/case/{a_case.pk}?tab=documents").content.decode()
    assert 'Documents <span class="count">1</span>' in page
    assert "Incident report" in page and "2 pages" in page and ">Stop</a>" in page
    assert f"/case/{a_case.pk}/document/{document.pk}/act" in page and "Re-link" in page
    # Re-link to a recording, then remove; one row each, and the folder goes.
    told = client.post(
        f"/case/{a_case.pk}/document/{document.pk}/act",
        {"action": "relink", "recording": str(first.pk)},
    )
    assert told.status_code == 302
    document.refresh_from_db()
    assert document.recording == first and document.incident is None
    assert Row.objects.filter(event="Document re-linked").count() == 1
    folder = document.folder
    assert folder.exists()
    client.post(f"/case/{a_case.pk}/document/{document.pk}/act", {"action": "remove"})
    assert Document.objects.count() == 0 and DocumentPage.objects.count() == 0
    assert not folder.exists()
    assert Row.objects.get(event="Document removed").object_label == "Incident report"


def test_the_document_page_opens_at_a_cited_paragraph_and_serves_its_pictures(
    person, a_case, client
):
    recording = video(person, a_case, "first")
    signed_in(client, person)
    add_report(client, a_case, recording=recording)
    document = Document.objects.get()
    page = client.get(f"{document.url()}?page=2&para=2").content.decode()
    assert 'data-open="2"' in page and 'data-lit="2"' in page
    assert 'id="sheet-1"' in page and 'id="sheet-2"' in page
    assert 'class="doc-para" data-page="2" data-n="2"' in page
    assert "Officer Reyes arrived" in page and "document.js" in page
    assert 'class="doc-box" data-page="1" data-n="2"' in page
    assert f"/case/{a_case.pk}/document/{document.pk}/page/1.png" in page
    picture = client.get(f"/case/{a_case.pk}/document/{document.pk}/page/1.png")
    assert picture.status_code == 200 and picture["Content-Type"] == "image/png"
    assert b"".join(picture.streaming_content)[:8] == b"\x89PNG\r\n\x1a\n"
    assert (
        client.get(f"/case/{a_case.pk}/document/{document.pk}/page/9.png").status_code
        == 404
    )
    download = client.get(f"/case/{a_case.pk}/document/{document.pk}/download")
    assert (
        download.status_code == 200 and "report.pdf" in download["Content-Disposition"]
    )
    # A stranger sees nothing of it.
    client.logout()
    stranger = User.objects.create(username="nobody", display_name="nobody")
    signed_in(client, stranger)
    assert client.get(document.url()).status_code == 404
    assert (
        client.get(f"/case/{a_case.pk}/document/{document.pk}/page/1.png").status_code
        == 404
    )


# Search, and going with the case ------------------------------------------------------


def test_search_hits_a_paragraph_and_a_document_goes_with_its_case(
    person, a_case, client
):
    recording = video(person, a_case, "first")
    signed_in(client, person)
    add_report(client, a_case, recording=recording)
    document = Document.objects.get()
    got = case_search.search(a_case, "tow truck", "documents")
    assert got["total"] == 1 and got["groups"][0]["head"] == "Incident report"
    hit = got["groups"][0]["hits"][0]
    assert hit["when"] == "page 2, paragraph 3" and hit["who"] == "Document"
    assert hit["url"] == f"{document.url()}?page=2&para=3"
    assert "<mark>tow</mark>" in str(hit["text"])
    counts = {
        one["key"]: one["count"]
        for one in case_search.search(a_case, "driver")["kinds"]
    }
    assert counts["documents"] == 2
    page = client.get(f"/case/{a_case.pk}?tab=search&q=tow+truck").content.decode()
    assert "Documents (1)" in page and "page 2, paragraph 3" in page
    # The hit carries the paragraph card's address (Phase 8 chapter 6).
    assert 'data-para-card="1"' in page and 'data-para="3"' in page
    assert hit["paragraph"] == {
        "url": document.url(),
        "page": 2,
        "n": 3,
        "title": "Incident report",
    }
    # Gone with the case: the document and its pages hang off it.
    from django.db.models import CASCADE

    assert Document._meta.get_field("case").remote_field.on_delete is CASCADE
    assert DocumentPage._meta.get_field("document").remote_field.on_delete is CASCADE
    assert document.folder.is_relative_to(a_case.folder)


def test_paragraphs_follow_the_gaps_and_the_indents():
    def word(text, x, top):
        return {"text": text, "x0": x, "top": top, "x1": x + 30, "bottom": top + 10}

    words = [word("One", 72, 100), word("two", 110, 100), word("three", 72, 114)]
    words += [word("Four", 72, 140)]  # a gap of more than a line
    words += [word("Five", 100, 154)]  # indented: a new paragraph
    got = documents.paragraphs_of(words)
    assert [one["text"] for one in got] == ["One two three", "Four", "Five"]
    assert got[0]["box"] == [72, 100, 140, 124]
    assert documents.paragraphs_of([]) == []
    # A bullet's hanging second line follows a full line and stays with it
    # (a real vacancy notice split one off, 2026-09-19).
    bullet = [word("Manage", 72, 100), word("files", 110, 100)]
    bullet += [word("unit,", 86, 114), word("tracking", 110, 114)]
    bullet += [word("Next", 72, 128), word("bullet", 110, 128)]
    got = documents.paragraphs_of(bullet)
    assert [one["text"] for one in got] == ["Manage files unit, tracking Next bullet"]
