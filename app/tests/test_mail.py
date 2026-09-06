"""Email notifications: what goes out, to whom, when, and what is written down.

The relay is a fake: a stand-in for smtplib.SMTP that records the SMTP steps
and answers as an office relay would, or refuses as one might. What would
be expensive to get wrong: a template never leaks anything but names and
counts; a message never goes while mail is off or to somebody without an
address; three tries then one row; the digest's blocks; each hook fires
once; the address rows; the panel's greying and its refusal of a strange
placeholder.
"""

from __future__ import annotations

import smtplib
from datetime import timedelta

import pytest
from core import audit, cases, mail, retention, settings_store, sharing, tasks
from core.audit import Row
from core.cases import Case
from core.jobs import Job, JobState
from core.mail import MailStatus
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording
from django.urls import reverse
from django.utils import timezone

PASSWORD = "a-long-enough-password"


class FakeRelay:
    """smtplib.SMTP as a relay that takes everything, unless told otherwise."""

    sent: list = []
    refuse: str = ""  # "connect", "sender", "recipient", "data", "auth"
    offers_tls = True
    logins: list = []

    def __init__(self, host, port, timeout=None):
        if FakeRelay.refuse == "connect":
            raise OSError("connection refused")
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def ehlo(self):
        return 250, b"ok"

    def has_extn(self, name):
        return name == "starttls" and FakeRelay.offers_tls

    def starttls(self):
        return 220, b"ready"

    def login(self, user, password):
        FakeRelay.logins.append((user, password))
        if FakeRelay.refuse == "auth":
            raise smtplib.SMTPAuthenticationError(535, b"bad password")

    def mail(self, sender):
        return (550, b"no") if FakeRelay.refuse == "sender" else (250, b"ok")

    def rcpt(self, to):
        return (
            (550, b"no such user") if FakeRelay.refuse == "recipient" else (250, b"ok")
        )

    def data(self, message):
        if FakeRelay.refuse == "data":
            return 554, b"rejected"
        FakeRelay.sent.append(message.decode("utf-8", "replace"))
        return 250, b"2.0.0 OK queued as 12345"


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"


@pytest.fixture(autouse=True)
def relay(monkeypatch, tmp_path):
    FakeRelay.sent = []
    FakeRelay.logins = []
    FakeRelay.refuse = ""
    FakeRelay.offers_tls = True
    monkeypatch.setattr(smtplib, "SMTP", FakeRelay)
    monkeypatch.setenv("SMTP_HOST", "relay.example")
    monkeypatch.setenv("SMTP_PORT", "25")
    monkeypatch.setenv("SMTP_STARTTLS", "auto")
    monkeypatch.setenv("SMTP_USER", "")
    monkeypatch.setenv("SMTP_PASSWORD_FILE", str(tmp_path / "no-such-file"))
    monkeypatch.setenv("MAIL_FROM", "transcribe@example.org")
    monkeypatch.setenv("OPERATOR_EMAIL", "it@example.org")
    monkeypatch.setenv("APP_HOSTNAME", "transcribe.example")
    monkeypatch.setenv("HTTPS_PORT", "8443")
    return FakeRelay


@pytest.fixture(autouse=True)
def sent_now(monkeypatch, db):
    """Every queued message is tried at once, as the worker would on try one."""
    queued = []

    def defer(**fields):
        queued.append(fields)
        mail.attempt(**fields)

    monkeypatch.setattr(tasks.send_email, "defer", defer)
    return queued


def person(username, name="", email="", admin=False, local=False):
    who = User.objects.create_local_admin(username, PASSWORD)
    who.is_local = local
    who.admin_flag = admin
    who.display_name = name or username
    who.email = email
    who.last_sign_in = timezone.now()
    who.save()
    return who


@pytest.fixture
def owner(db):
    return person("ana", "Ana Ruiz", "ana@example.org")


@pytest.fixture
def friend(db):
    return person("ben", "Ben Cole", "ben@example.org")


@pytest.fixture
def cases_on(db):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("sharing", True)


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def rows(event):
    return Row.objects.filter(event=event)


# The templates ------------------------------------------------------------------------


def test_the_template_fills_and_collapses_and_carries_the_footer(db):
    subject, body = mail.render(
        mail.DIGEST, name="Ana Ruiz", cases="- US v. Smith: x", shared="", link="L"
    )
    assert subject == "Gideon Transcribe: cases deleting soon"
    assert "Hello Ana Ruiz," in body and "- US v. Smith: x" in body
    # The empty shared block leaves no blank paragraph behind.
    assert "\n\n\n" not in body
    assert body.rstrip().endswith(
        "Sent automatically by Gideon Transcribe (https://transcribe.example:8443/). "
        "Replies go to it@example.org."
    )


def test_a_strange_placeholder_is_refused_and_an_omitted_one_is_not(db):
    assert mail.check_template(mail.SHARED, "Hello {name}, {owner} shared {case}") == ""
    assert "{days}" in mail.check_template(mail.SHARED, "Hello {name}, {days}")
    with pytest.raises(ValueError):
        settings_store.check("shared_body", "Hello {name} {failed_list}")
    assert settings_store.check("shared_body", "Hello {name}") == "Hello {name}"
    # A template an Admin has emptied falls back to the default.
    settings_store.set_to("shared_subject", "")
    subject, _ = mail.render(mail.SHARED, name="a", owner="o", case="c", link="l")
    assert subject == 'Gideon Transcribe: o shared the case "c" with you'


def test_the_email_settings_are_greyed_while_mail_is_not_configured(monkeypatch, db):
    told = settings_store.definition("email_notifications")
    assert told.needs_mail and told.default is True
    assert settings_store.greyed_because(told) == ""
    monkeypatch.setenv("SMTP_HOST", "")
    assert "not configured" in settings_store.greyed_because(told)
    assert not mail.configured() and not mail.notifications_on()


# Sending --------------------------------------------------------------------------


def test_a_message_is_marked_automatic_and_replies_go_to_the_operator(db):
    reply = mail.deliver("ben@example.org", "Hi", "Body\n")
    assert reply == "250 2.0.0 OK queued as 12345"
    raw = FakeRelay.sent[0]
    assert "From: Gideon Transcribe <transcribe@example.org>" in raw
    assert "Reply-To: it@example.org" in raw
    assert "Auto-Submitted: auto-generated" in raw
    assert "X-Auto-Response-Suppress: All" in raw
    assert "Content-Type: text/plain" in raw


def test_the_relays_refusals_become_the_three_reason_classes(db, tmp_path, monkeypatch):
    FakeRelay.refuse = "connect"
    with pytest.raises(mail.MailFailure) as told:
        mail.deliver("x@example.org", "s", "b")
    assert told.value.reason_class == mail.SMTP_UNREACHABLE
    for refuse in ("sender", "recipient", "data"):
        FakeRelay.refuse = refuse
        with pytest.raises(mail.MailFailure) as told:
            mail.deliver("x@example.org", "s", "b")
        assert told.value.reason_class == mail.SMTP_REFUSED
    FakeRelay.refuse = ""
    secret = tmp_path / "smtp_password"
    secret.write_text("hunter2")
    monkeypatch.setenv("SMTP_PASSWORD_FILE", str(secret))
    monkeypatch.setenv("SMTP_USER", "relay-user")
    mail.deliver("x@example.org", "s", "b")
    assert FakeRelay.logins[-1] == ("relay-user", "hunter2")
    FakeRelay.refuse = "auth"
    with pytest.raises(mail.MailFailure) as told:
        mail.deliver("x@example.org", "s", "b")
    assert told.value.reason_class == mail.SMTP_AUTH_FAILED
    # A password with no TLS on offer is refused before it is sent.
    FakeRelay.refuse = ""
    FakeRelay.offers_tls = False
    with pytest.raises(mail.MailFailure) as told:
        mail.deliver("x@example.org", "s", "b")
    assert told.value.reason_class == mail.SMTP_AUTH_FAILED


def test_three_tries_then_one_row_and_a_red_line(db, friend):
    FakeRelay.refuse = "connect"
    fields = dict(
        kind=mail.SHARED,
        to_address="ben@example.org",
        recipient="ben",
        subject="s",
        body="b",
        tries=1,
    )
    assert mail.attempt(**fields) == 5
    assert mail.attempt(**{**fields, "tries": 2}) == 20
    assert rows("Email failed").count() == 0
    assert mail.attempt(**{**fields, "tries": 3}) is None
    failed = rows("Email failed").get()
    assert failed.reason_class == mail.SMTP_UNREACHABLE
    assert failed.details["tries"] == 3 and failed.details["recipient"] == "ben"
    told = mail.status_for_the_panel()
    assert told["colour"] == "red" and "could not be reached" in told["says"]

    FakeRelay.refuse = ""
    assert mail.attempt(**fields) is None
    sent = rows("Email sent").get()
    assert sent.details["kind"] == mail.SHARED and sent.actor_kind == "system"
    assert mail.status_for_the_panel()["colour"] == "plain"


def test_nothing_goes_while_off_or_to_nobody(db, owner, friend, sent_now):
    friend.email = ""
    friend.save()
    assert not mail.send_to_person(mail.SHARED, friend, "s", "b")
    friend.email = "ben@example.org"
    friend.deactivated_at = timezone.now()
    friend.save()
    assert not mail.send_to_person(mail.SHARED, friend, "s", "b")
    friend.deactivated_at = None
    friend.save()
    settings_store.set_to("email_notifications", False)
    assert not mail.send_to_person(mail.SHARED, friend, "s", "b")
    # Operator mail obeys .env alone.
    assert mail.send_to_operator(mail.OPERATOR, "s", "b")
    assert sent_now and Row.objects.filter(event="Email sent").count() == 1
    settings_store.set_to("email_notifications", True)
    assert mail.send_to_person(mail.SHARED, friend, "s", "b")


def test_the_test_message_returns_the_relays_reply_and_writes_its_row(db, owner):
    reply = mail.send_test("ana@example.org", actor=owner)
    assert reply.startswith("250")
    row = rows("Test email sent").get()
    assert row.details["recipient_address"] == "ana@example.org"
    assert "queued" in row.details["reply"]
    FakeRelay.refuse = "recipient"
    with pytest.raises(mail.MailFailure):
        mail.send_test("nobody@example.org")
    assert rows("Test email sent").filter(outcome=audit.Outcome.FAILURE).count() == 1


def test_the_panels_test_button_shows_the_reply(db, owner, client):
    owner.is_local = True
    owner.save()
    signed_in(client, owner)
    answer = client.post(reverse("panel-test-mail"), follow=True)
    assert "The relay said: 250" in answer.content.decode()


# The kinds ------------------------------------------------------------------------


def test_sharing_a_case_mails_the_new_collaborator(cases_on, owner, friend, sent_now):
    a_case = Case.objects.create(owner=owner, name="Ramirez")
    sharing.grant(a_case, friend, actor=owner)
    raw = FakeRelay.sent[-1]
    assert 'Ana Ruiz shared the case "Ramirez" with you' in raw.replace("=\n", "")
    assert f"https://transcribe.example:8443/case/{a_case.pk}" in raw.replace("=\n", "")
    sent = rows("Email sent").get()
    assert sent.details["kind"] == mail.SHARED and sent.details["recipient"] == "ben"
    # Removing a Share sends nothing.
    sharing.revoke(a_case.shares.get(), actor=owner)
    assert rows("Email sent").count() == 1


def test_handing_a_case_over_mails_the_new_owner_with_the_days_left(
    cases_on, owner, friend, sent_now
):
    a_case = Case.objects.create(owner=owner, name="Ramirez")
    sharing.transfer(a_case, friend, actor=owner)
    raw = FakeRelay.sent[-1].replace("=\n", "")
    assert 'Ana Ruiz handed you the case "Ramirez"' in raw
    assert f"deletes in {retention.days_left(a_case)} days" in raw
    assert rows("Email sent").get().details["kind"] == mail.HANDED


def test_the_digest_goes_to_owners_and_collaborators_and_the_operator(
    cases_on, owner, friend, sent_now
):
    a_case = Case.objects.create(owner=owner, name="US v. Smith")
    sharing.grant(a_case, friend, actor=owner)
    FakeRelay.sent = []
    Row.objects.filter(category=audit.Category.EMAIL).delete()
    leaver = person("cy", "Cy Ng", "cy@example.org")
    leaver.deactivated_at = timezone.now()
    leaver.save()
    theirs = Case.objects.create(owner=leaver, name="People v. Doe")
    for one in (a_case, theirs):
        Case.objects.filter(pk=one.pk).update(
            last_activity=timezone.now() - timedelta(days=27)
        )
    retention.sweep()
    # Ana's own case; Ben's under Shared with you; the leaver's to the Operator.
    to_ana = [one for one in FakeRelay.sent if "To: ana@example.org" in one][0]
    assert "- US v. Smith: deletes in 3 days unless used (last used" in to_ana
    assert "Shared with you" not in to_ana
    to_ben = [one for one in FakeRelay.sent if "To: ben@example.org" in one][0]
    assert "- (none of your own)" in to_ben
    assert "Shared with you:" in to_ben and "(owner: Ana Ruiz)" in to_ben
    to_it = [one for one in FakeRelay.sent if "To: it@example.org" in one][0]
    assert "People v. Doe (owner: Cy Ng)" in to_it
    assert not any("To: cy@example.org" in one for one in FakeRelay.sent)
    digest_rows = rows("Email sent").filter(details__kind=mail.DIGEST)
    assert digest_rows.count() == 2
    # Nothing in a message but names, counts, dates, and one link.
    assert "Transcript" not in to_ana and "Speaker" not in to_ana


def test_a_batch_that_finishes_mails_once_when_asked(db, owner, sent_now):
    batch = Batch.objects.create(user=owner, email_when_done=True)
    good = Recording.objects.create(
        batch=batch,
        user=owner,
        title="Good call",
        original_filename="a.m4a",
        media_state=MediaState.READY,
    )
    bad = Recording.objects.create(
        batch=batch,
        user=owner,
        title="Bad call",
        original_filename="b.m4a",
        media_state=MediaState.FAILED,
        failure_message="The file holds no audio.",
    )
    Job.objects.create(recording=good, batch=batch, state=JobState.RUNNING)
    mail.note_batch_progress(bad)
    assert not FakeRelay.sent  # the Batch is not finished yet
    Job.objects.filter(recording=good).update(state=JobState.DONE)
    mail.note_batch_progress(good)
    raw = FakeRelay.sent[-1].replace("=\n", "")
    assert "your batch has finished (1 done, 1 failed)" in raw
    assert "- Bad call: The file holds no audio." in raw
    assert "in your recordings until your session ends" in raw
    # Once, never resent.
    mail.note_batch_progress(good)
    assert len(FakeRelay.sent) == 1
    batch.refresh_from_db()
    assert batch.mail_sent_at is not None
    # And not at all without the tick.
    quiet = Batch.objects.create(user=owner)
    Recording.objects.create(
        batch=quiet,
        user=owner,
        title="x",
        original_filename="x.m4a",
        media_state=MediaState.FAILED,
    )
    mail.note_batch_progress(quiet.recordings.get())
    assert len(FakeRelay.sent) == 1


def test_the_upload_page_offers_the_tick_and_remembers_it(db, owner, client):
    signed_in(client, owner)
    page = client.get(reverse("upload")).content.decode()
    assert (
        'id="email-when-done"' in page
        and "checked" not in page.split('id="email-when-done"')[1].split(">")[0]
    )
    Batch.objects.create(user=owner, email_when_done=True)
    page = client.get(reverse("upload")).content.decode()
    assert "checked" in page.split('id="email-when-done"')[1].split(">")[0]
    owner.email = ""
    owner.save()
    page = client.get(reverse("upload")).content.decode()
    assert (
        "ask IT" in page
        and "disabled" in page.split('id="email-when-done"')[1].split(">")[0]
    )
    settings_store.set_to("batch_finished_emails", False)
    assert 'id="email-when-done"' not in client.get(reverse("upload")).content.decode()


def test_backup_failures_mail_the_operator(db, sent_now):
    from django.core.management import call_command

    call_command(
        "record_backup",
        "failed",
        "--step",
        "snapshot",
        "--reason",
        "target_unreachable",
    )
    raw = FakeRelay.sent[-1].replace("=\n", "")
    assert "last night's backup failed" in raw and "target_unreachable" in raw
    assert rows("Email sent").get().details["recipient"] == "operator"


# The Email address -------------------------------------------------------------------


def test_a_changed_address_writes_its_row_at_sign_in(db, monkeypatch, client):
    from core import directory, signin

    known = person("dee", "Dee Fox", "old@example.org")
    known.is_local = False
    known.save()

    def fake_sign_in(username, password):
        return {
            "ok": True,
            "username": "dee",
            "directory_address": "dee@corp.example",
            "display_name": "Dee Fox",
            "email": "new@example.org",
            "in_admin_group": False,
        }

    monkeypatch.setattr(directory, "sign_in", fake_sign_in)
    monkeypatch.setattr(directory, "is_on", lambda: True)
    request = client.get("/").wsgi_request
    user = signin._from_the_directory(request, "dee", "pw", "10.0.0.1")
    assert user.email == "new@example.org"
    row = rows("Email address updated").get()
    assert row.details["email"] == "new@example.org" and row.affected_user == user


def test_the_users_page_shows_the_column_and_the_filter(db, owner, client):
    owner.is_local = True
    owner.save()
    person("eve", "Eve Lin", "")
    signed_in(client, owner)
    page = client.get(reverse("panel-users")).content.decode()
    assert "<th>Email</th>" in page and "ana@example.org" in page
    assert "No email address" in page
    only = client.get(reverse("panel-users") + "?no_email=1").content.decode()
    assert "eve" in only and "ana@example.org" not in only
    assert mail.people_without_email() == 1
    # A Local admin's address is the one typed address.
    client.post(
        reverse("panel-local-admin", args=[owner.username]),
        {"action": "email", "email": "ana2@example.org"},
    )
    owner.refresh_from_db()
    assert owner.email == "ana2@example.org"
    assert rows("Email address updated").count() == 1


def test_the_status_line_and_the_installation_page(db, owner, client, monkeypatch):
    assert mail.status_for_the_panel()["says"] == "nothing sent yet"
    MailStatus.the_one()
    monkeypatch.setenv("SMTP_HOST", "")
    assert mail.status_for_the_panel()["says"] == "not configured"
    monkeypatch.setenv("SMTP_HOST", "relay.example")
    owner.is_local = True
    owner.save()
    signed_in(client, owner)
    told = client.get(reverse("panel-status-lines")).json()
    assert told["email"]["says"] == "nothing sent yet"
    page = client.get(reverse("panel-installation")).content.decode()
    assert "relay.example" in page and "Mail relay password" in page
    assert cases is not None  # the import is used by the fixtures' callers
