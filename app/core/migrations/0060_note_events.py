# Phase 8 chapter 11, a note is an event: an Event may be the note on a line
# of a synced camera's transcript (its `segment`), one per line per Incident;
# the text column holds a note's length. The rows for the notes already
# written are made in 0061, a migration of its own: PostgreSQL will not build
# this migration's index over rows written in the same transaction (v1.81.1).

from django.db import migrations, models
from django.db.models import Q


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
    ]
