"""The robustness pass's two counters (v1.132.0).

A Recording counts how many times the minute sweep asked for its playback
copy again after the first making died, three at most. The backup status
remembers when the app first watched it, so a timer that never fires is
reported a day later rather than staying "no snapshot yet" for ever.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0078_integrity_rules"),
    ]

    operations = [
        migrations.AddField(
            model_name="backupstatus",
            name="watched_since",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="recording",
            name="playback_tries",
            field=models.IntegerField(default=0),
        ),
    ]
