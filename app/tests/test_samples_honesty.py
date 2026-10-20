"""The samples' honesty (the voice plan's section 12, v1.141.0): a line
whose timing is a guess is never a Sample and carries a pill, the Speakers
page lights the words and plays with a margin, and the one run says why no
names were suggested."""

from pathlib import Path

import pytest
from core import assistant, settings_store, speaker_check, speakers_page
from core.assistant import SpeakerCheck
from core.jobs import Segment
from core.models import User
from core.speakers_page import Line
from tests.helpers import signed_in
from tests.test_prepare import a_recording

PASSWORD = "a-long-enough-password"
HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent


@pytest.fixture
def admin(db):
    return User.objects.create_local_admin("adm", PASSWORD)


def test_a_repeated_phrase_or_thin_words_make_the_timing_a_guess():
    assert speakers_page.repeated_phrase("Hey, hold on, hold on, hold on.")
    assert speakers_page.repeated_phrase("no no no")
    assert speakers_page.repeated_phrase("I told you, I told you, I told you.")
    # Twice is speech; three times is the recogniser's stutter.
    assert not speakers_page.repeated_phrase("hold on, hold on, what?")
    assert not speakers_page.repeated_phrase("Tell me about the car.")
    # The usual pace is the median over lines of a second or more.
    rows = [(0.0, 2.0, "one two three four"), (3.0, 5.0, "five six seven eight")]
    assert speakers_page.usual_pace(rows) == 2.0
    assert speakers_page.usual_pace([]) == 0.0
    # Under two fifths of that pace over two seconds or more is a guess;
    # a short line, or a line at pace, is not.
    assert speakers_page.timing_guess("two words", 0.0, 4.0, 2.0)
    assert not speakers_page.timing_guess("two words", 0.0, 1.5, 2.0)
    assert not speakers_page.timing_guess("one two three four five six", 0.0, 4.0, 2.0)
    assert not speakers_page.timing_guess("two words", 0.0, 4.0, 0.0)


def test_a_guessed_line_is_passed_over_for_a_sample_while_a_sure_one_remains():
    sure = [Line(0.0, 4.0), Line(10.0, 14.0), Line(20.0, 24.0), Line(30.0, 34.0)]
    guessed = [Line(5.0, 9.0, True), Line(15.0, 19.0, True)]
    picked = speakers_page.pick_samples(sorted(sure + guessed, key=lambda o: o.start))
    assert all(not one.guess for one in picked) and len(picked) == 3
    # With nothing sure, the guessed lines are what there is.
    assert speakers_page.pick_samples(guessed) == guessed


def test_the_lines_the_pages_read_carry_the_flag_and_the_cards_skip_it(
    admin, tmp_path, settings, client
):
    recording = a_recording(admin, tmp_path, settings)
    transcript = recording.transcript
    stutter = Segment.objects.create(
        transcript=transcript,
        start=30.0,
        end=33.5,
        text="Hey, hold on, hold on, hold on.",
        speaker="Speaker 2",
        speaker_label="SPEAKER_01",
    )
    assert speakers_page.guesses(transcript) == {stutter.pk}
    signed_in(client, admin)
    rows = client.get(f"/recording/{recording.pk}/segments").json()["segments"]
    flags = {row["id"]: row["guess"] for row in rows}
    assert flags[stutter.pk] is True and sum(flags.values()) == 1
    page = client.get(f"/recording/{recording.pk}/speakers").content.decode()
    # Speaker 2 has a sure line at 12.4 and the stutter: the sample is the sure one.
    assert 'data-start="12.4"' in page and 'data-start="30.0"' not in page


def test_the_one_run_says_why_no_names_when_fewer_than_two_are_unnamed(
    admin, tmp_path, settings, client
):
    settings_store.set_to("assistant_available", True)
    settings_store.set_to("speaker_check_available", True)
    settings_store.set_to("suggestions_available", True)
    recording = a_recording(admin, tmp_path, settings)
    transcript = recording.transcript
    transcript.segments.filter(speaker="Speaker 1").update(speaker="Detective Ruiz")
    check = SpeakerCheck.objects.create(
        transcript=transcript, asked_by=admin, state=assistant.DONE, second_look={}
    )
    speaker_check._names_pass(check)
    check.refresh_from_db()
    assert check.second_look == {"names": None, "names_state": "too_few"}
    assert not transcript.suggestion_runs.exists()
    signed_in(client, admin)
    run = client.get(f"/recording/{recording.pk}/assistant").json()["speaker_check"][
        "run"
    ]
    assert run["names"] is None and run["names_state"] == "too_few"


def test_the_pages_carry_the_release():
    script = (HERE / "static" / "speakers-page.js").read_text(encoding="utf-8")
    assert '"/segments")' in script and "segments?words=0" not in script
    assert "var MARGIN = 0.5;" in script
    assert "segment.start - MARGIN" in script and "segment.end + MARGIN" in script
    assert "the timing of these words is a guess" in script
    assert "fewer than two speakers are still unnamed" in script
    assert "function wordsOf(segment)" in script
    css = (HERE / "static" / "app.css").read_text(encoding="utf-8")
    assert ".sp-read .seg .pill.guess" in css
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## v1.141.0" in changelog
    glossary = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    assert "never a line whose timing is a guess" in glossary
    guide = (ROOT / "docs" / "user-guide.md").read_text(encoding="utf-8")
    assert "the timing of these words is a guess" in guide
