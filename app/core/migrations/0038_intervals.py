"""Describe at intervals: the run counts its Moments; a Summary may ask for it first."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0037_cues"),
    ]

    operations = [
        migrations.AddField(
            model_name="cuerun",
            name="total",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="summary",
            name="describe_first",
            field=models.BooleanField(default=False),
        ),
    ]
