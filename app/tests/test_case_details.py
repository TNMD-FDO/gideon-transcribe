"""The Details tab (v1.165.0): About this case as a tab of the case page.

The column that sat beside every tab is a last tab, Details, with the case's
facts and actions, the Team, Names and places and Delete case; the other
tabs take the whole width with no right column; the Details tab reads for
a collaborator as the column did.
"""

from __future__ import annotations

import pytest
from core import settings_store
from core.cases import Case
from core.models import User
from core.recordings import Batch, MediaState, Recording
from django.urls import reverse
from tests.helpers import signed_in

PASSWORD = "a-long-enough-password"


@pytest.fixture(autouse=True)
def switches(db):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("sharing", True)


@pytest.fixture
def owner(db):
    return User.objects.create_local_admin("details-owner", PASSWORD)


@pytest.fixture
def a_case(owner):
    case = Case.objects.create(owner=owner, name="Harbour Street stop")
    Recording.objects.create(
        batch=Batch.objects.create(user=owner),
        user=owner,
        case=case,
        title="A call",
        original_filename="a-call.m4a",
        media_state=MediaState.READY,
        duration_seconds=60.0,
    )
    return case


def test_the_details_tab_holds_the_column_and_the_other_tabs_do_not(
    owner, a_case, client
):
    signed_in(client, owner)
    recordings = client.get(reverse("case", args=[a_case.pk])).content.decode()
    assert "?tab=details" in recordings and " Details</a>" in recordings
    # No right column on the Recordings tab: none of the column's pieces.
    for piece in (
        'id="rename"',
        'id="shared-with"',
        'id="case-vocabulary"',
        'id="delete-case"',
        "pane-detail",
    ):
        assert piece not in recordings, piece
    details = client.get(
        reverse("case", args=[a_case.pk]) + "?tab=details"
    ).content.decode()
    assert 'class="case-details about-case"' in details
    for piece in (
        'id="rename"',
        'id="share"',
        "Download all transcripts",
        'id="shared-with"',
        'id="case-vocabulary"',
        'class="case-foot"',
        'id="delete-case"',
    ):
        assert piece in details, piece
    # The facts read as they did: recordings and size, last activity, retention.
    assert "Last activity" in details and "Retention" in details
    # Delete stands after everything else about the case.
    assert details.index('id="case-vocabulary"') < details.index('id="delete-case"')
    assert details.index('id="shared-with"') < details.index('id="delete-case"')
    # The tab bar names Details last: its link comes after the Speakers tab's
    # in the bar (the first mention of each; the blocks mention tabs too).
    assert details.index("?tab=details") > details.index("?tab=speakers")


def test_a_collaborator_reads_the_details_tab_without_the_owners_actions(
    owner, a_case, client
):
    from core import sharing
    from django.utils import timezone

    colleague = User.objects.create_local_admin("details-colleague", PASSWORD)
    colleague.is_local = False
    colleague.last_sign_in = timezone.now()
    colleague.save()
    sharing.grant(a_case, colleague, owner)
    signed_in(client, colleague)
    details = client.get(
        reverse("case", args=[a_case.pk]) + "?tab=details"
    ).content.decode()
    assert "Shared by" in details and "Leave this case" in details
    assert 'id="rename"' not in details and 'id="delete-case"' not in details


def test_the_stylesheet_has_no_right_column_on_the_case_page():
    from pathlib import Path

    css = (Path(__file__).resolve().parents[1] / "static" / "app.css").read_text(
        encoding="utf-8"
    )
    assert ".case-page .panes { grid-template-columns: minmax(0, 1fr); }" in css
    assert (
        ".case-page .panes { grid-template-columns: minmax(0, 1fr) 24rem; }" not in css
    )
    assert ".case-details .details-grid {" in css
