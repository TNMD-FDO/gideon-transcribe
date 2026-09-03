"""The app's own Django application.

Everything the app is made of lives here for now. It gains models as the
build reaches them: accounts and Login sessions, then Recordings and Batches,
then Jobs and Runs, then Transcripts.
"""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self) -> None:
        """Import the background tasks so that a worker can find them.

        A worker that cannot see a task takes the job and fails it, which
        looks like a broken recording rather than a missing import.
        """
        from core import tasks  # noqa: F401
