# Phase 6 chapter 2 (v1.59.0): the Chronology's Events.

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0046_incidents"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Event",
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
                ("until", models.FloatField(blank=True, null=True)),
                ("text", models.CharField(max_length=500)),
                ("source", models.CharField(default="person", max_length=10)),
                ("cameras", models.JSONField(blank=True, default=list)),
                ("proposed", models.BooleanField(default=False)),
                ("added", models.DateTimeField(auto_now_add=True)),
                ("changed", models.DateTimeField(blank=True, null=True)),
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
                    "camera",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="events",
                        to="core.incidentcamera",
                    ),
                ),
                (
                    "changed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "incident",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to="core.incident",
                    ),
                ),
            ],
            options={"ordering": ["at", "added"]},
        ),
    ]
