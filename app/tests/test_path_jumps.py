"""v1.211.0: the jump rules (Phase 12 chapter 6.11).

The rules checked here: a far point the file keeps returning to is left out
everywhere, a lone spike is left out, a jump that remains between two real
stretches is marked and the map breaks the line there, the readings and
the chat's block say what was left out with the metres, the bounds follow
the kept fixes, an honest file loses nothing, and the minute task reads
the old files again.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from core import camera_paths, settings_store
from core.cases import Case
from core.models import User
from core.recordings import Batch, MediaState, Recording
from tests.test_camera_paths import LAT, LON, body_reading, vtt

APP = Path(__file__).resolve().parent.parent
PASSWORD = "a-long-enough-password"
FAR = (LAT + 0.1, LON)  # about 11 km north


@pytest.fixture(autouse=True)
def on(db):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("maps", True)


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("asker", PASSWORD)


@pytest.fixture
def a_case(person):
    return Case.objects.create(owner=person, name="Harbour Street stop")


def reading_at(t, where):
    one = body_reading(t)
    one["gpsCoordinates"] = f"N{where[0]:.6f} W{-where[1]:.6f}"
    return one


def route(t):
    """The real route: a slow walk north, a few metres a second."""
    return (LAT + t * 0.00002, LON)


def jumping_file(seconds=120, home_every=20, spike_at=55) -> str:
    cues = []
    for t in range(seconds):
        if home_every and t % home_every == 10:
            where = FAR
        elif t == spike_at:
            where = (LAT - 0.2, LON + 0.1)  # a lone glitch, elsewhere
        else:
            where = route(t)
        cues.append((t, t + 1, reading_at(t, where)))
    return vtt(cues).decode()


def test_the_far_point_the_file_keeps_returning_to_is_left_out_everywhere():
    parsed = camera_paths.parse(jumping_file(spike_at=None))
    # Six visits to the far point, every one left out; the route is whole.
    dropped = [m for m in parsed.marks if m[1] == "dropped"]
    assert [m[0] for m in dropped] == [10.0, 30.0, 50.0, 70.0, 90.0, 110.0]
    assert all(m[2] > 10_000 for m in dropped)
    assert parsed.fix_count == 114
    assert all(abs(f[1] - LAT) < 0.01 for f in parsed.fixes)
    # No jump remains, so no line breaks; the bounds are the route's.
    assert not [m for m in parsed.marks if m[1] == "jump"]
    assert parsed.bounds[2] < LAT + 0.01


def test_a_lone_spike_between_agreeing_neighbours_is_left_out():
    parsed = camera_paths.parse(jumping_file(home_every=0, spike_at=50))
    dropped = [m for m in parsed.marks if m[1] == "dropped"]
    assert len(dropped) == 1 and dropped[0][0] == 50.0 and dropped[0][2] > 20_000
    assert parsed.fix_count == 119
    assert not [m for m in parsed.marks if m[1] == "jump"]


def test_a_jump_that_remains_is_marked_and_the_map_breaks_the_line_there():
    # The camera really moved far between two stretches: both stretches
    # are real, the step between them is not drawn.
    cues = []
    for t in range(60):
        cues.append((t, t + 1, reading_at(t, route(t))))
    for t in range(60, 120):
        cues.append((t, t + 1, reading_at(t, (FAR[0] + (t - 60) * 0.00002, FAR[1]))))
    parsed = camera_paths.parse(vtt(cues).decode())
    assert parsed.fix_count == 120
    jumps = [m for m in parsed.marks if m[1] == "jump"]
    assert len(jumps) == 1 and jumps[0][0] == 60.0 and jumps[0][2] > 10_000
    assert not [m for m in parsed.marks if m[1] == "dropped"]
    script = (APP / "static" / "map.js").read_text(encoding="utf-8")
    assert 'if (m[1] === "jump") { jumpAt[m[0]] = true; }' in script
    assert "|| jumpAt[f[0]]" in script
    assert 'ev.kind === "dropped" || ev.kind === "jump"' in script
    assert "left out as jumps" in script


def test_an_honest_file_loses_nothing():
    from tests.test_camera_paths import body_file, car_file

    for text in (body_file().decode(), car_file().decode()):
        parsed = camera_paths.parse(text)
        assert not [m for m in parsed.marks if m[1] in ("dropped", "jump")]


def video(person, case, title):
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        case=case,
        title=title,
        original_filename=f"{title}.mp4",
        media_state=MediaState.READY,
        duration_seconds=120.0,
        playback_ready=True,
        probe={},
    )
    recording.folder.mkdir(parents=True, exist_ok=True)
    (recording.folder / "playback.mp4").write_bytes(b"not really media")
    return recording


def test_the_readings_the_row_and_the_chat_say_what_was_left_out(person, a_case):
    recording = video(person, a_case, "BWC2-1")
    path, warnings = camera_paths.add(
        recording,
        data=jumping_file().encode(),
        filename="BWC2-1.vtt",
        by=person,
        request=None,
    )
    assert warnings == []
    assert camera_paths.dropped_count(path) == 7
    words = [e["words"] for e in camera_paths.events_of(path) if e["kind"] == "dropped"]
    assert len(words) == 7
    assert words[0].startswith("A fix ") and "km away left out" in words[0]
    assert "(7 left out as jumps)" in camera_paths.words(path)
    lines = camera_paths.readings_words(path, None)
    assert any("7 fixes left out as jumps" in line for line in lines)
    assert camera_paths.READ_VERSION == 2 and path.read_version == 2


def test_the_minute_task_reads_the_old_paths_again(person, a_case, monkeypatch):
    recording = video(person, a_case, "BWC2-1")
    path, _ = camera_paths.add(
        recording, data=jumping_file().encode(), filename="BWC2-1.vtt", by=person
    )
    path.read_version = 1
    path.save(update_fields=["read_version"])
    queued = []
    from core import tasks

    monkeypatch.setattr(
        tasks.read_camera_path, "defer", lambda **kw: queued.append(kw["path_id"])
    )
    assert camera_paths.read_again_the_old() == 1 and queued == [str(path.pk)]
    source = (APP / "core" / "tasks.py").read_text(encoding="utf-8")
    assert "camera_paths.read_again_the_old()" in source
