# Summary templates by Recording type: the shipped templates' key, and the
# types a template is for.

from django.db import migrations, models


def key_the_standard(apps, schema_editor):
    SummaryTemplate = apps.get_model("core", "SummaryTemplate")
    SummaryTemplate.objects.filter(built_in=True, key="").update(key="standard")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0025_mail"),
    ]

    operations = [
        migrations.AddField(
            model_name="summarytemplate",
            name="key",
            field=models.CharField(blank=True, default="", max_length=40),
        ),
        migrations.AddField(
            model_name="summarytemplate",
            name="recording_types",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(key_the_standard, migrations.RunPython.noop),
    ]
