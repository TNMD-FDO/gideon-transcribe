"""Vision on the office's terms (Phase 4 chapter 5, v1.54.0).

The rules checked here: the Vision page carries the picture settings under
their groups, with the three withdrawn ones gone and the four new ones
there; a window edge is a clock time; a transcript lands into the office's
position (queued now, marked for tonight, or left for an Admin) by the tick,
and a session recording waits for no night; the night's tick queues the
oldest video first, one at a time, inside the window, and marks the rest
not reached as the window closes; the pages say the state in the one family
of words; the case page offers Enrich tonight to anyone, Ask for it now as a
request an Admin allows or declines in the Panel, and Enrich now to an
Admin, each writing its row; the summary under a schedule is written from
the transcript and says so; the batch mail says what will happen and a
second message says it did; the exports keep the camera section inside
when the office says so; the upload page's tick reaches the batch.
"""

from __future__ import annotations

import datetime as dt

import pytest
from core import assistant, engine, mail, settings_store, vision
from core.assistant import Summary
from core.audit import Row
from core.cases import Case
from core.models import LoginSession, User
from core.recordings import Batch
from django.utils import timezone
from tests.test_prepare import a_recording, engine_answering, no_ffmpeg

PASSWORD = "a-long-enough-password"


@pytest.fixture
def admin(db):
    return User.objects.create_local_admin("adm", PASSWORD)


@pytest.fixture
def person(db):
    """A directory account, not an Admin: what a Share may name."""
    who = User.objects.create_local_admin("asker", PASSWORD)
    who.is_local = False
    who.display_name = "asker"
    who.last_sign_in = timezone.now()
    who.save()
    return who


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


def a_case_video(owner, tmp_path, settings, title="Cam", ticked=True):
    settings_store.set_to("folder_management", True)
    case, _ = Case.objects.get_or_create(owner=owner, name="Ramirez")
    video = a_recording(owner, tmp_path, settings, case=case, title=title)
    video.vision_wanted = ticked
    video.save(update_fields=["vision_wanted"])
    return case, video


def at(hour, minute=0):
    now = timezone.localtime(timezone.now())
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0)


# Without a database ------------------------------------------------------------------


def test_the_vision_page_holds_the_picture_settings_under_their_groups():
    rows = settings_store.page_settings(settings_store.VISION)
    keys = [one.key for one in rows]
    assert keys[:5] == [
        "moments_available",
        "vision_runs",
        "vision_window_start",
        "vision_window_end",
        "vision_tick_default",
    ]
    groups = []
    for one in rows:
        if one.group not in groups:
            groups.append(one.group)
    assert groups == [
        "Vision",
        "The descriptions",
        "The scan",
        "The record",
        "The digest",
        "The chat",
        "The camera stamp",
        "Exports",
    ]
    for gone in (
        "moment_span_seconds",
        "moment_question_height",
        "moment_question_frames",
    ):
        assert gone not in settings_store.DEFINITIONS
    known = settings_store.DEFINITIONS
    assert known["moments_available"].name == "Vision"
    assert known["moments_answer_tokens"].name == "Description answer cap"
    assert known["vision_runs"].default == "lands"
    assert known["vision_window_start"].needs_value == ("vision_runs", "overnight")
    assert known["exports_camera_section"].default is True
    assert dict(settings_store.PAGES)[settings_store.VISION] == "Vision"


def test_a_window_edge_is_a_clock_time():
    assert settings_store.check("vision_window_start", " 21:30 ") == "21:30"
    for bad in ("9pm", "25:00", "20:60", "2000"):
        with pytest.raises(ValueError):
            settings_store.check("vision_window_end", bad)


# With a database ----------------------------------------------------------------------


@pytest.mark.django_db
def test_the_window_is_read_in_server_time_and_may_cross_midnight():
    settings_store.set_to("vision_window_start", "20:00")
    settings_store.set_to("vision_window_end", "06:00")
    assert vision.in_window(at(21)) and vision.in_window(at(2))
    assert not vision.in_window(at(12)) and not vision.in_window(at(6))
    assert vision.window_words() == "between 20:00 and 06:00"
    settings_store.set_to("vision_window_start", "01:00")
    settings_store.set_to("vision_window_end", "05:00")
    assert vision.in_window(at(3)) and not vision.in_window(at(23))
    assert vision.just_closed(at(5, 1)) and not vision.just_closed(at(5, 30))


@pytest.mark.django_db
def test_a_transcript_lands_into_the_offices_position(
    admin, tmp_path, settings, monkeypatch
):
    from core import tasks

    deferred = []
    monkeypatch.setattr(
        tasks.prepare_video, "defer", lambda **fields: deferred.append(fields)
    )
    case, video = a_case_video(admin, tmp_path, settings)
    session = a_recording(admin, tmp_path, settings, title="Session")
    session.vision_wanted = True
    session.save(update_fields=["vision_wanted"])
    # As each transcript lands: queued now, a session video too.
    assert vision.on_transcript(video) is True
    assert vision.on_transcript(session) is True
    assert len(deferred) == 2
    for one in (video, session):
        one.transcript.refresh_from_db()
        assert one.transcript.prepare_state == assistant.QUEUED
        one.transcript.prepare_state = ""
        one.transcript.save(update_fields=["prepare_state"])
    # Overnight: marked tonight in a case; nothing for the session.
    settings_store.set_to("vision_runs", "overnight")
    assert vision.on_transcript(video) is True
    assert vision.on_transcript(session) is False
    video.transcript.refresh_from_db()
    assert video.transcript.prepare_state == vision.TONIGHT
    assert vision.words(video.transcript) == ("Enriching tonight", "")
    session.transcript.refresh_from_db()
    assert session.transcript.prepare_state == ""
    # Only when asked: nothing runs by itself.
    settings_store.set_to("vision_runs", "asked")
    video.transcript.prepare_state = ""
    video.transcript.save(update_fields=["prepare_state"])
    assert vision.on_transcript(video) is False
    assert vision.words(video.transcript) == ("Not yet enriched with vision", "")
    # Not ticked: nothing, whatever the position.
    settings_store.set_to("vision_runs", "lands")
    video.vision_wanted = False
    video.save(update_fields=["vision_wanted"])
    assert vision.on_transcript(video) is False
    assert len(deferred) == 2


@pytest.mark.django_db
def test_the_night_takes_the_oldest_first_one_at_a_time_and_marks_the_rest(
    admin, tmp_path, settings, monkeypatch
):
    from core import tasks

    deferred = []
    monkeypatch.setattr(
        tasks.prepare_video, "defer", lambda **fields: deferred.append(fields)
    )
    settings_store.set_to("vision_runs", "overnight")
    settings_store.set_to("vision_window_start", "20:00")
    settings_store.set_to("vision_window_end", "06:00")
    case, first = a_case_video(admin, tmp_path, settings, title="First")
    _, second = a_case_video(admin, tmp_path, settings, title="Second")
    for one in (first, second):
        vision.mark_tonight(one.transcript)
    assert vision.ahead_of(second.transcript) == 1
    assert vision.words(second.transcript) == ("Enriching tonight, 1 ahead of it", "")
    # By day: nothing.
    assert vision.mind_the_night(at(12)) == "outside"
    assert not deferred
    # In the window: the oldest is queued; the next tick waits for it.
    assert vision.mind_the_night(at(21)) == "queued"
    first.transcript.refresh_from_db()
    assert first.transcript.prepare_state == assistant.QUEUED
    assert deferred == [{"transcript_id": str(first.transcript.pk)}]
    assert vision.mind_the_night(at(21, 1)) == "busy"
    # Done: the second follows.
    first.transcript.prepare_state = assistant.DONE
    first.transcript.save(update_fields=["prepare_state"])
    assert vision.mind_the_night(at(21, 2)) == "queued"
    assert len(deferred) == 2
    # The window closes with one still waiting: not reached, tonight again.
    second.transcript.prepare_state = vision.TONIGHT
    second.transcript.save(update_fields=["prepare_state"])
    assert vision.mind_the_night(at(6, 1)) == "outside"
    second.transcript.refresh_from_db()
    assert second.transcript.prepare_reason == vision.NOT_REACHED
    assert vision.words(second.transcript) == (
        "Not reached last night; tonight again",
        "",
    )
    assert vision.mind_the_night(at(21, 3)) == "queued"
    # Off, or as each transcript lands: the tick does nothing.
    settings_store.set_to("vision_runs", "lands")
    assert vision.mind_the_night(at(21)) == "off"


@pytest.mark.django_db
def test_the_engine_gone_during_the_night_puts_the_video_back_to_tonight(
    admin, tmp_path, settings, monkeypatch
):
    settings_store.set_to("vision_runs", "overnight")
    case, video = a_case_video(admin, tmp_path, settings)
    no_ffmpeg(monkeypatch)
    monkeypatch.setattr(engine, "is_reachable", lambda: False)
    assert assistant.prepare(video.transcript, asked_by=None) is False
    video.transcript.refresh_from_db()
    assert video.transcript.prepare_state == vision.TONIGHT
    assert video.transcript.prepare_reason == vision.NOT_REACHED
    row = Row.objects.get(event="Video enriched")
    assert row.outcome == "failure" and row.reason_class == "llm_unreachable"


@pytest.mark.django_db
def test_the_case_page_offers_tonight_to_anyone_and_now_to_an_admin(
    admin, person, tmp_path, settings, client, monkeypatch
):
    from core import sharing, tasks

    deferred = []
    monkeypatch.setattr(
        tasks.prepare_video, "defer", lambda **fields: deferred.append(fields)
    )
    settings_store.set_to("vision_runs", "overnight")
    case, video = a_case_video(admin, tmp_path, settings, ticked=False)
    settings_store.set_to("sharing", True)
    sharing.grant(case, person, admin)
    # A collaborator: the line, Enrich tonight and Ask for it now, no Enrich now.
    signed_in(client, person)
    page = client.get(f"/case/{case.pk}").content.decode()
    assert "1 video not yet enriched with vision" in page
    assert "Enrich tonight" in page and "Ask for it now" in page
    assert 'value="now"' not in page
    assert "<th>Vision</th>" in page
    answer = client.post(f"/case/{case.pk}/vision", {"action": "now"})
    assert answer.status_code == 403
    answer = client.post(f"/case/{case.pk}/vision", {"action": "tonight"})
    assert answer.status_code == 302
    video.transcript.refresh_from_db()
    video.refresh_from_db()
    assert video.transcript.prepare_state == vision.TONIGHT and video.vision_wanted
    assert Row.objects.get(event="Vision queued").details["how"] == "tonight"
    page = client.get(f"/case/{case.pk}").content.decode()
    assert "Enriching tonight" in page and "not yet enriched with vision" not in page
    # An Admin: Enrich now queues it at once, tonight or not.
    signed_in(client, admin)
    page = client.get(f"/case/{case.pk}").content.decode()
    assert 'value="now"' in page
    answer = client.post(
        f"/case/{case.pk}/vision", {"action": "now", "recording": str(video.pk)}
    )
    assert answer.status_code == 302
    video.transcript.refresh_from_db()
    assert video.transcript.prepare_state == assistant.QUEUED
    assert deferred == [{"transcript_id": str(video.transcript.pk)}]
    assert Row.objects.filter(event="Vision queued", details__how="now").exists()


@pytest.mark.django_db
def test_a_request_waits_for_an_admin_who_allows_or_declines_it(
    admin, person, tmp_path, settings, client, monkeypatch
):
    from core import sharing, tasks

    deferred = []
    monkeypatch.setattr(
        tasks.prepare_video, "defer", lambda **fields: deferred.append(fields)
    )
    sent = []
    monkeypatch.setattr(mail, "configured", lambda: True)
    monkeypatch.setattr(mail, "notifications_on", lambda: True)
    monkeypatch.setattr(
        mail,
        "send_to_person",
        lambda kind, who, subject, body, **d: (
            sent.append((kind, who.username, subject)) or True
        ),
    )
    admin.email = "adm@example.test"
    admin.save(update_fields=["email"])
    settings_store.set_to("vision_runs", "asked")
    case, video = a_case_video(admin, tmp_path, settings, ticked=False)
    settings_store.set_to("sharing", True)
    sharing.grant(case, person, admin)
    del sent[:]  # the share's own message
    signed_in(client, person)
    answer = client.post(
        f"/case/{case.pk}/vision", {"action": "ask", "why": "Hearing on Monday"}
    )
    assert answer.status_code == 302
    request = vision.VisionRequest.objects.get()
    assert request.state == "waiting" and request.why == "Hearing on Monday"
    assert vision.words(video.transcript) == (
        "Requested now, waiting for an Admin",
        "warn",
    )
    assert sent == [("vision_requested", "adm", sent[0][2])]
    assert "asks for vision now on the case Ramirez" in sent[0][2]
    row = Row.objects.get(event="Vision requested")
    assert "Hearing" not in str(row.details)
    # One open request at a time.
    client.post(f"/case/{case.pk}/vision", {"action": "ask"})
    assert vision.VisionRequest.objects.count() == 1
    # The Admin sees it on the Vision page, with a count in the rail, and allows it.
    signed_in(client, admin)
    page = client.get("/panel/settings/vision").content.decode()
    assert "asks for vision now on" in page and "Hearing on Monday" in page
    assert 'class="cnt warn"' in page
    answer = client.post(
        f"/panel/vision/request/{request.pk}", {"action": "allow", "line": "Go ahead"}
    )
    assert answer.status_code == 302
    request.refresh_from_db()
    assert request.state == "allowed" and request.decided_by == admin
    video.transcript.refresh_from_db()
    assert video.transcript.prepare_state == assistant.QUEUED
    assert len(deferred) == 1
    assert sent[-1][0] == "vision_allowed" and sent[-1][1] == "asker"
    assert Row.objects.filter(event="Vision allowed").exists()
    assert Row.objects.filter(event="Vision queued", details__how="allowed").exists()
    # The work done: the asker is told once.
    video.transcript.prepare_state = assistant.DONE
    video.transcript.save(update_fields=["prepare_state"])
    vision.note_progress(video)
    vision.note_progress(video)
    assert [one[0] for one in sent].count("vision_done") == 1
    # A second request, declined: the row says so with the line, no mail.
    video.transcript.prepare_state = ""
    video.transcript.save(update_fields=["prepare_state"])
    signed_in(client, person)
    client.post(f"/case/{case.pk}/vision", {"action": "ask"})
    second = vision.VisionRequest.objects.exclude(pk=request.pk).get()
    signed_in(client, admin)
    before = len(sent)
    client.post(
        f"/panel/vision/request/{second.pk}",
        {"action": "decline", "line": "Tonight will do"},
    )
    second.refresh_from_db()
    assert second.state == "declined" and len(sent) == before
    assert vision.words(video.transcript) == (
        "Not yet enriched with vision; the request was declined: Tonight will do",
        "",
    )
    assert Row.objects.filter(event="Vision declined").exists()


@pytest.mark.django_db
def test_under_a_schedule_the_summary_is_written_from_the_transcript(
    admin, tmp_path, settings, client, monkeypatch
):
    settings_store.set_to("vision_runs", "overnight")
    case, video = a_case_video(admin, tmp_path, settings)
    asked = engine_answering(monkeypatch, ["Summary: a stop."])
    summary = Summary.objects.create(
        recording=video, asked_by=admin, template_name="Video summary", length="short"
    )
    assistant.write_summary(summary.pk)
    summary.refresh_from_db()
    # One call, the summary's own: nothing prepared, no digest.
    assert summary.state == assistant.DONE and len(asked) == 1
    assert summary.digest_parts == 0
    video.transcript.refresh_from_db()
    assert video.transcript.prepare_state == ""
    signed_in(client, admin)
    state = client.get(f"/recording/{video.pk}/assistant").json()
    assert state["summaries"][0]["written_from"] == "transcript"
    assert state["cue_runs"]["prepare"]["scheduled"] is True
    # Enriched later: the same card says Regenerate takes the vision in.
    video.transcript.prepare_state = assistant.DONE
    video.transcript.save(update_fields=["prepare_state"])
    settings_store.set_to("digests_available", False)
    state = client.get(f"/recording/{video.pk}/assistant").json()
    assert state["summaries"][0]["written_from"] == "transcript_vision"


@pytest.mark.django_db
def test_the_batch_mail_says_what_will_happen_and_a_second_message_says_it_did(
    admin, tmp_path, settings, monkeypatch
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
    settings_store.set_to("vision_runs", "overnight")
    batch = Batch.objects.create(user=admin, email_when_done=True, vision=True)
    settings_store.set_to("folder_management", True)
    case = Case.objects.create(owner=admin, name="Grove Loop")
    video = a_recording(admin, tmp_path, settings, case=case, batch=batch, title="Cam")
    video.vision_wanted = True
    video.save(update_fields=["vision_wanted"])
    vision.mark_tonight(video.transcript)
    # The batch's mail goes at once: tonight is not "still preparing".
    assert mail.batch_finished(batch) is True
    assert sent[0][0] == "batch_finished"
    assert "The 1 video are enriched with vision tonight" in sent[0][2]
    assert "second message" in sent[0][2]
    # The night done: the second message, once.
    video.transcript.prepare_state = assistant.DONE
    video.transcript.save(update_fields=["prepare_state"])
    vision.note_progress(video)
    vision.note_progress(video)
    assert [one[0] for one in sent] == ["batch_finished", "vision_done"]
    assert "Enriched with vision: 1 video" in sent[1][2]
    batch.refresh_from_db()
    assert batch.vision_mail_sent_at is not None


@pytest.mark.django_db
def test_the_upload_page_offers_the_tick_and_the_batch_carries_it(
    admin, tmp_path, settings, client, monkeypatch
):
    from core import uploads, whisperx

    monkeypatch.setattr(whisperx, "is_alive", lambda: True)
    monkeypatch.setattr(uploads, "free_disk_bytes", lambda: 10**15)
    settings_store.set_to("assistant_available", True)
    settings_store.set_to("moments_available", True)
    signed_in(client, admin)
    page = client.get("/upload").content.decode()
    assert 'id="enrich-with-vision" checked' in page
    assert "as each transcript lands" in page
    settings_store.set_to("vision_runs", "overnight")
    settings_store.set_to("vision_tick_default", False)
    page = client.get("/upload").content.decode()
    assert (
        'id="enrich-with-vision"' in page
        and "checked" not in page.split('id="enrich-with-vision"')[1].split(">")[0]
    )
    assert "between 20:00 and 06:00" in page and 'data-needs-case="yes"' in page
    assert "needs a case" in page
    settings_store.set_to("vision_runs", "asked")
    page = client.get("/upload").content.decode()
    assert 'id="enrich-with-vision"' not in page
    settings_store.set_to("vision_runs", "lands")
    tick = vision.tick(admin)
    assert tick["offered"] and not tick["needs_case"]


@pytest.mark.django_db
def test_the_exports_keep_the_camera_section_inside_when_the_office_says(
    admin, tmp_path, settings
):
    from core import exports
    from core.assistant import Moment

    case, video = a_case_video(admin, tmp_path, settings)
    Moment.objects.create(
        transcript=video.transcript,
        at=0.0,
        span_start=0.0,
        span_end=10.0,
        source=Moment.INTERVAL,
        state=assistant.DONE,
        text="A doorway.",
    )
    assert exports.camera_moments(video.transcript)
    assert exports.CAMERA_HEADING in exports.plain_text(video)
    settings_store.set_to("exports_camera_section", False)
    assert exports.camera_moments(video.transcript) == []
    assert exports.CAMERA_HEADING not in exports.plain_text(video)


@pytest.mark.django_db
def test_the_words_for_every_state(admin, tmp_path, settings):
    case, video = a_case_video(admin, tmp_path, settings)
    transcript = video.transcript
    assert vision.words(None) == ("", "")
    transcript.prepare_state = assistant.DONE
    assert vision.words(transcript) == ("Enriched with vision", "ok")
    transcript.prepare_state = assistant.PREPARING
    transcript.prepare_total = 10
    transcript.prepare_done = 4
    assert vision.words(transcript)[0].startswith("Enriching now, 4 of 10")
    transcript.prepare_state = assistant.FAILED
    transcript.prepare_reason = engine.TOO_LONG
    assert vision.words(transcript)[0].startswith("Not enriched: ")
    transcript.prepare_state = ""
    assert vision.words(transcript) == ("Not yet enriched with vision", "")
    settings_store.set_to("picture_record_available", False)
    assert vision.words(transcript) == ("", "")


def test_the_new_settings_and_words_are_in_the_catalogue_and_the_glossary():
    from pathlib import Path

    here = Path(__file__).resolve().parents[2]
    catalogue = (here / "docs" / "spec" / "ADMIN-SETTINGS-CATALOGUE.md").read_text(
        encoding="utf-8"
    )
    for name in (
        "Vision runs",
        "Overnight from",
        "Exports carry what the camera showed",
    ):
        assert name in catalogue
    glossary = (here / "CONTEXT.md").read_text(encoding="utf-8")
    assert "**Vision**:" in glossary and "**Vision request**:" in glossary
    assert isinstance(dt.timedelta(minutes=3), dt.timedelta)
