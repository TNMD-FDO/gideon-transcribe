# Phase 8 chapter 2 (v1.69.0): a note on a line of a transcript, under the
# rules an Event's note already has: the words, who wrote it, when it changed.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0051_incident_chat"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="segment",
            name="note",
            field=models.TextField(blank=True, default="", max_length=2000),
        ),
        migrations.AddField(
            model_name="segment",
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
            model_name="segment",
            name="note_changed",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
