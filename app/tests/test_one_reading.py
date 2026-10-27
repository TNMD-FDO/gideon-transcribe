"""One reading (Phase 9 chapter 6, v1.163.0): how full a case is.

The packing rule and the words run without a database. The rest: the share a
Transcript keeps and when it is counted again, the three states of the strip
on the case page and its pill, the drawer's head line and Readings count, and
what a question read under its answer.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest
from core import case_chat, one_reading, settings_store
from core.assistant import DONE, RUNNING, DigestPart
from core.case_chat import CaseChat, CaseChatTurn
from core.case_scope import NARROWED, OVERVIEWS, WHOLE
from core.cases import Case
from core.jobs import Segment, Transcript
from core.models import User
from core.recordings import Batch, MediaState, Recording
from django.utils import timezone
from tests.helpers import signed_in

PASSWORD = "a-long-enough-password"


# Without a database ----------------------------------------------------------------


def test_the_packing_rule_on_sizes_matches_the_case_chats():
    assert one_reading.pack_sizes([10, 10, 10], 100) == [[0, 1, 2]]
    assert one_reading.pack_sizes([60, 60, 60], 100) == [[0], [1], [2]]
    # An item larger than a Reading is alone in its own, in order.
    assert one_reading.pack_sizes([10, 500, 10], 100) == [[0], [1], [2]]
    assert one_reading.pack_sizes([], 100) == []


def test_hours_are_said_plainly():
    assert one_reading.hours_words(4) == "4"
    assert one_reading.hours_words(4.5) == "4.5"
    assert one_reading.hours_words(0.75) == "0.8"
    assert one_reading.hours_words(38.4) == "38"
    assert one_reading.hours_words(150) == "150"


def _figures(**over) -> dict:
    base = {
        "zone": one_reading.ROOM,
        "hours": 4.0,
        "hours_words": "4",
        "allowed": 120,
        "readings": 1,
        "transcripts": 11,
        "not_ready": 1,
        "summarised": 0,
        "no_summary": 0,
        "room_hours": 116.0,
        "fill": 3.3,
        "cuts": [],
        "nearly": 85.0,
        "at_once": 2,
    }
    base.update(over)
    return base


def test_the_words_of_the_three_states():
    room = one_reading.words(_figures())
    assert room["figure"] == "One reading · 4 of 120 hours"
    assert room["pill"] == "room" and room["tone"] == "ok"
    assert room["left"] == "11 transcripts, 1 not ready yet"
    assert room["right"] == "room for about 116 hours more"
    assert room["sentence"].startswith(
        "A question reads every transcript whole at one go"
    )
    assert room["head"] == "This case · one reading · 4 of 120 hours"
    assert not room["offer_summaries"]

    several = one_reading.words(
        _figures(
            zone=one_reading.SEVERAL,
            hours=38.0,
            hours_words="38",
            readings=4,
            transcripts=100,
            not_ready=0,
            room_hours=82.0,
        )
    )
    assert several["figure"] == "4 readings · 38 of 120 hours"
    assert several["pill"] == "several readings" and several["tone"] == "warn"
    assert several["left"] == "100 transcripts, all ready"
    assert "in 4 readings 2 at a time, and takes a few minutes" in several["sentence"]
    assert several["head"] == "This case · 4 readings · 38 of 120 hours"

    over = one_reading.words(
        _figures(
            zone=one_reading.OVER,
            hours=150.0,
            hours_words="150",
            readings=20,
            transcripts=258,
            not_ready=2,
            summarised=240,
            no_summary=18,
            room_hours=0.0,
        )
    )
    assert over["figure"] == "Over the ceiling · 150 of 120 hours"
    assert over["pill"] == "overviews first" and over["tone"] == "danger"
    assert over["right"] == "240 summarised, 18 not yet"
    assert over["sentence"].endswith("18 have no summary yet and will not be read:")
    assert over["offer_summaries"]
    assert over["head"] == "Over the ceiling · 150 of 120 hours · overviews first"

    none = one_reading.words(
        _figures(zone=one_reading.OVER, hours=150.0, hours_words="150", transcripts=3)
    )
    assert none["pill"] == "no summary yet"
    assert none["sentence"].startswith("No recording has a summary yet")
    assert none["offer_summaries"]


def test_the_head_pill_shows_only_over_the_ceiling():
    assert one_reading.head_pill(None) is None
    assert one_reading.head_pill(_figures()) is None
    pill = one_reading.head_pill(_figures(zone=one_reading.OVER))
    assert pill == {
        "words": "over the reading ceiling",
        "href": "#one-reading",
        "tone": "danger",
    }


# With a database ----------------------------------------------------------------------


@pytest.fixture
def owner(db):
    return User.objects.create_local_admin("case-owner", PASSWORD)


@pytest.fixture
def a_case(owner):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("assistant_available", True)
    settings_store.set_to("chat_across_cases", True)
    return Case.objects.create(owner=owner, name="Marchetti")


def a_recording(owner, case, title, *, hours=0.25, transcript=True):
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=owner),
        user=owner,
        case=case,
        title=title,
        original_filename=f"{title}.m4a",
        media_state=MediaState.READY,
        duration_seconds=hours * 3600,
        diarize=True,
        recording_type="Jail call",
    )
    if transcript:
        made = Transcript.objects.create(recording=recording, language="en")
        for start, speaker, text in (
            (0.0, "Speaker 1", f"This is {title}, good morning to you."),
            (765.0, "Speaker 2", "The car was blue, and it was moved on Friday."),
        ):
            Segment.objects.create(
                transcript=made,
                start=start,
                end=start + 5,
                text=text,
                speaker=speaker,
                speaker_label=speaker.upper().replace(" ", "_"),
            )
    return recording


def test_a_share_is_counted_at_the_landing_and_cleared_by_a_change(owner, a_case):
    recording = a_recording(owner, a_case, "First call")
    transcript = recording.transcript
    assert transcript.reading_made_at is None and one_reading.stale(transcript)
    one_reading.on_transcript(recording)
    transcript.refresh_from_db()
    assert transcript.reading_made_at is not None
    assert transcript.reading_tokens > one_reading.HEADER_TOKENS
    assert not one_reading.stale(transcript)
    # A Correction or a translation clears it, and the next draw counts again.
    one_reading.changed(transcript)
    transcript.refresh_from_db()
    assert transcript.reading_made_at is None
    one_reading.figures(a_case)
    transcript.refresh_from_db()
    assert transcript.reading_made_at is not None


def test_the_landing_counts_nothing_while_the_case_chat_is_off(owner, a_case):
    settings_store.set_to("chat_across_cases", False)
    recording = a_recording(owner, a_case, "First call")
    one_reading.on_transcript(recording)
    recording.transcript.refresh_from_db()
    assert recording.transcript.reading_made_at is None


def test_a_digest_newer_than_the_count_makes_the_share_stale(owner, a_case):
    recording = a_recording(owner, a_case, "First call")
    transcript = recording.transcript
    one_reading.refresh(transcript)
    counted = transcript.reading_made_at
    DigestPart.objects.create(
        transcript=transcript,
        number=1,
        text="What was said.",
        made_at=counted + dt.timedelta(minutes=1),
    )
    transcript.refresh_from_db()
    assert one_reading.stale(transcript)
    one_reading.figures(a_case)
    transcript.refresh_from_db()
    assert transcript.reading_made_at > counted


def test_the_three_states_from_a_cases_recordings(owner, a_case, monkeypatch):
    for n in range(3):
        a_recording(owner, a_case, f"Call {n}")
    a_recording(owner, a_case, "Still transcribing", transcript=False)
    room = one_reading.figures(a_case)
    assert room["zone"] == one_reading.ROOM
    assert room["readings"] == 1 and room["cuts"] == []
    assert room["transcripts"] == 3 and room["not_ready"] == 1
    assert room["hours_words"] == "0.8" and room["allowed"] == 120
    assert room["left"] == "3 transcripts, 1 not ready yet"

    # A Reading that holds two of the three shares: two Readings, one tick
    # where they part, at the first two recordings' share of the ceiling.
    share = room["hours"] / 3
    sizes = [
        one.transcript.reading_tokens
        for one in a_case.recordings.exclude(transcript=None)
    ]
    monkeypatch.setattr(settings_store, "reading_tokens", lambda: max(sizes) * 2 + 1)
    several = one_reading.figures(a_case)
    assert several["zone"] == one_reading.SEVERAL
    assert several["readings"] == 2
    assert several["cuts"] == [round(100 * 2 * share / 120, 1)]
    assert several["head"] == "This case · 2 readings · 0.8 of 120 hours"

    # Over the ceiling, with no summary written: the refusal survives.
    monkeypatch.setattr(case_chat, "hours_allowed", lambda: 0.5)
    monkeypatch.setattr(settings_store, "reading_tokens", lambda: 100_000)
    over = one_reading.figures(a_case)
    assert over["zone"] == one_reading.OVER
    assert over["fill"] == 100.0 and over["room_hours"] == 0
    assert over["summarised"] == 0 and over["no_summary"] == 3
    assert over["pill"] == "no summary yet"
    assert over["head"] == "Over the ceiling · 0.8 of 0.5 hours · no summary yet"


def test_the_strip_costs_the_page_a_handful_of_queries_whatever_the_case(owner, a_case):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    for n in range(30):
        a_recording(owner, a_case, f"Call {n:02d}")
    one_reading.figures(a_case)  # the shares counted once
    with CaptureQueriesContext(connection) as asked:
        one_reading.figures(a_case)
    assert len(asked) <= 6, len(asked)


def test_the_case_page_shows_the_strip_and_the_pill_over_the_ceiling(
    owner, a_case, client, monkeypatch
):
    a_recording(owner, a_case, "First call")
    signed_in(client, owner)
    page = client.get(f"/case/{a_case.pk}").content.decode()
    assert 'id="one-reading"' in page
    assert "One reading · 0.2 of 120 hours" in page
    assert "over the reading ceiling" not in page

    monkeypatch.setattr(case_chat, "hours_allowed", lambda: 0.1)
    page = client.get(f"/case/{a_case.pk}").content.decode()
    assert "Over the ceiling · 0.2 of 0.1 hours" in page
    assert 'class="one-reading over"' in page
    assert ">over the reading ceiling</a>" in page
    assert 'href="#summaries-line">write the summaries tonight</a>' in page


def test_the_strip_is_not_drawn_while_the_case_chat_is_off(owner, a_case, client):
    settings_store.set_to("chat_across_cases", False)
    a_recording(owner, a_case, "First call")
    signed_in(client, owner)
    page = client.get(f"/case/{a_case.pk}").content.decode()
    assert 'id="one-reading"' not in page


def test_the_drawers_state_carries_the_figure_and_the_readings(
    owner, a_case, client, monkeypatch
):
    for n in range(3):
        a_recording(owner, a_case, f"Call {n}")
    signed_in(client, owner)
    # The case page's draw counts the shares; the poll reads them.
    client.get(f"/case/{a_case.pk}")
    body = json.loads(client.get(f"/case/{a_case.pk}/chat").content)
    assert body["head"] == "This case · one reading · 0.8 of 120 hours"
    assert body["readings"] == 1 and body["hours"] == "0.8"
    assert body["hours_allowed"] == 120 and not body["over"]

    sizes = [one.transcript.reading_tokens for one in a_case.recordings.all()]
    monkeypatch.setattr(settings_store, "reading_tokens", lambda: max(sizes) + 1)
    body = json.loads(client.get(f"/case/{a_case.pk}/chat").content)
    assert body["readings"] == 3
    assert body["at_once"] == settings_store.readings_at_once()
    assert body["head"] == "This case · 3 readings · 0.8 of 120 hours"


def test_the_drawers_poll_counts_no_share(owner, a_case, client):
    """The poll runs every few seconds while a question is answered; the
    case page's draw and the landing count the shares, never the poll."""
    recording = a_recording(owner, a_case, "First call")
    signed_in(client, owner)
    body = json.loads(client.get(f"/case/{a_case.pk}/chat").content)
    assert body["readings"] == 1
    recording.transcript.refresh_from_db()
    assert recording.transcript.reading_made_at is None
    client.get(f"/case/{a_case.pk}")
    recording.transcript.refresh_from_db()
    assert recording.transcript.reading_made_at is not None


def test_what_a_question_read_under_its_answer(owner, a_case):
    chat = CaseChat.objects.create(case=a_case, asked_by=owner)
    asked = timezone.now()
    turn = CaseChatTurn.objects.create(
        chat=chat,
        number=1,
        question="When was the car mentioned?",
        answer="On Friday.",
        state=DONE,
        route=WHOLE,
        readings=[{"recording": "a"}, {"recording": "b"}, {"recording": "c"}],
        parts=2,
        answered_at=asked + dt.timedelta(seconds=160),
    )
    CaseChatTurn.objects.filter(pk=turn.pk).update(asked_at=asked)
    turn.refresh_from_db()
    assert one_reading.read_line(turn) == (
        "Read 3 transcripts whole in 2 readings, 2 min 40 s"
    )

    turn.parts = 0
    turn.answered_at = asked + dt.timedelta(seconds=50)
    assert one_reading.read_line(turn) == "Read 3 transcripts whole in 1 reading, 50 s"

    turn.route = NARROWED
    assert one_reading.read_line(turn).startswith(
        "Read the 3 transcripts narrowed to, whole"
    )

    turn.route = OVERVIEWS
    turn.selection = {"overviews_read": 240, "read_whole": 9}
    turn.readings = [{"recording": str(n)} for n in range(9)]
    assert one_reading.read_line(turn) == (
        "Read the overviews of 240, then 9 recordings whole in 1 reading, 50 s"
    )

    # Nothing while the question is still being answered.
    turn.state = RUNNING
    assert one_reading.read_line(turn) == ""
