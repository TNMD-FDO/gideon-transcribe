# Phase 8 chapter 11: the note events for the notes already written on the
# lines of synced cameras, at the lines' moments on each Incident's clock.
# Kept apart from 0060, which adds the column and the index: PostgreSQL
# refuses to build an index while rows written in the same transaction still
# have their foreign-key checks pending ("cannot CREATE INDEX because it has
# pending trigger events"), which is how v1.81.0's upgrade failed.

from django.db import migrations

SYNCED = ("clock", "clock_unchecked", "sound", "file", "hand")


def make_note_events(apps, schema_editor):
    IncidentCamera = apps.get_model("core", "IncidentCamera")
    Segment = apps.get_model("core", "Segment")
    Event = apps.get_model("core", "Event")
    cameras = list(
        IncidentCamera.objects.filter(
            starts_at__isnull=False, placed__in=SYNCED
        ).select_related("recording", "incident")
    )
    for camera in cameras:
        placed = [
            one
            for one in IncidentCamera.objects.filter(incident=camera.incident)
            if one.starts_at is not None and one.placed
        ]
        noted = Segment.objects.filter(
            transcript__recording=camera.recording, same_as_other_side=False
        ).exclude(note="")
        for segment in noted:
            at = camera.starts_at + segment.start
            if Event.objects.filter(incident=camera.incident, segment=segment).exists():
                continue
            running = [
                str(one.pk)
                for one in placed
                if one.starts_at
                <= at
                <= one.starts_at + float(one.recording.duration_seconds or 0.0)
            ]
            Event.objects.create(
                incident=camera.incident,
                segment=segment,
                at=at,
                text=segment.note,
                source="note",
                camera=camera,
                cameras=running,
                added_by=segment.note_by,
            )


def unmake_note_events(apps, schema_editor):
    Event = apps.get_model("core", "Event")
    Event.objects.filter(source="note").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0060_note_events"),
    ]

    operations = [
        migrations.RunPython(make_note_events, unmake_note_events),
    ]
