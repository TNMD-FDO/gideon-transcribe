"""A Moment may answer a question about the picture (Phase 4, v1.39.0)."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0035_moments"),
    ]

    operations = [
        migrations.AddField(
            model_name="moment",
            name="question",
            field=models.TextField(blank=True, default=""),
        ),
    ]
