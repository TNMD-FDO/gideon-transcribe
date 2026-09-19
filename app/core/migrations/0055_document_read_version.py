# Phase 8 chapter 4, part 2 (v1.72.0): a Document remembers which reading
# split it, so a document read before a splitter change is read again.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0054_documents"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="read_version",
            field=models.IntegerField(default=0),
        ),
    ]
