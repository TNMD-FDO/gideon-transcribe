"""The video summary: a Summary remembers how many Moments it drew on."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0038_intervals"),
    ]

    operations = [
        migrations.AddField(
            model_name="summary",
            name="moments_used",
            field=models.IntegerField(default=0),
        ),
    ]
