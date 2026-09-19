# Phase 8 chapter 4, part 1 (v1.71.0): Documents beside the cameras. A PDF
# added to an Incident or a Recording, read page by page.

import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0053_reports"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Document",
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
                ("title", models.CharField(max_length=200)),
                ("original_filename", models.CharField(max_length=300)),
                ("size_bytes", models.BigIntegerField(default=0)),
                ("pages", models.IntegerField(default=0)),
                ("ocr_pages", models.IntegerField(default=0)),
                ("poor_pages", models.IntegerField(default=0)),
                ("state", models.CharField(default="reading", max_length=10)),
                ("error", models.CharField(blank=True, default="", max_length=300)),
                ("created", models.DateTimeField(default=django.utils.timezone.now)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                (
                    "added_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "case",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to="core.case",
                    ),
                ),
                (
                    "incident",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="documents",
                        to="core.incident",
                    ),
                ),
                (
                    "recording",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="documents",
                        to="core.recording",
                    ),
                ),
            ],
            options={
                "ordering": ["-created"],
            },
        ),
        migrations.CreateModel(
            name="DocumentPage",
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
                ("number", models.IntegerField()),
                ("width", models.FloatField(default=612.0)),
                ("height", models.FloatField(default=792.0)),
                ("text", models.TextField(blank=True, default="")),
                ("paragraphs", models.JSONField(blank=True, default=list)),
                ("ocr", models.BooleanField(default=False)),
                ("poor", models.BooleanField(default=False)),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="page_rows",
                        to="core.document",
                    ),
                ),
            ],
            options={
                "ordering": ["document", "number"],
                "unique_together": {("document", "number")},
            },
        ),
    ]
