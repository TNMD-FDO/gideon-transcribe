"""The phone system's voice (v1.159.0; Phase 5 chapter 2, "The phone
system's voice"): taught from the Call system's lines by their words,
counting what its voice would give until an Admin starts the giving; the
five guards; the way back on the guided page and the stop after three;
the Phone systems tab; and a kept voice whose case was deleted."""

from __future__ import annotations

import uuid

import numpy as np
import pytest
from core import (
    call_system,
    settings_store,
    speaker_check,
    system_voices,
    units,
    voice_book,
    whisperx,
)
from core.assistant import SpeakerCheck
from core.audit import Row
from core.system_voices import SystemVoice
from tests.helpers import signed_in
from tests.test_voice_prints import vec
from tests.test_voices import a_call
from tests.test_voices import admin as _admin  # noqa: F401

VOICE_S = np.asarray(vec(77))
RNG = np.random.default_rng(7)


def quiet(base) -> list[float]:
    return list((base + RNG.normal(scale=0.02, size=192)).astype(float))


def quiet_service(truth):
    """The service's answer from the truth, with a little seeded noise: the
    voice tests' fake adds a lot, and the guards here are margins."""

    def answer(audio, request, lane=""):
        rows = []
        for one in request["stretches"]:
            base = truth.get(one["id"])
            rows.append(
                {
                    "id": one["id"],
                    "label": one["label"],
                    "net_seconds": 2.9,
                    "rms_dbfs": -20.0,
                    "vector": quiet(base) if base is not None else None,
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


@pytest.fixture
def admin(_admin):  # noqa: F811
    return _admin


@pytest.fixture
def phones_on(db):
    settings_store.set_to("assistant_available", True)
    settings_store.set_to("speaker_check_available", True)
    settings_store.set_to("call_system_available", True)
    yield
    settings_store.set_to("call_system_available", False)


def a_jail_call(admin, tmp_path, settings, *, system=(0, 1, 2, 3), by_voice=(4,)):
    """A call whose first lines are the Call system's by their words, all
    voiced as the phone system; `by_voice` lines keep a party's label but
    are voiced as the system too."""
    recording, truth = a_call(admin, tmp_path, settings, lines=40, wrong=())
    segs = list(recording.transcript.segments.order_by("start"))
    for n in system:
        segs[n].speaker = call_system.NAME
        segs[n].save(update_fields=["speaker"])
        truth[str(segs[n].pk)] = VOICE_S
    for n in by_voice:
        truth[str(segs[n].pk)] = VOICE_S
    return recording, truth, segs


def run_step(recording, truth, monkeypatch) -> dict:
    """The voice step on the call, as the check runs it; one check a
    transcript (the database keeps it so)."""
    monkeypatch.setattr(whisperx, "voices", quiet_service(truth))
    transcript = recording.transcript
    check = SpeakerCheck.objects.filter(transcript=transcript).first()
    if check is None:
        check = SpeakerCheck.objects.create(transcript=transcript, state="running")
    summary = speaker_check._voice_notes(recording.transcript, {}, check)
    return summary["phone_system"]


def test_the_system_is_taught_from_the_words_and_counts_until_started(
    admin, tmp_path, settings, monkeypatch, phones_on
):
    recording, truth, segs = a_jail_call(admin, tmp_path, settings)
    out = run_step(recording, truth, monkeypatch)
    # Taught from the four word-found lines; the fifth, a party's line that
    # sounds like the system next to them, is counted and not moved.
    voice = SystemVoice.objects.get()
    assert voice.name == "Call system" and voice.live and not voice.giving
    assert list(voice.parts) == [str(recording.pk)]
    assert voice.parts[str(recording.pk)]["lines"] == 4
    assert out["would"] == 1 and out["given"] == 0 and out["giving"] is False
    segs[4].refresh_from_db()
    assert segs[4].speaker == "Speaker 1"
    assert Row.objects.filter(event="Phone system first heard").count() == 1
    assert system_voices.month_counts(voice)["would"] == 1
    assert system_voices.month_counts(voice)["calls"] == 1
    block = recording.transcript.provenance["call_system"]
    assert block["voice"] == str(voice.pk) and block["voice_would"] == 1
    state = system_voices.page_state(recording.transcript)
    assert state["words"] == 4 and state["voice"] == 0 and state["would"] == 1
    # Started by an Admin: the same reading gives the line, with its way back.
    system_voices.set_giving(voice, True, by=admin)
    out = run_step(recording, truth, monkeypatch)
    assert out["given"] == 1 and out["giving"] is True
    segs[4].refresh_from_db()
    assert segs[4].speaker == call_system.NAME
    block = recording.transcript.provenance["call_system"]
    assert block["by_voice"] == {str(segs[4].pk): "Speaker 1"}
    state = system_voices.page_state(recording.transcript)
    assert state["words"] == 4 and state["voice"] == 1 and state["giving"]
    assert state["voice_lines"][0]["segment"] == segs[4].pk
    assert state["voice_lines"][0]["was"] == "Speaker 1"
    # The second reading taught the same call again, not a second call.
    voice.refresh_from_db()
    assert len(voice.parts) == 1 and system_voices.month_counts(voice)["calls"] == 1
    # A line given by voice never teaches (guard 1): the part counts four.
    assert voice.parts[str(recording.pk)]["lines"] == 4
    # Not the system: back to its label, never given again by voice.
    assert system_voices.give_back(recording.transcript, segs[4].pk, by=admin) == (
        "Speaker 1"
    )
    segs[4].refresh_from_db()
    assert segs[4].speaker == "Speaker 1"
    out = run_step(recording, truth, monkeypatch)
    assert out["would"] == 0 and out["given"] == 0
    segs[4].refresh_from_db()
    assert segs[4].speaker == "Speaker 1"
    state = system_voices.page_state(recording.transcript)
    assert state["back_lines"][0]["segment"] == segs[4].pk
    assert Row.objects.filter(event="Phone system line given back").count() == 1
    # The system after all.
    system_voices.give_again(recording.transcript, segs[4].pk, by=admin)
    segs[4].refresh_from_db()
    assert segs[4].speaker == call_system.NAME
    with pytest.raises(ValueError, match="not given back"):
        system_voices.give_again(recording.transcript, segs[4].pk, by=admin)


def test_three_given_back_in_a_month_stop_the_giving(
    admin, tmp_path, settings, monkeypatch, phones_on
):
    recording, truth, segs = a_jail_call(admin, tmp_path, settings)
    run_step(recording, truth, monkeypatch)
    voice = SystemVoice.objects.get()
    system_voices.set_giving(voice, True, by=admin)
    run_step(recording, truth, monkeypatch)
    system_voices.bump(voice, back=system_voices.BACK_TO_STOP - 1)
    voice.save(update_fields=["months"])
    system_voices.give_back(recording.transcript, segs[4].pk, by=admin)
    voice.refresh_from_db()
    assert not voice.giving and voice.called_out_at is not None
    assert Row.objects.filter(event="Phone system called out").count() == 1
    # Started again by an Admin, the call-out clears.
    system_voices.set_giving(voice, True, by=admin)
    voice.refresh_from_db()
    assert voice.giving and voice.called_out_at is None


class FakeJudge:
    """Enough of the voice step's judge for the guards: a floor, a threshold,
    the vectors, every line's name (the ceiling is a share of them) and the
    parties' prints."""

    def __init__(self, transcript, rows: dict, prints: dict, threshold: float = 0.1):
        self.floor = 1.0
        self.stretches = {
            sid: {"timed": True, "net": 3.0, "start": start}
            for sid, (start, _v, _name) in rows.items()
        }
        self.vec = {sid: system_voices._unit(v) for sid, (_s, v, _n) in rows.items()}
        self.names = {
            str(pk): name
            for pk, name in transcript.segments.values_list("pk", "speaker")
        }
        self.names.update({sid: name for sid, (_s, _v, name) in rows.items()})
        self.prints = {name: system_voices._unit(v) for name, v in prints.items()}
        self._threshold = threshold

    def name_of(self, sid):
        return self.names.get(sid, "")

    def threshold(self, net):
        return self._threshold

    def cos_to(self, sid, name):
        print_ = self.prints.get(name)
        return None if print_ is None else float(self.vec[sid] @ print_)

    def others_for(self, sid):
        own = self.name_of(sid)
        return [(1, name) for name in sorted(self.prints) if name != own]


def test_the_guards_on_a_fake_judge(admin, tmp_path, settings, phones_on):
    recording, _truth, segs = a_jail_call(admin, tmp_path, settings, by_voice=())
    transcript = recording.transcript
    voice = SystemVoice.objects.create(vector=vec(77), giving=True)
    a, b, s = np.asarray(vec(1)), np.asarray(vec(2)), VOICE_S
    near = 14.0 + 5.0  # within NEAR_WORDS_SECONDS of the last system line (14 s)
    far = 200.0
    # Speaker 1 has 20 lines (the ceiling is a share of that many).
    rows = {
        str(segs[4].pk): (near, s, "Speaker 1"),  # the system's voice, by the words
        str(segs[6].pk): (far, s, "Speaker 1"),  # far from the words, but very strong
        str(segs[8].pk): (near, a, "Speaker 1"),  # Speaker 1's own voice: stays
        str(segs[10].pk): (near, (a + s) / 2, "Speaker 1"),  # between: not by a margin
    }
    judge = FakeJudge(transcript, rows, {"Speaker 1": a, "Speaker 2": b})
    out = system_voices.give(transcript, judge, [voice])
    given = set((transcript.provenance["call_system"].get("by_voice") or {}).keys())
    assert given == {str(segs[4].pk), str(segs[6].pk)} and out["given"] == 2
    # Guard 4, the ceiling: five of Speaker 1's twenty lines sound like the
    # system, more than the share, so none are taken and the label is named.
    block = dict(transcript.provenance["call_system"])
    block.pop("by_voice")
    transcript.provenance["call_system"] = block
    transcript.save(update_fields=["provenance"])
    transcript.segments.filter(pk__in=[segs[4].pk, segs[6].pk]).update(
        speaker="Speaker 1"
    )
    many = {str(segs[n].pk): (near, s, "Speaker 1") for n in (4, 6, 8, 12, 16)}
    prints = {"Speaker 1": a, "Speaker 2": b}
    out = system_voices.give(transcript, FakeJudge(transcript, many, prints), [voice])
    assert out["given"] == 0 and out["held"] == {"Speaker 1": 5}
    assert transcript.segments.filter(pk=segs[4].pk).get().speaker == "Speaker 1"
    # Guard 2 against another party: nearer Speaker 2's print than the system.
    rows = {str(segs[4].pk): (near, (b * 3 + s) / 4, "Speaker 1")}
    out = system_voices.give(transcript, FakeJudge(transcript, rows, prints), [voice])
    assert out["given"] == 0 and out["would"] == 0


def test_a_second_system_makes_a_second_card_and_the_switch_off_forgets(
    admin, tmp_path, settings, monkeypatch, phones_on
):
    recording, truth, _segs = a_jail_call(admin, tmp_path, settings, by_voice=())
    run_step(recording, truth, monkeypatch)
    other, truth2, segs2 = a_jail_call(admin, tmp_path, settings, by_voice=())
    for n in (0, 1, 2, 3):
        truth2[str(segs2[n].pk)] = np.asarray(vec(5))  # a system that sounds unlike
    run_step(other, truth2, monkeypatch)
    names = list(SystemVoice.objects.values_list("name", flat=True))
    assert names == ["Call system", "Call system 2"]
    # The Call system switch off deletes the prints; the lines stay.
    settings_store.set_to("call_system_available", False)
    assert SystemVoice.objects.count() == 0
    assert recording.transcript.segments.filter(speaker=call_system.NAME).count() == 4


def test_the_phone_systems_tab_and_its_admin_acts(
    admin, tmp_path, settings, monkeypatch, phones_on, client
):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("units", "Appeals | OU=Appeals,OU=Staff")
    settings_store.set_to("remember_voices", True)
    settings_store.set_to("unit_voices", True)
    units.set_by_hand(admin, "Appeals", by=admin)
    recording, truth, _segs = a_jail_call(admin, tmp_path, settings)
    run_step(recording, truth, monkeypatch)
    voice = SystemVoice.objects.get()
    signed_in(client, admin)
    place = client.get("/voices").content.decode()
    assert "Phone systems &middot; 1" in place
    page = client.get("/voices/phone-systems").content.decode()
    assert "Call system" in page and "listening, not moving" in page
    assert "would have given 1 line" in page
    assert "Start giving lines by its voice" in page
    assert "Hear it on" in page
    acts = f"/voices/phone-systems/{voice.pk}"
    assert client.post(f"{acts}/giving", {"giving": "1"}).status_code == 302
    voice.refresh_from_db()
    assert voice.giving
    page = client.get("/voices/phone-systems").content.decode()
    assert "giving lines by its voice" in page
    assert "Stop giving lines by its voice" in page
    assert client.post(f"{acts}/rename", {"name": "County jail"}).status_code == 302
    voice.refresh_from_db()
    assert voice.name == "County jail"
    assert Row.objects.filter(event="Phone system renamed").count() == 1
    # The guided page's state carries the phone system; the way back answers.
    state = speaker_check.state_json(recording.transcript, admin)
    assert state["phone_system"]["name"] == "County jail"
    assert (
        client.post(
            f"/recording/{recording.pk}/speakers/system-line/back",
            data='{"segment": 0}',
            content_type="application/json",
        ).status_code
        == 400
    )
    assert client.post(f"{acts}/forget").status_code == 302
    assert SystemVoice.objects.count() == 0
    # The scripts and the words the page reads.
    from pathlib import Path

    here = Path(__file__).resolve().parents[1]
    script = (here / "static" / "speakers-guided.js").read_text(encoding="utf-8")
    assert "phoneSystemHtml" in script and "Not the system" in script
    assert "speakers/system-line/" in script
    settings_store.set_to("unit_voices", False)
    settings_store.set_to("units", "")


def test_a_kept_voice_whose_case_was_deleted_says_so(admin, tmp_path, settings):
    from core.cases import Case
    from core.people import Person
    from tests.test_voice_prints import a_print, part

    settings_store.set_to("folder_management", True)
    settings_store.set_to("units", "Appeals | OU=Appeals,OU=Staff")
    settings_store.set_to("remember_voices", True)
    settings_store.set_to("unit_voices", True)
    units.set_by_hand(admin, "Appeals", by=admin)
    case = Case.objects.create(owner=admin, name="Gone")
    person = Person.objects.create(
        case=case,
        name="Lee Ortiz",
        role="Officer",
        voice_print=a_print((str(uuid.uuid4()), part(1))),
    )
    book = voice_book.keep(person, by=admin)
    row = voice_book.page_rows("Appeals", admin)[0]
    assert row["from_text"] == "Gone" and row["others_deleted"] == 0
    case.delete()
    book.refresh_from_db()
    assert book.live and book.from_case_id is None
    row = voice_book.page_rows("Appeals", admin)[0]
    assert row["from_text"] == "a case since deleted"
    settings_store.set_to("unit_voices", False)
    settings_store.set_to("units", "")
