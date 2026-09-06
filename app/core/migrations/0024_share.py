# The Share table: one Case opened to one colleague (Phase 2, Sharing).

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0023_backup_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="Share",
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
                ("added_on", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_opened", models.DateTimeField(blank=True, null=True)),
                (
                    "added_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "case",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="shares",
                        to="core.case",
                    ),
                ),
                (
                    "person",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="shares",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["added_on"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("case", "person"),
                        name="one_share_per_person_per_case",
                    )
                ],
            },
        ),
    ]
