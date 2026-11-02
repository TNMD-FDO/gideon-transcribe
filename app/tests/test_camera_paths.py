"""A camera's path from its path file (Phase 12 chapter 1, v1.187.0).

The rules checked here: the file beside a body-worn or in-car video is read
into fixes and marks with the wearer, the unit and, for an in-car unit, its
own clock; what is not a path file is refused with the reason and a file
with no position is kept for its readings; the file lands in the recording's
folder, is measured, goes with the recording and is never served; the map's
clock comes from the path file, then the recording's clock, then the file's
name; several files find their videos by name and the rest come back to be
settled; the readings give the lights, the siren, the mic and standing
still in the office's time of day, the chat's block says the same and never
a coordinate, the forming offer names cameras that kept close; the joins
link from hits, notes and incidents; one audit row each, never a position.

Every place here is fictional: the fixes sit in the open Atlantic.
"""

from __future__ import annotations

import datetime as dt
import io
import json
from pathlib import Path

import pytest
from core import (
    camera_paths,
    case_chronology,
    case_search,
    dashboard,
    maps,
    media_access,
    notes,
    settings_store,
)
from core.audit import Row
from core.cases import Case
from core.incidents import Incident, IncidentCamera
from core.models import User
from core.recordings import Batch, MediaState, Recording
from django.urls import reverse
from django.utils import timezone
from tests.helpers import signed_in, stamp

PASSWORD = "a-long-enough-password"
HERE = Path(__file__).resolve().parents[1]
LAT, LON = 10.0, -30.0


@pytest.fixture(autouse=True)
def switched_on(db, settings, tmp_path):
    settings.DATA_DIR = tmp_path
    settings_store.set_to("folder_management", True)
    settings_store.set_to("incidents", True)
    settings_store.set_to("maps", True)


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("walker", PASSWORD)


@pytest.fixture
def a_case(person):
    return Case.objects.create(owner=person, name="Harbour Street stop")


def video(person, case, title, *, name=None, stamp=None, seconds=120.0):
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        case=case,
        title=title,
        original_filename=name or f"{title}.mp4",
        media_state=MediaState.READY,
        duration_seconds=seconds,
        playback_ready=True,
        stamp=stamp,
        probe={},
    )
    recording.folder.mkdir(parents=True, exist_ok=True)
    (recording.folder / "playback.mp4").write_bytes(b"not really media")
    return recording


def clock(seconds: float) -> str:
    whole = int(seconds)
    millis = int(round((seconds - whole) * 1000))
    return f"{whole // 3600:02d}:{whole % 3600 // 60:02d}:{whole % 60:02d}.{millis:03d}"


def vtt(cues, *, crlf=False, bom=False) -> bytes:
    """A path file as the camera writes it: numbered cues, one JSON reading each."""
    lines = ["WEBVTT", ""]
    for number, (start, end, reading) in enumerate(cues, 1):
        body = json.dumps(reading) if isinstance(reading, dict) else reading
        lines += [str(number), f"{clock(start)} --> {clock(end)}", body, ""]
    text = "\n".join(lines)
    if crlf:
        text = text.replace("\n", "\r\n")
    if bom:
        text = "﻿" + text
    return text.encode("utf-8")


def body_reading(t: float, *, mic=0, where=True, officer="Pat Doe"):
    return {
        "gpsCoordinates": f"N{LAT + t * 0.0001:.6f} W{-LON:.6f}" if where else "",
        "mic": str(mic),
        "low battery": "0",
        "officer": officer,
        "vehicle": "",
        "department": "Demo Police",
        "eventDate": "",
    }


def body_file(seconds=120, *, activated_at=61, gap=None, still=False) -> bytes:
    cues = []
    for t in range(seconds):
        where = not (gap and gap[0] <= t < gap[1])
        reading = body_reading(
            0 if still else t, mic=int(t >= activated_at), where=where
        )
        cues.append((t, t + 1, reading))
    return vtt(cues)


def car_reading(
    t: float,
    *,
    when="11/06/25 14:20:03",
    lights=0,
    siren=0,
    brakes=0,
    bookmark=0,
    speed=0,
):
    moment = dt.datetime.strptime(when, "%m/%d/%y %H:%M:%S") + dt.timedelta(seconds=t)
    return {
        "gpsCoordinates": f"N{LAT + t * 0.0002:.6f} W{-LON:.6f}",
        "mic": "1",
        "officer": "Sam Roe",
        "vehicle": "9082",
        "department": "Demo Police",
        "eventDate": moment.strftime("%m/%d/%y %H:%M:%S"),
        "patrolSpeed": str(speed),
        "speedUnit": "MPH",
        "lights": str(lights),
        "siren": str(siren),
        "brakes": str(brakes),
        "crash": "0",
        "aux": "0",
        "bookmark": str(bookmark),
    }


def car_file(seconds=300, *, drift=0.0) -> bytes:
    """Lights on from 20 s to 140 s, siren 20 to 80, brakes at 78, a bookmark
    at 200, speed rising to 41 then falling."""
    cues = []
    for t in range(seconds):
        reading = car_reading(
            t + (drift if t == seconds - 1 else 0.0),
            lights=int(20 <= t < 140),
            siren=int(20 <= t < 80),
            brakes=int(t == 78),
            bookmark=int(t == 200),
            speed=min(41, t // 2) if t < 150 else max(0, 41 - (t - 150)),
        )
        cues.append((t, t + 1, reading))
    return vtt(cues)


def added(recording, data, *, by, filename=None, replace=False):
    return camera_paths.add(
        recording,
        data=data,
        filename=filename or Path(recording.original_filename).stem + ".vtt",
        by=by,
        replace=replace,
    )


# The parser --------------------------------------------------------------------


def test_a_body_camera_file_is_read_to_fixes_marks_and_the_wearer():
    parsed = camera_paths.parse(body_file().decode())
    assert parsed.source == camera_paths.BODY
    assert parsed.wearer == "Pat Doe" and parsed.department == "Demo Police"
    assert parsed.cues == 120 and parsed.fix_count == 120 and parsed.length == 120.0
    assert parsed.fixes[0] == [0.0, LAT, LON]
    assert parsed.first_fix == 0.0 and parsed.last_fix == 119.0
    # The mic's first value, then its one change.
    assert [one for one in parsed.marks if one[1] == "mic"] == [
        [0.0, "mic", 0],
        [61.0, "mic", 1],
    ]
    assert parsed.clock_start is None and parsed.bounds[0] == LAT


def test_an_in_car_file_gives_the_clock_from_its_event_date_in_the_office_zone():
    parsed = camera_paths.parse(car_file().decode())
    assert parsed.source == camera_paths.CAR
    assert parsed.unit == "9082" and parsed.speed_unit == "MPH"
    local = timezone.localtime(parsed.clock_start)
    assert (local.hour, local.minute, local.second) == (14, 20, 3)
    assert local.date() == dt.date(2025, 11, 6)
    assert parsed.clock_agrees is True


def test_first_and_last_dated_cues_disagreeing_makes_the_clock_likely(person, a_case):
    clear = camera_paths.parse(car_file().decode())
    drifted = camera_paths.parse(car_file(drift=5.0).decode())
    assert clear.clock_agrees and not drifted.clock_agrees
    one = video(person, a_case, "Dash-4")
    path, _ = added(one, car_file(), by=person)
    assert camera_paths.zero_of(one, path)["surety"]["word"] == "Clear"
    two = video(person, a_case, "Dash-5")
    path, _ = added(two, car_file(drift=5.0), by=person)
    assert camera_paths.zero_of(two, path)["surety"]["word"] == "Likely"


def test_consecutive_cues_at_one_position_collapse_to_one_fix():
    parsed = camera_paths.parse(body_file(still=True).decode())
    assert parsed.cues == 120 and parsed.fix_count == 1


def test_empty_coordinates_make_a_gap_and_no_fix():
    parsed = camera_paths.parse(body_file(gap=(30, 50)).decode())
    assert parsed.gaps == [[30.0, 50.0]]
    assert parsed.fix_count == 100
    # Five seconds without a fix is not a gap.
    short = camera_paths.parse(body_file(gap=(30, 35)).decode())
    assert short.gaps == []


def test_south_and_west_read_as_negative_and_out_of_range_is_no_fix():
    assert camera_paths._coordinates("S10.5 E20.25") == (-10.5, 20.25)
    assert camera_paths._coordinates("N10.5 W20.25") == (10.5, -20.25)
    assert camera_paths._coordinates("N95.0 W20.25") is None
    assert camera_paths._coordinates("") is None


def test_odd_cues_endings_and_a_byte_order_mark_are_read():
    cues = [
        (0.0, 0.0, body_reading(0)),  # zero-length
        (0.5, 1.0, body_reading(1)),  # half a second
        (1.0, 2.0, "not json at all"),
        (2.0, 3.0, body_reading(3)),
    ]
    parsed = camera_paths.parse(vtt(cues, crlf=True, bom=True).decode("utf-8-sig"))
    assert parsed.cues == 4 and parsed.unread == 1 and parsed.fix_count == 3


def test_a_file_that_is_not_webvtt_is_refused_with_the_reason():
    with pytest.raises(camera_paths.Refused) as told:
        camera_paths.parse("Hello\n\n00:00:00.000 --> 00:00:01.000\n{}")
    assert "WEBVTT" in str(told.value)
    with pytest.raises(camera_paths.Refused) as told:
        camera_paths.parse(vtt([(0, 1, {"caption": "words"})]).decode())
    assert "not a camera's path file" in str(told.value)


def test_a_file_with_no_position_is_kept_for_its_readings(person, a_case):
    one = video(person, a_case, "BWC3-1")
    cues = [
        (t, t + 1, body_reading(t, mic=int(t >= 61), where=False)) for t in range(90)
    ]
    path, warnings = added(one, vtt(cues), by=person)
    assert path.fix_count == 0 and path.bounds is None and path.has_fixes is False
    assert [e["words"] for e in camera_paths.events_of(path)] == [
        "Camera on",
        "Activated",
        "Camera off",
    ]


def test_a_file_over_the_cap_is_refused_before_it_is_read(person, a_case):
    one = video(person, a_case, "BWC3-1")
    with pytest.raises(camera_paths.Refused) as told:
        added(one, b"W" * (camera_paths.MOST_BYTES + 1), by=person)
    assert "MB" in str(told.value)
    assert camera_paths.of(one) is None


# Adding, replacing, removing ----------------------------------------------------


def test_the_file_lands_in_the_folder_is_measured_and_goes_with_the_recording(
    person, a_case
):
    one = video(person, a_case, "BWC2-1")
    before = one.on_disk_bytes
    path, warnings = added(one, body_file(), by=person)
    assert warnings == []
    assert (one.folder / camera_paths.FILE_NAME).exists()
    one.refresh_from_db()
    assert one.on_disk_bytes > (before or 0)
    row = Row.objects.get(event="Path file added")
    assert row.object_label == "BWC2-1"
    assert row.details["source"] == "body" and row.details["fixes"] == 120
    assert row.details["name_matches"] is True and row.details["clock"] is False
    # Never a position, a wearer, a unit or a department in a row.
    said = json.dumps(row.details)
    assert "Pat" not in said and "Demo" not in said and str(LAT) not in said
    one.delete()
    assert not camera_paths.CameraPath.objects.filter(pk=path.pk).exists()


def test_a_mismatched_name_is_taken_with_a_warning(person, a_case):
    one = video(person, a_case, "BWC2-1", name="BWC2-1_202511062027_abc.mp4")
    path, warnings = added(one, body_file(), by=person, filename="other.vtt")
    assert path.stem_matches is False
    assert any("name does not match" in w for w in warnings)


def test_a_second_add_replaces_only_when_asked(person, a_case):
    one = video(person, a_case, "BWC2-1")
    added(one, body_file(), by=person)
    with pytest.raises(camera_paths.Refused):
        added(one, body_file(seconds=60), by=person)
    path, _ = added(one, body_file(seconds=60), by=person, replace=True)
    assert path.cues == 60
    assert Row.objects.filter(event="Path file replaced").count() == 1
    assert Row.objects.filter(event="Path file removed").count() == 0


def test_removing_takes_the_file_and_writes_a_row(person, a_case):
    one = video(person, a_case, "BWC2-1")
    path, _ = added(one, body_file(), by=person)
    camera_paths.remove(path, by=person)
    assert not (one.folder / camera_paths.FILE_NAME).exists()
    assert camera_paths.of(one) is None
    assert Row.objects.get(event="Path file removed").object_label == "BWC2-1"


def test_the_path_file_is_never_servable():
    assert camera_paths.FILE_NAME not in media_access.SERVABLE


# The clock ----------------------------------------------------------------------


def test_the_zero_comes_from_the_path_file_then_the_clock_then_the_name(person, a_case):
    car = video(person, a_case, "Dash-4", name="Dash-4_202511062027_x.mp4")
    path, _ = added(car, car_file(), by=person)
    zero = camera_paths.zero_of(car, path)
    assert zero["how"] == "path" and zero["date"] == "2025-11-06"
    assert zero["second"] == 14 * 3600 + 20 * 60 + 3

    placed = video(person, a_case, "BWC1-1", name="BWC1-1_202511062027_x.mp4")
    case_chronology.place(placed, dt.date(2025, 11, 6), 50000.0, by=person)
    path, _ = added(placed, body_file(), by=person)
    zero = camera_paths.zero_of(placed, path)
    assert zero["how"] == "hand" and zero["second"] == 50000.0

    named = video(person, a_case, "BWC2-1", name="BWC2-1_202511062027_x.mp4")
    path, _ = added(named, body_file(), by=person)
    zero = camera_paths.zero_of(named, path)
    assert zero["how"] == "name" and zero["surety"]["word"] == "By its name"
    expected = timezone.localtime(dt.datetime(2025, 11, 6, 20, 27, tzinfo=dt.UTC))
    assert zero["date"] == expected.date().isoformat()
    assert zero["second"] == expected.hour * 3600 + expected.minute * 60

    nameless = video(person, a_case, "BWC3-1", name="clip.mp4")
    path, _ = added(nameless, body_file(), by=person)
    assert camera_paths.zero_of(nameless, path) is None


def test_the_file_names_minute_is_read_as_utc():
    when = camera_paths.name_moment_of("BWC2-1_202511062027_abc.vtt")
    assert when == dt.datetime(2025, 11, 6, 20, 27, tzinfo=dt.UTC)
    assert camera_paths.name_moment_of("nothing-here.vtt") is None
    assert camera_paths.name_moment_of("x_209913990000_y.vtt") is None


# The readings and the chat ---------------------------------------------------------


def test_the_readings_give_lights_siren_brakes_bookmark_and_speed(person, a_case):
    car = video(person, a_case, "Dash-4")
    path, _ = added(car, car_file(), by=person)
    events = {(e["kind"], e["value"]): e for e in camera_paths.events_of(path)}
    assert (
        events[("lights", 1)]["t"] == 20.0 and events[("lights", 1)]["until"] == 140.0
    )
    assert events[("siren", 1)]["until"] == 80.0 and events[("siren", 0)]["t"] == 80.0
    assert events[("brakes", 1)]["t"] == 78.0
    assert events[("bookmark", 1)]["t"] == 200.0
    assert events[("speed", 41)]["words"] == "Reached 41 mph"
    words = camera_paths.readings_words(path, camera_paths.zero_of(car, path))
    assert "lights on 14:20:23 to 14:22:23" in words
    assert "siren on 14:20:23 to 14:21:23" in words
    assert "recording began 14:20:03" in words


def test_a_body_camera_activated_and_standing_still_are_read(person, a_case):
    one = video(person, a_case, "BWC2-1")
    path, _ = added(one, body_file(seconds=200, still=True), by=person)
    events = camera_paths.events_of(path)
    assert [e["words"] for e in events if e["kind"] == "mic"] == ["Activated"]
    still = [e for e in events if e["kind"] == "still"]
    assert still and still[0]["t"] == 0.0 and still[0]["until"] == 200.0
    words = camera_paths.readings_words(path, None)
    assert any(w.startswith("activated 1:01 in") for w in words)
    assert any(w.startswith("stood still") and "(3 minutes)" in w for w in words)


def test_the_chats_block_names_the_camera_and_the_time_and_never_a_coordinate(
    person, a_case
):
    car = video(person, a_case, "Dash-4")
    added(car, car_file(), by=person)
    body = video(person, a_case, "BWC2-1", name="BWC2-1_202511061420_x.mp4")
    added(body, body_file(), by=person)
    block = camera_paths.readings_block(a_case, [car, body])
    assert block.startswith("The cameras' own files")
    assert "Recording 1 (Dash-4; an in-car camera, unit 9082, officer Sam Roe" in block
    assert "clock from its own file" in block
    assert "lights on 14:20:23 to 14:22:23" in block
    assert "Recording 2 (BWC2-1; a body camera, worn by Pat Doe" in block
    assert "activated " in block and "camera's buffer" in block
    assert str(LAT) not in block and str(LON) not in block and "N10" not in block
    # Nothing to say without a path, and nothing while maps are off.
    assert camera_paths.readings_block(a_case, []) == ""
    settings_store.set_to("maps", False)
    assert camera_paths.readings_block(a_case, [car]) == ""


def test_the_readings_rule_joins_both_chats():
    case_chat = (HERE / "core" / "case_chat.py").read_text(encoding="utf-8")
    incident_chat = (HERE / "core" / "incident_chat.py").read_text(encoding="utf-8")
    assert (
        "camera_paths.readings_block(" in case_chat and "camera_paths.RULE" in case_chat
    )
    assert "readings_block_for_incident(" in incident_chat
    assert "camera_paths.RULE" in incident_chat
    assert "[Recording N, HH:MM:SS]" in camera_paths.RULE


def test_two_cameras_that_kept_close_are_together_and_make_the_offer(person, a_case):
    a = video(person, a_case, "BWC1-1")
    b = video(person, a_case, "BWC2-1")
    case_chronology.place(a, dt.date(2025, 11, 6), 50000.0, by=person)
    case_chronology.place(b, dt.date(2025, 11, 6), 50000.0, by=person)
    added(a, body_file(seconds=400, still=True), by=person)
    added(b, body_file(seconds=400, still=True), by=person)
    told = camera_paths.map_of(a_case, viewer=person)
    assert len(told["offer"]) == 1
    offer = told["offer"][0]
    assert sorted(offer["recordings"]) == sorted([str(a.pk), str(b.pk)])
    assert "within 50" in offer["line"] and "in no incident" in offer["line"]
    block = camera_paths.readings_block(a_case, [a, b])
    assert "Recording 1 and Recording 2 were within 50 m" in block
    incident = Incident.objects.create(case=a_case, name="Stop", created_by=person)
    IncidentCamera.objects.create(incident=incident, recording=a)
    assert camera_paths.map_of(a_case, viewer=person)["offer"] == []


# Matching files to their videos ------------------------------------------------------


def test_several_files_land_on_their_videos_by_name_and_the_rest_come_back(
    person, a_case
):
    one = video(person, a_case, "BWC1-1", name="BWC1-1_202511061420_a.mp4")
    two = video(person, a_case, "BWC2-1", name="BWC2-1_202511061420_b.mp4")
    has = video(person, a_case, "BWC3-1", name="BWC3-1_202511061420_c.mp4")
    added(has, body_file(), by=person)
    flagged = video(
        person,
        a_case,
        "Dash-4",
        name="Dash-4_202511061420_d.mp4",
        stamp=stamp("14:20:03", "BWC7"),
    )
    told = camera_paths.match_files(
        a_case,
        [
            ("BWC1-1_202511061420_a.vtt", body_file(), ""),
            ("bwc2-1_202511061420_B.vtt", body_file(), ""),
            ("BWC3-1_202511061420_c.vtt", body_file(), ""),
            ("Dash-4_202511061420_d.vtt", car_file(), ""),
            ("nobody.vtt", body_file(), ""),
            ("notes.vtt", vtt([(0, 1, {"caption": "x"})]), ""),
        ],
        by=person,
    )
    assert {row["recording"] for row in told["landed"]} == {str(one.pk), str(two.pk)}
    whys = {row["file"]: row["why"] for row in told["leftovers"]}
    assert whys == {
        "BWC3-1_202511061420_c.vtt": "has_one",
        "Dash-4_202511061420_d.vtt": "flagged",
        "nobody.vtt": "unmatched",
        "notes.vtt": "refused",
    }
    by_file = {row["file"]: row for row in told["leftovers"]}
    assert "9082" in by_file["Dash-4_202511061420_d.vtt"]["words"]
    assert by_file["nobody.vtt"]["about"].startswith("A body camera, 2 minutes")
    # Settled: the flagged one taken anyway, the unmatched one given its
    # video, the one with a file replaced.
    settled = camera_paths.match_files(
        a_case,
        [
            ("Dash-4_202511061420_d.vtt", car_file(), str(flagged.pk)),
            ("nobody.vtt", body_file(seconds=30), str(has.pk)),
        ],
        by=person,
        replace_ids=[str(has.pk)],
    )
    assert settled["leftovers"] == []
    assert {row["recording"] for row in settled["landed"]} == {
        str(flagged.pk),
        str(has.pk),
    }
    assert camera_paths.of(has).cues == 30


def test_two_in_car_streams_of_one_unit_are_twins(person, a_case):
    front = video(person, a_case, "Dash-4 front")
    cabin = video(person, a_case, "Dash-4 cabin")
    added(front, car_file(), by=person)
    added(cabin, car_file(), by=person)
    told = camera_paths.map_of(a_case, viewer=person)
    by_id = {row["id"]: row for row in told["cameras"]}
    assert by_id[str(front.pk)]["twin_of"] == ""
    assert by_id[str(cabin.pk)]["twin_of"] == str(front.pk)


# The page and the endpoints -----------------------------------------------------------


def test_map_json_lists_this_cases_cameras_and_no_others(client, person, a_case):
    one = video(person, a_case, "Dash-4")
    added(one, car_file(), by=person)
    other = Case.objects.create(owner=person, name="Marsh Lane")
    added(video(person, other, "BWC9-1"), body_file(), by=person)
    without = video(person, a_case, "BWC5-1")
    signed_in(client, person)
    told = client.get(reverse("case-map", args=[a_case.pk])).json()
    assert [c["title"] for c in told["cameras"]] == ["Dash-4"]
    assert told["videos_without_path"] == [{"id": str(without.pk), "title": "BWC5-1"}]
    assert told["days"] == [
        {"date": "2025-11-06", "cameras": 1, "words": "06 Nov 2025"}
    ]
    assert told["day"] == "2025-11-06"
    assert told["basemap"] == {
        "present": False,
        "url": "",
        "attribution": maps.ATTRIBUTION,
    }
    assert told["may_add"] is True and told["add_url"].endswith("/paths/add")
    cam = told["cameras"][0]
    assert cam["zero"]["second"] == 51603.0 and cam["surety"]["word"] == "Clear"
    assert cam["fixes"][0][1] == LAT and cam["events"][0]["words"] == "Camera on"
    # Off, the tab's reading is not there.
    settings_store.set_to("maps", False)
    assert client.get(reverse("case-map", args=[a_case.pk])).status_code == 404


def test_the_posts_add_replace_and_remove_a_file_on_one_recording(
    client, person, a_case
):
    one = video(person, a_case, "BWC2-1")
    signed_in(client, person)
    url = reverse("camera-path-add", args=[one.pk])
    told = client.post(url, {"file": io.BytesIO(body_file())}).json()
    assert told["ok"] is True and told["fixes"] == 120
    assert told["words"].startswith("120 fixes over 2 minutes, body camera")
    again = client.post(url, {"file": io.BytesIO(body_file())})
    assert again.status_code == 400 and "replace" in again.json()["error"]
    replaced = client.post(
        url, {"file": io.BytesIO(body_file(seconds=30)), "replace": "1"}
    )
    assert replaced.status_code == 200 and camera_paths.of(one).cues == 30
    gone = client.post(reverse("camera-path-remove", args=[one.pk]))
    assert gone.json() == {"ok": True} and camera_paths.of(one) is None
    assert client.post(url, {}).status_code == 400


def test_the_post_refuses_a_recording_the_person_cannot_open(client, person, a_case):
    one = video(person, a_case, "BWC2-1")
    stranger = User.objects.create(username="stranger", display_name="stranger")
    signed_in(client, stranger)
    answer = client.post(
        reverse("camera-path-add", args=[one.pk]), {"file": io.BytesIO(body_file())}
    )
    assert answer.status_code == 404
    assert camera_paths.of(one) is None


def test_several_files_post_to_the_case_and_land(client, person, a_case):
    one = video(person, a_case, "BWC1-1", name="BWC1-1_202511061420_a.mp4")
    signed_in(client, person)
    told = client.post(
        reverse("case-paths-add", args=[a_case.pk]),
        {
            "files": [
                io.BytesIO(body_file()),
            ],
        },
    )
    # The browser names the file; the test client does not, so the name is "file".
    assert told.status_code == 200
    one_file = io.BytesIO(body_file())
    one_file.name = "BWC1-1_202511061420_a.vtt"
    told = client.post(
        reverse("case-paths-add", args=[a_case.pk]), {"files": [one_file]}
    ).json()
    assert [row["recording"] for row in told["landed"]] == [str(one.pk)]
    assert camera_paths.of(one) is not None


def test_the_map_route_is_answered_for_a_signed_in_person_and_refused_for_nobody(
    rf, person
):
    from django.contrib.auth.models import AnonymousUser

    request = rf.get("/maps-auth", HTTP_X_FORWARDED_URI="/maps/basemap.pmtiles")
    request.user = AnonymousUser()
    assert media_access.may_serve_map(request).status_code == 401
    request.user = person
    assert media_access.may_serve_map(request).status_code == 200
    stripped = rf.get("/maps-auth", HTTP_X_FORWARDED_URI="/basemap.pmtiles?x=1")
    stripped.user = person
    assert media_access.may_serve_map(stripped).status_code == 200
    other = rf.get("/maps-auth", HTTP_X_FORWARDED_URI="/maps/../cases/x.mp4")
    other.user = person
    assert media_access.may_serve_map(other).status_code == 404
    settings_store.set_to("maps", False)
    assert media_access.may_serve_map(request).status_code == 404


def test_the_basemap_state_says_absent_until_the_file_is_there(settings, tmp_path):
    assert maps.basemap_present() is False
    assert maps.basemap_state()["present"] is False
    assert maps.basemap_json()["url"] == ""
    maps.maps_dir().mkdir(parents=True, exist_ok=True)
    maps.basemap_file().write_bytes(b"PMTiles" + b"\0" * 100)
    assert maps.basemap_present() is True
    state = maps.basemap_state()
    assert state["present"] is True and state["words"].startswith("installed, 0 MB")
    assert maps.basemap_json()["url"] == "/maps/basemap.pmtiles"


# The joins -------------------------------------------------------------------------


def test_the_counts_and_links_reach_home_search_notes_and_incidents(
    client, person, a_case
):
    one = video(person, a_case, "BWC2-1")
    added(one, body_file(), by=person)
    case_chronology.place(one, dt.date(2025, 11, 6), 50000.0, by=person)
    video(person, a_case, "BWC5-1")
    counts = dashboard.counts_for([a_case], person)[a_case.pk]
    assert counts["paths"] == 1
    pills = dashboard.pills(a_case, "owner", person, counts)
    assert any(p["words"] == "1 camera on the map" for p in pills)
    note = notes.MomentNote.objects.create(
        recording=one, at=12.0, note="the stop begins", note_by=person
    )
    rows = notes._moment_rows(a_case)
    assert rows[0]["map"].endswith(f"?tab=map&recording={one.pk}&at=12.0")
    hits = case_search.search(a_case, "stop")
    notes_hits = [
        h for g in hits["groups"] for h in g["hits"] if h["who"].startswith("Note")
    ]
    assert notes_hits and notes_hits[0]["map"].endswith(f"&recording={one.pk}&at=12.0")
    day = case_chronology.day_of(a_case, dt.date(2025, 11, 6))
    entries = [e for spell in day["spells"] for e in spell["entries"]]
    assert entries and entries[0]["map"].endswith(f"&recording={one.pk}&at=12.0")
    assert entries[0]["id"] == note.pk
    incident = Incident.objects.create(case=a_case, name="Stop", created_by=person)
    IncidentCamera.objects.create(incident=incident, recording=one)
    # The incident's day as the chips compare it, ISO, whatever the incident keeps.
    incident.clock_date = "11/06/2025"
    incident.save()
    spans = camera_paths.map_of(a_case, viewer=person)["incidents"]
    assert spans[0]["date"] == "2025-11-06" and spans[0]["name"] == "Stop"
    assert camera_paths.incident_map_url(incident).endswith(
        f"?tab=map&incident={incident.pk}"
    )
    signed_in(client, person)
    page = client.get(reverse("case", args=[a_case.pk]) + "?tab=incidents")
    assert f"?tab=map&amp;incident={incident.pk}" in page.content.decode()
    page = client.get(reverse("case", args=[a_case.pk]) + "?tab=details")
    assert "1 camera with a path file" in page.content.decode()
    assert "1 video without" in page.content.decode()
    settings_store.set_to("maps", False)
    counts = dashboard.counts_for([a_case], person)[a_case.pk]
    assert counts["paths"] == 1
    pills = dashboard.pills(a_case, "owner", person, counts)
    assert not any("on the map" in p["words"] for p in pills)
    assert camera_paths.incident_map_url(incident) == ""


# The path file's clock places the recording (chapter 2, v1.188.0) ----------------


def test_an_in_car_file_places_a_clockless_recording_and_goes_with_the_file(
    person, a_case
):
    car = video(person, a_case, "Dash-4", name="clip.mp4", seconds=300)
    assert case_chronology.clock_of(car) == (None, None, "")
    path, _ = added(car, car_file(), by=person)
    car.refresh_from_db()
    assert case_chronology.clock_of(car) == (dt.date(2025, 11, 6), 51603.0, "path")
    assert case_chronology.placed_words(car) == "from its path file, walker"
    assert case_chronology.clock_surety(car)["word"] == "Clear"
    row = Row.objects.get(event="recording placed on the clock")
    assert row.details["how"] == "path"
    # A replacement places afresh; a removal takes the clock with the file.
    added(car, car_file(drift=5.0), by=person, replace=True)
    car.refresh_from_db()
    assert case_chronology.clock_of(car)[2] == "path"
    assert case_chronology.clock_surety(car)["word"] == "Likely"
    camera_paths.remove(camera_paths.of(car), by=person)
    car.refresh_from_db()
    assert case_chronology.clock_of(car) == (None, None, "")
    assert Row.objects.filter(event="recording taken off the clock").count() == 1


def test_the_path_clock_never_takes_over_a_clock_somebody_else_gave(person, a_case):
    by_hand = video(person, a_case, "Dash-5", seconds=300)
    case_chronology.place(by_hand, dt.date(2025, 11, 6), 1000.0, by=person)
    added(by_hand, car_file(), by=person)
    by_hand.refresh_from_db()
    placed = case_chronology.clock_of(by_hand)
    assert placed == (dt.date(2025, 11, 6), 1000.0, "hand")
    stamped = video(
        person, a_case, "Dash-6", seconds=300, stamp=stamp("09:00:00", "D6")
    )
    added(stamped, car_file(), by=person)
    stamped.refresh_from_db()
    assert case_chronology.clock_of(stamped)[2] == "clock"
    body = video(person, a_case, "BWC2-1")
    added(body, body_file(), by=person)
    body.refresh_from_db()
    assert case_chronology.clock_of(body) == (None, None, "")
    assert Row.objects.filter(event="recording placed on the clock").count() == 1


# The readings in the memo, the comparison and the timeline report (chapter 2) -----


def test_the_readings_join_the_memo_the_comparison_and_the_report(person, a_case):
    from core import prompts, timeline_report

    car = video(person, a_case, "Dash-4", seconds=300)
    added(car, car_file(), by=person)
    incident = Incident.objects.create(case=a_case, name="Stop", created_by=person)
    IncidentCamera.objects.create(incident=incident, recording=car)
    lines = camera_paths.readings_lines_for_incident(incident)
    assert len(lines) == 1 and lines[0].startswith("Camera ")
    assert "lights on" in lines[0] and "unit" not in lines[0].split(":")[0].lower()
    block = camera_paths.readings_block_for_incident(incident)
    assert block.startswith("The cameras' own files")
    memo = prompts.incident_memo_input("Cameras: one", [], "the record", readings=block)
    assert block in memo and memo.index("the record") < memo.index(block)
    without = prompts.incident_memo_input("Cameras: one", [], "the record")
    assert "own files" not in without
    compare = prompts.comparison_input(
        "head", [], "the record", "1. words", first=1, last=1, readings=block
    )
    assert block in compare and compare.index(block) < compare.index("The report")
    source = (HERE / "core" / "comparison.py").read_text(encoding="utf-8")
    assert "readings_block_for_incident(comparison.incident)" in source
    source = (HERE / "core" / "incident_assistant.py").read_text(encoding="utf-8")
    assert "readings=readings" in source and "camera_paths.RULE" in source
    report = (HERE / "core" / "timeline_report.py").read_text(encoding="utf-8")
    assert "readings_lines_for_incident(incident)" in report
    assert "The cameras' own files" in report
    assert str(LAT) not in block and "N10" not in "".join(lines)
    _ = timeline_report
