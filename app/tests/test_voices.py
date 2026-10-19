"""The voice step (ADR 0021, the voice plan's second release, v1.139.0): the
stretches the service is asked about, the judge's prints, calibration and
words from synthetic vectors, the voice's own proposals under the cap, the
Hand-over with its loudness guard, the check running with a fake service,
the split a Hand-over's Yes makes and its Undo, re-scoring on accept, the
vectors deleted when the check is done, and the switch per Recording type.
Nothing here needs the service: its answer is made here.
"""

from __future__ import annotations

import json

import numpy as np
import pytest
from core import call_system, settings_store, speaker_check, voices, whisperx
from core.assistant import Handover, SpeakerCheck, SpeakerCorrection
from core.jobs import Segment
from core.models import User
from core.recordings import Side
from tests.helpers import signed_in
from tests.test_prepare import a_recording

PASSWORD = "a-long-enough-password"
RNG = np.random.default_rng(11)
VOICE_A = RNG.normal(size=192)
VOICE_B = RNG.normal(size=192)
VOICE_C = RNG.normal(size=192)


@pytest.fixture
def admin(db):
    return User.objects.create_local_admin("adm", PASSWORD)


def noisy(base, scale=0.08):
    return list((base + RNG.normal(scale=scale, size=192)).astype(float))


def a_call(
    person,
    tmp_path,
    settings,
    *,
    lines=40,
    wrong=(5, 17),
    kind="Jail call",
    handover_from=None,
):
    """A call of `lines` lines, Speaker 1 and Speaker 2 alternating in pairs,
    each line timed with its own words; the lines in `wrong` are labelled
    Speaker 1 but will be voiced as Speaker 2 by the fake service; from
    `handover_from` (a line number) Speaker 2's lines are voiced as a third
    voice."""
    recording = a_recording(person, tmp_path, settings, title="Call", video=False)
    recording.recording_type = kind
    recording.save(update_fields=["recording_type"])
    transcript = recording.transcript
    transcript.segments.all().delete()
    side = Side.objects.create(recording=recording, number=1, kind=Side.WHOLE, name="")
    side.asr_path.parent.mkdir(parents=True, exist_ok=True)
    side.asr_path.write_bytes(b"RIFFfake wav")
    truth = {}
    for n in range(lines):
        speaker = "Speaker 1" if (n // 2) % 2 == 0 else "Speaker 2"
        start = 2.0 + n * 4.0
        words = [
            {
                "word": w,
                "start": start + i * 0.6,
                "end": start + i * 0.6 + 0.5,
                "speaker": speaker.upper().replace(" ", "_"),
            }
            for i, w in enumerate(("some", "words", "spoken", "here", "now"))
        ]
        seg = Segment.objects.create(
            transcript=transcript,
            side=side,
            start=start,
            end=start + 3.0,
            text="some words spoken here now",
            speaker=speaker,
            speaker_label=speaker.upper().replace(" ", "_"),
            words=words,
        )
        voice = VOICE_B if (speaker == "Speaker 2" or n in wrong) else VOICE_A
        if handover_from is not None and speaker == "Speaker 2" and n >= handover_from:
            voice = VOICE_C
        truth[str(seg.pk)] = voice
    return recording, truth


def fake_service(truth, *, loud=None):
    """The service's answer from the truth: one vector per stretch id."""

    def answer(audio, request, lane=""):
        rows = []
        for one in request["stretches"]:
            base = truth.get(one["id"])
            rows.append(
                {
                    "id": one["id"],
                    "label": one["label"],
                    "net_seconds": 2.9,
                    "rms_dbfs": (loud or {}).get(one["id"], -20.0),
                    "vector": noisy(base) if base is not None else None,
                }
            )
        return {
            "stretches": rows,
            "labels": [],
            "seconds": 0.3,
            "card_peak_gb": 0.3,
            "model": {"name": "titanet"},
        }

    return answer


def test_stretches_are_the_lines_own_words(admin, tmp_path, settings):
    recording, _ = a_call(admin, tmp_path, settings, lines=4)
    seg = recording.transcript.segments.order_by("start").first()
    # One foreign word in the middle is left out of the line's own spans.
    words = seg.words
    words[2]["speaker"] = "SPEAKER_9"
    seg.words = words
    seg.save()
    by_side = voices.stretches_of(recording.transcript)
    assert list(by_side) == [1]
    first = by_side[1][0]
    assert first["id"] == str(seg.pk) and first["timed"] and len(first["spans"]) == 4
    # A line with no timed words is one span, start to end, marked untimed.
    seg.words = [{"word": "x"}]
    seg.save()
    first = voices.stretches_of(recording.transcript)[1][0]
    assert first["timed"] is False and first["spans"] == [[seg.start, seg.end]]


def test_the_switch_is_per_recording_type(admin, tmp_path, settings):
    recording, _ = a_call(admin, tmp_path, settings, lines=2, kind="Body camera")
    assert settings_store.DEFINITIONS["voices_types"].default == "Jail call"
    assert not voices.on_for(recording)
    recording.recording_type = "Jail call"
    assert voices.on_for(recording)
    assert voices.floor_for(recording) == 1.0
    recording.recording_type = ""
    assert not voices.on_for(recording)


def test_the_judge_words_proposals_and_calibration(
    admin, tmp_path, settings, monkeypatch
):
    recording, truth = a_call(admin, tmp_path, settings, lines=40, wrong=(5, 17))
    monkeypatch.setattr(whisperx, "voices", fake_service(truth))
    answer = voices.ask(recording.transcript)
    judge = voices.Judge(recording.transcript, answer["stretches"], 1.0)
    assert len(judge.centroids) == 2
    assert judge.calibration["thresholds"]["long"] is not None
    segs = list(recording.transcript.segments.order_by("start"))
    wrong = segs[5]
    assert judge.word(wrong.pk, "Speaker 1", "Speaker 2")[0] == voices.AGREES
    right = segs[0]
    assert judge.word(right.pk, "Speaker 1", "Speaker 2")[0] == voices.AGAINST
    proposals = judge.own_proposals(set())
    assert {p["segment_id"] for p in proposals} == {segs[5].pk, segs[17].pk}
    assert all(p["to"] == "Speaker 2" for p in proposals)
    assert judge.own_proposals({segs[5].pk})[0]["segment_id"] == segs[17].pk


def test_a_hand_over_is_found_and_the_loudness_guard_holds_a_shout(
    admin, tmp_path, settings, monkeypatch
):
    recording, truth = a_call(
        admin, tmp_path, settings, lines=48, wrong=(), handover_from=28
    )
    monkeypatch.setattr(whisperx, "voices", fake_service(truth))
    answer = voices.ask(recording.transcript)
    judge = voices.Judge(recording.transcript, answer["stretches"], 1.0)
    found = judge.handovers()
    assert len(found) == 1
    one = found[0]
    assert one["speaker"] == "Speaker 2" and not one["held"]
    at_line = sorted(
        recording.transcript.segments.filter(
            speaker="Speaker 2", start__gte=one["at"]
        ).values_list("start", flat=True)
    )[0]
    assert abs(one["at"] - at_line) < 0.01
    # The same split in the vectors, but the second voice ten decibels louder: held.
    loud = {
        sid: (-10.0 if np.allclose(v, VOICE_C) else -20.0) for sid, v in truth.items()
    }
    monkeypatch.setattr(whisperx, "voices", fake_service(truth, loud=loud))
    judge = voices.Judge(
        recording.transcript, voices.ask(recording.transcript)["stretches"], 1.0
    )
    assert judge.handovers()[0]["held"] is True


def test_the_check_carries_the_voice_and_stores_its_proposals(
    admin, tmp_path, settings, monkeypatch
):
    settings_store.set_to("assistant_available", True)
    settings_store.set_to("speaker_check_available", True)
    recording, truth = a_call(
        admin, tmp_path, settings, lines=40, wrong=(5, 17), handover_from=None
    )
    monkeypatch.setattr(whisperx, "voices", fake_service(truth))
    transcript = recording.transcript
    segs = list(transcript.segments.order_by("start"))
    check = SpeakerCheck.objects.create(transcript=transcript, state="running")
    kept = {
        segs[5].pk: {
            "segment_id": segs[5].pk,
            "start": segs[5].start,
            "quote": "q",
            "from": "Speaker 1",
            "to": "Speaker 2",
            "reason": "answers",
        },
        segs[0].pk: {
            "segment_id": segs[0].pk,
            "start": segs[0].start,
            "quote": "q",
            "from": "Speaker 1",
            "to": "Speaker 2",
            "reason": "answers",
        },
    }
    summary = speaker_check._voice_notes(transcript, kept, check)
    assert summary["voice"] == "titanet"
    assert (
        kept[segs[5].pk]["voice"] == "agrees" and kept[segs[0].pk]["voice"] == "against"
    )
    # Line 17 was never flagged by the words: the voice proposes it.
    assert (
        segs[17].pk in kept and kept[segs[17].pk]["source"] == SpeakerCorrection.VOICE
    )
    assert summary["voice_proposals"] == 1
    assert check.voices["stretches"][str(segs[5].pk)]["vector"] is not None
    speaker_check._store(transcript, kept)
    rows = {one.segment_id: one for one in transcript.corrections.all()}
    assert rows[segs[17].pk].source == "voice" and rows[segs[17].pk].voice == "agrees"
    assert rows[segs[5].pk].source == "words"


def test_without_the_service_the_word_labels_speak(
    admin, tmp_path, settings, monkeypatch
):
    recording, _ = a_call(admin, tmp_path, settings, lines=8)

    def down(audio, request, lane=""):
        raise whisperx.ServiceError("down", "service_unreachable")

    monkeypatch.setattr(whisperx, "voices", down)
    segs = list(recording.transcript.segments.order_by("start"))
    kept = {
        segs[1].pk: {
            "segment_id": segs[1].pk,
            "start": 0,
            "quote": "q",
            "from": "Speaker 1",
            "to": "Speaker 2",
            "reason": "r",
        }
    }
    summary = speaker_check._voice_notes(recording.transcript, kept)
    assert summary["voice"] == "unavailable"
    assert summary["voice_unavailable"]
    # The old rule speaks only on a long line (twelve words or more): on
    # this short one the word labels are silent, as before the voice step.
    assert kept[segs[1].pk]["voice"] == ""


def test_a_hand_over_yes_splits_the_label_and_undo_puts_it_back(
    admin, tmp_path, settings, client
):
    recording, _ = a_call(admin, tmp_path, settings, lines=16)
    transcript = recording.transcript
    at = sorted(
        transcript.segments.filter(speaker="Speaker 2").values_list("start", flat=True)
    )[2]
    handover = Handover.objects.create(
        transcript=transcript, speaker="Speaker 2", at=at, lines_after=6, voices=2
    )
    browser = signed_in(client, admin)
    answer = browser.post(f"/handover/{handover.pk}/accept")
    assert answer.status_code == 200, answer.content
    body = answer.json()
    assert body["made"] == "Speaker 3"
    assert transcript.segments.filter(speaker="Speaker 3").count() == 6
    assert transcript.segments.filter(speaker="Speaker 2").count() == 2
    handover.refresh_from_db()
    assert handover.state == Handover.ACCEPTED and handover.made == "Speaker 3"
    assert "splitting Speaker 2" in body["undo"]
    undone = browser.post(f"/recording/{recording.pk}/speakers/undo")
    assert undone.status_code == 200
    assert transcript.segments.filter(speaker="Speaker 3").count() == 0
    assert transcript.segments.filter(speaker="Speaker 2").count() == 8
    # No: the finding is put away and nothing moves.
    other = Handover.objects.create(
        transcript=transcript, speaker="Speaker 1", at=at, lines_after=4, voices=2
    )
    assert browser.post(f"/handover/{other.pk}/dismiss").status_code == 200
    other.refresh_from_db()
    assert other.state == Handover.DISMISSED
    assert transcript.segments.filter(speaker="Speaker 1").count() == 8


def test_accepting_re_scores_and_done_deletes_the_vectors(
    admin, tmp_path, settings, monkeypatch, client
):
    settings_store.set_to("assistant_available", True)
    settings_store.set_to("speaker_check_available", True)
    recording, truth = a_call(admin, tmp_path, settings, lines=40, wrong=(5,))
    monkeypatch.setattr(whisperx, "voices", fake_service(truth))
    transcript = recording.transcript
    segs = list(transcript.segments.order_by("start"))
    check = SpeakerCheck.objects.create(transcript=transcript, state="running")
    kept = {
        segs[5].pk: {
            "segment_id": segs[5].pk,
            "start": segs[5].start,
            "quote": "q",
            "from": "Speaker 1",
            "to": "Speaker 2",
            "reason": "r",
        }
    }
    check.second_look = speaker_check._voice_notes(transcript, kept, check)
    check.state = "done"
    check.save()
    speaker_check._store(transcript, kept)
    assert transcript.corrections.filter(state="pending").count() == 1
    assert check.voices["stretches"]
    correction = transcript.corrections.get(segment=segs[5])
    browser = signed_in(client, admin)
    assert browser.post(f"/correction/{correction.pk}/accept").status_code == 200
    assert transcript.segments.get(pk=segs[5].pk).speaker == "Speaker 2"
    check.refresh_from_db()
    # Nothing pending any more: the vectors are gone.
    assert check.voices == {}


def test_the_state_carries_the_source_and_the_hand_overs(
    admin, tmp_path, settings, client
):
    recording, _ = a_call(admin, tmp_path, settings, lines=8)
    transcript = recording.transcript
    seg = transcript.segments.order_by("start").first()
    SpeakerCorrection.objects.create(
        transcript=transcript,
        segment=seg,
        start=seg.start,
        quote="q",
        speaker_from="Speaker 1",
        speaker_to="Speaker 2",
        reason="the voice sounds like Speaker 2",
        voice="agrees",
        source="voice",
    )
    Handover.objects.create(
        transcript=transcript, speaker="Speaker 2", at=20.0, lines_after=3, voices=2
    )
    Handover.objects.create(
        transcript=transcript,
        speaker="Speaker 1",
        at=24.0,
        lines_after=3,
        voices=2,
        held=True,
    )
    state = speaker_check.state_json(transcript)
    assert state["pending"][0]["source"] == "voice"
    assert [one["speaker"] for one in state["handovers"]] == ["Speaker 2"]
    assert state["handovers_held"] == 1
    assert state["voice"] == "words"


def test_the_opening_stretch_fills_in(admin, tmp_path, settings):
    settings_store.set_to("call_system_available", True)
    recording, _ = a_call(admin, tmp_path, settings, lines=0)
    transcript = recording.transcript
    plan = (
        (0.0, "For English, press one. For a collect call, press two."),
        (3.0, "Please..."),
        (7.0, "Your current balance is fourteen dollars."),
        (12.0, "Please enter the..."),
        (20.0, "Please hold."),
        (21.0, "Please wait while your call is being connected."),
        (60.0, "Hello?"),
        (62.0, "Hey, it's me."),
        (880.0, "You have one minute remaining."),
        (884.0, "Okay, love you."),
    )
    for start, text in plan:
        Segment.objects.create(
            transcript=transcript,
            start=start,
            end=start + 2.5,
            text=text,
            speaker="Speaker 1",
            speaker_label="SPEAKER_1",
        )
    # Six of the opening stretch (three by phrase, three filled in between
    # them) and the one-minute warning by phrase.
    assert call_system.mark(transcript) == 7
    marked = sorted(
        transcript.segments.filter(speaker=call_system.NAME).values_list(
            "start", flat=True
        )
    )
    assert marked == [0.0, 3.0, 7.0, 12.0, 20.0, 21.0, 880.0]
    # The party's lines after the connection and the last word stay theirs.
    assert transcript.segments.get(start=60.0).speaker == "Speaker 1"
    assert transcript.segments.get(start=884.0).speaker == "Speaker 1"


def test_the_voices_client_translates_the_services_answer(monkeypatch, tmp_path):
    seen = {}

    def fake_request(method, path, body=None, content_type=None, timeout=0, lane=""):
        seen.update({"method": method, "path": path, "timeout": timeout})
        return 200, {"stretches": [], "labels": []}

    monkeypatch.setattr(whisperx, "_request", fake_request)
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    assert whisperx.voices(wav, {"stretches": [], "sure_seconds": 2.0}) == {
        "stretches": [],
        "labels": [],
    }
    assert seen["path"] == "/v1/voices" and seen["timeout"] == whisperx.VOICES_TIMEOUT

    def refused(method, path, body=None, content_type=None, timeout=0, lane=""):
        return 503, {"error": "down", "reason_class": "diarizer_unavailable"}

    monkeypatch.setattr(whisperx, "_request", refused)
    with pytest.raises(whisperx.ServiceError) as caught:
        whisperx.voices(wav, {"stretches": []})
    assert caught.value.reason_class == "diarizer_unavailable"


def test_the_json_the_page_reads_is_json(admin, tmp_path, settings, monkeypatch):
    recording, truth = a_call(admin, tmp_path, settings, lines=12)
    monkeypatch.setattr(whisperx, "voices", fake_service(truth))
    answer = voices.ask(recording.transcript)
    kept = voices.dump(answer)
    json.dumps(kept)
    judge = voices.judge_from(recording.transcript, kept)
    assert judge is not None and len(judge.stretches) == 12
