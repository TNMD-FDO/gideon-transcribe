# Usage (Phase 13 chapter 3, v1.239.0): one row a month of numbers, and the
# marks for the parts of the app that write no audit row. The first count is
# made here, so the Panel's Usage page has figures on the day of the upgrade:
# every month the server still holds anything of, counted once from what it
# holds. A server with nothing transcribed yet has nothing to count.

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def first_count(apps, schema_editor):
    # The app's own code, with the live models. Inside a savepoint, so a
    # failure is logged and undone and the migration never fails the upgrade:
    # the nightly count makes the first count instead.
    try:
        from django.db import transaction

        from core import usage
        from core.jobs import Job

        if not Job.objects.exists():
            return
        with transaction.atomic():
            usage.tally()
    except Exception:  # noqa: BLE001 - the first count is a courtesy, not the schema
        import logging

        logging.getLogger(__name__).exception("the first usage count did not finish")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0109_paths_signature"),
    ]

    operations = [
        migrations.CreateModel(
            name="UsageMonth",
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
                ("month", models.DateField(unique=True)),
                ("counts", models.JSONField(default=dict)),
                (
                    "first_counted",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
                (
                    "counted_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
            ],
            options={
                "ordering": ["month"],
            },
        ),
        migrations.CreateModel(
            name="UsageMark",
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
                ("month", models.DateField()),
                ("part", models.CharField(max_length=20)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("month", "part", "user"),
                        name="usage_mark_once_a_month",
                    )
                ],
            },
        ),
        migrations.RunPython(first_count, migrations.RunPython.noop),
    ]
