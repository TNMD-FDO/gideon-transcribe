# Mail (Phase 2, Email notifications): the Status page's Email line, and the
# Batch's "Email me when this batch finishes" tick with its sent mark.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0024_share"),
    ]

    operations = [
        migrations.CreateModel(
            name="MailStatus",
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
                ("last_sent_at", models.DateTimeField(blank=True, null=True)),
                (
                    "last_sent_kind",
                    models.CharField(blank=True, default="", max_length=40),
                ),
                ("last_failed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "last_failed_reason",
                    models.CharField(blank=True, default="", max_length=40),
                ),
                ("last_try_failed", models.BooleanField(default=False)),
            ],
        ),
        migrations.AddField(
            model_name="batch",
            name="email_when_done",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="batch",
            name="mail_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
