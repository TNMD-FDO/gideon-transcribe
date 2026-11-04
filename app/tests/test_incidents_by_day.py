"""The same day on the Incidents tab (Phase 10 chapter 5, v1.184.0).

The strip's reading suggests the day's loose videos in no forming bracket
together, two or more, or one beside an incident or a forming one, keyed
like the offers and put away by Its own matter; the picker lists the day's
loose videos outside the span last and unticked; the days carry the
together mark on the strip's chips and the Notes tab's Date strip; the lead
counts the days to look at.
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
    return User.objects.create_local_admin("day-owner", PASSWORD)


@pytest.fixture
def a_case(owner):
    return Case.objects.create(owner=owner, name="Harbour Street stop")


def a_video(owner, case, title, time, *, seconds=1800.0):
    return Recording.objects.create(
        batch=Batch.objects.create(user=owner),
        user=owner,
        case=case,
        title=title,
        original_filename=f"{title}.mp4",
        media_state=MediaState.READY,
        duration_seconds=seconds,
        recording_type="Body camera",
        stamp={"date": "11/06/2025", "time": time, "at": 2.0, "checked": True},
        probe={"streams": [{"codec_type": "video"}]},
    )


def test_the_same_day_is_suggested_keyed_and_put_away(owner, a_case):
    # Two loose videos that never overlap: a same-day set of two.
    morning = a_video(owner, a_case, "Cell-5", "08:30:00")
    evening = a_video(owner, a_case, "Cell-6", "22:40:00")
    day = case_chronology.day_of(a_case, DAY, strip=True)
    same = day["same_day"]
    assert same["cameras"] == 2 and same["ids"] == sorted(
        str(pk) for pk in (morning.pk, evening.pk)
    )
    assert same["key"] == incidents.offer_key(same["ids"]) and not same["declined"]
    assert len(same["spans"]) == 2 and same["words"] == "same day · 2"
    assert day["hints"] == []
    days = incident_strip.days(a_case)
    assert days[0]["same_day"] == 1 and days[0]["together"] is False
    assert incident_strip.same_day_count(a_case) == 1
    # The Notes tab's reading says nothing of it.
    assert case_chronology.day_of(a_case, DAY)["same_day"] is None
    # Its own matter: put away by the key.
    incidents.decline(a_case, same["key"])
    a_case.refresh_from_db()
    assert case_chronology.day_of(a_case, DAY, strip=True)["same_day"]["declined"]
    assert incident_strip.days(a_case)[0]["same_day"] == 0
    # One loose video alone on a day with nothing else: no suggestion.
    evening.delete()
    morning.refresh_from_db()
    assert case_chronology.day_of(a_case, DAY, strip=True)["same_day"] is None


def test_one_loose_video_beside_a_forming_one_and_the_picker_lists_it(
    owner, a_case, client
):
    one = a_video(owner, a_case, "BWC1-1", "20:24:38")
    two = a_video(owner, a_case, "BWC2-1", "20:26:10")
    MomentNote.objects.create(recording=one, at=120.0, note="a note", note_by=owner)
    loose = a_video(owner, a_case, "Cell-5", "08:30:00")
    day = case_chronology.day_of(a_case, DAY, strip=True)
    assert day["hints"][0]["notes"] == 1 and day["hints"][0]["cameras"] == 2
    assert day["same_day"]["ids"] == [str(loose.pk)]
    days = incident_strip.days(a_case)
    assert days[0]["forming"] == 1 and days[0]["same_day"] == 1
    assert days[0]["together"] is True
    # The Date strip of the Notes tab marks the day too.
    assert case_chronology.days_of(a_case)[0]["together"] is True
    # The picker for the forming span lists the loose video last, unticked.
    signed_in(client, owner)
    start = 20 * 3600 + 24 * 60 + 36
    told = client.get(
        f"/case/{a_case.pk}/chronology/span",
        {"day": "2025-11-06", "from": "20:24", "to": "20:55"},
    ).json()
    titles = [row["title"] for row in told["rows"]]
    assert titles[-1] == "Cell-5" and told["rows"][-1]["same_day"] is True
    assert told["rows"][-1]["ticked"] is False
    assert [row for row in told["rows"] if row["title"] == "BWC1-1"][0]["ticked"]
    assert start < 20 * 3600 + 55 * 60
    # The tab's lead counts the day; the strip's JSON carries the set.
    page = client.get(f"/case/{a_case.pk}?tab=incidents").content.decode()
    # The lead as counts (Phase 12 chapter 7): the forming run and the same
    # day are two suggestions.
    assert "No incident yet" in page and "2 suggested" in page
    strip = client.get(f"/case/{a_case.pk}/incidents/strip.json").json()
    assert strip["day"]["same_day"]["cameras"] == 1
    assert strip["days"][0]["together"] is True
    assert two.pk  # both overlapping videos stand in the forming bracket


def test_a_video_in_an_incident_is_not_same_day(owner, a_case):
    one = a_video(owner, a_case, "BWC1-1", "20:24:38")
    two = a_video(owner, a_case, "BWC2-1", "20:26:10")
    incidents.make(a_case, "Stop", [one, two], by=owner)
    loose = a_video(owner, a_case, "Cell-5", "08:30:00")
    day = case_chronology.day_of(a_case, DAY, strip=True)
    # The incident's cameras form nothing; the loose one stands beside it.
    assert day["hints"] == [] and day["same_day"]["ids"] == [str(loose.pk)]
    assert len(day["incidents"]) == 1
    days = incident_strip.days(a_case)
    assert days[0]["same_day"] == 1 and days[0]["together"] is True
