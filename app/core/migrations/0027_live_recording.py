# Live recording (Phase 3): the Recording's live facts and the Batch's mark.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0026_summary_template_types"),
    ]

    operations = [
        migrations.AddField(
            model_name="recording",
            name="live",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="batch",
            name="is_live",
            field=models.BooleanField(default=False),
        ),
    ]
