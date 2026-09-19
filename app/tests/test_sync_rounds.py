"""v1.66.0: Sync as one control, and the clip from the strip (Phase 6,
chapter 5).

The rules checked here: the rounds try a camera's clock (checked, then
unchecked), then the sound against the synced camera it overlaps most,
then leave it needing a hand with a reason; Sync all leaves synced cameras
alone and Sync ticked redoes them; the state line counts the rounds; the
camera's state carries its reason; the clip from the strip needs no event,
takes an unsynced camera, and says "from the strip" wherever the clip is
named; an event's clip keeps chapter 1's rule.
"""

from __future__ import annotations

import json

import pytest
from core import chronology, incidents, settings_store, tasks
from core.cases import Case
from core.clips import Clip
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
    settings_store.set_to("clips_available", True)
    settings_store.set_to("incidents_clips", True)


@pytest.fixture(autouse=True)
def no_workers(monkeypatch):
    """Nothing reaches the queue; what would have is remembered."""
    deferred = []

    class Deferrer:
        def __init__(self, **options):
            self.options = options

        def defer(self, **fields):
            deferred.append(fields)

    monkeypatch.setattr(tasks.match_sound, "defer", lambda **f: deferred.append(f))
    monkeypatch.setattr(tasks.match_sound, "configure", lambda **o: Deferrer(**o))
    monkeypatch.setattr(tasks.render_clip, "defer", lambda **f: deferred.append(f))
    monkeypatch.setattr(tasks.render_clip, "configure", lambda **o: Deferrer(**o))
    return deferred


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


def stamp(time: str, camera: str, checked: bool = True):
    return {
        "date": "06/07/2025",
        "time": time,
        "camera": camera,
        "at": 2.0,
        "checked": checked,
    }


def video(person, case, title, *, seconds=600.0, stamp=None):
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
    return recording


def cameras_of(incident):
    return {one.recording.title: one for one in incident.cameras.all()}


# The rounds --------------------------------------------------------------------------


def test_the_rounds_try_the_clock_then_the_sound_then_ask_for_a_hand(
    person, a_case, no_workers
):
    checked = video(person, a_case, "checked", stamp=stamp("21:56:19", "BWC2-1"))
    once = video(person, a_case, "once", stamp=stamp("21:58:00", "BWC2-2", False))
    mute = video(person, a_case, "mute", stamp={})
    unread = video(person, a_case, "unread", stamp=None)
    incident = incidents.make(a_case, "Stop", [checked, once, mute, unread], by=person)
    cams = cameras_of(incident)
    # Making the incident placed the checked clock; the rest wait as guesses
    # (the unchecked one too, until a person or the rounds place it).
    for camera in cams.values():
        if camera.recording.title != "checked":
            incidents.IncidentCamera.objects.filter(pk=camera.pk).update(
                placed=incidents.GUESS, starts_at=0.0
            )
    for camera in cams.values():
        camera.refresh_from_db()
    assert incidents.needs_hand_reason(cams["checked"]) == ""
    assert incidents.needs_hand_reason(cams["once"]) == ""
    assert incidents.needs_hand_reason(cams["mute"]) == "no clock in the picture"
    assert (
        incidents.needs_hand_reason(cams["unread"]) == "the clock has not been read yet"
    )

    got = incidents.sync_rounds(incident, list(cams.values()), by=person)
    assert got == {
        str(cams["checked"].pk): "synced",
        str(cams["once"].pk): "unchecked",
        str(cams["mute"].pk): "matching",
        str(cams["unread"].pk): "matching",
    }
    for camera in cams.values():
        camera.refresh_from_db()
    assert cams["once"].placed == "clock_unchecked"
    assert cams["once"].starts_at == pytest.approx(101.0)
    # The sound is matched against the synced camera each overlaps most.
    assert cams["mute"].match_state == "queued"
    assert cams["mute"].match_against_id == cams["checked"].pk
    # (The worker is deferred on commit, which a test transaction never reaches.)
    assert incidents.rounds_line(got) == (
        "Syncing 3 cameras: 1 from its clock (1 read once), 2 matching the sound."
    )
    assert incidents.rounds_line({"a": "synced"}) == "Every camera is synced already."
    assert incidents.rounds_line({"a": "hand", "b": "hand", "c": "clock"}) == (
        "Syncing 3 cameras: 1 from its clock, 2 need a hand."
    )
    # With Match by sound off there is nothing to try on a mute camera.
    settings_store.set_to("incidents_sound_match", False)
    incidents.IncidentCamera.objects.filter(pk=cams["mute"].pk).update(
        match_state="", match_against=None
    )
    cams["mute"].refresh_from_db()
    got = incidents.sync_rounds(incident, [cams["mute"]], by=person)
    assert got == {str(cams["mute"].pk): "hand"}
    assert incidents.needs_hand_reason(cams["mute"]) == (
        "no clock in the picture, and Match by sound is off"
    )
    settings_store.set_to("incidents_sound_match", True)
    incidents.IncidentCamera.objects.filter(pk=cams["mute"].pk).update(
        match_state="failed", match_reason="the sounds did not line up"
    )
    cams["mute"].refresh_from_db()
    assert incidents.needs_hand_reason(cams["mute"]) == (
        "no match: the sounds did not line up"
    )


def test_sync_all_and_sync_ticked_from_the_page(person, a_case, client, no_workers):
    first = video(person, a_case, "first", stamp=stamp("21:56:19", "BWC2-1"))
    second = video(person, a_case, "second", stamp=stamp("22:01:00", "BWC2-2"))
    incident = incidents.make(a_case, "Stop", [first, second], by=person)
    cams = cameras_of(incident)
    incidents.place_by_hand(cams["second"], 100.0, by=person)
    signed_in(client, person)
    url = f"/case/{a_case.pk}/incident/{incident.pk}"
    page = client.get(url).content.decode()
    assert 'id="sync-open"' in page and 'id="sync-box"' in page
    assert 'id="clip-band"' in page and 'id="clip-unsynced"' in page
    # Sync all leaves a synced camera alone.
    got = client.post(url + "/act", {"action": "sync_all"}).json()
    assert got["said"] == "Every camera is synced already."
    cams["second"].refresh_from_db()
    assert cams["second"].placed == "hand" and cams["second"].starts_at == 100.0
    # Sync ticked redoes the ticked one from its clock.
    got = client.post(
        url + "/act", {"action": "sync_all", "cameras": [str(cams["second"].pk)]}
    ).json()
    assert got["said"] == "Syncing 1 camera: 1 from its clock."
    cams["second"].refresh_from_db()
    assert cams["second"].placed == "clock"
    assert cams["second"].starts_at == pytest.approx(281.0)
    state = got["state"]
    by_id = {one["camera_id"]: one for one in state["cameras"]}
    assert by_id["BWC2-2"]["needs_hand"] == "" and by_id["BWC2-2"]["ends_at"] == 881.0


# The clip from the strip ------------------------------------------------------------


def test_the_clip_from_the_strip_needs_no_event_and_takes_an_unsynced_camera(
    person, a_case, client, no_workers
):
    first = video(person, a_case, "first", stamp=stamp("21:56:19", "BWC2-1"))
    mute = video(person, a_case, "mute", stamp={})
    incident = incidents.make(a_case, "Stop", [first, mute], by=person)
    cams = cameras_of(incident)
    assert not cams["mute"].is_synced()
    signed_in(client, person)
    url = f"/case/{a_case.pk}/incident/{incident.pk}"
    body = {
        "from": 50,
        "until": 70,
        "cameras": [str(cams["first"].pk), str(cams["mute"].pk)],
        "sound": str(cams["first"].pk),
        "layout": "grid",
    }
    answer = client.post(
        url + "/clip", json.dumps(body), content_type="application/json"
    )
    assert answer.status_code == 200, answer.content
    got = answer.json()
    assert got["said"] == "Rendering. The clip lands on the case's Clips tab."
    assert got["event_clips"] == 0
    clip = Clip.objects.get()
    assert clip.event_id is None and clip.incident_id == incident.pk
    assert clip.title == "21:57:07 to 21:57:27"
    assert clip.picture["from_strip"] is True
    assert [one["label"] for one in clip.picture["cameras"]] == ["BWC2-1", "mute"]
    assert clip.from_event == "from the strip, 21:57:07 to 21:57:27"
    assert got["clip"]["from_event"] == "from the strip, 21:57:07 to 21:57:27"
    assert chronology.clips_line(incident, {}) == (
        "Clips made from events and the strip: from the strip: "
        "21:57:07 to 21:57:27 (20 s)."
    )
    # A person's title wins; the same span from the ruler twice is two clips.
    body["title"] = "The stop"
    assert (
        client.post(
            url + "/clip", json.dumps(body), content_type="application/json"
        ).status_code
        == 200
    )
    assert Clip.objects.filter(title="The stop").exists()
    # An event's clip keeps chapter 1's rule on an unsynced camera.
    event = chronology.add(incident, {"at": "60", "text": "Stopped"}, by=person)
    answer = client.post(
        url + f"/event/{event.pk}/clip",
        json.dumps(body),
        content_type="application/json",
    )
    assert answer.status_code == 400
    assert answer.json()["error"] == "mute is not synced yet."
    # A missing playback copy is refused by either door.
    (mute.folder / "playback.mp4").unlink()
    answer = client.post(
        url + "/clip", json.dumps(body), content_type="application/json"
    )
    assert answer.json()["error"] == "mute has no playback copy."
