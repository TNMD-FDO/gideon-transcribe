# Phase 7 chapter 5 (v1.67.0): Gideon on the incident page. A conversation
# may belong to an Incident, grounded in the incident record.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0050_watch_phrases"),
    ]

    operations = [
        migrations.AddField(
            model_name="casechat",
            name="incident",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="chats",
                to="core.incident",
            ),
        ),
    ]
