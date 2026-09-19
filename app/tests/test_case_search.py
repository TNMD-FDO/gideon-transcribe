"""v1.65.0: the dashboard line, search across a case, and Find on the
incident page (Phase 7, chapter 3).

The rules checked here: the line shows a pill for everything that has a
state and nothing otherwise, each a link; the Search tab reads six kinds,
words all present or a phrase in quotes, hits grouped by where they live
with the words marked, every hit a place that opens, the first two hundred
of a kind; Phase 2's ?q= opens the Search tab; Find answers moments on the
incident clock and skips a camera not synced; and nothing of a search is
ever written to the audit log.
"""

from __future__ import annotations

import json

import pytest
from core import (
    case_search,
    chronology,
    dashboard,
    incident_assistant,
    incidents,
    settings_store,
)
from core.assistant import Summary
from core.audit import Row
from core.cases import Case
from core.clips import Clip
from core.jobs import Job, JobState, Segment, Transcript
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording

PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"


@pytest.fixture(autouse=True)
def switched_on(db):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("incidents", True)
    settings_store.set_to("assistant_available", True)
    settings_store.set_to("clips_available", True)


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("asker", PASSWORD)


@pytest.fixture
def a_case(person):
    return Case.objects.create(owner=person, name="Traffic stop")


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def stamp(time: str, camera: str):
    return {
        "date": "06/07/2025",
        "time": time,
        "camera": camera,
        "at": 2.0,
        "checked": True,
    }


def video(person, case, title, *, seconds=600.0, stamp=None, lines=()):
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        case=case,
        title=title,
        original_filename=f"{title}.mp4",
        media_state=MediaState.READY,
        duration_seconds=seconds,
        playback_ready=True,
        stamp=stamp,
        probe={},
    )
    recording.folder.mkdir(parents=True, exist_ok=True)
    (recording.folder / "playback.mp4").write_bytes(b"not really media")
    if lines:
        transcript = Transcript.objects.create(recording=recording, language="en")
        for start, speaker, text in lines:
            Segment.objects.create(
                transcript=transcript,
                start=start,
                end=start + 4,
                text=text,
                speaker=speaker,
                speaker_label=speaker.upper().replace(" ", "_"),
            )
    return recording


@pytest.fixture
def incident(person, a_case):
    first = video(
        person,
        a_case,
        "first",
        stamp=stamp("21:56:19", "BWC2-1"),
        lines=(
            (10.0, "Officer Hale", "Step out of the vehicle for me."),
            (30.0, "Officer Hale", "I got, I got gun, I got gun."),
        ),
    )
    second = video(
        person,
        a_case,
        "second",
        stamp=stamp("22:01:00", "BWC2-2"),
        lines=((5.0, "Speaker 1", "Stay in the car, please."),),
    )
    return incidents.make(a_case, "Stop", [first, second], by=person)


# The dashboard line ---------------------------------------------------------------


def test_the_line_shows_nothing_when_nothing_is_pending(person, a_case, client):
    assert dashboard.pills(a_case) == []
    signed_in(client, person)
    page = client.get(f"/case/{a_case.pk}").content.decode()
    assert 'id="dashboard-line" hidden' in page


def test_the_line_has_a_pill_for_everything_with_a_state(
    person, a_case, incident, client
):
    first = a_case.recordings.get(title="first")
    Job.objects.create(recording=first, batch=first.batch, state=JobState.RUNNING)
    cams = {one.camera_id(): one for one in incident.cameras.all()}
    # An incident not synced (its cameras placed by the app's guess), an
    # event to check, a proposal waiting, a clip rendering and one failed.
    incidents.IncidentCamera.objects.filter(pk=cams["BWC2-2"].pk).update(
        placed=incidents.GUESS
    )
    chronology.add(
        incident,
        {"at": "10", "text": "Asked out", "to_check": "yes"},
        by=person,
    )
    chronology.Event.objects.create(
        incident=incident, at=20.0, text="Maybe", source="assistant", proposed=True
    )
    Clip.objects.create(recording=first, user=person, title="One", start=0, end=5)
    Clip.objects.create(
        recording=first, user=person, title="Two", start=0, end=5, state="failed"
    )
    pills = dashboard.pills(a_case)
    words = [one["words"] for one in pills]
    assert words == [
        "1 transcribing",
        "1 incident not synced",
        "1 event to check",
        "1 proposed event waiting",
        "1 clip rendering",
        "1 clip failed",
    ]
    tones = {one["words"]: one["tone"] for one in pills}
    assert tones["1 incident not synced"] == "warn" and tones["1 clip rendering"] == ""
    hrefs = {one["words"]: one["href"] for one in pills}
    assert hrefs["1 clip failed"].endswith("?tab=clips")
    assert hrefs["1 event to check"].endswith("?tab=incidents")
    assert hrefs["1 transcribing"] == f"/case/{a_case.pk}"
    signed_in(client, person)
    page = client.get(f"/case/{a_case.pk}?tab=speakers").content.decode()
    assert "1 event to check" in page and 'id="dashboard-line"' in page
    assert 'id="dashboard-line" hidden' not in page


# Search across a case -------------------------------------------------------------


def test_terms_are_words_all_present_or_a_phrase_in_quotes():
    assert case_search.terms("gun  backpack") == ["gun", "backpack"]
    assert case_search.terms('"I got gun"') == ["I got gun"]
    assert case_search.terms("“I got gun”") == ["I got gun"]
    assert case_search.terms('""') == []
    assert str(case_search.mark("A gun, a Gun.", ["gun"])) == (
        "A <mark>gun</mark>, a <mark>Gun</mark>."
    )
    assert str(case_search.mark("<b>", ["b"])) == "&lt;<mark>b</mark>&gt;"


def test_the_search_reads_six_kinds_and_groups_by_where_they_live(
    person, a_case, incident, client
):
    first = a_case.recordings.get(title="first")
    cams = {one.camera_id(): one for one in incident.cameras.all()}
    event = chronology.add(
        incident,
        {
            "at": "30",
            "text": "An officer said he had found a gun",
            "note": "The gun question, page 4",
            "camera": str(cams["BWC2-1"].pk),
        },
        by=person,
    )
    chronology.Event.objects.filter(pk=event.pk).update(
        why="A weapon changes the stop."
    )
    incidents.set_about(incident, "The stop where a gun was found.", by=person)
    memo = incident_assistant.IncidentMemo.objects.create(
        incident=incident,
        state="done",
        text="Summary:\nAn officer found a gun at [21:56:49].\n\nThe cameras:\nTwo.",
    )
    Summary.objects.create(
        recording=first,
        template_name="Body camera",
        state="done",
        text="The officer found a gun.\n\nNothing else happened.",
    )
    Clip.objects.create(
        recording=first, user=person, title="The gun moment", start=0, end=5
    )

    got = case_search.search(a_case, "gun")
    assert got["total"] == 7
    assert [(k["key"], k["count"]) for k in got["kinds"]] == [
        ("words", 1),
        ("events", 2),
        ("notes", 1),
        ("memos", 1),
        ("summaries", 1),
        ("clips", 1),
    ]
    heads = [g["head"] for g in got["groups"]]
    assert heads == ["first", "Stop"]
    recording_hits = got["groups"][0]["hits"]
    assert [h["when"] for h in recording_hits] == ["00:00:30", "Summary", "Clip"]
    assert recording_hits[0]["url"] == f"/recording/{first.pk}?t=30.0"
    assert recording_hits[0]["all_cameras"].startswith(incident.url() + "?t=")
    assert "<mark>gun</mark>" in str(recording_hits[0]["text"])
    assert "?panel=summary&summary=" in recording_hits[1]["url"]
    assert recording_hits[2]["url"].endswith(
        "?tab=clips#clip-" + str(Clip.objects.get(title="The gun moment").pk)
    )
    incident_hits = got["groups"][1]["hits"]
    # The first camera's stamp reads 21:56:19 two seconds in, so 30 seconds on
    # the incident clock is 21:56:47.
    assert [h["when"] for h in incident_hits] == [
        "About",
        "21:56:47",
        "21:56:47",
        "Memo",
    ]
    assert "<mark>gun</mark>" in str(incident_hits[1]["text"])
    assert "weapon" in str(incident_hits[1]["under"])
    assert incident_hits[2]["who"] == "Note, asker"
    assert incident_hits[3]["url"] == f"{incident.url()}?tab=memo&para=1"
    assert memo.pk  # the memo hit's paragraph is the second block
    # A kind narrows; words all present; a phrase exactly.
    assert case_search.search(a_case, "gun", "notes")["groups"][0]["head"] == "Stop"
    # The line (its speaker is Officer Hale), the event, the memo, the summary.
    assert case_search.search(a_case, "gun officer")["total"] == 4
    assert case_search.search(a_case, '"got gun"')["total"] == 1
    assert case_search.search(a_case, "g")["short"] is True
    # The page: the tab, the pills, the old ?q= landing on it, never logged.
    signed_in(client, person)
    page = client.get(f"/case/{a_case.pk}?tab=search&q=gun").content.decode()
    assert "7 hits for" in page and "Words (1)" in page and "<mark>gun</mark>" in page
    assert 'class="tab on">Search</a>' in page
    page = client.get(f"/case/{a_case.pk}?q=gun").content.decode()
    assert 'class="tab on">Search</a>' in page and "7 hits for" in page
    page = client.get(f"/case/{a_case.pk}").content.decode()
    assert "Search this case" not in page and 'name="q"' not in page
    for row in Row.objects.all():
        assert "gun" not in json.dumps(row.details).lower()


def test_the_search_keeps_the_first_two_hundred_of_a_kind(person, a_case):
    recording = video(person, a_case, "long")
    transcript = Transcript.objects.create(recording=recording, language="en")
    Segment.objects.bulk_create(
        Segment.objects.model(
            transcript=transcript, start=float(n), end=n + 1.0, text=f"gun {n}"
        )
        for n in range(205)
    )
    got = case_search.search(a_case, "gun")
    assert got["kinds"][0]["count"] == 200 and got["more"] is True
    assert len(got["groups"][0]["hits"]) == 200


# Find on the incident page --------------------------------------------------------


def test_find_answers_moments_on_the_incident_clock(person, a_case, incident, client):
    cams = {one.camera_id(): one for one in incident.cameras.all()}
    chronology.add(
        incident,
        {"at": "40", "text": "Gun found", "camera": str(cams["BWC2-1"].pk)},
        by=person,
    )
    incident_assistant.IncidentMemo.objects.create(
        incident=incident,
        state="done",
        text="Summary:\nAn officer found a gun at [21:56:49].",
    )
    signed_in(client, person)
    url = f"/case/{a_case.pk}/incident/{incident.pk}/find"
    got = client.get(url, {"q": "gun"}).json()
    kinds = [(h["kind"], h["at"]) for h in got["hits"]]
    # The memo's citation [21:56:49] is 32 seconds on the clock (the first
    # camera starts at 21:56:17).
    assert kinds == [("words", 30.0), ("memo", 32.0), ("event", 40.0)]
    words = got["hits"][0]
    assert words["camera"] == str(cams["BWC2-1"].pk) and words["camera_id"] == "BWC2-1"
    assert "<mark>gun</mark>" in words["html"] and words["line_at"] == 30.0
    assert got["hits"][1]["para"] == 1 and got["hits"][2]["event"]
    assert got["skipped"] == 0
    # A camera not synced is not searched, and the answer says so.
    incidents.IncidentCamera.objects.filter(pk=cams["BWC2-2"].pk).update(
        placed=incidents.GUESS
    )
    got = client.get(url, {"q": "car"}).json()
    assert got["hits"] == [] and got["skipped"] == 1
    assert client.get(url, {"q": "g"}).json()["hits"] == []
    for row in Row.objects.all():
        assert "gun" not in json.dumps(row.details).lower()
    # The page opens on a tab at a paragraph, and carries the Find box.
    page = client.get(
        f"/case/{a_case.pk}/incident/{incident.pk}?tab=memo&para=1"
    ).content.decode()
    assert 'openTab: "memo"' in page and 'para: "1"' in page and 'id="find"' in page
    page = client.get(
        f"/case/{a_case.pk}/incident/{incident.pk}?tab=nonsense&para=x"
    ).content.decode()
    assert 'openTab: ""' in page and 'para: ""' in page
