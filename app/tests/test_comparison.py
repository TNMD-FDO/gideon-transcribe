"""v1.73.0: the comparison, part 3 (Phase 8, chapter 4).

The rules checked here: Compare with the report reads the report in windows
of pages against the incident record and the chronology, and against a
recording's transcript; every finding kept cites a real paragraph and a real
moment for its mark, and one with a side missing is dropped; what the report
leaves out is asked once against the whole report; the findings land as JSON
for the layer with the four marks and their counts; a person dismisses,
notes and makes one an event that rests on the paragraph with source report;
the comparison goes stale when the chronology changes; Comparison to Word;
the settings; the audit rows, never a word.
"""

from __future__ import annotations

import io
import json

import pytest
from core import chronology, comparison, documents, incidents, settings_store, tasks
from core.audit import Row
from core.cases import Case
from core.comparison import Comparison
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
    monkeypatch.setattr(
        tasks.read_document, "defer", lambda **f: documents.read(f["document_id"])
    )
    monkeypatch.setattr(tasks.compare_report, "defer", lambda **f: None)


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


LINES = (
    (0.0, "Officer Hale", "Step out of the vehicle for me."),
    (30.0, "Officer Hale", "I got, I got gun, I got gun."),
    (60.0, "Driver", "That bag is not mine."),
)


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


def a_report(person, case, home, title="Incident report"):
    report = documents.add(
        case,
        home=home,
        data=make_pdf(REPORT),
        filename="report.pdf",
        title=title,
        by=person,
    )
    report.refresh_from_db()
    return report


@pytest.fixture
def stop(person, a_case):
    first = video(
        person, a_case, "first", stamp=stamp("21:56:19", "BWC2-1"), lines=LINES
    )
    second = video(person, a_case, "second", stamp=stamp("22:01:00", "BWC2-2"))
    incident = incidents.make(a_case, "Stop", [first, second], by=person)
    cams = {one.camera_id(): one for one in incident.cameras.all()}
    chronology.add(
        incident,
        {"at": "30", "text": "Gun found", "camera": str(cams["BWC2-1"].pk)},
        by=person,
    )
    report = a_report(person, a_case, {"incident": incident})
    return incident, report, first


def findings_json(*items):
    return json.dumps({"findings": list(items)})


# The run ------------------------------------------------------------------------------


def test_the_comparison_reads_windows_keeps_cited_findings_and_drops_the_rest(
    stop, person, monkeypatch
):
    incident, report, first = stop
    made = comparison.ask_for(report, incident, by=person)
    assert made is not None and made.state == "queued"
    # A second ask while it runs returns the same one.
    assert comparison.ask_for(report, incident, by=person).pk == made.pk
    asked = engine_answering(
        monkeypatch,
        [
            # The one window of pages: kept, kept, and four dropped (a made-up
            # paragraph, a time outside the incident, no mark, no time on agrees).
            findings_json(
                {
                    "page": 1,
                    "paragraph": 2,
                    "claim": "The driver was asked out of the car",
                    "at": "21:56:17",
                    "mark": "agrees",
                    "why": "Officer Hale says step out at the start.",
                },
                {
                    "page": 1,
                    "paragraph": 3,
                    "claim": "The driver said the bag was not his",
                    "at": "21:57:17",
                    "mark": "differs",
                    "why": "The camera hears the driver say the bag is not mine.",
                },
                {
                    "page": 2,
                    "paragraph": 2,
                    "claim": "Officer Reyes stood by the passenger door",
                    "at": "",
                    "mark": "not on camera",
                    "why": "No camera shows the passenger door.",
                },
                {
                    "page": 9,
                    "paragraph": 1,
                    "claim": "x",
                    "at": "21:56:17",
                    "mark": "agrees",
                },
                {
                    "page": 1,
                    "paragraph": 1,
                    "claim": "y",
                    "at": "03:00:00",
                    "mark": "agrees",
                },
                {"page": 1, "paragraph": 1, "claim": "z", "at": "21:56:17"},
                {"page": 1, "paragraph": 1, "claim": "w", "at": "", "mark": "agrees"},
                {
                    "page": 1,
                    "paragraph": 3,
                    "claim": "The driver said the bag was not his",
                    "at": "21:57:17",
                    "mark": "differs",
                },
            ),
            # What the report leaves out: the gun, and a stray agrees dropped.
            findings_json(
                {
                    "page": "",
                    "paragraph": "",
                    "claim": "Gun found",
                    "at": "21:56:47",
                    "mark": "not_in_report",
                    "why": "No paragraph mentions a gun.",
                },
                {
                    "page": 1,
                    "paragraph": 2,
                    "claim": "stray",
                    "at": "21:56:17",
                    "mark": "agrees",
                },
            ),
        ],
    )
    comparison.compare(made.pk)
    made.refresh_from_db()
    assert made.state == "done" and made.windows == 1 and made.cut_short == 0
    marks = [(one["mark"], one["page"], one["n"], one["at"]) for one in made.findings]
    # The report's findings in page order, then what the report leaves out.
    assert marks == [
        ("agrees", 1, 2, 0.0),
        ("differs", 1, 3, 60.0),
        ("not_on_camera", 2, 2, None),
        ("not_in_report", 0, 0, 30.0),
    ]
    assert made.findings[0]["paragraph"].startswith("On 7 June")
    assert made.counts() == {
        "agrees": 1,
        "differs": 1,
        "not_on_camera": 1,
        "not_in_report": 1,
    }
    assert made.cameras_used == ["BWC2-1"] and made.events_signature
    # The window's text: the record, the chronology and the pages, then the
    # left-out check against the whole report.
    user = asked[0]["messages"][-1]["content"]
    assert "The report, pages 1 to 2" in user
    assert "[Report, page 1, paragraph 3] A small bag was found" in user
    assert "Event 1, 21:56:47, Gun found" in user and "I got gun" in user
    assert "Do not report what the report leaves out here." in user
    assert (
        "Which events of the chronology does the report not mention"
        in (asked[1]["messages"][-1]["content"])
    )
    assert "Answer with JSON only" in asked[0]["messages"][0]["content"]
    # One assistant row for the run, counting its two calls; one row for the
    # run's counts; never the words.
    call = Row.objects.get(event="AI assistant call")
    assert call.details["calls"] == 2 and call.details["feature"] == "compare_report"
    run = Row.objects.get(event="Comparison run")
    assert run.details["findings"] == 4 and run.details["differs"] == 1
    assert "bag" not in json.dumps(run.details).lower()
    # The page's JSON.
    got = comparison.as_json(made, report, incident)
    assert got["state"] == "done" and got["can_make_event"] is True
    assert got["counts"]["agrees"] == 1 and got["stale"] == ""
    assert (
        "4 findings: 1 agree, 1 differ, 1 not on camera, 1 not in the report"
        in got["words"]
    )
    row = got["findings"][1]
    assert row["clock"] == "21:57:17" and row["mark_words"] == "Differs"
    assert row["paragraph_url"] == f"{report.url()}?page=1&para=3"
    assert got["findings"][3]["paragraph_url"] == ""
    assert got["export_url"].endswith(f"/comparison/export?incident={incident.pk}")
    # Stale once the chronology changes; Compare again replaces it.
    chronology.add(incident, {"at": "100", "text": "Tow arrives"}, by=person)
    assert (
        comparison.as_json(made, report, incident)["stale"]
        == "the chronology changed since"
    )
    again = comparison.ask_for(report, incident, by=person)
    assert again.pk != made.pk and not Comparison.objects.filter(pk=made.pk).exists()


def test_a_finding_is_dismissed_noted_and_made_an_event_that_rests_on_the_paragraph(
    stop, person, client, monkeypatch
):
    incident, report, first = stop
    made = comparison.ask_for(report, incident, by=person)
    engine_answering(
        monkeypatch,
        [
            findings_json(
                {
                    "page": 1,
                    "paragraph": 3,
                    "claim": "The driver said the bag was not his",
                    "at": "21:57:17",
                    "mark": "differs",
                    "why": "Heard on camera.",
                },
                {
                    "page": 2,
                    "paragraph": 2,
                    "claim": "Reyes at the passenger door",
                    "at": "",
                    "mark": "not_on_camera",
                    "why": "",
                },
            ),
            findings_json(),
        ],
    )
    comparison.compare(made.pk)
    made.refresh_from_db()
    signed_in(client, person)
    base = f"/case/{incident.case_id}/document/{report.pk}"
    state = client.get(f"{base}/comparison?incident={incident.pk}").json()
    first_id, second_id = (one["id"] for one in state["findings"])
    act = f"{base}/comparison/act"
    got = client.post(
        act,
        {
            "incident": str(incident.pk),
            "action": "note",
            "finding": first_id,
            "note": "  Check the  audio.",
        },
    ).json()
    assert got["findings"][0]["note"] == "Check the audio."
    got = client.post(
        act, {"incident": str(incident.pk), "action": "dismiss", "finding": second_id}
    ).json()
    assert (
        got["findings"][1]["dismissed"] is True and got["counts"]["not_on_camera"] == 0
    )
    got = client.post(
        act, {"incident": str(incident.pk), "action": "undismiss", "finding": second_id}
    ).json()
    assert got["findings"][1]["dismissed"] is False
    # Make it an event: on the chronology at the moment, source report,
    # resting on the paragraph, the mark as its why, the note carried.
    got = client.post(
        act, {"incident": str(incident.pk), "action": "make_event", "finding": first_id}
    ).json()
    assert got["findings"][0]["event"]
    event = chronology.Event.objects.get(pk=got["findings"][0]["event"])
    assert event.source == "report" and event.at == 60.0 and event.proposed is False
    assert event.text == "The driver said the bag was not his"
    assert event.rests_on.startswith("[Report, page 1, paragraph 3] A small bag")
    assert event.why == "Differs: Heard on camera." and event.note == "Check the audio."
    state = client.get(f"{incident.url()}/state").json()
    row = next(one for one in state["events"] if one["id"] == str(event.pk))
    assert row["source_words"] == "From the report" and row["rests_on"].startswith(
        "[Report"
    )
    # The memo reads the paragraph the event rests on.
    from core.incident_assistant import _chronology_lines

    lines, _ = _chronology_lines(incident)
    assert any(
        "from the report, which says: [Report, page 1, paragraph 3]" in one
        for one in lines
    )
    # Not on camera needs a moment; a stray finding is refused.
    told = client.post(
        act,
        {"incident": str(incident.pk), "action": "make_event", "finding": second_id},
    )
    assert told.status_code == 400 and "moment" in told.json()["error"]
    told = client.post(
        act,
        {
            "incident": str(incident.pk),
            "action": "make_event",
            "finding": second_id,
            "at": "45",
        },
    )
    assert told.status_code == 200
    assert chronology.Event.objects.filter(source="report").count() == 2
    assert (
        client.post(
            act, {"incident": str(incident.pk), "action": "dismiss", "finding": "nope"}
        ).status_code
        == 404
    )
    # Comparison to Word, with one row.
    word = client.get(f"{base}/comparison/export?incident={incident.pk}")
    assert word.status_code == 200 and "comparison.docx" in word["Content-Disposition"]
    from docx import Document as Docx

    text = "\n".join(
        cell.text
        for table in Docx(io.BytesIO(word.content)).tables
        for row in table.rows
        for cell in row.cells
    )
    assert "Differs" in text and "Check the audio." in text and "21:57:17" in text
    assert Row.objects.get(event="comparison exported").details["kind"] == "comparison"
    # Not against a home the report is not for.
    assert client.get(f"{base}/comparison?recording={first.pk}").status_code == 404


def test_the_comparison_runs_against_a_recording_and_refuses_when_it_cannot(
    person, a_case, client, monkeypatch
):
    recording = video(person, a_case, "first", lines=LINES)
    report = a_report(person, a_case, {"recording": recording})
    signed_in(client, person)
    base = f"/case/{a_case.pk}/document/{report.pk}"
    got = client.get(f"{base}/comparison?recording={recording.pk}").json()
    assert (
        got["state"] == ""
        and got["possible"] is True
        and got["can_make_event"] is False
    )
    told = client.post(f"{base}/compare", {"recording": str(recording.pk)}).json()
    assert told["state"] == "queued" and told["busy"] is True
    made = Comparison.objects.get()
    engine_answering(
        monkeypatch,
        [
            findings_json(
                {
                    "page": 1,
                    "paragraph": 3,
                    "claim": "The bag was not his",
                    "at": "00:01:00",
                    "mark": "agrees",
                    "why": "Said at one minute.",
                },
                {
                    "page": 1,
                    "paragraph": 2,
                    "claim": "Too late",
                    "at": "00:20:00",
                    "mark": "agrees",
                },
            )
        ],
    )
    comparison.compare(made.pk)
    made.refresh_from_db()
    assert made.state == "done" and len(made.findings) == 1
    assert made.findings[0]["at"] == 60.0 and made.cameras_used == ["first"]
    got = client.get(f"{base}/comparison?recording={recording.pk}").json()
    assert got["findings"][0]["clock"] == "00:01:00" and got["stale"] == ""
    # Off, the button is gone and a run is refused; a recording without a
    # transcript cannot be compared against.
    settings_store.set_to("documents_compare", False)
    got = client.get(f"{base}/comparison?recording={recording.pk}").json()
    assert got["on"] is False and got["possible"] is False
    told = client.post(f"{base}/compare", {"recording": str(recording.pk)})
    assert told.status_code == 400 and "off" in told.json()["error"]
    settings_store.set_to("documents_compare", True)
    bare = video(person, a_case, "bare")
    other = a_report(person, a_case, {"recording": bare})
    assert comparison.possible(other, bare) == (
        False,
        "The recording has no transcript to compare against yet.",
    )
    for key in (
        "documents_compare",
        "documents_compare_answer_tokens",
        "documents_compare_time_seconds",
    ):
        assert settings_store.definition(key).page == "documents"
    assert settings_store.time_limit_seconds("compare_report") == 600
    # The Report tab's state carries the comparison's addresses.
    state = client.get(f"{base}/state").json()
    assert state["compare"].endswith("/compare") and state["recording"] == str(
        recording.pk
    )


def test_a_failed_call_says_so_and_a_cut_answer_is_counted(stop, person, monkeypatch):
    incident, report, _ = stop
    made = comparison.ask_for(report, incident, by=person)
    from core import engine

    def refused(*args, **kwargs):
        raise engine.Problem(engine.ERROR, "llm_error")

    monkeypatch.setattr(engine, "is_reachable", lambda: True)
    monkeypatch.setattr(engine, "complete", refused)
    comparison.compare(made.pk)
    made.refresh_from_db()
    assert made.state == "failed" and made.reason_class == "llm_error"
    got = comparison.as_json(made, report, incident)
    assert got["state"] == "failed" and got["words"]
    # An unreadable answer loses the window, not the run.
    again = comparison.ask_for(report, incident, by=person)
    engine_answering(monkeypatch, ["not json at all", findings_json()])
    comparison.compare(again.pk)
    again.refresh_from_db()
    assert again.state == "done" and again.findings == []
    said = comparison.as_json(again, report, incident)["words"]
    assert "0 findings" in said and "1 answer could not be read" in said
    assert again.unreadable == 1
    # A fenced answer, as the engine wraps JSON when asked for JSON only
    # (v1.74.2, from the first real report), is read like a bare one; the
    # findings it names that the app cannot place are counted by reason.
    fenced = comparison.ask_for(report, incident, by=person)
    kept = {
        "page": 1,
        "paragraph": 2,
        "claim": "The driver was asked out of the car",
        "at": "21:56:17",
        "mark": "agrees",
        "why": "Said on the first camera.",
    }
    on_no_page = dict(kept, page=99, claim="On no page")
    timeless = dict(kept, claim="Timeless", at="", mark="differs")
    marked_oddly = dict(kept, claim="Marked oddly", mark="maybe")
    good = findings_json(kept, on_no_page, timeless, marked_oddly)
    engine_answering(
        monkeypatch,
        [
            "Here you are:\n```json\n" + good + "\n```\n",
            "```json\n" + findings_json() + "\n```",
        ],
    )
    comparison.compare(fenced.pk)
    fenced.refresh_from_db()
    assert fenced.state == "done" and fenced.unreadable == 0
    assert [one["claim"] for one in fenced.findings] == [kept["claim"]]
    assert fenced.dropped == {
        "paragraph not found": 1,
        "no time on the clock": 1,
        "mark unknown": 1,
    }
    said = comparison.as_json(fenced, report, incident)["words"]
    assert "3 findings dropped: mark unknown 1, no time on the clock 1" in said
    row = Row.objects.filter(event="Comparison run").order_by("-at").first()
    assert row.details["dropped"] == 3 and row.details["unreadable"] == 0


# The report in place (Phase 8 chapter 6) ----------------------------------------


def test_the_pages_carry_the_card_and_the_export_links(
    stop, person, client, monkeypatch
):
    """The incident page and the case page load the paragraph card's script;
    the incident page's Export menu holds Comparison to Word, greyed until a
    comparison is done; the Documents tab row gains the link once one is;
    Gideon's panel has its handle."""
    incident, report, first = stop
    signed_in(client, person)
    page = client.get(incident.url()).content.decode()
    assert "paragraph-card.js" in page and 'id="gideon-grip"' in page
    assert 'id="export-comparison"' in page and 'id="export-comparison-off"' in page
    documents_tab = client.get(
        f"/case/{incident.case_id}?tab=documents"
    ).content.decode()
    assert "Comparison to Word" not in documents_tab
    made = comparison.ask_for(report, incident, by=person)
    engine_answering(monkeypatch, [findings_json(), findings_json()])
    comparison.compare(made.pk)
    made.refresh_from_db()
    assert made.state == "done"
    documents_tab = client.get(
        f"/case/{incident.case_id}?tab=documents"
    ).content.decode()
    assert "Comparison to Word" in documents_tab
    assert (
        f"/document/{report.pk}/comparison/export?incident={incident.pk}"
        in documents_tab
    )
    case_page = client.get(f"/case/{incident.case_id}").content.decode()
    assert "paragraph-card.js" in case_page
