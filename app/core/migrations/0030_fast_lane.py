"""The fast lane: a Run remembers which copy of the service holds it."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0029_dictation"),
    ]

    operations = [
        migrations.AddField(
            model_name="run",
            name="lane",
            field=models.CharField(blank=True, default="", max_length=10),
        ),
    ]
