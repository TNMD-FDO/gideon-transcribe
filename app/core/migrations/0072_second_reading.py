# The second reading and the voice on a Speaker correction, what the second
# reading did on a Speaker check, and how the transcript backs a suggested
# name (v1.105.0). Everything already stored keeps its meaning: an empty
# `second` is a correction no second reading saw, an empty `basis` a
# suggestion made before the app said which way its evidence points.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0071_comparison_second_look"),
    ]

    operations = [
        migrations.AddField(
            model_name="suggestion",
            name="basis",
            field=models.CharField(blank=True, default="", max_length=12),
        ),
        migrations.AddField(
            model_name="speakercheck",
            name="second_look",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="speakercorrection",
            name="second",
            field=models.CharField(blank=True, default="", max_length=10),
        ),
        migrations.AddField(
            model_name="speakercorrection",
            name="aside_why",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="speakercorrection",
            name="voice",
            field=models.CharField(blank=True, default="", max_length=10),
        ),
    ]
