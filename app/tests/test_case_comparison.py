"""v1.170.0: the comparison against the case (Phase 10 chapter 4, the third
release).

Checked here: Compare with the case reads the document against every
recording of the case that has a transcript, one child run each, and the
parent holds their findings merged, each naming its recording, in day and
time order on the case's clock; the Documents tab says where it stands and
offers the layer; the acts on a merged finding reach the child and Make it
a note writes the note on the right recording; Compare again replaces the
run; a recording landed since is said; the Word export names the
recordings; the home is refused for a document of another case.
"""

from __future__ import annotations

import datetime as dt
import io
import json

import pytest
from core import case_chronology, comparison, documents, engine, settings_store, tasks
from core.audit import Row
from core.cases import Case
from core.comparison import Comparison
from core.jobs import Segment, Transcript
from core.models import User
from core.recordings import Batch, MediaState, Recording
from tests.helpers import signed_in, stamp
from tests.test_documents import REPORT, make_pdf

PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def switched_on(db, monkeypatch):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("incidents", True)
    settings_store.set_to("assistant_available", True)
    settings_store.set_to("documents", True)
    settings_store.set_to("documents_compare", True)
    monkeypatch.setattr(tasks.compare_report, "defer", lambda **f: None)
    monkeypatch.setattr(tasks.compare_report_case, "defer", lambda **f: None)
    monkeypatch.setattr(tasks.read_document, "defer", lambda **f: None)


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("asker", PASSWORD)


@pytest.fixture
def a_case(person):
    return Case.objects.create(owner=person, name="Traffic stop")


def video(person, case, title, *, stamp=None, lines=()):
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
        for start, text in lines:
            Segment.objects.create(
                transcript=transcript,
                start=start,
                end=start + 4,
                text=text,
                speaker="Officer Hale",
                speaker_label="OFFICER_HALE",
            )
    return recording


def a_report(person, case, home):
    report = documents.add(
        case,
        home=home,
        data=make_pdf(REPORT),
        filename="report.pdf",
        title="Incident report",
        by=person,
    )
    documents.read(report.pk)
    report.refresh_from_db()
    return report


def findings(*items):
    return json.dumps(
        {
            "findings": [
                {
                    "page": page,
                    "paragraph": n,
                    "claim": claim,
                    "at": at,
                    "mark": mark,
                    "why": why,
                }
                for page, n, claim, at, mark, why in items
            ]
        }
    )


def answering(monkeypatch, by_words: dict):
    """The engine answering each child's window by the words it was given,
    and "more" to anything else (the check's readings, which then change
    nothing)."""
    monkeypatch.setattr(engine, "is_reachable", lambda: True)
    monkeypatch.setattr(engine, "address", lambda: "http://gideon-generator:8000/v1")
    asked = []

    def complete(messages, **options):
        user = messages[-1]["content"]
        asked.append(user)
        text = "more"
        for words, answer in by_words.items():
            if words in user and "findings" not in user.split(words)[0][-200:]:
                text = answer
                break
        return {
            "text": text,
            "finish_reason": "stop",
            "input_tokens": 1,
            "output_tokens": 1,
            "model": "m",
        }

    monkeypatch.setattr(engine, "complete", complete)
    return asked


def test_the_case_run_reads_every_recording_and_merges_by_the_clock(
    person, a_case, client, monkeypatch
):
    first = video(
        person,
        a_case,
        "BWC2-1",
        stamp=stamp("21:56:19", "BWC2-1"),
        lines=(
            (0.0, "Step out of the vehicle for me."),
            (60.0, "That bag is not mine."),
        ),
    )
    second = video(person, a_case, "Call", lines=((5.0, "Stay in the car."),))
    case_chronology.place(
        second, dt.date(2025, 6, 7), 20 * 3600.0, by=person, how="hand"
    )
    video(person, a_case, "No words")
    report = a_report(person, a_case, {"recording": first})
    assert comparison.possible(report, a_case) == (True, "")
    # Each child's window answered by the words it was given; the check's
    # readings get "more" and change nothing.
    answering(
        monkeypatch,
        {
            "That bag is not mine": findings(
                (
                    1,
                    3,
                    "The driver said the bag was not his",
                    "00:01:00",
                    "differs",
                    "Heard on camera.",
                ),
                (2, 2, "Reyes at the passenger door", "", "not_on_camera", ""),
            ),
            "Stay in the car": findings(
                (1, 1, "The passenger was told to stay", "00:00:05", "agrees", "")
            ),
        },
    )
    made = comparison.ask_for(report, a_case, by=person)
    assert made is not None and made.case == a_case and made.state == "queued"
    assert made.expectation["key"] == "compare_report"
    assert comparison.ask_for(report, a_case, by=person) == made  # one at a time
    comparison.compare_for_case(made.pk)
    made.refresh_from_db()
    assert made.state == "done" and made.stage == ""
    children = list(made.children.order_by("created"))
    assert [c.recording.title for c in children] == ["BWC2-1", "Call"]
    assert all(c.state == "done" and c.parent == made for c in children)
    assert made.cameras_used == ["BWC2-1", "Call"]
    # Merged: by day and time on the case's clock; the Call placed by hand at
    # 20:00 comes before the camera's 21:57:19; a Not on camera finding
    # first on its recording.
    ids = [one["id"] for one in made.findings]
    assert all(":" in one for one in ids)
    assert [(one["recording"], one["clock_words"]) for one in made.findings] == [
        ("Call", "7 Jun 2025 20:00:05"),
        ("BWC2-1", ""),
        ("BWC2-1", "7 Jun 2025 21:57:17"),
    ]
    told = comparison.as_json(made, report, a_case)
    assert told["home"] == "case" and told["can_make_note"] is True
    assert "against 2 recordings, read one at a time" in told["words"]
    assert told["counts"] == {
        "agrees": 1,
        "differs": 1,
        "not_on_camera": 1,
        "not_in_report": 0,
    }
    assert told["findings"][0]["clock"] == "7 Jun 2025 20:00:05"
    assert told["export_url"].endswith(f"?case={a_case.pk}")
    # The audit: one row per child and one for the whole.
    whole = Row.objects.get(event="Comparison run", details__whole_case=True)
    assert whole.details["recordings"] == 2 and whole.details["read"] == 2
    assert Row.objects.filter(event="Comparison run").count() == 3
    for row in Row.objects.all():
        assert "bag" not in json.dumps(row.details).lower()
    # The Documents tab says where it stands and carries the layer.
    signed_in(client, person)
    page = client.get(f"/case/{a_case.pk}?tab=documents").content.decode()
    assert "3 findings" in page and 'id="case-compare"' in page
    assert "data-case-compare" in page and ">Comparison<" in page
    assert "To Word" in page
    # The acts on a merged finding reach the child.
    base = f"/case/{a_case.pk}/document/{report.pk}"
    act = f"{base}/comparison/act"
    differs = next(one for one in made.findings if one["mark"] == "differs")
    got = client.post(
        act,
        {
            "case": str(a_case.pk),
            "action": "note",
            "finding": differs["id"],
            "note": "Check it.",
        },
    ).json()
    assert (
        next(one for one in got["findings"] if one["id"] == differs["id"])["note"]
        == "Check it."
    )
    child = children[0]
    child.refresh_from_db()
    assert child.findings[0]["note"] == "Check it."
    got = client.post(
        act, {"case": str(a_case.pk), "action": "make_note", "finding": differs["id"]}
    ).json()
    row = next(one for one in got["findings"] if one["id"] == differs["id"])
    assert row["note_id"] and row["note_kind"] == "line" and row["note_on"] == "BWC2-1"
    assert Segment.objects.get(start=60.0).note == "The driver said the bag was not his"
    assert (
        Segment.objects.get(start=60.0).note_from["words"]
        == "from the report, page 1, paragraph 3"
    )
    # Not on camera needs a moment, into its own recording.
    noc = next(one for one in made.findings if one["mark"] == "not_on_camera")
    told = client.post(
        act, {"case": str(a_case.pk), "action": "make_note", "finding": noc["id"]}
    )
    assert told.status_code == 400 and "moment" in told.json()["error"]
    got = client.post(
        act,
        {
            "case": str(a_case.pk),
            "action": "make_note",
            "finding": noc["id"],
            "at": "30",
        },
    ).json()
    assert (
        next(one for one in got["findings"] if one["id"] == noc["id"])["note_kind"]
        == "moment"
    )
    # Dismiss and undo, and a stray id.
    agrees = next(one for one in made.findings if one["mark"] == "agrees")
    got = client.post(
        act, {"case": str(a_case.pk), "action": "dismiss", "finding": agrees["id"]}
    ).json()
    assert got["counts"]["agrees"] == 0
    got = client.post(
        act, {"case": str(a_case.pk), "action": "undismiss", "finding": agrees["id"]}
    ).json()
    assert got["counts"]["agrees"] == 1
    assert (
        client.post(
            act, {"case": str(a_case.pk), "action": "dismiss", "finding": "nope:1"}
        ).status_code
        == 404
    )
    # The export names the recordings, with a Recording column.
    word = client.get(f"{base}/comparison/export?case={a_case.pk}")
    assert word.status_code == 200
    from docx import Document as Docx

    doc = Docx(io.BytesIO(word.content))
    cells = [
        cell.text for table in doc.tables for row in table.rows for cell in row.cells
    ]
    assert "Recording" in cells and "Call" in cells and "7 Jun 2025 20:00:05" in cells
    assert "the case Traffic stop, every recording with a transcript" in cells
    # A recording landed since is said, and Compare again replaces the run.
    video(person, a_case, "Late", lines=((1.0, "Later."),))
    assert (
        comparison.stale_words(made) == "1 recording landed since and not yet compared"
    )
    again = comparison.ask_for(report, a_case, by=person)
    assert again.pk != made.pk and not Comparison.objects.filter(pk=made.pk).exists()
    assert not Comparison.objects.filter(parent_id=made.pk).exists()
    # The recording page's own comparison is untouched by the case rows.
    assert (
        comparison.of(report, first) is None
        or comparison.of(report, first).parent_id is not None
    )


def test_the_case_home_is_refused_for_another_case_and_when_off(person, a_case, client):
    other = Case.objects.create(owner=person, name="Other")
    video(person, a_case, "BWC2-1", lines=((0.0, "Step out."),))
    report = a_report(person, a_case, {"recording": a_case.recordings.get()})
    signed_in(client, person)
    base = f"/case/{a_case.pk}/document/{report.pk}"
    assert client.get(f"{base}/comparison?case={other.pk}").status_code == 404
    got = client.get(f"{base}/comparison?case={a_case.pk}").json()
    assert got["state"] == "" and got["possible"] is True and got["home"] == "case"
    told = client.post(f"{base}/compare", {"case": str(a_case.pk)}).json()
    assert told["state"] == "queued" and told["busy"] is True
    # With no recording readable the ask is refused with the reason.
    empty = Case.objects.create(owner=person, name="Empty")
    video(person, empty, "Silent")
    report2 = a_report(person, empty, {"recording": empty.recordings.get()})
    assert comparison.possible(report2, empty) == (
        False,
        "No recording in the case has a transcript yet.",
    )
    page = client.get(f"/case/{empty.pk}?tab=documents").content.decode()
    assert "No recording in the case has a transcript yet." in page
