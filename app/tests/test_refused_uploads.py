"""Refused uploads go (v1.181.0, at the maintainer's word).

A refused upload's row says when it goes by itself and carries Remove; the
case's Recordings tab counts them and offers Remove all refused; the hourly
sweep removes the ones older than the week, by the sweeper, with the audit
row every removal writes.
"""

from __future__ import annotations

import datetime as dt

import pytest
from core import lifecycle, settings_store
from core.audit import Row
from core.cases import Case
from core.models import User
from core.recordings import REFUSED_KEPT_DAYS, Batch, MediaState, Recording, Refusal
from django.utils import timezone
from tests.helpers import signed_in

PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def switches(db):
    settings_store.set_to("folder_management", True)


@pytest.fixture
def owner(db):
    return User.objects.create_local_admin("refused-owner", PASSWORD)


@pytest.fixture
def a_case(owner):
    return Case.objects.create(owner=owner, name="Harbour Street stop")


def a_recording(owner, case, title, *, refused=False, days_ago=0):
    one = Recording.objects.create(
        batch=Batch.objects.create(user=owner),
        user=owner,
        case=case,
        title=title,
        original_filename=f"{title}.mp4",
        media_state=MediaState.REJECTED if refused else MediaState.READY,
        refusal_class=Refusal.NO_AUDIO if refused else "",
        failure_message="The file has no sound." if refused else "",
        duration_seconds=0.0 if refused else 600.0,
    )
    if days_ago:
        Recording.objects.filter(pk=one.pk).update(
            created=timezone.now() - dt.timedelta(days=days_ago)
        )
        one.refresh_from_db()
    return one


def test_the_tab_says_how_many_were_refused_and_each_row_when_it_goes(
    owner, a_case, client
):
    good = a_recording(owner, a_case, "BWC1-1")
    bad = a_recording(owner, a_case, "Silent clip", refused=True)
    signed_in(client, owner)
    page = client.get(f"/case/{a_case.pk}").content.decode()
    assert "1 upload in this case was refused and is still listed" in page
    assert "Remove all refused" in page
    when = bad.created + dt.timedelta(days=REFUSED_KEPT_DAYS)
    goes = f"{when.day} {when:%b}"
    assert f"goes by itself on {goes}" in page
    assert f'data-refused="1" data-recording="{bad.pk}"' in page
    assert f'data-refused="1" data-recording="{good.pk}"' not in page
    # My recordings says it too, for a refused upload outside any case.
    loose = a_recording(owner, None, "Loose silent clip", refused=True)
    mine = client.get("/recordings").content.decode()
    assert loose.title in mine and f"goes by itself on {goes}" in mine
    # Nothing refused: no line.
    bad.delete()
    page = client.get(f"/case/{a_case.pk}").content.decode()
    assert "refused and" not in page


def test_remove_all_refused_takes_only_the_refused_ones(owner, a_case, client):
    good = a_recording(owner, a_case, "BWC1-1")
    a_recording(owner, a_case, "Silent clip", refused=True)
    a_recording(owner, a_case, "Empty clip", refused=True)
    signed_in(client, owner)
    answer = client.post(f"/case/{a_case.pk}/refused/remove")
    assert answer.status_code == 302 and answer["Location"].endswith("?tab=recordings")
    assert list(a_case.recordings.values_list("title", flat=True)) == ["BWC1-1"]
    assert good.pk == a_case.recordings.get().pk
    rows = Row.objects.filter(event="Recording deleted")
    assert rows.count() == 2 and {row.details.get("cause") for row in rows} == {
        "refused"
    }


def test_the_sweep_removes_refused_rows_older_than_the_week(owner, a_case):
    fresh = a_recording(owner, a_case, "Refused today", refused=True)
    old = a_recording(owner, a_case, "Refused last week", refused=True, days_ago=8)
    kept_good = a_recording(owner, a_case, "Old but fine", days_ago=30)
    assert lifecycle.sweep_refused() == 1
    titles = set(a_case.recordings.values_list("title", flat=True))
    assert titles == {fresh.title, kept_good.title}
    assert not Recording.objects.filter(pk=old.pk).exists()
    row = Row.objects.get(event="Recording deleted")
    assert row.details.get("cause") == "refused" and row.actor_user_id is None
    # Nothing older now: nothing swept.
    assert lifecycle.sweep_refused() == 0
