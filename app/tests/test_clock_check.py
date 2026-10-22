"""The clock verdict (ADR 0022, v1.151.0): the transcript's clock against the
audio's pauses. The three rules on made-up lines, the marks written as a
transcript lands and given later to one that never had them, the window
every player reads, the samples and the voice step leaving marked lines
out, and the pages carrying the mark."""

from __future__ import annotations

from pathlib import Path

import pytest
from core import clock_check, speakers_page, voices
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


@pytest.fixture
def owner(db):
    return User.objects.create_local_admin("adm", PASSWORD)


def a_call(owner, tmp_path, settings, quiet=QUIET, monkeypatch=None):
    recording = a_recording(owner, tmp_path, settings, title="Call", video=False)
    Side.objects.create(recording=recording, number=1)
    transcript = recording.transcript
    transcript.segments.all().delete()
    for start, end, speaker in LINES:
        Segment.objects.create(
            transcript=transcript,
            start=start,
            end=end,
            text="words here",
            speaker=speaker,
            speaker_label=speaker.upper().replace(" ", "_"),
        )
    if monkeypatch is not None:
        monkeypatch.setattr(clock_check, "_measure", lambda path: quiet)
    return recording


def test_landing_marks_the_lines_and_writes_the_counts(
    owner, tmp_path, settings, monkeypatch
):
    recording = a_call(owner, tmp_path, settings, monkeypatch=monkeypatch)
    transcript = recording.transcript
    clock_check.on_landed(transcript)
    marked = list(transcript.segments.exclude(clock=None).order_by("start"))
    assert len(marked) == 6 and marked[0].start == 125.0
    assert marked[0].clock["bound"] == 15.8 and marked[0].clock["block"] == marked[0].pk
    transcript.refresh_from_db()
    counts = transcript.provenance["clock_check"]
    assert counts["measured"] and counts["marked"] == 6 and counts["blocks"] == 1
    # The window every player reads: wider on a marked line, half a second
    # either side on a sure one.
    assert clock_check.window(marked[0]) == (124.5, 158.4)
    sure = transcript.segments.get(start=95.0)
    assert clock_check.window(sure) == (94.5, 97.5)
    shown = clock_check.verdict_json(marked[0])
    assert shown["head"] and shown["about"] == 140.8 and shown["play_to"] == 158.4
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


def test_marked_lines_are_never_samples_nor_measured_by_the_voice(
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


def test_the_scripts_and_the_styles_carry_the_marks():
    viewer = (HERE / "static" / "viewer.js").read_text(encoding="utf-8")
    assert "segment.clock" in viewer and "clock-pill" in viewer
    assert "clock unsure · up to" in viewer and "heard about" in viewer
    guided = (HERE / "static" / "speakers-guided.js").read_text(encoding="utf-8")
    for piece in (
        "function verdictOf(",
        "function stripHtml(",
        "heard about",
        "this line’s clock is unsure, so the voice did not measure it",
        "play_from",
        "play_to",
    ):
        assert piece in guided, piece
    css = (HERE / "static" / "app.css").read_text(encoding="utf-8")
    assert ".seg.unsure" in css and ".sg-strip" in css and ".sg-ctx-line.unsure" in css
    queue = (HERE / "core" / "queue.py").read_text(encoding="utf-8")
    assert "clock_check.on_landed(transcript)" in queue
    check = (HERE / "core" / "speaker_check.py").read_text(encoding="utf-8")
    assert "clock_check.mark_if_missed(transcript)" in check
