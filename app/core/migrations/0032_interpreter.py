"""The Interpreter (Phase 3, chapter 3): a Session's Turns, and a Segment's
language and translation."""

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0031_stretches"),
    ]

    operations = [
        migrations.AddField(
            model_name="segment",
            name="language",
            field=models.CharField(blank=True, default="", max_length=10),
        ),
        migrations.AddField(
            model_name="segment",
            name="translation",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.CreateModel(
            name="Turn",
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
                ("number", models.IntegerField()),
                ("side", models.CharField(blank=True, default="", max_length=10)),
                ("typed", models.BooleanField(default=False)),
                ("start", models.FloatField(default=0.0)),
                ("end", models.FloatField(default=0.0)),
                ("language", models.CharField(blank=True, default="", max_length=10)),
                ("heard", models.TextField(blank=True, default="")),
                ("translation", models.TextField(blank=True, default="")),
                ("state", models.CharField(default="hearing", max_length=12)),
                ("failure", models.CharField(blank=True, default="", max_length=60)),
                (
                    "service_job_id",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                ("lane", models.CharField(blank=True, default="", max_length=10)),
                ("created", models.DateTimeField(auto_now_add=True)),
                (
                    "recording",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="turns",
                        to="core.recording",
                    ),
                ),
            ],
            options={"ordering": ["number"]},
        ),
    ]
