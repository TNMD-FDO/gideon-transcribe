"""v1.63.0: the clip across cameras (Phase 7, chapter 1).

The rules checked here: the tile table and the picture sizes the chapter
fixes; the clock text to the byte, and the clock's second normalised into
the day; the filter graph per tile, the stack, the clock and the sound with
silence where the sound camera was not running; the ffmpeg arguments with a
seek, a length and the thread cap before every input; the id files written
and taken away; a failed cut leaving no file; the render dispatching an
Incident clip to cut_wall from its own picture and an ordinary Clip to
cut_clip as before; the endpoint's refusals and what a good press makes;
where the clip shows and where it does not; the setting; and the words.
"""

from __future__ import annotations

import io
import json
import re
import uuid
import zipfile
from pathlib import Path

import pytest
from core import (
    chronology,
    clip_pages,
    clip_work,
    incident_clips,
    incidents,
    media,
    settings_store,
    tasks,
)
from core.audit import Row
from core.cases import Case
from core.clips import Clip, RenderState
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording

APP = Path(__file__).resolve().parent.parent
ROOT = APP.parent
PASSWORD = "a-long-enough-password"
FONT = "'/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'"


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


@pytest.fixture
def incident(person, a_case):
    # The first camera starts at 0 on the Incident clock (21:56:17), the
    # second 281 s later; both run for ten minutes.
    first = video(person, a_case, "first", stamp=stamp("21:56:19", "BWC2-1"))
    second = video(person, a_case, "second", stamp=stamp("22:01:00", "BWC2-2"))
    return incidents.make(a_case, "Stop", [first, second], by=person)


@pytest.fixture
def event(incident, person):
    return chronology.add(
        incident, {"at": "300", "text": "Asked out of the car"}, by=person
    )


@pytest.fixture
def no_render(monkeypatch):
    """Nothing is deferred to the queue; what would have been is remembered."""
    seen = []

    class Deferrer:
        def __init__(self, **options):
            self.options = options

        def defer(self, **fields):
            seen.append({"options": self.options, **fields})

    monkeypatch.setattr(tasks.render_clip, "configure", lambda **o: Deferrer(**o))
    monkeypatch.setattr(
        tasks.render_clip, "defer", lambda **f: seen.append({"options": {}, **f})
    )
    return seen


def cameras_of(incident) -> dict:
    return {
        one.camera_id(): one for one in incident.cameras.select_related("recording")
    }


def docx_text(body: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(body)) as bundle:
        return bundle.read("word/document.xml").decode("utf-8")


# The tiles and the clock -------------------------------------------------------


def test_the_tile_table_is_the_chapters():
    boxes, picture = media.tile_boxes("focus", 1)
    assert boxes == [(0, 0, 1280, 720)] and picture == (1280, 720)
    boxes, picture = media.tile_boxes("focus", 3)
    assert boxes == [(0, 0, 1280, 720), (320, 720, 320, 180), (640, 720, 320, 180)]
    assert picture == (1280, 900)
    boxes, _ = media.tile_boxes("focus", 5)
    assert [box[0] for box in boxes[1:]] == [0, 320, 640, 960]
    boxes, _ = media.tile_boxes("focus", 2)
    assert boxes[1] == (480, 720, 320, 180)
    boxes, picture = media.tile_boxes("grid", 2)
    assert boxes == [(0, 0, 640, 360), (640, 0, 640, 360)] and picture == (1280, 360)
    boxes, picture = media.tile_boxes("grid", 4)
    assert boxes == [
        (0, 0, 640, 360),
        (640, 0, 640, 360),
        (0, 360, 640, 360),
        (640, 360, 640, 360),
    ]
    assert picture == (1280, 720)
    boxes, picture = media.tile_boxes("grid", 5)
    assert [box[:2] for box in boxes] == [
        (0, 0),
        (428, 0),
        (854, 0),
        (0, 240),
        (428, 240),
    ]
    assert boxes[0][2:] == (426, 240) and picture == (1280, 480)
    boxes, picture = media.tile_boxes("grid", 9)
    assert boxes[-1] == (854, 480, 426, 240) and picture == (1280, 720)
    # Every size even, every tile inside the picture, no two overlapping.
    for layout, most in (("focus", 5), ("grid", 9)):
        for count in range(1, most + 1):
            boxes, (width, height) = media.tile_boxes(layout, count)
            assert width == 1280 and height % 2 == 0
            for x, y, w, h in boxes:
                assert w % 2 == 0 and h % 2 == 0 and x + w <= width and y + h <= height
            for index, (x, y, w, h) in enumerate(boxes):
                for x2, y2, w2, h2 in boxes[index + 1 :]:
                    assert x + w <= x2 or x2 + w2 <= x or y + h <= y2 or y2 + h2 <= y
    for layout, count in (("focus", 0), ("grid", 10), ("focus", 6), ("row", 2)):
        with pytest.raises(ValueError):
            media.tile_boxes(layout, count)


def test_the_clock_text_to_the_byte_and_the_delta_in_the_day(incident):
    assert media.clock_text(34215) == r"%{pts\:gmtime\:34215\:%T}"
    assert ":" not in media.clock_text(5).replace(r"\:", "")
    incident.clock_zero = 79270.0
    assert incident_clips.clock_delta(incident, 0.0) == 79270
    incident.clock_zero = 86395.0
    assert incident_clips.clock_delta(incident, 10.0) == 5
    incident.clock_zero = 100.0
    assert incident_clips.clock_delta(incident, -280.0) == 86220
    incident.clock_zero = None
    assert incident_clips.clock_delta(incident, 3.0) is None


def test_the_id_label_fits_its_tile():
    long = "AXON Body 3 X6039A12 issued to Officer Hale on 6 June\nsecond line"
    assert "\n" not in media.id_label(long, 1280)
    assert len(media.id_label(long, 1280)) == 40
    assert len(media.id_label(long, 320)) == 30
    assert media.id_label("  Dash cam   12 ", 640) == "Dash cam 12"


# The filter graph --------------------------------------------------------------


def three_focus():
    return [
        media.Tile(Path("/v/A/playback.mp4"), 612.4, "AXON Body 3 X6039A12"),
        media.Tile(Path("/v/B/playback.mp4"), 87.15, "Dash cam 12"),
        media.Tile(Path("/v/C/playback.mp4"), -4.0, "X6039A15"),
    ]


def ids(count):
    return [Path(f"/tmp/tmpk3j1/tile-{index}.txt") for index in range(count)]


def test_the_graph_for_three_cameras_in_focus():
    graph = media.wall_filter(
        three_focus(), "focus", 30.0, sound=0, clock=34215, id_files=ids(3)
    )
    chains = graph.split(";")
    assert len(chains) == 5
    assert chains[0] == (
        "[0:v]setpts=PTS-STARTPTS,fps=30,"
        "scale=w='trunc(min(1280,720*dar)/2)*2':h='trunc(min(720,1280/dar)/2)*2',"
        "pad=1280:720:-1:-1:color=black,setsar=1,"
        "tpad=start_duration=0.000:stop_duration=30.000:color=black,format=yuv420p,"
        f"drawtext=fontfile={FONT}:fontsize=22:fontcolor=white:borderw=2:"
        "bordercolor=black@0.5:textfile='/tmp/tmpk3j1/tile-0.txt':expansion=none:"
        "x=8:y=h-th-8[t0]"
    )
    # The small tiles at 16 px; the late camera black for its first four seconds.
    assert "scale=w='trunc(min(320,180*dar)/2)*2'" in chains[1]
    assert "fontsize=16" in chains[1] and "tile-1.txt" in chains[1]
    assert "tpad=start_duration=4.000:stop_duration=30.000" in chains[2]
    assert chains[2].endswith("[t2]")
    assert chains[3] == (
        "[t0][t1][t2]xstack=inputs=3:layout=0_0|320_720|640_720:fill=black,"
        f"drawtext=fontfile={FONT}:fontsize=28:fontcolor=white:borderw=2:"
        "bordercolor=black@0.5:x=w-tw-16:y=16:text='"
        + r"%{pts\:gmtime\:34215\:%T}"
        + "'[v]"
    )
    assert chains[4] == "[0:a]apad=whole_dur=30.000[a]"


def test_the_graph_for_a_grid_with_the_sound_starting_inside_the_span():
    tiles = [
        media.Tile(Path("/v/P/playback.mp4"), 100.0, "P"),
        media.Tile(Path("/v/Q/playback.mp4"), -2.5, "Q"),
        media.Tile(Path("/v/R/playback.mp4"), 7.0, "R"),
        media.Tile(Path("/v/S/playback.mp4"), 233.25, "S"),
    ]
    graph = media.wall_filter(
        tiles, "grid", 20.0, sound=1, clock=34215, id_files=ids(4)
    )
    assert "xstack=inputs=4:layout=0_0|640_0|0_360|640_360:fill=black" in graph
    assert "scale=w='trunc(min(640,360*dar)/2)*2'" in graph and "fontsize=22" in graph
    # Silence written for the lead, not a shifted timestamp, then padded to the span.
    assert graph.endswith(
        "[1:a]adelay=delays=2500:all=1,aresample=async=1:first_pts=0,"
        "apad=whole_dur=20.000[a]"
    )
    # Without the ids or the clock, no drawtext at all.
    plain = media.wall_filter(tiles, "grid", 20.0, sound=0, clock=None, id_files=None)
    assert "drawtext" not in plain and "fill=black[v];" in plain


def test_the_graph_for_one_camera_has_no_stack():
    tile = media.Tile(Path("/v/A/playback.mp4"), 3.0, "A")
    plain = media.wall_filter([tile], "focus", 10.0, sound=0, clock=None, id_files=None)
    assert plain == (
        "[0:v]setpts=PTS-STARTPTS,fps=30,"
        "scale=w='trunc(min(1280,720*dar)/2)*2':h='trunc(min(720,1280/dar)/2)*2',"
        "pad=1280:720:-1:-1:color=black,setsar=1,"
        "tpad=start_duration=0.000:stop_duration=10.000:color=black,format=yuv420p[v];"
        "[0:a]apad=whole_dur=10.000[a]"
    )
    with_clock = media.wall_filter(
        [tile], "grid", 10.0, sound=0, clock=7, id_files=None
    )
    assert with_clock.startswith("[0:v]setpts") and ",drawtext=" in with_clock
    assert "xstack" not in with_clock and with_clock.count("[v]") == 1


def test_the_arguments_and_the_id_files(monkeypatch, tmp_path):
    seen = {}

    def remember(arguments, timeout):
        seen["arguments"] = arguments
        seen["timeout"] = timeout
        # The id files are there while ffmpeg runs, one line each, cut.
        files = [Path(one.strip("'")) for one in _textfiles(arguments)]
        seen["ids"] = [one.read_text(encoding="utf-8") for one in files]
        seen["files"] = files
        Path(arguments[-1]).write_bytes(b"mp4")

        class Finished:
            returncode = 0
            stderr = ""

        return Finished()

    monkeypatch.setattr(media, "_run", remember)
    monkeypatch.setenv("MEDIA_THREADS_PER_JOB", "8")
    target = tmp_path / "clips" / "one.mp4"
    tiles = three_focus()
    tiles[1] = media.Tile(
        tiles[1].source, tiles[1].offset, "A very long dash camera name indeed, unit 12"
    )
    media.cut_wall(
        tiles, target, 30.0, layout="focus", sound=0, clock=34215, timeout=750
    )
    arguments = seen["arguments"]
    assert seen["timeout"] == 750 and target.exists()
    # One -threads, -ss, -t before each -i, in tile order; never a negative seek;
    # the late camera's length shortened by its lead.
    inputs = [index for index, one in enumerate(arguments) if one == "-i"]
    assert len(inputs) == 3
    for index, tile in zip(inputs, tiles, strict=True):
        assert arguments[index - 6 : index] == [
            "-threads",
            "8",
            "-ss",
            f"{tile.seek:.3f}",
            "-t",
            f"{30.0 - tile.lead:.3f}",
        ]
        assert arguments[index + 1] == str(tile.source)
    assert arguments[inputs[2] - 3 : inputs[2]] == ["-ss", "0.000", "-t", "26.000"][1:]
    after = arguments[inputs[-1] + 2 :]
    assert after[:2] == ["-filter_complex_threads", "8"]
    assert after[2] == "-filter_complex" and after[3].startswith("[0:v]setpts")
    assert after[4:10] == ["-map", "[v]", "-map", "[a]", "-t", "30.000"]
    assert after[10:12] == ["-threads", "8"]
    assert after[12:] == [
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(target),
    ]
    assert seen["ids"] == [
        "AXON Body 3 X6039A12",
        "A very long dash camera name i",
        "X6039A15",
    ]
    assert not any(one.exists() for one in seen["files"])


def _textfiles(arguments):
    """The id files named in the graph, as paths again (the colon unescaped)."""
    graph = arguments[arguments.index("-filter_complex") + 1]
    return [
        "'" + found.replace(r"\:", ":") + "'"
        for found in re.findall(r"textfile='([^']*)'", graph)
    ]


def test_a_failed_cut_leaves_no_file(monkeypatch, tmp_path):
    def fail(arguments, timeout):
        Path(arguments[-1]).write_bytes(b"half")

        class Finished:
            returncode = 1
            stderr = "Fontconfig error: cannot load default config file"

        return Finished()

    monkeypatch.setattr(media, "_run", fail)
    target = tmp_path / "clips" / "one.mp4"
    with pytest.raises(media.MediaError) as caught:
        media.cut_wall(three_focus(), target, 30.0, layout="focus", sound=0, clock=None)
    assert caught.value.reason_class == "clip_render_failed"
    assert not target.exists()
    with pytest.raises(media.MediaError):
        media.cut_wall([], target, 30.0, layout="grid", sound=0, clock=None)


# The render ----------------------------------------------------------------------


def an_incident_clip(incident, event, person, *, layout="focus", from_at=290.0):
    cams = cameras_of(incident)
    chosen = [cams["BWC2-1"], cams["BWC2-2"]]
    sound = cams["BWC2-1"]
    picture = incident_clips.picture_for(
        incident,
        chosen,
        sound,
        layout,
        (from_at, from_at + 20.0),
        burn_clock=True,
        burn_ids=True,
    )
    return Clip.objects.create(
        recording=sound.recording,
        user=person,
        title=event.text,
        start=from_at - sound.starts_at,
        end=from_at + 20.0 - sound.starts_at,
        incident=incident,
        event=event,
        picture=picture,
    )


def test_the_render_cuts_the_wall_from_the_clips_own_picture(
    incident, event, person, monkeypatch
):
    clip = an_incident_clip(incident, event, person)
    seen = []

    def remember(arguments, timeout):
        seen.append((arguments, timeout))
        Path(arguments[-1]).write_bytes(b"mp4")

        class Finished:
            returncode = 0
            stderr = ""

        return Finished()

    monkeypatch.setattr(media, "_run", remember)
    clip_work.render(clip)
    clip.refresh_from_db()
    assert clip.state == RenderState.READY and clip.size_bytes == 3
    assert clip.captions_of == "" and clip.downloads == 0
    arguments, timeout = seen[0]
    # The span plus five minutes plus a minute per camera.
    assert timeout == 20 + 300 + 120
    assert arguments.count("-i") == 2 and "-filter_complex" in arguments
    seeks = [
        arguments[index + 1] for index, one in enumerate(arguments) if one == "-ss"
    ]
    assert seeks == ["290.000", "9.000"]
    graph = arguments[arguments.index("-filter_complex") + 1]
    assert "layout=0_0|480_720" in graph and "[0:a]apad" in graph
    assert r"%{pts\:gmtime\:79267\:%T}" in graph
    # A camera re-synced and renamed afterwards changes nothing: the offsets
    # and the ids were copied when the clip was made.
    cams = cameras_of(incident)
    incidents.place_by_hand(cams["BWC2-2"], 100.0, by=person)
    cams["BWC2-2"].recording.title = "renamed"
    cams["BWC2-2"].recording.save()
    clip_work.render(clip)
    again, _ = seen[1]
    assert [
        again[index + 1] for index, one in enumerate(again) if one == "-ss"
    ] == seeks
    # The same graph but for the id files' folder, which is new each run.
    without_files = re.compile(r"textfile='[^']*'")
    assert without_files.sub(
        "textfile=X", again[again.index("-filter_complex") + 1]
    ) == (without_files.sub("textfile=X", graph))


def test_the_render_fails_plainly_when_a_copy_is_missing(
    incident, event, person, monkeypatch
):
    clip = an_incident_clip(incident, event, person)
    cams = cameras_of(incident)
    (cams["BWC2-2"].recording.folder / "playback.mp4").unlink()
    monkeypatch.setattr(media, "_run", lambda *a, **k: pytest.fail("ffmpeg ran"))
    clip_work.render(clip)
    clip.refresh_from_db()
    assert (
        clip.state == RenderState.FAILED and clip.failure_class == "clip_render_failed"
    )
    row = Row.objects.filter(event="Clip render failed").order_by("-at").first()
    assert row is not None and row.object_label == "290.0-310.0"
    # A cut that fails inside ffmpeg is the same failure with no file left.
    (cams["BWC2-2"].recording.folder / "playback.mp4").write_bytes(b"back")

    def fail(arguments, timeout):
        Path(arguments[-1]).write_bytes(b"half")

        class Finished:
            returncode = 1
            stderr = "boom"

        return Finished()

    monkeypatch.setattr(media, "_run", fail)
    clip_work.render(clip)
    clip.refresh_from_db()
    assert clip.state == RenderState.FAILED and not clip.path.exists()


def test_an_ordinary_clip_still_goes_through_cut_clip(incident, person, monkeypatch):
    recording = cameras_of(incident)["BWC2-1"].recording
    clip = Clip.objects.create(
        recording=recording, user=person, title="Plain", start=10.0, end=25.0
    )
    seen = []

    def remember(arguments, timeout):
        seen.append((arguments, timeout))
        Path(arguments[-1]).write_bytes(b"mp4")

        class Finished:
            returncode = 0
            stderr = ""

        return Finished()

    monkeypatch.setattr(media, "_run", remember)
    clip_work.render(clip)
    arguments, timeout = seen[0]
    assert timeout == 15 + 300 and arguments.count("-i") == 1
    assert "-filter_complex" not in arguments and "10.000" in arguments
    assert clip_work.timeout_for(clip) == 315


# The endpoint --------------------------------------------------------------------


def url_for(incident, event) -> str:
    return f"/case/{incident.case_id}/incident/{incident.pk}/event/{event.pk}/clip"


def press(client, incident, event, **body):
    cams = cameras_of(incident)
    wanted = {
        "from": 290,
        "until": 310,
        "cameras": [str(cams["BWC2-1"].pk), str(cams["BWC2-2"].pk)],
        "sound": str(cams["BWC2-1"].pk),
        "layout": "focus",
        "burn_clock": True,
        "burn_ids": True,
        "title": "",
    }
    wanted.update(body)
    return client.post(
        url_for(incident, event), json.dumps(wanted), content_type="application/json"
    )


def test_the_switches_and_the_standing(incident, event, person, client, no_render):
    signed_in(client, person)
    for key in ("incidents_clips", "clips_available"):
        settings_store.set_to(key, False)
        assert press(client, incident, event).status_code == 403
        settings_store.set_to(key, True)
    settings_store.set_to("incidents", False)
    assert press(client, incident, event).status_code == 404
    settings_store.set_to("incidents", True)
    # Every local account is an Admin, who may look in; a directory user who
    # is not on the case is told there is no such page.
    stranger = User.objects.create(username="stranger", display_name="stranger")
    signed_in(client, stranger)
    assert press(client, incident, event).status_code == 404
    assert Clip.objects.count() == 0 and not no_render


def test_the_refusals(incident, event, person, client, no_render):
    signed_in(client, person)
    cams = cameras_of(incident)
    first, second = str(cams["BWC2-1"].pk), str(cams["BWC2-2"].pk)

    def refused(words, **body):
        answer = press(client, incident, event, **body)
        assert answer.status_code == 400, answer.content
        assert answer.json()["error"] == words

    refused("A clip is at least one second long.", **{"from": 300, "until": 300.5})
    refused("A clip may be up to 30 minutes long.", **{"from": 0, "until": 1801})
    made_up = [str(uuid.uuid4()) for _ in range(10)]
    refused("Up to nine cameras in one clip.", cameras=made_up)
    refused("Focus holds up to five cameras.", cameras=made_up[:6])
    refused("Tick at least one camera.", cameras=[])
    refused("That camera is not on this incident.", cameras=[first, str(event.pk)])
    # The second camera starts at 281: a span before it is refused.
    refused("BWC2-2 is not running then.", **{"from": 100, "until": 120})
    refused(
        "The sound must come from one of the clip's cameras.",
        cameras=[first],
        sound=second,
    )
    refused("Those times could not be read.", **{"from": "soon"})
    (cams["BWC2-2"].recording.folder / "playback.mp4").unlink()
    refused("BWC2-2 is not synced with a playback copy.")
    assert Clip.objects.count() == 0 and not no_render


def test_a_good_press_makes_the_clip(incident, event, person, client, no_render):
    signed_in(client, person)
    cams = cameras_of(incident)
    answer = press(
        client,
        incident,
        event,
        cameras=[str(cams["BWC2-2"].pk), str(cams["BWC2-1"].pk)],
        sound=str(cams["BWC2-2"].pk),
    )
    assert answer.status_code == 200, answer.content
    got = answer.json()
    clip = Clip.objects.get()
    assert clip.recording_id == cams["BWC2-2"].recording_id
    # The span moved onto the sound camera's own clock: it starts at 281.
    assert clip.start == pytest.approx(9.0) and clip.end == pytest.approx(29.0)
    assert clip.title == "Asked out of the car" and clip.burn_captions is False
    assert clip.incident_id == incident.pk and clip.event_id == event.pk
    picture = clip.picture
    assert picture["clock"] == 79267 and isinstance(picture["clock"], int)
    assert (
        picture["layout"] == "focus" and picture["burn_clock"] and picture["burn_ids"]
    )
    assert [one["label"] for one in picture["cameras"]] == ["BWC2-2", "BWC2-1"]
    assert [one["offset"] for one in picture["cameras"]] == [9.0, 290.0]
    assert picture["span"] == [290.0, 310.0] and picture["sound"] == str(
        cams["BWC2-2"].pk
    )
    # Rendered one at a time on the media worker, under one lock.
    assert no_render == [
        {"options": {"lock": "incident-clip"}, "clip_id": str(clip.pk)}
    ]
    row = Row.objects.filter(event="Clip created").order_by("-at").first()
    assert row.details["cameras"] == 2 and row.details["layout"] == "focus"
    assert "Asked" not in json.dumps(row.details) and row.object_label == "290.0-310.0"
    # The answer carries the row, the count on the event and the state.
    assert got["clip"]["cameras"] == "2 cameras, Focus"
    assert got["clip"]["from_event"] == "from the event Asked out of the car"
    assert (
        got["clip"]["span"] == "22:01:07 to 22:01:27"
        and got["clip"]["length"] == "20 s"
    )
    assert (
        got["clip"]["may_adjust"] is False
        and got["clip"]["incident_url"] == incident.url()
    )
    assert got["event_clips"] == 1
    events = {one["id"]: one for one in got["state"]["events"]}
    assert events[str(event.pk)]["clips"] == 1
    # Without an Incident clock the clock is not burned, whatever was asked.
    incident.clock_zero = None
    incident.save(update_fields=["clock_zero"])
    answer = press(client, incident, event, layout="grid", title="  Grid one  ")
    later = Clip.objects.exclude(pk=clip.pk).get()
    assert later.picture["clock"] is None and later.picture["burn_clock"] is False
    assert later.title == "Grid one" and later.span == "4:50 to 5:10"


def test_the_rules_the_review_added(
    incident, event, person, client, no_render, monkeypatch
):
    """A body that is not an object, Process again on the sound camera, a
    recording that carries an incident clip staying in its case, and a
    camera moved away failing the render plainly."""
    signed_in(client, person)
    cams = cameras_of(incident)
    answer = client.post(
        url_for(incident, event), "[]", content_type="application/json"
    )
    assert (
        answer.status_code == 400
        and answer.json()["error"] == "That could not be read."
    )
    # A camera listed twice is counted once.
    first, second = str(cams["BWC2-1"].pk), str(cams["BWC2-2"].pk)
    answer = press(client, incident, event, cameras=[first, first, second])
    assert answer.status_code == 200
    assert len(Clip.objects.get().picture["cameras"]) == 2
    Clip.objects.all().delete()
    monkeypatch.setattr("core.viewer.being_replaced", lambda recording: True)
    answer = press(client, incident, event)
    assert answer.status_code == 409 and "transcribed again" in answer.json()["error"]
    monkeypatch.setattr("core.viewer.being_replaced", lambda recording: False)
    assert press(client, incident, event).status_code == 200
    clip = Clip.objects.get()
    # The sound camera's recording cannot leave the case while the clip is on it.
    from core.jobs import Transcript

    sound = cams["BWC2-1"].recording
    Transcript.objects.create(recording=sound, language="en")
    other = Case.objects.create(owner=person, name="Another matter")
    answer = client.post(f"/recording/{sound.pk}/move", {"case": str(other.pk)})
    assert answer.status_code == 400
    assert answer.json()["why"] == (
        "This recording carries 1 clip cut from an incident in this case. Delete "
        "them first, or leave the recording here."
    )
    sound.refresh_from_db()
    assert sound.case_id == incident.case_id
    # The other camera moved away: Render again says so and cuts nothing.
    away = cams["BWC2-2"].recording
    away.case = other
    away.save(update_fields=["case"])
    tiles, _, why = clip_work.tiles_of(clip)
    assert tiles == [] and why == "camera BWC2-2 is no longer in this case"
    # With the clip gone, the recording may move.
    clip.delete()
    answer = client.post(f"/recording/{sound.pk}/move", {"case": str(other.pk)})
    assert answer.status_code == 200 and answer.json()["ok"] is True


# Where it shows --------------------------------------------------------------------


def test_where_the_clip_shows_and_where_it_does_not(
    incident, event, person, client, no_render
):
    clip = an_incident_clip(incident, event, person)
    cams = cameras_of(incident)
    recording = cams["BWC2-1"].recording
    signed_in(client, person)
    # The case's Clips tab and the Clips page, with the Cameras column.
    page = client.get(f"/case/{incident.case_id}?tab=clips").content.decode()
    assert "<th>Cameras</th>" in page and "2 cameras, Focus" in page
    assert "from the event Asked out of the car" in page
    assert "22:01:07 to 22:01:27" in page and "Open the incident" in page
    assert "Open in viewer" not in page
    page = client.get("/clips").content.decode()
    assert "2 cameras, Focus" in page and "from the event Asked out of the car" in page
    assert f'data-open="{incident.url()}"' in page and "Open the incident" in page
    # An ordinary clip on the Clips page shows its span and length at last.
    plain = Clip.objects.create(
        recording=recording, user=person, title="Plain", start=10.0, end=25.0
    )
    page = client.get("/clips").content.decode()
    assert "00:00:10 to 00:00:25" in page and "15 s" in page
    # The viewer's sheet lists the recording's own clips and not the wall.
    listed = client.get(f"/recording/{recording.pk}/clips").json()["clips"]
    assert [one["id"] for one in listed] == [str(plain.pk)]
    # The span of an Incident clip is its event's: only a new clip changes it.
    answer = client.post(
        f"/clip/{clip.pk}",
        json.dumps({"start": 1, "end": 5}),
        content_type="application/json",
    )
    assert answer.status_code == 400 and "cut from its event" in answer.json()["error"]
    answer = client.post(
        f"/clip/{clip.pk}",
        json.dumps({"title": "Renamed"}),
        content_type="application/json",
    )
    assert answer.status_code == 200 and Clip.objects.get(pk=clip.pk).title == "Renamed"
    # The Word export lists the clips made from events under the table.
    text = docx_text(chronology.word(incident, None, "asker"))
    assert "Clips made from events: #1 Renamed (20 s)." in text
    # The event removed: the clip stays and says so.
    chronology.remove(event, by=person)
    clip.refresh_from_db()
    assert clip.event_id is None and clip.from_event == "from an event since removed"
    assert (
        chronology.clips_line(incident, {}) == "Clips made from events: Renamed (20 s)."
    )
    # Render again keeps the lock; delete takes the file and the row.
    no_render.clear()
    client.post(f"/clip/{clip.pk}/rerender")
    assert no_render[0]["options"] == {"lock": "incident-clip"}
    clip.folder.mkdir(parents=True, exist_ok=True)
    clip.path.write_bytes(b"mp4")
    client.post(f"/clip/{clip.pk}/delete")
    assert not clip.path.exists() and not Clip.objects.filter(pk=clip.pk).exists()


def test_the_row_and_the_span_words(incident, event, person):
    clip = an_incident_clip(incident, event, person)
    row = clip_pages._row(clip, asker=person)
    assert row["picture"] is True and row["cameras"] == "2 cameras, Focus"
    assert row["may_change"] is True and row["may_adjust"] is False
    assert clip.span_label == "290.0-310.0" and clip.suffix == ".mp4"
    assert clip.path.name == f"{clip.pk}.mp4"
    plain = Clip.objects.create(
        recording=clip.recording, user=person, title="p", start=3.0, end=8.0
    )
    assert clip_pages._row(plain, asker=person)["may_adjust"] is True
    assert plain.span_label == "3.0-8.0" and plain.cameras_line == ""


# The setting and the words ---------------------------------------------------------


def test_the_setting_is_greyed_under_either_switch():
    known = settings_store.definition("incidents_clips")
    assert (
        known.page == "incidents" and known.group == "Clips" and known.default is True
    )
    assert settings_store.greyed_because(known) == ""
    settings_store.set_to("clips_available", False)
    assert settings_store.greyed_because(known) == (
        "Greyed while Clips available is off; the value is kept."
    )
    settings_store.set_to("clips_available", True)
    settings_store.set_to("incidents", False)
    assert "Incidents is off" in settings_store.greyed_because(known)
    settings_store.set_to("incidents", True)
    settings_store.set_to("incidents_clips", False)
    assert incident_clips.on() is False


def test_the_words_are_in_the_documents():
    glossary = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    assert "**Incident clip**:" in glossary
    guide = (ROOT / "docs" / "user-guide.md").read_text(encoding="utf-8")
    assert "Clip this event" in guide
    admin = (ROOT / "docs" / "admin-guide.md").read_text(encoding="utf-8")
    assert "Incident clips" in admin
    catalogue = (ROOT / "docs" / "spec" / "ADMIN-SETTINGS-CATALOGUE.md").read_text(
        encoding="utf-8"
    )
    assert "| Incident clips |" in catalogue and "v1.63.0" in catalogue
    dockerfile = (APP / "Dockerfile").read_text(encoding="utf-8")
    assert "fonts-dejavu-core" in dockerfile
    for word in ("drawtext", "xstack", "tpad", "DejaVuSans.ttf"):
        assert word in dockerfile
    note = (ROOT / "docs" / "research" / "incident-clip.md").read_text(encoding="utf-8")
    assert "xstack" in note and "gmtime" in note
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## v1.63.0" in changelog
