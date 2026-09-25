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
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording
from django.test import Client
from django.urls import reverse

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


def signed_in(client, who):
    client.force_login(who)
    LoginSession.objects.create(user=who, session_key=client.session.session_key)
    return client


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
        assert "What is running, and what needs you" in page
        assert "Kept for a matter, after sign-out" in page
        assert "This session only, then gone" in page
    home_page = client.get(reverse("home")).content.decode()
    assert 'aria-current="page"' in home_page
    assert home_page.index('aria-current="page"') < home_page.index("What is running")
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


def test_needs_you_and_recent_cases(client, ana, cases_on):
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
    assert "Needs you" in page
    needs = page.split("Needs you", 1)[1].split("Recent cases", 1)[0]
    assert "Busy matter" in needs and "1 event to check" in needs
    assert "Quiet matter" not in needs
    recent = page.split("Recent cases", 1)[1]
    assert "Busy matter" in recent and "Quiet matter" in recent
    assert 'id="open-new"' in page and 'id="new-box"' in page
    # Every case is listed, not a capped few.
    for n in range(12):
        Case.objects.create(owner=ana, name=f"Matter {n}")
    page = client.get(reverse("home")).content.decode()
    recent = page.split("Recent cases", 1)[1]
    assert recent.count("Matter ") == 12
    assert "Quiet matter" in recent and "Busy matter" in recent


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
    section = page.split("This session", 1)[1].split("Recent cases", 1)[0]
    assert "session-only" in section and "kept-here" not in section
    assert page.count(home.keep_line()) == 1
    assert "Put a recording in a case to keep it." in page
    settings_store.set_to("folder_management", False)
    page = client.get(reverse("home")).content.decode()
    assert "Recent cases" not in page and "Needs you" not in page
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
    assert "Warehouse" in page and "Shared by ben" in page


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
    assert "## 14. Deferred and ruled out" in spec
    assert not (APP / "templates" / "start.html").exists()
