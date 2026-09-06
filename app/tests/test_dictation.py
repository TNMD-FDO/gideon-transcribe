"""Dictation (Phase 3): a recording kept on its own, a memo, Send to.

What would be expensive to get wrong: the tab exists only under its setting;
a dictation is kept outside the Workspace and off the Recordings page; the
memo is one click with the shipped template; Send to gives one colleague
that one dictation and nothing more, and the mail carries the memo only when
the office says so; the office's retention takes each dictation on its own.
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest
from core import dictation, lifecycle, live, mail, settings_store, tasks
from core.assistant import Summary, SummaryTemplate
from core.audit import Row
from core.dictation import DictationShare
from core.jobs import Segment, Transcript
from core.models import LoginSession, User
from core.recordings import MediaState, Recording
from django.urls import reverse
from django.utils import timezone

PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings, monkeypatch):
    from core import uploads

    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"
    (tmp_path / "uploads").mkdir()
    monkeypatch.setattr(uploads, "free_disk_bytes", lambda: 10**15)


@pytest.fixture(autouse=True)
def on(db):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("live_recording", True)
    settings_store.set_to("dictation", True)
    settings_store.set_to("assistant_available", True)


@pytest.fixture(autouse=True)
def quiet_tasks(monkeypatch):
    queued = {"summaries": [], "mail": []}
    monkeypatch.setattr(
        tasks.write_summary, "defer", lambda **f: queued["summaries"].append(f)
    )
    monkeypatch.setattr(tasks.send_email, "defer", lambda **f: queued["mail"].append(f))
    return queued


def person(username, name, email="", local=False):
    who = User.objects.create_local_admin(username, PASSWORD)
    who.is_local = local
    who.display_name = name
    who.email = email
    who.last_sign_in = timezone.now()
    who.save()
    return who


@pytest.fixture
def ana(db):
    return person("ana", "Ana Ruiz", "ana@example.org")


@pytest.fixture
def ben(db):
    return person("ben", "Ben Cole", "ben@example.org")


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def a_dictation(who, ready=True):
    recording = live.start(who, None, dictation=True)
    if ready:
        recording.media_state = MediaState.READY
        recording.duration_seconds = 90
        recording.save()
        transcript = Transcript.objects.create(recording=recording, language="en")
        Segment.objects.create(
            transcript=transcript, start=0, end=5, text="Dear colleague", speaker="A"
        )
    return recording


def rows(event):
    return Row.objects.filter(event=event)


# The tab and the setting --------------------------------------------------------


def test_the_tab_exists_only_under_its_setting(ana, client):
    signed_in(client, ana)
    assert 'href="/record"' in client.get(reverse("upload")).content.decode()
    assert client.get(reverse("record")).status_code == 200
    assert client.get(reverse("record-new")).status_code == 200
    # The old addresses lead to the new pages.
    assert client.get(reverse("dictations")).status_code == 302
    assert client.get(reverse("dictate")).status_code == 302
    settings_store.set_to("dictation", False)
    assert client.get(reverse("record")).status_code == 404
    assert client.get(reverse("record-new")).status_code == 404
    assert 'href="/record"' not in client.get(reverse("upload")).content.decode()
    told = settings_store.definition("dictation")
    assert told.needs == "live_recording" and told.default is False


# A dictation stands on its own -----------------------------------------------------


def test_a_dictation_is_kept_on_its_own_outside_the_workspace(ana, client):
    signed_in(client, ana)
    answer = client.post(
        reverse("record-start"), json.dumps({"dictation": True}), "application/json"
    )
    assert answer.status_code == 200, answer.content
    assert answer.json()["case"] == "/record"
    recording = Recording.objects.get(pk=answer.json()["id"])
    assert recording.is_dictation and recording.case is None
    assert recording.recording_type == "Dictation" and not recording.diarize
    assert recording.title.startswith("Dictation") and recording.last_used is not None
    assert rows("Live recording started").get().details["dictation"] is True
    # Not the Workspace's: not discarded at sign-out, not on the Recordings page.
    assert list(lifecycle.in_the_workspace(ana)) == []
    recording.media_state = MediaState.READY
    recording.save()
    assert recording.title not in client.get(reverse("home")).content.decode()
    page = client.get(reverse("record")).content.decode()
    assert recording.title in page and "New recording" in page
    # Without the setting a dictation cannot start.
    settings_store.set_to("dictation", False)
    answer = client.post(
        reverse("record-start"), json.dumps({"dictation": True}), "application/json"
    )
    assert answer.status_code == 400


def test_the_new_recording_page_asks_one_question(ana, client):
    signed_in(client, ana)
    page = client.get(reverse("record-new")).content.decode()
    assert '<h1 class="grow">New recording</h1>' in page
    assert "What are you recording?" in page and "More options" in page
    assert page.count('name="style"') == 3 and 'href="/record"' in page


def test_the_styles_preset_the_type_the_sides_and_the_product(ana):
    meeting = live.start(ana, None, dictation=True, style="meeting")
    assert meeting.recording_type == "Interview" and meeting.diarize
    assert meeting.live["style"] == "meeting" and meeting.live["sources"] == [
        "microphone"
    ]
    assert dictation.product_of(meeting) == "summary"
    call = live.start(ana, None, dictation=True, style="call")
    assert call.recording_type == "Meeting" and call.live["sources"] == [
        "microphone",
        "computer",
    ]
    assert dictation.product_of(call) == "summary"
    # A type chosen under More options wins over the style's.
    jail = live.start(
        ana, None, dictation=True, style="call", recording_type="Jail call"
    )
    assert jail.recording_type == "Jail call"
    plain = live.start(ana, None, dictation=True, style="dictation")
    assert plain.recording_type == "Dictation" and not plain.diarize
    assert dictation.product_of(plain) == "memo"
    # The Meeting summary ships for the Meeting type.
    assert SummaryTemplate.chosen_for(call).key == "meeting"
    assert SummaryTemplate.chosen_for(meeting).key == "interview"


# The memo ---------------------------------------------------------------------------


def test_the_memo_is_one_click_with_the_shipped_template(ana, client, quiet_tasks):
    recording = a_dictation(ana)
    template = dictation.memo_template()
    assert template is not None and template.recording_types == ["Dictation"]
    assert "do not summarise" in template.text and "[unclear]" in template.text
    signed_in(client, ana)
    page = client.get(reverse("record")).content.decode()
    assert "Write the memo" in page
    answer = client.post(reverse("dictation-memo", args=[recording.pk]))
    assert answer.status_code == 200
    memo = Summary.objects.get(pk=answer.json()["memo_id"])
    assert memo.template.key == "dictation" and memo.length == "detailed"
    assert quiet_tasks["summaries"] == [{"summary_id": str(memo.pk)}]
    told = client.get(reverse("dictation-state", args=[recording.pk])).json()
    assert told["memo"] == "queued" and told["state"] == "ready"
    # Written: the page offers Open the memo.
    memo.state = "done"
    memo.text = "Dear colleague"
    memo.save()
    page = client.get(reverse("record")).content.decode()
    assert (
        "Open the memo" in page and f"/recording/{recording.pk}?panel=summary" in page
    )
    # The viewer preselects the Dictation memo for a dictation.
    assert SummaryTemplate.chosen_for(recording).key == "dictation"


def test_no_memo_before_the_transcript_or_without_the_assistant(ana, client):
    recording = a_dictation(ana, ready=False)
    signed_in(client, ana)
    answer = client.post(reverse("dictation-memo", args=[recording.pk]))
    assert answer.status_code == 400 and "transcript" in answer.json()["why"]


# Send to ---------------------------------------------------------------------------


def test_send_to_gives_one_colleague_that_dictation(
    ana, ben, client, quiet_tasks, monkeypatch
):
    monkeypatch.setenv("SMTP_HOST", "relay.example")
    monkeypatch.setenv("MAIL_FROM", "transcribe@example.org")
    recording = a_dictation(ana)
    signed_in(client, ana)
    told = client.get(reverse("dictation-who", args=[recording.pk])).json()
    assert [one["username"] for one in told["people"]] == ["ben"]
    answer = client.post(
        reverse("dictation-send", args=[recording.pk]),
        json.dumps({"who": "Ben Cole"}),
        "application/json",
    )
    assert answer.status_code == 200, answer.content
    share = DictationShare.objects.get(recording=recording, person=ben)
    assert share.attached is False  # no memo yet, and the setting is off
    row = rows("Dictation sent").get()
    assert row.details["recipient"] == "ben" and row.details["attached"] is False
    assert len(quiet_tasks["mail"]) == 1
    sent = quiet_tasks["mail"][0]
    assert sent["kind"] == mail.DICTATION and sent["to_address"] == "ben@example.org"
    assert (
        "sent you a recording" in sent["subject"]
        and "attach_memo" not in sent["details"]
    )
    # Ben sees it under Sent to you, reads it, and can do nothing more with it.
    signed_in(client, ben)
    page = client.get(reverse("record")).content.decode()
    assert "Sent to you" in page and recording.title in page
    assert "Write the memo" not in page and "Send to" not in page
    assert client.get(reverse("viewer", args=[recording.pk])).status_code == 200
    assert (
        client.post(
            reverse("dictation-send", args=[recording.pk]), "{}", "application/json"
        ).status_code
        == 404
    )
    assert (
        client.post(reverse("delete-recording", args=[recording.pk])).status_code == 404
    )
    # Sending again changes nothing; taking back removes it.
    signed_in(client, ana)
    client.post(
        reverse("dictation-send", args=[recording.pk]),
        json.dumps({"who": "ben"}),
        "application/json",
    )
    assert DictationShare.objects.filter(recording=recording).count() == 1
    answer = client.post(
        reverse("dictation-take-back", args=[recording.pk]), {"share": share.pk}
    )
    assert answer.status_code == 200
    assert not DictationShare.objects.filter(pk=share.pk).exists()
    assert rows("Dictation taken back").get().details["recipient"] == "ben"
    signed_in(client, ben)
    assert client.get(reverse("viewer", args=[recording.pk])).status_code == 302


def test_the_memo_rides_with_the_mail_only_when_the_office_says_so(
    ana, ben, client, quiet_tasks, monkeypatch
):
    monkeypatch.setenv("SMTP_HOST", "relay.example")
    monkeypatch.setenv("MAIL_FROM", "transcribe@example.org")
    recording = a_dictation(ana)
    memo = dictation.write_memo(recording, ana)
    memo.state = "done"
    memo.text = "Dear colleague, new paragraph."
    memo.save()
    settings_store.set_to("dictation_by_email", True)
    assert dictation.by_email()
    dictation.send(recording, ben, ana)
    sent = quiet_tasks["mail"][-1]
    assert sent["details"]["attach_memo"] == str(recording.pk)
    assert DictationShare.objects.get(recording=recording).attached is True
    # The file itself: the memo as Word, built when the mail goes.
    name, data = mail._memo_file(str(recording.pk))
    assert name.endswith(" - memo.docx") and data[:2] == b"PK"
    message = mail.build("ben@example.org", "s", "body", (name, data))
    parts = [part.get_filename() for part in message.iter_attachments()]
    assert parts == [name]
    # Off: nothing rides.
    settings_store.set_to("dictation_by_email", False)
    other = person("cy", "Cy Ng", "cy@example.org")
    dictation.send(recording, other, ana)
    assert "attach_memo" not in quiet_tasks["mail"][-1]["details"]


# Retention ----------------------------------------------------------------------------


def test_the_offices_retention_takes_each_dictation_on_its_own(ana, client):
    recording = a_dictation(ana)
    assert dictation.days_left(recording) == 30
    Recording.objects.filter(pk=recording.pk).update(
        last_used=timezone.now() - timedelta(days=25)
    )
    recording.refresh_from_db()
    assert dictation.days_left(recording) == 5
    signed_in(client, ana)
    page = client.get(reverse("record")).content.decode()
    assert "unless opened" in page and 'class="expiring"' in page
    assert dictation.for_tonights_digest() == {
        ana.pk: [{"title": recording.title, "days_left": 5}]
    }
    # Opening it starts the clock over.
    client.get(reverse("viewer", args=[recording.pk]))
    recording.refresh_from_db()
    assert dictation.days_left(recording) == 30
    # Run out: the sweep deletes it, for good, with the recording's own row.
    Recording.objects.filter(pk=recording.pk).update(
        last_used=timezone.now() - timedelta(days=31)
    )
    assert dictation.sweep() == {"deleted": 1}
    assert not Recording.objects.filter(pk=recording.pk).exists()
    assert rows("Recording deleted").get().details["cause"] == "retention"
    # The sweep runs whatever Folder management says.
    settings_store.set_to("folder_management", False)
    assert dictation.sweep() == {"deleted": 0}


def test_the_digest_carries_the_dictations_block(ana, ben, monkeypatch, quiet_tasks):
    monkeypatch.setenv("SMTP_HOST", "relay.example")
    monkeypatch.setenv("MAIL_FROM", "transcribe@example.org")
    recording = a_dictation(ana)
    sent = mail.send_digests({}, {ana.pk: [{"title": recording.title, "days_left": 3}]})
    assert sent == 1
    body = quiet_tasks["mail"][-1]["body"]
    assert "Dictations deleting soon:" in body
    assert f"- {recording.title}: deletes in 3 days unless opened" in body
    assert "- (none)" in body
