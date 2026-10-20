"""The speaker picker (v1.142.0, the voice plan's section 13): one control
wherever the app asks whose a line or a voice is; samples by the voice
print; a role on someone new; Split into a chosen speaker; the pages."""

import json
from pathlib import Path

import pytest
from core import speaker_check, speakers_page, viewer
from core.assistant import Handover, SpeakerCheck
from core.models import User
from core.people import Person
from core.speakers_page import Line
from tests.helpers import signed_in
from tests.test_people import a_case, owner  # noqa: F401
from tests.test_people import a_recording as a_case_recording
from tests.test_prepare import a_recording

PASSWORD = "a-long-enough-password"
HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent


@pytest.fixture
def admin(db):
    return User.objects.create_local_admin("adm", PASSWORD)


class FakeJudge:
    """A judge with a known fit for each line."""

    def __init__(self, fits):
        self.stretches = {str(pk): {} for pk in fits}
        self._fits = {str(pk): fit for pk, fit in fits.items()}

    def name_of(self, sid):
        return "Speaker 1" if sid in self._fits else ""

    def cos_to(self, sid, name):
        return self._fits.get(sid)


def test_samples_are_the_lines_nearest_the_print_where_the_voice_scored():
    lines = [
        Line(0.0, 4.0, id=1, fit=0.4),
        Line(10.0, 14.0, id=2, fit=0.9),
        Line(20.0, 24.0, id=3, fit=0.1),
        Line(30.0, 34.0, id=4, fit=0.8),
        Line(40.0, 44.0, id=5, fit=0.7),
        Line(50.0, 54.0, id=6, fit=0.95),
    ]
    picked = speakers_page.pick_samples(lines)
    assert [one.id for one in picked] == [2, 4, 6]
    # A line the voice did not score is passed over while a scored one remains.
    lines[1].fit = None
    assert [one.id for one in speakers_page.pick_samples(lines)][0] == 1
    # Without any score the length rule stands.
    plain = [Line(0.0, 4.0, id=1), Line(10.0, 12.0, id=2), Line(20.0, 30.0, id=3)]
    assert speakers_page.pick_samples(plain) == plain


def test_the_voice_step_writes_each_lines_fit_and_a_hand_move_clears_it(
    admin, tmp_path, settings
):
    recording = a_recording(admin, tmp_path, settings)
    transcript = recording.transcript
    first, second = list(transcript.segments.order_by("start"))[:2]
    speaker_check._write_fits(transcript, FakeJudge({first.pk: 0.81}))
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.voice_fit == pytest.approx(0.81) and second.voice_fit is None
    viewer.move_line(transcript, first, "Speaker 2", by=admin)
    first.refresh_from_db()
    assert first.voice_fit is None


def test_the_picker_offers_this_call_the_case_and_the_roles(owner, a_case, client):  # noqa: F811
    recording = a_case_recording(owner, a_case)
    other = a_case_recording(owner, a_case, title="a second interview")
    other.transcript.segments.filter(speaker="Speaker 1").update(
        speaker="Dana Reyes", voice_fit=0.9
    )
    Person.objects.create(
        case=a_case, name="Dana Reyes", role="Client", also_called=["Mama"]
    )
    Person.objects.create(case=a_case, name="Lee Ortiz")
    signed_in(client, owner)
    offer = client.get(f"/recording/{recording.pk}/picker").json()
    assert offer["in_case"] is True
    assert [one["name"] for one in offer["on_call"]] == ["Speaker 1", "Speaker 2"]
    first = offer["on_call"][0]
    assert first["lines"] == 2
    assert first["samples"][0]["id"] and first["samples"][0]["quote"]
    assert first["by_voice"] is False
    people = {one["name"]: one for one in offer["people"]}
    assert set(people) == {"Dana Reyes", "Lee Ortiz"}
    dana = people["Dana Reyes"]
    assert dana["role"] == "Client" and dana["also_called"] == ["Mama"]
    assert dana["recordings"] == 1
    assert dana["sample"]["recording"] == str(other.pk)
    assert dana["sample"]["title"] == "a second interview"
    assert people["Lee Ortiz"]["sample"] is None
    assert isinstance(offer["roles"], list)
    # A recording outside a case offers the call alone.
    alone = a_case_recording(owner, None)
    offer = client.get(f"/recording/{alone.pk}/picker").json()
    assert offer["in_case"] is False and offer["people"] == []


def test_someone_new_from_the_picker_brings_a_role(owner, a_case, client):  # noqa: F811
    from core import people

    recording = a_case_recording(owner, a_case)
    roles = people.roles()
    role = roles[0] if roles else ""
    line = recording.transcript.segments.order_by("start").first()
    signed_in(client, owner)
    answer = client.post(
        f"/recording/{recording.pk}/segment/{line.pk}/speaker",
        data=json.dumps({"speaker": "Priya Nair", "role": role}),
        content_type="application/json",
    )
    assert answer.status_code == 200 and answer.json()["changed"] == 1
    person = Person.objects.get(case=a_case, name="Priya Nair")
    assert person.role == role
    # A role not on the Admin's list is ignored.
    again = client.post(
        f"/recording/{recording.pk}/segment/{line.pk}/speaker",
        data=json.dumps({"speaker": "Sam Cole", "role": "Not a role"}),
        content_type="application/json",
    )
    assert again.json()["changed"] == 1
    assert Person.objects.get(case=a_case, name="Sam Cole").role == ""


def test_a_hand_over_splits_into_the_picked_speaker(owner, a_case, client):  # noqa: F811
    recording = a_case_recording(owner, a_case)
    transcript = recording.transcript
    check = SpeakerCheck.objects.create(transcript=transcript, state="done")
    handover = Handover.objects.create(
        transcript=transcript, run=check, speaker="Speaker 1", at=700.0, lines_after=1
    )
    signed_in(client, owner)
    answer = client.post(
        f"/handover/{handover.pk}/accept",
        data=json.dumps({"into": "Dana Reyes"}),
        content_type="application/json",
    ).json()
    assert answer["ok"] is True and answer["made"] == "Dana Reyes"
    assert transcript.segments.get(start=724.0).speaker == "Dana Reyes"
    assert transcript.segments.get(start=0.0).speaker == "Speaker 1"
    # Inside a case the picked name is a Person.
    assert Person.objects.filter(case=a_case, name="Dana Reyes").exists()
    # Into the same label is nothing.
    second = Handover.objects.create(
        transcript=transcript, run=check, speaker="Speaker 1", at=0.0, lines_after=1
    )
    same = viewer.split_speaker(
        transcript, "Speaker 1", 0.0, by=owner, into="Speaker 1"
    )
    assert same == ""
    second.refresh_from_db()


def test_the_pages_carry_the_picker():
    picker = (HERE / "static" / "picker.js").read_text(encoding="utf-8")
    assert "window.Picker = " in picker and "On this call" in picker
    assert "In this case, not yet on this call" in picker and "Someone new" in picker
    assert "Manage speakers" in picker
    page = (HERE / "static" / "speakers-page.js").read_text(encoding="utf-8")
    assert "window.Picker.open({" in page and "not-voice" in page
    assert "newSpeaker: true" in page
    template = (HERE / "templates" / "speakers-page.html").read_text(encoding="utf-8")
    assert 'class="ghost tiny not-voice"' in template
    assert "this label mixes people" in template
    assert "picker.js" in template and "preview.js" in template
    recording_page = (HERE / "templates" / "viewer.html").read_text(encoding="utf-8")
    assert "picker.js" in recording_page
    script = (HERE / "static" / "viewer.js").read_text(encoding="utf-8")
    assert "speaker-row" in script and "function pickSpeakerFor" in script
    css = (HERE / "static" / "app.css").read_text(encoding="utf-8")
    assert ".picker .opt" in css
    assert ".picker { position: fixed; left: 0; right: 0; bottom: 0" in css


def test_a_runs_unreadable_vectors_never_break_a_hand_move(
    admin, tmp_path, settings, client
):
    """Found on the local walk: a malformed vectors field raised through
    move_line and the line endpoint answered 500 after the line had moved."""
    recording = a_recording(admin, tmp_path, settings)
    transcript = recording.transcript
    SpeakerCheck.objects.create(
        transcript=transcript, state="done", voices={"stretches": [1, 2]}
    )
    line = transcript.segments.order_by("start").first()
    signed_in(client, admin)
    answer = client.post(
        f"/recording/{recording.pk}/segment/{line.pk}/speaker",
        data=json.dumps({"speaker": "Speaker 2"}),
        content_type="application/json",
    )
    assert answer.status_code == 200 and answer.json()["changed"] == 1
    line.refresh_from_db()
    assert line.speaker == "Speaker 2"
    assert speaker_check.rescore(transcript) == 0


def test_the_pages_hold_still_while_a_picker_is_open():
    """v1.142.1: the picker says when it opens and closes, and neither page
    scrolls to a playing sample while it is open."""
    picker = (HERE / "static" / "picker.js").read_text(encoding="utf-8")
    assert 'new CustomEvent("picker-open"' in picker
    assert 'new CustomEvent("picker-close"' in picker
    for name in ("viewer.js", "speakers-page.js"):
        script = (HERE / "static" / name).read_text(encoding="utf-8")
        assert 'addEventListener("picker-open"' in script, name
        assert 'addEventListener("picker-close"' in script, name
        assert "!holding" in script, name


def test_one_sound_at_a_time():
    """v1.142.2: a sample on the recording page stops at its end, and a
    Preview pauses the page's player before it plays."""
    viewer = (HERE / "static" / "viewer.js").read_text(encoding="utf-8")
    assert "window.VIEWER.playRange = function (start, end)" in viewer
    assert "window.VIEWER.playRange(start, end); }" in viewer
    page = (HERE / "static" / "speakers-page.js").read_text(encoding="utf-8")
    assert "V.pause = pause;" in page
    preview = (HERE / "static" / "preview.js").read_text(encoding="utf-8")
    assert 'typeof window.VIEWER.pause === "function"' in preview
    picker = (HERE / "static" / "picker.js").read_text(encoding="utf-8")
    assert "sample.start - 0.5" in picker and "sample.end + 0.5" in picker


def test_the_speakers_page_breathes():
    """v1.143.0 (the drawing phase-5-speakers-page-breathes.html): the slim
    card, the picker beside the card, the hand-over on two lines, and the
    proposal rows measured on the reading pane."""
    template = (HERE / "templates" / "speakers-page.html").read_text(encoding="utf-8")
    assert 'class="sample-line"' in template and "name-or-merge" in template
    assert "namebox" not in template and "same person as" not in template
    assert 'data-quote="{{ sample.quote }}"' in template
    page = (HERE / "static" / "speakers-page.js").read_text(encoding="utf-8")
    assert "function nameOrMerge" in page and 'question: name + " is"' in page
    assert "beside: card" in page and "split-from" in page
    assert "<div class='acts'>" in page and "Split here..." in page
    picker = (HERE / "static" / "picker.js").read_text(encoding="utf-8")
    assert "function place()" in page or "function place()" in picker
    assert 'box.classList.toggle("beside", beside)' in picker
    assert "suggestedPill(options, one.name)" in picker
    css = (HERE / "static" / "app.css").read_text(encoding="utf-8")
    assert ".picker.beside, .picker.below { position: fixed" in css
    assert "@container reading (max-width: 1299px)" in css
    assert ".sp-card .sample-line" in css
