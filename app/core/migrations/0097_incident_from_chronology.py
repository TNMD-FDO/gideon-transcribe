# An incident made from the case's chronology (Phase 10 chapter 2, v1.167.0):
# where it came from, the span it covers now, and each addition from the
# chronology since. Empty on an incident made any other way.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0096_note_to_check"),
    ]

    operations = [
        migrations.AddField(
            model_name="incident",
            name="from_chronology",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
