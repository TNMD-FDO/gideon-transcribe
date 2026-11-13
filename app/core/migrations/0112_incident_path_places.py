# The catch-up of v1.240.0: an incident camera the app had only guessed at,
# whose path file carries a clock of its own (an in-car unit's), takes that
# clock now, once. Until this release an incident never read a path file's
# clock, so such a video stood at the incident's start, "Not synced yet",
# while the case's clock had it right. Nothing a person chose, nothing read
# from the picture and nothing matched by sound is touched. No schema change;
# the reverse does nothing, since a placement is a row like any other and
# stands.

from django.db import migrations, transaction


def place_from_paths(apps, schema_editor):
    # The app's own code, with the live models: this is the last migration,
    # so the tables are as the code expects. Inside a savepoint, and a
    # failure is logged: the catch-up never fails the upgrade.
    try:
        from core import incidents

        with transaction.atomic():
            incidents.catch_up_path_places()
    except Exception:  # noqa: BLE001 - the catch-up is a courtesy, not the schema
        import logging

        logging.getLogger(__name__).exception(
            "the incidents' path-file catch-up did not finish"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0111_usage_recount"),
    ]

    operations = [
        migrations.RunPython(place_from_paths, migrations.RunPython.noop),
    ]
