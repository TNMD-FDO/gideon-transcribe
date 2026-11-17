"""v1.246.0: the Preservation copy's mail, and one save between several owners
(Phase 14 chapter 3; the drawing phase-14-preservation-mail.html).

The rules checked here: a copy's owners are the Case's Owner and everyone
marked Also an owner, written on the archived copy as the Case goes; each
sees it in Archived and may download it, and only the Owner and Admins may
remove it; the first to take a copy marks it for all, a later download by
another is asked first, and Mark as saved asks once and then marks; the
message goes to each owner, says who else has it, and carries the file only
to one person, when the office allows and it fits; the Retention policy's
deletion is told the night the Case is binned and not again at its wipe; with
nobody to tell the Operator address is told; the nightly digest lists copies
not yet saved every night and, once, the ones somebody else took; a copy made
from the Details tab sends nothing; and the words are where they belong.
"""

from __future__ import annotations

import smtplib
from datetime import timedelta
from pathlib import Path

import pytest
from core import cases, mail, preservation, retention, settings_store
from core.audit import Row
from core.cases import Case
from core.models import User
from core.preservation import ArchivedCopy, PreservationCopy
from core.sharing import Share
from django.utils import timezone
from tests.helpers import signed_in
from tests.test_mail import FakeRelay
from tests.test_preservation import a_recording, a_transcript, made
from tests.test_retention import aged, binned_for

PASSWORD = "a-long-enough-password"
APP = Path(__file__).resolve().parent.parent
ROOT = APP.parent


def person(username: str, name: str, address: str = "") -> User:
    user = User.objects.from_directory(username, display_name=name)
    user.email = address
    user.save(update_fields=["email"])
    return user


@pytest.fixture
def owner(db):
    return person("jsmith", "J Smith", "jsmith@example.org")


@pytest.fixture
def second(db):
    return person("mjones", "M Jones", "mjones@example.org")


@pytest.fixture
def third(db):
    return person("akhan", "A Khan", "akhan@example.org")


@pytest.fixture
def a_case(owner):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("sharing", True)
    case = Case.objects.create(owner=owner, name="Ramirez")
    a_transcript(a_recording(owner, case))
    return case


@pytest.fixture
def also(a_case, owner, second):
    """M Jones, marked Also an owner of the Case."""
    return Share.objects.create(
        case=a_case, person=second, added_by=owner, also_owner=True
    )


@pytest.fixture(autouse=True)
def post(monkeypatch, tmp_path):
    """A relay that is set up, and the messages queued for it, kept."""
    FakeRelay.sent = []
    FakeRelay.refuse = ""
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
    queued: list = []

    def queue(kind, to_address, recipient, subject, body, **fields):
        queued.append(
            {
                "kind": kind,
                "to": to_address,
                "recipient": recipient,
                "subject": subject,
                "body": body,
                **fields,
            }
        )

    monkeypatch.setattr(mail, "_queue", queue)
    return queued


def of_kind(post, kind):
    return [one for one in post if one["kind"] == kind]


# Who a copy's owners are --------------------------------------------------------


def test_a_copys_owners_are_the_owner_and_everyone_marked_also_an_owner(
    a_case, owner, second, third, also
):
    Share.objects.create(case=a_case, person=third, added_by=owner)
    assert preservation.owners_of(a_case) == [owner, second]
    # The mark is a Share's, so it holds only while Sharing is on.
    settings_store.set_to("sharing", False)
    assert preservation.owners_of(a_case) == [owner]


def test_the_other_owners_are_written_on_the_copy_as_the_case_goes(
    a_case, owner, second, third, also, client
):
    Share.objects.create(case=a_case, person=third, added_by=owner)
    made(a_case, owner)
    cases.delete(a_case, actor=owner)
    kept = ArchivedCopy.objects.get()
    assert kept.also_owners == [{"id": second.pk, "name": "M Jones"}]
    assert kept.also_owner_ids == [second.pk]

    # A person marked Also an owner sees it, and may download it, not remove it.
    theirs = signed_in(client, second)
    assert ">Archived (1)</a>" in theirs.get("/cases").content.decode()
    page = theirs.get("/cases/archived").content.decode()
    assert "<b>Ramirez</b>" in page and "Owners: J Smith, M Jones" in page
    assert f"/cases/archived/{kept.pk}/download" in page
    assert "remove-copy" not in page
    assert theirs.post(f"/cases/archived/{kept.pk}/remove").status_code == 404
    assert ArchivedCopy.objects.count() == 1
    # A Collaborator without the mark sees nothing of it.
    plain = signed_in(client, third)
    assert "Ramirez" not in plain.get("/cases/archived").content.decode()
    assert plain.get(f"/cases/archived/{kept.pk}/download").status_code == 404
    # The Owner still may remove it.
    mine = signed_in(client, owner)
    assert "remove-copy" in mine.get("/cases/archived").content.decode()


# One mark -------------------------------------------------------------------------


def test_the_first_to_take_it_marks_it_and_another_is_asked_first(
    a_case, owner, second, also, client
):
    made(a_case, owner)
    cases.delete(a_case, actor=owner)
    kept = ArchivedCopy.objects.get()
    address = f"/cases/archived/{kept.pk}/download"

    answer = signed_in(client, second).get(address)
    assert answer["Content-Type"] == "application/zip"
    b"".join(answer.streaming_content)
    kept.refresh_from_db()
    assert kept.downloaded_by_user_id == second.pk and kept.taken_how == "downloaded"
    assert preservation.waiting_count(owner) == 0

    # The Owner sees who has it, and is asked before it is given again.
    mine = signed_in(client, owner)
    page = mine.get("/cases/archived").content.decode()
    assert "by M Jones</span>" in page and ">Download again</a>" in page
    assert "Mark as saved" not in page
    asked = mine.get(address)
    assert asked["Content-Type"].startswith("text/html")
    asked = asked.content.decode()
    assert "<h1>M Jones already downloaded this</h1>" in asked
    assert "you do not need to save it again" in asked
    assert f'href="{address}?again=1"' in asked and ">Leave it</a>" in asked
    again = mine.get(address + "?again=1")
    assert again["Content-Type"] == "application/zip"
    b"".join(again.streaming_content)
    # The mark is the first one's, and is not moved.
    kept.refresh_from_db()
    assert kept.downloaded_by_name == "M Jones"
    # The one who took it is given it again without a question.
    theirs = signed_in(client, second).get(address)
    assert theirs["Content-Type"] == "application/zip"
    b"".join(theirs.streaming_content)


def test_mark_as_saved_asks_once_and_then_marks(a_case, owner, client):
    made(a_case, owner)
    cases.delete(a_case, actor=owner)
    kept = ArchivedCopy.objects.get()
    browser = signed_in(client, owner)
    assert "Mark as saved" in browser.get("/cases/archived").content.decode()
    address = f"/cases/archived/{kept.pk}/saved"
    # The message's link only asks: a mail system may open a link by itself.
    page = browser.get(address).content.decode()
    assert "Have you saved the Preservation copy of <b>Ramirez</b>" in page
    assert ">Yes, I saved it</button>" in page
    kept.refresh_from_db()
    assert kept.downloaded_at is None

    assert browser.post(address).status_code == 302
    kept.refresh_from_db()
    assert kept.taken_how == "saved" and kept.downloaded_by_user_id == owner.pk
    assert Row.objects.filter(event="preservation copy marked saved").count() == 1
    assert "saved " in browser.get("/cases/archived").content.decode()
    assert "is marked already" in browser.get(address).content.decode()
    browser.post(address)
    assert Row.objects.filter(event="preservation copy marked saved").count() == 1


# The message ------------------------------------------------------------------------


def test_one_owner_is_sent_a_link_unless_the_office_attaches(a_case, owner, post):
    made(a_case, owner)
    cases.delete(a_case, actor=owner)
    kept = ArchivedCopy.objects.get()
    (sent,) = of_kind(post, mail.PRESERVATION)
    assert sent["to"] == "jsmith@example.org" and sent["recipient"] == "jsmith"
    assert sent["subject"] == (
        'Gideon Transcribe: save the Preservation copy of "Ramirez"'
    )
    body = sent["body"]
    assert "Hello J Smith," in body
    assert f'The case "Ramirez" was deleted on {kept.gone_on:%d %B %Y} by you.' in body
    assert "is to be saved to the client's file of record." in body
    assert "This went to" not in body
    assert f"https://transcribe.example:8443/cases/archived/{kept.pk}/download" in body
    # Attach is Off until the office says its mail may carry the file.
    assert "attach_copy" not in sent["details"] and "is attached" not in body


def test_the_file_goes_to_one_person_when_the_office_allows_and_it_fits(
    a_case, owner, post
):
    settings_store.set_to("preservation_attach", True)
    made(a_case, owner)
    cases.delete(a_case, actor=owner)
    kept = ArchivedCopy.objects.get()
    (sent,) = of_kind(post, mail.PRESERVATION)
    body = sent["body"]
    assert "Its Preservation copy is attached: everything made in the case" in body
    assert "Saved it from this message? Press here so you are not reminded:" in body
    assert f"/cases/archived/{kept.pk}/saved" in body
    assert sent["details"]["attach_copy"] == str(kept.path)
    assert sent["details"]["attach_name"].startswith("Ramirez - preservation copy ")

    # Sent: the zip is read then, and the row says it was attached.
    mail.attempt(
        kind=sent["kind"],
        to_address=sent["to"],
        recipient=sent["recipient"],
        subject=sent["subject"],
        body=sent["body"],
        tries=1,
        object_type=sent["object_type"],
        object_id=sent["object_id"],
        object_label=sent["object_label"],
        details=sent["details"],
    )
    (message,) = FakeRelay.sent
    assert "Ramirez - preservation copy" in message and "application/zip" in message
    row = Row.objects.get(event="Email sent")
    assert row.details["kind"] == "preservation_copy" and row.details["attached"]
    assert "attach_copy" not in row.details


def test_several_owners_are_told_of_each_other_and_none_is_handed_the_file(
    a_case, owner, second, also, post
):
    settings_store.set_to("preservation_attach", True)
    made(a_case, owner)
    cases.delete(a_case, actor=owner)
    sent = of_kind(post, mail.PRESERVATION)
    assert sorted(one["to"] for one in sent) == [
        "jsmith@example.org",
        "mjones@example.org",
    ]
    for one in sent:
        assert (
            "This went to J Smith (owner) and M Jones. Only one of you needs to "
            "save it. Whoever downloads it is recorded, and the others are told "
            "it is done."
        ) in one["body"]
        assert "by J Smith." in one["body"]
        # A file in two mailboxes is a file nobody can know was saved once.
        assert "attach_copy" not in one["details"]
        assert "is attached" not in one["body"] and "Download it, until" in one["body"]


def test_a_copy_too_large_to_attach_says_so(owner, post, tmp_path):
    settings_store.set_to("preservation_attach", True)
    settings_store.set_to("preservation_attach_most_mb", 5)
    mail.preservation_copy(
        [owner],
        case_id="c",
        case_name="State v. Quay",
        owner_name="J Smith",
        happened="It went.",
        download="https://x/download",
        saved="https://x/saved",
        until=timezone.localdate(),
        path=tmp_path / "copy.zip",
        filename="copy.zip",
        size_bytes=64 * 1024 * 1024,
    )
    (sent,) = of_kind(post, mail.PRESERVATION)
    assert (
        "Its Preservation copy is 64 MB, too large to attach (the office's limit "
        "is 5 MB)."
    ) in sent["body"]
    assert "attach_copy" not in sent["details"]


def test_the_clocks_deletion_is_told_at_the_bin_and_not_again_at_the_wipe(
    a_case, owner, post
):
    aged(a_case, 30)
    retention.sweep()
    (sent,) = of_kind(post, mail.PRESERVATION)
    body = sent["body"]
    assert 'The case "Ramirez" went unused for 30 days and was deleted by the' in body
    assert "retention policy on" in body and "It waits in the Recycle bin until" in body
    assert "https://transcribe.example:8443/cases/bin" in body
    assert f"/cases/bin/{a_case.pk}/preservation/download" in body
    post.clear()
    binned_for(a_case, 30)
    retention.sweep()
    assert ArchivedCopy.objects.count() == 1
    assert of_kind(post, mail.PRESERVATION) == []


def test_with_nobody_to_tell_the_operator_is_told_the_name_and_never_the_file(
    a_case, owner, post
):
    settings_store.set_to("preservation_attach", True)
    owner.email = ""
    owner.save(update_fields=["email"])
    made(a_case, owner)
    cases.delete(a_case, actor=owner)
    assert of_kind(post, mail.PRESERVATION) == []
    (told,) = of_kind(post, mail.OPERATOR)
    assert told["to"] == "it@example.org"
    assert 'The case "Ramirez" (owner: J Smith) was deleted' in told["body"]
    assert "attach_copy" not in told["details"]


def test_the_office_may_turn_the_mail_off_and_a_made_copy_sends_none(
    a_case, owner, post
):
    # A copy a person made from the Details tab is not a deletion: no mail.
    made(a_case, owner)
    assert post == []
    settings_store.set_to("preservation_mail", False)
    cases.delete(a_case, actor=owner)
    assert post == [] and preservation.for_tonights_digest() == {}


def test_an_also_owner_reaches_a_binned_cases_copy_by_their_link(
    a_case, owner, second, also, client
):
    aged(a_case, 30)
    retention.sweep()
    browser = signed_in(client, second)
    # The Recycle bin page is not theirs; the copy's address is.
    assert "Ramirez" not in browser.get("/cases/bin").content.decode()
    answer = browser.get(f"/cases/bin/{a_case.pk}/preservation/download")
    assert answer["Content-Type"] == "application/zip"
    b"".join(answer.streaming_content)
    copy = PreservationCopy.objects.get(case=a_case)
    assert copy.downloaded_by_user_id == second.pk
    asked = signed_in(client, owner).get(
        f"/cases/bin/{a_case.pk}/preservation/download"
    )
    assert "M Jones already downloaded this" in asked.content.decode()


# The nightly reminder ---------------------------------------------------------------


def test_the_digest_lists_copies_not_yet_saved_every_night(
    a_case, owner, second, also, post
):
    made(a_case, owner)
    cases.delete(a_case, actor=owner)
    kept = ArchivedCopy.objects.get()
    for _ in range(2):
        post.clear()
        retention.sweep()
        digests = of_kind(post, mail.DIGEST)
        assert sorted(one["recipient"] for one in digests) == ["jsmith", "mjones"]
        for one in digests:
            assert (
                "Preservation copies not yet saved to the client's file:"
                in (one["body"])
            )
            until = kept.gone_on + timedelta(days=30)
            assert (
                f"- Ramirez: kept until {until:%d %B %Y} (30 days left)"
                in (one["body"])
            )
            assert "https://transcribe.example:8443/cases/archived" in one["body"]
            assert one["details"]["copies"] == 1


def test_the_others_are_told_once_that_it_is_done(
    a_case, owner, second, also, post, client
):
    made(a_case, owner)
    cases.delete(a_case, actor=owner)
    kept = ArchivedCopy.objects.get()
    answer = signed_in(client, second).get(f"/cases/archived/{kept.pk}/download")
    b"".join(answer.streaming_content)
    post.clear()
    retention.sweep()
    # The Owner is told; the one who took it has nothing to be told.
    (told,) = of_kind(post, mail.DIGEST)
    assert told["recipient"] == "jsmith"
    assert "Preservation copies saved by someone else:" in told["body"]
    assert "- Ramirez: downloaded by M Jones on" in told["body"]
    assert "Nothing more for you to do." in told["body"]
    assert "not yet saved" not in told["body"]
    # Once: the night after, nobody is told anything.
    ArchivedCopy.objects.update(downloaded_at=timezone.now() - timedelta(days=2))
    post.clear()
    retention.sweep()
    assert of_kind(post, mail.DIGEST) == []


def test_a_binned_cases_copy_is_in_the_digest_as_in_the_recycle_bin(
    a_case, owner, post
):
    aged(a_case, 30)
    retention.sweep()
    post.clear()
    retention.sweep()
    (told,) = of_kind(post, mail.DIGEST)
    assert "- Ramirez: kept until" in told["body"]
    assert "(60 days left; the case is in the Recycle bin)" in told["body"]


def test_an_edited_digest_without_the_block_has_it_at_its_foot(a_case, owner, post):
    settings_store.set_to("digest_body", "Hello {name},\n\n{cases}\n\nBye.\n")
    made(a_case, owner)
    cases.delete(a_case, actor=owner)
    post.clear()
    retention.sweep()
    (told,) = of_kind(post, mail.DIGEST)
    body = told["body"]
    assert "Bye." in body and "Preservation copies not yet saved" in body
    assert body.index("Bye.") < body.index("Preservation copies not yet saved")
    assert body.index("Preservation copies") < body.index("Sent automatically by")


# The settings and the words -----------------------------------------------------------


def test_the_settings_their_defaults_and_the_template(db):
    assert settings_store.get("preservation_mail") is True
    assert settings_store.get("preservation_attach") is False
    assert settings_store.get("preservation_attach_most_mb") == 20
    told = mail.TEMPLATES[mail.PRESERVATION]
    assert told["placeholders"] == {
        "name",
        "case",
        "happened",
        "copy",
        "owners",
        "link",
    }
    assert "copies" in mail.TEMPLATES[mail.DIGEST]["placeholders"]
    assert mail.check_template(mail.PRESERVATION, "{name} {quote}") != ""
    assert mail.KIND_WORDS[mail.PRESERVATION] == "preservation copy kept"
    # The setting's default wording is the template's own.
    assert settings_store.get("preservation_body") == told["body"]
    assert settings_store.get("digest_body") == mail.TEMPLATES[mail.DIGEST]["body"]


def test_the_words_are_in_the_glossary_the_record_the_guides_and_the_changelog():
    catalogue = (ROOT / "docs/spec/ADMIN-SETTINGS-CATALOGUE.md").read_text(
        encoding="utf-8"
    )
    for key in (
        "preservation_mail",
        "preservation_attach",
        "preservation_attach_most_mb",
        "preservation_subject",
    ):
        assert f"`{key}`" in catalogue, key
    glossary = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    assert "everyone who was marked Also an owner, from v1.246.0" in glossary
    record = ROOT / "docs/adr/0030-a-deleted-case-leaves-its-preservation-copy.md"
    assert "## Added with v1.246.0 (Phase 14 chapter 3)" in record.read_text(
        encoding="utf-8"
    )
    spec = (ROOT / "docs/spec/SPEC-PHASE-14.md").read_text(encoding="utf-8")
    assert (
        "## 3. The Preservation copy's mail, and one save between several owners "
        "(v1.246.0)"
    ) in spec
    drawing = ROOT / "docs/spec/mockups/phase-14-preservation-mail.html"
    assert drawing.exists() and "<img" not in drawing.read_text(encoding="utf-8")
    guide = (ROOT / "docs" / "user-guide.md").read_text(encoding="utf-8")
    assert "**Mark as saved**" in guide and "**Download again**" in guide
    assert "only one of you needs to save it" in guide
    admin = (ROOT / "docs" / "admin-guide.md").read_text(encoding="utf-8")
    assert "**Attach the Preservation copy**" in admin
    assert "**Preservation copy mail**" in admin
    log = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## v1.246.0" in log and "Attach the Preservation copy" in log
