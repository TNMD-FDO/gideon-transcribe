# The Look for run (v1.96.0): a run with Look for filled in proposes only
# what was looked for and leaves the waiting proposals alone. The Incident
# keeps whether its last run was one, and when its last full run ended; that
# time starts as the last run's, since every run before this was a full one.
from django.db import migrations, models
from django.db.models import F


def fill(apps, schema_editor):
    Incident = apps.get_model("core", "Incident")
    Incident.objects.filter(proposals_at__isnull=False).update(
        proposals_full_at=F("proposals_at")
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0065_expectation"),
    ]

    operations = [
        migrations.AddField(
            model_name="incident",
            name="proposals_looked",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="incident",
            name="proposals_full_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(fill, migrations.RunPython.noop),
    ]
