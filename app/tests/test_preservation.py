"""v1.244.0: the Preservation copy, from the case's Details tab (Phase 14
chapter 1; the drawing phase-14-preservation-copy-details.html).

The rules checked here: the part sits on the Details tab above Delete case
and says where the copy stands; Make queues the work and the worker writes
one zip with the layout the chapter fixes, every document a PDF; what was
uploaded is listed and left out while a Recording made in the app and a saved
picture of the map go in; a Clip is recorded and its file left out; the copy
is kept on the Case, replaced only once a new one is ready, marked behind
once the Case has changed and never by its being opened; Stop leaves nothing;
a document that cannot be made fails the whole copy by name; a download
writes its audit row; the copy goes with the Case; the PDF maker is run as
the research note says; and the words are in the glossary, the guides, the
specification and the changelog.
"""

from __future__ import annotations

import io
import subprocess
import zipfile
from pathlib import Path

import pytest
from core import cases, pdf_maker, preservation, settings_store
from core.audit import Row
from core.cases import Case
from core.clips import Clip, RenderState
from core.jobs import Segment, Transcript
from core.models import User
from core.notes import MomentNote
from core.preservation import PreservationCopy
from core.recordings import Batch, MediaState, Recording
from tests.helpers import signed_in

PASSWORD = "a-long-enough-password"
APP = Path(__file__).resolve().parent.parent
ROOT = APP.parent


@pytest.fixture
def owner(db):
    return User.objects.from_directory("jsmith", display_name="J Smith")


@pytest.fixture
def stranger(db):
    return User.objects.from_directory("mjones", display_name="M Jones")


@pytest.fixture
def a_case(owner):
    settings_store.set_to("folder_management", True)
    return Case.objects.create(owner=owner, name="Ramirez")


@pytest.fixture
def a_maker(monkeypatch):
    """A stand-in for LibreOffice: each Word file becomes a small file that
    says it is a PDF, and what it was asked for is kept."""
    asked = []

    def convert(sources, out_dir):
        out_dir.mkdir(parents=True, exist_ok=True)
        asked.append([one.name for one in sources])
        made = []
        for one in sources:
            assert one.read_bytes()[:2] == b"PK", "a Word file is a zip"
            pdf = out_dir / f"{one.stem}.pdf"
            pdf.write_bytes(b"%PDF-1.7 stand-in")
            made.append(pdf)
        return made

    monkeypatch.setattr(pdf_maker, "convert", convert)
    monkeypatch.setattr(pdf_maker, "binary", lambda: "soffice")
    return asked


def a_recording(person, case, title="Stop", filename="stop.mp4", **more):
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        case=case,
        title=title,
        original_filename=filename,
        media_state=MediaState.READY,
        playback_ready=True,
        **more,
    )
    recording.folder.mkdir(parents=True, exist_ok=True)
    return recording


def a_transcript(recording, words="Good morning."):
    transcript = Transcript.objects.create(recording=recording, language="en")
    Segment.objects.create(
        transcript=transcript, start=0, end=4, text=words, speaker="Rowe"
    )
    return transcript


def made(case, by) -> PreservationCopy:
    """A copy queued and made, as the press and the worker do between them."""
    copy = preservation.start(case, by)
    preservation.make(str(copy.pk))
    copy.refresh_from_db()
    return copy


def names_in(copy) -> list[str]:
    with zipfile.ZipFile(copy.path) as bundle:
        return bundle.namelist()


# The part on the Details tab ---------------------------------------------------


def test_the_details_tab_carries_the_part_above_delete_case(a_case, owner, client):
    page = signed_in(client, owner).get(f"/case/{a_case.pk}?tab=details")
    page = page.content.decode()
    assert 'id="preservation"' in page
    assert "<h3>Preservation copy</h3>" in page and "none made yet" in page
    assert "to save to the client's file of record" in page
    assert "Make the Preservation copy" in page
    assert page.index('id="preservation"') < page.index('id="delete-case"')
    assert "preservation.js" in page
    # No other tab carries it or its script.
    other = client.get(f"/case/{a_case.pk}").content.decode()
    assert 'id="preservation"' not in other and "preservation.js" not in other


def test_a_build_without_the_maker_says_so_and_greys_the_press(
    a_case, owner, client, monkeypatch
):
    monkeypatch.setattr(pdf_maker, "binary", lambda: None)
    browser = signed_in(client, owner)
    page = browser.get(f"/case/{a_case.pk}?tab=details").content.decode()
    assert pdf_maker.NOT_INSTALLED in page
    assert 'data-act="make" disabled' in page
    answer = browser.post(f"/case/{a_case.pk}/preservation/make")
    assert answer.status_code == 409
    assert answer.json()["error"] == pdf_maker.NOT_INSTALLED
    assert not PreservationCopy.objects.exists()


# Making it -------------------------------------------------------------------


def test_make_queues_it_and_the_worker_writes_the_zip(a_case, owner, client, a_maker):
    a_transcript(a_recording(owner, a_case))
    browser = signed_in(client, owner)
    answer = browser.post(f"/case/{a_case.pk}/preservation/make")
    assert answer.status_code == 200
    told = answer.json()
    assert told["making"] is True and "being made" in told["html"]
    assert "You can leave this page." in told["html"]
    copy = PreservationCopy.objects.get()
    assert copy.state == preservation.QUEUED and copy.made_by == owner
    # A second press while one is under way starts no second one.
    browser.post(f"/case/{a_case.pk}/preservation/make")
    assert PreservationCopy.objects.count() == 1

    preservation.make(str(copy.pk))
    copy.refresh_from_db()
    assert copy.state == preservation.READY
    assert copy.documents_done == copy.documents_total == 4
    assert copy.size_bytes == copy.path.stat().st_size > 0
    assert copy.path.parent == a_case.folder / "preservation"
    assert names_in(copy) == [
        "00 Read me first.pdf",
        "01 Recordings/Stop/Transcript.pdf",
        "08 Recordings and documents, listed.pdf",
        "10 Activity record.pdf",
    ]
    row = Row.objects.get(event="preservation copy made")
    assert row.object_id == str(a_case.pk) and row.details["documents"] == 4

    told = browser.get(f"/case/{a_case.pk}/preservation").json()
    assert told == {"making": False, "state": "ready", "html": told["html"]}
    assert "ready" in told["html"] and "by J Smith" in told["html"]
    assert "4 documents" in told["html"] and ">Download</a>" in told["html"]
    assert "Save it to the client's file of record." in told["html"]


def test_the_layout_what_goes_in_and_what_is_only_listed(a_case, owner, a_maker):
    from core import documents

    uploaded = a_recording(owner, a_case, "Body camera", "bwc.mp4")
    uploaded.original_path.write_bytes(b"video that the office holds already")
    a_transcript(uploaded)
    here = a_recording(
        owner, a_case, "Interview", "interview.webm", live={"from": "recorder"}
    )
    here.original_path.write_bytes(b"sound recorded in the app")
    a_transcript(here)
    not_done = a_recording(owner, a_case, "Still waiting", "later.mp4")
    MomentNote.objects.create(
        recording=uploaded, at=3.0, note="Look here", note_by=owner
    )
    Clip.objects.create(
        recording=uploaded,
        user=owner,
        title="The stop",
        start=0.0,
        end=4.0,
        state=RenderState.READY,
    )
    picture = documents.Document.objects.create(
        case=a_case,
        title="Map at 20:26",
        kind=documents.PICTURE,
        original_filename="map.png",
        state=documents.READY,
        added_by=owner,
    )
    picture.folder.mkdir(parents=True, exist_ok=True)
    picture.original_path.write_bytes(b"PNG picture made in the app")
    report = documents.Document.objects.create(
        case=a_case,
        title="Incident report",
        kind=documents.REPORT,
        original_filename="report.pdf",
        state=documents.READY,
        added_by=owner,
    )
    report.folder.mkdir(parents=True, exist_ok=True)
    report.original_path.write_bytes(b"%PDF uploaded report")

    copy = made(a_case, owner)
    assert copy.state == preservation.READY, copy.reason
    names = names_in(copy)
    assert names == [
        "00 Read me first.pdf",
        "01 Recordings/Body camera/Transcript.pdf",
        "01 Recordings/Interview/Transcript.pdf",
        "01 Recordings/Interview/interview.webm",
        "03 Notes and chronology/Notes.pdf",
        "06 Map pictures and timelapses/Map at 20-26.png",
        "07 Record of clips.pdf",
        "08 Recordings and documents, listed.pdf",
        "10 Activity record.pdf",
    ]
    with zipfile.ZipFile(copy.path) as bundle:
        # The Recording made in the app goes in as it was recorded.
        sound = bundle.read("01 Recordings/Interview/interview.webm")
        assert sound == b"sound recorded in the app"
    # Nothing that was uploaded, no Clip file, nothing of a Recording with
    # no Transcript.
    assert not [n for n in names if n.endswith((".mp4", ".m4a"))]
    assert not [n for n in names if "Still waiting" in n or "report" in n.lower()]
    assert not_done.pk and report.pk
    # Every Word document was handed to the maker, in batches.
    assert sum(len(batch) for batch in a_maker) == copy.documents_total - 2
    assert max(len(batch) for batch in a_maker) <= preservation.BATCH


def test_the_documents_written_here_say_what_the_chapter_fixes(a_case, owner):
    from docx import Document

    recording = a_recording(owner, a_case, "Body camera", "bwc.mp4")
    a_transcript(recording, "Step out of the car.")
    Clip.objects.create(
        recording=recording, user=owner, title="The stop", start=0.0, end=4.0
    )
    MomentNote.objects.create(
        recording=recording, at=3.0, note="Look here", note_by=owner
    )

    def text_of(body: bytes) -> str:
        document = Document(io.BytesIO(body))
        cells = [
            cell.text
            for table in document.tables
            for row in table.rows
            for cell in row.cells
        ]
        return "\n".join([p.text for p in document.paragraphs] + cells)

    by_name = {one.name: one for one in preservation.plan(a_case, owner)}
    first = text_of(by_name["00 Read me first"].word())
    assert preservation.SAVE_IT in first and "Ramirez" in first
    assert "IN THIS COPY" in first and "NOT IN THIS COPY" in first
    assert "1 transcript (folder 01)" in first
    assert "The 1 recording that were uploaded." in first
    assert "The 1 clip as files. File 07 says which recording" in first
    clips = text_of(by_name["07 Record of clips"].word())
    assert "1. The stop" in clips and "bwc.mp4" in clips
    assert "00:00:00 to 00:00:04 (4 s)" in clips
    assert "Rowe: Step out of the car." in clips
    notes = text_of(by_name["03 Notes and chronology/Notes"].word())
    assert "[00:00:03] Look here" in notes and "J Smith" in notes
    listed = text_of(by_name["08 Recordings and documents, listed"].word())
    assert "bwc.mp4" in listed and "SHA-256" in listed
    activity = text_of(by_name["10 Activity record"].word())
    assert "oldest first" in activity


# Kept, behind, stopped, failed ---------------------------------------------------


def test_behind_the_case_after_a_change_and_never_after_an_opening(
    a_case, owner, client, a_maker
):
    recording = a_recording(owner, a_case)
    a_transcript(recording)
    made(a_case, owner)
    assert preservation.for_page(a_case)["state"] == "ready"
    # Opening the Case is use, and changes nothing in it.
    signed_in(client, owner).get(f"/case/{a_case.pk}?tab=details")
    cases.note_activity(a_case, by=owner)
    assert preservation.for_page(a_case)["state"] == "ready"
    MomentNote.objects.create(recording=recording, at=1.0, note="New", note_by=owner)
    told = preservation.for_page(a_case)
    assert told["state"] == "behind"
    page = client.get(f"/case/{a_case.pk}?tab=details").content.decode()
    assert "behind the case" in page and "the case has changed since" in page
    assert "Download the one of" in page and "Make it again" in page


def test_a_new_copy_replaces_the_old_one_only_once_it_is_ready(a_case, owner, a_maker):
    a_transcript(a_recording(owner, a_case))
    first = made(a_case, owner)
    old = first.path
    second = preservation.start(a_case, owner)
    # While the second is under way the first is still there to download.
    assert preservation.ready(a_case) == first and old.exists()
    preservation.make(str(second.pk))
    assert list(PreservationCopy.objects.values_list("pk", flat=True)) == [second.pk]
    assert not old.exists() and preservation.ready(a_case).path.exists()
    assert a_case.disk_bytes() >= preservation.ready(a_case).size_bytes > 0


def test_stop_ends_it_and_leaves_nothing_behind(a_case, owner, client, a_maker):
    a_transcript(a_recording(owner, a_case))
    browser = signed_in(client, owner)
    browser.post(f"/case/{a_case.pk}/preservation/make")
    copy = PreservationCopy.objects.get()
    told = browser.post(f"/case/{a_case.pk}/preservation/stop").json()
    assert told["making"] is False and "none made yet" in told["html"]
    copy.refresh_from_db()
    assert copy.state == preservation.STOPPED
    # The worker, reaching it late, makes nothing.
    preservation.make(str(copy.pk))
    assert not copy.path.exists() and a_maker == []
    assert Row.objects.filter(event="preservation copy stopped").count() == 1


def test_a_document_that_cannot_be_made_fails_the_whole_copy_by_name(
    a_case, owner, client, monkeypatch
):
    a_transcript(a_recording(owner, a_case))
    monkeypatch.setattr(pdf_maker, "binary", lambda: "soffice")

    def convert(sources, out_dir):
        raise pdf_maker.Failed(f"{sources[1].stem} could not be turned into a PDF.")

    monkeypatch.setattr(pdf_maker, "convert", convert)
    copy = made(a_case, owner)
    assert copy.state == preservation.FAILED
    assert copy.reason == "Transcript could not be turned into a PDF."
    assert not copy.path.exists()
    assert Row.objects.get(event="preservation copy failed").details["reason"]
    page = signed_in(client, owner).get(f"/case/{a_case.pk}?tab=details")
    page = page.content.decode()
    assert "could not be made" in page
    assert "Transcript could not be turned into a PDF." in page
    assert "Make the Preservation copy" in page


# Downloading, and who may ------------------------------------------------------


def test_download_names_the_zip_and_writes_its_row(a_case, owner, client, a_maker):
    a_transcript(a_recording(owner, a_case))
    browser = signed_in(client, owner)
    assert browser.get(f"/case/{a_case.pk}/preservation/download").status_code == 404
    copy = made(a_case, owner)
    answer = browser.get(f"/case/{a_case.pk}/preservation/download")
    assert answer.status_code == 200 and answer["Content-Type"] == "application/zip"
    day = f"{copy.finished:%Y}"
    assert "Ramirez%20-%20preservation%20copy%20" + day in answer["Content-Disposition"]
    body = b"".join(answer.streaming_content)
    assert zipfile.ZipFile(io.BytesIO(body)).namelist()[0] == "00 Read me first.pdf"
    row = Row.objects.get(event="export made")
    assert row.details["kind"] == "preservation copy"
    assert row.object_type == "case" and row.object_id == str(a_case.pk)


def test_a_stranger_is_told_there_is_no_such_case(a_case, owner, stranger, client):
    browser = signed_in(client, stranger)
    for way, address in (
        ("get", "preservation"),
        ("post", "preservation/make"),
        ("post", "preservation/stop"),
        ("get", "preservation/download"),
    ):
        answer = getattr(browser, way)(f"/case/{a_case.pk}/{address}")
        assert answer.status_code == 404, address
    assert not PreservationCopy.objects.exists()


def test_an_admin_looking_in_may_make_one_and_asking_how_it_stands_is_quiet(
    a_case, owner, client, a_maker
):
    admin = User.objects.create_local_admin("asker", PASSWORD)
    a_transcript(a_recording(owner, a_case))
    browser = signed_in(client, admin)
    assert browser.post(f"/case/{a_case.pk}/preservation/make").status_code == 200
    before = Row.objects.count()
    # Asked every few seconds while one is being made: never an audit row.
    for _ in range(3):
        assert browser.get(f"/case/{a_case.pk}/preservation").status_code == 200
    assert Row.objects.count() == before
    copy = PreservationCopy.objects.get()
    preservation.make(str(copy.pk))
    row = Row.objects.get(event="preservation copy made")
    assert row.actor_username == "asker" and row.affected_username == "jsmith"


def test_the_copy_goes_with_the_case(a_case, owner, a_maker):
    a_transcript(a_recording(owner, a_case))
    copy = made(a_case, owner)
    path = copy.path
    assert path.exists()
    cases.delete(a_case, actor=owner)
    assert not path.exists() and not PreservationCopy.objects.exists()


# The PDF maker ---------------------------------------------------------------


def test_the_maker_runs_libreoffice_as_the_research_note_says(tmp_path, monkeypatch):
    ran = {}

    def run(command, **how):
        ran["command"] = command
        ran["how"] = how
        out = Path(command[command.index("--outdir") + 1])
        for one in command[command.index("--outdir") + 2 :]:
            (out / f"{Path(one).stem}.pdf").write_bytes(b"%PDF-1.7")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    monkeypatch.setattr(pdf_maker, "binary", lambda: "/usr/bin/soffice")
    monkeypatch.setattr(subprocess, "run", run)
    sources = [tmp_path / "00001.docx", tmp_path / "00002.docx"]
    for one in sources:
        one.write_bytes(b"PK")
    made_ = pdf_maker.convert(sources, tmp_path / "pdf")
    assert [one.name for one in made_] == ["00001.pdf", "00002.pdf"]
    command = ran["command"]
    assert command[0] == "/usr/bin/soffice"
    assert "--headless" in command and "--norestore" in command
    # PDF/A-2b, asked for in the filter's own words.
    assert command[command.index("--convert-to") + 1] == pdf_maker.FILTER
    assert '"SelectPdfVersion":{"type":"long","value":"2"}' in pdf_maker.FILTER
    # A profile of its own, which is also its home, and gone afterwards.
    profile = [a for a in command if a.startswith("-env:UserInstallation=file://")]
    assert len(profile) == 1
    home = Path(ran["how"]["env"]["HOME"])
    assert home.name.startswith("transcribe-pdf-profile-") and not home.exists()
    assert ran["how"]["timeout"] == 60 + 60 * 2 and "shell" not in ran["how"]


def test_the_maker_fails_by_name_and_says_when_it_is_not_there(tmp_path, monkeypatch):
    monkeypatch.setattr(pdf_maker, "binary", lambda: None)
    with pytest.raises(pdf_maker.Failed, match="not in this build"):
        pdf_maker.convert([tmp_path / "a.docx"], tmp_path / "pdf")
    monkeypatch.setattr(pdf_maker, "binary", lambda: "soffice")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda c, **how: subprocess.CompletedProcess(c, 1, b"", b"no"),
    )
    (tmp_path / "Memo.docx").write_bytes(b"PK")
    with pytest.raises(pdf_maker.Failed, match="Memo could not be turned into a PDF"):
        pdf_maker.convert([tmp_path / "Memo.docx"], tmp_path / "pdf")


# The image, and the words ------------------------------------------------------


def test_the_image_carries_the_maker_and_proves_it_at_build():
    build = (APP / "Dockerfile").read_text(encoding="utf-8")
    for wanted in (
        "libreoffice-writer-nogui",
        "fonts-crosextra-carlito",
        "COPY app/fonts-for-pdf.conf /etc/fonts/conf.d/45-transcribe-pdf.conf",
        "fc-match Calibri | grep -qi carlito",
        'fc-match Consolas | grep -qi "dejavu sans mono"',
        # A conversion by the app's own command, with the network cut.
        "RUN --network=none cd /tmp/pdfcheck",
        "pdf_maker.convert(",
        "assert b'pdfaid:part' in data, 'not a PDF/A'",
    ):
        assert wanted in build, wanted
    faces = (APP / "fonts-for-pdf.conf").read_text(encoding="utf-8")
    assert "<family>Carlito</family>" in faces
    assert "<family>DejaVu Sans Mono</family>" in faces
    licences = (ROOT / "THIRD_PARTY_LICENSES.md").read_text(encoding="utf-8")
    assert "| LibreOffice Writer (no-GUI packages) | MPL-2.0 |" in licences
    assert "| Carlito (font) | OFL-1.1 |" in licences


def test_the_words_are_in_the_glossary_the_guides_the_spec_and_the_changelog():
    glossary = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    assert "**Preservation copy**:" in glossary
    spec = (ROOT / "docs" / "spec" / "SPEC-PHASE-14.md").read_text(encoding="utf-8")
    assert "## 1. The Preservation copy, from the Details tab (v1.244.0)" in spec
    assert "### What the next releases add" in spec
    note = (ROOT / "docs" / "research" / "pdf-maker.md").read_text(encoding="utf-8")
    assert "--disable-online-update" in note and "SelectPdfVersion" in note
    drawing = ROOT / "docs/spec/mockups/phase-14-preservation-copy-details.html"
    # The drawing is kept; the local demo's picture is not.
    assert drawing.exists() and "<img" not in drawing.read_text(encoding="utf-8")
    guide = (ROOT / "docs" / "user-guide.md").read_text(encoding="utf-8")
    assert "**Preservation copy**" in guide
    assert "Save it to the client's file of record" in guide
    admin = (ROOT / "docs" / "admin-guide.md").read_text(encoding="utf-8")
    assert "Preservation copy" in admin and "LibreOffice" in admin
    log = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## v1.244.0" in log and "Database: migrates" in log
