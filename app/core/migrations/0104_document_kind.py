# A Document's kind (Phase 12 chapter 5): the police report as a PDF, or a
# picture of the map saved from the page. Every row so far is a report.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0103_camera_path"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="kind",
            field=models.CharField(default="report", max_length=10),
        ),
    ]
