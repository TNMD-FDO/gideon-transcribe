# Phase 8 chapter 9, One sitting: the window the engine reports, kept with the
# minute check; a camera pinned into the Sitting; which cameras a memo or a
# comparison read by their words alone.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0057_comparison_unreadable_dropped"),
    ]

    operations = [
        migrations.AddField(
            model_name="enginestatus",
            name="window_tokens",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="incidentcamera",
            name="pinned",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="incidentmemo",
            name="cameras_words_alone",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="comparison",
            name="cameras_words_alone",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
