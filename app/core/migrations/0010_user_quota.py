"""A per-person Workspace quota, set from the Users page.

Empty means the default setting, whatever it is at the time, so raising the
default raises it for everybody who has no figure of their own.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0009_setting_text")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="quota_gb",
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
