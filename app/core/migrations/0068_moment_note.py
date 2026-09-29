# A note where nothing was said (v1.99.0): a note written at a moment of a
# recording when no line is being spoken is kept at the moment itself, and
# is an Event on the Chronology of a synced camera at that exact moment.
# Until now such a note was put on the nearest line, which could be a
# minute or more from what was noted.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0067_close_matches"),
    ]

    operations = [
        migrations.CreateModel(
            name="MomentNote",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("at", models.FloatField()),
                ("note", models.TextField(max_length=2000)),
                ("note_changed", models.DateTimeField(blank=True, null=True)),
                ("created", models.DateTimeField(auto_now_add=True)),
                (
                    "note_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "recording",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="moment_notes",
                        to="core.recording",
                    ),
                ),
            ],
            options={
                "ordering": ["at", "id"],
            },
        ),
        migrations.AddField(
            model_name="event",
            name="moment_note",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="events",
                to="core.momentnote",
            ),
        ),
        migrations.AddConstraint(
            model_name="event",
            constraint=models.UniqueConstraint(
                condition=models.Q(("moment_note__isnull", False)),
                fields=("incident", "moment_note"),
                name="one_note_event_per_moment",
            ),
        ),
    ]
