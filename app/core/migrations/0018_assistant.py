"""The AI assistant's tables: the prompt and Summary templates an Admin edits,
and what the three features store, Summaries, Chats and their turns, and
Speaker suggestions with the runs that made them. A Summary or Chat lives as
long as its Recording; a suggestion as long as its Transcript.
"""

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0017_engine_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="PromptTemplate",
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
                ("key", models.CharField(max_length=30, unique=True)),
                ("text", models.TextField()),
                ("version", models.IntegerField(default=1)),
                ("updated", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="SummaryTemplate",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=80)),
                (
                    "description",
                    models.CharField(blank=True, default="", max_length=200),
                ),
                ("text", models.TextField()),
                ("version", models.IntegerField(default=1)),
                ("enabled", models.BooleanField(default=True)),
                ("is_default", models.BooleanField(default=False)),
                ("built_in", models.BooleanField(default=False)),
                ("created", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-built_in", "name"],
            },
        ),
        migrations.CreateModel(
            name="Chat",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(blank=True, default="", max_length=80)),
                ("created", models.DateTimeField(auto_now_add=True)),
                (
                    "asked_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "recording",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="chats",
                        to="core.recording",
                    ),
                ),
            ],
            options={
                "ordering": ["-created"],
            },
        ),
        migrations.CreateModel(
            name="ChatTurn",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("number", models.IntegerField()),
                ("question", models.TextField()),
                ("answer", models.TextField(blank=True, default="")),
                ("citations", models.JSONField(blank=True, default=dict)),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("queued", "queued"),
                            ("running", "running"),
                            ("done", "done"),
                            ("failed", "failed"),
                        ],
                        default="queued",
                        max_length=10,
                    ),
                ),
                (
                    "reason_class",
                    models.CharField(blank=True, default="", max_length=40),
                ),
                ("cut_short", models.BooleanField(default=False)),
                ("model", models.CharField(blank=True, default="", max_length=120)),
                ("transcript_created", models.DateTimeField(blank=True, null=True)),
                ("asked_at", models.DateTimeField(auto_now_add=True)),
                ("answered_at", models.DateTimeField(blank=True, null=True)),
                (
                    "chat",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="turns",
                        to="core.chat",
                    ),
                ),
            ],
            options={
                "ordering": ["number"],
            },
        ),
        migrations.CreateModel(
            name="Suggestion",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("speaker", models.CharField(max_length=60)),
                ("name", models.CharField(max_length=60)),
                ("kind", models.CharField(default="name", max_length=10)),
                ("confidence", models.CharField(default="medium", max_length=10)),
                ("line", models.IntegerField(default=0)),
                ("start", models.FloatField(default=0.0)),
                ("quote", models.CharField(blank=True, default="", max_length=300)),
                ("state", models.CharField(default="pending", max_length=10)),
                ("created", models.DateTimeField(auto_now_add=True)),
                (
                    "segment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="core.segment",
                    ),
                ),
                (
                    "transcript",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="suggestions",
                        to="core.transcript",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="SuggestionRun",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("queued", "queued"),
                            ("running", "running"),
                            ("done", "done"),
                            ("failed", "failed"),
                        ],
                        default="queued",
                        max_length=10,
                    ),
                ),
                (
                    "reason_class",
                    models.CharField(blank=True, default="", max_length=40),
                ),
                ("found", models.IntegerField(default=0)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "asked_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "transcript",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="suggestion_runs",
                        to="core.transcript",
                    ),
                ),
            ],
            options={
                "ordering": ["-created"],
            },
        ),
        migrations.CreateModel(
            name="Summary",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("template_name", models.CharField(max_length=80)),
                ("template_version", models.IntegerField(default=1)),
                ("ground_rules_version", models.IntegerField(default=1)),
                ("focus", models.CharField(blank=True, default="", max_length=200)),
                ("length", models.CharField(default="standard", max_length=10)),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("queued", "queued"),
                            ("running", "running"),
                            ("done", "done"),
                            ("failed", "failed"),
                        ],
                        default="queued",
                        max_length=10,
                    ),
                ),
                (
                    "reason_class",
                    models.CharField(blank=True, default="", max_length=40),
                ),
                ("text", models.TextField(blank=True, default="")),
                ("citations", models.JSONField(blank=True, default=dict)),
                ("cut_short", models.BooleanField(default=False)),
                ("model", models.CharField(blank=True, default="", max_length=120)),
                ("transcript_created", models.DateTimeField(blank=True, null=True)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("written_at", models.DateTimeField(blank=True, null=True)),
                (
                    "asked_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "recording",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="summaries",
                        to="core.recording",
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="core.summarytemplate",
                    ),
                ),
            ],
            options={
                "ordering": ["-created"],
            },
        ),
    ]
