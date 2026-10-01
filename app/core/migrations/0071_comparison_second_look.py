# What the check against the record's lines did to a Comparison (v1.104.0):
# how many Agrees and Differs rows it read, moved to not on camera, dropped,
# left because its two readings differed, or could not read. Empty on every
# comparison written before the check, and the page says nothing of it then.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0070_incident_clock_checked"),
    ]

    operations = [
        migrations.AddField(
            model_name="comparison",
            name="second_look",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
