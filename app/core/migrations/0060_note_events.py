# Phase 8 chapter 11, a note is an event: an Event may be the note on a line
# of a synced camera's transcript (its `segment`), one per line per Incident;
# the text column holds a note's length. The rows for the notes already
# written are made here, at the lines' moments on each Incident's clock.

from django.db import migrations, models
from django.db.models import Q

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
        ("core", "0059_camera_shares"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="segment",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name="events",
                to="core.segment",
            ),
        ),
        migrations.AlterField(
            model_name="event",
            name="text",
            field=models.CharField(max_length=2000),
        ),
        migrations.AddConstraint(
            model_name="event",
            constraint=models.UniqueConstraint(
                condition=Q(segment__isnull=False),
                fields=("incident", "segment"),
                name="one_note_event_per_line",
            ),
        ),
        migrations.RunPython(make_note_events, unmake_note_events),
    ]
