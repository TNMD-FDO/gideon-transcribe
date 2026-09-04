"""The media pipeline's own arithmetic, without ffmpeg or a file.

What needs a real recording is checked on the server against the office's own
corpus, because the interesting cases are its actual files. What is checked
here is everything that reads or decides rather than measures.
"""

import subprocess
from pathlib import Path
from unittest import mock

from core import media
from core.recordings import Refusal

# What ffmpeg really prints. Every line a filter writes carries a prefix
# naming the filter and its address, which is what the parser has to see past.
ASTATS = """\
size=N/A time=00:05:24.41 bitrate=N/A speed= 649x
[Parsed_astats_0 @ 0x72afb8004500] Channel: 1
[Parsed_astats_0 @ 0x72afb8004500] DC offset: 0.000031
[Parsed_astats_0 @ 0x72afb8004500] RMS level dB: -26.528908
[Parsed_astats_0 @ 0x72afb8004500] Channel: 2
[Parsed_astats_0 @ 0x72afb8004500] RMS level dB: -27.603545
[Parsed_astats_0 @ 0x72afb8004500] Overall
[Parsed_astats_0 @ 0x72afb8004500] RMS level dB: -27.033072
"""

SILENT = """\
[Parsed_astats_0 @ 0x1] Channel: 1
[Parsed_astats_0 @ 0x1] RMS level dB: -inf
[Parsed_astats_0 @ 0x1] Channel: 2
[Parsed_astats_0 @ 0x1] RMS level dB: -21.5
"""


def test_the_levels_are_read_past_the_filter_prefix():
    levels = media.read_levels(ASTATS)
    assert levels["1"] == -26.528908
    assert levels["2"] == -27.603545
    assert levels["overall"] == -27.033072


def test_a_silent_channel_reads_as_silence_rather_than_a_number():
    levels = media.read_levels(SILENT)
    assert levels["1"] == float("-inf")
    assert levels["2"] == -21.5


def test_nothing_printed_means_nothing_read():
    assert media.read_levels("") == {}


def test_the_decoder_is_named_only_when_ffmpeg_could_not_work_it_out():
    unknown = media.Track(index=0, codec="", channels=2, sample_rate=8000)
    known = media.Track(index=0, codec="g729", channels=2, sample_rate=8000)
    assert media.forced_decoder(unknown) == ["-c:a", "g729"]
    assert media.forced_decoder(known) == []
    assert media.forced_decoder(None) == ["-c:a", "g729"]


def test_the_track_with_the_most_channels_wins():
    """whisperx's own loader takes the track with the most channels."""
    probe = media.Probe(
        raw={},
        duration_seconds=60.0,
        tracks=(
            media.Track(index=0, codec="aac", channels=1, sample_rate=48000),
            media.Track(index=1, codec="aac", channels=2, sample_rate=48000),
        ),
    )
    assert probe.best_track.index == 1
    assert probe.has_audio is True


def test_a_file_with_no_audio_has_no_track():
    probe = media.Probe(raw={}, duration_seconds=60.0, tracks=())
    assert probe.has_audio is False
    assert probe.best_track is None


def test_one_channel_takes_that_channel_and_no_channel_takes_everything():
    assert media._channel_filter(0) == "pan=1c|c0=c0,"
    assert media._channel_filter(1) == "pan=1c|c0=c1,"
    assert media._channel_filter(None) == ""


def test_every_refusal_a_person_can_meet_has_words_for_them():
    for reason in Refusal.ALL:
        assert reason in Refusal.MESSAGES, reason
        assert Refusal.MESSAGES[reason].strip()


def test_the_margin_that_separates_a_call_from_ordinary_stereo():
    """The threshold, against what the office's own recordings measured.

    Calls came out between -13.1 and -2.1 decibels, and ordinary stereo
    between +1.2 and +5.0, so zero sits between them with room on both sides.
    """
    calls = [-13.1, -3.0, -2.6, -2.1]
    stereo = [1.2, 2.1, 5.0]
    assert all(margin < media.DIFFERENCE_MARGIN_DB for margin in calls)
    assert all(margin >= media.DIFFERENCE_MARGIN_DB for margin in stereo)


def test_the_playback_copy_pins_its_sample_rate():
    """A browser will not play 96 kHz AAC, and nothing else pins the rate.

    The loudness filter resamples to 192 kHz inside itself, so with no rate
    asked for the encoder settles on 96 kHz and the whole file fails to play,
    not only its sound. This is a regression guard, not a preference.
    """
    seen = {}

    def remember(arguments, timeout):
        seen["arguments"] = arguments
        return subprocess.CompletedProcess(arguments, 0, "", "")

    probed = media.Probe(
        raw={"streams": [{"codec_type": "audio", "channels": 2}]},
        duration_seconds=10.0,
        tracks=(media.Track(index=0, codec="aac", channels=2, sample_rate=48000),),
    )

    with (
        mock.patch.object(media, "_run", remember),
        mock.patch.object(media, "_measure_loudness", return_value={}),
        mock.patch.object(Path, "exists", return_value=True),
    ):
        media.make_playback_copy(Path("in.mp4"), Path("out.m4a"), probed, "standard")

    arguments = seen["arguments"]
    assert "-ar" in arguments
    assert arguments[arguments.index("-ar") + 1] == "48000"


def test_the_asr_audio_keeps_wall_clock_time():
    """A hole in the audio is filled, not closed.

    This is a real failure: a body-worn camera dropped 5.26s of audio across a
    25-minute file. The mp4 playback copy kept the hole, because it carries a
    timestamp per frame; the WAV could not, so ffmpeg wrote the samples end to
    end and every word after the hole was 5.26s early against the video.
    """
    from core import media

    assert media.KEEP_THE_CLOCK.startswith("aresample=async=1")
    assert "first_pts=0" in media.KEEP_THE_CLOCK


def test_both_copies_start_with_the_same_filter(tmp_path, monkeypatch):
    """The playback copy and the ASR audio must agree about time.

    They are made by two separate ffmpeg runs, so nothing but this keeps them
    in step. The commands are captured rather than run: what is being checked
    is what ffmpeg is asked to do.
    """
    from core import media

    asked = []

    def remember(arguments, **rest):
        asked.append(arguments)

        class Finished:
            returncode = 0
            stdout = ""
            stderr = ""

        target = arguments[-1]
        if not str(target).startswith("-"):
            Path(target).parent.mkdir(parents=True, exist_ok=True)
            Path(target).write_bytes(b"x")
        return Finished()

    monkeypatch.setattr(media, "_run", remember)

    source = tmp_path / "original.mp4"
    source.write_bytes(b"x")

    media.make_asr_audio(source, tmp_path / "asr-side1.wav", None, profile="none")
    media.make_playback_copy(
        source,
        tmp_path / "playback.mp4",
        media.Probe(raw={"streams": [], "format": {}}, duration_seconds=1.0, tracks=()),
        profile="none",
    )

    filters = [
        arguments[arguments.index("-af") + 1]
        for arguments in asked
        if "-af" in arguments
    ]
    assert len(filters) == 2
    for one in filters:
        assert one.startswith(media.KEEP_THE_CLOCK), one


# The thread cap ---------------------------------------------------------------


def test_every_ffmpeg_is_capped(monkeypatch):
    """The specification's cap, applied where it cannot be forgotten.

    The media worker runs several jobs at once and shares the server with the
    web process, the queue and Postgres. Without this each ffmpeg takes every
    core it can see, and four transcodes make the rest of the app wait.
    """
    monkeypatch.setenv("MEDIA_THREADS_PER_JOB", "3")
    asked = []

    def remember(arguments, **rest):
        asked.append(arguments)

        class Finished:
            returncode = 0
            stdout = "{}"
            stderr = ""

        return Finished()

    monkeypatch.setattr(subprocess, "run", remember)

    media._run(["ffmpeg", "-i", "in.mp4", "out.wav"], timeout=5)
    media._run(["ffprobe", "-v", "error", "in.mp4"], timeout=5)
    media._run(["audiowaveform", "-i", "in.wav"], timeout=5)

    assert asked[0][:3] == ["ffmpeg", "-threads", "3"]
    assert asked[1][:3] == ["ffprobe", "-threads", "3"]
    # Only ffmpeg's own tools take it; audiowaveform has no such option and
    # would refuse to start.
    assert asked[2] == ["audiowaveform", "-i", "in.wav"]


def test_the_cap_falls_back_to_the_specifications_default(monkeypatch):
    monkeypatch.delenv("MEDIA_THREADS_PER_JOB", raising=False)
    assert media.threads_per_job() == 8
    monkeypatch.setenv("MEDIA_THREADS_PER_JOB", "not a number")
    assert media.threads_per_job() == 8
    monkeypatch.setenv("MEDIA_THREADS_PER_JOB", "0")
    assert media.threads_per_job() == 8
