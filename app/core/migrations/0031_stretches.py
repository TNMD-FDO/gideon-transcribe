"""Stretches: a Live recording transcribed while it records (Phase 3, step five)."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0030_fast_lane"),
    ]

    operations = [
        migrations.AddField(
            model_name="job",
            name="open",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="run",
            name="stretch",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="run",
            name="offset_seconds",
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name="run",
            name="seconds",
            field=models.FloatField(default=0.0),
        ),
    ]
