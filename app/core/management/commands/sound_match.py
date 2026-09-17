"""The sound match tried on two recordings, by hand (Phase 6 chapter 1).

For the probe the chapter asks for on the office's own files, and for
support: prints how many seconds after the first recording the second
starts by their sound, how clearly, and how long the comparison took.
Nothing is changed, and nothing of the sound is printed.
"""

from __future__ import annotations

import time

from django.core.management.base import BaseCommand, CommandError

from core import incidents, sound_match
from core.recordings import Recording


class Command(BaseCommand):
    help = "Compare two recordings' sound and print the shift between them."

    def add_arguments(self, parser):
        parser.add_argument(
            "reference", help="the recording id the other is measured against"
        )
        parser.add_argument("other", help="the recording id to place")
        parser.add_argument(
            "--expected",
            type=float,
            default=None,
            help="a shift in seconds to search around, ten minutes either way",
        )

    def handle(self, *args, **options):
        reference = self._recording(options["reference"])
        other = self._recording(options["other"])
        try:
            mine = incidents._first_side_audio(reference)
            theirs = incidents._first_side_audio(other)
        except sound_match.NoMatch as why:
            raise CommandError(str(why)) from why
        started = time.monotonic()
        try:
            found = sound_match.lag_between(mine, theirs, expected=options["expected"])
        except sound_match.NoMatch as why:
            raise CommandError(f"No match: {why}") from why
        seconds = time.monotonic() - started
        self.stdout.write(
            f"{other.title} starts {found.lag:+.2f} s after {reference.title} "
            f"by their sound; strength {found.strength:.2f} "
            f"({'strong' if found.strength >= incidents.STRONG_MATCH else 'weak'}, "
            f"the threshold is {incidents.STRONG_MATCH}); {seconds:.1f} s to compare."
        )

    @staticmethod
    def _recording(text: str) -> Recording:
        recording = Recording.objects.filter(pk=text).first()
        if recording is None:
            raise CommandError(f"No recording {text}")
        return recording
