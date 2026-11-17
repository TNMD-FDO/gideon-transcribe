"""v1.245.0: the Preservation copy at deletion, and Archived (Phase 14 chapter
2, ADR 0030; the drawing phase-14-preservation-at-deletion.html).

The rules checked here: a Case that is deleted leaves its copy in Archived,
made first; a Case whose copy is not behind goes at once and one without
waits for its copy, on the Details tab, and may be stopped; a copy that
cannot be made stops an owner's Delete, which then offers Try again and
Delete without a copy; the Retention policy makes the copy before it bins a
Case and bins it either way, the copy comes back with a restored Case, and a
wipe sends it to Archived with its full days; the sweep removes a copy past
its days; Archived is the owner's and the Admins', with Download and Remove
now; the office may turn all of it off; and the words are in the glossary,
the decision record, the guides, the specification and the changelog.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from core import cases, exports, preservation, retention, settings_store
from core.audit import Row
from core.cases import Case
from core.models import User
from core.preservation import ArchivedCopy, PreservationCopy
from core.sharing import Share
from django.utils import timezone
from tests.helpers import signed_in
from tests.test_preservation import a_recording, a_transcript, made
from tests.test_retention import aged, binned_for

PASSWORD = "a-long-enough-password"
APP = Path(__file__).resolve().parent.parent
ROOT = APP.parent


@pytest.fixture
def owner(db):
    return User.objects.from_directory("jsmith", display_name="J Smith")


@pytest.fixture
def stranger(db):
    return User.objects.from_directory("mjones", display_name="M Jones")


@pytest.fixture
def admin(db):
    return User.objects.create_local_admin("asker", PASSWORD)


@pytest.fixture
def a_case(owner):
    settings_store.set_to("folder_management", True)
    case = Case.objects.create(owner=owner, name="Ramirez")
    a_transcript(a_recording(owner, case))
    return case


def events(event: str):
    return Row.objects.filter(event=event)


# The settings ------------------------------------------------------------------


def test_the_two_settings_and_their_defaults(db):
    assert settings_store.get("preservation_at_deletion") is True
    assert settings_store.get("preservation_copy_days") == 30
    assert preservation.at_deletion_on() and preservation.keep_days() == 30
    catalogue = (ROOT / "docs/spec/ADMIN-SETTINGS-CATALOGUE.md").read_text(
        encoding="utf-8"
    )
    assert (
        "| Preservation copy at deletion (key `preservation_at_deletion`) |"
        in catalogue
    )
    assert "| Preservation copy kept (key `preservation_copy_days`) |" in catalogue


# An owner's Delete -------------------------------------------------------------


def test_the_question_says_where_the_copy_will_be(a_case, owner, client):
    page = signed_in(client, owner).get(f"/case/{a_case.pk}?tab=details")
    page = page.content.decode()
    assert 'id="delete-case" data-copy-days="30"' in page
    assert f'data-delete="/case/{a_case.pk}/delete"' in page
    script = (APP / "static" / "cases.js").read_text(encoding="utf-8")
    assert (
        '"A Preservation copy is made first and kept in Archived for " + '
        'plural(days, "day") + ", for you to save to the client\'s file of record."'
    ) in script
    assert "if (answer.said.making) {" in script
    assert (
        '" is deleted." + (days ? " Its Preservation copy is in Archived for "'
        in script
    )


def test_a_case_whose_copy_is_not_behind_goes_at_once_and_its_copy_is_archived(
    a_case, owner, client
):
    copy = made(a_case, owner)
    was_at = copy.path
    answer = signed_in(client, owner).post(f"/case/{a_case.pk}/delete")
    told = answer.json()
    assert told["ok"] and told["where"] == "/cases"
    assert told["name"] == "Ramirez" and told["kept_days"] == 30
    assert not Case.objects.filter(pk=a_case.pk).exists()
    kept = ArchivedCopy.objects.get()
    assert kept.case_name == "Ramirez" and kept.case_id_was == a_case.pk
    assert kept.owner == owner and kept.owner_name == "J Smith"
    assert kept.how == preservation.OWNER and kept.gone_on == timezone.localdate()
    assert kept.documents == copy.documents_total and kept.size_bytes == copy.size_bytes
    # The file went out of the Case's folder before the folder went.
    assert kept.path.exists() and not was_at.exists()
    assert kept.path.parent == preservation.archive_folder()
    assert preservation.days_left(kept) == 30
    row = events("preservation copy archived").get()
    assert row.details == {"cause": "owner", "days": 30}
    assert events("case deleted").get().details["copy"] == "kept"


def test_a_case_without_a_copy_waits_for_it_and_then_goes(a_case, owner, client):
    browser = signed_in(client, owner)
    told = browser.post(f"/case/{a_case.pk}/delete").json()
    assert told == {"ok": True, "making": True}
    # The Case is still there, and in use, until its copy is ready.
    assert Case.objects.filter(pk=a_case.pk).exists()
    copy = PreservationCopy.objects.get()
    assert copy.then_delete and copy.state == preservation.QUEUED
    waiting = browser.get(f"/case/{a_case.pk}/preservation").json()
    assert waiting["making"] is True
    assert "<b>Deleting this case.</b>" in waiting["html"]
    assert "Stop, and keep the case" in waiting["html"]
    assert "The case is deleted when its copy is ready" in waiting["html"]

    preservation.make(str(copy.pk))
    assert not Case.objects.filter(pk=a_case.pk).exists()
    kept = ArchivedCopy.objects.get()
    assert kept.path.exists() and kept.how == preservation.OWNER
    assert events("case deleted").get().actor_username == "jsmith"
    # The page that was waiting is told the Case is gone, and where its copy is.
    gone = browser.get(f"/case/{a_case.pk}/preservation").json()
    assert gone == {"gone": True, "name": "Ramirez", "days": 30}


def test_the_page_keeps_asking_between_the_copy_and_the_case_going(a_case, owner):
    # The copy is ready and the Case is going this moment: a page that asked
    # now and stopped asking would never learn the Case had gone.
    copy = made(a_case, owner)
    PreservationCopy.objects.filter(pk=copy.pk).update(then_delete=True)
    told = preservation.for_page(a_case)
    assert told["making"] is True and told["deleting"] is True
    assert told["done"] == told["total"] == copy.documents_total
    # Keep the case ends it.
    preservation.stop(a_case, owner)
    assert "making" not in preservation.for_page(a_case)


def test_stop_keeps_the_case(a_case, owner, client):
    browser = signed_in(client, owner)
    browser.post(f"/case/{a_case.pk}/delete")
    copy = PreservationCopy.objects.get()
    told = browser.post(f"/case/{a_case.pk}/preservation/stop").json()
    assert told["making"] is False and "Deleting this case" not in told["html"]
    preservation.make(str(copy.pk))
    assert Case.objects.filter(pk=a_case.pk).exists()
    assert not ArchivedCopy.objects.exists()


def test_a_copy_that_cannot_be_made_stops_the_delete_and_the_owner_decides(
    a_case, owner, client, monkeypatch
):
    def word(recording, exported_by, **more):
        raise ValueError("a transcript the writer cannot lay out")

    browser = signed_in(client, owner)
    browser.post(f"/case/{a_case.pk}/delete")
    with monkeypatch.context() as broken:
        broken.setattr(exports, "word", word)
        preservation.make(str(PreservationCopy.objects.get().pk))
    # The Case is as it was, and the page says so with what to do next.
    assert Case.objects.filter(pk=a_case.pk).exists()
    page = browser.get(f"/case/{a_case.pk}?tab=details").content.decode()
    assert "<b>Ramirez was not deleted.</b>" in page
    assert "Transcript could not be written." in page
    for act in ("delete-again", "stop", "delete-without"):
        assert f'data-act="{act}"' in page, act
    assert "Delete without a copy" in page and "Try again" in page

    # Keep the case: the page no longer says a Delete stopped.
    browser.post(f"/case/{a_case.pk}/preservation/stop")
    page = browser.get(f"/case/{a_case.pk}?tab=details").content.decode()
    assert "was not deleted" not in page

    # Delete without a copy, by the person's second word.
    told = browser.post(f"/case/{a_case.pk}/delete", {"without_copy": "1"}).json()
    assert told["ok"] and told["kept_days"] == 0
    assert not Case.objects.filter(pk=a_case.pk).exists()
    assert not ArchivedCopy.objects.exists()
    assert events("case deleted").get().details["copy"] == "declined"
    script = (APP / "static" / "preservation.js").read_text(encoding="utf-8")
    assert '{ without_copy: "1" }' in script
    assert '"Delete " + part.dataset.name + " without a Preservation copy?"' in script


def test_with_the_setting_off_delete_leaves_nothing(a_case, owner, client):
    settings_store.set_to("preservation_at_deletion", False)
    made(a_case, owner)
    browser = signed_in(client, owner)
    page = browser.get(f"/case/{a_case.pk}?tab=details").content.decode()
    assert 'id="delete-case" data-copy-days="0"' in page
    told = browser.post(f"/case/{a_case.pk}/delete").json()
    assert told["ok"] and told["kept_days"] == 0 and "making" not in told
    assert not Case.objects.filter(pk=a_case.pk).exists()
    assert not ArchivedCopy.objects.exists()
    assert not preservation.archive_folder().exists()
    assert events("case deleted").get().details["copy"] == "none"


def test_an_admins_delete_of_somebody_elses_keeps_the_copy_as_the_owners(
    a_case, owner, admin
):
    cases.delete(a_case, actor=admin)
    kept = ArchivedCopy.objects.get()
    assert kept.owner == owner and kept.how == preservation.ADMIN
    assert kept.gone_by_name == "asker"
    row = events("preservation copy archived").get()
    assert row.actor_username == "asker" and row.affected_username == "jsmith"


# The Retention policy ------------------------------------------------------------


def test_the_sweep_makes_the_copy_before_it_bins_and_restore_brings_it_back(
    a_case, owner, client
):
    aged(a_case, 30)
    counts = retention.sweep()
    assert counts["deleted"] == 1 and counts["copies_removed"] == 0
    a_case.refresh_from_db()
    assert a_case.is_binned
    copy = PreservationCopy.objects.get(case=a_case)
    assert copy.state == preservation.READY and copy.path.exists()
    assert copy.made_by is None and copy.made_by_name == "Gideon Transcribe"
    assert not ArchivedCopy.objects.exists()

    # The Recycle bin's row has the copy to download meanwhile.
    browser = signed_in(client, owner)
    page = browser.get("/cases/bin").content.decode()
    assert "<th>Preservation copy</th>" in page and "not yet downloaded" in page
    assert f"/cases/bin/{a_case.pk}/preservation/download" in page
    answer = browser.get(f"/cases/bin/{a_case.pk}/preservation/download")
    assert answer.status_code == 200 and answer["Content-Type"] == "application/zip"
    assert "downloaded " in browser.get("/cases/bin").content.decode()
    assert events("export made").get().details["kind"] == "preservation copy"

    # Restored: the copy is the Case's own again, and nothing is in Archived.
    cases.restore(a_case, actor=owner)
    a_case.refresh_from_db()
    told = preservation.for_page(a_case)
    assert told["state"] == "ready" and told["made_by"] == "Gideon Transcribe"
    assert not ArchivedCopy.objects.exists()


def test_the_case_is_binned_even_when_its_copy_cannot_be_made(
    a_case, owner, client, monkeypatch
):
    def word(recording, exported_by, **more):
        raise ValueError("no")

    aged(a_case, 30)
    with monkeypatch.context() as broken:
        broken.setattr(exports, "word", word)
        retention.sweep()
    a_case.refresh_from_db()
    assert a_case.is_binned and preservation.ready(a_case) is None
    # Its row offers Make the copy, and that makes one.
    browser = signed_in(client, owner)
    page = browser.get("/cases/bin").content.decode()
    assert f'class="small make-copy" data-case="{a_case.pk}"' in page
    answer = browser.post(f"/cases/bin/{a_case.pk}/preservation/make")
    assert answer.json() == {"ok": True}
    assert preservation.ready(a_case) is not None


def test_a_wipe_sends_the_copy_to_archived_with_its_full_days(a_case, owner):
    aged(a_case, 30)
    retention.sweep()
    binned_for(a_case, 30)
    counts = retention.sweep()
    assert counts["wiped"] == 1 and counts["copies_removed"] == 0
    assert not Case.objects.filter(pk=a_case.pk).exists()
    kept = ArchivedCopy.objects.get()
    # Counted from the day the Case was gone for good, not from its binning.
    assert kept.how == preservation.RETENTION and kept.gone_on == timezone.localdate()
    assert preservation.days_left(kept) == 30 and kept.path.exists()
    assert events("case permanently deleted").get().details["copy"] == "kept"


def test_delete_permanently_from_the_bin_keeps_the_copy_too(a_case, owner, client):
    aged(a_case, 30)
    retention.sweep()
    answer = signed_in(client, owner).post(f"/case/{a_case.pk}/wipe")
    assert answer.json()["ok"]
    assert ArchivedCopy.objects.get().how == preservation.OWNER


def test_the_sweep_removes_a_copy_past_its_days_downloaded_or_not(a_case, owner):
    made(a_case, owner)
    cases.delete(a_case, actor=owner)
    kept = ArchivedCopy.objects.get()
    ArchivedCopy.objects.filter(pk=kept.pk).update(
        gone_on=timezone.localdate() - timedelta(days=29)
    )
    assert retention.sweep()["copies_removed"] == 0
    ArchivedCopy.objects.filter(pk=kept.pk).update(
        gone_on=timezone.localdate() - timedelta(days=30)
    )
    path = kept.path
    assert retention.sweep()["copies_removed"] == 1
    assert not ArchivedCopy.objects.exists() and not path.exists()
    row = events("preservation copy removed").get()
    assert row.details == {"cause": "its days", "downloaded": False}
    assert row.affected_username == "jsmith"


def test_a_shorter_number_removes_at_the_next_sweep(a_case, owner):
    made(a_case, owner)
    cases.delete(a_case, actor=owner)
    ArchivedCopy.objects.update(gone_on=timezone.localdate() - timedelta(days=10))
    assert retention.sweep()["copies_removed"] == 0
    settings_store.set_to("preservation_copy_days", 7)
    assert retention.sweep()["copies_removed"] == 1


# Archived ------------------------------------------------------------------------


def test_archived_is_the_owners_and_the_admins(a_case, owner, stranger, admin, client):
    settings_store.set_to("sharing", True)
    Share.objects.create(case=a_case, person=stranger, added_by=owner)
    made(a_case, owner)
    cases.delete(a_case, actor=owner)
    kept = ArchivedCopy.objects.get()

    browser = signed_in(client, owner)
    cases_page = browser.get("/cases").content.decode()
    assert ">Archived (1)</a>" in cases_page
    page = browser.get("/cases/archived").content.decode()
    assert "<h1>Archived</h1>" in page and "<b>Ramirez</b>" in page
    assert "by you" in page and "30 days left" in page and "not yet" in page
    assert "save it to the client's file of record" in page
    assert f"/cases/archived/{kept.pk}/download" in page
    assert 'class="small ghost danger remove-copy"' in page

    # A Collaborator, who saw the Case, sees nothing of its copy.
    other = signed_in(client, stranger)
    assert "Ramirez" not in other.get("/cases/archived").content.decode()
    assert other.get(f"/cases/archived/{kept.pk}/download").status_code == 404
    assert other.post(f"/cases/archived/{kept.pk}/remove").status_code == 404

    # An Admin sees everyone's, with the owner named.
    looking = signed_in(client, admin)
    page = looking.get("/cases/archived").content.decode()
    assert "<b>Ramirez</b>" in page and "J Smith" in page and "by J Smith" in page
    assert ">Archived</a>" in page  # none of the Admin's own is waiting


def test_download_marks_it_and_remove_now_takes_it(a_case, owner, client):
    made(a_case, owner)
    cases.delete(a_case, actor=owner)
    kept = ArchivedCopy.objects.get()
    browser = signed_in(client, owner)
    answer = browser.get(f"/cases/archived/{kept.pk}/download")
    assert answer.status_code == 200
    assert "Ramirez%20-%20preservation%20copy%20" in answer["Content-Disposition"]
    b"".join(answer.streaming_content)
    kept.refresh_from_db()
    assert kept.downloaded_at is not None and kept.downloaded_by_name == "J Smith"
    row = events("export made").get()
    assert row.details["kind"] == "preservation copy" and row.object_label == "Ramirez"
    # Downloaded: it no longer counts on the tab, and the row says so.
    assert preservation.waiting_count(owner) == 0
    page = browser.get("/cases/archived").content.decode()
    assert "by J Smith</span>" in page and 'data-downloaded="1"' in page

    path = kept.path
    assert browser.post(f"/cases/archived/{kept.pk}/remove").json() == {"ok": True}
    assert not ArchivedCopy.objects.exists() and not path.exists()
    row = events("preservation copy removed").get()
    assert row.details == {"cause": "owner", "downloaded": True}


def test_an_admins_removal_is_recorded_with_the_owner(a_case, owner, admin, client):
    made(a_case, owner)
    cases.delete(a_case, actor=owner)
    kept = ArchivedCopy.objects.get()
    signed_in(client, admin).post(f"/cases/archived/{kept.pk}/remove")
    row = events("preservation copy removed").get()
    assert row.details["cause"] == "admin"
    assert row.actor_username == "asker" and row.affected_username == "jsmith"


def test_archived_is_hidden_while_cases_are_off(a_case, owner, client):
    made(a_case, owner)
    cases.delete(a_case, actor=owner)
    settings_store.set_to("folder_management", False)
    assert signed_in(client, owner).get("/cases/archived").status_code == 404
    # And the copy's days do not run: the sweep does nothing while Off.
    ArchivedCopy.objects.update(gone_on=timezone.localdate() - timedelta(days=60))
    assert retention.sweep() is None and ArchivedCopy.objects.count() == 1


# The words -------------------------------------------------------------------------


def test_the_words_are_in_the_glossary_the_record_the_guides_and_the_changelog():
    glossary = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    assert "**Archived**:" in glossary
    assert "then outlives the Case in Archived" in glossary
    record = ROOT / "docs/adr/0030-a-deleted-case-leaves-its-preservation-copy.md"
    assert "Status: accepted. Release: v1.245.0" in record.read_text(encoding="utf-8")
    spec = (ROOT / "docs/spec/SPEC-PHASE-14.md").read_text(encoding="utf-8")
    assert "## 2. The Preservation copy at deletion, and Archived (v1.245.0)" in spec
    assert "### As built, where it departs from the drawing" in spec
    drawing = ROOT / "docs/spec/mockups/phase-14-preservation-at-deletion.html"
    assert drawing.exists() and "<img" not in drawing.read_text(encoding="utf-8")
    guide = (ROOT / "docs" / "user-guide.md").read_text(encoding="utf-8")
    assert "**Archived**" in guide and "**Remove now**" in guide
    assert "**Delete without a copy**" in guide
    admin = (ROOT / "docs" / "admin-guide.md").read_text(encoding="utf-8")
    assert "**Preservation copy at deletion**" in admin
    assert "**Preservation copy kept**" in admin
    log = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## v1.245.0" in log and "Delete no longer leaves nothing" in log
