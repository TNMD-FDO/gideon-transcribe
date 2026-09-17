# Phase 6 chapter 3 (v1.61.0): the assistant on the Incident. The Propose
# events run's state on the Incident, a proposal's words and its dismissal
# on the Event, and the Incident memo.

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0047_events"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="incident",
            name="proposals_state",
            field=models.CharField(blank=True, default="", max_length=10),
        ),
        migrations.AddField(
            model_name="incident",
            name="proposals_reason",
            field=models.CharField(blank=True, default="", max_length=40),
        ),
        migrations.AddField(
            model_name="incident",
            name="proposals_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="incident",
            name="proposals_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="incident",
            name="proposals_found",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="incident",
            name="proposals_cameras",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="event",
            name="rests_on",
            field=models.CharField(blank=True, default="", max_length=500),
        ),
        migrations.AddField(
            model_name="event",
            name="dismissed",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="IncidentMemo",
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
                ("stage", models.CharField(blank=True, default="", max_length=60)),
                (
                    "reason_class",
                    models.CharField(blank=True, default="", max_length=40),
                ),
                ("text", models.TextField(blank=True, default="")),
                ("citations", models.JSONField(blank=True, default=dict)),
                ("event_numbers", models.JSONField(blank=True, default=dict)),
                ("cut_short", models.BooleanField(default=False)),
                ("model", models.CharField(blank=True, default="", max_length=120)),
                ("template_version", models.IntegerField(default=1)),
                ("ground_rules_version", models.IntegerField(default=1)),
                ("cameras_used", models.JSONField(blank=True, default=list)),
                (
                    "cameras_transcript_only",
                    models.JSONField(blank=True, default=list),
                ),
                ("cameras_not_read", models.JSONField(blank=True, default=list)),
                ("cameras_left_out", models.JSONField(blank=True, default=list)),
                ("events_count", models.IntegerField(default=0)),
                (
                    "events_signature",
                    models.CharField(blank=True, default="", max_length=32),
                ),
                (
                    "cameras_signature",
                    models.CharField(blank=True, default="", max_length=32),
                ),
                ("record_lines", models.IntegerField(default=0)),
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
                    "incident",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memo",
                        to="core.incident",
                    ),
                ),
            ],
        ),
    ]
