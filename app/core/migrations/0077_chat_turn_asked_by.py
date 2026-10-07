# v1.126.0: who asked each turn of a case chat.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0076_phase_9_reads_what_fits"),
    ]

    operations = [
        migrations.AddField(
            model_name="casechatturn",
            name="asked_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="core.user",
            ),
        ),
    ]
