"""v1.50.0: the Speakers page (Phase 5, chapter 1).

The rules checked here: one card per Speaker in the order they first spoke,
with its lines, its talking time and its three Samples chosen by the rule;
the fragment hint names a bigger Speaker the small one never overlaps; the
progress line counts the named; the page is reached from the strip and the
window route shows the same page; a new Person made from the page can take
its Role at once, and one that exists keeps its own; nothing about it is
stored; and the words are in the glossary and the guide.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from core import settings_store, speakers_page
from core.cases import Case
from core.jobs import Segment, Transcript
from core.models import LoginSession, User
from core.people import Person
from core.recordings import Batch, MediaState, Recording
from core.speakers_page import Line

APP = Path(__file__).resolve().parent.parent
ROOT = APP.parent
PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("asker", PASSWORD)


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


LINES = (
    # start, end, speaker: Speaker 3 talks only in Speaker 1's gaps, and
    # Speaker 10 first speaks after Speaker 2 though its name sorts before.
    (0.0, 4.0, "Speaker 1"),
    (4.5, 7.0, "Speaker 2"),
    (8.0, 9.0, "Speaker 3"),
    (10.0, 16.0, "Speaker 1"),
    (12.0, 14.0, "Speaker 10"),
    (17.0, 18.0, "Speaker 3"),
    (19.0, 25.0, "Speaker 1"),
    (26.0, 27.5, "Speaker 2"),
    (30.0, 33.0, "Speaker 1"),
)


def a_recording(person, video=True, with_transcript=True, case=None):
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        case=case,
        title="Stop",
        original_filename="bodycam.mp4" if video else "call.m4a",
        media_state=MediaState.READY,
        duration_seconds=40.0,
        diarize=True,
        playback_ready=True,
    )
    recording.folder.mkdir(parents=True, exist_ok=True)
    (recording.folder / ("playback.mp4" if video else "playback.m4a")).write_bytes(
        b"not really media"
    )
    if with_transcript:
        transcript = Transcript.objects.create(recording=recording, language="en")
        for start, end, speaker in LINES:
            Segment.objects.create(
                transcript=transcript,
                start=start,
                end=end,
                text=f"words at {start}",
                speaker=speaker,
                speaker_label=speaker.upper().replace(" ", "_"),
            )
    return recording


# The arithmetic --------------------------------------------------------------------


def test_samples_come_one_from_each_third_nearest_four_seconds():
    lines = [
        Line(0, 1),  # too short
        Line(2, 12),  # too long
        Line(13, 16),  # 3 s: the first third's pick
        Line(20, 26),  # 6 s
        Line(27, 31.5),  # 4.5 s: the middle third's pick
        Line(33, 34),
        Line(40, 40.5),  # the last third holds nothing between 2 and 8 s...
        Line(41, 41.8),
        Line(42, 43.5),  # ...so its longest is taken
    ]
    chosen = speakers_page.pick_samples(lines)
    assert [(one.start, one.end) for one in chosen] == [
        (13, 16),
        (27, 31.5),
        (42, 43.5),
    ]
    # Few lines: all of them, in order.
    assert speakers_page.pick_samples(lines[:2]) == lines[:2]
    assert speakers_page.pick_samples([]) == []


def test_overlap_allows_a_touch_of_half_a_second():
    a = [Line(0, 10), Line(20, 30)]
    assert speakers_page.overlaps(a, [Line(9.6, 15)]) is False
    assert speakers_page.overlaps(a, [Line(9.4, 15)]) is True
    assert speakers_page.overlaps(a, [Line(12, 19)]) is False
    assert speakers_page.overlaps(a, [Line(25, 26)]) is True
    assert speakers_page.overlaps([], a) is False


def test_talking_time_reads_plainly():
    assert speakers_page.talking_text(41.4) == "41 s"
    assert speakers_page.talking_text(303.0) == "5 min 03 s"
    assert speakers_page.is_named("Speaker 2") is False
    assert speakers_page.is_named("Side 1 Speaker 2") is False
    assert speakers_page.is_named("Ofc. Ruiz") is True


@pytest.mark.django_db
def test_cards_in_the_order_they_first_spoke_with_the_hint(person):
    recording = a_recording(person)
    looks = [
        {"name": "Speaker 1", "colour": "var(--sp1)", "role": ""},
        {"name": "Speaker 10", "colour": "var(--sp2)", "role": ""},
        {"name": "Speaker 2", "colour": "var(--sp3)", "role": ""},
        {"name": "Speaker 3", "colour": "var(--sp4)", "role": ""},
    ]
    made = speakers_page.cards(recording.transcript, looks)
    assert [one["name"] for one in made] == [
        "Speaker 1",
        "Speaker 2",
        "Speaker 3",
        "Speaker 10",
    ]
    first = made[0]
    assert first["lines"] == 4 and first["talking"] == 19.0
    assert first["talking_text"] == "19 s" and first["first_clock"] == "0:00"
    assert first["label"] == "SPEAKER_1" and first["colour"] == "var(--sp1)"
    assert first["named"] is False and first["small"] is True
    # The last third holds a 6 s line and a 3 s one; 3 s is nearer four.
    assert [one["start"] for one in first["samples"]] == [0.0, 10.0, 30.0]
    # Speaker 3 never talks while Speaker 1 does and has fewer lines: the hint.
    third = made[2]
    assert third["hint_other"] == "Speaker 1"
    # Speaker 2 never overlaps Speaker 1 either. Speaker 10 talks over
    # Speaker 1, so the next biggest Speaker it never overlaps is named.
    assert made[1]["hint_other"] == "Speaker 1"
    assert made[3]["hint_other"] == "Speaker 2"
    # The biggest Speaker has nobody bigger to be a fragment of.
    assert first["hint_other"] == ""


# The page --------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_page_is_reached_from_the_strip_and_shows_the_cards(person, client):
    recording = a_recording(person)
    signed_in(client, person)

    page = client.get(f"/recording/{recording.pk}").content.decode()
    assert 'id="manage-speakers"' in page and "Manage speakers" in page
    assert f'data-href="/recording/{recording.pk}/speakers"' in page
    assert "tag-speakers" not in page and "Tag speakers" not in page

    answer = client.get(f"/recording/{recording.pk}/speakers")
    assert answer.status_code == 200
    body = answer.content.decode()
    assert 'class="viewer speakers-page"' in body
    assert len(re.findall(r'class="sp-card( unnamed)?"', body)) == 4
    assert len(re.findall(r'class="lane( small)?"', body)) == 4
    assert '<kbd class="k">1</kbd>' in body and '<kbd class="k">4</kbd>' in body
    assert "0 of 4 speakers named" in body
    assert 'id="lanes"' in body and 'id="transcript"' in body and 'id="reading"' in body
    assert 'id="done"' in body and f'href="/recording/{recording.pk}"' in body
    assert 'id="open-in-window"' in body
    assert '<video id="player"' in body and 'id="play"' in body
    assert 'data-zoom="0"' in body and 'data-zoom="30"' in body
    assert 'class="tiny sample" data-start="0.0" data-end="4.0"' in body
    assert "Never speaks while Speaker 1 does" in body
    assert 'data-onto="Speaker 1"' in body
    assert "speakers-page.js" in body and "inWindow: false" in body
    # Speaker 10 is drawn last, and its engine label beside it.
    assert body.index('data-name="Speaker 2"') < body.index('data-name="Speaker 10"')
    assert "SPEAKER_10" in body
    # No Suggest names while the assistant is off; no people box outside a case.
    assert 'id="suggest-names"' not in body and "Known in this case" not in body
    # A name box on every card, open on the unnamed ones.
    assert body.count('class="namebox"') == 4 and 'class="namebox" hidden' not in body

    # Sound alone: an audio element and the waveform strip.
    sound = a_recording(person, video=False)
    body = client.get(f"/recording/{sound.pk}/speakers").content.decode()
    assert '<audio id="player"' in body and 'id="wave"' in body and "<video" not in body
    assert 'class="sp-desk sound"' in body

    # Nothing to tag: the line and the way back.
    waiting = a_recording(person, with_transcript=False)
    body = client.get(f"/recording/{waiting.pk}/speakers").content.decode()
    assert "no speaker labels to tag" in body and "Back to the recording" in body
    assert 'id="cards"' not in body

    # A recording that is not there sends the person home.
    gone = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/recording/{gone}/speakers").status_code == 302


@pytest.mark.django_db
def test_the_window_route_shows_the_page_and_names_count_as_named(person, client):
    settings_store.set_to("assistant_available", True)
    settings_store.set_to("suggestions_available", True)
    recording = a_recording(person)
    signed_in(client, person)
    body = client.get(f"/recording/{recording.pk}/window/speakers").content.decode()
    assert 'class="viewer speakers-page window"' in body
    assert "inWindow: true" in body and 'id="cards"' in body
    assert 'id="done"' not in body and 'id="open-in-window"' not in body
    assert "roster" not in body and "nowbox" not in body
    assert 'id="suggest-names"' in body

    # A name, and the progress line moves; the named card's box starts hidden.
    client.post(
        f"/recording/{recording.pk}/speakers",
        data=json.dumps({"from": "Speaker 1", "to": "Ofc. Ruiz"}),
        content_type="application/json",
    )
    body = client.get(f"/recording/{recording.pk}/speakers").content.decode()
    assert "1 of 4 speakers named" in body
    assert 'data-name="Ofc. Ruiz"' in body and 'class="namebox" hidden' in body
    assert body.count('class="namebox" hidden') == 1
    assert "Undo" in body and "renaming Speaker 1 to Ofc. Ruiz" in body


@pytest.mark.django_db
def test_a_new_person_from_the_page_takes_its_role_and_an_old_one_keeps_it(
    person, client
):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("speaker_roles", "Officer\nDefendant")
    case = Case.objects.create(name="State v. Nobody", owner=person)
    Person.objects.create(
        case=case, name="M. Okafor", role="Defendant", added_by=person
    )
    recording = a_recording(person, case=case)
    signed_in(client, person)

    body = client.get(f"/recording/{recording.pk}/speakers").content.decode()
    assert "Known in this case" in body and 'data-name="M. Okafor"' in body
    assert "<option>Officer</option>" in body and "New name takes the role" in body

    url = f"/recording/{recording.pk}/speakers"
    # A new name with a Role on the list: the Person is made with it.
    answer = client.post(
        url,
        data=json.dumps({"from": "Speaker 1", "to": "Ofc. Ruiz", "role": "Officer"}),
        content_type="application/json",
    )
    assert answer.status_code == 200
    assert Person.objects.get(case=case, name="Ofc. Ruiz").role == "Officer"
    # A Role not on the list is ignored.
    client.post(
        url,
        data=json.dumps({"from": "Speaker 2", "to": "Dispatch", "role": "Wizard"}),
        content_type="application/json",
    )
    assert Person.objects.get(case=case, name="Dispatch").role == ""
    # A Person that exists keeps its own Role whatever is sent.
    client.post(
        url,
        data=json.dumps({"from": "Speaker 3", "to": "M. Okafor", "role": "Officer"}),
        content_type="application/json",
    )
    assert Person.objects.get(case=case, name="M. Okafor").role == "Defendant"
    assert Person.objects.filter(case=case).count() == 3


def test_the_words_the_stylesheet_and_the_guides_carry_the_page():
    glossary = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    for word in ("**Speakers page**:", "**Lane**:", "**Sample**:", "**Voice print**:"):
        assert word in glossary, word
    css = (APP / "static" / "app.css").read_text(encoding="utf-8")
    assert ".sp-desk {" in css and ".sp-lanes .lane .track i {" in css
    assert ".speakers-window" not in css
    script = (APP / "static" / "speakers-page.js").read_text(encoding="utf-8")
    for piece in (
        "stopAt = segment.end",
        'kind: "window-time"',
        "lanes-zoom",
        '"dragstart"',
        "function outOfTheMiddle(",
        "/suggest",
        'role: role || ""',
    ):
        assert piece in script, piece
    old = (APP / "static" / "viewer-window.js").read_text(encoding="utf-8")
    assert "roster" not in old and 'getElementById("player")' not in old
    guide = (ROOT / "docs" / "user-guide.md").read_text(encoding="utf-8")
    assert "**Manage speakers**" in guide and "Tag speakers" not in guide
    spec = (ROOT / "docs" / "spec" / "SPEC-PHASE-5.md").read_text(encoding="utf-8")
    assert "## 1. The Speakers page" in spec and "## 2. Voice prints" in spec
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## v1.50.0" in changelog
