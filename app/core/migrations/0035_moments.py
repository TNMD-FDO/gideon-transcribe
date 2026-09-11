"""A Moment: what the camera showed at one time of a video Recording (Phase 4)."""

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0034_speaker_changes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Moment",
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
                ("span_start", models.FloatField(default=0.0)),
                ("span_end", models.FloatField(default=0.0)),
                ("source", models.CharField(default="asked", max_length=10)),
                ("cue_text", models.CharField(blank=True, default="", max_length=80)),
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
                ("text", models.TextField(blank=True, default="")),
                ("edited", models.BooleanField(default=False)),
                ("model", models.CharField(blank=True, default="", max_length=120)),
                ("frames", models.IntegerField(default=0)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("described_at", models.DateTimeField(blank=True, null=True)),
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
                        related_name="moments",
                        to="core.transcript",
                    ),
                ),
            ],
            options={
                "ordering": ["at", "created"],
            },
        ),
    ]
