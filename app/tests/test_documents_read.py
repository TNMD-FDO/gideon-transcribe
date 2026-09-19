"""v1.72.0: Documents beside the cameras, part 2 (Phase 8, chapter 4).

The rules checked here: a report is read whole under the reading ceiling
and by the paragraphs matching the question past it, with the line that
says so; a citation names a real paragraph of a document that was read and
comes back resolved with its neighbours, in the case chat, the incident chat
and the recording page's chat; the Report tab is on both pages only while a
document is linked, drawn from the document's state; a document is added
from the Documents tab with a picker (an incident, a recording, or both) and
re-linked on its row; the document page has its ways back; a document read
by an older splitter is read again by the minute task.
"""

from __future__ import annotations

import io
import json

import pytest
from core import case_chat, documents, incident_chat, incidents, settings_store, tasks
from core.case_chat import CaseChat, CaseChatTurn
from core.cases import Case
from core.documents import Document
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording
from tests.test_documents import REPORT, make_pdf
from tests.test_prepare import engine_answering

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
    settings_store.set_to("assistant_available", True)
    settings_store.set_to("chat_available", True)
    settings_store.set_to("chat_across_cases", True)
    monkeypatch.setattr(
        tasks.read_document, "defer", lambda **f: documents.read(f["document_id"])
    )
    monkeypatch.setattr(tasks.answer_incident_turn, "defer", lambda **f: None)
    monkeypatch.setattr(tasks.answer_case_turn, "defer", lambda **f: None)


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


def video(person, case, title, *, stamp=None, lines=()):
    from core.jobs import Segment, Transcript

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
    if lines:
        transcript = Transcript.objects.create(recording=recording, language="en")
        for start, speaker, text in lines:
            Segment.objects.create(
                transcript=transcript,
                start=start,
                end=start + 4,
                text=text,
                speaker=speaker,
                speaker_label=speaker.upper().replace(" ", "_"),
            )
    return recording


LINES = (
    (0.0, "Officer Hale", "This is Officer Hale."),
    (30.0, "Officer Hale", "I got, I got gun, I got gun."),
)


def a_report(person, case, *, incident=None, recording=None, title="Incident report"):
    home = documents.home_of(case, incident=incident, recording=recording)
    report = documents.add(
        case,
        home=home,
        data=make_pdf(REPORT),
        filename="report.pdf",
        title=title,
        by=person,
    )
    # The reading ran at once (the fixture); the row has moved on.
    report.refresh_from_db()
    return report


# Reading ------------------------------------------------------------------------------


def test_a_report_is_read_whole_under_the_ceiling_and_by_matching_past_it(
    person, a_case
):
    recording = video(person, a_case, "first")
    report = a_report(person, a_case, recording=recording)
    text, note, named = documents.reading_block(
        [report], "Was a bag found?", heading="The report for this recording:"
    )
    assert text.startswith("The report for this recording:\nReport: Incident report")
    assert "[Report, page 1, paragraph 3] A small bag was found" in text
    assert "[Report, page 2, paragraph 3] A tow truck" in text
    assert note == "" and list(named) == ["Report"]
    # Past the ceiling, only the matching paragraphs, and the line says so.
    settings_store.set_to("documents_reading_most", 5)
    text, note, named = documents.reading_block(
        [report], "small bag found?", heading="The report for this recording:"
    )
    assert "[Report, page 1, paragraph 3] A small bag" in text
    assert "tow truck" not in text
    assert note == "Read 1 of 6 paragraphs of the report, those matching the question."
    # Two documents are named by their titles; a citation to either resolves.
    second = a_report(person, a_case, recording=recording, title="Supplement [A]")
    text, note, named = documents.reading_block(
        [report, second], "tow truck", heading="The reports:"
    )
    assert set(named) == {"Incident report", "Supplement (A)"}
    assert "[Supplement (A), page 2, paragraph 3] A tow truck" in text
    cited = documents.citations_in(
        "See [Incident report, page 1, paragraph 3] and [Supplement (A), page 2, "
        "paragraph 3]; not [Incident report, page 9, paragraph 1] nor "
        "[Nothing, page 1, paragraph 1].",
        named,
    )
    assert set(cited) == {
        "[Incident report, page 1, paragraph 3]",
        "[Supplement (A), page 2, paragraph 3]",
    }
    one = cited["[Incident report, page 1, paragraph 3]"]
    assert one["kind"] == "document" and one["page"] == 1 and one["para"] == 3
    assert one["text"].startswith("A small bag") and one["before"].startswith(
        "On 7 June"
    )
    assert one["after"] == "" and one["href"] == f"{report.url()}?page=1&para=3"
    # Alone, "Report" is the name and a stray name still resolves to it.
    assert documents.citations_in("[Report, page 2, paragraph 1] x", {"Report": report})
    assert not documents.reading_block([], "x", heading="h")[0]


def test_gideon_reads_the_report_and_cites_its_paragraphs(
    person, a_case, client, monkeypatch
):
    first = video(
        person, a_case, "first", stamp=stamp("21:56:19", "BWC2-1"), lines=LINES
    )
    second = video(person, a_case, "second", stamp=stamp("22:01:00", "BWC2-2"))
    incident = incidents.make(a_case, "Stop", [first, second], by=person)
    report = a_report(person, a_case, incident=incident)
    signed_in(client, person)
    # The incident's Gideon: the report after the chronology, the rule, the
    # citation resolved for the page.
    chat = incident_chat.new_chat(incident, by=person)
    turn = CaseChatTurn.objects.create(chat=chat, number=1, question="Was a bag found?")
    asked = engine_answering(
        monkeypatch,
        [
            "The report says a bag was found [Report, page 1, paragraph 3]; the camera "
            "shows the gun at [21:56:47]."
        ],
    )
    incident_chat.answer_incident_turn(turn.pk)
    turn.refresh_from_db()
    user = asked[0]["messages"][-1]["content"]
    assert "The report for this incident:\nReport: Incident report, 2 pages." in user
    assert "[Report, page 1, paragraph 3] A small bag was found" in user
    assert user.index("The report for this incident") < user.index("The question:")
    assert documents.RULE in asked[0]["messages"][0]["content"]
    assert turn.citations["[21:56:47]"] == 30.0
    assert turn.citations["[Report, page 1, paragraph 3]"]["kind"] == "document"
    state = client.get(f"{incident.url()}/chat").json()
    cited = state["chats"][0]["turns"][0]["citations"]
    assert cited["[Report, page 1, paragraph 3]"]["text"].startswith("A small bag")
    assert cited["[21:56:47]"]["clock"] == "21:56:47"
    # The case's Gideon: the reports of the case with the recordings.
    case_chat_row = CaseChat.objects.create(case=a_case, asked_by=person, name="Bag?")
    turn = CaseChatTurn.objects.create(
        chat=case_chat_row, number=1, question="Was a bag found?"
    )
    asked = engine_answering(monkeypatch, ["Yes [Report, page 1, paragraph 3]."])
    case_chat.answer_case_turn(turn.pk)
    user = asked[0]["messages"][-1]["content"]
    assert (
        "The reports in this case:" in user and "[Report, page 1, paragraph 3]" in user
    )
    assert documents.RULE in asked[0]["messages"][0]["content"]
    got = client.get(f"/case/{a_case.pk}/chat").json()
    cited = got["chats"][0]["turns"][0]["citations"]["[Report, page 1, paragraph 3]"]
    assert cited["href"] == f"{report.url()}?page=1&para=3" and cited["ocr"] is False
    # Past the ceiling the answer says what was read.
    settings_store.set_to("documents_reading_most", 5)
    turn = CaseChatTurn.objects.create(chat=case_chat_row, number=2, question="A bag?")
    engine_answering(monkeypatch, ["Yes."])
    case_chat.answer_case_turn(turn.pk)
    turn.refresh_from_db()
    assert turn.answer.endswith(
        "(Read 1 of 6 paragraphs of the report, those matching the question.)"
    )


# The Report tab and the pages ---------------------------------------------------------


def test_the_report_tab_is_there_only_while_a_document_is_linked(
    person, a_case, client
):
    first = video(person, a_case, "first", stamp=stamp("21:56:19", "BWC2-1"))
    second = video(person, a_case, "second", stamp=stamp("22:01:00", "BWC2-2"))
    incident = incidents.make(a_case, "Stop", [first, second], by=person)
    signed_in(client, person)
    page = client.get(f"/recording/{first.pk}").content.decode()
    assert 'data-panel="report"' not in page
    report = a_report(person, a_case, incident=incident, recording=first)
    assert report.home_kind() == "incident and recording"
    page = client.get(f"/recording/{first.pk}").content.decode()
    assert 'data-panel="report">' in page and 'id="report-panel"' in page
    assert f"/document/{report.pk}/state" in page and "report-panel.js" in page
    page = client.get(incident.url()).content.decode()
    assert 'id="tab-report"' in page and 'id="panel-report"' in page
    state = client.get(f"{incident.url()}/state").json()["incident"]
    assert state["documents"][0]["id"] == str(report.pk)
    assert state["case_id"] == str(a_case.pk)
    got = client.get(f"/case/{a_case.pk}/document/{report.pk}/state").json()
    assert got["title"] == "Incident report" and len(got["pages_rows"]) == 2
    assert got["pages_rows"][0]["paragraphs"][2]["text"].startswith("A small bag")
    assert got["pages_rows"][1]["picture"].endswith("/page/2.png")
    assert got["home"] == "Stop and first"
    # The document page's ways back.
    page = client.get(report.url()).content.decode()
    assert "Back to the incident" in page and "Back to the recording" in page
    assert (
        f'href="{incident.url()}"' in page
        and f"/recording/{first.pk}?panel=details" in page
    )
    assert f'href="/case/{a_case.pk}?tab=documents"' in page


def test_adding_from_the_documents_tab_picks_the_home_and_relink_is_a_row(
    person, a_case, client
):
    first = video(person, a_case, "first", stamp=stamp("21:56:19", "BWC2-1"))
    second = video(person, a_case, "second", stamp=stamp("22:01:00", "BWC2-2"))
    incident = incidents.make(a_case, "Stop", [first, second], by=person)
    signed_in(client, person)
    tab = client.get(f"/case/{a_case.pk}?tab=documents").content.decode()
    assert f'id="add-document" href="/case/{a_case.pk}/documents/add"' in tab
    page = client.get(f"/case/{a_case.pk}/documents/add").content.decode()
    assert 'id="pick-incident"' in page and 'id="pick-recording"' in page
    assert ">Stop</option>" in page and ">first</option>" in page
    assert "for an incident or a camera of this case" in page
    # From a Details tab the home arrives ticked.
    page = client.get(
        f"/case/{a_case.pk}/documents/add?incident={incident.pk}"
    ).content.decode()
    assert f'value="{incident.pk}" selected' in page and "this incident" in page
    # Nothing picked is refused with the reason; both picked links both.
    fields = {"title": "R", "file": io.BytesIO(make_pdf(REPORT))}
    fields["file"].name = "r.pdf"
    page = client.post(f"/case/{a_case.pk}/documents/add", fields).content.decode()
    assert "Say which incident or recording" in page and Document.objects.count() == 0
    fields = {
        "title": "R",
        "file": io.BytesIO(make_pdf(REPORT)),
        "incident": str(incident.pk),
        "recording": str(second.pk),
    }
    fields["file"].name = "r.pdf"
    told = client.post(f"/case/{a_case.pk}/documents/add", fields)
    assert told.status_code == 302 and told.url == incident.url()
    document = Document.objects.get()
    assert document.incident == incident and document.recording == second
    # Re-link on the row: two choices and a button, the current ones shown.
    tab = client.get(f"/case/{a_case.pk}?tab=documents").content.decode()
    assert (
        'class="row relink"' in tab and "<details" not in tab.split('id="documents"')[1]
    )
    assert f'value="{second.pk}" selected' in tab
    told = client.post(
        f"/case/{a_case.pk}/document/{document.pk}/act",
        {"action": "relink", "incident": "", "recording": str(first.pk)},
    )
    assert told.status_code == 302
    document.refresh_from_db()
    assert document.incident is None and document.recording == first
    told = client.post(
        f"/case/{a_case.pk}/document/{document.pk}/act",
        {"action": "relink", "incident": "", "recording": ""},
    )
    document.refresh_from_db()
    assert document.recording == first  # refused: never loose
    # The Details blocks say both homes.
    assert (
        "Incident report"
        not in client.get(incident.url() + "/state")
        .json()["incident"]["documents"]
        .__str__()
    )


def test_a_document_read_by_an_older_splitter_is_read_again(
    person, a_case, monkeypatch
):
    recording = video(person, a_case, "first")
    report = a_report(person, a_case, recording=recording)
    assert report.read_version == documents.READ_VERSION
    Document.objects.filter(pk=report.pk).update(read_version=1)
    queued = []
    monkeypatch.setattr(
        tasks.read_document, "defer", lambda **f: queued.append(f["document_id"])
    )
    assert documents.read_again_the_old() == 1
    assert queued == [str(report.pk)]
    report.refresh_from_db()
    assert report.state == "reading"
    # Queued once: the next minute finds nothing.
    assert documents.read_again_the_old() == 0
    documents.read(report.pk)
    report.refresh_from_db()
    assert report.state == "ready" and report.read_version == documents.READ_VERSION
    assert settings_store.definition("documents_reading_most").page == "documents"
    assert json.dumps(documents.as_json(report))
