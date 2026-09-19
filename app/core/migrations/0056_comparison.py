# Phase 8 chapter 4, part 3 (v1.73.0): the comparison, a report against the
# record, kept on its home with its findings.

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0055_document_read_version"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Comparison",
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
                ("state", models.CharField(default="queued", max_length=10)),
                ("stage", models.CharField(blank=True, default="", max_length=80)),
                (
                    "reason_class",
                    models.CharField(blank=True, default="", max_length=40),
                ),
                ("findings", models.JSONField(blank=True, default=list)),
                ("windows", models.IntegerField(default=0)),
                ("cut_short", models.IntegerField(default=0)),
                ("left_out_check", models.BooleanField(default=False)),
                ("model", models.CharField(blank=True, default="", max_length=120)),
                ("template_version", models.IntegerField(default=1)),
                ("ground_rules_version", models.IntegerField(default=1)),
                ("cameras_used", models.JSONField(blank=True, default=list)),
                ("record_lines", models.IntegerField(default=0)),
                (
                    "events_signature",
                    models.CharField(blank=True, default="", max_length=32),
                ),
                (
                    "cameras_signature",
                    models.CharField(blank=True, default="", max_length=32),
                ),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("written_at", models.DateTimeField(blank=True, null=True)),
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
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comparisons",
                        to="core.document",
                    ),
                ),
                (
                    "incident",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comparisons",
                        to="core.incident",
                    ),
                ),
                (
                    "recording",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comparisons",
                        to="core.recording",
                    ),
                ),
            ],
            options={
                "ordering": ["-created"],
            },
        ),
    ]
