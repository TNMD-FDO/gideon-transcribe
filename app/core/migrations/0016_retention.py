"""The Retention policy's one new column: the day a Case was first warned.

The retention sweep writes one "retention warning" row the night a Case first
comes inside its warning window, and this is how it knows it already has. Any
activity clears it, so the next approach to the edge is warned about afresh.
The other columns the policy needs, last_activity and deleted_on, were carried
from the first Cases migration, waiting for this chapter.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0015_no_landing_preference")]

    operations = [
        migrations.AddField(
            model_name="case",
            name="warned_on",
            field=models.DateField(blank=True, null=True),
        ),
    ]
