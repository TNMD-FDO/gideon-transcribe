"""The performance pass (v1.134.0): the pages that had asked a question per
row ask a handful for the whole page, and nothing in a request walks the
disk.

Each test seeds a page at two sizes and counts the queries at both: the
count must sit under the audit's target and must not grow with the rows.
The disk tests make every stat fail and open the page anyway. Every name
here is fictional.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from core import settings_store
from core.cases import Case
from core.jobs import Segment, Transcript
from core.models import User
from core.recordings import Batch, MediaState, Recording
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from tests.helpers import signed_in

PASSWORD = "a long enough password 1"

# A probe with a picture, so that whether a recording is a video is read
# from the row and never from the disk.
VIDEO_PROBE = {
    "format": {"tags": {}},
    "streams": [{"codec_type": "video", "codec_name": "h264", "height": 720}],
}
SOUND_PROBE = {"format": {"tags": {}}, "streams": [{"codec_type": "audio"}]}


@pytest.fixture(autouse=True)
def cases_on(db):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("sharing", True)
    settings_store.set_to("incidents", True)
    settings_store.set_to("clips_available", True)


@pytest.fixture
def owner(db):
    return User.objects.create_local_admin("perf-owner", PASSWORD)


@pytest.fixture
def admin(db):
    return User.objects.create_local_admin("perf-admin", PASSWORD)


def a_recording(
    owner,
    case=None,
    title="a call",
    *,
    batch=None,
    words=True,
    speakers=("Speaker 1", "Speaker 2"),
    video=False,
    stamp=None,
    measured=1024,
):
    recording = Recording.objects.create(
        batch=batch or Batch.objects.create(user=owner),
        user=owner,
        case=case,
        title=title,
        original_filename=f"{title}.{'mp4' if video else 'wav'}",
        media_state=MediaState.READY,
        duration_seconds=600.0,
        playback_ready=True,
        probe=VIDEO_PROBE if video else SOUND_PROBE,
        stamp=stamp,
        on_disk_bytes=measured,
    )
    if words:
        transcript = Transcript.objects.create(recording=recording, language="en")
        for n, speaker in enumerate(speakers):
            Segment.objects.create(
                transcript=transcript,
                start=5.0 * n,
                end=5.0 * n + 4,
                text=f"words from {speaker}",
                speaker=speaker,
                speaker_label=f"SPEAKER_0{n}",
            )
    return recording


def queries_for(client, url: str, **kwargs) -> tuple[int, object]:
    with CaptureQueriesContext(connection) as asked:
        answer = client.get(url, **kwargs)
    assert answer.status_code == 200, answer.status_code
    return len(asked), answer


def no_disk(monkeypatch, *, stats_too: bool = True) -> list:
    """Every walk fails, and every stat under the App data folder is written
    down (pytest's own stats go on): a page that measures the disk cannot
    open, and the list says whether one so much as looked."""
    from django.conf import settings

    touched: list = []
    data = str(settings.DATA_DIR)
    original = Path.stat

    def refuse(self, *args, **kwargs):
        raise AssertionError(f"the request walked the disk: {self}")

    def noted(self, *args, **kwargs):
        if str(self).startswith(data):
            touched.append(str(self))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "rglob", refuse)
    monkeypatch.setattr(Recording, "measure_disk", refuse)
    if stats_too:
        monkeypatch.setattr(Path, "stat", noted)
    return touched


# Home (finding 2) -------------------------------------------------------------


def seed_cases(owner, how_many: int) -> list:
    made = []
    for n in range(how_many):
        case = Case.objects.create(owner=owner, name=f"Matter {n:02d}")
        batch = Batch.objects.create(user=owner)
        for m in range(3):
            one = a_recording(owner, case, f"Call {n}-{m}", batch=batch)
            if m == 0:
                one.assigned_to = owner
                one.save(update_fields=["assigned_to"])
        made.append(case)
    return made


def test_home_asks_a_handful_whatever_the_number_of_cases(owner, client, monkeypatch):
    from core import uploads

    # The person's used bytes are summed per owned case in uploads.used_bytes,
    # which another fixer owns; the figure is held still here so this test
    # measures Home's own questions.
    monkeypatch.setattr(uploads, "used_bytes", lambda user: 0)
    signed_in(client, owner)
    seed_cases(owner, 5)
    at_five, page = queries_for(client, reverse("home"))
    assert page.content.decode().count("Matter ") == 5
    seed_cases(owner, 15)
    at_twenty, page = queries_for(client, reverse("home"))
    assert page.content.decode().count("Matter ") == 20
    assert at_twenty < 60, (at_five, at_twenty)
    assert at_twenty <= at_five + 2, (at_five, at_twenty)


# The disk walks (findings 3 and 31) -------------------------------------------


def still_services(monkeypatch) -> None:
    """The Status page's network checks answered from here, not the office."""
    from core import panel_pages, whisperx

    monkeypatch.setenv("LDAP_ENABLED", "false")
    monkeypatch.setattr(whisperx, "is_alive", lambda lane="": False)
    monkeypatch.setattr(
        panel_pages,
        "_listening",
        lambda name, host, port: {"name": name, "state": "healthy", "says": ""},
    )
    monkeypatch.setattr(
        panel_pages,
        "_reachable",
        lambda name, url: {"name": name, "state": "healthy", "says": ""},
    )
    panel_pages.forget_checks()


def test_the_status_and_users_pages_never_walk_the_disk(
    admin, owner, client, monkeypatch
):
    still_services(monkeypatch)
    case = Case.objects.create(owner=owner, name="Measured matter")
    for n in range(4):
        a_recording(owner, case, f"Kept {n}", measured=2 * 1024**3)
        a_recording(owner, None, f"Session {n}", measured=1024**3)
    binned = Case.objects.create(owner=owner, name="Binned matter")
    a_recording(owner, binned, "Binned", measured=1024**3)
    from django.utils import timezone

    binned.deleted_on = timezone.localdate()
    binned.save(update_fields=["deleted_on"])
    signed_in(client, admin)
    # Every recording measured already: the pages read the kept figures.
    no_disk(monkeypatch, stats_too=False)
    told = client.get(reverse("panel-status-lines")).json()["workspaces"]
    assert told["gigabytes"] == "4.0"
    assert told["cases"] == 1 and told["cases_gigabytes"] == "8.0"
    assert told["binned"] == 1 and told["binned_gigabytes"] == "1.0"
    page = client.get(reverse("panel-users")).content.decode()
    assert "4 in session, 4.0 GB" in page
    assert "5 in cases, 9.0 GB" in page
    # What a Delete would take, from the same figures.
    told = client.get(reverse("what-would-go", args=[case.pk])).json()
    assert told["recordings"] == 4 and told["transcripts"] == 4
    assert told["size"].startswith("8")
    signed_in(client, owner)
    told = client.get(reverse("what-would-go")).json()
    assert told["recordings"] == 4 and told["transcripts"] == 4


def test_the_sign_out_counts_are_two_counts_and_a_sum(owner):
    from core import lifecycle

    for n in range(6):
        a_recording(owner, None, f"Session {n}", measured=1024**3, words=n % 2 == 0)
    with CaptureQueriesContext(connection) as asked:
        told = lifecycle.counts(owner)
    assert told["recordings"] == 6 and told["transcripts"] == 3
    assert told["gigabytes"] == 6.0
    assert len(asked) <= 8, len(asked)


# The batch page's poll (finding 6) ---------------------------------------------


def a_batch_of(owner, how_many: int, *, running: bool = True):
    from core.jobs import Job, JobState, Run
    from core.recordings import Side

    batch = Batch.objects.create(user=owner)
    for n in range(how_many):
        recording = a_recording(
            owner, None, f"Upload {n:02d}", batch=batch, words=False
        )
        side = Side.objects.create(recording=recording, number=1)
        job = Job.objects.create(
            batch=batch,
            recording=recording,
            state=JobState.RUNNING if running else JobState.DONE,
        )
        Run.objects.create(job=job, side=side, state="running", stage="transcribing")
    return batch


def test_the_batch_poll_asks_a_handful_whatever_the_batch(owner, client, monkeypatch):
    from core import pages, whisperx

    asked_the_service = []

    def status(lane="", timeout=None):
        asked_the_service.append(timeout)
        return {"speed": {"minutes_per_minute": 10}}

    monkeypatch.setattr(whisperx, "status", status)
    pages._speed.update({"at": 0.0, "speed": None, "asked": None})
    signed_in(client, owner)
    small = a_batch_of(owner, 5)
    at_five, _ = queries_for(client, reverse("batch-state", args=[small.pk]))
    large = a_batch_of(owner, 25)
    at_many, answer = queries_for(client, reverse("batch-state", args=[large.pk]))
    told = answer.json()
    assert len(told["recordings"]) == 25
    assert told["recordings"][0]["job"]["step"] == "Transcribing"
    assert told["recordings"][0]["sides"] == 1
    assert at_many < 30, (at_five, at_many)
    assert at_many <= at_five + 2, (at_five, at_many)
    # The service was asked once, with a short wait, not on every poll.
    assert asked_the_service == [3]


# The Queue poll (finding 7) ----------------------------------------------------


def test_the_queue_poll_asks_a_handful_at_a_hundred_jobs(admin, owner, client):
    a_batch_of(owner, 100)
    signed_in(client, admin)
    count, answer = queries_for(client, reverse("panel-queue-state"))
    told = answer.json()["jobs"]
    assert len(told) == 100 and told[0]["step"] == "Transcribing"
    assert count < 20, count


def test_the_status_checks_are_kept_for_thirty_seconds(admin, client, monkeypatch):
    from core import panel_pages, whisperx

    still_services(monkeypatch)
    signed_in(client, admin)
    asked = []
    monkeypatch.setattr(whisperx, "status", lambda lane="": asked.append(lane) or {})
    monkeypatch.setenv("COMPOSE_PROFILES", "transcription")
    client.get(reverse("panel-status-lines"))
    client.get(reverse("panel-status-lines"))
    # Three lines read the status, two polls: one question of the service.
    assert asked == [""]
    # A fresh function standing in is asked afresh, and forgetting asks again.
    monkeypatch.setattr(whisperx, "status", lambda lane="": asked.append("again") or {})
    client.get(reverse("panel-status-lines"))
    assert asked == ["", "again"]
    panel_pages.forget_checks()
    client.get(reverse("panel-status-lines"))
    assert asked == ["", "again", "again"]


# People (finding 8) ------------------------------------------------------------


def a_case_of_people(owner, people: int, recordings: int):
    from core.people import Person

    case = Case.objects.create(owner=owner, name="Crowded matter")
    names = [f"Person {n:02d}" for n in range(people)]
    for name in names:
        Person.objects.create(case=case, name=name, role="Witness")
    made = []
    for n in range(recordings):
        # Each recording has two named people and one label still to name.
        speakers = (names[n % people], names[(n + 1) % people], "Speaker 3")
        made.append(a_recording(owner, case, f"Interview {n:03d}", speakers=speakers))
    return case, made


def test_the_viewer_of_a_crowded_case_asks_a_handful(owner, client):
    case, made = a_case_of_people(owner, 15, 20)
    signed_in(client, owner)
    count, answer = queries_for(client, reverse("viewer", args=[made[0].pk]))
    page = answer.content.decode()
    assert "Person 00" in page and "Witness" in page
    assert count < 80, count


def test_the_speakers_tab_asks_a_handful_whatever_the_case(owner, client):
    case, _ = a_case_of_people(owner, 15, 20)
    signed_in(client, owner)
    tab = reverse("case", args=[case.pk]) + "?tab=speakers"
    at_twenty, _ = queries_for(client, tab)
    for n in range(180):
        a_recording(
            owner,
            case,
            f"Later {n:03d}",
            speakers=(f"Person {n % 15:02d}", "Speaker 2"),
        )
    at_two_hundred, answer = queries_for(client, tab)
    page = answer.content.decode()
    assert "15 people, 200 recordings with unnamed speakers" in page
    # The tab's own questions are four; the rest is the case page under it,
    # which reads each setting it needs in a query of its own (twenty-three
    # of them) and counts every feature apart, the English to follow among
    # them since v1.162.0 (one count, whatever the case). Flat is the point
    # here.
    assert at_two_hundred < 95, (at_twenty, at_two_hundred)
    assert at_two_hundred <= at_twenty + 2, (at_twenty, at_two_hundred)


def test_a_persons_recordings_are_two_queries(owner):
    case, made = a_case_of_people(owner, 3, 6)
    person = case.people.get(name="Person 00")
    with CaptureQueriesContext(connection) as asked:
        where = person.recordings()
    assert len(asked) == 2
    assert [one.title for one, _ in where] == [
        "Interview 000",
        "Interview 002",
        "Interview 003",
        "Interview 005",
    ]
    assert where[0][1] == 0.0 and where[1][1] == 5.0


# The case chat poll (finding 9) ------------------------------------------------


def test_the_case_chat_poll_asks_a_handful_at_two_hundred_recordings(
    owner, client, monkeypatch
):
    from core import engine
    from core.case_chat import CaseChat, CaseChatTurn

    settings_store.set_to("assistant_available", True)
    settings_store.set_to("chat_across_cases", True)
    monkeypatch.setattr(engine, "is_reachable", lambda: True)
    case = Case.objects.create(owner=owner, name="Chatty matter")
    made = [
        a_recording(owner, case, f"Call {n:03d}", words=n % 4 != 3) for n in range(200)
    ]
    chat = CaseChat.objects.create(case=case, asked_by=owner)
    for t in range(5):
        citations = {
            f"[Recording {c + 1}, 00:00:0{c}]": {
                "recording": str(made[c].pk),
                "seconds": float(5 * c),
            }
            for c in range(5)
        }
        CaseChatTurn.objects.create(
            chat=chat,
            number=t + 1,
            question="Who called?",
            answer="Pike did " + " ".join(citations),
            citations=citations,
            state="done",
            asked_by=owner,
        )
    signed_in(client, owner)
    count, answer = queries_for(client, reverse("case-chat-state", args=[case.pk]))
    told = answer.json()
    assert told["readable"] == 150 and told["skipped"] == 50
    turns = told["chats"][0]["turns"]
    assert len(turns) == 5
    cited = turns[0]["citations"]["[Recording 2, 00:00:01]"]
    assert cited["line"] == "Speaker 2: words from Speaker 2"
    assert cited["media"].endswith("/playback.m4a")
    assert count < 25, count


# The segments answer without its words (finding 15) ---------------------------


def test_the_segments_answer_leaves_the_words_out_when_asked(owner, client):
    recording = a_recording(owner, None, "Timed")
    line = recording.transcript.segments.first()
    line.words = [{"word": "words", "start": 0.0, "end": 0.5}]
    line.save(update_fields=["words"])
    signed_in(client, owner)
    url = reverse("segments", args=[recording.pk])
    full = client.get(url).json()["segments"]
    assert full[0]["words"] == [{"word": "words", "start": 0.0, "end": 0.5}]
    bare = client.get(url + "?words=0").json()["segments"]
    assert "words" not in bare[0] and bare[0]["text"] == full[0]["text"]
    again = client.get(url + "?words=1").json()["segments"]
    assert again[0]["words"] == full[0]["words"]


# The incident page's state (finding 28) ----------------------------------------


def an_incident(owner, cameras: int, others: int):
    from core import incidents
    from tests.helpers import stamp

    case = Case.objects.create(owner=owner, name="Filmed matter")
    videos = [
        a_recording(
            owner,
            case,
            f"Camera {n}",
            video=True,
            stamp=stamp(f"21:5{n}:00", f"BWC-{n}"),
        )
        for n in range(cameras)
    ]
    for n in range(others):
        a_recording(owner, case, f"Other {n:03d}", video=True, stamp={})
    incident = incidents.make(case, "The stop", videos, by=owner)
    return case, incident


def test_the_incident_state_asks_a_handful_and_the_busy_form_three(
    owner, client, monkeypatch
):
    from core import incident_pages

    case, incident = an_incident(owner, 8, 30)
    signed_in(client, owner)
    touched = no_disk(monkeypatch)
    count, answer = queries_for(client, incident.url() + "/state")
    assert touched == []
    told = answer.json()
    assert len(told["cameras"]) == 8 and len(told["others"]) == 30
    assert told["cameras"][0]["media_url"].endswith("/playback.mp4")
    assert told["cameras"][0]["clock_reading"] is False
    # v1.168.0 reads the Proposal table twice more (the rows waiting and
    # their count), and nothing per camera.
    assert count < 42, count
    with CaptureQueriesContext(connection) as asked:
        busy = incident_pages.busy_json(incident)
    assert busy == {"busy": False} and len(asked) <= 3, len(asked)
    assert client.get(incident.url() + "/state?what=busy").json() == {"busy": False}
    camera = incident.cameras.first()
    camera.match_state = "running"
    camera.save(update_fields=["match_state"])
    assert client.get(incident.url() + "/state?what=busy").json() == {"busy": True}


# The case page (finding 29) ----------------------------------------------------


def test_the_case_page_asks_a_handful_and_never_stats(owner, client, monkeypatch):
    case, incident = an_incident(owner, 8, 0)
    for n in range(192):
        a_recording(owner, case, f"Call {n:03d}")
    signed_in(client, owner)
    touched = no_disk(monkeypatch)
    count, answer = queries_for(client, reverse("case", args=[case.pk]))
    assert touched == []
    assert answer.content.decode().count("Call ") >= 192
    assert count < 100, count
    count, answer = queries_for(
        client, reverse("case", args=[case.pk]) + "?tab=incidents"
    )
    assert touched == []
    page = answer.content.decode()
    assert "The stop" in page and "8 of 8 synced" in page
    assert count < 100, count


# My recordings (finding 30) ----------------------------------------------------


def test_my_recordings_asks_a_handful_at_fifty(owner, client):
    a_batch_of(owner, 25, running=False)
    a_batch_of(owner, 25, running=False)
    signed_in(client, owner)
    count, answer = queries_for(client, reverse("recordings"))
    assert answer.content.decode().count('class="pick"') == 50
    assert count < 25, count


# The audit viewer (finding 32) -------------------------------------------------


def test_the_audit_viewer_filters_on_moments_and_bounds_its_count(admin, client):
    from core import audit

    for n in range(3):
        audit.write(audit.Category.ADMIN, "settings changed", actor=admin, n=n)
    signed_in(client, admin)
    with CaptureQueriesContext(connection) as asked:
        answer = client.get(
            reverse("panel-audit") + "?since=2026-01-01&until=2026-12-31&page=9"
        )
    assert answer.status_code == 200
    sql = "\n".join(one["sql"] for one in asked)
    assert "AT TIME ZONE" not in sql and "::date" not in sql
    assert "LIMIT 10001" in sql
    page = answer.content.decode()
    assert "Page 1 of 1" in page


# The media guard (finding 37) --------------------------------------------------


def test_an_admin_looking_in_is_written_down_once_a_session(admin, owner, client):
    from core.audit import Row

    recording = a_recording(owner, None, "Theirs")
    signed_in(client, admin)
    for _ in range(10):
        answer = client.get(
            reverse("media-auth"),
            HTTP_X_FORWARDED_URI=f"/media/{owner.pk}/{recording.pk}/playback.mp4",
        )
        assert answer.status_code == 200
    rows = Row.objects.filter(event="Playback copy served to an Admin")
    assert rows.count() == 1
    assert rows.get().affected_username == owner.username
