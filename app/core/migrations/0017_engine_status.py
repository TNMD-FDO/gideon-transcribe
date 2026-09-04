"""The engine's status row: what the last minute's check found.

One row, written by llm-worker, the only container on the engine's network,
and read by the Status page and the viewer, which never touch that network.
"""

from django.db import migrations, models
from django.utils import timezone


class Migration(migrations.Migration):
    dependencies = [("core", "0016_retention")]

    operations = [
        migrations.CreateModel(
            name="EngineStatus",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("reachable", models.BooleanField(default=False)),
                ("since", models.DateTimeField(default=timezone.now)),
                ("checked_at", models.DateTimeField(blank=True, null=True)),
                ("served_models", models.JSONField(blank=True, default=list)),
                ("reason", models.CharField(blank=True, default="", max_length=40)),
                ("last_test", models.JSONField(blank=True, default=dict)),
            ],
            options={"verbose_name": "engine status"},
        ),
    ]
