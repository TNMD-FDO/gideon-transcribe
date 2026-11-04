# The catch-up of Phase 12 chapter 6 (v1.197.0): a camera whose path file
# can place it on the case's clock and which nothing has placed takes its
# clock now, once. The files added before a path file could place anything
# (v1.188.0) had stood as not on the clock; the body cameras the name's
# minute now places join them. Nothing a person chose is touched. No schema
# change; the reverse does nothing, since a placement is a row like any
# other and stands.

from django.db import migrations


def place_from_paths(apps, schema_editor):
    # The app's own code, with the live models: this is the last migration,
    # so the tables are as the code expects. A failure in one file is logged
    # and the rest go on; the migration never fails the upgrade.
    try:
        from core import camera_paths

        camera_paths.catch_up_placements()
    except Exception:  # noqa: BLE001 - the catch-up is a courtesy, not the schema
        import logging

        logging.getLogger(__name__).exception("the path-file catch-up did not finish")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0105_waiting_path_file"),
    ]

    operations = [
        migrations.RunPython(place_from_paths, migrations.RunPython.noop),
    ]
