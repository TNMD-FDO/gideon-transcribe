"""Background jobs that have stopped moving, and putting them back in the line.

The transcription queue is not this. That is the WhisperX service's own line,
and a Run lost there fails with a reason class and offers Retry on the page.
This is the app's own background work: the media jobs, the polls, the nightly
sweeps.

A worker that dies holding a job leaves it marked as being done, and it sits
there for ever. A periodic task puts those back every ten minutes on its own.
This is for the times that is not enough: a job wedged by something the app
cannot see, at three in the morning, with somebody waiting.

    docker compose run --rm app stuck_jobs
    docker compose run --rm app stuck_jobs --release
    docker compose run --rm app stuck_jobs --release --queue media
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from core import audit

# What counts as stopped moving. A worker writes a heartbeat every ten
# seconds, so thirty is already generous; an hour of no progress on a job
# nobody is holding is not slowness, it is stuck.
LONG_ENOUGH = 60 * 60


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
        from procrastinate.jobs import Status

        from core.tasks import app as queue_app

        wanted = options["queue"]
        release = options["release"]

        with queue_app.open():
            doing = list(
                queue_app.job_manager.list_jobs(
                    queue=wanted or None, status=Status.DOING.value
                )
            )
            stalled = {job.id for job in queue_app.job_manager.get_stalled_jobs()}

        if not doing:
            where = f" (queue: {wanted})" if wanted else ""
            print("Nothing is being worked on." + where)
            return

        now = timezone.now()
        stuck = []
        for job in doing:
            started = getattr(job, "started_at", None) or getattr(
                job, "scheduled_at", None
            )
            age = (now - started).total_seconds() if started else None
            looks_stuck = job.id in stalled or (age is not None and age > LONG_ENOUGH)
            stuck.append((job, age, looks_stuck))

        print(f"{len(doing)} job(s) being worked on:")
        for job, age, looks_stuck in stuck:
            print(
                f"  {str(job.id).rjust(7)}  {job.queue:<8} {job.task_name:<24}"
                f"  {'?' if age is None else f'{age / 60:.0f} min'}"
                f"  {'STUCK' if looks_stuck else ''}"
            )

        wedged = [job for job, _, looks_stuck in stuck if looks_stuck]
        if not wedged:
            print("\nNone of them has stopped moving. Nothing to do.")
            return

        if not release:
            print(
                f"\n{len(wedged)} look stuck. Run it again with --release to put "
                "them back in the line."
            )
            return

        with queue_app.open():
            for job in wedged:
                queue_app.job_manager.retry_job(job)

        for job in wedged:
            audit.write(
                audit.Category.SYSTEM,
                "stuck job released",
                system="admin command",
                object_type="job",
                object_id=job.id,
                object_label=job.task_name,
                queue=job.queue,
            )

        print(f"\n{len(wedged)} put back in the line. A worker will pick them up.")
