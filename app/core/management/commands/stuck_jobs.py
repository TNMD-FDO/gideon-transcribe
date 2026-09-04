"""Background jobs that have stopped moving, and putting them back in the line.

The transcription queue is not this. That is the WhisperX service's own line,
and a Run lost there fails with a reason class and offers Retry on the page.
This is the app's own background work: the media jobs, the polls, the nightly
sweeps.

A worker that dies holding a job leaves it marked as being done, and it sits
there for ever. A periodic task puts those back every ten minutes on its own,
by the worker's heartbeat. This is for the times that is not enough: a job
wedged by something the app cannot see, at three in the morning, with somebody
waiting.

    docker compose run --rm app stuck_jobs
    docker compose run --rm app stuck_jobs --release
    docker compose run --rm app stuck_jobs --release --queue media
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from core import audit

# What counts as stopped moving. The longest thing this app asks of a media
# worker is a Playback copy of a multi-gigabyte recording, which is minutes;
# an hour with no progress is not slowness.
LONG_ENOUGH = 60 * 60

DOING = "doing"


def started(job) -> object | None:
    """When the work began, under whichever name this version of the queue uses."""
    for name in ("started_at", "scheduled_at", "attempted_at"):
        when = getattr(job, name, None)
        if when is not None:
            return when
    return None


class Command(BaseCommand):
    help = "Show background jobs that have stopped moving, and put them back."

    def add_arguments(self, parser):
        parser.add_argument(
            "--release",
            action="store_true",
            help="put them back in the line; without this it only says what it found",
        )
        parser.add_argument(
            "--queue",
            default="",
            help="one queue only: media, default, or llm",
        )

    def handle(self, *arguments, **options):
        from core.tasks import app as queue_app

        wanted = options["queue"]
        release = options["release"]

        # The synchronous half of the queue's own interface, which is what a
        # command run by hand should use: the asynchronous half belongs to the
        # workers.
        with queue_app.open():
            doing = queue_app.job_manager.list_jobs(queue=wanted or None, status=DOING)

            if not doing:
                where = f" in the {wanted} queue" if wanted else ""
                print(f"Nothing is being worked on{where}.")
                return

            now = timezone.now()
            rows = []
            for job in doing:
                began = started(job)
                minutes = (now - began).total_seconds() / 60 if began else None
                stuck = minutes is not None and minutes * 60 > LONG_ENOUGH
                rows.append((job, minutes, stuck))

            print(f"{len(doing)} job(s) being worked on:")
            for job, minutes, stuck in rows:
                age = "unknown" if minutes is None else f"{minutes:.0f} min"
                print(
                    f"  {str(job.id).rjust(7)}  {job.queue:<9}{job.task_name:<26}"
                    f"{age:>10}  {'STUCK' if stuck else ''}"
                )

            wedged = [job for job, _, stuck in rows if stuck]
            if not wedged:
                print("\nNone of them has been at it for an hour. Nothing to do.")
                return

            if not release:
                print(
                    f"\n{len(wedged)} have been at it for over an hour. Run this "
                    "again with --release to put them back in the line."
                )
                return

            for job in wedged:
                queue_app.job_manager.retry_job_by_id(job_id=job.id, retry_at=now)

        for job in wedged:
            # An Admin reaching into the queue by hand is a thing the log knows
            # about, as every other admin action is.
            audit.write(
                audit.Category.SYSTEM,
                "stuck job released",
                system="stuck_jobs",
                object_type="job",
                object_id=job.id,
                object_label=job.task_name,
                queue=job.queue,
            )

        print(f"\n{len(wedged)} put back in the line. A worker will pick them up.")
