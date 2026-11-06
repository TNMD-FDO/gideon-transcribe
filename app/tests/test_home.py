"""Home and the rail (Phase 8 chapter 13).

The rules checked here: sign-in lands on Home and an old /start link follows;
Home shows Ready to download for a finished batch of this session until Done
with these, Needs you for a case with something to settle, Running now for a
batch in hand, This session with the keep-or-lose line said once and a cased
recording left out, and every case under Recent cases; the rail carries the
two actions on every page, Record now only under its setting or inside a
case, and both carry the case a person is inside; My recordings groups this
session by batch with each batch's download; the words are in the glossary
and the guide.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from core import chronology, home, incidents, settings_store, sharing
from core.cases import Case
from core.jobs import Job, JobState, Segment, Transcript
from core.models import User
from core.recordings import Batch, MediaState, Recording
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from tests.helpers import signed_in

APP = Path(__file__).resolve().parent.parent
ROOT = APP.parent
PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def its_own_disk(tmp_path, settings, monkeypatch):
    settings.DATA_DIR = tmp_path
    settings.SCRATCH_DIR = tmp_path / "scratch"
    settings.UPLOADS_DIR = tmp_path / "uploads"
    from core import uploads, whisperx

    monkeypatch.setattr(uploads, "free_disk_bytes", lambda: 10**13)
    monkeypatch.setattr(whisperx, "is_alive", lambda lane="": True)


@pytest.fixture
def ana(db):
    return User.objects.create_local_admin("ana", PASSWORD)


@pytest.fixture
def cases_on(db):
    settings_store.set_to("folder_management", True)


def a_recording(
    person, batch, title, *, case=None, state=MediaState.READY, transcript=True
):
    recording = Recording.objects.create(
        batch=batch,
        user=person,
        case=case,
        title=title,
        original_filename=f"{title}.m4a",
        media_state=state,
        duration_seconds=600,
    )
    if transcript:
        made = Transcript.objects.create(recording=recording, language="en")
        Segment.objects.create(
            transcript=made, start=0.0, end=5.0, text="Hello.", speaker="Speaker 1"
        )
        Job.objects.create(batch=batch, recording=recording, state=JobState.DONE)
    return recording


# Landing ---------------------------------------------------------------------------


def test_sign_in_lands_on_home_and_start_follows(client, ana):
    answer = client.post(reverse("sign-in"), {"username": "ana", "password": PASSWORD})
    assert answer.status_code == 302 and answer["Location"] == "/"
    signed_in(client, ana)
    old = client.get(reverse("start"))
    assert old.status_code == 302 and old["Location"] == reverse("home")
    page = client.get(reverse("home")).content.decode()
    assert "Good morning" in page or "Good afternoon" in page or "Good evening" in page
    assert "What do you want to do?" not in page
    # The brand goes home; My recordings is its own page.
    assert 'class="brand" href="/"' in page
    assert 'href="/recordings"' in page
    assert "Uploaded this session" in client.get(reverse("recordings")).content.decode()


# The rail --------------------------------------------------------------------------


def test_the_rail_on_every_page(client, ana, cases_on):
    signed_in(client, ana)
    for where in (
        reverse("home"),
        reverse("recordings"),
        reverse("cases"),
        reverse("upload"),
    ):
        page = client.get(where).content.decode()
        assert '<nav class="rail" aria-label="Main">' in page, where
        assert 'href="/upload"' in page and "Upload files" in page, where
        assert "Your work, your cases, your team" in page
        assert "Kept for a matter, after sign-out" in page
        assert "This session only, then gone" in page
    home_page = client.get(reverse("home")).content.decode()
    assert 'aria-current="page"' in home_page
    assert home_page.index('aria-current="page"') < home_page.index("Your work, your")
    # Record now waits on its setting.
    assert 'href="/record/new"' not in home_page
    settings_store.set_to("live_recording", True)
    settings_store.set_to("dictation", True)
    assert 'href="/record/new"' in client.get(reverse("home")).content.decode()


def test_the_actions_carry_the_case_a_person_is_inside(client, ana, cases_on):
    settings_store.set_to("live_recording", True)
    signed_in(client, ana)
    case = Case.objects.create(owner=ana, name="Stop")
    page = client.get(reverse("case", args=[case.pk])).content.decode()
    assert f'href="/upload?case={case.pk}"' in page
    # Live recording without Record now: Record only inside a case.
    assert f'href="/record/new?case={case.pk}"' in page
    assert 'href="/record/new"' not in client.get(reverse("home")).content.decode()
    # An Admin inside somebody else's case gets neither.
    boss = User.objects.create_local_admin("boss", PASSWORD)
    other = signed_in(__import__("django.test", fromlist=["Client"]).Client(), boss)
    theirs = other.get(reverse("case", args=[case.pk])).content.decode()
    assert f"?case={case.pk}" not in theirs
    # The upload page preselects the case.
    upload = client.get(reverse("upload") + f"?case={case.pk}").content.decode()
    assert (
        f'value="{case.pk}" selected' in upload
        or f'<option value="{case.pk}" selected' in upload
    )


# Home's sections -------------------------------------------------------------------


def test_ready_to_download_until_done_with_these(client, ana):
    signed_in(client, ana)
    batch = Batch.objects.create(user=ana)
    a_recording(ana, batch, "one")
    a_recording(ana, batch, "two")
    a_recording(ana, batch, "three", state=MediaState.FAILED, transcript=False)
    page = client.get(reverse("home")).content.decode()
    assert "Ready to download" in page and "2 transcripts ready" in page
    assert f'href="/batch/{batch.pk}/download"' in page
    assert "1 not transcribed" in page
    assert "1 ready" in page  # the rail's Home item
    assert home.ready_count(ana) == 1
    # My recordings has the same download on the batch's group.
    mine = client.get(reverse("recordings")).content.decode()
    assert (
        f'href="/batch/{batch.pk}/download"' in mine and "2 transcripts ready" in mine
    )
    # Done with these clears it and lands on Home.
    said = client.post(reverse("clear-recordings"), {"batch": str(batch.pk)}).json()
    assert said["where"] == reverse("home")
    page = client.get(reverse("home")).content.decode()
    assert "Ready to download" not in page and home.ready_count(ana) == 0


def test_a_batch_in_a_case_or_still_running_is_not_ready(client, ana, cases_on):
    signed_in(client, ana)
    case = Case.objects.create(owner=ana, name="Stop")
    batch = Batch.objects.create(user=ana)
    a_recording(ana, batch, "cased", case=case)
    assert home.ready_batches(ana) == []
    running = Batch.objects.create(user=ana)
    done = a_recording(ana, running, "done")
    waiting = a_recording(ana, running, "waiting", transcript=False)
    Job.objects.create(batch=running, recording=waiting, state=JobState.QUEUED)
    assert home.ready_batches(ana) == []
    page = client.get(reverse("home")).content.decode()
    assert "Running now" in page and "1 of 2 transcribed" in page
    assert done.title in page
    assert "Ready to download" not in page


def test_the_desk_lists_your_work_and_the_case_rows(client, ana, cases_on):
    settings_store.set_to("incidents", True)
    signed_in(client, ana)
    Case.objects.create(owner=ana, name="Quiet matter")
    busy = Case.objects.create(owner=ana, name="Busy matter")
    batch = Batch.objects.create(user=ana)
    first = a_recording(ana, batch, "first", case=busy)
    first.stamp = {
        "date": "06/07/2025",
        "time": "21:56:19",
        "camera": "BWC2-1",
        "at": 2.0,
        "checked": True,
    }
    first.recording_type = "Body camera"
    first.save()
    incident = incidents.make(busy, "Stop", [first], by=ana)
    chronology.add(
        incident, {"at": "10", "text": "Step out", "to_check": "yes"}, by=ana
    )
    page = client.get(reverse("home")).content.decode()
    # The desk (Phase 13 chapter 1, v1.215.0): no Needs you, no pill on a
    # case's row, no incident line; every case a plain row saying what it
    # holds, the one with an incident counting it.
    assert 'id="needs-you"' not in page and "Needs you" not in page
    assert "1 event to check" not in page and "The rest, by last activity" not in page
    assert f'href="{incident.url()}"' not in page
    rows = page.split('id="cases"', 1)[1]
    assert "Busy matter" in rows and "Quiet matter" in rows
    busy_row = rows.split("Busy matter", 1)[1].split('class="row case-row"', 1)[0]
    assert "1 recording" in busy_row and "1 incident" in busy_row
    assert 'id="open-new"' in page and 'id="new-box"' in page
    # Your work: assigned to the person and not reviewed, with Next and All.
    assert 'id="your-work"' not in page
    first.assigned_to = ana
    first.save(update_fields=["assigned_to"])
    page = client.get(reverse("home")).content.decode()
    work = page.split('id="your-work"', 1)[1].split('id="cases"', 1)[0]
    assert "Busy matter" in work and "1 of 1 left for you" in work
    assert f'href="/recording/{first.pk}"' in work and "Next: first" in work
    assert f"/case/{busy.pk}?who=me&amp;state=unreviewed" in work and "All 1" in work
    first.reviewed_by = ana
    first.reviewed_on = timezone.now()
    first.save(update_fields=["reviewed_by", "reviewed_on"])
    assert 'id="your-work"' not in client.get(reverse("home")).content.decode()
    # Every case is listed, not a capped few.
    for n in range(12):
        Case.objects.create(owner=ana, name=f"Matter {n}")
    page = client.get(reverse("home")).content.decode()
    assert page.split('id="cases"', 1)[1].count("Matter ") == 12


def test_this_session_says_the_rule_once_and_leaves_cased_recordings_out(
    client, ana, cases_on
):
    signed_in(client, ana)
    case = Case.objects.create(owner=ana, name="Stop")
    batch = Batch.objects.create(user=ana)
    a_recording(ana, batch, "kept-here", case=case)
    a_recording(
        ana, batch, "session-only", transcript=False, state=MediaState.PREPARING
    )
    page = client.get(reverse("home")).content.decode()
    section = page.split('id="this-session"', 1)[1]
    assert "session-only" in section and "kept-here" not in section
    assert page.count(home.keep_line()) == 1
    assert "Put a recording in a case to keep it." in page
    # Cases stand before This session (v1.115.0: the left column).
    assert page.index('id="cases"') < page.index('id="this-session"')
    settings_store.set_to("folder_management", False)
    page = client.get(reverse("home")).content.decode()
    assert 'id="cases"' not in page and "Needs you" not in page
    assert "Export anything you want to keep." in page


def test_an_admin_who_owns_nothing_sees_the_office_line(client, cases_on):
    boss = User.objects.create_local_admin("boss", PASSWORD)
    other = User.objects.create_local_admin("other", PASSWORD)
    Case.objects.create(owner=other, name="Theirs")
    signed_in(client, boss)
    page = client.get(reverse("home")).content.decode()
    assert "None of yours yet; 1 case in the office" in page
    assert 'href="/cases?who=everyone"' in page


def test_a_shared_case_shows_who_shared_it(client, ana, cases_on):
    settings_store.set_to("sharing", True)
    ben = User.objects.create_local_admin("ben", PASSWORD)
    case = Case.objects.create(owner=ben, name="Warehouse")
    sharing.grant(case, ana, ben)
    signed_in(client, ana)
    page = client.get(reverse("home")).content.decode()
    assert "Warehouse" in page and "shared with you by ben" in page
    assert '<span class="pill small acc">new</span>' in page
    # The owner's row names the colleagues.
    other = Client()
    signed_in(other, ben)
    page = other.get(reverse("home")).content.decode()
    assert "shared with ana" in page


def test_your_team_lately_reads_the_records_and_seen_folds_it(client, ana, cases_on):
    """Phase 13 chapter 1: what colleagues did in the shared cases, from the
    reviewed, noted, added, shared and asked records; the person's own acts
    never; Seen folds it until something newer happens; an office of one
    sees nothing."""
    from core.case_chat import CaseChat, CaseChatTurn
    from core.notes import MomentNote

    settings_store.set_to("sharing", True)
    signed_in(client, ana)
    assert 'id="team-lately"' not in client.get(reverse("home")).content.decode()
    ben = User.objects.create_local_admin("ben", PASSWORD)
    ben.display_name = "Ben Okonkwo"
    ben.save(update_fields=["display_name"])
    case = Case.objects.create(owner=ben, name="Warehouse")
    sharing.grant(case, ana, ben)
    batch = Batch.objects.create(user=ben)
    now = timezone.now()
    call = a_recording(ben, batch, "call 0417", case=case)
    call.reviewed_by = ben
    call.reviewed_on = now
    call.save(update_fields=["reviewed_by", "reviewed_on"])
    MomentNote.objects.create(
        recording=call, at=10.0, note="Check this", note_by=ben, note_changed=now
    )
    MomentNote.objects.create(
        recording=call, at=20.0, note="And this", note_by=ben, note_changed=now
    )
    # The person's own note is never listed.
    MomentNote.objects.create(
        recording=call, at=30.0, note="Mine", note_by=ana, note_changed=now
    )
    chat = CaseChat.objects.create(case=case, asked_by=ben, name="Phone?")
    CaseChatTurn.objects.create(
        chat=chat, number=1, question="When was the phone handed over?", asked_by=ben
    )
    page = client.get(reverse("home")).content.decode()
    team = page.split('id="team-lately"', 1)[1]
    assert (
        " open>" in page.split('id="team-lately"', 1)[0][-40:] + team[:1]
        or 'id="team-lately" open' in page
    )
    assert "Ben Okonkwo" in team and "Warehouse" in team
    assert "reviewed 1 recording and left 2 notes and added 1 recording in" in team
    assert "shared" in team and "with you" in team
    assert "asked Gideon about" in team and "When was the phone handed over?" in team
    assert "Mine" not in team and "today," in team
    assert team.count('class="who"') == 3
    # Seen folds it, and keeps nothing but the time on the account.
    told = client.post(reverse("home-team-seen"))
    assert told.status_code == 302
    ana.refresh_from_db()
    assert ana.team_seen_on is not None
    page = client.get(reverse("home")).content.decode()
    assert (
        'id="team-lately" open' not in page and "Nothing new since you looked" in page
    )
    # Something newer opens it again.
    later = timezone.now()
    MomentNote.objects.create(
        recording=call, at=40.0, note="Newer", note_by=ben, note_changed=later
    )
    page = client.get(reverse("home")).content.decode()
    assert 'id="team-lately" open' in page
    # The greeting names the person.
    assert ", ana</h1>" in page or ", Ana" in page


def test_my_recordings_lists_the_workspace_alone(client, ana, cases_on):
    """A batch that went into a case is listed with the case, not on My
    recordings (v1.86.1); the Admin's view of somebody's workspace shows the
    same rows, grouped, and never Done with these."""
    signed_in(client, ana)
    case = Case.objects.create(owner=ana, name="Stop")
    kept = Batch.objects.create(user=ana)
    a_recording(ana, kept, "case-upload", case=case)
    mine = Batch.objects.create(user=ana)
    a_recording(ana, mine, "session-upload")
    page = client.get(reverse("recordings")).content.decode()
    assert "session-upload" in page and f'data-batch="{mine.pk}"' in page
    assert "case-upload" not in page and f'data-batch="{kept.pk}"' not in page
    assert "Done with these" in page
    boss = User.objects.create_local_admin("boss", PASSWORD)
    other = signed_in(Client(), boss)
    theirs = other.get(f"/panel/users/{ana.username}/workspace").content.decode()
    assert "session-upload" in theirs and f'data-batch="{mine.pk}"' in theirs
    assert f'href="/batch/{mine.pk}/download"' in theirs
    assert "case-upload" not in theirs and "Done with these" not in theirs


# The words --------------------------------------------------------------------------


def test_the_words_are_in_the_glossary_the_guide_and_the_spec():
    glossary = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    for word in ("**Home**:", "**Rail**:", "**Ready to download**:"):
        assert word in glossary, word
    assert "_Avoid_: home, dashboard" not in glossary
    guide = (ROOT / "docs" / "user-guide.md").read_text(encoding="utf-8")
    assert "You land on Home" in guide and "rail" in guide
    assert "Ready to download" in guide and "Done with these" in guide
    spec = (ROOT / "docs" / "spec" / "SPEC-PHASE-8.md").read_text(encoding="utf-8")
    assert "## 13. One home and the rail" in spec
    assert "## 15. Deferred and ruled out" in spec
    assert not (APP / "templates" / "start.html").exists()
