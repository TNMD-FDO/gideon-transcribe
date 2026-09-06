# Live recording (Phase 3, step three): the speaker taps and the Marks.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0027_live_recording"),
    ]

    operations = [
        migrations.AddField(
            model_name="recording",
            name="speaker_taps",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="recording",
            name="marks",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
