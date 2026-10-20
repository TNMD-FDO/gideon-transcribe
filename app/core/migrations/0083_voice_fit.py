# The speaker picker's release (v1.142.0): each line's closeness to its
# speaker's voice print, so the samples are the lines the recording itself
# agrees are that voice.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0082_one_run"),
    ]

    operations = [
        migrations.AddField(
            model_name="segment",
            name="voice_fit",
            field=models.FloatField(blank=True, null=True),
        ),
    ]
