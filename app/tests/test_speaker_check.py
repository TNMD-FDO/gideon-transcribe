"""The Speaker check (Phase 5 chapter 3, v1.55.0): the windows, the checks
on the engine's answer, the run as a transcript lands or on a press, the
corrections on the Speakers page, Accept and Dismiss through the same move
a line makes by hand, the switch, the night, and the documents.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest
from core import assistant, engine, prompts, settings_store, speaker_check, tasks
from core.assistant import PromptTemplate, SpeakerCheck, SpeakerCorrection
from core.audit import Row
from core.jobs import Segment
from core.models import LoginSession, User
from django.utils import timezone
from tests.test_prepare import a_recording, engine_answering

PASSWORD = "a-long-enough-password"
DOCS = Path(__file__).resolve().parents[2] / "docs"


@pytest.fixture
def admin(db):
    return User.objects.create_local_admin("adm", PASSWORD)


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def switched_on():
    settings_store.set_to("assistant_available", True)
    settings_store.set_to("speaker_check_available", True)


def swallow(monkeypatch):
    """The task's defer captured, now or scheduled."""
    deferred = []

    class Configured:
        def __init__(self, options):
            self.options = options

        def defer(self, **fields):
            deferred.append((self.options, fields))

    monkeypatch.setattr(
        tasks.check_speakers, "defer", lambda **fields: deferred.append(({}, fields))
    )
    monkeypatch.setattr(
        tasks.check_speakers, "configure", lambda **options: Configured(options)
    )
    return deferred


def moves(*items):
    return json.dumps(
        {
            "moves": [
                {"line": line, "from": from_, "to": to, "reason": why}
                for line, from_, to, why in items
            ]
        }
    )


# Without a database ------------------------------------------------------------------


def test_windows_split_by_seconds_and_carry_a_few_lines_over():
    lines = [prompts.Line(n + 1, n, float(n * 60), "Speaker 1", "w") for n in range(25)]
    spans = speaker_check.windows(lines, 600)
    assert spans[0] == (0, 10)
    assert spans[1] == (4, 20)
    assert spans[2] == (14, 25)
    # One line alone still makes a window; nothing makes none.
    assert speaker_check.windows(lines[:1], 600) == [(0, 1)]
    assert speaker_check.windows([], 600) == []


def test_keep_corrections_drops_what_fails_the_checks():
    lines = [
        prompts.Line(1, "a", 0.0, "Speaker 1", "Step out of the car, ma'am."),
        prompts.Line(2, "b", 4.0, "Speaker 2 (corrected)", "Why? What did I do?"),
        prompts.Line(3, "c", 8.0, "Speaker 1", "Licence and registration."),
    ]
    speakers = ["Speaker 1", "Speaker 2"]
    raw = [
        {"line": 2, "from": "Speaker 2", "to": "Speaker 1", "reason": "asks"},
        # A line not in the window, a speaker not on the transcript, a label
        # that is not what was shown, a move to the same speaker, and a
        # second move for a line already kept: all dropped.
        {"line": 9, "from": "Speaker 1", "to": "Speaker 2", "reason": "x"},
        {"line": 1, "from": "Speaker 1", "to": "Officer Kelly", "reason": "x"},
        {"line": 3, "from": "Speaker 2", "to": "Speaker 1", "reason": "x"},
        {"line": 3, "from": "Speaker 1", "to": "Speaker 1", "reason": "x"},
        {"line": 2, "from": "Speaker 2", "to": "Speaker 1", "reason": "again"},
        "not even a dict",
    ]
    kept = prompts.keep_corrections(raw, lines, speakers)
    assert kept == [
        {
            "segment_id": "b",
            "start": 4.0,
            "quote": "Why? What did I do?",
            "from": "Speaker 2",
            "to": "Speaker 1",
            "reason": "asks",
        }
    ]
    # The engine may only answer with a Speaker on the Transcript.
    schema = prompts.speaker_check_schema(speakers)
    assert (
        schema["properties"]["moves"]["items"]["properties"]["to"]["enum"] == speakers
    )
    assert "Speakers: Speaker 1, Speaker 2" in prompts.speaker_check_input(
        lines, speakers
    )
    assert "[2] [00:00:04] Speaker 2 (corrected): Why?" in prompts.speaker_check_input(
        lines, speakers
    )


# With one ----------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_check_runs_as_the_transcript_lands_and_the_page_decides(
    admin, tmp_path, settings, client, monkeypatch
):
    switched_on()
    # One window over the whole recording: its lines span twelve minutes.
    settings_store.set_to("speaker_check_window_seconds", 1800)
    deferred = swallow(monkeypatch)
    recording = a_recording(admin, tmp_path, settings)
    transcript = recording.transcript
    # As the transcript lands: one check queued at once under lands.
    speaker_check.on_transcript(recording)
    check = SpeakerCheck.objects.get()
    assert check.asked_by is None and check.state == assistant.QUEUED
    assert deferred == [({}, {"check_id": str(check.pk)})]
    assert Row.objects.get(event="Speaker check queued").details["how"] == "landed"
    # Not twice while one waits.
    assert speaker_check.queue_check(recording) is None

    asked = engine_answering(
        monkeypatch,
        [
            moves(
                (2, "Speaker 2", "Speaker 1", "the officer points"),
                (1, "Speaker 1", "Nobody", "no such speaker"),
                (3, "Speaker 2", "Speaker 1", "label not as shown"),
            )
        ],
    )
    speaker_check.run(check.pk)
    check.refresh_from_db()
    assert check.state == assistant.DONE and check.found == 1 and check.windows == 1
    call = asked[0]
    assert call["temperature"] == 0.0 and call["thinking"] is False
    assert call["schema"]["properties"]["moves"]["items"]["properties"]["to"][
        "enum"
    ] == [
        "Speaker 1",
        "Speaker 2",
    ]
    assert "Speakers: Speaker 1, Speaker 2" in call["messages"][-1]["content"]
    assert (
        "Speaker check v1"
        in Row.objects.get(event="AI assistant call").details["templates"]
    )
    row = Row.objects.get(event="AI assistant call")
    assert row.details["feature"] == "speaker_check" and row.details["found"] == 1
    assert "Look at that" not in json.dumps(row.details)

    correction = SpeakerCorrection.objects.get()
    assert (correction.speaker_from, correction.speaker_to) == (
        "Speaker 2",
        "Speaker 1",
    )
    assert correction.quote == "Look at that, right there." and correction.start == 12.4

    signed_in(client, admin)
    state = client.get(f"/recording/{recording.pk}/assistant").json()["speaker_check"]
    assert state["offered"] is True and state["run"]["state"] == "done"
    (pending,) = state["pending"]
    assert pending["clock"] == "00:00:12" and pending["to"] == "Speaker 1"
    assert pending["reason"] == "the officer points"
    # The Speakers page carries the button and the section; the recording
    # page the strip's pill.
    page = client.get(f"/recording/{recording.pk}/speakers").content.decode()
    assert 'id="check-speakers"' in page and 'id="corrections"' in page
    assert "speakerCheck: true" in page
    viewer_page = client.get(f"/recording/{recording.pk}").content.decode()
    assert 'id="corrections-pill"' in viewer_page

    # Accept moves the line as the number keys do: the same Undo, an audit
    # row without the words.
    answer = client.post(f"/correction/{correction.pk}/accept").json()
    assert answer["changed"] == 1 and answer["stale"] is False
    assert answer["undo"]
    assert Segment.objects.get(start=12.4).speaker == "Speaker 1"
    transcript.refresh_from_db()
    assert transcript.speaker_changes[-1]["line"] is True
    row = Row.objects.get(event="Speaker correction accepted")
    assert row.details["segments_changed"] == 1 and row.details["how"] == "check"
    assert "Look at that" not in json.dumps(row.details)
    correction.refresh_from_db()
    assert correction.state == SpeakerCorrection.ACCEPTED
    assert correction.decided_by == admin
    assert client.post(f"/correction/{correction.pk}/accept").status_code == 404

    # A correction whose line changed since the check is not applied on the
    # stale label: it is dismissed and the page told.
    stale = SpeakerCorrection.objects.create(
        transcript=transcript,
        segment=Segment.objects.get(start=0.0),
        start=0.0,
        quote="This is Officer Ruiz.",
        speaker_from="Speaker 2",
        speaker_to="Speaker 1",
    )
    answer = client.post(f"/correction/{stale.pk}/accept").json()
    assert answer["stale"] is True and answer["changed"] == 0
    stale.refresh_from_db()
    assert stale.state == SpeakerCorrection.DISMISSED
    assert Segment.objects.get(start=0.0).speaker == "Speaker 1"

    # Dismiss puts one away, with its row.
    put_away = SpeakerCorrection.objects.create(
        transcript=transcript,
        segment=Segment.objects.get(start=724.0),
        start=724.0,
        quote="Tell me about the car.",
        speaker_from="Speaker 1",
        speaker_to="Speaker 2",
    )
    assert client.post(f"/correction/{put_away.pk}/dismiss").json()["ok"] is True
    put_away.refresh_from_db()
    assert put_away.state == SpeakerCorrection.DISMISSED
    assert Row.objects.filter(event="Speaker correction dismissed").count() == 1
    # A run later does not offer the dismissed line again.
    speaker_check._store(
        transcript,
        {
            put_away.segment_id: {
                "segment_id": put_away.segment_id,
                "start": 724.0,
                "quote": "Tell me about the car.",
                "from": "Speaker 1",
                "to": "Speaker 2",
                "reason": "x",
            }
        },
    )
    assert not transcript.corrections.filter(state=SpeakerCorrection.PENDING).exists()


@pytest.mark.django_db
def test_accept_all_moves_every_pending_line(admin, tmp_path, settings, client):
    switched_on()
    recording = a_recording(admin, tmp_path, settings)
    transcript = recording.transcript
    for start, from_, to in (
        (12.4, "Speaker 2", "Speaker 1"),
        (724.0, "Speaker 1", "Speaker 2"),
    ):
        SpeakerCorrection.objects.create(
            transcript=transcript,
            segment=Segment.objects.get(start=start),
            start=start,
            speaker_from=from_,
            speaker_to=to,
        )
    signed_in(client, admin)
    answer = client.post(f"/recording/{recording.pk}/corrections/accept-all").json()
    assert answer["changed"] == 2 and answer["undo"]
    assert Segment.objects.get(start=12.4).speaker == "Speaker 1"
    assert Segment.objects.get(start=724.0).speaker == "Speaker 2"
    assert not transcript.corrections.filter(state=SpeakerCorrection.PENDING).exists()
    assert Row.objects.filter(event="Speaker correction accepted").count() == 2


@pytest.mark.django_db
def test_a_press_runs_now_and_the_switch_off_runs_nothing(
    admin, tmp_path, settings, client, monkeypatch
):
    deferred = swallow(monkeypatch)
    recording = a_recording(admin, tmp_path, settings)
    signed_in(client, admin)
    # Off: nothing queued as the transcript lands, the route says so, and
    # the page carries no button.
    speaker_check.on_transcript(recording)
    assert deferred == [] and not SpeakerCheck.objects.exists()
    assert client.post(f"/recording/{recording.pk}/speaker-check").status_code == 404
    page = client.get(f"/recording/{recording.pk}/speakers").content.decode()
    assert 'id="check-speakers"' not in page and "speakerCheck: false" in page
    assert (
        client.get(f"/recording/{recording.pk}/assistant").json()["speaker_check"][
            "offered"
        ]
        is False
    )
    # On: a press queues a run at once, whatever the position, and not twice.
    switched_on()
    settings_store.set_to("speaker_check_runs", "overnight")
    answer = client.post(f"/recording/{recording.pk}/speaker-check")
    assert answer.status_code == 200
    check = SpeakerCheck.objects.get()
    assert check.asked_by == admin
    assert deferred == [({}, {"check_id": str(check.pk)})]
    assert Row.objects.get(event="Speaker check queued").details["how"] == "pressed"
    assert client.post(f"/recording/{recording.pk}/speaker-check").status_code == 409
    # One speaker only: nothing to check.
    Segment.objects.filter(transcript=recording.transcript).update(speaker="Speaker 1")
    check.state = assistant.DONE
    check.save(update_fields=["state"])
    assert client.post(f"/recording/{recording.pk}/speaker-check").status_code == 409
    assert speaker_check.queue_check(recording) is None


@pytest.mark.django_db
def test_under_overnight_a_check_queued_by_day_waits_for_the_window(
    admin, tmp_path, settings, monkeypatch
):
    switched_on()
    settings_store.set_to("speaker_check_runs", "overnight")
    settings_store.set_to("vision_window_start", "20:00")
    settings_store.set_to("vision_window_end", "06:00")
    now = timezone.localtime(timezone.now()).replace(
        hour=14, minute=0, second=0, microsecond=0
    )
    assert speaker_check.seconds_until_the_night(now) == 6 * 3600
    assert speaker_check.seconds_until_the_night(now.replace(hour=22)) == 0
    assert speaker_check.seconds_until_the_night(now.replace(hour=3)) == 0
    monkeypatch.setattr(timezone, "now", lambda: now - dt.timedelta(hours=0))
    deferred = swallow(monkeypatch)
    recording = a_recording(admin, tmp_path, settings)
    speaker_check.on_transcript(recording)
    ((options, fields),) = deferred
    assert options["schedule_in"]["seconds"] == 6 * 3600
    assert Row.objects.get(event="Speaker check queued").details["waits_seconds"] == (
        6 * 3600
    )


@pytest.mark.django_db
def test_an_unreadable_window_is_lost_and_a_problem_keeps_what_was_found(
    admin, tmp_path, settings, monkeypatch
):
    switched_on()
    settings_store.set_to("speaker_check_window_seconds", 120)
    recording = a_recording(admin, tmp_path, settings)
    transcript = recording.transcript
    # Two windows: the first answer unreadable, the second good.
    engine_answering(
        monkeypatch, ["not json", moves((2, "Speaker 2", "Speaker 1", "asks"))]
    )
    check = SpeakerCheck.objects.create(transcript=transcript)
    speaker_check.run(check.pk)
    check.refresh_from_db()
    assert check.state == assistant.DONE and check.windows == 2 and check.found == 1
    # A problem on the second call: the run fails with its reason, and the
    # correction the first window found is kept.
    asked = engine_answering(
        monkeypatch, [moves((2, "Speaker 2", "Speaker 1", "asks"))]
    )
    good = engine.complete

    def failing(messages, **options):
        if asked:
            raise engine.Problem(engine.TIMEOUT, "too slow")
        return good(messages, **options)

    monkeypatch.setattr(engine, "complete", failing)
    check = SpeakerCheck.objects.create(transcript=transcript)
    speaker_check.run(check.pk)
    check.refresh_from_db()
    assert check.state == assistant.FAILED and check.reason_class == engine.TIMEOUT
    assert check.windows == 1 and check.found == 1
    assert transcript.corrections.filter(state=SpeakerCorrection.PENDING).count() == 1
    assert Row.objects.filter(event="AI assistant call", outcome="failure").exists()


@pytest.mark.django_db
def test_a_swap_between_times_moves_both_ways_and_undo_puts_both_back(
    admin, tmp_path, settings, client
):
    switched_on()
    recording = a_recording(admin, tmp_path, settings)
    transcript = recording.transcript
    # Lines at 0 (Speaker 1), 12.4 (Speaker 2), 724 (Speaker 1). A correction
    # on the 12.4 line to Speaker 1 is fulfilled by the swap; one on the
    # first line to Speaker 2 is not.
    fulfilled = SpeakerCorrection.objects.create(
        transcript=transcript,
        segment=Segment.objects.get(start=12.4),
        start=12.4,
        speaker_from="Speaker 2",
        speaker_to="Speaker 1",
    )
    outside = SpeakerCorrection.objects.create(
        transcript=transcript,
        segment=Segment.objects.get(start=724.0),
        start=724.0,
        speaker_from="Speaker 1",
        speaker_to="Speaker 2",
    )
    signed_in(client, admin)
    answer = client.post(
        f"/recording/{recording.pk}/speakers/swap",
        {"a": "Speaker 1", "b": "Speaker 2", "start": 0, "end": 60},
        content_type="application/json",
    ).json()
    assert answer["changed"] == 2
    assert answer["undo"] == "swapping Speaker 1 and Speaker 2 between 0:00 and 1:00"
    assert Segment.objects.get(start=0.0).speaker == "Speaker 2"
    assert Segment.objects.get(start=12.4).speaker == "Speaker 1"
    assert Segment.objects.get(start=724.0).speaker == "Speaker 1"
    fulfilled.refresh_from_db()
    outside.refresh_from_db()
    assert fulfilled.state == SpeakerCorrection.ACCEPTED
    assert outside.state == SpeakerCorrection.PENDING
    row = Row.objects.get(event="Speakers swapped")
    assert row.details["segments_changed"] == 2 and row.details["seconds"] == 60
    assert "Speaker" not in json.dumps(row.details)
    # Undo puts both sides back.
    undone = client.post(f"/recording/{recording.pk}/speakers/undo").json()
    assert undone["restored"] == 2
    assert Segment.objects.get(start=0.0).speaker == "Speaker 1"
    assert Segment.objects.get(start=12.4).speaker == "Speaker 2"
    assert Row.objects.get(event="Speaker change undone").details["was_swap"] is True
    # The refusals: the same speaker twice, times backwards, a stranger, an
    # empty stretch.
    for body, status in (
        ({"a": "Speaker 1", "b": "Speaker 1", "start": 0, "end": 60}, 400),
        ({"a": "Speaker 1", "b": "Speaker 2", "start": 60, "end": 0}, 400),
        ({"a": "Speaker 1", "b": "Nobody", "start": 0, "end": 60}, 404),
        ({"a": "Speaker 1", "b": "Speaker 2", "start": 100, "end": 200}, 409),
    ):
        assert (
            client.post(
                f"/recording/{recording.pk}/speakers/swap",
                body,
                content_type="application/json",
            ).status_code
            == status
        ), body
    page = client.get(f"/recording/{recording.pk}/speakers").content.decode()
    assert 'id="swap-form"' in page and 'id="swap-open"' in page


@pytest.mark.django_db
def test_a_window_cut_short_at_the_cap_is_counted_and_said(
    admin, tmp_path, settings, client, monkeypatch
):
    switched_on()
    settings_store.set_to("speaker_check_window_seconds", 1800)
    recording = a_recording(admin, tmp_path, settings)
    engine_answering(monkeypatch, [moves((2, "Speaker 2", "Speaker 1", "asks"))])
    good = engine.complete

    def cut(messages, **options):
        answer = good(messages, **options)
        answer["finish_reason"] = "length"
        return answer

    monkeypatch.setattr(engine, "complete", cut)
    check = SpeakerCheck.objects.create(transcript=recording.transcript)
    speaker_check.run(check.pk)
    check.refresh_from_db()
    assert check.state == assistant.DONE and check.found == 1 and check.cut_short == 1
    assert Row.objects.get(event="AI assistant call").details["cut_short"] == 1
    signed_in(client, admin)
    state = client.get(f"/recording/{recording.pk}/assistant").json()["speaker_check"]
    assert state["run"]["cut_short"] == 1
    schema = prompts.speaker_check_schema(["Speaker 1", "Speaker 2"])
    assert schema["properties"]["moves"]["maxItems"] == 400


@pytest.mark.django_db
def test_the_settings_page_the_templates_page_and_the_documents(admin, client):
    signed_in(client, admin)
    page = client.get("/panel/settings/speakers").content.decode()
    for name in (
        "Speaker check",
        "Speaker check runs",
        "Speaker check window",
        "Speaker check answer cap",
        "Speaker check time limit",
    ):
        assert name in page
    templates = client.get("/panel/templates").content.decode()
    assert "Speaker check" in templates
    row = PromptTemplate.named(PromptTemplate.SPEAKER_CHECK)
    assert row.text == prompts.SPEAKER_CHECK and not row.behind
    assert (
        prompts.text_hash(prompts.SPEAKER_CHECK)
        in prompts.SHIPPED_HISTORY["prompt:speaker_check"]
    )
    assert settings_store.time_limit_seconds("speaker_check") == 180

    catalogue = (DOCS / "spec" / "ADMIN-SETTINGS-CATALOGUE.md").read_text(
        encoding="utf-8"
    )
    for name in (
        "Speaker check",
        "Speaker check runs",
        "Speaker check window",
        "Speaker check answer cap",
        "Speaker check time limit",
    ):
        assert f"| {name} " in catalogue, name
    glossary = (DOCS.parent / "CONTEXT.md").read_text(encoding="utf-8")
    assert "**Speaker check**" in glossary and "**Speaker correction**" in glossary
    spec = (DOCS / "spec" / "SPEC-PHASE-5.md").read_text(encoding="utf-8")
    assert "## 3. The Speaker check" in spec
    for guide in ("user-guide.md", "admin-guide.md"):
        assert "Speaker check" in (DOCS / guide).read_text(encoding="utf-8"), guide
