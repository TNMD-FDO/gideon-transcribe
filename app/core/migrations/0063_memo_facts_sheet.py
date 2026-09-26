# The facts sheet the incident memo is written from (v1.91.0, ADR 0016):
# kept with the memo, with the app's checks, and whether it was cut at its
# cap. Memos written before this carry an empty sheet and read as before.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0062_note_events_own_camera"),
    ]

    operations = [
        migrations.AddField(
            model_name="incidentmemo",
            name="sheet",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="incidentmemo",
            name="sheet_cut_short",
            field=models.BooleanField(default=False),
        ),
    ]
