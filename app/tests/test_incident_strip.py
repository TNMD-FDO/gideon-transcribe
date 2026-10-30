"""The Incidents tab as a strip (Phase 10 chapter 5, v1.180.0).

The days with a video on the clock and their counts in one pass; the day
read for the strip (the ruler fitted to the videos, every run of overlapping
videos kept with its key, the faint ones and the declined ones marked); the
strip's JSON; the tab's page with its lead, its host, its cards and the
folded videos; Not these from the strip answering JSON by the offer's key;
the Notes tab's chronology unchanged.
"""

from __future__ import annotations

import datetime as dt

import pytest
from core import case_chronology, incident_strip, incidents, settings_store
from core.cases import Case
from core.models import User
from core.notes import MomentNote
from core.recordings import Batch, MediaState, Recording
from tests.helpers import signed_in

PASSWORD = "a-long-enough-password"
DAY = dt.date(2025, 11, 6)


@pytest.fixture(autouse=True)
def switches(db):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("incidents", True)


@pytest.fixture
def owner(db):
    return User.objects.create_local_admin("strip-owner", PASSWORD)


@pytest.fixture
def a_case(owner):
    return Case.objects.create(owner=owner, name="Harbour Street stop")


def a_video(owner, case, title, time, *, seconds=1800.0, checked=True):
    return Recording.objects.create(
        batch=Batch.objects.create(user=owner),
        user=owner,
        case=case,
        title=title,
        original_filename=f"{title}.mp4",
        media_state=MediaState.READY,
        duration_seconds=seconds,
        recording_type="Body camera",
        stamp={"date": "11/06/2025", "time": time, "at": 2.0, "checked": checked},
        probe={"streams": [{"codec_type": "video"}]},
    )


def a_note(owner, recording, at):
    return MomentNote.objects.create(
        recording=recording, at=at, note="a note", note_by=owner
    )


@pytest.fixture
def three_cameras(owner, a_case):
    one = a_video(owner, a_case, "BWC1-1", "20:24:38")
    two = a_video(owner, a_case, "BWC2-1", "20:26:10")
    three = a_video(owner, a_case, "BWC3-1", "20:40:00")
    return one, two, three


def test_the_days_count_videos_notes_and_forming_in_one_pass(
    owner, a_case, three_cameras
):
    one, two, three = three_cameras
    # Three videos on the day, no notes: a run with no notes forms nothing.
    days = incident_strip.days(a_case)
    assert [d["date"] for d in days] == ["2025-11-06"]
    assert days[0]["videos"] == 3 and days[0]["notes"] == 0
    assert days[0]["forming"] == 0
    # Two notes under the overlap: one forming.
    a_note(owner, one, 120.0)
    a_note(owner, two, 300.0)
    days = incident_strip.days(a_case)
    assert days[0]["notes"] == 2 and days[0]["forming"] == 1
    assert incident_strip.forming_count(a_case) == 1
    # Not these, by the offer's key for the same three videos: forming no more.
    key = incidents.offer_key([one.pk, two.pk, three.pk])
    incidents.decline(a_case, key)
    a_case.refresh_from_db()
    assert incident_strip.days(a_case)[0]["forming"] == 0
    # A lone video on another day is a day with no forming; the tab opens on
    # the day with the most forming, then the most notes, then the latest.
    later = a_video(owner, a_case, "Dash-4", "09:00:00")
    later.stamp = {**later.stamp, "date": "11/07/2025"}
    later.save(update_fields=["stamp"])
    days = incident_strip.days(a_case)
    assert [(d["date"], d["videos"], d["forming"]) for d in days] == [
        ("2025-11-06", 3, 0),
        ("2025-11-07", 1, 0),
    ]
    assert incident_strip.pick_day(days) == DAY
    assert incident_strip.pick_day([]) is None


def test_the_strip_reading_keeps_every_run_with_its_key(owner, a_case, three_cameras):
    one, two, three = three_cameras
    # A fourth video alone later in the evening, and a note on the first.
    a_video(owner, a_case, "Dash-4", "22:30:00")
    a_note(owner, one, 120.0)
    strip = case_chronology.day_of(a_case, DAY, strip=True)
    # The ruler fits the videos, so the evening video is on the strip.
    assert strip["ruler"]["to"] >= 22 * 3600 + 30 * 60 + 1798
    # The forming run: three cameras, one note, keyed, not faint, not declined.
    runs = strip["hints"]
    assert len(runs) == 1
    assert runs[0]["cameras"] == 3 and runs[0]["notes"] == 1
    assert runs[0]["ids"] == sorted(str(pk) for pk in (one.pk, two.pk, three.pk))
    assert runs[0]["key"] == incidents.offer_key(runs[0]["ids"])
    assert runs[0]["faint"] is False and runs[0]["declined"] is False
    # Two more overlapping with no notes: a faint run on the strip, and none
    # on the Notes tab's chronology, which is as it was.
    a_video(owner, a_case, "Cell-5", "23:05:00")
    a_video(owner, a_case, "Cell-6", "23:10:00")
    strip = case_chronology.day_of(a_case, DAY, strip=True)
    assert [run["faint"] for run in strip["hints"]] == [False, True]
    assert strip["hints"][1]["words"].startswith("2 cameras, 0 notes, 23:04 to ")
    notes_tab = case_chronology.day_of(a_case, DAY)
    assert len(notes_tab["hints"]) == 1 and "faint" in notes_tab["hints"][0]
    # Declined: marked, still drawn.
    incidents.decline(a_case, runs[0]["key"])
    a_case.refresh_from_db()
    strip = case_chronology.day_of(a_case, DAY, strip=True)
    assert strip["hints"][0]["declined"] is True
    # Two of the three made an incident: they form nothing more, and the
    # third alone is no run; the Notes tab's own bracket still counts them.
    start = 20 * 3600 + 24 * 60 + 36
    case_chronology.make_incident(
        a_case, DAY, (start, start + 1800), "Stop", [one, two], by=owner
    )
    strip = case_chronology.day_of(a_case, DAY, strip=True)
    assert [run["cameras"] for run in strip["hints"]] == [2]
    assert strip["hints"][0]["faint"] is True
    assert incident_strip.days(a_case)[0]["forming"] == 0
    assert len(case_chronology.day_of(a_case, DAY)["hints"]) == 1


def test_the_strip_json_and_the_tab(owner, a_case, three_cameras, client):
    one, two, three = three_cameras
    a_note(owner, one, 120.0)
    signed_in(client, owner)
    told = client.get(f"/case/{a_case.pk}/incidents/strip.json").json()
    assert told["days"][0]["forming"] == 1 and told["day"]["date"] == "2025-11-06"
    assert told["may_make"] is True and told["most"] == incidents.most_cameras()
    assert told["day"]["hints"][0]["key"].startswith("new:")
    # A day asked for.
    told = client.get(f"/case/{a_case.pk}/incidents/strip.json?day=2025-11-07").json()
    assert told["day"]["date"] == "2025-11-07" and told["day"]["bars"] == []
    # The tab: the lead counts the forming, the strip's host carries its
    # addresses, the clocks' offer is a card with its key, the videos fold
    # closed because every video is on the clock.
    page = client.get(f"/case/{a_case.pk}?tab=incidents").content.decode()
    assert "No incident yet, 1 forming." in page
    assert 'id="incident-strip"' in page and 'data-mode="strip"' in page
    assert f"/case/{a_case.pk}/incidents/strip.json" in page
    assert 'id="forming-cards"' in page
    key = incidents.offer_key([one.pk, two.pk, three.pk])
    assert f'data-key="{key}"' in page
    assert '<details class="mt18" id="case-videos">' in page
    assert "Videos in this case · 3" in page
    # A video with no clock and no incident opens the fold.
    Recording.objects.create(
        batch=Batch.objects.create(user=owner),
        user=owner,
        case=a_case,
        title="Interview room",
        original_filename="Interview room.mp4",
        media_state=MediaState.READY,
        duration_seconds=600.0,
        recording_type="Body camera",
        probe={"streams": [{"codec_type": "video"}]},
    )
    page = client.get(f"/case/{a_case.pk}?tab=incidents").content.decode()
    assert '<details class="mt18" id="case-videos" open>' in page


def test_not_these_from_the_strip_answers_json(owner, a_case, three_cameras, client):
    one, two, three = three_cameras
    signed_in(client, owner)
    key = incidents.offer_key([one.pk, two.pk, three.pk])
    answer = client.post(
        f"/case/{a_case.pk}/incidents/decline",
        {"key": key},
        HTTP_ACCEPT="application/json",
    )
    assert answer.status_code == 200 and answer.json() == {"ok": True}
    a_case.refresh_from_db()
    assert key in a_case.declined_offers
    # The offer's own form lands back on the Incidents tab.
    answer = client.post(f"/case/{a_case.pk}/incidents/decline", {"key": key})
    assert answer.status_code == 302 and answer["Location"].endswith("?tab=incidents")
