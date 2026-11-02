# The sound match's surety (v1.183.0): clear, likely or unclear, kept on
# the camera beside the match's lag and strength.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0100_comparison_case_home"),
    ]

    operations = [
        migrations.AddField(
            model_name="incidentcamera",
            name="match_surety",
            field=models.CharField(blank=True, default="", max_length=10),
        ),
    ]
