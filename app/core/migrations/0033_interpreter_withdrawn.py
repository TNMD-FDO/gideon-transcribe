"""The Interpreter withdrawn (v1.35.0): its Turns and the two Segment fields go.

Migration 0032 stays in the history so a server that applied it is in step;
this one takes back what it added. A Session recorded under v1.33.0 to
v1.34.0 keeps its Recording and its Transcript; only the translations under
the Segments and the Turn rows are dropped.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0032_interpreter"),
    ]

    operations = [
        migrations.DeleteModel(name="Turn"),
        migrations.RemoveField(model_name="segment", name="language"),
        migrations.RemoveField(model_name="segment", name="translation"),
    ]
