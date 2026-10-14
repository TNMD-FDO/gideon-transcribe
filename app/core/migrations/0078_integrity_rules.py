"""The data integrity pass's rules (v1.131.0).

A Segment's side link is set null rather than cascading, so a Side deletion
can never empty a Transcript again (Retry after a failed Process again had).
A Run counts the polls at which the service did not list it. And two rules
the code had kept by a check alone become the database's: one live
transcription Job per recording, one live Speaker check per transcript.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0077_chat_turn_asked_by"),
    ]

    operations = [
        migrations.AddField(
            model_name="run",
            name="missing_polls",
            field=models.IntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="segment",
            name="side",
            field=models.ForeignKey(
                null=True, on_delete=django.db.models.deletion.SET_NULL, to="core.side"
            ),
        ),
        migrations.AddConstraint(
            model_name="job",
            constraint=models.UniqueConstraint(
                condition=models.Q(("kind", ""), ("state__in", ("queued", "running"))),
                fields=("recording",),
                name="one_live_job_per_recording",
            ),
        ),
        migrations.AddConstraint(
            model_name="speakercheck",
            constraint=models.UniqueConstraint(
                condition=models.Q(("state__in", ("queued", "running"))),
                fields=("transcript",),
                name="one_live_check_per_transcript",
            ),
        ),
    ]
