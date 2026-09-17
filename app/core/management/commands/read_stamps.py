"""Read the camera stamp of every case video that has none (Phase 6 chapter 1).

The stamp reads as a playback copy lands from v1.58.0 on; the videos already
in cases before then have no clock until something reads it. This queues
the read for each of them, on the assistant's queue, two small engine calls
per video, and prints how many were queued. Run once after the upgrade; it
is safe to run again, since a video with a stamp, even an empty one, is
skipped.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from core import engine, incidents, tasks
from core.recordings import Recording


class Command(BaseCommand):
    help = "Queue the camera stamp read for every case video without one."

    def handle(self, *args, **options):
        if not incidents.stamp_early_on():
            self.stdout.write(
                "Stamp reads early is off (or Incidents, Vision, or Read the "
                "camera's stamp is off); nothing queued."
            )
            return
        if not engine.is_reachable():
            self.stdout.write("The engine is not answering; nothing queued.")
            return
        queued = 0
        for recording in Recording.objects.filter(
            case__isnull=False, playback_ready=True, stamp=None
        ).iterator():
            if incidents.wants_early_stamp(recording):
                tasks.read_stamp_early.defer(recording_id=str(recording.pk))
                queued += 1
        self.stdout.write(f"{queued} video{'' if queued == 1 else 's'} queued.")
