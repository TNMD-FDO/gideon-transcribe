# The Transcription notice's shipped wording changes at v1.248.0 (it says the
# transcript may contain errors and to confirm it against the recording, and
# names the model that wrote the words truly). A setting is stored only once
# somebody saves it, so most offices take the new wording as it ships. This
# is for the office whose Notices page was saved with the old shipped words
# in the box: that row is the old default, not an edit, and it is removed so
# the new wording is theirs too. A wording an office wrote for itself is not
# the old default and is left exactly as it is. No schema change; the reverse
# does nothing.

from django.db import migrations

SHIPPED_UNTIL_NOW = (
    "Automatic transcription by Whisper {model}. Corrections made by staff are "
    "marked. This is not a certified transcript."
)


def forget_the_old_default(apps, schema_editor):
    Setting = apps.get_model("core", "Setting")
    for stored in Setting.objects.filter(key="transcription_notice"):
        if " ".join((stored.text or "").split()) == SHIPPED_UNTIL_NOW:
            stored.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0115_preservation_owners"),
    ]

    operations = [
        migrations.RunPython(forget_the_old_default, migrations.RunPython.noop),
    ]
