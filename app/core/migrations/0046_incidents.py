# Phase 6 chapter 1 (v1.58.0): Incidents.
#
# The camera stamp moves from the Transcript to the Recording, since the
# picture is the recording's and a Process again must not lose it; every
# stamp a Transcript holds is copied over first. Then the two Incident tables
# and the case's list of declined offers.

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def copy_stamps(apps, schema_editor):
    Transcript = apps.get_model("core", "Transcript")
    Recording = apps.get_model("core", "Recording")
    for transcript in Transcript.objects.exclude(stamp=None).iterator():
        Recording.objects.filter(pk=transcript.recording_id, stamp=None).update(
            stamp=transcript.stamp
        )


def copy_back(apps, schema_editor):
    Transcript = apps.get_model("core", "Transcript")
    Recording = apps.get_model("core", "Recording")
    for recording in Recording.objects.exclude(stamp=None).iterator():
        Transcript.objects.filter(recording_id=recording.pk).update(
            stamp=recording.stamp
        )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0045_speaker_check_cut_short"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="recording",
            name="stamp",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.RunPython(copy_stamps, copy_back),
        migrations.RemoveField(model_name="transcript", name="stamp"),
        migrations.AddField(
            model_name="case",
            name="declined_offers",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.CreateModel(
            name="Incident",
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
                ("name", models.CharField(max_length=200)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("how", models.CharField(default="hand", max_length=10)),
                ("clock_zero", models.FloatField(blank=True, null=True)),
                ("clock_date", models.CharField(blank=True, default="", max_length=40)),
                ("wall", models.JSONField(blank=True, default=list)),
                (
                    "case",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="incidents",
                        to="core.case",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["created"]},
        ),
        migrations.CreateModel(
            name="IncidentCamera",
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
                ("starts_at", models.FloatField(blank=True, null=True)),
                ("placed", models.CharField(blank=True, default="", max_length=20)),
                ("placed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "match_state",
                    models.CharField(blank=True, default="", max_length=10),
                ),
                ("match_lag", models.FloatField(blank=True, null=True)),
                ("match_strength", models.FloatField(blank=True, null=True)),
                (
                    "match_reason",
                    models.CharField(blank=True, default="", max_length=60),
                ),
                ("added", models.DateTimeField(auto_now_add=True)),
                (
                    "incident",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cameras",
                        to="core.incident",
                    ),
                ),
                (
                    "match_against",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="core.incidentcamera",
                    ),
                ),
                (
                    "placed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "recording",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="incident_cameras",
                        to="core.recording",
                    ),
                ),
            ],
            options={"ordering": ["added"]},
        ),
        migrations.AddConstraint(
            model_name="incidentcamera",
            constraint=models.UniqueConstraint(
                fields=("incident", "recording"), name="one_camera_per_recording"
            ),
        ),
    ]
