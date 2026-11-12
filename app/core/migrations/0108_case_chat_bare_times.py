# The catch-up of v1.233.0: a case chat's answer gives a bare time its
# recording from the lines above it now, not only from its own line, and the
# answers saved before that are read again once, so the times that stood as
# plain text under a sentence that named their recording become references.
# Only the brackets change; no other word of an answer is touched. No schema
# change; the reverse does nothing, since the full shape is what a new answer
# is saved with.

from django.db import migrations


def mend(apps, schema_editor):
    # The app's own code, with the live models: this is the last migration,
    # so the tables are as the code expects. A failure in one answer is
    # logged and the rest go on; the migration never fails the upgrade.
    try:
        from core import case_chat

        case_chat.mend_bare_times()
    except Exception:  # noqa: BLE001 - the catch-up is a courtesy, not the schema
        import logging

        logging.getLogger(__name__).exception("the case chat catch-up did not finish")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0107_user_team_seen_on"),
    ]

    operations = [
        migrations.RunPython(mend, migrations.RunPython.noop),
    ]
