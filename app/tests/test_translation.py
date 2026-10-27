"""Translation from the words as spoken (ADR 0026, Phase 1 chapter 7,
v1.162.0): the lines to write, the windows, the checks, the run and its
states, the hooks, the pages' words, the exports and the search."""

from __future__ import annotations

import datetime as dt
import json

import pytest
from core import (
    assistant,
    case_search,
    engine,
    exports,
    mail,
    prompts,
    settings_store,
    translation,
)
from core.assistant import Translation
from core.audit import Row
from core.jobs import Segment, Transcript
from core.models import User
from django.utils import timezone
from tests.test_prepare import a_recording

PASSWORD = "a-long-enough-password"

QWEN = {"settings_used": {"recogniser": "qwen3-asr", "model": "qwen3-asr-1.7b"}}

LINES = (
    (0.0, "Call system", "This call is from a correctional facility.", "en"),
    (6.0, "Marisol", "¿Hablaste con el abogado ayer?", "es"),
    (10.0, "Esteban", "Sí, dijo que la audiencia es el catorce.", "es"),
    (16.0, "Marisol", "Which papers?", "en"),
    (20.0, "Esteban", "La carpeta azul, sí, y el título del carro.", "es"),
)


@pytest.fixture
def admin(db):
    return User.objects.create_local_admin("adm", PASSWORD)


def a_spanish_call(person, tmp_path, settings, *, translate=True, lines=LINES):
    recording = a_recording(person, tmp_path, settings, title="Call", video=False)
    recording.translate = translate
    recording.save(update_fields=["translate"])
    transcript = recording.transcript
    transcript.language = "es"
    transcript.provenance = {"run-1": QWEN}
    transcript.save(update_fields=["language", "provenance"])
    transcript.segments.all().delete()
    for start, speaker, text, language in lines:
        Segment.objects.create(
            transcript=transcript,
            start=start,
            end=start + 3,
            text=text,
            speaker=speaker,
            speaker_label=speaker.upper(),
            language=language,
        )
    return recording


def engine_on(monkeypatch):
    settings_store.set_to("assistant_available", True)
    monkeypatch.setattr(engine, "configured", lambda: True)
    monkeypatch.setattr(engine, "is_reachable", lambda: True)


def english_for(window_text: str) -> list[dict]:
    """A fake answer: every asked line's number with an English made of it."""
    out = []
    for line in window_text.splitlines():
        if "(context, do not answer)" in line or not line.startswith("["):
            continue
        number = int(line[1 : line.index("]")])
        out.append({"n": number, "english": f"English of line {number}"})
    return out


def engine_translating(monkeypatch, answers=None):
    """The engine answering each window with an English per asked line, or
    with the given texts in turn."""
    asked: list[str] = []

    def complete(messages, **options):
        user = messages[-1]["content"]
        asked.append(user)
        if answers is not None and len(asked) <= len(answers):
            text = answers[len(asked) - 1]
        else:
            text = json.dumps({"lines": english_for(user)})
        return {
            "text": text,
            "finish_reason": "stop",
            "model": "qwen-chat",
            "input_tokens": 10,
            "output_tokens": 10,
        }

    monkeypatch.setattr(engine, "complete", complete)
    return asked


# What a line reads as ----------------------------------------------------------------


def test_a_line_awaits_its_english_unless_said_in_english_or_written():
    spoken = Segment(text="Hola", language="es")
    assert translation.awaits(spoken)
    assert translation.reading(spoken) == "Hola"
    spoken.english = "Hello"
    spoken.english_of = translation.signature("Hola")
    assert not translation.awaits(spoken)
    assert translation.reading(spoken) == "Hello"
    # A Correction on the words as spoken leaves the English stale.
    spoken.text = "Hola, ¿qué tal?"
    assert translation.awaits(spoken)
    english = Segment(text="Hello", language="en")
    assert not translation.awaits(english)
    assert translation.reading(english) == "Hello"
    assert not translation.awaits(Segment(text="  ", language="es"))


def test_the_windows_carry_context_lines_that_are_never_answered():
    lines = [
        prompts.Line(number=n, segment_id=f"s{n}", start=n * 5.0, speaker="A", text=t)
        for n, t in enumerate(["uno", "dos", "tres", "cuatro", "cinco", "seis"], 1)
    ]
    asked = {"s3", "s4"}
    windows = translation.windows(lines, asked, budget=10_000)
    assert len(windows) == 1
    assert [one.number for one in windows[0]["asked"]] == [3, 4]
    assert [one.number for one in windows[0]["context"]] == [1, 2, 5, 6]
    user = translation.window_input(windows[0], {"s3": "es", "s4": "es"})
    assert "[3] (es)" in user and "[1] (context, do not answer)" in user
    kept = translation.keep_lines(
        [
            {"n": 3, "english": "three"},
            {"n": 1, "english": "one"},  # a context line: never
            {"n": 4, "english": ""},  # empty: never
            {"n": 9, "english": "nine"},  # not in the window
            {"n": 4, "english": "x" * 400},  # absurdly long
            "not a dict",
        ],
        windows[0],
    )
    assert kept == {"s3": "three"}


# Whether the English is the engine's --------------------------------------------------


def test_by_engine_needs_qwen_and_the_ask(admin, tmp_path, settings, monkeypatch):
    engine_on(monkeypatch)
    recording = a_spanish_call(admin, tmp_path, settings)
    transcript = recording.transcript
    assert translation.by_engine(transcript)
    assert translation.wanted(transcript)
    assert [one.start for one in translation.to_do(transcript)] == [6.0, 10.0, 20.0]
    # Not asked: nothing is the engine's to write.
    recording.translate = False
    recording.save(update_fields=["translate"])
    transcript.recording.refresh_from_db()
    assert not translation.by_engine(transcript)
    # The mixed rule asks for it.
    transcript.language_mixed = True
    transcript.save(update_fields=["language_mixed"])
    settings_store.set_to("translate_mixed", True)
    assert translation.by_engine(transcript)
    # Under Whisper nothing moves.
    transcript.provenance = {"run-1": {"settings_used": {"model": "large-v3"}}}
    transcript.save(update_fields=["provenance"])
    assert not translation.by_engine(transcript)


# The run ------------------------------------------------------------------------------


def test_the_run_writes_the_english_line_by_line(
    admin, tmp_path, settings, monkeypatch
):
    engine_on(monkeypatch)
    asked = engine_translating(monkeypatch)
    recording = a_spanish_call(admin, tmp_path, settings)
    transcript = recording.transcript
    row = translation.queue_run(recording)
    assert row is not None and row.lines == 3 and row.how == "landed"
    assert translation.pending(transcript)
    # Queued twice: the database keeps one live run.
    assert translation.queue_run(recording) is None
    translation.run(row.pk)
    row.refresh_from_db()
    assert row.state == assistant.DONE and row.reason_class == ""
    assert row.lines_written == 3 and row.lines_missing == 0
    assert row.windows == 1 and row.windows_done == 1
    assert len(asked) == 1 and "(es)" in asked[0]
    # The English lines were never sent.
    assert "correctional facility" not in asked[0].split("[2]")[1]
    spanish = transcript.segments.filter(language="es").order_by("start")
    assert all(one.english.startswith("English of line") for one in spanish)
    assert all(one.english_of == translation.signature(one.text) for one in spanish)
    assert transcript.segments.get(start=0.0).english == ""
    assert not translation.awaits_any(transcript)
    # The reader takes the English; the run read the words as spoken.
    assert prompts.lines_of(transcript)[1].text == "English of line 2"
    assert prompts.lines_of(transcript, spoken=True)[1].text.startswith("¿Hablaste")
    # One audit row for the engine's call, counts only, feeding the pace.
    call = Row.objects.filter(event="AI assistant call").order_by("-at").first()
    assert call.details["feature"] == "translation" and call.details["written"] == 3
    assert "English of" not in json.dumps(call.details)
    assert Row.objects.filter(event="Translation queued").exists()
    said, tone = translation.words(transcript)
    assert said == "English ready" and tone == "ok"


def test_an_unreadable_window_is_lost_and_a_missing_line_is_counted(
    admin, tmp_path, settings, monkeypatch
):
    engine_on(monkeypatch)
    # Both rounds unreadable: nothing written, the run done with its count.
    engine_translating(monkeypatch, answers=["not json", "not json"])
    recording = a_spanish_call(admin, tmp_path, settings)
    transcript = recording.transcript
    row = translation.queue_run(recording)
    translation.run(row.pk)
    row.refresh_from_db()
    assert row.state == assistant.DONE
    assert row.reason_class == translation.LINES_MISSING and row.lines_missing == 3
    said, tone = translation.words(transcript)
    assert said == "English for 3 lines not written · Translate again"
    assert tone == "danger"
    assert (
        translation.words(transcript, brief=True)[0]
        == "English for 3 lines not written"
    )
    # Translate again queues once more.
    again = translation.again(recording, by=admin)
    assert again is not None and again.how == "again"


def test_the_run_waits_for_the_engine_and_a_problem_fails_it(
    admin, tmp_path, settings, monkeypatch
):
    settings_store.set_to("assistant_available", True)
    monkeypatch.setattr(engine, "configured", lambda: True)
    monkeypatch.setattr(engine, "is_reachable", lambda: False)
    recording = a_spanish_call(admin, tmp_path, settings)
    transcript = recording.transcript
    row = translation.queue_run(recording)
    translation.run(row.pk)
    row.refresh_from_db()
    assert row.state == assistant.QUEUED and row.reason_class == translation.ENGINE_AWAY
    assert translation.words(transcript) == ("English to follow", "warn")
    # The sweep's eye: a queued run with no task behind it, old enough.
    Translation.objects.filter(pk=row.pk).update(
        created=timezone.now() - dt.timedelta(minutes=3)
    )
    monkeypatch.setattr(translation, "task_waiting_for", lambda one: False)
    assert [one.pk for one in translation.queued_without_a_task()] == [row.pk]
    # All night: the pages say so.
    Translation.objects.filter(pk=row.pk).update(
        created=timezone.now() - dt.timedelta(hours=9)
    )
    assert translation.words(transcript)[0].startswith(
        "English not written: the engine"
    )
    # The engine back, and failing the call: the run fails with its reason.
    monkeypatch.setattr(engine, "is_reachable", lambda: True)

    def failing(messages, **options):
        raise engine.Problem(engine.TIMEOUT, "too slow")

    monkeypatch.setattr(engine, "complete", failing)
    translation.run(row.pk)
    row.refresh_from_db()
    assert row.state == assistant.FAILED and row.reason_class == engine.TIMEOUT
    assert translation.words(transcript)[1] == "danger"


def test_a_correction_leaves_one_line_stale_and_queues_a_run(
    admin, tmp_path, settings, monkeypatch
):
    engine_on(monkeypatch)
    engine_translating(monkeypatch)
    recording = a_spanish_call(admin, tmp_path, settings)
    transcript = recording.transcript
    row = translation.queue_run(recording)
    translation.run(row.pk)
    line = transcript.segments.get(start=10.0)
    line.text = "Sí, dijo que la audiencia es el quince."
    line.save(update_fields=["text"])
    translation.on_correction(line, by=admin)
    line.refresh_from_db()
    assert line.english == "" and translation.awaits(line)
    assert [one.start for one in translation.to_do(transcript)] == [10.0]
    queued = translation.latest(transcript)
    assert queued.how == "corrected" and queued.state == assistant.QUEUED
    assert queued.lines == 1


# The hooks and the pages --------------------------------------------------------------


def test_the_mail_waits_and_the_row_says_english_to_follow(
    admin, tmp_path, settings, monkeypatch
):
    from core import pages

    engine_on(monkeypatch)
    recording = a_spanish_call(admin, tmp_path, settings)
    transcript = recording.transcript
    assert translation.words(transcript) == ("English to follow", "warn")
    translation.queue_run(recording)
    assert mail._still_preparing(recording)
    recording.being_replaced = False
    recording.in_the_queue = False
    assert pages.state_words(recording) == ("English to follow", "warn")
    assert "read in the language spoken" in translation.mail_line([recording])


def test_exports_read_the_english_and_offer_the_words_as_spoken(
    admin, tmp_path, settings, monkeypatch
):
    engine_on(monkeypatch)
    engine_translating(monkeypatch)
    recording = a_spanish_call(admin, tmp_path, settings)
    transcript = recording.transcript
    translation.run(translation.queue_run(recording).pk)
    plain = exports.plain_text(recording)
    assert "English of line 2" in plain and "¿Hablaste" not in plain
    both = exports.plain_text(recording, with_spoken=True)
    assert "(as spoken) ¿Hablaste con el abogado ayer?" in both
    assert exports.kind_line(transcript) == "Translated to English from Spanish"
    notice = exports.notice_for(transcript)
    assert "office's language model" in notice and "Qwen3-ASR" in notice
    assert "not a certified" in notice
    captions = exports.srt(recording)
    assert "English of line 2" in captions
    assert "machine translation" in prompts.nature_line(recording, transcript)
    assert "Qwen3-ASR" in exports.english_words(transcript)
    # The Word export with the words as spoken builds.
    assert exports.word(recording, "adm", with_spoken=True)[:2] == b"PK"


def test_search_finds_either_text_and_says_which(
    admin, tmp_path, settings, monkeypatch
):
    from core import cases as the_cases

    engine_on(monkeypatch)
    engine_translating(monkeypatch)
    case = the_cases.Case.objects.create(name="A matter", owner=admin)
    recording = a_spanish_call(admin, tmp_path, settings)
    recording.case = case
    recording.save(update_fields=["case"])
    translation.run(translation.queue_run(recording).pk)
    found = case_search.search(case, "abogado", "words")
    hits = [hit for group in found["groups"] for hit in group["hits"]]
    assert hits and hits[0]["under"] == "in the words as spoken"
    found = case_search.search(case, "English of line 2", "words")
    hits = [hit for group in found["groups"] for hit in group["hits"]]
    assert hits and not hits[0]["under"]


def test_the_landing_stores_each_lines_language(admin, tmp_path, settings):
    # The service's per-line language (0.8.0) is kept from this release.
    from core import queue

    with open(queue.__file__, encoding="utf-8") as source:
        assert "language=(segment.get" in source.read()
    assert Transcript._meta.get_field  # the columns exist
    for name in ("language", "english", "english_of"):
        assert Segment._meta.get_field(name)
