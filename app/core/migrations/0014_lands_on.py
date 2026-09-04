"""Which of the two front pages a person actually works on.

Empty until they open one, so the specified landing page stands for everybody
who has not shown otherwise, and nothing changes for an office that works in
Cases.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0013_both_sides")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="lands_on",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
    ]
