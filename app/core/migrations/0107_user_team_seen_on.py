# Home as the desk (Phase 13 chapter 1, v1.215.0): when the person last
# pressed Seen on Your team, lately, so the section stays folded until
# something newer happens. One nullable column; the reverse drops it.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0106_place_from_paths_catch_up")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="team_seen_on",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
