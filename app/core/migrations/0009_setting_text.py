"""Settings that are words rather than numbers.

The notices, the Office Vocabulary, and the engine's address are text, so a
setting now holds either a number or text, and which one it holds is decided
by the setting's own kind rather than by the row.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0008_recording_discarding")]

    operations = [
        migrations.AddField(
            model_name="setting",
            name="text",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="setting",
            name="value",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
