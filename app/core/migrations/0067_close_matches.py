# Close matches (v1.97.0): Find and Search also look for a word's near
# spellings, by the trigram similarity of pg_trgm. The extension ships in
# the database image and is trusted, so the app's own database user adds
# it. No index: a search of every line takes under a tenth of a second
# (docs/research/close-matches.md).
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0066_look_for_run"),
    ]

    operations = [
        migrations.RunSQL(
            "CREATE EXTENSION IF NOT EXISTS pg_trgm",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
