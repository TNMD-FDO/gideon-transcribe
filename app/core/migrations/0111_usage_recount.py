# The catch-up of v1.239.1: the months counted by v1.239.0 are counted again
# once for two figures it got wrong. The AI assistant's calls put Vision's
# own work (a call for every span described, every part of a Digest and
# every camera clock read) under Other, where it swamped what people asked
# for; and the wait began at the Job's making, which is after the file had
# arrived and been prepared. No schema change; the reverse does nothing.

from django.db import migrations


def recount(apps, schema_editor):
    # The app's own code, with the live models, inside a savepoint: a failure
    # is logged and undone and never fails the upgrade. The nightly count
    # then mends this month and last by itself.
    try:
        from django.db import transaction

        from core import usage

        if not usage.UsageMonth.objects.exists():
            return
        with transaction.atomic():
            usage.recount()
    except Exception:  # noqa: BLE001 - the catch-up is a courtesy, not the schema
        import logging

        logging.getLogger(__name__).exception("the usage recount did not finish")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0110_usage"),
    ]

    operations = [
        migrations.RunPython(recount, migrations.RunPython.noop),
    ]
