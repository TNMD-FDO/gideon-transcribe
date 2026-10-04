"""Summaries tonight (Phase 9 chapter 5, ADR 0017).

The rules checked here: the upload page offers the tick for a batch into a
case and the batch and its recordings carry it; a transcript landing with
the mark gets one Summary in the state tonight, the type's template, Standard
length, no Focus, and never a second; the case page says how many have no
summary and offers to write them tonight, one audit row with the count; the
night's tick hands the oldest over inside the window while no video is being
enriched, one or two at a time, waits for a recording's own picture, leaves
everything waiting while the engine is away, and marks the rest not reached
as the window closes; the pills and the rows say so; the batch mail gains
its one line; the two settings sit on their pages.
"""

from __future__ import annotations

import pytest
from core import (
    assistant,
    dashboard,
    engine,
    home,
    mail,
    settings_store,
    summaries_tonight,
    tasks,
    vision,
)
from core.assistant import DONE, QUEUED, TONIGHT, Summary
from core.audit import Row
from core.cases import Case
from core.models import LoginSession, User
from core.recordings import Batch
from django.utils import timezone
from tests.test_prepare import a_recording

PASSWORD = "a-long-enough-password"


@pytest.fixture
def admin(db):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("assistant_available", True)
    settings_store.set_to("summary_available", True)
    return User.objects.create_local_admin("adm", PASSWORD)


@pytest.fixture
def a_case(admin):
    return Case.objects.create(owner=admin, name="Pike calls")


@pytest.fixture
def deferred(monkeypatch):
    queued = []
    monkeypatch.setattr(
        tasks.write_summary, "defer", lambda **kw: queued.append(kw) or None
    )
    monkeypatch.setattr(engine, "is_reachable", lambda: True)
    return queued


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def a_call(admin, tmp_path, settings, case, title="Call", batch=None, wanted=True):
    call = a_recording(
        admin, tmp_path, settings, case=case, title=title, batch=batch, video=False
    )
    call.recording_type = "Jail call"
    call.summary_wanted = wanted
    call.save(update_fields=["recording_type", "summary_wanted"])
    return call


def at(hour, minute=0):
    now = timezone.localtime(timezone.now())
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0)


# The settings ------------------------------------------------------------------------


def test_the_two_settings_sit_on_their_pages():
    known = settings_store.DEFINITIONS
    assert known["summaries_at_once_overnight"].page == settings_store.VISION
    assert known["summaries_at_once_overnight"].default == 1
    assert known["summaries_at_once_overnight"].most == 2
    assert known["summaries_tonight_tick_default"].page == settings_store.ASSISTANT
    assert known["summaries_tonight_tick_default"].default is False
    # The window is shared, so it is never greyed behind the vision position.
    assert known["vision_window_start"].needs_value == ()
    assert known["vision_window_end"].needs == ""


# The tick and the mark ---------------------------------------------------------------


@pytest.mark.django_db
def test_the_upload_page_offers_the_tick_for_a_case_and_the_batch_carries_it(
    admin, a_case, client, monkeypatch
):
    from core import uploads, whisperx

    monkeypatch.setattr(whisperx, "is_alive", lambda: True)
    monkeypatch.setattr(uploads, "free_disk_bytes", lambda: 10**15)
    signed_in(client, admin)
    page = client.get("/upload").content.decode()
    assert 'id="summaries-tonight"' in page and 'id="summaries-tick"' in page
    assert "checked" not in page.split('id="summaries-tonight"')[1].split(">")[0]
    assert "between 20:00 and 06:00" in page
    settings_store.set_to("summaries_tonight_tick_default", True)
    page = client.get("/upload").content.decode()
    assert 'id="summaries-tonight" checked' in page
    settings_store.set_to("summary_available", False)
    assert 'id="summaries-tonight"' not in client.get("/upload").content.decode()
    settings_store.set_to("summary_available", True)

    told = client.post(
        "/upload/submit",
        data={
            "files": [{"name": "0409.wav", "size": 1000, "title": "Call 0409"}],
            "batch": {"case": str(a_case.pk), "summaries": True, "enrich": False},
        },
        content_type="application/json",
    )
    assert told.status_code == 200, told.content
    batch = Batch.objects.latest("created")
    assert batch.summaries is True
    assert batch.recordings.get().summary_wanted is True


@pytest.mark.django_db
def test_a_transcript_landing_with_the_mark_gets_one_summary_for_tonight(
    admin, a_case, tmp_path, settings
):
    call = a_call(admin, tmp_path, settings, a_case, "Call 0409")
    assert summaries_tonight.on_transcript(call) is True
    summary = Summary.objects.get(recording=call)
    assert summary.state == TONIGHT and summary.overnight is True
    assert summary.template_name == "Jail call summary"
    assert summary.length == "standard"
    assert summary.focus == "" and summary.asked_by is None
    # Never a second one.
    assert summaries_tonight.on_transcript(call) is False
    assert Summary.objects.filter(recording=call).count() == 1
    # Without the tick, or outside a case, nothing.
    quiet = a_call(admin, tmp_path, settings, a_case, "Call 0410", wanted=False)
    assert summaries_tonight.on_transcript(quiet) is False
    loose = a_call(admin, tmp_path, settings, None, "Loose")
    assert summaries_tonight.on_transcript(loose) is False
    assert Summary.objects.count() == 1
    # The row's words.
    assert summaries_tonight.words(summary) == "Summary tonight"


# The case page's offer -------------------------------------------------------------


@pytest.mark.django_db
def test_the_case_page_counts_the_missing_and_writes_them_tonight_with_a_row(
    admin, a_case, tmp_path, settings, client
):
    first = a_call(admin, tmp_path, settings, a_case, "Call 0409", wanted=False)
    second = a_call(admin, tmp_path, settings, a_case, "Call 0410", wanted=False)
    done = a_call(admin, tmp_path, settings, a_case, "Call 0411", wanted=False)
    Summary.objects.create(
        recording=done,
        state=DONE,
        template_name="Jail call",
        transcript_created=done.transcript.created,
        text="Overview:\nShort.",
    )
    assert [one.pk for one in summaries_tonight.missing_in(a_case)] == [
        first.pk,
        second.pk,
    ]
    signed_in(client, admin)
    page = client.get(f"/case/{a_case.pk}").content.decode()
    assert "2 recordings without a summary" in page
    assert "Write the 2 missing summaries tonight" in page
    before = Row.objects.count()
    told = client.post(f"/case/{a_case.pk}/summaries-tonight")
    assert told.status_code == 302
    assert Summary.objects.filter(state=TONIGHT).count() == 2
    first.refresh_from_db()
    assert first.summary_wanted is True
    row = Row.objects.get(event="Summaries scheduled")
    assert row.details["count"] == 2 and row.object_id == str(a_case.pk)
    assert Row.objects.count() == before + 1
    # The page now says so, and the rows do.
    page = client.get(f"/case/{a_case.pk}").content.decode()
    assert "2 summaries tonight from 20:00" in page
    assert "without a summary" not in page
    assert "summary tonight" in page
    assert dashboard.pills(a_case)[0]["words"] == "Summaries tonight: 2"
    # The case's pill alone (v1.123.0): the session block said it too.
    assert not any(
        one["words"] == "Summaries tonight: 2" for one in home.running_now(admin)
    )
    # Pressing again marks nothing and writes no row.
    client.post(f"/case/{a_case.pk}/summaries-tonight")
    assert Row.objects.filter(event="Summaries scheduled").count() == 1
    # Summary off: not offered.
    settings_store.set_to("summary_available", False)
    assert client.post(f"/case/{a_case.pk}/summaries-tonight").status_code == 403
    assert (
        'id="summaries-line"' not in client.get(f"/case/{a_case.pk}").content.decode()
    )


# The night ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_night_hands_the_oldest_over_inside_the_window_one_at_a_time(
    admin, a_case, tmp_path, settings, deferred
):
    first = a_call(admin, tmp_path, settings, a_case, "Call 0409")
    second = a_call(admin, tmp_path, settings, a_case, "Call 0410")
    third = a_call(admin, tmp_path, settings, a_case, "Call 0411")
    for call in (first, second, third):
        summaries_tonight.on_transcript(call)
    # By day: nothing.
    assert summaries_tonight.mind_the_night("off", at(12)) == "outside"
    assert not deferred
    # In the window: the oldest, then the tick waits for it.
    assert summaries_tonight.mind_the_night("off", at(21)) == "queued"
    one = Summary.objects.get(recording=first)
    assert one.state == QUEUED and one.expectation.get("key") == "summary"
    assert deferred == [{"summary_id": str(one.pk)}]
    assert summaries_tonight.mind_the_night("off", at(21, 1)) == "busy"
    # Done: the next follows.
    Summary.objects.filter(pk=one.pk).update(state=DONE)
    assert summaries_tonight.mind_the_night("off", at(21, 2)) == "queued"
    assert len(deferred) == 2
    # Two at once when the Admin allows it.
    settings_store.set_to("summaries_at_once_overnight", 2)
    assert summaries_tonight.mind_the_night("off", at(21, 3)) == "queued"
    assert len(deferred) == 3
    assert summaries_tonight.mind_the_night("off", at(21, 4)) == "busy"
    # The vision work comes first.
    fourth = a_call(admin, tmp_path, settings, a_case, "Call 0412")
    summaries_tonight.on_transcript(fourth)
    assert summaries_tonight.mind_the_night("queued", at(21, 5)) == "vision"
    assert summaries_tonight.mind_the_night("busy", at(21, 5)) == "vision"
    # The engine away: everything waits, nothing fails.
    Summary.objects.filter(state=QUEUED).update(state=DONE)
    import core.summaries_tonight as module

    module.engine.is_reachable = lambda: False
    assert summaries_tonight.mind_the_night("off", at(21, 6)) == "engine away"
    module.engine.is_reachable = lambda: True
    # The window closes with one waiting: not reached, tonight again.
    assert summaries_tonight.mind_the_night("off", at(6, 1)) == "outside"
    waiting = Summary.objects.get(recording=fourth)
    assert waiting.state == TONIGHT and waiting.reason_class == vision.NOT_REACHED
    assert (
        summaries_tonight.words(waiting)
        == "Summary not reached last night; tonight again"
    )
    assert summaries_tonight.mind_the_night("off", at(21, 7)) == "queued"
    waiting.refresh_from_db()
    assert waiting.reason_class == ""
    # Summary off: the tick does nothing.
    settings_store.set_to("summary_available", False)
    assert summaries_tonight.mind_the_night("off", at(21, 8)) == "off"


@pytest.mark.django_db
def test_a_recording_whose_vision_is_tonight_waits_for_its_picture(
    admin, a_case, tmp_path, settings, deferred
):
    settings_store.set_to("moments_available", True)
    settings_store.set_to("vision_runs", "overnight")
    video = a_recording(admin, tmp_path, settings, case=a_case, title="Cam")
    video.summary_wanted = True
    video.save(update_fields=["summary_wanted"])
    vision.mark_tonight(video.transcript)
    summaries_tonight.on_transcript(video)
    call = a_call(admin, tmp_path, settings, a_case, "Call 0409")
    summaries_tonight.on_transcript(call)
    # The video's summary waits; the call's goes.
    assert summaries_tonight.mind_the_night("off", at(21)) == "queued"
    assert deferred == [{"summary_id": str(Summary.objects.get(recording=call).pk)}]
    Summary.objects.filter(recording=call).update(state=DONE)
    assert summaries_tonight.mind_the_night("off", at(21, 1)) == "nothing"
    # Its picture done: the summary follows.
    video.transcript.prepare_state = assistant.DONE
    video.transcript.save(update_fields=["prepare_state"])
    assert summaries_tonight.mind_the_night("off", at(21, 2)) == "queued"
    assert len(deferred) == 2


@pytest.mark.django_db
def test_the_minute_task_runs_the_vision_tick_then_the_summaries(monkeypatch):
    calls = []
    monkeypatch.setattr(vision, "mind_the_night", lambda: calls.append("v") or "off")
    monkeypatch.setattr(
        summaries_tonight, "mind_the_night", lambda did: calls.append(did) or ""
    )
    tasks.mind_the_night.__wrapped__(0) if hasattr(
        tasks.mind_the_night, "__wrapped__"
    ) else tasks.mind_the_night(0)
    assert calls == ["v", "off"]


# The card and the mail ----------------------------------------------------------------


@pytest.mark.django_db
def test_the_card_says_when_and_the_batch_mail_gains_its_line(
    admin, a_case, tmp_path, settings, client, monkeypatch
):
    sent = []
    monkeypatch.setattr(mail, "configured", lambda: True)
    monkeypatch.setattr(mail, "notifications_on", lambda: True)
    monkeypatch.setattr(mail, "batch_mail_on", lambda: True)
    monkeypatch.setattr(
        mail,
        "send_to_person",
        lambda kind, who, subject, body, **d: (
            sent.append((kind, subject, body)) or True
        ),
    )
    admin.email = "adm@example.test"
    admin.save(update_fields=["email"])
    batch = Batch.objects.create(user=admin, email_when_done=True, summaries=True)
    call = a_call(admin, tmp_path, settings, a_case, "Call 0409", batch=batch)
    summaries_tonight.on_transcript(call)
    assert mail.batch_finished(batch) is True
    assert sent[0][0] == "batch_finished"
    assert "Each recording's summary will be written tonight." in sent[0][2]
    signed_in(client, admin)
    state = client.get(f"/recording/{call.pk}/assistant").json()
    assert state["summaries"][0]["state"] == "tonight"
    assert state["summaries"][0]["due"].startswith("Written tonight")
