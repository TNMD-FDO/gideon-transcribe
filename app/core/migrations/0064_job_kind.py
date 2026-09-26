# A Job's kind (v1.94.0): "" for a transcription, "speakers" for the pass
# over a whole Live recording that matches the speakers across its
# stretches once it has ended. Jobs made before this are transcriptions.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0063_memo_facts_sheet"),
    ]

    operations = [
        migrations.AddField(
            model_name="job",
            name="kind",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
    ]
