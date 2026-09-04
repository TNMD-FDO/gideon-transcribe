"""The engine's own label for a voice, kept beside the name a person reads.

An export's Appearances table prints both, and renaming a Speaker must not
lose the label the Provenance refers to.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0006_segment_corrected")]

    operations = [
        migrations.AddField(
            model_name="segment",
            name="speaker_label",
            field=models.CharField(blank=True, default="", max_length=60),
        ),
    ]
