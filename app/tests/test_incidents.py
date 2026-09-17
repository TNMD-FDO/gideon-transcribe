"""v1.58.0: Incidents (Phase 6, chapter 1).

The rules checked here: videos whose clocks overlap are offered as one
incident, and an offer put away stays away; making an incident places the
clocked cameras and sets the clock from the first checked one; a camera is
placed by hand, from its file, and from its clock, and the pill says which;
the case page carries the strip and the two columns only while Incidents
is on; the incident page answers its owner and its act endpoint changes the
rows; a recording that leaves the case leaves its incident; All cameras
appears for a placed camera; the stamp is read early only when the office
allows it; the sound match finds a known shift; and the words are in the
glossary, the guide and the catalogue.
"""

from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np
import pytest
from core import cases, incidents, settings_store, sound_match
from core.cases import Case
from core.incidents import Incident
from core.jobs import Segment, Transcript
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording, Side

APP = Path(__file__).resolve().parent.parent
ROOT = APP.parent
PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"


@pytest.fixture(autouse=True)
def incidents_on(db):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("incidents", True)


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


def stamp(time: str, date: str = "06/07/2025", camera: str = "BWC2-1", checked=True):
    return {"date": date, "time": time, "camera": camera, "at": 2.0, "checked": checked}


def video(person, case, title, *, seconds=600.0, stamp=None, created=None, tags=None):
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
        probe={"format": {"tags": tags or {}}},
    )
    recording.folder.mkdir(parents=True, exist_ok=True)
    (recording.folder / "playback.mp4").write_bytes(b"not really media")
    return recording


def with_transcript(recording, lines=((0.0, 5.0, "Officer"),)):
    transcript = Transcript.objects.create(recording=recording, language="en")
    for start, end, speaker in lines:
        Segment.objects.create(
            transcript=transcript,
            start=start,
            end=end,
            text=f"words at {start}",
            speaker=speaker,
            speaker_label=speaker.upper(),
        )
    return transcript


# The offer ---------------------------------------------------------------------------


def test_videos_whose_clocks_overlap_are_offered_as_one_incident(person, a_case):
    first = video(person, a_case, "first", stamp=stamp("21:56:19"))
    second = video(person, a_case, "second", stamp=stamp("22:01:00", camera="BWC2-2"))
    third = video(person, a_case, "third", stamp=stamp("22:09:30", camera="DC-12"))
    # Another day, and one with no clock: neither joins.
    video(person, a_case, "later", stamp=stamp("21:57:00", date="08/07/2025"))
    video(person, a_case, "mute", stamp={})
    video(person, a_case, "unchecked", stamp=stamp("21:58:00", checked=False))

    offered = incidents.offers(a_case)
    assert len(offered) == 1 and offered[0]["kind"] == "new"
    assert {one.pk for one in offered[0]["recordings"]} == {
        first.pk,
        second.pk,
        third.pk,
    }
    assert offered[0]["line"].startswith("3 videos ran at the same time on 06/07/2025.")

    # Put away, and it stays away; a fresh video makes a fresh offer.
    incidents.decline(a_case, offered[0]["key"])
    assert incidents.offers(a_case) == []
    video(person, a_case, "fourth", stamp=stamp("22:05:00", camera="BWC2-4"))
    assert len(incidents.offers(a_case)) == 1

    # Proposing off: nothing offered; New incident stays.
    settings_store.set_to("incidents_proposed", False)
    assert incidents.offers(a_case) == []


def test_a_later_video_is_offered_to_the_incident_it_ran_during(person, a_case):
    first = video(person, a_case, "first", stamp=stamp("21:56:19"))
    second = video(person, a_case, "second", stamp=stamp("22:01:00", camera="BWC2-2"))
    incident = incidents.make(a_case, "Stop", [first, second], by=person)
    later = video(person, a_case, "later", stamp=stamp("22:03:00", camera="BWC2-3"))
    offered = incidents.offers(a_case)
    assert len(offered) == 1 and offered[0]["kind"] == "add"
    assert offered[0]["incident"] == incident and offered[0]["recording"] == later


# Placing -----------------------------------------------------------------------------


def test_making_an_incident_places_the_clocked_cameras_on_one_clock(person, a_case):
    late = video(person, a_case, "late", stamp=stamp("22:01:00", camera="BWC2-2"))
    early = video(person, a_case, "early", stamp=stamp("21:56:19"))
    mute = video(person, a_case, "mute", stamp={})
    incident = incidents.make(a_case, "Stop", [late, early, mute], by=person)

    # The first checked clock, by start, is the Incident's zero: 21:56:17,
    # the stamp less the two seconds it was read at.
    assert incident.clock_zero == 21 * 3600 + 56 * 60 + 17
    assert incident.clock_date == "06/07/2025"
    by_title = {one.recording.title: one for one in incident.cameras.all()}
    assert by_title["early"].starts_at == 0.0 and by_title["early"].placed == "clock"
    assert by_title["late"].starts_at == pytest.approx(4 * 60 + 41)
    assert by_title["mute"].starts_at is None and by_title["mute"].placed == ""
    # The late camera: 22:01:00 read two seconds in, ten minutes long.
    assert incidents.span_words(incident) == "06/07/2025 21:56:17 to 22:10:58"
    assert incidents.placed_words(incident) == ("2 of 3 placed", "warn")
    # The Wall holds the placed ones, in clock order.
    assert [one.recording.title for one in incidents.wall_of(incident)] == [
        "early",
        "late",
    ]

    # By hand: a number on the clock, and the pill says so.
    incidents.place_by_hand(by_title["mute"], 120.5, by=person)
    by_title["mute"].refresh_from_db()
    assert by_title["mute"].placed == "hand" and by_title["mute"].starts_at == 120.5
    assert incidents.PLACED_WORDS["hand"] == "Placed by hand"
    assert incidents.placed_words(incident) == ("3 of 3 placed", "ok")

    # From the clock again, and a nudged camera reads by hand.
    assert incidents.place_from_clock(by_title["late"], by=person)
    by_title["late"].refresh_from_db()
    assert by_title["late"].placed == "clock"


def test_the_file_time_places_a_camera_unchecked(person, a_case, settings):
    settings.TIME_ZONE = "UTC"
    clocked = video(person, a_case, "clocked", stamp=stamp("21:56:19"))
    filed = video(
        person,
        a_case,
        "filed",
        stamp={},
        tags={"creation_time": "2025-06-07T21:58:17.000000Z"},
    )
    words, second = incidents.file_time_of(filed)
    assert words == "07 Jun 2025 21:58:17" and second == 21 * 3600 + 58 * 60 + 17
    incident = incidents.make(a_case, "Stop", [clocked, filed], by=person)
    camera = incident.cameras.get(recording=filed)
    assert incidents.place_from_file(camera, by=person)
    camera.refresh_from_db()
    assert camera.placed == "file" and camera.starts_at == pytest.approx(120.0)
    # No clock on the incident, no file placement: nothing to place against.
    alone = incidents.make(a_case, "Alone", [filed], by=person)
    assert incidents.place_from_file(alone.cameras.first(), by=person) is False


def test_an_incident_without_a_clock_counts_from_its_first_camera(person, a_case):
    one = video(person, a_case, "one", stamp={})
    two = video(person, a_case, "two", stamp={})
    incident = incidents.make(a_case, "Stop", [one, two], by=person)
    assert (
        not incident.has_clock()
        and incidents.span_words(incident) == "no camera placed"
    )
    incidents.place_by_hand(incident.cameras.get(recording=one), 0.0, by=person)
    incidents.place_by_hand(incident.cameras.get(recording=two), 30.0, by=person)
    assert incidents.time_of_day(incident, 90.0) == "1:30"
    assert (
        incidents.span_words(incident) == "10:30 from the first camera; no camera clock"
    )
    # A checked clock arriving later gives the clock; the distances stay.
    third = video(person, a_case, "three", stamp=stamp("22:00:00"))
    incidents.add_cameras(incident, [third], by=person)
    incident.refresh_from_db()
    assert incident.has_clock()
    assert incident.cameras.get(recording=two).starts_at == 30.0


# The case page and the incident page ------------------------------------------------


@pytest.mark.django_db
def test_the_case_page_carries_the_strip_only_while_incidents_are_on(
    person, a_case, client
):
    signed_in(client, person)
    first = video(person, a_case, "first", stamp=stamp("21:56:19"))
    second = video(person, a_case, "second", stamp=stamp("22:01:00", camera="BWC2-2"))
    page = client.get(f"/case/{a_case.pk}").content.decode()
    assert "Make them an incident?" in page and "New incident" in page
    assert "Clock in the picture" in page and "06/07/2025 21:56:19, checked" in page

    # New incident from the page: named by the date, opened on its own page.
    answer = client.post(
        f"/case/{a_case.pk}/incidents/new",
        {"recordings": [str(first.pk), str(second.pk)], "how": "offer"},
    )
    incident = Incident.objects.get()
    assert answer.status_code == 302 and answer["Location"] == incident.url()
    assert incident.name == "06/07/2025" and incident.how == "offer"
    page = client.get(f"/case/{a_case.pk}").content.decode()
    assert "Open the incident" in page and "2 of 2 placed" in page
    assert "Make them an incident?" not in page

    # Not these, for a further offer.
    third = video(person, a_case, "third", stamp=stamp("22:03:00", camera="BWC2-3"))
    key = incidents.offers(a_case)[0]["key"]
    client.post(f"/case/{a_case.pk}/incidents/decline", {"key": key})
    a_case.refresh_from_db()
    assert key in a_case.declined_offers and incidents.offers(a_case) == []
    _ = third

    # Off: the strip, the columns and the page itself are gone; the rows stay.
    settings_store.set_to("incidents", False)
    page = client.get(f"/case/{a_case.pk}").content.decode()
    assert "Open the incident" not in page and "Clock in the picture" not in page
    assert client.get(incident.url()).status_code == 404
    assert Incident.objects.count() == 1


@pytest.mark.django_db
def test_the_incident_page_and_its_act_endpoint(person, a_case, client):
    signed_in(client, person)
    first = video(person, a_case, "first", stamp=stamp("21:56:19"))
    with_transcript(first)
    second = video(person, a_case, "second", stamp={})
    incident = incidents.make(a_case, "Stop", [first, second], by=person)
    cam_first = incident.cameras.get(recording=first)
    cam_second = incident.cameras.get(recording=second)

    page = client.get(incident.url() + f"?recording={first.pk}&at=30")
    assert page.status_code == 200
    body = page.content.decode()
    assert "Incident" in body and "incident-state" in body and "at: 30.00" in body
    state = json.loads(client.get(f"{incident.url()}/state").content)
    assert state["incident"]["has_clock"] and state["incident"]["count"] == 2
    cameras = {one["title"]: one for one in state["cameras"]}
    assert cameras["first"]["on_wall"] and cameras["first"]["camera_id"] == "BWC2-1"
    assert (
        cameras["second"]["placed_words"] == "Not placed"
        and not cameras["second"]["on_wall"]
    )

    # The lines under a tile.
    lines = json.loads(client.get(f"/incident-camera/{cam_first.pk}/lines").content)
    assert lines["segments"][0]["speaker"] == "Officer"
    assert json.loads(
        client.get(f"/incident-camera/{cam_second.pk}/lines").content
    ) == {
        "segments": [],
        "moments": [],
    }

    act = f"{incident.url()}/act"
    said = client.post(
        act,
        {
            "action": "place",
            "camera": cam_second.pk,
            "how": "hand",
            "starts_at": "45.5",
        },
    ).json()
    assert (
        said["ok"]
        and {one["title"]: one["placed"] for one in said["state"]["cameras"]}["second"]
        == "hand"
    )
    assert (
        client.post(
            act, {"action": "place", "camera": cam_second.pk, "how": "clock"}
        ).status_code
        == 400
    )
    client.post(act, {"action": "wall", "cameras": f"{cam_second.pk},{cam_first.pk}"})
    incident.refresh_from_db()
    assert [one.recording.title for one in incidents.wall_of(incident)] == [
        "second",
        "first",
    ]
    client.post(act, {"action": "rename", "name": "The stop"})
    incident.refresh_from_db()
    assert incident.name == "The stop"
    client.post(act, {"action": "remove", "camera": cam_second.pk})
    assert incident.cameras.count() == 1
    third = video(person, a_case, "third", stamp={})
    client.post(act, {"action": "add", "recordings": [str(third.pk)]})
    assert incident.cameras.count() == 2
    gone = client.post(act, {"action": "delete"}).json()
    assert gone["redirect"] == f"/case/{a_case.pk}"
    assert Incident.objects.count() == 0 and Recording.objects.count() == 3

    # The audit rows, without a camera id or a word.
    from core.audit import Row

    events = list(Row.objects.filter(category="cases").values_list("event", flat=True))
    assert "incident made" in events and "camera placed" in events
    assert "incident changed" in events and "incident deleted" in events


@pytest.mark.django_db
def test_a_recording_that_leaves_the_case_leaves_its_incident(person, a_case):
    first = video(person, a_case, "first", stamp=stamp("21:56:19"))
    second = video(person, a_case, "second", stamp=stamp("22:01:00", camera="BWC2-2"))
    incident = incidents.make(a_case, "Stop", [first, second], by=person)
    other = Case.objects.create(owner=person, name="Another")
    cases.move_recording(second, other, actor=person)
    assert incident.cameras.count() == 1
    first.delete()
    assert incident.cameras.count() == 0
    incident.refresh_from_db()
    assert incidents.placed_words(incident) == ("no cameras", "warn")


@pytest.mark.django_db
def test_all_cameras_points_at_the_incident_for_a_placed_camera(person, a_case, client):
    signed_in(client, person)
    first = video(person, a_case, "first", stamp=stamp("21:56:19"))
    with_transcript(first)
    loose = video(person, a_case, "loose", stamp=stamp("23:00:00"))
    with_transcript(loose)
    incidents.make(a_case, "Stop", [first], by=person)
    incident = Incident.objects.get()
    assert incidents.link_for(first) == {
        "url": incident.url(),
        "starts_at": 0.0,
        "name": "Stop",
    }
    assert incidents.link_for(loose) is None
    assert incidents.all_cameras_url(first, 12.5) == f"{incident.url()}?t=12.50"
    page = client.get(f"/recording/{first.pk}").content.decode()
    assert 'id="all-cameras"' in page
    assert (
        'id="all-cameras"' not in client.get(f"/recording/{loose.pk}").content.decode()
    )


# The stamp, read early ---------------------------------------------------------


@pytest.mark.django_db
def test_the_stamp_is_read_early_only_when_the_office_allows(
    person, a_case, monkeypatch
):
    from core import engine, tasks

    settings_store.set_to("assistant_available", True)
    settings_store.set_to("moments_available", True)
    monkeypatch.setattr(engine, "is_reachable", lambda: True)
    queued = []
    monkeypatch.setattr(tasks.read_stamp_early, "defer", lambda **kw: queued.append(kw))
    recording = video(person, a_case, "fresh", stamp=None)
    incidents.after_playback(recording)
    assert queued == [{"recording_id": str(recording.pk)}]
    # Not twice, not for a stamp already read, not outside a case, not when off.
    queued.clear()
    read = video(person, a_case, "read", stamp={})
    incidents.after_playback(read)
    incidents.after_playback(video(person, None, "session", stamp=None))
    settings_store.set_to("incidents_stamp_early", False)
    incidents.after_playback(video(person, a_case, "later", stamp=None))
    assert queued == []


# The sound match ----------------------------------------------------------------------


def write_wav(path: Path, samples: np.ndarray, rate: int = 16000) -> None:
    with wave.open(str(path), "wb") as sound:
        sound.setnchannels(1)
        sound.setsampwidth(2)
        sound.setframerate(rate)
        sound.writeframes(np.clip(samples, -32767, 32767).astype(np.int16).tobytes())


def test_the_sound_match_finds_a_known_shift(tmp_path):
    rate = 16000
    rng = np.random.default_rng(7)
    # Ninety seconds of quiet with bursts at random moments: the scene.
    scene = rng.normal(0, 40, rate * 90)
    for at in rng.uniform(1, 88, 40):
        start = int(at * rate)
        scene[start : start + rate // 4] += rng.normal(0, 6000, rate // 4)
    # The second camera starts 3.2 s later and hears it through its own noise.
    shift = int(3.2 * rate)
    other = scene[shift:] + rng.normal(0, 300, len(scene) - shift)
    write_wav(tmp_path / "a.wav", scene)
    write_wav(tmp_path / "b.wav", other)
    found = sound_match.lag_between(tmp_path / "a.wav", tmp_path / "b.wav")
    assert found.lag == pytest.approx(3.2, abs=0.05)
    assert found.strength >= incidents.STRONG_MATCH
    # The other way round: the reference starts 3.2 s before.
    back = sound_match.lag_between(tmp_path / "b.wav", tmp_path / "a.wav")
    assert back.lag == pytest.approx(-3.2, abs=0.05)
    # With an expected shift far from the truth, the window says no.
    with pytest.raises(sound_match.NoMatch):
        sound_match.lag_between(
            tmp_path / "a.wav", tmp_path / "b.wav", expected=60.0, window=10.0
        )


@pytest.mark.django_db
def test_a_strong_match_places_the_camera_by_sound(
    person, a_case, tmp_path, monkeypatch
):
    first = video(person, a_case, "first", stamp=stamp("21:56:19"))
    second = video(person, a_case, "second", stamp={})
    for recording in (first, second):
        Side.objects.create(recording=recording, number=1)
        (recording.folder / "asr-side1.wav").write_bytes(b"x")
    incident = incidents.make(a_case, "Stop", [first, second], by=person)
    cam_first = incident.cameras.get(recording=first)
    cam_second = incident.cameras.get(recording=second)
    deferred = []
    from core import tasks

    monkeypatch.setattr(tasks.match_sound, "defer", lambda **kw: deferred.append(kw))
    monkeypatch.setattr(
        sound_match,
        "lag_between",
        lambda a, b, expected=None: sound_match.Match(41.3, 4.0),
    )
    assert incidents.ask_for_match(cam_second, cam_first, by=person)
    cam_second.refresh_from_db()
    assert cam_second.match_state == "queued"
    incidents.run_match(cam_second)
    cam_second.refresh_from_db()
    assert cam_second.match_state == "done" and cam_second.match_lag == 41.3
    assert cam_second.placed == "sound" and cam_second.starts_at == pytest.approx(41.3)
    # A weak match is kept and shown, not applied.
    monkeypatch.setattr(
        sound_match,
        "lag_between",
        lambda a, b, expected=None: sound_match.Match(10.0, 1.1),
    )
    third = video(person, a_case, "third", stamp={})
    incidents.add_cameras(incident, [third], by=person)
    Side.objects.create(recording=third, number=1)
    (third.folder / "asr-side1.wav").write_bytes(b"x")
    cam_third = incident.cameras.get(recording=third)
    incidents.ask_for_match(cam_third, cam_first, by=person)
    incidents.run_match(cam_third)
    cam_third.refresh_from_db()
    assert cam_third.match_state == "done" and cam_third.placed == ""
    assert incidents.apply_match(cam_third, by=person)
    cam_third.refresh_from_db()
    assert cam_third.placed == "sound" and cam_third.starts_at == pytest.approx(10.0)
    # Off, the match is not offered.
    settings_store.set_to("incidents_sound_match", False)
    assert incidents.ask_for_match(cam_third, cam_first, by=person) is False


# The words ---------------------------------------------------------------------


def test_the_words_are_in_the_glossary_the_guide_and_the_catalogue():
    glossary = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    for word in ("**Incident**", "**Incident clock**", "**Placed**", "**Wall**"):
        assert word in glossary
    guide = (ROOT / "docs" / "user-guide.md").read_text(encoding="utf-8")
    assert "### Incidents" in guide and "Match the sound" in guide
    catalogue = (ROOT / "docs" / "spec" / "ADMIN-SETTINGS-CATALOGUE.md").read_text(
        encoding="utf-8"
    )
    for setting in ("Cameras on the wall", "Stamp reads early", "Match by sound"):
        assert setting in catalogue
    for key in (
        "incidents",
        "incidents_proposed",
        "incidents_wall",
        "incidents_most_cameras",
        "incidents_stamp_early",
        "incidents_sound_match",
    ):
        assert settings_store.definition(key).page == "incidents"
