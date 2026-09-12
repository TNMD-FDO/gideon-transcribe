"""Moments (Phase 4): what the camera showed at a time, as a model described it.

The rules checked here: a Cue is a line whose words point at something, found
by pattern and never stored; a Moment is a clip cut from the Playback copy
around the chosen time, shown to the engine with the words spoken in it,
never with thinking, and the clip is gone whatever happens; the engine's
request carries a priority; an engine that takes no video says so; the
endpoints refuse while Moments are off, before the Playback copy exists, and
for sound alone; the state lists Moments and Cues; a Moment's words reach
Summary and Chat as labelled camera lines only while the office says so, and
the exports carry them marked; the audit rows carry no words; and a Moment
goes with its Transcript.
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


def test_the_finders_answer_is_checked_line_by_line():
    lines = [
        a_line(1, 0.0, "Speaker 1", "This is Detective Ruiz."),
        a_line(2, 12.4, "Speaker 2", "Look at that, right there in the console."),
        a_line(3, 30.0, "Speaker 1", "Tell me about the car."),
    ]
    raw = [
        {
            "line": 2,
            "kind": "pointing",
            "reason": "a bag in the console",
            "confidence": "high",
        },
        {"line": 2, "kind": "object", "reason": "again", "confidence": "high"},
        {"line": 3, "kind": "action", "reason": "  too   unsure ", "confidence": "low"},
        {"line": 9, "kind": "object", "reason": "no such line", "confidence": "high"},
        {"line": 1, "kind": "sermon", "reason": "no such kind", "confidence": "high"},
        {"line": 1, "kind": "command", "reason": "", "confidence": "medium"},
        "not a dict",
    ]
    kept = prompts.keep_cues(raw, lines, "medium", 10)
    assert kept == [
        {
            "segment_id": 2,
            "start": 12.4,
            "line": 2,
            "kind": "pointing",
            "reason": "a bag in the console",
            "confidence": "high",
        }
    ]
    # Lower the floor and the unsure one comes in, after the surer, with its
    # spaces tidied; the most allowed cuts the list.
    assert [one["line"] for one in prompts.keep_cues(raw, lines, "low", 10)] == [2, 3]
    assert prompts.keep_cues(raw, lines, "low", 10)[1]["reason"] == "too unsure"
    assert len(prompts.keep_cues(raw, lines, "low", 1)) == 1
    assert prompts.finder_schema(5)["properties"]["cues"]["maxItems"] == 5


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


def test_a_clips_cost_is_estimated_by_its_frames_and_its_height():
    # Twenty frames of 640 by 360, paired: ten times 23 by 13 patches.
    assert prompts.video_tokens(20, 360) == 10 * 23 * 13
    assert prompts.video_tokens(0, 360) == 0
    assert prompts.video_tokens(6, 180) < prompts.video_tokens(6, 720)
    assert prompts.fits("a" * 400, answer_cap=100, window=4000)
    assert not prompts.fits("a" * 400, answer_cap=100, window=4000, extra=3900)


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


@pytest.mark.django_db
def test_a_moment_is_described_from_the_clip_and_the_words(
    ready, person, client, monkeypatch, tmp_path
):
    asked = reachable(monkeypatch, "A hand holds a small bag (at 4 s).")
    cuts = a_cut(monkeypatch)
    swallow_defer(monkeypatch)
    signed_in(client, person)
    segment = segment_at(ready, 12.4)
    answer = client.post(
        f"/recording/{ready.pk}/moments",
        data=json.dumps({"at": 12.4, "segment": str(segment.pk), "source": "asked"}),
        content_type="application/json",
    )
    assert answer.status_code == 200, answer.content
    moment = Moment.objects.get(pk=answer.json()["id"])
    assert moment.state == assistant.QUEUED and moment.segment == segment

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
    # The cue on that line is gone from the suggestions now that it is described.
    assert state["cues"] == []


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
def test_the_state_lists_cues_and_a_moment_being_described_keeps_the_page_busy(
    ready, person, client, monkeypatch
):
    from core.assistant import Cue

    swallow_defer(monkeypatch)
    signed_in(client, person)
    state = client.get(f"/recording/{ready.pk}/assistant").json()
    assert state["moments"] == [] and state["cues"] == [] and state["busy"] is False
    assert state["cue_runs"]["finders"] == {"transcript": True, "media": False}

    segment = segment_at(ready, 12.4)
    cue = Cue.objects.create(
        transcript=ready.transcript,
        segment=segment,
        at=12.4,
        line=2,
        kind="pointing",
        reason="a bag in the console",
        confidence="high",
    )
    state = client.get(f"/recording/{ready.pk}/assistant").json()
    (listed,) = state["cues"]
    assert listed["id"] == str(cue.pk) and listed["reason"] == "a bag in the console"
    assert listed["segment_id"] == str(segment.pk) and listed["clock"] == "00:00:12"

    # Accepting a Cue makes a Moment at its time and line, from the cue.
    answer = client.post(
        f"/recording/{ready.pk}/moments",
        data=json.dumps({"cue": str(cue.pk), "source": "cue"}),
        content_type="application/json",
    )
    assert answer.status_code == 200
    moment = Moment.objects.get(pk=answer.json()["id"])
    assert moment.source == "cue" and moment.cue_text == "a bag in the console"
    assert moment.at == 12.4 and moment.segment == segment
    cue.refresh_from_db()
    assert cue.state == Cue.ACCEPTED
    state = client.get(f"/recording/{ready.pk}/assistant").json()
    assert state["busy"] is True and state["cues"] == []
    # The same time again while it runs is refused.
    again = client.post(
        f"/recording/{ready.pk}/moments",
        data=json.dumps({"at": 12.9}),
        content_type="application/json",
    )
    assert again.status_code == 409

    # Dismissing a Cue takes it off the list for good.
    other = Cue.objects.create(
        transcript=ready.transcript, at=30.0, reason="a door", confidence="medium"
    )
    assert client.post(f"/cue/{other.pk}/dismiss").status_code == 200
    other.refresh_from_db()
    assert other.state == Cue.DISMISSED
    assert client.get(f"/recording/{ready.pk}/assistant").json()["cues"] == []


@pytest.mark.django_db
def test_find_moments_reads_the_transcript_once_and_keeps_what_it_checks(
    ready, person, client, monkeypatch
):
    from core.assistant import Cue, CueRun

    answer_json = json.dumps(
        {
            "cues": [
                {
                    "line": 2,
                    "kind": "pointing",
                    "reason": "something in the console",
                    "confidence": "high",
                },
                {"line": 3, "kind": "object", "reason": "the car", "confidence": "low"},
            ]
        }
    )
    asked = reachable(monkeypatch, answer_json)
    from core import tasks

    deferred = []
    monkeypatch.setattr(
        tasks.find_moments, "defer", lambda **fields: deferred.append(("text", fields))
    )
    monkeypatch.setattr(
        tasks.scan_for_moments,
        "defer",
        lambda **fields: deferred.append(("media", fields)),
    )
    signed_in(client, person)
    answer = client.post(f"/recording/{ready.pk}/find-moments")
    assert answer.status_code == 200, answer.content
    assert [kind for kind, _ in deferred] == ["text"]
    run = CueRun.objects.get(pk=answer.json()["ids"][0])
    assert run.source == CueRun.TRANSCRIPT and run.state == assistant.QUEUED
    assert client.post(f"/recording/{ready.pk}/find-moments").status_code == 409

    assistant.find_moments(run.pk)
    run.refresh_from_db()
    assert run.state == assistant.DONE and run.found == 1
    (cue,) = Cue.objects.filter(transcript=ready.transcript)
    assert cue.line == 2 and cue.reason == "something in the console"
    assert cue.segment == segment_at(ready, 12.4) and cue.source == Cue.TRANSCRIPT
    call = asked[0]
    assert prompts.FINDER in call["messages"][0]["content"]
    assert (
        "[2] [00:00:12] Speaker 2: Look at that, right there."
        in call["messages"][-1]["content"]
    )
    assert "List at most 12 lines" in call["messages"][-1]["content"]
    assert call["schema"]["properties"]["cues"]["maxItems"] == 12
    assert call["temperature"] == 0.0 and call["timeout"] == 180
    row = Row.objects.filter(category="llm").latest("at")
    assert row.details["feature"] == "moment_finder" and row.details["found"] == 1
    assert "console" not in json.dumps(row.details)
    state = client.get(f"/recording/{ready.pk}/assistant").json()
    assert state["cue_runs"]["transcript"] == {
        "state": "done",
        "found": 1,
        "total": 0,
        "said": "",
    }

    # With the media finder on as well, both runs start, and the scan writes
    # its own Cues from what ffmpeg printed.
    settings_store.set_to("moment_finder_media", True)
    deferred.clear()
    answer = client.post(f"/recording/{ready.pk}/find-moments")
    assert [kind for kind, _ in deferred] == ["text", "media"]
    media_run = CueRun.objects.get(source=CueRun.MEDIA)
    from core import moment_scan

    monkeypatch.setattr(
        moment_scan,
        "scene_changes",
        lambda source, threshold, timeout=0: [5.0, 6.0, 300.0],
    )
    monkeypatch.setattr(
        moment_scan, "loud_seconds", lambda source, rise, timeout=0: [301.0, 730.0]
    )
    moment_scan.scan_for_moments(media_run.pk)
    media_run.refresh_from_db()
    assert media_run.state == assistant.DONE and media_run.found == 3
    scanned = list(
        Cue.objects.filter(source__in=(Cue.PICTURE, Cue.SOUND)).order_by("at")
    )
    assert [(one.at, one.source) for one in scanned] == [
        (5.0, Cue.PICTURE),
        (300.0, Cue.PICTURE),
        (730.0, Cue.SOUND),
    ]
    assert scanned[2].segment == segment_at(ready, 724.0)
    row = Row.objects.get(event="Picture and sound scanned")
    assert row.details["found"] == 3 and row.details["picture_changes"] == 2


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
    answer = client.post(
        f"/recording/{recording.pk}/moments",
        data=json.dumps({"at": 12.4}),
        content_type="application/json",
    )
    assert answer.status_code == 409
    # The task side says the same, should a Moment be queued before the copy lands.
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
    answer = client.post(
        f"/recording/{audio.pk}/moments",
        data=json.dumps({"at": 12.4}),
        content_type="application/json",
    )
    assert answer.status_code == 409
    page = client.get(f"/recording/{audio.pk}").content.decode()
    assert 'data-panel="moments"' not in page


@pytest.mark.django_db
def test_moments_start_off_and_the_viewer_offers_the_tab_only_when_on(
    ready, person, client, monkeypatch
):
    swallow_defer(monkeypatch)
    signed_in(client, person)
    page = client.get(f"/recording/{ready.pk}").content.decode()
    assert 'data-panel="moments"' in page and "moments: true" in page
    settings_store.set_to("moments_available", False)
    assert assistant.features()["moments"] is False
    page = client.get(f"/recording/{ready.pk}").content.decode()
    assert 'data-panel="moments"' not in page
    answer = client.post(
        f"/recording/{ready.pk}/moments",
        data=json.dumps({"at": 12.4}),
        content_type="application/json",
    )
    assert answer.status_code == 404
    state = client.get(f"/recording/{ready.pk}/assistant").json()
    assert state["moments"] == [] and state["cues"] == []
    assert settings_store.DEFINITIONS["moments_available"].default is False


@pytest.mark.django_db
def test_edit_again_and_delete_write_rows_without_words(
    ready, person, client, monkeypatch
):
    swallow_defer(monkeypatch)
    signed_in(client, person)
    moment = Moment.objects.create(
        transcript=ready.transcript,
        at=12.4,
        state=assistant.DONE,
        text="A hand holds a small bag.",
        model="the-model",
        asked_by=person,
    )
    answer = client.post(
        f"/moment/{moment.pk}/edit",
        data=json.dumps({"text": "  A hand holds a clear plastic bag.  "}),
        content_type="application/json",
    )
    assert answer.status_code == 200
    moment.refresh_from_db()
    assert moment.text == "A hand holds a clear plastic bag." and moment.edited
    row = Row.objects.get(event="Moment edited")
    assert "bag" not in json.dumps(row.details)
    assert (
        client.post(
            f"/moment/{moment.pk}/edit",
            data=json.dumps({"text": " "}),
            content_type="application/json",
        ).status_code
        == 400
    )

    answer = client.post(f"/moment/{moment.pk}/again")
    assert answer.status_code == 200
    moment.refresh_from_db()
    assert moment.state == assistant.QUEUED and moment.text == "" and not moment.edited

    answer = client.post(f"/moment/{moment.pk}/delete")
    assert answer.status_code == 200
    assert not Moment.objects.filter(pk=moment.pk).exists()
    row = Row.objects.get(event="Moment deleted")
    assert row.details == {} or "bag" not in json.dumps(row.details)


@pytest.mark.django_db
def test_summary_and_chat_carry_the_camera_block_only_while_the_office_says_so(
    ready, person, monkeypatch
):
    asked = reachable(monkeypatch, "Summary: at [00:00:12] a bag is shown.")
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
def test_the_exports_carry_the_camera_lines_marked(ready, person):
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
        at=800.0,
        state=assistant.DONE,
        text="The car door is open.",
        model="the-model",
    )
    text = exports.plain_text(ready)
    lines = text.split("\r\n")
    assert exports.CAMERA_LEGEND in text
    spoken = [line for line in lines if line.startswith("[00:00:12] Speaker")]
    assert spoken[0].startswith("[00:00:12] Speaker 2:")
    camera = [line for line in lines if exports.CAMERA_TAG in line]
    assert camera == [
        f"[00:00:12] {exports.CAMERA_TAG}: A hand holds a small bag.",
        f"[00:13:20] {exports.CAMERA_TAG}: The car door is open.",
    ]
    # The Moment at 12.4 goes before the line that starts at 12.4, and the
    # one at 800 after the last line.
    assert lines.index(camera[0]) < lines.index(spoken[0])
    assert lines.index(camera[1]) > lines.index(
        [line for line in lines if line.startswith("[00:12:04]")][0]
    )
    assert exports.camera_moments_row(ready.transcript) == (
        "2 described by the-model, 1 edited by staff"
    )

    word = exports.word(ready, "asker")
    assert word[:2] == b"PK"
    import io
    import zipfile

    document = zipfile.ZipFile(io.BytesIO(word)).read("word/document.xml").decode()
    assert "Camera: " in document and "A hand holds a small bag." in document
    assert "Camera moments" in document and exports.CAMERA_LEGEND[:30] in document


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
    answer = client.post(
        f"/recording/{ready.pk}/moments",
        data=json.dumps({"at": 12.4, "question": " Is that a gun on the seat? "}),
        content_type="application/json",
    )
    assert answer.status_code == 200, answer.content
    moment = Moment.objects.get(pk=answer.json()["id"])
    assert moment.question == "Is that a gun on the seat?" and moment.is_question

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
    # A question does not block a description at the same time, and the
    # camera line carries the question in front of the answer.
    assert (
        client.post(
            f"/recording/{ready.pk}/moments",
            data=json.dumps({"at": 12.4}),
            content_type="application/json",
        ).status_code
        == 200
    )
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


def test_interval_times_skip_what_is_described_and_spread_the_rest():
    assert assistant.interval_times(300.0, 60.0, 40, []) == [
        30.0,
        90.0,
        150.0,
        210.0,
        270.0,
    ]
    # A time already described within half an interval is skipped.
    assert assistant.interval_times(300.0, 60.0, 40, [95.0]) == [
        30.0,
        150.0,
        210.0,
        270.0,
    ]
    # More than the most allowed are spread over the recording, not its start.
    spread = assistant.interval_times(3600.0, 60.0, 6, [])
    assert len(spread) == 6 and spread[0] == 30.0 and spread[-1] > 3000.0
    assert assistant.interval_times(0.0, 60.0, 40, []) == []
    assert assistant.interval_times(10.0, 60.0, 40, []) == []


@pytest.mark.django_db
def test_the_whole_recording_is_described_at_intervals_in_one_lane(
    ready, person, client, monkeypatch
):
    from core import tasks
    from core.assistant import CueRun

    asked = reachable(monkeypatch, "A doorway.")
    a_cut(monkeypatch)
    settings_store.set_to("moment_interval_seconds", 300)
    Moment.objects.create(
        transcript=ready.transcript,
        at=452.0,
        state=assistant.DONE,
        text="Already here.",
        model="the-model",
    )
    deferred = []
    monkeypatch.setattr(
        tasks.describe_intervals, "defer", lambda **fields: deferred.append(fields)
    )
    signed_in(client, person)
    answer = client.post(f"/recording/{ready.pk}/describe-intervals")
    assert answer.status_code == 200, answer.content
    assert client.post(f"/recording/{ready.pk}/describe-intervals").status_code == 409
    run = CueRun.objects.get(pk=answer.json()["id"])
    assert run.source == CueRun.INTERVAL and deferred == [{"run_id": str(run.pk)}]

    assistant.describe_intervals(run.pk)
    run.refresh_from_db()
    # 900 s at 300 s: 150, 450, 750; 450 is within half an interval of 452.
    assert run.state == assistant.DONE and (run.found, run.total) == (2, 2)
    made = list(Moment.objects.filter(source=Moment.INTERVAL).order_by("at"))
    assert [one.at for one in made] == [150.0, 750.0]
    assert all(one.state == assistant.DONE and one.text == "A doorway." for one in made)
    assert len(asked) == 2
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
def test_a_summary_may_describe_the_moments_first_and_export_what_the_camera_showed(
    ready, person, client, monkeypatch
):
    from core import tasks

    answers = iter(
        [
            "A doorway.",
            "A car.",
            "A bag.",
            "Summary: the camera shows a bag at [00:12:30].",
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
    monkeypatch.setattr(tasks.write_summary, "defer", lambda **fields: None)
    settings_store.set_to("moment_interval_seconds", 300)
    signed_in(client, person)
    state = client.get(f"/recording/{ready.pk}/assistant").json()
    assert state["cue_runs"]["describe_first_default"] is False
    settings_store.set_to("summary_describes_first", True)
    assert client.get(f"/recording/{ready.pk}/assistant").json()["cue_runs"][
        "describe_first_default"
    ]
    page = client.get(f"/recording/{ready.pk}").content.decode()
    assert 'id="summary-describe-first"' in page

    answer = client.post(
        f"/recording/{ready.pk}/summaries",
        data=json.dumps({"length": "short", "describe_first": True}),
        content_type="application/json",
    )
    assert answer.status_code == 200
    summary = Summary.objects.get(pk=answer.json()["id"])
    assert summary.describe_first
    assistant.write_summary(summary.pk)
    summary.refresh_from_db()
    assert summary.state == assistant.DONE
    # Three interval Moments, then the summary, which was handed them.
    assert (
        Moment.objects.filter(source=Moment.INTERVAL, state=assistant.DONE).count() == 3
    )
    assert len(asked) == 4
    user = asked[3]["messages"][-1]["content"]
    assert prompts.CAMERA_HEADING in user and "[00:12:30] [camera] A bag." in user
    assert "the camera shows" in prompts.SUMMARY_FORMAT
    assert summary.citations == {"[00:12:30]": 750.0}

    word = exports.summary_word(summary, "asker")
    import io
    import zipfile

    document = zipfile.ZipFile(io.BytesIO(word)).read("word/document.xml").decode()
    assert "What the camera showed" in document and "A bag." in document
    assert exports.CAMERA_LEGEND[:30] in document


def test_the_interval_settings_start_as_the_chapter_says():
    for key, default in (
        ("moment_interval_seconds", 60),
        ("moment_interval_most", 40),
        ("summary_describes_first", False),
    ):
        assert settings_store.DEFINITIONS[key].default == default
    text = CATALOGUE.read_text(encoding="utf-8")
    for name in (
        "Describe at intervals: every",
        "Describe at intervals: at most",
        "Summaries describe the moments first",
    ):
        assert f"| {name} |" in text, f"the catalogue has no row for {name}"
