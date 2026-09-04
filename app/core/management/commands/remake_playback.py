"""Make the Playback copies again, for Recordings that have one or need one.

Two things bring somebody here. A Playback copy made before the audio's
sample rate was pinned holds 96 kHz AAC, which a browser will not play; and a
Recording whose Playback copy failed the first time has none at all, so its
viewer says "Preparing video" for ever.

Nothing is lost by running it: the copy and the waveform are made from the
uploaded bytes, which are still there, and the Transcript is not touched.
"""

from __future__ import annotations

import subprocess

from django.core.management.base import BaseCommand

from core import media, pipeline
from core.recordings import MediaState, Recording

# What the copy's audio should be. Anything else was made before the rate was
# pinned and will not play.
WANTED_RATE = media.PLAYBACK_SAMPLE_RATE


class Command(BaseCommand):
    help = "Make the Playback copies again where they are missing or wrong"

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="remake every Playback copy, not only the missing and wrong ones",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="say what would be done and do nothing",
        )

    def handle(self, *arguments, **options):
        ready = Recording.objects.filter(media_state=MediaState.READY)
        wanted = []

        for recording in ready:
            why = self._why(recording, options["all"])
            if why:
                wanted.append((recording, why))

        if not wanted:
            self.stdout.write("Every playback copy is there and playable.")
            return

        self.stdout.write(f"{len(wanted)} recording(s) to do:")
        for recording, why in wanted:
            self.stdout.write(f"  {recording.title[:44]:46} {why}")

        if options["dry_run"]:
            self.stdout.write("\nNothing was done (--dry-run).")
            return

        self.stdout.write("")
        done = 0
        for recording, _ in wanted:
            self.stdout.write(f"  {recording.title[:44]:46} ", ending="")
            self.stdout.flush()
            before = recording.playback_path()
            if before is not None and before.exists():
                before.unlink()

            recording = pipeline.make_playback(recording)
            after = recording.playback_path()
            if after is not None and after.exists():
                done += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{after.name}, {after.stat().st_size / 1024 / 1024:.0f} MB"
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR("could not be made; see the journal")
                )

        self.stdout.write(f"\n{done} of {len(wanted)} done.")

    def _why(self, recording: Recording, everything: bool) -> str:
        """The reason this Recording needs the work, or nothing."""
        path = recording.playback_path()
        if path is None or not path.exists():
            return "no playback copy"
        if everything:
            return "asked for"

        rate = self._sample_rate(path)
        if rate is None:
            return "the copy could not be read"
        if rate != WANTED_RATE:
            return f"audio at {rate} Hz, which a browser will not play"
        if not recording.waveform_path.exists():
            return "no waveform"
        return ""

    def _sample_rate(self, path) -> int | None:
        finished = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=sample_rate",
                "-of", "default=nw=1:nk=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        said = finished.stdout.strip()
        return int(said) if said.isdigit() else None
