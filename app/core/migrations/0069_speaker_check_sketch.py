# The Speaker check's sketch of who is who (v1.100.0): read once over the
# whole Transcript before the windows, kept on the run so the Speakers page
# can show it; and whether the Transcript was checked whole, in one window.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0068_moment_note"),
    ]

    operations = [
        migrations.AddField(
            model_name="speakercheck",
            name="sketch",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="speakercheck",
            name="whole",
            field=models.BooleanField(default=False),
        ),
    ]
