"""Voices first (v1.145.0; the drawing phase-5-voices-first.html): the run
turned over where the voice listens, the lines in doubt from the prints, the
stages, the words' second reading, the split at the word with Undo, and the
page's strings. Where the voice is off, the run is as before."""

import json
from pathlib import Path

import pytest
from core import prompts, settings_store, speaker_check, voices_first, whisperx
from core.assistant import SpeakerCheck, SpeakerCorrection
from core.jobs import Segment
from tests.helpers import signed_in
from tests.test_prepare import engine_answering
from tests.test_speaker_check import SKETCH, moves, swallow, switched_on
from tests.test_speaker_check import admin as _admin  # noqa: F401
from tests.test_voices import a_call, fake_service

HERE = Path(__file__).resolve().parents[1]


@pytest.fixture
def admin(_admin):  # noqa: F811
    return _admin


def voice_on():
    switched_on()
    settings_store.set_to("voices_types", "Jail call")


def test_where_the_voice_listens_the_arrival_run_is_the_voices(
    admin,
    tmp_path,
    settings,
    monkeypatch,  # noqa: F811
):
    voice_on()
    recording, truth = a_call(admin, tmp_path, settings, lines=40, wrong=(5, 17))
    monkeypatch.setattr(whisperx, "voices", fake_service(truth))
    asked = engine_answering(monkeypatch, [SKETCH, moves()])
    check = SpeakerCheck.objects.create(transcript=recording.transcript)
    speaker_check.run(check.pk)
    check.refresh_from_db()
    assert check.state == "done" and check.windows == 0 and check.sketch == ""
    look = check.second_look
    assert look["mode"] == voices_first.VOICES and look["stage"] == 1
    assert look["voice"] == "titanet" and look["doubt"]["near"] >= 2
    rows = recording.transcript.corrections.filter(state=SpeakerCorrection.PENDING)
    assert rows.count() == check.found and rows.exclude(source="voice").count() == 0
    segs = list(recording.transcript.segments.order_by("start"))
    near = {one.segment_id for one in rows.exclude(voice="")}
    assert {segs[5].pk, segs[17].pk} <= near
    # No engine call made for moves; the names pass is off (suggestions off).
    assert all(
        "Lines:" not in str(one["messages"]) or "moves" not in str(one) for one in asked
    )
    state = speaker_check.state_json(recording.transcript)
    assert state["stage"] == 1 and state["mode"] == voices_first.VOICES
    assert state["doubt"]["near"] >= 2 and state["cast"] == {"total": 2, "named": 0}
    assert (
        state["pending"][0]["words"] == "" and state["pending"][0]["split_at"] is None
    )


def test_where_the_voice_is_off_the_words_run_first_as_before(
    admin,
    tmp_path,
    settings,
    monkeypatch,  # noqa: F811
):
    switched_on()
    settings_store.set_to("voices_types", "Interview")
    recording, truth = a_call(admin, tmp_path, settings, lines=8, wrong=())
    engine_answering(
        monkeypatch, [SKETCH, moves((2, "Speaker 1", "Speaker 2", "asks"))]
    )
    check = SpeakerCheck.objects.create(transcript=recording.transcript)
    speaker_check.run(check.pk)
    check.refresh_from_db()
    assert check.state == "done" and check.windows >= 1 and check.sketch == SKETCH
    assert check.second_look.get("mode") == voices_first.WORDS
    assert "stage" not in check.second_look
    assert speaker_check.state_json(recording.transcript)["stage"] is None


def test_a_mixed_line_is_a_split_at_the_word(admin, tmp_path, settings, client):  # noqa: F811
    recording, _ = a_call(admin, tmp_path, settings, lines=6, wrong=())
    segs = list(recording.transcript.segments.order_by("start"))
    line = segs[0]  # Speaker 1; the last three words wear Speaker 2's label
    words = line.words
    for w in words[2:]:
        w["speaker"] = "SPEAKER_2"
    line.words = words
    line.save(update_fields=["words"])
    found = voices_first.mixed_lines(recording.transcript, set())
    assert len(found) == 1
    one = found[0]
    assert one["segment_id"] == line.pk and one["split_at"] == 2
    assert one["split_part"] == "second" and one["to"] == "Speaker 2"
    # Accepting splits the line: a new line from the third word, the first
    # part kept, and Undo puts it back whole.
    row = SpeakerCorrection.objects.create(
        transcript=recording.transcript,
        segment=line,
        start=line.start,
        quote=line.text,
        speaker_from="Speaker 1",
        speaker_to="Speaker 2",
        reason=one["reason"],
        voice=SpeakerCorrection.VOICE_AGREES,
        source=SpeakerCorrection.VOICE,
        split_at=2,
        split_part="second",
    )
    before = recording.transcript.segments.count()
    original_end = line.end
    assert speaker_check.accept(row, by=admin) == 1
    line.refresh_from_db()
    assert recording.transcript.segments.count() == before + 1
    assert (
        line.text == "some words"
        and len(line.words) == 2
        and line.speaker == "Speaker 1"
    )
    made = recording.transcript.segments.get(start=words[2]["start"])
    assert made.text == "spoken here now" and made.speaker == "Speaker 2"
    assert made.speaker_label == "SPEAKER_2" and made.end == pytest.approx(original_end)
    recording.transcript.refresh_from_db()
    assert recording.transcript.speaker_changes[-1]["split_line"] is True
    from core import viewer

    assert viewer.last_change_line(recording.transcript).startswith(
        "splitting one line of Speaker 1"
    )
    # Undo, through the page.
    signed_in(client, admin)
    assert client.post(f"/recording/{recording.pk}/speakers/undo").status_code == 200
    line.refresh_from_db()
    assert line.text == "some words spoken here now" and len(line.words) == 5
    assert recording.transcript.segments.count() == before


def test_the_stages_queue_the_reading_and_the_words_run(
    admin, tmp_path, settings, monkeypatch, client, django_capture_on_commit_callbacks
):
    voice_on()
    recording, truth = a_call(admin, tmp_path, settings, lines=40, wrong=(5, 17))
    monkeypatch.setattr(whisperx, "voices", fake_service(truth))
    engine_answering(monkeypatch, [SKETCH])
    check = SpeakerCheck.objects.create(transcript=recording.transcript)
    speaker_check.run(check.pk)
    deferred = swallow(monkeypatch)
    from core import tasks

    read = []
    monkeypatch.setattr(
        tasks.read_doubts, "defer", lambda **fields: read.append(fields)
    )
    signed_in(client, admin)
    with django_capture_on_commit_callbacks(execute=True):
        answer = client.post(f"/recording/{recording.pk}/stage/2")
    assert answer.status_code == 200 and answer.json()["queued"] == "reading"
    check.refresh_from_db()
    assert (
        check.second_look["stage"] == 2
        and check.second_look["reading"]["state"] == "queued"
    )
    assert read and read[0]["check_id"] == str(check.pk)
    # Stage 3: the words' run over the whole call, in words mode.
    with django_capture_on_commit_callbacks(execute=True):
        answer = client.post(f"/recording/{recording.pk}/stage/3")
    assert answer.status_code == 200 and answer.json()["queued"] == "words"
    queued = SpeakerCheck.objects.filter(
        transcript=recording.transcript, state="queued"
    ).get()
    assert queued.second_look == {"mode": voices_first.WORDS} and deferred
    # Back to the voices: no job, the stage alone.
    assert client.post(f"/recording/{recording.pk}/stage/1").json()["queued"] == ""
    check.refresh_from_db()
    assert check.second_look["stage"] == 1


def test_the_words_second_reading_lands_on_the_lines_in_doubt(
    admin,
    tmp_path,
    settings,
    monkeypatch,  # noqa: F811
):
    voice_on()
    recording, truth = a_call(admin, tmp_path, settings, lines=40, wrong=(5, 17))
    monkeypatch.setattr(whisperx, "voices", fake_service(truth))
    engine_answering(monkeypatch, [SKETCH])
    check = SpeakerCheck.objects.create(transcript=recording.transcript)
    speaker_check.run(check.pk)
    rows = list(
        recording.transcript.corrections.filter(state="pending")
        .exclude(voice="")
        .order_by("start")
    )
    assert len(rows) >= 2
    lines = prompts.lines_of(recording.transcript, without_system=True)
    number = {line.segment_id: line.number for line in lines}
    # The words agree on the first, read the second as it is labelled.
    answer = json.dumps(
        {
            "lines": [
                {
                    "line": number[rows[0].segment_id],
                    "speaker": rows[0].speaker_to,
                    "reason": "answers",
                },
                {
                    "line": number[rows[1].segment_id],
                    "speaker": rows[1].speaker_from,
                    "reason": "the officer",
                },
            ]
        }
    )
    asked = engine_answering(monkeypatch, [answer])
    voices_first.read_doubts(check.pk)
    rows[0].refresh_from_db()
    rows[1].refresh_from_db()
    assert rows[0].words == SpeakerCorrection.VOICE_AGREES
    assert (
        rows[1].words == SpeakerCorrection.VOICE_AGAINST
        and rows[1].words_why == "the officer"
    )
    check.refresh_from_db()
    reading = check.second_look["reading"]
    assert (
        reading["state"] == "done" and reading["agree"] == 1 and reading["against"] == 1
    )
    # The cast and the lines in doubt were in the question, with the name list.
    sent = asked[0]["messages"][-1]["content"]
    assert "Speakers: Speaker 1; Speaker 2" in sent and "Line in doubt [" in sent
    assert asked[0]["schema"]["properties"]["lines"]["items"]["properties"]["speaker"][
        "enum"
    ] == [
        "Speaker 1",
        "Speaker 2",
    ]
    counts = voices_first.doubt_counts(recording.transcript)
    assert counts["agree"] == 1 and counts["words_against"] == 1


def test_the_page_carries_the_stages():
    page = (HERE / "static" / "speakers-page.js").read_text(encoding="utf-8")
    assert "function drawStages" in page and "function moveToStage" in page
    assert "Split at the word" in page and "voice and words agree" in page
    assert "The words point at a name" in page and "prefill:" in page
    template = (HERE / "templates" / "speakers-page.html").read_text(encoding="utf-8")
    assert 'id="stages"' in template and 'id="stage-next"' in template
    strip = (HERE / "static" / "assistant.js").read_text(encoding="utf-8")
    assert "voice to name" in strip and "line in doubt" in strip
    picker = (HERE / "static" / "picker.js").read_text(encoding="utf-8")
    assert "options.prefill" in picker
    css = (HERE / "static" / "app.css").read_text(encoding="utf-8")
    assert ".sp-corrections .stages" in css and ".sp-read .seg.change.mixed" in css
    assert "body.voices-first .sp-card" in css


def test_the_prompt_pieces_read_plainly():
    assert "Never invent a speaker" in prompts.LINES_IN_DOUBT
    schema = prompts.lines_in_doubt_schema(["Dana Reyes", "Speaker 2"])
    assert schema["properties"]["lines"]["items"]["properties"]["speaker"]["enum"] == [
        "Dana Reyes",
        "Speaker 2",
    ]
    assert prompts.parse_json('{"lines": []}') == {"lines": []}
    assert isinstance(Segment, type)
