"""Cues and their runs: where the picture would tell what the words cannot (Phase 4)."""

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0036_moment_question"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Cue",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("at", models.FloatField()),
                ("line", models.IntegerField(default=0)),
                ("kind", models.CharField(default="change", max_length=12)),
                ("reason", models.CharField(blank=True, default="", max_length=120)),
                ("confidence", models.CharField(default="medium", max_length=8)),
                ("source", models.CharField(default="transcript", max_length=12)),
                ("state", models.CharField(default="pending", max_length=10)),
                ("created", models.DateTimeField(auto_now_add=True)),
                (
                    "segment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="core.segment",
                    ),
                ),
                (
                    "transcript",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cues",
                        to="core.transcript",
                    ),
                ),
            ],
            options={"ordering": ["at", "created"]},
        ),
        migrations.CreateModel(
            name="CueRun",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("source", models.CharField(default="transcript", max_length=12)),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("queued", "queued"),
                            ("running", "running"),
                            ("done", "done"),
                            ("failed", "failed"),
                        ],
                        default="queued",
                        max_length=10,
                    ),
                ),
                (
                    "reason_class",
                    models.CharField(blank=True, default="", max_length=40),
                ),
                ("found", models.IntegerField(default=0)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "asked_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "transcript",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cue_runs",
                        to="core.transcript",
                    ),
                ),
            ],
            options={"ordering": ["-created"]},
        ),
    ]
