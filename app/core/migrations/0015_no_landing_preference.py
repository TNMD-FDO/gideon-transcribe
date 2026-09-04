"""The landing preference goes: everybody lands on the Upload page.

It was added this morning, when the choice was between Cases and Recordings
and the point was to stop a batch office paying for a page it never opens.
The answer turned out to be neither: signing in opens Upload, which is what
everybody came to do, so there is nothing left to remember.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("core", "0014_lands_on")]

    operations = [
        migrations.RemoveField(model_name="user", name="lands_on"),
    ]
