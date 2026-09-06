# Dictation (Phase 3): the Recording's mark and clock, and the DictationShare.

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0028_taps_and_marks"),
    ]

    operations = [
        migrations.AddField(
            model_name="recording",
            name="is_dictation",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="recording",
            name="last_used",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="DictationShare",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("sent_on", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_opened", models.DateTimeField(blank=True, null=True)),
                ("attached", models.BooleanField(default=False)),
                (
                    "person",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dictations_received",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "recording",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dictation_shares",
                        to="core.recording",
                    ),
                ),
                (
                    "sent_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["sent_on"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("recording", "person"),
                        name="one_dictation_share_per_person",
                    )
                ],
            },
        ),
    ]
