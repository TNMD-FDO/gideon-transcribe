# v1.74.2: a comparison keeps how many answers could not be read and what
# it dropped by reason, so an empty comparison says why.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0056_comparison"),
    ]

    operations = [
        migrations.AddField(
            model_name="comparison",
            name="unreadable",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="comparison",
            name="dropped",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
