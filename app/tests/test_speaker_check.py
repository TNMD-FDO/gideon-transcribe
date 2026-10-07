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


SKETCH = (
    "Speaker 1 asks the questions and gives the commands; the officer. "
    "Speaker 2 answers and speaks of the car as his own; the driver."
)


def too_small_for_the_whole(monkeypatch, transcript):
    """The engine's window set just under what the whole transcript needs,
    so the check reads in windows and the sketch reads what fits."""
    lines = prompts.lines_of(transcript)
    speakers = speaker_check.speakers_of(transcript)
    system = prompts.system_message(
        PromptTemplate.named(PromptTemplate.GROUND_RULES).text,
        PromptTemplate.named(PromptTemplate.SPEAKER_CHECK).text,
        prompts.SPEAKER_CHECK_FORMAT,
    )
    whole = prompts.tokens(system) + prompts.tokens(
        prompts.speaker_check_input(lines, speakers, SKETCH)
    )
    cap = settings_store.speaker_check_answer_cap()
    monkeypatch.setattr(assistant, "window", lambda: whole + cap - 1)


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
    admin, tmp_path, settings, client, monkeypatch, django_capture_on_commit_callbacks
):
    switched_on()
    # Ten-minute windows: these lines span twelve minutes, so two, which the
    # whole read replaces (v1.100.0).
    settings_store.set_to("speaker_check_window_seconds", 600)
    deferred = swallow(monkeypatch)
    recording = a_recording(admin, tmp_path, settings)
    transcript = recording.transcript
    # As the transcript lands: one check queued at once under lands, its
    # task sent once the row is committed (v1.56.1).
    with django_capture_on_commit_callbacks(execute=True):
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
            SKETCH,
            moves(
                (2, "Speaker 2", "Speaker 1", "the officer points"),
                (1, "Speaker 1", "Nobody", "no such speaker"),
                (3, "Speaker 2", "Speaker 1", "label not as shown"),
            ),
        ],
    )
    speaker_check.run(check.pk)
    check.refresh_from_db()
    assert check.state == assistant.DONE and check.found == 1 and check.windows == 1
    # The sketch first (v1.100.0): the whole transcript, plain text, kept on
    # the run; then the check, given the sketch above its lines, whole in
    # one window since it fits; and no reading after them (v1.128.0).
    assert len(asked) == 2
    assert check.second_look["rows"] == 1
    sketching = asked[0]
    assert "Read the whole transcript" in sketching["messages"][0]["content"]
    assert "Speakers: Speaker 1, Speaker 2" in sketching["messages"][-1]["content"]
    assert "schema" not in sketching
    assert check.sketch == SKETCH and check.whole is True
    call = asked[1]
    # Read whole, the one call has the time of the windows it replaced
    # (v1.100.1): these lines span twelve minutes, two ten-minute windows.
    assert sketching["timeout"] == assistant.time_limit("speaker_check")
    assert call["timeout"] == assistant.time_limit("speaker_check") * 2
    assert prompts.SPEAKER_SKETCH_ABOVE in call["messages"][-1]["content"]
    assert SKETCH in call["messages"][-1]["content"]
    assert prompts.SPEAKER_SKETCH_USE in call["messages"][-1]["content"]
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
    assert row.details["sketch"] is True and row.details["whole"] is True
    assert row.details["sketch_cut"] is False
    assert "Look at that" not in json.dumps(row.details)
    assert "asks the questions" not in json.dumps(row.details)

    correction = SpeakerCorrection.objects.get()
    assert (correction.speaker_from, correction.speaker_to) == (
        "Speaker 2",
        "Speaker 1",
    )
    assert correction.quote == "Look at that, right there." and correction.start == 12.4

    signed_in(client, admin)
    state = client.get(f"/recording/{recording.pk}/assistant").json()["speaker_check"]
    assert state["offered"] is True and state["run"]["state"] == "done"
    assert state["run"]["sketch"] == SKETCH and state["run"]["whole"] is True
    (pending,) = state["pending"]
    assert pending["clock"] == "00:00:12" and pending["to"] == "Speaker 1"
    assert pending["reason"] == "the officer points"
    # The Speakers page carries the button and the section; the recording
    # page the strip's pill.
    page = client.get(f"/recording/{recording.pk}/speakers").content.decode()
    assert 'id="check-speakers"' in page and 'id="corrections"' in page
    # The sketch stays on the run and off the page (v1.129.0).
    assert 'id="check-sketch"' not in page
    assert "Who is who, as the check read it" not in page
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
def test_accept_every_voice_backed_stretch_moves_those_lines_and_leaves_the_rest(
    admin, tmp_path, settings, client
):
    """v1.128.0: the one-press path takes the corrections the voice step
    itself heard the other speaker on, and leaves the rest to their cards."""
    switched_on()
    recording = a_recording(admin, tmp_path, settings)
    transcript = recording.transcript
    for start, from_, to, voice in (
        (12.4, "Speaker 2", "Speaker 1", SpeakerCorrection.VOICE_AGREES),
        (724.0, "Speaker 1", "Speaker 2", ""),
    ):
        SpeakerCorrection.objects.create(
            transcript=transcript,
            segment=Segment.objects.get(start=start),
            start=start,
            speaker_from=from_,
            speaker_to=to,
            voice=voice,
        )
    signed_in(client, admin)
    answer = client.post(f"/recording/{recording.pk}/corrections/accept-all").json()
    assert answer["changed"] == 1 and answer["undo"]
    assert Segment.objects.get(start=12.4).speaker == "Speaker 1"
    assert Segment.objects.get(start=724.0).speaker == "Speaker 1"
    assert transcript.corrections.filter(state=SpeakerCorrection.PENDING).count() == 1
    assert Row.objects.filter(event="Speaker correction accepted").count() == 1


def spoken(text, label, other="", others=0):
    """A line's words as the service gives them: each with the label of the
    voice it fell under, the first `others` under another voice."""
    return [
        {
            "word": word,
            "start": float(at),
            "end": float(at) + 0.2,
            "speaker": other if at < others else label,
        }
        for at, word in enumerate(text.split())
    ]


@pytest.mark.django_db
def test_the_check_says_the_big_thing_first_and_the_voice_is_the_one_measure(
    admin, tmp_path, settings, client, monkeypatch
):
    """v1.128.0: no second reading. Each move keeps the voice step's note;
    the state draws one card per label whose lines often read as another
    speaker's (Merge primary only when the share and the voice agree) and
    one card per stretch of moves between the same two speakers; a card's
    worth is accepted or dismissed at once; nothing is dropped."""
    switched_on()
    monkeypatch.setattr(speaker_check, "CARD_LEAST", 2)
    recording = a_recording(admin, tmp_path, settings)
    transcript = recording.transcript
    transcript.segments.all().delete()
    firm = "I am going to ask you one more time to step out now please"
    for start, name, text, words in (
        (0.0, "Speaker 1", "Step out of the car for me, please.", None),
        (5.0, "Speaker 2", "Why, what did I do, officer?", None),
        (10.0, "Speaker 2", "Licence and registration, right now please.", None),
        (15.0, "Speaker 1", "It is in the glove box, sir.", None),
        (20.0, "Speaker 2", "Okay.", None),
        (25.0, "Speaker 1", firm, spoken(firm, "SPEAKER_1")),
        (
            30.0,
            "Speaker 1",
            "No no that bag is not mine at all",
            spoken("No no that bag is not mine at all", "SPEAKER_1", "SPEAKER_2", 3),
        ),
        (35.0, "Speaker 2", "I told you already that the car is mine.", None),
    ):
        label = name.upper().replace(" ", "_")
        Segment.objects.create(
            transcript=transcript,
            start=start,
            end=start + 4,
            text=text,
            speaker=name,
            speaker_label=label,
            words=words if words is not None else spoken(text, label),
        )
    check = SpeakerCheck.objects.create(transcript=transcript, asked_by=admin)
    asked = engine_answering(
        monkeypatch,
        [
            SKETCH,
            moves(
                (3, "Speaker 2", "Speaker 1", "a command"),
                (4, "Speaker 1", "Speaker 2", "answers"),
                (5, "Speaker 2", "Speaker 1", "acknowledges"),
                (6, "Speaker 1", "Speaker 2", "pleads"),
                (7, "Speaker 1", "Speaker 2", "denies the bag"),
                (8, "Speaker 2", "Speaker 1", "speaks of the car"),
            ),
        ],
    )
    speaker_check.run(check.pk)
    check.refresh_from_db()
    assert check.state == assistant.DONE and check.found == 6
    # The sketch and the one window: no reading after them.
    assert len(asked) == 2
    assert check.second_look == {
        "rows": 6,
        "voice_agrees": 1,
        "voice_against": 1,
        "silent": 4,
    }
    by_start = {one.start: one for one in SpeakerCorrection.objects.all()}
    assert by_start[30.0].voice == "agrees" and by_start[25.0].voice == "against"
    assert all(one.second == "" for one in by_start.values())
    assert {one.state for one in by_start.values()} == {SpeakerCorrection.PENDING}
    row = Row.objects.get(event="AI assistant call")
    assert row.details["voice_agrees"] == 1 and row.details["voice_against"] == 1
    assert "backed" not in row.details and "Licence" not in json.dumps(row.details)

    # The state: six pending, two speaker cards, five stretches, all within
    # the cards' pairs.
    signed_in(client, admin)
    state = client.get(f"/recording/{recording.pk}/assistant").json()["speaker_check"]
    assert len(state["pending"]) == 6 and "aside" not in state
    cards = {one["from"]: one for one in state["speakers"]}
    assert set(cards) == {"Speaker 1", "Speaker 2"}
    one = cards["Speaker 1"]
    assert (one["to"], one["count"], one["lines"], one["share"]) == (
        "Speaker 2",
        3,
        4,
        0.75,
    )
    # Three of four lines read as the other speaker, but the voice backs only
    # one of them, so the bar is not cleared: the card describes.
    assert one["clears"] is False and one["voice"] == "agrees"
    assert one["voice_both"] == 1 and one["voice_against"] == 1
    assert [hear["start"] for hear in one["hear"]] == [15.0, 25.0, 30.0]
    assert one["own"]["start"] == 0.0 and len(one["ids"]) == 3
    runs = state["stretches"]
    assert len(runs) == 5 and all(run["covered"] for run in runs)
    pair = [run for run in runs if run["count"] == 2][0]
    assert (pair["from"], pair["to"], pair["start"], pair["end"]) == (
        "Speaker 1",
        "Speaker 2",
        25.0,
        30.0,
    )
    assert pair["voice"] == "mixed" and pair["reason"] == "pleads"
    assert runs[0]["voice"] == "agrees" or runs[0]["voice"] == "silent"
    assert state["run"]["voice_notes"]["rows"] == 6
    assert speaker_check.pending_count(transcript) == 6
    page = client.get(f"/recording/{recording.pk}/speakers").content.decode()
    assert 'id="speaker-cards"' in page and 'id="stretches"' in page
    assert 'id="stretches-quiet"' in page and 'id="corrections-progress"' in page
    assert 'id="corrections-aside"' not in page
    script = (
        Path(__file__).resolve().parents[1] / "static" / "speakers-page.js"
    ).read_text(encoding="utf-8")
    assert "two voices heard" in script and "the voice is silent" in script
    # Every finding is a question with a yes and a no (v1.129.0).
    assert "the same voice as" in script and "Yes, the same voice" in script
    assert "Yes, move " in script and "Yes to all " in script
    assert "after listening" not in script and "secondWords" not in script

    # A stretch accepted at once moves its lines; a card dismissed at once
    # puts its corrections away; the decisions are counted.
    answer = client.post(
        f"/recording/{recording.pk}/corrections/accept-many",
        {"ids": ",".join(pair["ids"])},
    ).json()
    assert answer["ok"] is True and answer["changed"] == 2 and answer["decided"] == 2
    assert Segment.objects.get(start=25.0).speaker == "Speaker 2"
    assert Segment.objects.get(start=30.0).speaker == "Speaker 2"
    answer = client.post(
        f"/recording/{recording.pk}/corrections/dismiss-many",
        {"ids": ",".join(cards["Speaker 2"]["ids"])},
    ).json()
    assert answer["ok"] is True and answer["decided"] == 3
    assert transcript.corrections.filter(state=SpeakerCorrection.PENDING).count() == 1
    assert speaker_check.score(transcript) == {"accepted": 2, "dismissed": 3}
    # Nothing left for the one-press path: the voice-backed line is already moved.
    assert (
        client.post(f"/recording/{recording.pk}/corrections/accept-all").json()[
            "changed"
        ]
        == 0
    )
    assert (
        client.post(
            f"/recording/{recording.pk}/corrections/accept-many", {"ids": "nothing"}
        ).status_code
        == 409
    )


def test_the_voice_says_nothing_of_a_short_line_or_a_label_spread_over_names(db):
    """What the voice step heard is read from the words' own labels, and only
    where they can be trusted: a short line firm on its speaker settles
    nothing, and words without labels say nothing."""
    from collections import Counter

    assert speaker_check.voice_of(Counter(), "A", "B") == ("", "")
    assert speaker_check.voice_of(Counter({"A": 5}), "A", "B") == ("", "")
    verdict, note = speaker_check.voice_of(Counter({"A": 12}), "A", "B")
    assert verdict == "against" and "all 12 words" in note
    verdict, note = speaker_check.voice_of(Counter({"A": 20, "B": 2}), "A", "B")
    assert verdict == "agrees" and "A and B" in note
    assert speaker_check.voice_of(Counter({"A": 20, "B": 1}), "A", "B")[0] == ""


@pytest.mark.django_db
def test_a_press_runs_now_and_the_switch_off_runs_nothing(
    admin, tmp_path, settings, client, monkeypatch, django_capture_on_commit_callbacks
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
    with django_capture_on_commit_callbacks(execute=True):
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
    admin, tmp_path, settings, monkeypatch, django_capture_on_commit_callbacks
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
    with django_capture_on_commit_callbacks(execute=True):
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
    # The engine's window made too small for the whole transcript, so the
    # check reads in windows (v1.100.0), and the sketch reads what fits.
    too_small_for_the_whole(monkeypatch, transcript)
    # No lines carried over, or the second window of these three lines would
    # be the whole transcript again.
    monkeypatch.setattr(speaker_check, "OVERLAP_LINES", 0)
    # Two windows: the first answer good, the second unreadable.
    engine_answering(
        monkeypatch, [SKETCH, moves((2, "Speaker 2", "Speaker 1", "asks")), "not json"]
    )
    check = SpeakerCheck.objects.create(transcript=transcript)
    speaker_check.run(check.pk)
    check.refresh_from_db()
    assert check.state == assistant.DONE and check.windows == 2 and check.found == 1
    assert check.whole is False and check.sketch == SKETCH
    row = Row.objects.filter(event="AI assistant call").order_by("-at").first()
    assert row.details["whole"] is False and row.details["sketch_cut"] is False
    # A problem on the second window: the run fails with its reason, and the
    # correction the first window found is kept.
    asked = engine_answering(
        monkeypatch, [SKETCH, moves((2, "Speaker 2", "Speaker 1", "asks"))]
    )
    good = engine.complete

    def failing(messages, **options):
        if len(asked) >= 2:
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
def test_the_sketch_reads_what_fits_and_a_failed_sketch_stops_nothing(
    admin, tmp_path, settings, monkeypatch
):
    """v1.100.0: an engine too small for the whole transcript is given as much
    as fits, told so; a sketch the engine refuses leaves the check to run
    without one, and the page says nothing of a sketch."""
    switched_on()
    recording = a_recording(admin, tmp_path, settings)
    transcript = recording.transcript
    speakers = speaker_check.speakers_of(transcript)
    ground = PromptTemplate.named(PromptTemplate.GROUND_RULES).text
    system = prompts.system_message(ground, prompts.SPEAKER_SKETCH, "")
    one_line = prompts.tokens(
        prompts.speaker_sketch_input(prompts.lines_of(transcript)[:1], speakers, True)
    )
    cap = prompts.sketch_cap(speakers)
    monkeypatch.setattr(
        assistant, "window", lambda: prompts.tokens(system) + one_line + cap + 5
    )
    asked = engine_answering(monkeypatch, [SKETCH])
    words, cut, told = speaker_check.sketch_of(transcript, speakers, ground)
    assert words == SKETCH and cut is True and told["model"] == "the-model"
    assert (
        "Only the first part of the transcript is given"
        in asked[0]["messages"][-1]["content"]
    )
    assert asked[0]["max_completion_tokens"] == cap
    assert asked[0]["messages"][-1]["content"].count("] [") == 1

    def refusing(messages, **options):
        raise engine.Problem(engine.TIMEOUT, "too slow")

    monkeypatch.setattr(engine, "complete", refusing)
    assert speaker_check.sketch_of(transcript, speakers, ground) == ("", True, {})
    # The check itself, with the sketch refused: the windows run without it.
    monkeypatch.setattr(assistant, "window", lambda: 100_000)
    calls = []
    good = engine_answering(monkeypatch, [moves((2, "Speaker 2", "Speaker 1", "asks"))])

    def sketch_refused(messages, **options):
        calls.append(messages)
        if len(calls) == 1:
            raise engine.Problem(engine.TIMEOUT, "too slow")
        return engine_answering_good(messages, **options)

    engine_answering_good = engine.complete
    monkeypatch.setattr(engine, "complete", sketch_refused)
    check = SpeakerCheck.objects.create(transcript=transcript)
    speaker_check.run(check.pk)
    check.refresh_from_db()
    assert check.state == assistant.DONE and check.found == 1 and check.sketch == ""
    assert prompts.SPEAKER_SKETCH_ABOVE not in good[-1]["messages"][-1]["content"]
    row = Row.objects.filter(event="AI assistant call").order_by("-at").first()
    assert row.details["sketch"] is False and row.details["whole"] is True
    assert speaker_check.state_json(transcript)["run"]["sketch"] == ""


@pytest.mark.django_db
def test_a_window_cut_short_at_the_cap_is_counted_and_said(
    admin, tmp_path, settings, client, monkeypatch
):
    switched_on()
    settings_store.set_to("speaker_check_window_seconds", 1800)
    recording = a_recording(admin, tmp_path, settings)
    engine_answering(
        monkeypatch, [SKETCH, moves((2, "Speaker 2", "Speaker 1", "asks"))]
    )
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
def test_a_job_ahead_of_its_row_looks_again_and_the_sweep_queues_again(
    admin, tmp_path, settings, monkeypatch
):
    import uuid

    from core import tasks

    switched_on()
    deferred = swallow(monkeypatch)
    # No row yet on the first go: look again in a few seconds; on the second
    # go, nothing.
    missing = uuid.uuid4()
    speaker_check.run(missing)
    assert deferred == [
        ({"schedule_in": {"seconds": 5}}, {"check_id": str(missing), "attempt": 2})
    ]
    speaker_check.run(missing, attempt=2)
    assert len(deferred) == 1
    # A check left queued for two minutes with no task is queued again by the
    # minute sweep; a fresh one, or one with a task, is left alone.
    recording = a_recording(admin, tmp_path, settings)
    check = SpeakerCheck.objects.create(transcript=recording.transcript)
    monkeypatch.setattr(speaker_check, "task_waiting_for", lambda one: False)
    assert speaker_check.queued_without_a_task() == []
    SpeakerCheck.objects.filter(pk=check.pk).update(
        created=timezone.now() - dt.timedelta(minutes=5)
    )
    assert [one.pk for one in speaker_check.queued_without_a_task()] == [check.pk]
    monkeypatch.setattr(speaker_check, "task_waiting_for", lambda one: True)
    assert speaker_check.queued_without_a_task() == []
    monkeypatch.setattr(speaker_check, "task_waiting_for", lambda one: False)
    del deferred[:]
    from core import uploads

    monkeypatch.setattr(uploads, "drop_abandoned", lambda: 0)
    tasks.keep_the_queue_moving(0)
    assert deferred == [({}, {"check_id": str(check.pk)})]


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


def test_the_sketch_is_in_the_glossary_and_the_guide():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent.parent
    glossary = (root / "CONTEXT.md").read_text(encoding="utf-8")
    guide = (root / "docs" / "user-guide.md").read_text(encoding="utf-8")
    assert "**Sketch**:" in glossary
    assert "writes a sketch of who is who" in guide
    # Off the page since v1.129.0.
    assert "**Who is who, as the check read it**" not in guide
    assert "—" not in prompts.SPEAKER_SKETCH + prompts.SPEAKER_SKETCH_USE


@pytest.mark.django_db
def test_a_merge_settles_the_corrections_it_fulfils_and_undo_puts_them_back(
    admin, tmp_path, settings, client
):
    """v1.129.0: a yes on a speaker question is the page's merge, and the
    pending corrections follow it: the ones it fulfils are accepted, one
    that proposed another speaker for a merged line keeps its proposal
    under the new label, one that proposed the merged-away label now
    proposes the surviving one, and a proposal made moot is dismissed.
    Undo puts every one of them back. A rename is followed the same way."""
    switched_on()
    recording = a_recording(admin, tmp_path, settings)
    transcript = recording.transcript
    # Lines at 0 (Speaker 1), 12.4 (Speaker 2), 724 (Speaker 1).
    Segment.objects.create(
        transcript=transcript,
        start=400.0,
        end=403.0,
        text="And then he said no.",
        speaker="Speaker 3",
        speaker_label="SPEAKER_3",
    )

    def row(start, was, to):
        return SpeakerCorrection.objects.create(
            transcript=transcript,
            segment=Segment.objects.get(start=start),
            start=start,
            speaker_from=was,
            speaker_to=to,
        )

    fulfilled = row(12.4, "Speaker 2", "Speaker 1")
    kept = row(12.4, "Speaker 2", "Speaker 3")
    retargeted = row(400.0, "Speaker 3", "Speaker 2")
    moot = row(0.0, "Speaker 1", "Speaker 2")
    signed_in(client, admin)
    answer = client.post(
        f"/recording/{recording.pk}/speakers",
        {"from": "Speaker 2", "to": "Speaker 1"},
        content_type="application/json",
    ).json()
    assert answer["merged"] is True and answer["settled"] == 1
    for one in (fulfilled, kept, retargeted, moot):
        one.refresh_from_db()
    assert fulfilled.state == SpeakerCorrection.ACCEPTED
    assert fulfilled.decided_by_id == admin.pk
    assert (kept.state, kept.speaker_from, kept.speaker_to) == (
        SpeakerCorrection.PENDING,
        "Speaker 1",
        "Speaker 3",
    )
    assert (retargeted.state, retargeted.speaker_from, retargeted.speaker_to) == (
        SpeakerCorrection.PENDING,
        "Speaker 3",
        "Speaker 1",
    )
    assert (moot.state, moot.speaker_to) == (SpeakerCorrection.DISMISSED, "Speaker 1")
    # The kept and the retargeted are still live: their lines carry the label.
    live = {str(one.pk) for one in speaker_check.live_rows(transcript)}
    assert live == {str(kept.pk), str(retargeted.pk)}
    assert speaker_check.score(transcript) == {"accepted": 1, "dismissed": 1}
    row_ = Row.objects.get(event="Speakers merged")
    assert row_.details["corrections_settled"] == 2
    assert "Speaker" not in json.dumps(row_.details)
    # Undo puts the lines and the corrections back.
    undone = client.post(f"/recording/{recording.pk}/speakers/undo").json()
    assert undone["restored"] == 1
    for one in (fulfilled, kept, retargeted, moot):
        one.refresh_from_db()
        assert one.state == SpeakerCorrection.PENDING and one.decided_by_id is None
    assert (kept.speaker_from, kept.speaker_to) == ("Speaker 2", "Speaker 3")
    assert (retargeted.speaker_from, retargeted.speaker_to) == (
        "Speaker 3",
        "Speaker 2",
    )
    assert (moot.speaker_from, moot.speaker_to) == ("Speaker 1", "Speaker 2")
    assert len(speaker_check.live_rows(transcript)) == 4
    # A rename carries every correction's labels with it, and Undo back.
    client.post(
        f"/recording/{recording.pk}/speakers",
        {"from": "Speaker 2", "to": "Pat"},
        content_type="application/json",
    )
    fulfilled.refresh_from_db()
    retargeted.refresh_from_db()
    assert fulfilled.speaker_from == "Pat" and retargeted.speaker_to == "Pat"
    assert len(speaker_check.live_rows(transcript)) == 4
    client.post(f"/recording/{recording.pk}/speakers/undo")
    fulfilled.refresh_from_db()
    assert fulfilled.speaker_from == "Speaker 2"
    assert len(speaker_check.live_rows(transcript)) == 4
