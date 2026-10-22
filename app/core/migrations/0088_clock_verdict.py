# The clock verdict (ADR 0022, v1.151.0): each line's verdict on its own
# clock, None when the audio agrees with it, else the bound, where the sound
# is and the block it belongs to.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0087_units_by_hand"),
    ]

    operations = [
        migrations.AddField(
            model_name="segment",
            name="clock",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
