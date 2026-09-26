# The time expectation a written output is given at the ask (v1.95.0): the
# size it was measured at, the office's figure, and when it was asked for
# and started, kept on each run so the page shows a stable figure and a
# live count. Runs made before this carry an empty one and draw their step
# alone.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0064_job_kind"),
    ]

    operations = [
        migrations.AddField(
            model_name="incidentmemo",
            name="expectation",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="summary",
            name="expectation",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="chatturn",
            name="expectation",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="casechatturn",
            name="expectation",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="comparison",
            name="expectation",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="incident",
            name="proposals_expectation",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
