"""Put a file on the server through the media pipeline, without a browser.

    docker compose run --rm app ingest /corpus/04a-jail-call-g729.wav --user fpdadmin

This exists so that the pipeline can be tried against an office's own
recordings before the Upload page is built, and afterwards whenever somebody
needs to know what the app makes of a particular file. It does exactly what an
upload does once the bytes have arrived: hash, look inside, decide, work out
the Sides, and prepare the audio the WhisperX service is sent.

It is not how anybody uploads. Uploading is the Upload page, over tus, in a
browser.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core import pipeline
from core.models import User
from core.recordings import Batch


class Command(BaseCommand):
    help = "Run a file on the server through the media pipeline."

    def add_arguments(self, parser) -> None:
        parser.add_argument("path", help="the file, as this container sees it")
        parser.add_argument("--user", required=True, help="whose recording it is")
        parser.add_argument(
            "--diarize",
            action="store_true",
            help="separate the speakers",
        )
        parser.add_argument(
            "--preprocessing",
            default="standard",
            choices=["standard", "off"],
            help="how the audio is prepared (the default is standard)",
        )

    def handle(self, *args, **options) -> None:
        source = Path(options["path"])
        if not source.is_file():
            raise CommandError(f"{source} is not a file this container can see.")

        try:
            user = User.objects.get(username=options["user"])
        except User.DoesNotExist:
            raise CommandError(
                f"There is no account called {options['user']}."
            ) from None

        batch = Batch.objects.create(user=user)
        recording = pipeline.accept(
            user,
            batch,
            source,
            source.name,
            diarize=options["diarize"],
            preprocessing=options["preprocessing"],
        )
        self.stdout.write(f"recording {recording.id}")

        recording = pipeline.prepare(recording)

        self.stdout.write(f"  state       {recording.media_state}")
        if recording.failure_message:
            self.stdout.write(f"  because     {recording.failure_message}")
            self.stdout.write(f"  reason      {recording.refusal_class}")
            return

        minutes = (recording.duration_seconds or 0) / 60
        self.stdout.write(f"  length      {minutes:.1f} minutes")
        self.stdout.write(f"  hash        {recording.sha256[:16]}")
        self.stdout.write(f"  tracks      {recording.tracks_found}")
        self.stdout.write(
            f"  call        {'yes' if recording.is_two_channel_call else 'no'}"
        )
        for side in recording.sides.all():
            size = side.asr_path.stat().st_size if side.asr_path.exists() else 0
            self.stdout.write(
                f"  side {side.number}      {side.name or 'the whole recording'}, "
                f"{size / 1024 / 1024:.1f} MB of prepared audio"
            )

        # The Playback copy and the waveform follow Ready and never hold
        # recognition up. Here they are run straight afterwards, because there
        # is nothing else waiting.
        recording = pipeline.make_playback(recording)
        playback = recording.playback_path()
        if playback is None:
            self.stdout.write("  playback    could not be made; see the journal")
            return
        self.stdout.write(
            f"  playback    {playback.name}, "
            f"{playback.stat().st_size / 1024 / 1024:.1f} MB"
        )
        if recording.waveform_path.exists():
            peaks = json.loads(recording.waveform_path.read_text())
            self.stdout.write(
                f"  waveform    {len(peaks.get('data', []))} points, "
                f"{peaks.get('channels', 1)} channel(s)"
            )
