"""A Transcript remembers its speaker renames and merges, so the last can be undone."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0033_interpreter_withdrawn"),
    ]

    operations = [
        migrations.AddField(
            model_name="transcript",
            name="speaker_changes",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
