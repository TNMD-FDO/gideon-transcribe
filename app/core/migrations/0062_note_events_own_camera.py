# v1.85.2: a note event is seen on its own camera alone. The rows made by
# 0061 and by the app since v1.81.0 carried every camera running at the
# note's moment, which read on the Event card as if the note were on each
# camera. Every note event's cameras become its own camera; a person may
# add others afterwards, as for any event.

from django.db import migrations


def own_camera(apps, schema_editor):
    Event = apps.get_model("core", "Event")
    for event in Event.objects.filter(source="note", camera__isnull=False):
        wanted = [str(event.camera_id)]
        if event.cameras != wanted:
            event.cameras = wanted
            event.save(update_fields=["cameras"])


def nothing(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0061_note_events_made"),
    ]

    operations = [
        migrations.RunPython(own_camera, nothing),
    ]
