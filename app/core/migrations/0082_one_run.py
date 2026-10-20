# The voice plan's third release (ADR 0021, v1.140.0): a Person's Also
# called list, and the form a suggested name came through.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0081_voice_step"),
    ]

    operations = [
        migrations.AddField(
            model_name="person",
            name="also_called",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="suggestion",
            name="form",
            field=models.CharField(blank=True, default="", max_length=60),
        ),
    ]
