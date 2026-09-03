"""The app's own Django application.

Everything the app is made of lives here for now. It gains models as the
build reaches them: accounts and Login sessions, then Recordings and Batches,
then Jobs and Runs, then Transcripts.
"""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
