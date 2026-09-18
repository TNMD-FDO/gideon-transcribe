# Phase 7 chapter 1 (v1.63.0): the chronology as a document, and the clip
# across cameras. A Note with its writer and a To check mark on the Event,
# About on the Incident, and on the Clip the Incident, the Event and the
# picture that make it an Incident clip.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0048_incident_assistant"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="clip",
            name="event",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="clips",
                to="core.event",
            ),
        ),
        migrations.AddField(
            model_name="clip",
            name="incident",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="clips",
                to="core.incident",
            ),
        ),
        migrations.AddField(
            model_name="clip",
            name="picture",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="event",
            name="note",
            field=models.TextField(blank=True, default="", max_length=2000),
        ),
        migrations.AddField(
            model_name="event",
            name="note_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="event",
            name="note_changed",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="event",
            name="to_check",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="incident",
            name="about",
            field=models.TextField(blank=True, default="", max_length=2000),
        ),
    ]
