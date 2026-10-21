"""The guided Speakers page (Phase 5 chapter 3, "The guided page", v1.148.0):
the Speakers address draws the guide, the question and its context from
the check's state; the classic page stays at /classic; the script keeps
the six rules' pieces and acts only through the endpoints the page had."""

from pathlib import Path

import pytest
from core import settings_store
from tests.helpers import signed_in
from tests.test_people import a_case as _a_case  # noqa: F401
from tests.test_people import a_recording
from tests.test_people import owner as _owner  # noqa: F401

HERE = Path(__file__).resolve().parents[1]


@pytest.fixture
def owner(_owner):  # noqa: F811
    return _owner


@pytest.fixture
def a_case(_a_case):  # noqa: F811
    return _a_case


def test_the_speakers_address_is_the_guided_page_and_classic_is_kept(
    owner, a_case, client
):
    recording = a_recording(owner, a_case)
    signed_in(client, owner)
    page = client.get(f"/recording/{recording.pk}/speakers").content.decode()
    assert 'id="sg"' in page and 'id="guide"' in page
    assert 'id="sg-focus"' in page and 'id="sg-context"' in page
    assert 'id="sg-next"' in page and 'id="sg-back"' in page and 'id="sg-undo"' in page
    assert "speakers-guided.js" in page and "picker.js" in page
    assert 'id="sg-cards"' in page and "Done for now" in page
    assert f"/recording/{recording.pk}/speakers/classic" in page
    assert "Lanes, zoom and swap (the classic page)" in page
    # The classic page is the page as it was, at its own address.
    classic = client.get(f"/recording/{recording.pk}/speakers/classic").content.decode()
    assert 'class="sp-cast"' in classic and 'id="sg"' not in classic
    assert 'class="viewer speakers-page"' in classic
    # POST at the Speakers address is still the rename and merge endpoint.
    answer = client.post(
        f"/recording/{recording.pk}/speakers",
        data='{"from": "Speaker 1", "to": "Dana Reyes", "role": ""}',
        content_type="application/json",
    )
    assert answer.status_code == 200


def test_the_no_type_line_and_the_empty_page_sit_in_the_guided_frame(
    owner, a_case, client
):
    settings_store.set_to("speaker_check_available", True)
    settings_store.set_to("voices_types", "Jail call")
    recording = a_recording(owner, a_case)
    signed_in(client, owner)
    page = client.get(f"/recording/{recording.pk}/speakers").content.decode()
    assert "This recording has no type, so the check reads the words alone" in page
    recording.transcript.segments.all().delete()
    page = client.get(f"/recording/{recording.pk}/speakers").content.decode()
    assert "no speaker labels to tag" in page and 'id="guide"' not in page
    settings_store.set_to("speaker_check_available", False)


def test_the_script_keeps_the_six_rules_and_the_old_endpoints():
    script = (HERE / "static" / "speakers-guided.js").read_text(encoding="utf-8")
    # Where am I, what now, what next, how back.
    for piece in (
        '"Step " + step + " of " + steps.length',
        '"Voice " + (index + 1) + " of "',
        '"Line " + (index + 1) + " of "',
        "Next voice",
        "Next line",
        "Finish",
        "Skip this voice",
        "Leave it for now",
    ):
        assert piece in script, piece
    # The answers in plain words, ranked.
    assert "sounds very like" in script and "sounds a bit like" in script
    assert "a name said on the call" in script and "Who is this?" in script
    assert "Whose line is this?" in script and "Split at the word" in script
    # Every act goes through the endpoints the page already had.
    for url in (
        "/assistant",
        "/segments?words=0",
        '/speakers"',
        "/speakers/undo",
        "/stage/",
        '/corrections/" + verdict + "-many',
        "/corrections/accept-many",
        "/voice-match/",
        "/book-check/",
        '/book-check"',
        "/segment/",
        '/speaker-check"',
    ):
        assert url in script, url
    # Nothing accepts everything: the one shortcut is the lines voice and
    # words agree on, and the words-first one the voice backs.
    assert "Accept all" in script and "accept-all" not in script
    css = (HERE / "static" / "app.css").read_text(encoding="utf-8")
    assert (
        ".sg-guide {" in css
        and ".sg-choice.best" in css
        and "@media (max-width: 900px)" in css
    )
    template = (HERE / "templates" / "speakers-guided.html").read_text(encoding="utf-8")
    assert "speakers-classic" in template and "type-hint.js" in template
