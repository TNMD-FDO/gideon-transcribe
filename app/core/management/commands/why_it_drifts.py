"""Say why a Recording's transcript does not line up with its playback.

There are only a few ways this happens, and they leave different marks:

  A constant offset  the uploaded file's streams do not start at zero, or its
                     audio starts after its video. The playback copy keeps the
                     video's own timestamps when the video is copied, while
                     the audio the model heard starts at its first sample, so
                     everything is out by the difference.

  A growing gap      the audio has holes in it, which many body-worn cameras
                     record. Re-encoding closes the holes, so the audio the
                     model heard is shorter than the video and every word
                     after a hole is early by the total of the holes so far.

  A stretch          the durations disagree by a ratio rather than an amount,
                     which means a timebase was misread.

This reads the file, the playback copy, and the transcript, prints what each
one says, and names which of the three it looks like. It changes nothing.
"""

from __future__ import annotations

import json
import subprocess

from django.core.management.base import BaseCommand

from core.recordings import Recording


def probe(path) -> dict:
    finished = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if finished.returncode != 0:
        return {}
    try:
        return json.loads(finished.stdout or "{}")
    except json.JSONDecodeError:
        return {}


def number(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def streams_of(raw: dict, kind: str) -> list:
    return [one for one in raw.get("streams", []) if one.get("codec_type") == kind]


def say(label: str, raw: dict) -> dict:
    """Print what one file says about itself, and hand back the figures."""
    shape = raw.get("format", {})
    told = {
        "duration": number(shape.get("duration")),
        "start": number(shape.get("start_time")),
    }
    print(f"\n{label}")
    print(
        f"  container   {shape.get('format_name', '?')}"
        f"  start {told['start']}  duration {told['duration']}"
    )
    for kind in ("video", "audio"):
        for one in streams_of(raw, kind):
            told[f"{kind}_start"] = number(one.get("start_time"))
            told[f"{kind}_duration"] = number(one.get("duration"))
            rate = one.get("sample_rate") or one.get("avg_frame_rate", "")
            print(
                f"  {kind:<11} {one.get('codec_name', '?')}"
                f"  start {one.get('start_time')}"
                f"  duration {one.get('duration')}"
                f"  rate {rate}"
                f"  channels {one.get('channels', '')}"
            )
    return told


class Command(BaseCommand):
    help = "Say why a Recording's transcript does not line up with its playback."

    def add_arguments(self, parser):
        parser.add_argument(
            "which",
            help="part of the Recording's title, or its id",
        )

    def handle(self, *arguments, **options):
        which = options["which"]
        recording = (
            Recording.objects.filter(pk=which).first()
            if len(which) == 36
            else Recording.objects.filter(title__icontains=which)
            .order_by("-created")
            .first()
        )
        if recording is None:
            self.stderr.write(f"No recording whose title holds {which!r}.")
            return

        print(f"{recording.title}  ({recording.pk})")
        print(f"  folder      {recording.folder}")
        print(f"  in a case   {bool(recording.case_id)}")
        print(f"  two-channel {recording.is_two_channel_call}")
        print(f"  app says    duration {recording.duration_seconds}")

        original = say("The uploaded file", recording.probe or {})

        playback_path = recording.playback_path()
        playback = {}
        if playback_path is None:
            print("\nThe playback copy: there is none.")
        else:
            playback = say(
                f"The playback copy ({playback_path.name})", probe(playback_path)
            )

        heard = {}
        for side in recording.sides.all():
            candidate = side.asr_path
            if candidate.exists():
                heard = say(
                    f"The audio the model heard (side {side.number}, {candidate.name})",
                    probe(candidate),
                )

        transcript = getattr(recording, "transcript", None)
        last_word = None
        if transcript is not None:
            segments = transcript.segments.order_by("start")
            first = segments.first()
            last = segments.last()
            if last is not None:
                last_word = last.end
                print("\nThe transcript")
                print(f"  segments    {segments.count()}")
                print(f"  first at    {first.start}")
                print(f"  last ends   {last.end}")

        print("\nWhat that looks like")
        self.verdict(original, playback, heard, last_word)

    def verdict(self, original, playback, heard, last_word):
        offsets = [
            ("the uploaded file's container", original.get("start")),
            ("its video stream", original.get("video_start")),
            ("its audio stream", original.get("audio_start")),
            ("the playback copy's video", playback.get("video_start")),
            ("the playback copy's audio", playback.get("audio_start")),
        ]
        moved = [(what, at) for what, at in offsets if at not in (None, 0.0)]
        for what, at in moved:
            print(f"  {what} starts at {at}, not zero")

        video_start = original.get("video_start") or 0.0
        audio_start = original.get("audio_start") or 0.0
        apart = round(abs(audio_start - video_start), 3)
        if apart > 0.05:
            print(
                f"  the audio and the video of the uploaded file start {apart}s "
                "apart, which is a constant offset of that much"
            )

        long_file = original.get("duration")
        long_heard = heard.get("duration") or heard.get("audio_duration")
        long_playback = playback.get("duration")

        if long_file and long_heard:
            missing = round(long_file - long_heard, 2)
            if abs(missing) > 1.0:
                ratio = round(long_heard / long_file, 4)
                print(
                    f"  the model heard {long_heard}s of a {long_file}s file, "
                    f"{missing}s less ({ratio} of it)"
                )
                if 0.98 < ratio < 1.02:
                    print(
                        "  -> a growing gap: holes in the audio, closed by re-encoding"
                    )
                else:
                    print(
                        "  -> a stretch: the durations are out by a "
                        "ratio, not an amount"
                    )

        if long_playback and long_file and abs(long_playback - long_file) > 1.0:
            print(
                f"  the playback copy is {round(long_playback - long_file, 2)}s "
                "longer than the uploaded file"
            )

        if last_word and long_playback and last_word > long_playback + 1:
            print(
                f"  the last word is at {last_word}s in a {long_playback}s "
                "playback copy, so the transcript runs past the end of it"
            )

        nothing_odd = (
            not moved
            and apart <= 0.05
            and long_file
            and long_heard
            and abs(long_file - long_heard) <= 1.0
        )
        if nothing_odd:
            print("  nothing here explains a drift. Say what you saw and when.")
