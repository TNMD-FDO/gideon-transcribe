# Whether an Incident's clock came from a checked stamp (v1.101.1). Until
# now only a checked stamp could set the clock, so cameras with unchecked
# readings all started together; the first unchecked one now sets it, said
# to be unchecked until a checked reading that agrees with it arrives. Every
# clock set before this came from a checked stamp.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0069_speaker_check_sketch"),
    ]

    operations = [
        migrations.AddField(
            model_name="incident",
            name="clock_checked",
            field=models.BooleanField(default=True),
        ),
    ]
