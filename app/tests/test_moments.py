"""Moments (Phase 4): what the camera showed at a time, as a model described it.

The rules checked here: a Moment is a clip cut from the Playback copy around
the chosen time, shown to the engine with the words spoken in it, never with
thinking, and the clip is gone whatever happens; the engine's request
carries a priority; an engine that takes no video says so; the endpoints
refuse while Moments are off, before the Playback copy exists, and for sound
alone; the state lists Moments; a Moment's words reach Summary and Chat as
labelled camera lines only while the office says so, and the exports carry
them in a section of their own; the audit rows carry no words; a Moment goes
with its Transcript; and the picture record (chapter 6) is cut where the
picture changes, described once per span with the previous span in hand,
never twice. The Cues of v1.40.0 to v1.50.1 are gone.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from core import assistant, engine, exports, media, prompts, settings_store
from core.assistant import Moment, PromptTemplate, Summary
from core.audit import Row
from core.jobs import Segment, Transcript
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording

PASSWORD = "a-long-enough-password"
CATALOGUE = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "spec"
    / "ADMIN-SETTINGS-CATALOGUE.md"
)


def a_line(number, start, speaker, text, segment_id=None):
    return prompts.Line(
        number=number,
        segment_id=segment_id or number,
        start=start,
        speaker=speaker,
        text=text,
    )


# Without a database ------------------------------------------------------------------


def test_the_record_is_cut_where_the_picture_changes():
    # No change points: the clock alone, spans that touch and never overlap.
    assert assistant.record_spans(900.0, [], 300.0, 3.0, 600) == [
        (0.0, 300.0),
        (300.0, 600.0),
        (600.0, 900.0),
    ]
    # Cut at the change points; a long stretch cut into equal pieces no
    # longer than the ceiling; a short one (100 to 101.5) joined to the span
    # before it.
    spans = assistant.record_spans(900.0, [100.0, 101.5, 450.0], 300.0, 3.0, 600)
    assert spans == [
        (0.0, 101.5),
        (101.5, 275.75),
        (275.75, 450.0),
        (450.0, 675.0),
        (675.0, 900.0),
    ]
    assert all(b > a for a, b in spans)
    assert all(spans[n][1] == spans[n + 1][0] for n in range(len(spans) - 1))
    # A span already covered by a Moment is left out: nothing twice.
    assert assistant.record_spans(
        900.0, [], 300.0, 3.0, 600, taken=[(300.0, 600.0)]
    ) == [(0.0, 300.0), (600.0, 900.0)]
    # Past the most allowed the cut is made coarser, never taken from the start.
    many = assistant.record_spans(3600.0, [], 15.0, 3.0, 20)
    assert len(many) <= 20 and many[0][0] == 0.0 and many[-1][1] == 3600.0
    assert assistant.record_spans(0.0, [], 15.0, 3.0, 600) == []
    # A long still span costs no more than a short busy one.
    assert assistant.record_fps(15.0, 2, 16) == 1.067
    assert assistant.record_fps(2.0, 2, 16) == 2.0
    assert assistant.record_fps(160.0, 2, 16) == 0.1


def test_the_scan_reads_ffmpeg_and_thins_what_it_finds():
    from core import moment_scan

    printed = "\n".join(
        [
            "frame:0 pts:0 pts_time:0",
            "lavfi.astats.Overall.RMS_level=-30.0",
            "frame:1 pts:16000 pts_time:1",
            "lavfi.astats.Overall.RMS_level=-29.5",
            "frame:2 pts:32000 pts_time:2",
            "lavfi.astats.Overall.RMS_level=-31.0",
            "frame:3 pts:48000 pts_time:3",
            "lavfi.astats.Overall.RMS_level=-12.0",
            "frame:4 pts:64000 pts_time:4",
            "lavfi.astats.Overall.RMS_level=-11.0",
            "frame:5 pts:80000 pts_time:5",
            "lavfi.astats.Overall.RMS_level=-inf",
            "frame:6 pts:96000 pts_time:6",
            "lavfi.astats.Overall.RMS_level=-30.5",
        ]
    )
    assert moment_scan.loud_from(printed, 12.0) == [3.0, 4.0]
    assert moment_scan.loud_from("nothing", 12.0) == []
    assert moment_scan.thin([3.0, 4.0, 40.0, 41.0, 70.0], 15.0) == [3.0, 40.0, 70.0]
    # The camera's clock in a question, and the stamp's arithmetic.
    assert prompts.times_in("what was in his hand at 12:40?", 900.0) == [760.0]
    assert prompts.times_in("at 1:02:03 and again at 12:40", 4000.0) == [3723.0, 760.0]
    assert prompts.times_in("nothing timed", 900.0) == []
    assert prompts.clock_seconds("21:56:19") == 21 * 3600 + 56 * 60 + 19
    assert (
        prompts.clock_seconds("9:05") is None
        and prompts.clock_seconds("25:00:00") is None
    )
    line = prompts.stamp_line(
        {
            "date": "06/07/2025",
            "time": "21:56:19",
            "camera": "BWC2-098679",
            "at": 2.0,
            "checked": True,
        }
    )
    assert "06/07/2025, 21:56:19 at [00:00:02]" in line and "camera BWC2-098679" in line
    assert (
        "[00:00:00] of the recording was 21:56:17" in line
        and "without reordering" in line
    )
    assert "not checked" not in line
    assert "not checked" in prompts.stamp_line({"time": "21:56:19", "at": 2.0})
    assert prompts.stamp_line({}) == "" and prompts.stamp_line(None) == ""
    assert (
        prompts.stamp_row({"camera": "BWC2-098679"})
        == "camera BWC2-098679 (read from one frame)"
    )


def test_a_clips_cost_is_estimated_by_its_frames_and_its_height():
    # Twenty frames of 640 by 360, paired: ten times 23 by 13 patches.
    assert prompts.video_tokens(20, 360) == 10 * 23 * 13
    assert prompts.video_tokens(0, 360) == 0
    assert prompts.video_tokens(6, 180) < prompts.video_tokens(6, 720)
    assert prompts.fits("a" * 400, answer_cap=100, window=4000)
    assert not prompts.fits("a" * 400, answer_cap=100, window=4000, extra=3900)


def test_the_cut_hands_ffmpeg_a_fraction_of_a_frame_a_second(monkeypatch, tmp_path):
    """Sixteen frames over twenty seconds is 0.8 a second. Rounded to a whole
    number it was zero, and a zero frame rate cut nothing for ever (v1.52.1)."""
    ran = []

    class Finished:
        returncode = 0

    def run(arguments, timeout):
        ran.append(arguments)
        Path(arguments[-1]).write_bytes(b"\x00\x00\x00\x18ftypmp42")
        return Finished()

    monkeypatch.setattr(media, "_run", run)
    source, clip = tmp_path / "playback.mp4", tmp_path / "clip.mp4"
    media.cut_for_description(source, clip, 59.52, 79.37, fps=0.806, height=360)
    assert ran[0][ran[0].index("-vf") + 1] == "fps=0.806,scale=-2:'min(360,ih)'"
    media.cut_for_description(source, clip, 0.0, 8.0, fps=2, height=360)
    assert ran[1][ran[1].index("-vf") + 1] == "fps=2,scale=-2:'min(360,ih)'"


def test_the_words_in_the_span_are_told_with_the_span():
    lines = [
        a_line(1, 0.0, "Speaker 1", "This is Detective Ruiz."),
        a_line(2, 12.4, "Speaker 2", "Thanks, Maria."),
        a_line(3, 724.0, "Speaker 1", "Tell me about the car."),
    ]
    inside = prompts.lines_in_span(lines, 7.4, 17.4)
    assert [one.number for one in inside] == [2]
    said = prompts.moment_input(inside, 7.4, 17.4)
    assert said.startswith("This clip runs from [00:00:07] to [00:00:17]")
    assert "[2] [00:00:12] Speaker 2: Thanks, Maria." in said
    # Nothing inside: the neighbours either side, so the model has its bearings.
    assert [one.number for one in prompts.lines_in_span(lines, 100.0, 110.0)] == [2, 3]
    assert "No words were transcribed" in prompts.moment_input([], 100.0, 110.0)


def test_camera_lines_are_labelled_and_cite_the_moment():
    class Seen:
        def __init__(self, at, text):
            self.at, self.text = at, text

    block = prompts.camera_lines([Seen(12.4, "A hand holds a small bag.")])
    assert block.startswith(prompts.CAMERA_HEADING)
    assert "[00:00:12] [camera] A hand holds a small bag." in block
    assert prompts.camera_lines([]) == ""
    lines = [a_line(1, 0.0, "Speaker 1", "This is Detective Ruiz.")]
    cited = prompts.citations("At [00:00:12] a bag.", lines, [Seen(12.4, "x")])
    assert cited == {"[00:00:12]": 12.4}
    assert prompts.citations("At [00:00:12] a bag.", lines) == {}


def test_the_moment_template_and_its_settings_start_as_the_chapter_says():
    assert PromptTemplate.DEFAULTS[PromptTemplate.MOMENT][1] == prompts.MOMENT
    assert "not visible" in prompts.MOMENT and "never by name" in prompts.MOMENT
    for key, default in (
        ("moments_available", False),
        ("moments_in_answers", True),
        ("moments_answer_tokens", 250),
        ("moments_time_seconds", 120),
        ("moment_span_seconds", 10),
        ("moment_frames_per_second", 2),
        ("moment_frame_height", 360),
    ):
        known = settings_store.DEFINITIONS[key]
        assert known.default == default and known.page == settings_store.ASSISTANT
    text = CATALOGUE.read_text(encoding="utf-8")
    for name in (
        "Moments",
        "Moments in answers",
        "Moment answer cap",
        "Moment time limit",
        "Moment clip length",
        "Moment frames a second",
        "Moment frame height",
    ):
        assert f"| {name} |" in text, f"the catalogue has no row for {name}"


def test_the_engine_request_carries_a_priority_and_the_extra_fields(monkeypatch):
    sent = {}

    class Completions:
        def create(self, **request):
            sent.update(request)

            class Choice:
                finish_reason = "stop"

                class message:
                    content = "ready"

            class Usage:
                prompt_tokens, completion_tokens = 3, 1

            class Answer:
                choices = [Choice()]
                usage = Usage()
                model = "the-model"

            return Answer()

    class Client:
        class chat:
            completions = Completions()

    monkeypatch.setattr(engine, "client", lambda timeout: Client())
    monkeypatch.setattr(engine, "model_name", lambda: "the-model")
    engine.complete(
        [{"role": "user", "content": "hi"}],
        max_completion_tokens=8,
        temperature=0,
        top_p=1,
        thinking=False,
        timeout=5,
        extra={"mm_processor_kwargs": {"fps": 1.0}},
    )
    assert sent["extra_body"]["priority"] == engine.PRIORITY == 1
    assert sent["extra_body"]["chat_template_kwargs"] == {"enable_thinking": False}
    assert sent["extra_body"]["mm_processor_kwargs"] == {"fps": 1.0}


# With a database ----------------------------------------------------------------------


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("asker", PASSWORD)


def a_recording(person, tmp_path, settings, video=True):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        title="Stop",
        original_filename="bodycam.mp4" if video else "call.m4a",
        media_state=MediaState.READY,
        duration_seconds=900.0,
        diarize=True,
        playback_ready=True,
    )
    recording.folder.mkdir(parents=True, exist_ok=True)
    (recording.folder / ("playback.mp4" if video else "playback.m4a")).write_bytes(
        b"not really media"
    )
    transcript = Transcript.objects.create(recording=recording, language="en")
    for start, speaker, text in (
        (0.0, "Speaker 1", "This is Officer Ruiz."),
        (12.4, "Speaker 2", "Look at that, right there."),
        (724.0, "Speaker 1", "Tell me about the car."),
    ):
        Segment.objects.create(
            transcript=transcript,
            start=start,
            end=start + 5,
            text=text,
            speaker=speaker,
            speaker_label=speaker.upper().replace(" ", "_"),
        )
    settings_store.set_to("assistant_available", True)
    settings_store.set_to("moments_available", True)
    return recording


@pytest.fixture
def ready(person, tmp_path, settings):
    return a_recording(person, tmp_path, settings)


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def reachable(monkeypatch, answer_text, finish="stop"):
    monkeypatch.setattr(engine, "is_reachable", lambda: True)
    monkeypatch.setattr(engine, "address", lambda: "http://gideon-generator:8000/v1")
    asked = []

    def complete(messages, **options):
        asked.append({"messages": messages, **options})
        return {
            "text": answer_text,
            "finish_reason": finish,
            "input_tokens": 3000,
            "output_tokens": 80,
            "model": "the-model",
        }

    monkeypatch.setattr(engine, "complete", complete)
    return asked


def a_cut(monkeypatch):
    """A cut that writes a few bytes where ffmpeg would, and remembers the call."""
    cuts = []

    def cut(source, target, start, end, *, fps, height, timeout=120):
        cuts.append(
            {"source": source, "start": start, "end": end, "fps": fps, "height": height}
        )
        Path(target).write_bytes(b"\x00\x00\x00\x18ftypmp42")

    monkeypatch.setattr(media, "cut_for_description", cut)
    return cuts


def swallow_defer(monkeypatch):
    from core import tasks

    monkeypatch.setattr(tasks.describe_moment, "defer", lambda **fields: None)


def segment_at(recording, start):
    return recording.transcript.segments.get(start=start)


def no_scan_no_stamp(monkeypatch):
    """The record without ffmpeg: no change points found, and the stamp off."""
    from core import moment_scan

    monkeypatch.setattr(moment_scan, "scene_changes", lambda *a, **k: [])
    monkeypatch.setattr(moment_scan, "loud_seconds", lambda *a, **k: [])
    settings_store.set_to("stamp_available", False)


@pytest.mark.django_db
def test_a_moment_is_described_from_the_clip_and_the_words(
    ready, person, client, monkeypatch, tmp_path
):
    asked = reachable(monkeypatch, "A hand holds a small bag (at 4 s).")
    cuts = a_cut(monkeypatch)
    swallow_defer(monkeypatch)
    signed_in(client, person)
    segment = segment_at(ready, 12.4)
    # Nobody presses anything on the page since v1.52.0; a Moment asked for
    # by a person is made the same way the record makes one.
    moment = Moment.objects.create(
        transcript=ready.transcript, segment=segment, at=12.4, asked_by=person
    )
    assert moment.state == assistant.QUEUED and moment.segment == segment
    assert client.post(f"/recording/{ready.pk}/moments").status_code == 404

    assistant.describe_moment(moment.pk)
    moment.refresh_from_db()
    assert moment.state == assistant.DONE
    assert moment.text == "A hand holds a small bag (at 4 s)."
    assert (moment.span_start, moment.span_end) == (7.4, 17.4)
    assert moment.frames == 20 and moment.model == "the-model"
    assert cuts == [
        {
            "source": ready.playback_path(),
            "start": 7.4,
            "end": 17.4,
            "fps": 2,
            "height": 360,
        }
    ]
    # The temporary clip is gone.
    import tempfile

    assert not list(Path(tempfile.gettempdir()).glob("moment-*.mp4"))

    call = asked[0]
    system, user = call["messages"]
    assert system["content"].startswith(prompts.GROUND_RULES)
    assert (
        prompts.MOMENT in system["content"]
        and prompts.MOMENT_FORMAT in system["content"]
    )
    text_part, video_part = user["content"]
    assert text_part["type"] == "text"
    assert "The words spoken in this clip were:" in text_part["text"]
    assert "[2] [00:00:12] Speaker 2: Look at that, right there." in text_part["text"]
    assert video_part["type"] == "video_url"
    assert video_part["video_url"]["url"].startswith("data:video/mp4;base64,AAAAGGZ0")
    assert call["thinking"] is False and call["timeout"] == 120
    assert call["max_completion_tokens"] == 250

    row = Row.objects.filter(category="llm").latest("at")
    assert row.event == "AI assistant call" and row.details["feature"] == "moment"
    assert row.details["templates"] == "ground-rules v1; Moment v1"
    assert row.details["source"] == "asked" and row.details["output_tokens"] == 80
    details = json.dumps(row.details)
    assert "bag" not in details and "Look at" not in details

    state = client.get(f"/recording/{ready.pk}/assistant").json()
    assert state["moments"] is not None and state["video"] is True
    (listed,) = state["moments"]
    assert listed["clock"] == "00:00:12" and listed["text"] == moment.text
    assert listed["state"] == "done" and listed["notice"]
    assert "cues" not in state


@pytest.mark.django_db
def test_a_moment_never_thinks_even_when_the_office_lets_the_model_think(
    ready, person, monkeypatch
):
    asked = reachable(monkeypatch, "A doorway.")
    a_cut(monkeypatch)
    settings_store.set_to("assistant_thinks", True)
    settings_store.set_to("moment_span_seconds", 20)
    settings_store.set_to("moment_frames_per_second", 1)
    settings_store.set_to("moment_frame_height", 720)
    moment = Moment.objects.create(transcript=ready.transcript, at=5.0, asked_by=person)
    assistant.describe_moment(moment.pk)
    moment.refresh_from_db()
    assert moment.state == assistant.DONE
    assert asked[0]["thinking"] is False and asked[0]["max_completion_tokens"] == 250
    # The span is clamped to the start of the file: 0 to 15, at one frame a second.
    assert (moment.span_start, moment.span_end) == (0.0, 15.0) and moment.frames == 15


@pytest.mark.django_db
def test_the_state_and_a_moment_being_described_keeps_the_page_busy(
    ready, person, client, monkeypatch
):
    swallow_defer(monkeypatch)
    signed_in(client, person)
    state = client.get(f"/recording/{ready.pk}/assistant").json()
    assert state["moments"] == [] and state["busy"] is False
    assert state["cue_runs"]["record"] is True and "finders" not in state["cue_runs"]
    assert state["cue_runs"]["digest"] == {
        "parts": 0,
        "made": "",
        "moments": 0,
        "current": False,
    }
    assert state["cue_runs"]["prepare"]["state"] == "none"
    assert "describe_first_default" not in state["cue_runs"]
    Moment.objects.create(transcript=ready.transcript, at=12.4, asked_by=person)
    state = client.get(f"/recording/{ready.pk}/assistant").json()
    assert state["busy"] is True
    # The routes of the presses are gone.
    for gone in ("find-moments", "moments", "describe-intervals"):
        assert client.post(f"/recording/{ready.pk}/{gone}").status_code == 404


@pytest.mark.django_db
def test_the_scan_keeps_the_change_points_on_the_transcript(ready, person, monkeypatch):
    from core import moment_scan

    monkeypatch.setattr(
        moment_scan,
        "scene_changes",
        lambda source, threshold, timeout=0: [5.0, 6.0, 300.0],
    )
    monkeypatch.setattr(
        moment_scan, "loud_seconds", lambda source, rise, timeout=0: [301.0, 730.0]
    )
    assert ready.transcript.change_points is None
    points = moment_scan.change_points_of(ready.transcript, actor=person)
    # Thinned to the gap (3 s shipped): 5 and 6 are one, 300 and 301 are one.
    assert points == [5.0, 300.0, 730.0]
    ready.transcript.refresh_from_db()
    assert ready.transcript.change_points == [5.0, 300.0, 730.0]
    row = Row.objects.get(event="Picture and sound scanned")
    assert row.details["found"] == 3 and row.details["picture_changes"] == 2
    assert row.details["loud_seconds"] == 2

    # A scan that fails raises, writes its row, and leaves the points unset.
    def broken(source, threshold, timeout=0):
        raise media.MediaError("no", "media_failed")

    monkeypatch.setattr(moment_scan, "scene_changes", broken)
    ready.transcript.change_points = None
    ready.transcript.save(update_fields=["change_points"])
    with pytest.raises(media.MediaError):
        moment_scan.change_points_of(ready.transcript, actor=person)
    assert Row.objects.filter(event="Picture and sound scanned").count() == 2


@pytest.mark.django_db
def test_an_engine_without_vision_says_so_and_a_cut_that_fails_is_media_failed(
    ready, person, monkeypatch
):
    monkeypatch.setattr(engine, "is_reachable", lambda: True)
    monkeypatch.setattr(engine, "address", lambda: "http://gideon-generator:8000/v1")
    a_cut(monkeypatch)

    def refuses(messages, **options):
        raise engine.Problem(engine.NO_VISION, "does not support video input")

    monkeypatch.setattr(engine, "complete", refuses)
    moment = Moment.objects.create(
        transcript=ready.transcript, at=12.4, asked_by=person
    )
    assistant.describe_moment(moment.pk)
    moment.refresh_from_db()
    assert moment.state == assistant.FAILED and moment.reason_class == "llm_no_vision"
    assert (
        assistant.what_to_say(moment.reason_class)
        == "This engine cannot look at video."
    )
    row = Row.objects.filter(category="llm").latest("at")
    assert (
        row.details["reason_class"] == "llm_no_vision"
        if "reason_class" in row.details
        else True
    )
    assert row.outcome == "failure"

    def broken(source, target, start, end, *, fps, height, timeout=120):
        raise media.MediaError("ffmpeg said no", "media_failed")

    monkeypatch.setattr(media, "cut_for_description", broken)
    moment = Moment.objects.create(
        transcript=ready.transcript, at=12.4, asked_by=person
    )
    assistant.describe_moment(moment.pk)
    moment.refresh_from_db()
    assert moment.state == assistant.FAILED and moment.reason_class == "media_failed"
    assert "could not be cut" in assistant.what_to_say("media_failed")


@pytest.mark.django_db
def test_a_moment_waits_for_the_playback_copy_and_never_for_sound_alone(
    person, client, tmp_path, settings, monkeypatch
):
    swallow_defer(monkeypatch)
    signed_in(client, person)
    recording = a_recording(person, tmp_path, settings)
    recording.playback_ready = False
    recording.save(update_fields=["playback_ready"])
    # A Moment queued before the copy lands fails and says so.
    moment = Moment.objects.create(
        transcript=recording.transcript, at=12.4, asked_by=person
    )
    monkeypatch.setattr(engine, "is_reachable", lambda: True)
    monkeypatch.setattr(engine, "address", lambda: "http://gideon-generator:8000/v1")
    assistant.describe_moment(moment.pk)
    moment.refresh_from_db()
    assert moment.state == assistant.FAILED and moment.reason_class == "media_not_ready"
    assert "still being prepared" in assistant.what_to_say("media_not_ready")

    audio = a_recording(person, tmp_path / "two", settings, video=False)
    page = client.get(f"/recording/{audio.pk}").content.decode()
    assert 'data-panel="moments"' not in page
    assert (
        client.get(f"/recording/{audio.pk}/assistant").json()["cue_runs"]["prepare"]
        is None
    )


@pytest.mark.django_db
def test_nothing_about_moments_is_on_the_page_and_moments_start_off(
    ready, person, client, monkeypatch
):
    swallow_defer(monkeypatch)
    signed_in(client, person)
    page = client.get(f"/recording/{ready.pk}").content.decode()
    # v1.52.0: no Moments tab, no button on the stage, no tick in the summary
    # dialog; the dialog has one line that says what preparing does.
    assert "moments: true" in page
    assert 'data-panel="moments"' not in page
    assert 'id="summary-prepare-note"' in page
    for gone in (
        "describe-now",
        "describe-intervals",
        "moment-list",
        "cue-list",
        "camera-row",
        "summary-describe-first",
        "Look at the picture first",
        "Describe this moment",
    ):
        assert gone not in page, gone
    assert "Summarise this video" in page
    settings_store.set_to("moments_available", False)
    assert assistant.features()["moments"] is False
    page = client.get(f"/recording/{ready.pk}").content.decode()
    assert 'id="summary-prepare-note"' not in page and "New summary" in page
    state = client.get(f"/recording/{ready.pk}/assistant").json()
    assert state["moments"] == [] and "cues" not in state
    assert settings_store.DEFINITIONS["moments_available"].default is False


@pytest.mark.django_db
def test_summary_and_chat_carry_the_camera_block_only_while_the_office_says_so(
    ready, person, monkeypatch
):
    asked = reachable(monkeypatch, "Summary: at [00:00:12] a bag is shown.")
    # Without a Digest the block is sent as before (test_digest has the rest),
    # and without the record nothing is prepared first.
    settings_store.set_to("digests_available", False)
    settings_store.set_to("picture_record_available", False)
    Moment.objects.create(
        transcript=ready.transcript,
        at=12.4,
        state=assistant.DONE,
        text="A hand holds a small bag.",
        model="the-model",
    )
    Moment.objects.create(transcript=ready.transcript, at=30.0, state=assistant.FAILED)
    summary = Summary.objects.create(
        recording=ready,
        asked_by=person,
        template_name="Standard summary",
        length="short",
    )
    assistant.write_summary(summary.pk)
    summary.refresh_from_db()
    user = asked[0]["messages"][-1]["content"]
    assert prompts.CAMERA_HEADING in user
    assert "[00:00:12] [camera] A hand holds a small bag." in user
    assert user.count("[camera]") == 1
    # The camera line's time is a citation the viewer can follow.
    assert summary.citations == {"[00:00:12]": 12.4}

    settings_store.set_to("moments_in_answers", False)
    summary.state = assistant.QUEUED
    summary.save()
    assistant.write_summary(summary.pk)
    assert prompts.CAMERA_HEADING not in asked[1]["messages"][-1]["content"]

    settings_store.set_to("moments_in_answers", True)
    settings_store.set_to("moments_available", False)
    summary.state = assistant.QUEUED
    summary.save()
    assistant.write_summary(summary.pk)
    assert prompts.CAMERA_HEADING not in asked[2]["messages"][-1]["content"]


@pytest.mark.django_db
def test_the_exports_carry_the_camera_lines_in_their_own_section(ready, person):
    Moment.objects.create(
        transcript=ready.transcript,
        at=12.4,
        state=assistant.DONE,
        text="A hand holds a small bag.",
        model="the-model",
        edited=True,
    )
    Moment.objects.create(
        transcript=ready.transcript,
        at=600.0,
        span_start=600.0,
        span_end=615.0,
        source=Moment.INTERVAL,
        state=assistant.DONE,
        text="The car door is open.",
        model="the-model",
    )
    text = exports.plain_text(ready)
    lines = text.split("\r\n")
    # Nothing about the camera among the lines (v1.51.0): the talk, then a
    # section of its own with the legend, a span on a record's line.
    spoken = [line for line in lines if line.startswith("[00:00:12] Speaker")]
    assert spoken[0].startswith("[00:00:12] Speaker 2:")
    assert "Camera (a model" not in text
    heading = lines.index(exports.CAMERA_HEADING)
    assert heading > lines.index(
        [one for one in lines if one.startswith("[00:12:04]")][0]
    )
    assert lines[heading + 1] == exports.CAMERA_LEGEND
    assert lines[heading + 2] == "[00:00:12] A hand holds a small bag."
    assert lines[heading + 3] == "[00:10:00]-[00:10:15] The car door is open."
    assert exports.camera_moments_row(ready.transcript) == (
        "2 described by the-model, 1 edited by staff"
    )

    word = exports.word(ready, "asker")
    assert word[:2] == b"PK"
    import io
    import zipfile

    document = zipfile.ZipFile(io.BytesIO(word)).read("word/document.xml").decode()
    assert (
        "What the camera showed" in document and "A hand holds a small bag." in document
    )
    assert "Camera moments" in document and exports.CAMERA_LEGEND[:30] in document
    assert "Camera: " not in document


@pytest.mark.django_db
def test_a_moment_goes_with_its_transcript(ready, person):
    Moment.objects.create(transcript=ready.transcript, at=12.4, asked_by=person)
    ready.transcript.delete()
    assert Moment.objects.count() == 0


@pytest.mark.django_db
def test_the_details_panel_counts_the_moments(ready, person, client):
    signed_in(client, person)
    Moment.objects.create(
        transcript=ready.transcript,
        at=12.4,
        state=assistant.DONE,
        text="A doorway.",
        model="the-model",
    )
    rows = dict(client.get(f"/recording/{ready.pk}/details").json()["rows"])
    assert rows["Camera moments"] == "1 described by the-model"
    assert "doorway" not in json.dumps(rows)


# Questions, styles, and clips (v1.39.0) ----------------------------------------------


def test_question_frames_are_spread_a_second_either_side():
    assert assistant.question_times(12.4, 3, 900.0) == [11.4, 12.4, 13.4]
    assert assistant.question_times(12.4, 1, 900.0) == [12.4]
    assert assistant.question_times(0.2, 3, 900.0) == [0.0, 0.2, 1.2]
    assert assistant.question_times(899.5, 3, 900.0) == [898.5, 899.5, 900.0]
    assert prompts.still_tokens(3, 720) == 3 * 26 * 46
    said = prompts.question_input([], 12.4, 7.4, 17.4, "  is that a gun?  ")
    assert said.startswith("The frames are from [00:00:12]")
    assert said.endswith("The question: is that a gun?")


@pytest.mark.django_db
def test_a_question_is_answered_from_close_frames(ready, person, client, monkeypatch):
    asked = reachable(
        monkeypatch,
        "Visible: a dark, flat object on the seat. Consistent with: a phone or a "
        "handgun. Cannot be told: which, the frame is too small.",
    )
    grabbed = []

    def grab(source, folder, times, *, height, timeout=120):
        grabbed.append({"times": times, "height": height})
        written = []
        for n, _ in enumerate(times, start=1):
            frame = Path(folder) / f"frame-{n}.jpg"
            frame.write_bytes(b"\xff\xd8\xff\xe0JFIF")
            written.append(frame)
        return written

    monkeypatch.setattr(media, "grab_frames", grab)
    swallow_defer(monkeypatch)
    signed_in(client, person)
    moment = Moment.objects.create(
        transcript=ready.transcript,
        at=12.4,
        question="Is that a gun on the seat?",
        asked_by=person,
    )
    assert moment.is_question

    assistant.describe_moment(moment.pk)
    moment.refresh_from_db()
    assert moment.state == assistant.DONE and moment.frames == 3
    assert moment.text.startswith("Visible:")
    assert grabbed == [{"times": [11.4, 12.4, 13.4], "height": 720}]
    system, user = asked[0]["messages"]
    assert prompts.QUESTION in system["content"]
    assert prompts.QUESTION_FORMAT in system["content"]
    parts = user["content"]
    assert parts[0]["type"] == "text"
    assert "The question: Is that a gun" in parts[0]["text"]
    assert [one["type"] for one in parts[1:]] == ["image_url"] * 3
    assert parts[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert asked[0]["thinking"] is False
    import tempfile

    assert not list(Path(tempfile.gettempdir()).glob("moment-*"))
    row = Row.objects.filter(category="llm").latest("at")
    assert row.details["kind"] == "question" and "gun" not in json.dumps(row.details)
    state = client.get(f"/recording/{ready.pk}/assistant").json()
    assert state["moments"][0]["question"] == "Is that a gun on the seat?"
    # The camera line carries the question in front of the answer.
    text = exports.plain_text(ready)
    assert '(asked "Is that a gun on the seat?") Visible:' in text


@pytest.mark.django_db
def test_the_style_setting_chooses_the_answer_shape(ready, person, monkeypatch):
    asked = reachable(monkeypatch, "A doorway.")
    a_cut(monkeypatch)
    moment = Moment.objects.create(transcript=ready.transcript, at=5.0, asked_by=person)
    assistant.describe_moment(moment.pk)
    assert prompts.MOMENT_FORMAT_BRIEF in asked[0]["messages"][0]["content"]
    settings_store.set_to("moment_style", "full")
    moment = Moment.objects.create(transcript=ready.transcript, at=5.0, asked_by=person)
    assistant.describe_moment(moment.pk)
    assert prompts.MOMENT_FORMAT_FULL in asked[1]["messages"][0]["content"]
    with pytest.raises(ValueError):
        settings_store.set_to("moment_style", "verbose")


@pytest.mark.django_db
def test_a_clip_carries_the_camera_line_as_a_caption(ready, person):
    from core import clip_work
    from core.clips import Clip

    Moment.objects.create(
        transcript=ready.transcript,
        at=12.4,
        state=assistant.DONE,
        text="A hand holds a small bag.",
        model="the-model",
    )
    Moment.objects.create(
        transcript=ready.transcript,
        at=300.0,
        state=assistant.DONE,
        text="Outside the span.",
        model="the-model",
    )
    clip = Clip.objects.create(
        recording=ready, user=person, title="The bag", start=10.0, end=20.0
    )
    captions = clip_work.srt_for(clip)
    cues = captions.split("\r\n\r\n")
    assert any("Camera: A hand holds a small bag." in cue for cue in cues)
    assert not any("Outside the span" in cue for cue in cues)
    camera = [cue for cue in cues if "Camera:" in cue][0]
    assert "00:00:02,400 --> 00:00:06,400" in camera
    # The spoken cue at 12.4 is there too, after the camera cue's number.
    assert any("Speaker 2: Look at that, right there." in cue for cue in cues)


# Intervals and the summary (v1.41.0) -------------------------------------------------


@pytest.mark.django_db
def test_the_whole_recording_is_described_at_intervals_in_one_lane(
    ready, person, client, monkeypatch
):
    from core.assistant import CueRun

    asked = reachable(monkeypatch, "A doorway.")
    a_cut(monkeypatch)
    no_scan_no_stamp(monkeypatch)
    settings_store.set_to("moment_interval_seconds", 300)
    # A span already described is never described twice.
    Moment.objects.create(
        transcript=ready.transcript,
        at=300.0,
        span_start=300.0,
        span_end=600.0,
        source=Moment.INTERVAL,
        state=assistant.DONE,
        text="Already here.",
        model="the-model",
    )
    signed_in(client, person)
    run = CueRun.objects.create(
        transcript=ready.transcript, source=CueRun.INTERVAL, asked_by=person
    )

    assistant.describe_intervals(run.pk)
    run.refresh_from_db()
    # 900 s cut at 300 s with no change points: 0-300, 300-600, 600-900, and
    # the middle one is described already.
    assert run.state == assistant.DONE and (run.found, run.total) == (2, 2)
    made = list(
        Moment.objects.filter(source=Moment.INTERVAL).exclude(text="Already here.")
    )
    assert [(one.at, one.span_start, one.span_end) for one in made] == [
        (0.0, 0.0, 300.0),
        (600.0, 600.0, 900.0),
    ]
    assert all(one.state == assistant.DONE and one.text == "A doorway." for one in made)
    assert len(asked) == 2
    # The span is the clip, thinned to the frames allowed, and the second
    # span is told what the one before it showed and asked for what is new.
    first, second = asked
    assert first["messages"][-1]["content"][0]["text"].count("The clip before") == 0
    assert (
        "The clip before this one showed: Already here."
        in second["messages"][-1]["content"][0]["text"]
    )
    assert prompts.RECORD_NEW in second["messages"][0]["content"]
    assert made[0].frames == 16
    state = client.get(f"/recording/{ready.pk}/assistant").json()
    assert state["cue_runs"]["interval"] == {
        "state": "done",
        "found": 2,
        "total": 2,
        "said": "",
    }
    assert state["moments"][0]["source"] == "interval"


@pytest.mark.django_db
def test_the_intervals_stop_when_the_engine_goes_away(ready, person, monkeypatch):
    from core.assistant import CueRun

    a_cut(monkeypatch)
    no_scan_no_stamp(monkeypatch)
    monkeypatch.setattr(engine, "address", lambda: "http://gideon-generator:8000/v1")
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        return calls["n"] <= 1

    monkeypatch.setattr(engine, "is_reachable", flaky)
    monkeypatch.setattr(
        engine,
        "complete",
        lambda messages, **options: {
            "text": "A doorway.",
            "finish_reason": "stop",
            "input_tokens": 1,
            "output_tokens": 1,
            "model": "the-model",
        },
    )
    settings_store.set_to("moment_interval_seconds", 300)
    run = CueRun.objects.create(
        transcript=ready.transcript, source=CueRun.INTERVAL, asked_by=person
    )
    assistant.describe_intervals(run.pk)
    run.refresh_from_db()
    assert run.state == assistant.FAILED and run.reason_class == "llm_unreachable"
    assert (run.found, run.total) == (1, 3)
    states = [one.state for one in Moment.objects.order_by("at")]
    assert states == [assistant.DONE, assistant.FAILED, assistant.FAILED]


@pytest.mark.django_db
def test_the_state_counts_what_describing_the_whole_recording_would_make(
    ready, person, client, monkeypatch
):
    swallow_defer(monkeypatch)
    signed_in(client, person)
    # 900 s at the shipped 15 s ceiling, the picture not yet scanned: sixty
    # spans by the clock alone, an estimate.
    state = client.get(f"/recording/{ready.pk}/assistant").json()
    assert state["cue_runs"]["intervals"] == {
        "every": 15.0,
        "count": 60,
        "estimated": True,
        "minutes": 20,
    }
    settings_store.set_to("moment_interval_seconds", 300)
    # A span described already is left out; a failed one is not; one waiting
    # its turn is, as describe_intervals counts them.
    done = Moment.objects.create(
        transcript=ready.transcript,
        at=300.0,
        span_start=300.0,
        span_end=600.0,
        source=Moment.INTERVAL,
        state=assistant.DONE,
        text="Already here.",
        model="the-model",
    )
    assert (
        client.get(f"/recording/{ready.pk}/assistant").json()["cue_runs"]["intervals"][
            "count"
        ]
        == 2
    )
    done.state = assistant.FAILED
    done.save(update_fields=["state"])
    assert (
        client.get(f"/recording/{ready.pk}/assistant").json()["cue_runs"]["intervals"][
            "count"
        ]
        == 3
    )
    Moment.objects.create(
        transcript=ready.transcript,
        at=0.0,
        span_start=0.0,
        span_end=300.0,
        source=Moment.INTERVAL,
        asked_by=person,
    )
    assert (
        client.get(f"/recording/{ready.pk}/assistant").json()["cue_runs"]["intervals"][
            "count"
        ]
        == 2
    )
    # Once the picture is scanned the cut is at its change points, and no
    # longer an estimate.
    ready.transcript.change_points = [100.0, 450.0]
    ready.transcript.save(update_fields=["change_points"])
    Moment.objects.all().delete()
    state = client.get(f"/recording/{ready.pk}/assistant").json()
    assert state["cue_runs"]["intervals"] == {
        "every": 300.0,
        "count": 5,
        "estimated": False,
        "minutes": 2,
    }
    # The record off: nothing to describe, and nothing to prepare.
    settings_store.set_to("picture_record_available", False)
    state = client.get(f"/recording/{ready.pk}/assistant").json()
    assert state["cue_runs"]["intervals"]["count"] == 0
    assert state["cue_runs"]["record"] is False
    assert state["cue_runs"]["prepare"] is None
    # Nothing while Moments are off: the runs dict is empty.
    settings_store.set_to("moments_available", False)
    assert client.get(f"/recording/{ready.pk}/assistant").json()["cue_runs"] == {}


@pytest.mark.django_db
def test_a_summary_prepares_the_video_first_and_writes_one_account(
    ready, person, client, monkeypatch
):
    from core import tasks

    answers = iter(
        [
            "A doorway.",
            "A car.",
            "A bag.",
            "1. [00:00:00]-[00:15:00] (both) A doorway, a car, a bag.",
            "Executive summary: a stop, a bag at [00:10:00].",
            "Executive summary: again.",
        ]
    )
    monkeypatch.setattr(engine, "is_reachable", lambda: True)
    monkeypatch.setattr(engine, "address", lambda: "http://gideon-generator:8000/v1")
    asked = []

    def complete(messages, **options):
        asked.append({"messages": messages, **options})
        return {
            "text": next(answers),
            "finish_reason": "stop",
            "input_tokens": 1,
            "output_tokens": 1,
            "model": "the-model",
        }

    monkeypatch.setattr(engine, "complete", complete)
    a_cut(monkeypatch)
    no_scan_no_stamp(monkeypatch)
    monkeypatch.setattr(tasks.write_summary, "defer", lambda **fields: None)
    settings_store.set_to("moment_interval_seconds", 300)
    signed_in(client, person)
    state = client.get(f"/recording/{ready.pk}/assistant").json()
    assert state["cue_runs"]["prepare"]["state"] == "none"
    assert state["cue_runs"]["prepare"]["line"] == "Not prepared"
    assert state["cue_runs"]["prepare"]["seconds_left"] > 0

    answer = client.post(
        f"/recording/{ready.pk}/summaries",
        data=json.dumps({"length": "short"}),
        content_type="application/json",
    )
    assert answer.status_code == 200
    summary = Summary.objects.get(pk=answer.json()["id"])
    assistant.write_summary(summary.pk)
    summary.refresh_from_db()
    assert summary.state == assistant.DONE, summary.reason_class
    # Prepared first: three spans of the record, the Digest's one part, and
    # then the summary, one account under the narrative rules.
    transcript = ready.transcript
    transcript.refresh_from_db()
    assert transcript.prepare_state == assistant.DONE and transcript.prepared_at
    assert transcript.prepare_total == 4 and transcript.prepare_done == 4
    assert (
        Moment.objects.filter(source=Moment.INTERVAL, state=assistant.DONE).count() == 3
    )
    assert len(asked) == 5
    digest_call = asked[3]
    assert prompts.DIGEST in digest_call["messages"][0]["content"]
    assert "Window 1 of 1" in digest_call["messages"][-1]["content"]
    assert (
        "[00:10:00]-[00:15:00] [camera] A bag."
        in digest_call["messages"][-1]["content"]
    )
    system = asked[4]["messages"][0]["content"]
    user = asked[4]["messages"][-1]["content"]
    assert prompts.RECORD_HEADING in user and "(both) A doorway, a car, a bag." in user
    assert prompts.CAMERA_HEADING not in user
    assert "Write one account from it" in user
    assert system.endswith(prompts.NARRATIVE_RULES)
    assert prompts.CAMERA_RULES not in system
    assert "Executive summary" in prompts.SHIPPED_SUMMARIES["video"]
    assert "Seen but not said" not in prompts.SHIPPED_SUMMARIES["video"]
    assert "Seen but not said" not in prompts.SHIPPED_SUMMARIES["body_camera"]
    assert summary.citations == {"[00:10:00]": 600.0}
    assert summary.moments_used == 3 and summary.digest_parts == 1
    assert summary.stage == ""
    row = Row.objects.get(event="Video prepared")
    assert row.details["descriptions"] == 3 and row.details["parts"] == 1
    assert "doorway" not in json.dumps(row.details)
    assert Moment.objects.filter(source=Moment.INTERVAL).first().seconds >= 0

    # Prepared already: the next summary is one call.
    again = Summary.objects.create(
        recording=ready, asked_by=person, template_name="Video summary", length="short"
    )
    assistant.write_summary(again.pk)
    assert len(asked) == 6
    state = client.get(f"/recording/{ready.pk}/assistant").json()
    assert state["cue_runs"]["prepare"]["state"] == "done"
    assert state["cue_runs"]["prepare"]["line"] == "Prepared"

    word = exports.summary_word(summary, "asker")
    import io
    import zipfile

    document = zipfile.ZipFile(io.BytesIO(word)).read("word/document.xml").decode()
    assert "What the camera showed" in document and "A bag." in document
    assert exports.CAMERA_LEGEND[:30] in document


def test_the_record_and_digest_settings_start_as_the_chapter_says():
    for key, default in (
        ("picture_record_available", True),
        ("moment_interval_seconds", 15),
        ("picture_shortest_span", 3),
        ("moment_interval_most", 600),
        ("picture_frames_most", 16),
        ("digests_available", True),
        ("digest_window_tokens", 12000),
        ("digest_part_tokens", 1200),
        ("chat_descriptions_near", 6),
        ("stamp_available", True),
        ("moment_media_gap_seconds", 3),
    ):
        assert settings_store.DEFINITIONS[key].default == default, key
    for gone in (
        "moment_finder_transcript",
        "moment_finder_media",
        "moment_finder_most",
        "moment_finder_confidence",
        "moment_finder_tokens",
        "moment_finder_time_seconds",
        "summary_moments_enough",
        "summary_describes_first",
    ):
        assert gone not in settings_store.DEFINITIONS, gone
    assert (
        settings_store.DEFINITIONS["moment_scene_threshold"].needs
        == "moments_available"
    )
    text = CATALOGUE.read_text(encoding="utf-8")
    for name in (
        "Picture record for summaries",
        "Picture record: longest span",
        "Picture record: shortest span",
        "Picture record: most descriptions",
        "Picture record: frames per description",
        "Digests",
        "Digest window",
        "Digest part cap",
        "Chat: descriptions near an asked time",
        "Read the camera's stamp",
        "Gap between change points",
    ):
        assert f"| {name} |" in text, f"the catalogue has no row for {name}"
    for gone in (
        "| Find moments from the words |",
        "| Enough moments for a video summary |",
    ):
        assert gone not in text, gone
