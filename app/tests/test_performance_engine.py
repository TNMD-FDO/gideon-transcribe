"""The performance pass over the engine's callers (v1.134.0).

The rules checked here: a rendered line's opening is counted at its real
cost, so a long transcript is no longer undercounted by a quarter; every
Reading of the Case Chat is checked as the whole request it will be; the
engine's one retry is sent only when the connection was never made or the
request is small; the Speaker check's whole read is given at most four
windows' time and never thinks; a window of the proposals lists only the
events near it; a report that fits beside the record is compared in one
window; the night hands over as many summaries as the setting allows and
a finished one starts the next; the picture record reads the lines and the
templates once and cuts each clip while the engine describes the one
before; and the reading goes ahead of the chat history.
"""

from __future__ import annotations

import math

import pytest
from core import (
    assistant,
    case_chat,
    comparison,
    engine,
    incident_assistant,
    prompts,
    settings_store,
    speaker_check,
    summaries_tonight,
)
from core.assistant import DONE, QUEUED, TONIGHT, CueRun, Moment, Summary
from tests.test_prepare import a_recording, engine_answering, no_ffmpeg
from tests.test_summaries_tonight import a_call, at


@pytest.fixture
def admin(db):
    from core.models import User

    return User.objects.create_local_admin("night", "a-long-enough-password")


@pytest.fixture
def deferred(monkeypatch):
    from core import tasks

    queued = []
    monkeypatch.setattr(
        tasks.write_summary, "defer", lambda **kw: queued.append(kw) or None
    )
    monkeypatch.setattr(engine, "is_reachable", lambda: True)
    return queued


def a_rendered_transcript(count: int = 3000) -> tuple[list, str]:
    lines = [
        prompts.Line(
            number=n,
            segment_id=n,
            start=float(n * 4),
            speaker=f"Speaker {1 + n % 2}",
            text="We were at the storage unit on Elm Street when the car came by.",
        )
        for n in range(1, count + 1)
    ]
    return lines, prompts.render(lines)


# The estimate (finding 12) ------------------------------------------------------------


def test_a_rendered_lines_opening_costs_eighteen_tokens():
    lines, rendered = a_rendered_transcript(3000)
    assert rendered.count("\n") == 2999
    openings = prompts.RENDERED_LINE.findall(rendered)
    assert len(openings) == 3000 and openings[-1] == "[3000] [03:20:00]"
    # The words at four characters a token with the margin, the openings at
    # eighteen apiece.
    opening_chars = sum(len(one) for one in openings)
    words = math.ceil((len(rendered) - opening_chars) * 11 / 40)
    assert prompts.tokens(rendered) == words + 3000 * prompts.LINE_PREFIX_TOKENS
    # About a quarter more than four characters a token said of the whole.
    plain = math.ceil(len(rendered) * 11 / 40)
    assert prompts.tokens(rendered) / plain > 1.2
    assert prompts.line_tokens(3000) == 54000
    # Plain text is counted as it was.
    assert prompts.tokens("a" * 400) == 110
    assert prompts.tokens("") == 0
    # A time in the middle of a line, or a report's paragraph, is not an opening.
    assert prompts.tokens("said at [00:01:00] and left") == math.ceil(27 * 11 / 40)
    assert prompts.RENDERED_LINE.findall("[Report, page 1, paragraph 2] It was") == []
    # An incident record's line, "camera: [time on the clock]", the same way
    # at fourteen: the memo's Sitting and the comparison size the record.
    record = "BWC2-1: [21:56:27] Speaker 1: Hands.\nBWC2-2: [21:56:30] Speaker 2: Ok."
    openings = prompts.RECORD_LINE.findall(record)
    assert openings == ["BWC2-1: [21:56:27]", "BWC2-2: [21:56:30]"]
    rest = len(record) - sum(len(one) for one in openings)
    assert prompts.tokens(record) == math.ceil(rest * 11 / 40) + 2 * 14


def test_every_fit_reads_the_same_estimate():
    _, rendered = a_rendered_transcript(3000)
    cost = prompts.tokens(rendered)
    assert prompts.fits(rendered, answer_cap=100, window=cost + 100)
    assert not prompts.fits(rendered, answer_cap=100, window=cost + 99)
    # Packed into Readings by the same count.
    assert case_chat.pack([(1, rendered), (2, rendered)], cost) == [[1], [2]]
    assert case_chat.pack([(1, rendered), (2, rendered)], 2 * cost) == [[1, 2]]


# The whole-request fit of every Reading (finding 12) ----------------------------------


def test_a_reading_that_does_not_fit_as_a_whole_request_moves_its_last_transcript():
    _, rendered = a_rendered_transcript(1000)
    texts = {n: rendered for n in range(1, 6)}
    one = prompts.tokens(rendered)
    system = "x" * 4000
    # Three transcripts fit a Reading by the Reading size alone; with the
    # system message, the question and the answer's room beside them, two.
    groups = case_chat.pack(list(texts.items()), 3 * one)
    assert groups == [[1, 2, 3], [4, 5]]
    window = prompts.tokens(system) + 2 * one + 200 + 500 + 10

    def fits(group):
        return prompts.fits(
            system,
            *(texts[n] for n in group),
            "the question",
            answer_cap=500,
            window=window,
            extra=200,
        )

    assert case_chat.regroup(groups, fits) == [[1, 2], [3, 4], [5]]
    # Nothing to move: a Reading of one is left for the caller's refusal.
    assert case_chat.regroup([[1], [2]], lambda group: False) == [[1], [2]]
    assert case_chat.regroup([[1, 2]], lambda group: False) == [[1], [2]]
    assert case_chat.regroup([], fits) == []
    # A Reading that fits is left as it is.
    assert case_chat.regroup([[1, 2], [3]], lambda group: True) == [[1, 2], [3]]


# The retry (finding 17) ------------------------------------------------------------


def _answer():
    class Message:
        content = "ready"

    class Choice:
        message = Message()
        finish_reason = "stop"

    class Usage:
        prompt_tokens = 10
        completion_tokens = 1

    class Answer:
        choices = [Choice()]
        usage = Usage()
        model = "the-model"

    return Answer()


def _client_failing_first(monkeypatch, failure):
    calls = []

    class Completions:
        def create(self, **request):
            calls.append(request)
            if len(calls) == 1:
                raise failure
            return _answer()

    class Chat:
        completions = Completions()

    class Client:
        chat = Chat()

    monkeypatch.setattr(engine, "client", lambda timeout: Client())
    monkeypatch.setattr(engine, "model_name", lambda: "the-model")
    return calls


def _call(messages):
    return engine.complete(
        messages,
        max_completion_tokens=10,
        temperature=0.0,
        top_p=1.0,
        thinking=False,
        timeout=5,
    )


def test_a_large_request_is_sent_again_only_when_the_connection_was_never_made(
    monkeypatch,
):
    import httpx
    from openai import APIConnectionError

    request = httpx.Request("POST", "http://engine.test/v1/chat/completions")
    large = [{"role": "user", "content": "w" * (engine.SMALL_REQUEST_TOKENS * 4 + 4)}]
    small = [{"role": "user", "content": "w" * 400}]
    # Never connected: tried once more, large or small.
    never = APIConnectionError(request=request)
    never.__cause__ = httpx.ConnectError("refused", request=request)
    calls = _client_failing_first(monkeypatch, never)
    assert _call(large)["text"] == "ready" and len(calls) == 2
    assert engine.retry_allowed(never, large) is True
    # Reset part-way through a large request: unreachable, not sent twice.
    reset = APIConnectionError(request=request)
    reset.__cause__ = httpx.ReadError("reset", request=request)
    calls = _client_failing_first(monkeypatch, reset)
    with pytest.raises(engine.Problem) as told:
        _call(large)
    assert told.value.reason == engine.UNREACHABLE and len(calls) == 1
    assert engine.retry_allowed(reset, large) is False
    # The same failure on a small request: tried once more.
    calls = _client_failing_first(monkeypatch, reset)
    assert _call(small)["text"] == "ready" and len(calls) == 2
    assert engine.retry_allowed(reset, small) is True


# The Speaker check (findings 18 and 23) --------------------------------------------


def test_the_whole_read_is_given_at_most_four_windows_time_and_never_thinks(
    monkeypatch, tmp_path, settings, db
):
    from core.models import User

    person = User.objects.create_local_admin("checker", "a-long-enough-password")
    settings_store.set_to("speaker_check_available", True)
    settings_store.set_to("assistant_thinks", True)
    # Two-minute windows over a transcript with a line every two minutes
    # for forty: twenty windows, read whole, so the one call would have had
    # twenty windows' time; it is given four.
    from core.jobs import Segment

    settings_store.set_to("speaker_check_window_seconds", 120)
    recording = a_recording(person, tmp_path, settings)
    for n in range(20):
        Segment.objects.create(
            transcript=recording.transcript,
            start=1000.0 + n * 120,
            end=1002.0 + n * 120,
            text="And then what?" if n % 2 else "We waited.",
            speaker="Speaker 1" if n % 2 else "Speaker 2",
            speaker_label="SPEAKER_1" if n % 2 else "SPEAKER_2",
        )
    check = speaker_check.queue_check(recording, by=person, how="asked")
    asked = engine_answering(monkeypatch, ["a sketch", '{"moves": []}'])
    speaker_check.run(check.pk)
    check.refresh_from_db()
    assert check.state == DONE and check.whole is True
    sketching, reading = asked
    sliced = len(speaker_check.windows(prompts.lines_of(recording.transcript), 120))
    assert sliced > speaker_check.WHOLE_READ_WINDOWS
    limit = assistant.time_limit(speaker_check.FEATURE)
    assert reading["timeout"] == limit * speaker_check.WHOLE_READ_WINDOWS
    assert sketching["timeout"] == limit
    # Thinking is on in the Panel; neither call thinks.
    assert sketching["thinking"] is False and reading["thinking"] is False


# The proposals' head (finding 19) ---------------------------------------------------


class _Event:
    def __init__(self, at, text, note=""):
        self.at, self.text, self.note = at, text, note


class _Camera:
    starts_at = 100.0


class _Incident:
    def has_clock(self):
        return False


def test_a_windows_head_lists_the_events_within_a_window_either_side():
    incident = _Incident()
    events = [
        _Event(50.0, "Before the camera started"),
        _Event(110.0, "At the start", note="checked"),
        _Event(1300.0, "In the second window"),
        _Event(2500.0, "Far on"),
    ]
    window = ["[00:10:00] Speaker 1: Step out.", "[00:19:59] Speaker 1: Hands."]
    span = incident_assistant._window_span(_Camera(), window, 600)
    assert span == (100.0 + 600 - 600, 100.0 + 1199 + 600)
    listed = incident_assistant._known(incident, events, [], within=span)
    assert listed == [
        "00:01:50 At the start (the office's note: checked)",
        "00:21:40 In the second window",
    ]
    # Without a span, every event, as before.
    assert len(incident_assistant._known(incident, events, [])) == 4
    # A window whose lines carry no time keeps the whole list.
    assert incident_assistant._window_span(_Camera(), ["no time here"], 600) is None


# The comparison's windows (finding 20) -----------------------------------------------


def test_the_report_is_compared_in_one_window_when_the_whole_fits():
    pages = [[{"page": 1, "n": 1, "text": "a"}], [{"page": 9, "n": 1, "text": "b"}]]
    whole = [pages[0][0], pages[1][0]]
    assert comparison._one_window_if_it_fits(pages, lambda rows: True) == [whole]
    assert comparison._one_window_if_it_fits(pages, lambda rows: False) == pages
    assert comparison._one_window_if_it_fits([pages[0]], lambda rows: False) == [
        pages[0]
    ]


# The night (finding 10) --------------------------------------------------------------


@pytest.mark.django_db
def test_the_tick_hands_over_the_settings_count_and_a_finished_one_starts_the_next(
    admin, tmp_path, settings, deferred, monkeypatch
):
    from core.cases import Case

    a_case = Case.objects.create(name="Night", owner=admin)
    calls = [a_call(admin, tmp_path, settings, a_case, f"Call {n}") for n in range(4)]
    for call in calls:
        summaries_tonight.on_transcript(call)
    settings_store.set_to("summaries_at_once_overnight", 3)
    assert summaries_tonight.at_once() == 3
    # One tick: three handed over, the oldest first, never more than waiting.
    assert summaries_tonight.mind_the_night("off", at(21)) == "queued"
    assert [one["summary_id"] for one in deferred] == [
        str(Summary.objects.get(recording=call).pk) for call in calls[:3]
    ]
    assert summaries_tonight.running_now() == 3
    assert summaries_tonight.mind_the_night("off", at(21, 1)) == "busy"
    # The first finishes inside the window: the fourth starts at once.
    first = Summary.objects.get(recording=calls[0])
    Summary.objects.filter(pk=first.pk).update(state=DONE)
    assert summaries_tonight.carry_on(at(21, 2)) == 1
    assert len(deferred) == 4
    assert Summary.objects.filter(recording=calls[3]).get().state == QUEUED
    # Nothing waiting: nothing handed over; outside the window: nothing.
    assert summaries_tonight.carry_on(at(21, 3)) == 0
    summaries_tonight.on_transcript(a_call(admin, tmp_path, settings, a_case, "Late"))
    assert summaries_tonight.carry_on(at(12)) == 0
    assert Summary.objects.filter(state=TONIGHT).count() == 1
    # The setting's ceiling is four.
    real_get = settings_store.get
    monkeypatch.setattr(
        settings_store,
        "get",
        lambda key: 9 if key == "summaries_at_once_overnight" else real_get(key),
    )
    assert summaries_tonight.at_once() == 4
    assert settings_store.DEFINITIONS["summaries_at_once_overnight"].most == 4


@pytest.mark.django_db
def test_write_summary_hands_the_next_of_the_night_over_as_it_finishes(
    admin, tmp_path, settings, deferred, monkeypatch
):
    from core.cases import Case

    a_case = Case.objects.create(name="Night", owner=admin)
    first = a_call(admin, tmp_path, settings, a_case, "Call 1")
    second = a_call(admin, tmp_path, settings, a_case, "Call 2")
    for call in (first, second):
        summaries_tonight.on_transcript(call)
    assert summaries_tonight.mind_the_night("off", at(21)) == "queued"
    assert len(deferred) == 1
    monkeypatch.setattr(summaries_tonight.vision, "in_window", lambda now=None: True)
    asked = engine_answering(monkeypatch, ["Overview:\nA call."])
    assistant.write_summary(Summary.objects.get(recording=first).pk)
    assert len(asked) == 1
    assert Summary.objects.get(recording=first).state == DONE
    # The second was handed over by the finish, not by a tick.
    assert len(deferred) == 2
    assert Summary.objects.get(recording=second).state == QUEUED


# The picture record (finding 21) ---------------------------------------------------


@pytest.mark.django_db
def test_the_record_reads_the_lines_once_and_cuts_each_clip_a_span_ahead(
    tmp_path, settings, monkeypatch
):
    from core import media
    from core.models import User

    person = User.objects.create_local_admin("asker", "a-long-enough-password")
    recording = a_recording(person, tmp_path, settings)
    transcript = recording.transcript
    settings_store.set_to("picture_record_available", True)
    settings_store.set_to("digests_available", False)
    no_ffmpeg(monkeypatch)
    import tempfile

    clips = tmp_path / "clips"
    clips.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(clips))
    cuts: list = []
    real_cut = media.cut_for_description

    def cut(source, target, start, end, **options):
        cuts.append((start, end))
        return real_cut(source, target, start, end, **options)

    monkeypatch.setattr(media, "cut_for_description", cut)
    read: list = []
    real_lines_of = prompts.lines_of
    monkeypatch.setattr(
        prompts, "lines_of", lambda one: read.append(one.pk) or real_lines_of(one)
    )
    asked = engine_answering(monkeypatch, [])
    run = CueRun.objects.create(
        transcript=transcript, source=CueRun.INTERVAL, asked_by=person
    )
    assistant.describe_intervals(run.pk)
    run.refresh_from_db()
    spans = list(
        Moment.objects.filter(transcript=transcript, source=Moment.INTERVAL)
        .order_by("at")
        .values_list("span_start", "span_end")
    )
    # One clip per span, each the span itself, each shown to the engine.
    assert run.state == DONE and run.total == len(spans) == run.found >= 2
    assert sorted(cuts) == spans and len(asked) == len(spans)
    # The lines read once for the run, not once per span.
    assert read == [transcript.pk]
    # No clip left behind.
    assert not list(clips.glob("moment-*.mp4"))
    # A clip cut ahead that failed fails its own span and no other.
    Moment.objects.filter(transcript=transcript).delete()

    def failing_cut(source, target, start, end, **options):
        if start == 0.0:
            raise media.MediaError("no frame", reason_class="media_failed")
        return real_cut(source, target, start, end, **options)

    monkeypatch.setattr(media, "cut_for_description", failing_cut)
    again = CueRun.objects.create(
        transcript=transcript, source=CueRun.INTERVAL, asked_by=person
    )
    assistant.describe_intervals(again.pk)
    again.refresh_from_db()
    assert again.found == len(spans) - 1
    assert not list(clips.glob("moment-*.mp4"))
    failed = Moment.objects.get(transcript=transcript, span_start=0.0)
    assert failed.state == "failed" and failed.reason_class == assistant.MEDIA_FAILED


# The order of the messages (finding 1) ------------------------------------------------


def test_the_reading_goes_at_the_end_of_the_system_message_ahead_of_the_history():
    messages = assistant._messages(
        "the rules",
        "the question",
        [("first?", "first answer")],
        reading="the transcript",
    )
    assert messages == [
        {"role": "system", "content": "the rules\n\nthe transcript"},
        {"role": "user", "content": "first?"},
        {"role": "assistant", "content": "first answer"},
        {"role": "user", "content": "the question"},
    ]
    # The shared prefix of two questions in one chat is the reading itself.
    second = assistant._messages(
        "the rules",
        "another question",
        [("first?", "first answer"), ("the question", "an answer")],
        reading="the transcript",
    )
    assert second[:3] == messages[:3]
    assert case_chat._messages("s", "q", [], reading="r") == assistant._messages(
        "s", "q", [], reading="r"
    )
    # Without a reading, as before.
    assert assistant._messages("s", "q") == [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "q"},
    ]
