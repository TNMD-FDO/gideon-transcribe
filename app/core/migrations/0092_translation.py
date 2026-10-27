# Translation by the chat engine from the words as spoken (ADR 0026, Phase 1
# chapter 7, v1.162.0): each line's language and its English beside the
# words as spoken, and the run row, one live per Transcript.

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0091_system_voice"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="segment",
            name="language",
            field=models.CharField(blank=True, default="", max_length=8),
        ),
        migrations.AddField(
            model_name="segment",
            name="english",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="segment",
            name="english_of",
            field=models.CharField(blank=True, default="", max_length=16),
        ),
        migrations.CreateModel(
            name="Translation",
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
                ("how", models.CharField(blank=True, default="", max_length=12)),
                ("lines", models.IntegerField(default=0)),
                ("lines_written", models.IntegerField(default=0)),
                ("lines_missing", models.IntegerField(default=0)),
                ("windows", models.IntegerField(default=0)),
                ("windows_done", models.IntegerField(default=0)),
                ("expectation", models.JSONField(blank=True, default=dict)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
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
                        related_name="translations",
                        to="core.transcript",
                    ),
                ),
            ],
            options={
                "ordering": ["-created"],
            },
        ),
        migrations.AddConstraint(
            model_name="translation",
            constraint=models.UniqueConstraint(
                condition=models.Q(("state__in", ("queued", "running"))),
                fields=("transcript",),
                name="one_live_translation_per_transcript",
            ),
        ),
    ]
