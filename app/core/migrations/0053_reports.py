# Phase 8 chapter 3 (v1.70.0): Report a problem. A person's own account of a
# problem or an idea, kept for the Admins with where they were.

import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0052_line_notes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Report",
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
                ("kind", models.CharField(default="problem", max_length=10)),
                ("happened", models.TextField(max_length=4000)),
                ("expected", models.TextField(blank=True, default="", max_length=4000)),
                ("page", models.CharField(blank=True, default="", max_length=300)),
                ("release", models.CharField(blank=True, default="", max_length=60)),
                ("browser", models.CharField(blank=True, default="", max_length=80)),
                ("window", models.CharField(blank=True, default="", max_length=30)),
                (
                    "sent_by_name",
                    models.CharField(blank=True, default="", max_length=150),
                ),
                ("made", models.DateTimeField(default=django.utils.timezone.now)),
                ("state", models.CharField(default="new", max_length=8)),
                ("marked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "marked_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "sent_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-made"],
            },
        ),
    ]
