"""The clock verdict (ADR 0022, v1.151.0) and the clock re-read (ADR 0023,
v1.152.0): the three rules on made-up lines, the squeeze, the marks written
as a transcript lands and given later to one that never had them, the
window every player reads, the samples and the voice step leaving unsure
lines out and taking re-timed ones back, the matching of a second reading
to the lines, the pass through the service, and the pages carrying the
marks."""

from __future__ import annotations

from pathlib import Path

import pytest
from core import audit, clock_check, speakers_page, tasks, voices
from core.jobs import Segment
from core.models import User
from core.recordings import Side
from tests.helpers import signed_in
from tests.test_prepare import a_recording

HERE = Path(__file__).resolve().parents[1]
PASSWORD = "a-long-enough-password"

# The shape measured on the office's call: lines up to 1:44, a hole to 2:05
# that the audio fills, a block 2:05 to 2:22 with two lines over a pause,
# a hole to 2:38 that is mostly sound, then lines on.
LINES = (
    (95.0, 97.0, "Speaker 1"),
    (99.0, 103.8, "Speaker 2"),
    (125.0, 125.8, "Speaker 1"),
    (125.8, 133.6, "Speaker 2"),
    (133.7, 135.8, "Speaker 2"),
    (136.2, 137.8, "Speaker 1"),
    (138.1, 141.2, "Speaker 2"),
    (141.3, 142.1, "Speaker 2"),
    (157.9, 161.0, "Speaker 1"),
    (161.0, 166.1, "Speaker 2"),
)
# The audio's pauses: short turn pauses, two of them inside the block's lines.
QUIET = [(91.5, 93.1), (129.4, 131.0), (134.1, 135.4), (155.1, 157.0), (161.1, 163.2)]
# The words of the block's lines, so a second reading can be matched.
WORDS = {
    125.0: "is it cold down there",
    125.8: (
        "hey man back when you were nineteen or twenty I never heard you say "
        "it was cold"
    ),
    133.7: "no it was not that bad",
    136.2: "you sure about that",
    138.1: "yeah I am sure we had the heat on all night long",
    141.3: "all right then",
}


def rows():
    return [clock_check.Row(i + 1, s, e) for i, (s, e, _) in enumerate(LINES)]


def test_the_three_rules_mark_the_early_block_and_nothing_else():
    verdict = clock_check.judge(rows(), QUIET)
    # One hole after the block (2:22 to 2:38) counts; the hole before it
    # (1:44 to 2:05) is sound too but no block with a pause inside sits
    # before it, so the lines before it are left alone.
    assert verdict["holes"] == 2 and verdict["blocks"] == 1
    marked = verdict["marks"]
    assert set(marked) == {3, 4, 5, 6, 7, 8}
    one = marked[3]
    assert one["bound"] == 15.8 and one["to"] == 157.9 and one["block"] == 3
    assert one["hole"] == [142.1, 157.9]
    # Rule 2 alone: a line over a pause.
    assert clock_check.spans_a_pause(clock_check.Row(4, 125.8, 133.6), QUIET)
    assert not clock_check.spans_a_pause(clock_check.Row(1, 95.0, 97.0), QUIET)
    # A short line over a pause is not judged; a pause at the very edge is
    # not inside the line.
    assert not clock_check.spans_a_pause(clock_check.Row(9, 129.0, 130.5), QUIET)
    # Rule 1 alone: a hole the audio does not fill is not a hole.
    silent = [(142.1, 157.9)]
    assert clock_check.judge(rows(), silent)["holes"] == 1  # only the first gap
    # The same lines with no pauses measured: nothing is marked.
    assert clock_check.judge(rows(), [])["marks"] == {}


def test_the_squeeze_marks_only_the_lines_inside_the_recognisers_window():
    """v1.152.0: a long block before a hole is marked only in its last
    forty-five seconds, from the hole's end back, and the line over a pause
    must be among them."""
    long_block = [
        clock_check.Row(i + 1, 10.0 + 10 * i, 14.0 + 10 * i) for i in range(14)
    ]
    # Lines at 10, 20, ... 140; the last ends 144; a hole 144 to 160 the
    # audio fills; then a line on.
    long_block.append(clock_check.Row(99, 160.0, 164.0))
    quiet = [(131.0, 132.6)]  # inside the line 130 to 134
    verdict = clock_check.judge(long_block, quiet)
    assert verdict["holes"] == 1 and verdict["blocks"] == 1
    # 160 - 45 = 115: the lines at 120, 130 and 140, the first of them the head.
    assert set(verdict["marks"]) == {12, 13, 14}
    assert verdict["marks"][13]["block"] == 12
    assert verdict["marks"][12]["bound"] == 16.0
    # The pause outside the window: the block is not marked at all.
    assert clock_check.judge(long_block, [(51.0, 52.6)])["marks"] == {}
    # A re-timed mark no longer means doubt; an unsure one does.
    assert clock_check.unsure({"bound": 16.0, "block": 12})
    assert not clock_check.unsure({"bound": 16.0, "block": 12, "retimed": True})
    assert not clock_check.unsure(None)


def test_the_window_is_cut_into_pieces_at_the_pauses():
    """v1.152.1: a piece a few seconds long cannot carry words across a
    pause, so the recogniser's rough stamps cannot trap them."""
    # No pause inside: one piece, or shared evenly when long.
    assert clock_check.pieces_of(10.0, 18.0, []) == [(10.0, 18.0)]
    assert clock_check.pieces_of(10.0, 40.0, []) == [
        (10.0, 20.0),
        (20.0, 30.0),
        (30.0, 40.0),
    ]
    # Cut at the middle of each pause; a pause at the very edge is not used;
    # a long piece between two pauses is shared evenly.
    assert clock_check.pieces_of(10.0, 30.0, [(14.0, 16.0), (29.5, 31.0)]) == [
        (10.0, 15.0),
        (15.0, 22.5),
        (22.5, 30.0),
    ]
    # A piece too short joins the one before it.
    assert clock_check.pieces_of(10.0, 30.0, [(13.0, 14.0), (14.6, 15.4)]) == [
        (10.0, 15.0),
        (15.0, 22.5),
        (22.5, 30.0),
    ]


@pytest.fixture
def owner(db):
    return User.objects.create_local_admin("adm", PASSWORD)


def a_call(owner, tmp_path, settings, quiet=QUIET, monkeypatch=None):
    recording = a_recording(owner, tmp_path, settings, title="Call", video=False)
    Side.objects.create(recording=recording, number=1)
    transcript = recording.transcript
    transcript.segments.all().delete()
    for start, end, speaker in LINES:
        words = WORDS.get(start, "words here")
        timed = []
        count = len(words.split())
        for i, piece in enumerate(words.split()):
            timed.append(
                {
                    "word": piece,
                    "start": round(start + (end - start) * i / count, 3),
                    "end": round(start + (end - start) * (i + 1) / count, 3),
                }
            )
        Segment.objects.create(
            transcript=transcript,
            start=start,
            end=end,
            text=words,
            words=timed,
            speaker=speaker,
            speaker_label=speaker.upper().replace(" ", "_"),
        )
    if monkeypatch is not None:
        monkeypatch.setattr(clock_check, "_measure", lambda path: quiet)
        # The re-read is asked for through the task queue; the tests that
        # want it call ask() themselves.
        monkeypatch.setattr(clock_check, "_ask_later", lambda transcript: None)
    return recording


def test_landing_marks_the_lines_and_writes_the_counts(
    owner, tmp_path, settings, monkeypatch
):
    recording = a_call(owner, tmp_path, settings, monkeypatch=monkeypatch)
    transcript = recording.transcript
    asked = []
    monkeypatch.setattr(clock_check, "_ask_later", lambda t: asked.append(t.pk))
    clock_check.on_landed(transcript)
    marked = list(transcript.segments.exclude(clock=None).order_by("start"))
    assert len(marked) == 6 and marked[0].start == 125.0
    assert marked[0].clock["bound"] == 15.8 and marked[0].clock["block"] == marked[0].pk
    transcript.refresh_from_db()
    counts = transcript.provenance["clock_check"]
    assert counts["measured"] and counts["marked"] == 6 and counts["blocks"] == 1
    # The re-read was asked for, once, because something was marked.
    assert asked == [transcript.pk]
    # The window every player reads: wider on a marked line, half a second
    # either side on a sure one.
    assert clock_check.window(marked[0]) == (124.5, 158.4)
    sure = transcript.segments.get(start=95.0)
    assert clock_check.window(sure) == (94.5, 97.5)
    shown = clock_check.verdict_json(marked[0])
    assert shown["head"] and shown["about"] == 140.8 and shown["play_to"] == 158.4
    assert shown["retimed"] is False and shown["unplaced"] is False
    assert clock_check.verdict_json(sure) is None
    # Given once: a transcript that was measured is left alone later.
    assert clock_check.mark_if_missed(transcript) is None
    # A failure inside never fails the landing.
    monkeypatch.setattr(clock_check, "mark", lambda t: 1 / 0)
    clock_check.on_landed(transcript)


def test_the_pass_given_later_and_the_audio_not_on_disk(
    owner, tmp_path, settings, monkeypatch
):
    recording = a_call(owner, tmp_path, settings)
    transcript = recording.transcript
    monkeypatch.setattr(clock_check, "_ask_later", lambda transcript: None)
    # The prepared audio gone: nothing written, so a later pass may still come.
    monkeypatch.setattr(clock_check, "_measure", lambda path: None)
    assert clock_check.mark(transcript)["measured"] is False
    transcript.refresh_from_db()
    assert "clock_check" not in (transcript.provenance or {})
    # Later, with the audio there: the pass a check's run gives first.
    monkeypatch.setattr(clock_check, "_measure", lambda path: QUIET)
    counts = clock_check.mark_if_missed(transcript)
    assert counts["marked"] == 6
    # Measured and nothing marked is still measured, and still once.
    other = a_call(owner, tmp_path, settings, monkeypatch=monkeypatch, quiet=[])
    counts = clock_check.mark(other.transcript)
    assert counts["measured"] and counts["marked"] == 0
    assert clock_check.mark_if_missed(other.transcript) is None
    # Nothing marked: no re-read is asked for.
    asked = []
    monkeypatch.setattr(clock_check, "_ask_later", lambda t: asked.append(t.pk))
    third = a_call(owner, tmp_path, settings, monkeypatch=monkeypatch, quiet=[])
    monkeypatch.setattr(clock_check, "_ask_later", lambda t: asked.append(t.pk))
    clock_check.mark(third.transcript)
    assert asked == []


def test_asking_later_defers_the_task_and_never_fails(
    owner, tmp_path, settings, monkeypatch
):
    recording = a_call(owner, tmp_path, settings)
    deferred = []
    monkeypatch.setattr(
        tasks.reread_clock, "defer", lambda **fields: deferred.append(fields)
    )
    clock_check._ask_later(recording.transcript)
    assert deferred == [{"transcript_id": str(recording.transcript.pk)}]
    monkeypatch.setattr(tasks.reread_clock, "defer", lambda **fields: 1 / 0)
    clock_check._ask_later(recording.transcript)  # logged, not raised


def test_unsure_lines_are_never_samples_nor_measured_by_the_voice(
    owner, tmp_path, settings, monkeypatch
):
    recording = a_call(owner, tmp_path, settings, monkeypatch=monkeypatch)
    transcript = recording.transcript
    clock_check.on_landed(transcript)
    # The voice step's stretches leave the marked lines out.
    by_side = voices.stretches_of(transcript)
    asked = {int(one["id"]) for rows_ in by_side.values() for one in rows_}
    marked = set(transcript.segments.exclude(clock=None).values_list("id", flat=True))
    assert asked and not (asked & marked)
    # The samples come from the sure lines, and the card counts the rest.
    cards = speakers_page.cards(
        transcript, [{"name": "Speaker 1"}, {"name": "Speaker 2"}]
    )
    for card in cards:
        assert all(one["id"] not in marked for one in card["samples"])
    by_name = {card["name"]: card for card in cards}
    assert by_name["Speaker 2"]["unsure"] == 4 and by_name["Speaker 1"]["unsure"] == 2
    samples = speakers_page.samples_for(transcript, "Speaker 2")
    assert samples and all(one["id"] not in marked for one in samples)


# The second reading of the block's window (ADR 0023) -------------------------

# The service's reading of the cut from 124.0 (a second before the first
# marked line) to 158.4: the same words, where the audio has them. The
# first line is heard eight seconds late, the long one sixteen, as on the
# office's call.
LONG_SAID = "Hey man, back when you were 19 or 20 I never heard you say it was cold."
READING = {
    "segments": [
        {
            "start": 9.0,
            "end": 10.1,
            "text": "Is it cold down there?",
            "words": [
                {"word": "Is", "start": 9.0, "end": 9.2},
                {"word": "it", "start": 9.2, "end": 9.4},
                {"word": "cold", "start": 9.4, "end": 9.7},
                {"word": "down", "start": 9.7, "end": 9.9},
                {"word": "there?", "start": 9.9, "end": 10.1},
            ],
        },
        {
            "start": 17.8,
            "end": 25.0,
            "text": LONG_SAID,
            "words": [
                {
                    "word": w,
                    "start": round(17.8 + i * 0.45, 2),
                    "end": round(18.2 + i * 0.45, 2),
                }
                for i, w in enumerate(LONG_SAID.split())  # noqa: SIM905
            ],
        },
        {
            "start": 26.0,
            "end": 28.0,
            "text": "No, it was not that bad.",
            "words": [
                {
                    "word": w,
                    "start": round(26.0 + i * 0.3, 2),
                    "end": round(26.25 + i * 0.3, 2),
                }
                for i, w in enumerate("No, it was not that bad.".split())  # noqa: SIM905
            ],
        },
        # The next two lines are not in the reading at all (the service
        # heard something else there), so they stay unplaced.
        {
            "start": 29.0,
            "end": 31.0,
            "text": "something quite different here",
            "words": [],
        },
        {
            "start": 32.5,
            "end": 33.4,
            "text": "All right then.",
            "words": [],  # no word times: the span is shared among the words
        },
    ]
}


def test_the_reading_is_matched_to_the_lines_and_places_them():
    heard = clock_check.heard_words(READING, 124.0)
    # Timed words carry their own times; untimed ones share the span.
    assert heard[0] == ("is", 133.0, 133.2)
    shared = [one for one in heard if one[0] in ("all", "right", "then")]
    assert [round(one[1], 2) for one in shared] == [156.5, 156.8, 157.1]
    lines = [clock_check.Row(i + 1, s, e) for i, (s, e, _) in enumerate(LINES[2:8])]
    texts = {i + 1: WORDS[LINES[2 + i][0]] for i in range(6)}
    placed = clock_check.place(lines, texts, heard)
    # The short first line moves eight seconds, the long one sixteen.
    assert placed[1] == (133.0, 134.1)
    assert placed[2][0] == 141.8 and placed[2][1] == pytest.approx(149.4, abs=0.1)
    assert placed[3] == (150.0, 151.75)
    # Half the words at least: "you sure about that" against nothing is
    # unplaced, and so is the line whose words the reading never had.
    assert placed[4] is None and placed[5] is None
    # "all right then", untimed in the reading, from the shared span.
    assert placed[6] == (156.5, 157.4)
    # Nothing matched: everything unplaced, nothing raised.
    assert all(v is None for v in clock_check.place(lines, texts, []).values())
    # Words found with their times out of order (an aligner's oddity) still
    # place the lines in order: no line starts before the one above it ends.
    swapped = [clock_check.Row(1, 0.0, 1.0), clock_check.Row(2, 1.0, 2.0)]
    heard2 = [("one", 11.0, 11.5), ("two", 10.0, 10.5)]
    got = clock_check.place(swapped, {1: "one", 2: "two"}, heard2)
    assert got[1] == (11.0, 11.5) and got[2] == (11.5, 12.5)
    assert clock_check.tokens("Hey, man! It's 19.") == ["hey", "man", "its", "19"]


def test_retime_moves_the_lines_and_keeps_everything_else(
    owner, tmp_path, settings, monkeypatch
):
    recording = a_call(owner, tmp_path, settings, monkeypatch=monkeypatch)
    transcript = recording.transcript
    clock_check.on_landed(transcript)
    head = transcript.segments.get(start=125.0)
    heard = clock_check.heard_words(READING, 124.0)
    counts = clock_check.retime(transcript, head.pk, heard)
    assert counts == {"retimed": 4, "unplaced": 2}
    head.refresh_from_db()
    assert head.start == 133.0 and head.end == 134.1
    assert head.clock["retimed"] is True and head.clock["was"] == [125.0, 125.8]
    assert head.clock["shift"] == 8.0 and head.clock["block"] == head.pk
    # The words moved with the line and stay inside it; the text, the
    # speaker and the label are as they were.
    assert head.text == WORDS[125.0] and head.speaker == "Speaker 1"
    assert all(133.0 <= w["start"] <= w["end"] <= 134.1 for w in head.words)
    long = transcript.segments.get(clock__was__0=125.8)
    assert long.start == 141.8 and long.clock["shift"] == 16.0
    unplaced = transcript.segments.get(start=136.2)
    assert unplaced.clock["unplaced"] is True and not unplaced.clock.get("retimed")
    # The verdict the pages read: re-read with the clock it had; unplaced
    # still unsure and saying so; the player's window back to the edges.
    shown = clock_check.verdict_json(head)
    assert shown["retimed"] and shown["was"] == 125.0 and shown["head"]
    assert shown["play_from"] == 132.5 and shown["play_to"] == 134.6
    assert clock_check.window(head) == (132.5, 134.6)
    left = clock_check.verdict_json(unplaced)
    assert left["unplaced"] and not left["retimed"] and left["play_to"] == 158.4
    # A re-timed line is a sure line: the voice measures it, it may be a sample.
    by_side = voices.stretches_of(transcript)
    asked = {int(one["id"]) for rows_ in by_side.values() for one in rows_}
    assert head.pk in asked and long.pk in asked and unplaced.pk not in asked
    cards = speakers_page.cards(transcript, [{"name": "Speaker 2"}])
    assert cards[0]["unsure"] == 1
    # Done once: a second landing of the same window finds nothing to move.
    assert clock_check.retime(transcript, head.pk, heard) == {
        "retimed": 0,
        "unplaced": 2,
    }
    # The windows still to re-read: none, the block's unplaced lines stay.
    assert clock_check.windows_of(transcript) == []


def test_the_pass_through_the_service(owner, tmp_path, settings, monkeypatch):
    from core import whisperx

    recording = a_call(owner, tmp_path, settings, monkeypatch=monkeypatch)
    transcript = recording.transcript
    clock_check.on_landed(transcript)
    side = recording.sides.get()
    side.asr_path.parent.mkdir(parents=True, exist_ok=True)
    side.asr_path.write_bytes(b"RIFF....WAVE")
    # One window: a second before the first marked line to half a second
    # after the hole's end.
    windows = clock_check.windows_of(transcript)
    assert len(windows) == 1
    assert windows[0]["from"] == 124.0 and windows[0]["to"] == 158.4
    # The window is read in pieces cut at the audio's pauses (v1.152.1):
    # the three pauses inside it, the long piece shared in two.
    head = windows[0]["head"]
    assert clock_check.pieces_of(124.0, 158.4, QUIET) == [
        (124.0, 130.2),
        (130.2, 134.75),
        (134.75, 145.4),
        (145.4, 156.05),
        (156.05, 158.4),
    ]
    cuts = {}

    def cut(src, dst, a, b):
        cuts[dst.name] = (a, b)
        return True

    monkeypatch.setattr(clock_check, "_cut", cut)
    sent = []
    pieces = {}

    def submit(audio, request, lane=""):
        sent.append(request)
        pieces[f"svc-{len(sent)}"] = cuts[audio.name]
        return whisperx.Submitted(
            id=f"svc-{len(sent)}", position=0, audio_minutes_ahead=0.0
        )

    def reading_of(job_id, lane=""):
        # The reading of one piece: the words of READING that fall in it,
        # with times from the piece's own start.
        a, b = pieces[job_id]
        out = []
        for segment in READING["segments"]:
            start = 124.0 + float(segment["start"])
            if not (a <= start < b):
                continue
            moved = dict(segment)
            moved["start"] = round(start - a, 3)
            moved["end"] = round(124.0 + float(segment["end"]) - a, 3)
            moved["words"] = [
                {
                    **w,
                    "start": round(124.0 + w["start"] - a, 3),
                    "end": round(124.0 + w["end"] - a, 3),
                }
                for w in segment["words"]
            ]
            out.append(moved)
        return {"segments": out}

    monkeypatch.setattr(whisperx, "submit", submit)
    monkeypatch.setattr(whisperx, "lane_for", lambda recording: "")
    state = clock_check.ask(transcript)
    assert state["state"] == "waiting"
    assert list(state["jobs"]) == [f"{head}:{i}" for i in range(5)]
    assert cuts[f"{head}-0.wav"] == (124.0, 130.2)
    assert cuts[f"{head}-4.wav"] == (156.05, 158.4)
    request = sent[0]
    assert request["task"] == "transcribe" and request["diarize"] is False
    assert request["language"] == "en" and request["priority"] == 90
    assert request["fit_words_over_whole"] is True
    assert request["client_reference"].startswith(f"clock-{transcript.pk}-")
    transcript.refresh_from_db()
    assert transcript.provenance["clock_check"]["reread"]["state"] == "waiting"
    # Still running at the service: waiting on.
    monkeypatch.setattr(
        whisperx, "status_of", lambda job_id, lane="": {"state": "running"}
    )  # noqa: E501
    assert clock_check.poll(transcript)["state"] == "waiting"
    # Done: the reading lands, the job is deleted, the row is written.
    monkeypatch.setattr(
        whisperx, "status_of", lambda job_id, lane="": {"state": "done"}
    )  # noqa: E501
    monkeypatch.setattr(whisperx, "result", reading_of)
    deleted = []
    monkeypatch.setattr(
        whisperx, "delete", lambda job_id, lane="": deleted.append(job_id)
    )
    state = clock_check.poll(transcript)
    assert state["state"] == "done" and state["retimed"] == 4 and state["unplaced"] == 2
    assert sorted(deleted) == [f"svc-{i}" for i in range(1, 6)]
    row = audit.Row.objects.get(event="Clock re-read")
    assert row.details["lines_changed"] == 4 and row.details["lines_left"] == 2
    assert row.details["windows"] == 1 and row.details["pieces"] == 5
    assert transcript.segments.get(start=133.0).clock["retimed"] is True
    # Polled again when done: nothing changes.
    assert clock_check.poll(transcript)["state"] == "done"
    # The clock a line first had is kept through a second re-read.
    moved = transcript.segments.get(start=133.0)
    later = [
        (w, t + 1.0, e + 1.0) for w, t, e in clock_check.heard_words(READING, 124.0)
    ]
    clock_check.retime(transcript, head, later)
    moved.refresh_from_db()
    assert moved.start == 133.0 and moved.clock["was"] == [125.0, 125.8]
    # A window the service lost fails the pass, and the marks stay.
    other = a_call(owner, tmp_path, settings, monkeypatch=monkeypatch)
    clock_check.on_landed(other.transcript)
    other_side = other.sides.get()
    other_side.asr_path.parent.mkdir(parents=True, exist_ok=True)
    other_side.asr_path.write_bytes(b"RIFF....WAVE")
    clock_check.ask(other.transcript)
    monkeypatch.setattr(whisperx, "status_of", lambda job_id, lane="": None)
    state = clock_check.poll(other.transcript)
    assert state["state"] == "failed"
    assert other.transcript.segments.filter(clock__retimed=True).count() == 0
    assert other.transcript.segments.exclude(clock=None).count() == 6
    # Nothing to send (the audio gone): failed, and said so.
    third = a_call(owner, tmp_path, settings, monkeypatch=monkeypatch)
    clock_check.on_landed(third.transcript)
    assert clock_check.ask(third.transcript)["state"] == "failed"


def test_the_tasks_ask_and_poll_and_ask_again(owner, tmp_path, settings, monkeypatch):
    recording = a_call(owner, tmp_path, settings, monkeypatch=monkeypatch)
    pk = str(recording.transcript.pk)
    later = []

    class Later:
        def __init__(self, **options):
            self.options = options

        def defer(self, **fields):
            later.append((self.options, fields))

    monkeypatch.setattr(
        tasks.poll_reread, "configure", lambda **options: Later(**options)
    )  # noqa: E501
    monkeypatch.setattr(clock_check, "ask", lambda t: {"state": "waiting"})
    tasks.reread_clock(transcript_id=pk)
    assert later == [({"schedule_in": {"seconds": 10}}, {"transcript_id": pk})]
    monkeypatch.setattr(clock_check, "poll", lambda t: {"state": "waiting"})
    tasks.poll_reread(transcript_id=pk)
    assert len(later) == 2
    monkeypatch.setattr(clock_check, "poll", lambda t: {"state": "done"})
    tasks.poll_reread(transcript_id=pk)
    assert len(later) == 2
    # A transcript that is gone: nothing asked, nothing raised.
    tasks.reread_clock(transcript_id="00000000-0000-0000-0000-000000000000")
    tasks.poll_reread(transcript_id="00000000-0000-0000-0000-000000000000")


def test_the_pages_carry_the_verdict(owner, tmp_path, settings, monkeypatch, client):
    recording = a_call(owner, tmp_path, settings, monkeypatch=monkeypatch)
    transcript = recording.transcript
    clock_check.on_landed(transcript)
    signed_in(client, owner)
    told = client.get(f"/recording/{recording.pk}/segments?words=0").json()
    marked = [one for one in told["segments"] if one["clock"]]
    assert len(marked) == 6 and marked[0]["clock"]["head"] is True
    assert marked[1]["clock"]["head"] is False
    assert all(one["clock"] is None for one in told["segments"] if one["start"] < 120)
    # The Preview's reading: the moment's verdict, the lines' verdicts, and
    # a speaker's samples when asked.
    around = client.get(
        f"/recording/{recording.pk}/around?t=125.8&speaker=Speaker%202"
    ).json()
    assert around["clock_verdict"]["bound"] == 15.8
    assert any(one["verdict"] for one in around["lines"])
    assert around["samples"]
    assert all(not (125 <= one["start"] < 143) for one in around["samples"])
    plain = client.get(f"/recording/{recording.pk}/around?t=95").json()
    assert plain["clock_verdict"] is None and plain["samples"] == []
    # After the re-read: the head line at its new clock, re-read, with the
    # clock it had; the Preview on it says so too.
    head = transcript.segments.get(start=125.0)
    clock_check.retime(transcript, head.pk, clock_check.heard_words(READING, 124.0))
    told = client.get(f"/recording/{recording.pk}/segments?words=0").json()
    moved = next(one for one in told["segments"] if one["start"] == 133.0)
    assert moved["clock"]["retimed"] and moved["clock"]["was"] == 125.0
    assert moved["clock"]["head"] is True
    around = client.get(f"/recording/{recording.pk}/around?t=133").json()
    assert around["clock_verdict"]["retimed"]
    assert around["clock_verdict"]["was"] == 125.0


def test_the_scripts_and_the_styles_carry_the_marks():
    viewer = (HERE / "static" / "viewer.js").read_text(encoding="utf-8")
    assert "segment.clock" in viewer and "clock-pill" in viewer
    # Quiet on the page (v1.159.1): two words, the numbers in the hover.
    assert 'pill.textContent = "time uncertain"' in viewer and "heard about" in viewer
    assert "clock unsure · up to" not in viewer
    # The follow resumes at the player's own time (v1.159.1), so a click on a
    # line no longer pulls the page back to the line it had just left.
    assert "function resumeFollowing(time)" in viewer
    assert "window.VIEWER.resumeFollowing(wanted)" in viewer
    assert 'typeof time === "number" ? at(time)' in viewer
    # The re-read (v1.152.0).
    assert "clock re-read · was" in viewer and 'classList.add("retimed")' in viewer
    assert "not found by the re-read" in viewer
    guided = (HERE / "static" / "speakers-guided.js").read_text(encoding="utf-8")
    for piece in (
        "function verdictOf(",
        "function stripHtml(",
        "heard about",
        "this line’s clock is unsure, so the voice did not measure it",
        "play_from",
        "play_to",
        '" retimed"',
        "clock re-read, was",
    ):
        assert piece in guided, piece
    preview = (HERE / "static" / "preview.js").read_text(encoding="utf-8")
    assert "clock re-read · was" in preview and "verdict.retimed" in preview
    css = (HERE / "static" / "app.css").read_text(encoding="utf-8")
    assert ".seg.unsure" in css and ".sg-strip" in css and ".sg-ctx-line.unsure" in css
    assert ".seg.retimed" in css and ".sg-ctx-line.retimed" in css
    queue = (HERE / "core" / "queue.py").read_text(encoding="utf-8")
    assert "clock_check.on_landed(transcript)" in queue
    check = (HERE / "core" / "speaker_check.py").read_text(encoding="utf-8")
    assert "clock_check.mark_if_missed(transcript)" in check
