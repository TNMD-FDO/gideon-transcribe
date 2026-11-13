"""v1.239.0: Usage (Phase 13 chapter 3).

The rules checked here: a month's numbers are counted from the Jobs, the
Recordings and the audit log, each Recording once; people are counted and
never kept; a count never goes down when a Case is swept, a level is the
newest and a typical figure is the one worked out from more; the first count
reaches back over what the server still holds and tells those months apart;
the parts that write no audit row are counted from marks that are deleted
once their month is final; the Panel's Usage page is the Admins' alone,
shows counts and never a name, and opening it writes no audit row.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from core import audit, settings_store, tasks, usage
from core.audit import Row
from core.cases import Case
from core.jobs import Job, JobState, Transcript
from core.models import User
from core.recordings import Batch, MediaState, Recording
from core.usage import UsageMark, UsageMonth
from django.urls import reverse
from django.utils import timezone
from tests.helpers import signed_in

PASSWORD = "a-long-enough-password"


@pytest.fixture
def admin(db):
    return User.objects.create_local_admin("asker", PASSWORD)


@pytest.fixture
def person(db):
    return User.objects.create(username="ana", display_name="Ana Alvarez")


@pytest.fixture
def a_case(admin):
    return Case.objects.create(owner=admin, name="Riverside matter")


def midmonth(months_back: int = 0):
    """Noon on the tenth of this month, or of one so many months back."""
    month = usage.this_month()
    for _ in range(months_back):
        month = usage.before(month)
    start, _end = usage.span(month)
    return start + timedelta(days=9, hours=12)


def transcribed(
    owner,
    case,
    title,
    *,
    seconds=1800.0,
    kind="",
    language="en",
    translate=False,
    when=None,
    waited=600,
):
    """A Recording with a finished Job, as the count reads them."""
    when = when or timezone.now()
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=owner),
        user=owner,
        case=case,
        title=title,
        original_filename=f"{title}.mp4",
        media_state=MediaState.READY,
        duration_seconds=seconds,
        recording_type=kind,
        translate=translate,
        probe={},
    )
    Transcript.objects.create(recording=recording, language=language)
    job = Job.objects.create(
        recording=recording, batch=recording.batch, state=JobState.DONE
    )
    Job.objects.filter(pk=job.pk).update(
        created=when - timedelta(seconds=waited), finished=when
    )
    return recording


def row_at(when, *args, **kwargs):
    row = audit.write(*args, **kwargs)
    Row.objects.filter(pk=row.pk).update(at=when)
    return row


def asked(actor, case, feature="case_chat_turn", *, ok=True, took=20.0, when=None):
    return row_at(
        when or timezone.now(),
        audit.Category.LLM,
        "AI assistant call",
        actor=actor,
        outcome=audit.Outcome.SUCCESS if ok else audit.Outcome.FAILURE,
        reason_class="" if ok else "llm_too_long",
        object_type="case",
        object_id=case.pk,
        object_label=case.name,
        feature=feature,
        duration_seconds=took,
    )


# The count ---------------------------------------------------------------------


def test_a_month_counts_each_recording_once_with_its_hours(admin, a_case):
    now = timezone.now()
    one = transcribed(admin, a_case, "Camera 1", seconds=3600, kind="Body camera")
    transcribed(admin, a_case, "Call", seconds=1800, kind="Jail call", waited=120)
    transcribed(admin, a_case, "Interview", seconds=1800, language="es", translate=True)
    # Processed again in the same month: still one Recording, one hour.
    again = Job.objects.create(recording=one, batch=one.batch, state=JobState.DONE)
    Job.objects.filter(pk=again.pk).update(
        created=now - timedelta(seconds=60), finished=now
    )
    # A speakers pass and a failed run are not a transcription.
    Job.objects.create(
        recording=one, batch=one.batch, state=JobState.DONE, kind="speakers"
    )
    counts = usage.count(usage.this_month())
    assert counts["recordings"] == 3
    assert counts["seconds"] == 7200
    assert counts["types"] == {"Body camera": 3600, "Jail call": 1800, "": 1800}
    assert counts["languages"] == {"en": 5400, "es": 1800}
    assert counts["translated_seconds"] == 1800
    assert counts["waits"] == 4
    assert counts["wait_longest"] == 600
    assert counts["wait_typical"] == 360


def test_a_job_finished_last_month_is_last_months(admin, a_case):
    transcribed(admin, a_case, "Old", seconds=600, when=midmonth(1))
    assert usage.count(usage.this_month())["recordings"] == 0
    assert usage.count(usage.before(usage.this_month()))["recordings"] == 1


def test_people_and_cases_are_counted_from_the_audit_log(admin, person, a_case):
    other = Case.objects.create(owner=person, name="Second matter")
    recording = transcribed(person, other, "Camera 2")
    asked(admin, a_case)
    asked(admin, a_case, took=40.0)
    asked(person, a_case, "summary", ok=False)
    audit.write(
        audit.Category.EDITS,
        "Note added",
        actor=person,
        object_type="recording",
        object_id=recording.pk,
        object_label=recording.title,
    )
    audit.write(audit.Category.SYSTEM, "daily sweeper ran", system="sweeper")
    counts = usage.count(usage.this_month())
    # Two people, and the sweeper is nobody.
    assert counts["people"] == 2
    # The case named on a row, and the case that holds the recording on one.
    assert counts["cases"] == 2
    assert counts["parts"]["chat"] == 1
    assert counts["parts"]["notes"] == 1
    assert counts["parts"]["clips"] == 0
    assert counts["ai"] == {"chat": 2, "summary": 1}
    assert counts["ai_failed"] == 1
    assert counts["ai_reasons"] == {"llm_too_long": 1}
    assert counts["chat_typical"] == 30


def test_the_levels_are_only_for_the_month_being_lived_in(admin, a_case):
    assert "accounts" in usage.count(usage.this_month())
    assert "disk_held" in usage.count(usage.this_month())
    earlier = usage.count(usage.before(usage.this_month()))
    assert "accounts" not in earlier and "disk_held" not in earlier


# What is kept ------------------------------------------------------------------


def test_a_count_never_goes_down_and_a_level_is_the_newest():
    old = {
        "recordings": 10,
        "seconds": 36000,
        "types": {"Body camera": 30000, "Jail call": 6000},
        "waits": 10,
        "wait_typical": 300,
        "disk_held": 500,
        "accounts": 12,
    }
    new = {
        "recordings": 7,
        "seconds": 40000,
        "types": {"Body camera": 20000, "Interview": 900},
        "waits": 7,
        "wait_typical": 90,
        "disk_held": 420,
        "accounts": 11,
    }
    kept = usage.merged(old, new)
    assert kept["recordings"] == 10
    assert kept["seconds"] == 40000
    assert kept["types"] == {"Body camera": 30000, "Jail call": 6000, "Interview": 900}
    # The typical wait was worked out from more waits before the sweep.
    assert kept["wait_typical"] == 300 and kept["waits"] == 10
    # A level is what it is today.
    assert kept["disk_held"] == 420 and kept["accounts"] == 11


def test_a_swept_case_does_not_change_the_month(admin, a_case):
    transcribed(admin, a_case, "Camera 1", seconds=3600)
    transcribed(admin, a_case, "Camera 2", seconds=3600)
    usage.tally()
    Recording.objects.filter(title="Camera 2").delete()
    usage.tally()
    row = UsageMonth.objects.get(month=usage.this_month())
    assert row.counts["recordings"] == 2 and row.counts["seconds"] == 7200


def test_the_first_count_reaches_back_and_tells_those_months_apart(admin, a_case):
    transcribed(admin, a_case, "Long ago", seconds=600, when=midmonth(3))
    transcribed(admin, a_case, "Now", seconds=600)
    done = usage.tally()
    months = list(UsageMonth.objects.values_list("month", flat=True))
    three_back = usage.before(usage.before(usage.before(usage.this_month())))
    # The month with work and this month; the empty months between are not rows.
    assert months == [three_back, usage.this_month()]
    assert done["months"] == 2
    shown = usage.page(usage.ALL)
    assert shown["late"] is True
    late = [one for one in shown["months"] if one["late"]]
    assert len(late) == 1 and late[0]["figure"] == "0"
    # The second night counts this month and last, and only those.
    assert usage.tally()["months"] == 1
    assert UsageMonth.objects.count() == 2


def test_nothing_held_makes_one_row_for_this_month(db):
    usage.tally()
    assert list(UsageMonth.objects.values_list("month", flat=True)) == [
        usage.this_month()
    ]


# The marks ---------------------------------------------------------------------


def test_a_mark_is_kept_once_a_month_and_only_for_the_parts_without_rows(person):
    usage.seen(person, usage.MAP)
    usage.seen(person, usage.MAP)
    usage.seen(person, usage.SEARCH)
    usage.seen(person, "chat")  # the audit log already says
    usage.seen(None, usage.MAP)
    assert UsageMark.objects.count() == 2
    assert usage.count(usage.this_month())["parts"]["map"] == 1


def test_old_marks_are_deleted_once_their_month_is_final(person):
    month = usage.this_month()
    last = usage.before(month)
    UsageMark.objects.create(month=usage.before(last), part=usage.MAP, user=person)
    UsageMark.objects.create(month=last, part=usage.MAP, user=person)
    UsageMark.objects.create(month=month, part=usage.MAP, user=person)
    assert usage.tally()["marks_removed"] == 1
    assert sorted(UsageMark.objects.values_list("month", flat=True)) == [last, month]


def test_a_search_in_a_case_leaves_a_mark(client, admin, a_case):
    settings_store.set_to("folder_management", True)
    signed_in(client, admin)
    client.get(reverse("case", args=[a_case.pk]))
    assert not UsageMark.objects.exists()
    client.get(reverse("case", args=[a_case.pk]) + "?q=licence")
    assert list(UsageMark.objects.values_list("part", flat=True)) == [usage.SEARCH]


# The nightly step ---------------------------------------------------------------


def test_the_nightly_task_counts_only_at_half_past_three(db, monkeypatch):
    monkeypatch.setattr(tasks, "_not_half_past_three", lambda: True)
    tasks.count_usage(0)
    assert not UsageMonth.objects.exists()
    monkeypatch.setattr(tasks, "_not_half_past_three", lambda: False)
    tasks.count_usage(0)
    assert UsageMonth.objects.count() == 1


# The page ----------------------------------------------------------------------


def test_the_page_is_the_admins_alone(client, person):
    signed_in(client, person)
    answer = client.get(reverse("panel-usage"))
    assert answer.status_code == 302 and answer.url == reverse("home")


def test_before_the_first_count_the_page_says_so(client, admin):
    signed_in(client, admin)
    page = client.get(reverse("panel-usage")).content.decode()
    assert "Nothing has been counted yet" in page
    assert 'href="/panel/usage"' in page  # the rail lists it


def test_the_page_shows_counts_and_never_a_name(client, admin, person, a_case):
    transcribed(person, a_case, "Camera 7 Okafor", seconds=7200, kind="Body camera")
    transcribed(admin, a_case, "Front desk call", seconds=1800, kind="Jail call")
    asked(person, a_case)
    usage.tally()
    signed_in(client, admin)
    before = Row.objects.count()
    page = client.get(reverse("panel-usage") + "?period=month").content.decode()
    # Opening it is no reading of anybody's work: no audit row.
    assert Row.objects.count() == before
    assert "2.5 h" in page and "of recordings transcribed" in page
    assert "Body camera" in page and "Jail call" in page
    assert "Chat questions" in page
    assert "Copy the figures" in page
    assert "Recordings transcribed: 2 (2.5 h)" in page
    for word in ("Riverside", "Okafor", "Front desk", "Ana Alvarez", "ana"):
        # The Admin's own name is in the page's furniture; nobody else's is.
        assert word not in page.split('<section class="panel-page')[1], word


def test_people_are_a_typical_month_over_a_longer_period(admin, person, a_case):
    asked(admin, a_case, when=midmonth(2))
    asked(person, a_case, when=midmonth(2))
    asked(admin, a_case, when=midmonth(1))
    asked(admin, a_case, when=midmonth(1), feature="summary")
    asked(person, a_case, when=midmonth(1))
    asked(admin, a_case)
    usage.tally()
    year = usage.page(usage.TWELVE)
    assert year["tiles"][2]["figure"] == "2"
    assert "typical month" in year["tiles"][2]["words"]
    # Until a whole month has been counted as it was lived, the parts are the
    # month so far: an earlier month has no marks for the Map or a search.
    assert year["parts_month"] == f"{usage.this_month():%B %Y} so far"
    # Once one has, the parts are the last whole month's, named.
    UsageMonth.objects.update(first_counted=midmonth(3))
    year = usage.page(usage.TWELVE)
    last = usage.before(usage.this_month())
    assert year["parts_month"] == f"{last:%B %Y}"
    chat = next(one for one in year["parts"] if one["words"] == "Chat")
    assert chat["figure"] == "2 people"
    month = usage.page(usage.MONTH)
    assert month["tiles"][2]["figure"] == "1"
    assert month["tiles"][2]["words"] == "people used the app"


def test_the_disk_grows_by_the_months_counted(db):
    month = usage.this_month()
    gb = 1024**3
    floor = settings_store.minimum_free_disk_bytes()
    for back, held in ((2, 100 * gb), (1, 110 * gb), (0, 120 * gb)):
        at = month
        for _ in range(back):
            at = usage.before(at)
        UsageMonth.objects.create(
            month=at,
            counts={
                "disk_held": held,
                "disk_total": 1000 * gb,
                "disk_free": floor + 120 * gb,
            },
        )
    disk = usage.page(usage.TWELVE)["disk"]
    assert disk["held"] == "120 GB" and disk["growth"] == "10 GB"
    assert disk["room"] == "about 12 months"


def test_the_words_for_sizes_and_waits():
    assert usage.hours(9000) == "2.5 h"
    assert usage.hours(4622400) == "1,284 h"
    assert usage.length(24) == "24 s"
    assert usage.length(540) == "9 min"
    assert usage.length(11400) == "3 h 10 min"
    assert usage.size(1.9 * 1024**4) == "1.9 TB"
