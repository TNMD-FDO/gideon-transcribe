# Phase 8 chapter 10, the sitting on the case page: each camera's share of
# the Sitting kept on the camera, so a case page draws the bar without
# reading a Digest.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0058_one_sitting"),
    ]

    operations = [
        migrations.AddField(
            model_name="incidentcamera",
            name="record_tokens",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="incidentcamera",
            name="words_tokens",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="incidentcamera",
            name="record_made_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
