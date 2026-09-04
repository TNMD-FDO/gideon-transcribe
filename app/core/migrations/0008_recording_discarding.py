"""The mark the Discard leaves on a Recording before it removes it.

A crash half way through a Discard leaves the mark rather than a half-removed
Recording, and the next minute's run finishes what it started.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0007_segment_speaker_label")]

    operations = [
        migrations.AddField(
            model_name="recording",
            name="discarding_since",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
