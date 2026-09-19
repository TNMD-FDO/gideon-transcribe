# Phase 7 chapter 2 (v1.64.0): the assistant's judgement, and the watch
# phrases under it. The why line on an Event, and on the Incident what the
# last run cut, what the watch phrases found and the Look for it was given.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0049_incident_clips"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="why",
            field=models.CharField(blank=True, default="", max_length=300),
        ),
        migrations.AddField(
            model_name="incident",
            name="proposals_cut",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="incident",
            name="proposals_watch",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="incident",
            name="proposals_look_for",
            field=models.CharField(blank=True, default="", max_length=300),
        ),
    ]
