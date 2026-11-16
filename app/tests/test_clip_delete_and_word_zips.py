"""v1.242.0: an Admin deletes any Clip they can reach, a refusal is said, and
the zips of many Transcripts come as Word documents as well as text.

The rules checked here: an Admin who is not on a Case may delete a Clip in it
(their own or a colleague's) and the row names whose material it was; they
still may not adjust, rename or re-render it, and are told why; a person with
no standing is told "no such clip" as before; the Case's Clips tab, the
Recording's Clips sheet and the Clips page offer the Admin Delete; the Batch,
Workspace and Case zips give each Recording's Word document with `?as=word`
and plain text without it, one audit row per file of the right kind; and the
pages carry the menu with both choices.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from core import settings_store
from core.audit import Row
from core.cases import Case
from core.clips import Clip, RenderState
from core.models import User
from core.recordings import Batch, MediaState, Recording
from tests.helpers import signed_in

PASSWORD = "a-long-enough-password"
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def owner(db):
    return User.objects.from_directory("jsmith", display_name="J Smith")


@pytest.fixture
def admin(db):
    return User.objects.create_local_admin("asker", PASSWORD)


@pytest.fixture
def stranger(db):
    return User.objects.from_directory("mjones", display_name="M Jones")


@pytest.fixture
def a_case(owner):
    settings_store.set_to("clips_available", True)
    settings_store.set_to("folder_management", True)
    return Case.objects.create(owner=owner, name="Ramirez")


def a_recording(person, case=None, title="Stop", batch=None):
    recording = Recording.objects.create(
        batch=batch or Batch.objects.create(user=person),
        user=person,
        case=case,
        title=title,
        original_filename="call.m4a",
        media_state=MediaState.READY,
        playback_ready=True,
    )
    recording.folder.mkdir(parents=True, exist_ok=True)
    return recording


def a_ready_clip(recording, person, title, start=0.0):
    clip = Clip.objects.create(
        recording=recording,
        user=person,
        title=title,
        start=start,
        end=start + 5,
        state=RenderState.READY,
        include_excerpt=False,
    )
    clip.folder.mkdir(parents=True, exist_ok=True)
    clip.path.write_bytes(b"ID3 not really sound")
    return clip


def a_transcript(recording):
    from core.jobs import Segment, Transcript

    transcript = Transcript.objects.create(recording=recording, language="en")
    Segment.objects.create(
        transcript=transcript, start=0, end=4, text="Good morning.", speaker="Rowe"
    )
    return transcript


def names_in(answer) -> list[str]:
    body = b"".join(answer.streaming_content) if answer.streaming else answer.content
    return sorted(zipfile.ZipFile(io.BytesIO(body)).namelist())


# An Admin deletes any Clip they can reach -----------------------------------------


def test_an_admin_not_on_the_case_deletes_a_clip_in_it(a_case, owner, admin, client):
    recording = a_recording(owner, a_case)
    own = a_ready_clip(recording, admin, "Saved by the Admin")
    theirs = a_ready_clip(recording, owner, "Saved by the owner", start=10.0)
    assert not a_case.member(admin)
    signed_in(client, admin)

    for clip in (own, theirs):
        path = clip.path
        answer = client.post(f"/clip/{clip.pk}/delete")
        assert answer.status_code == 200 and answer.json() == {"deleted": True}
        assert not Clip.objects.filter(pk=clip.pk).exists()
        assert not path.exists()

    rows = Row.objects.filter(event="Clip deleted")
    assert rows.count() == 2
    # Whose material it was: the row an Admin's act always leaves.
    assert {row.affected_user_id for row in rows} == {owner.pk}
    assert {row.actor_user_id for row in rows} == {admin.pk}


def test_an_admin_deletes_a_clip_in_somebody_elses_workspace(owner, admin, client):
    settings_store.set_to("clips_available", True)
    clip = a_ready_clip(a_recording(owner), owner, "Theirs")
    signed_in(client, admin)
    assert client.post(f"/clip/{clip.pk}/delete").status_code == 200
    assert not Clip.objects.filter(pk=clip.pk).exists()
    assert Row.objects.get(event="Clip deleted").affected_user_id == owner.pk


def test_the_admin_still_changes_nothing_else_and_is_told_why(
    a_case, owner, admin, client
):
    clip = a_ready_clip(a_recording(owner, a_case), owner, "Theirs")
    signed_in(client, admin)

    renamed = client.post(
        f"/clip/{clip.pk}",
        data=json.dumps({"title": "Mine now"}),
        content_type="application/json",
    )
    again = client.post(f"/clip/{clip.pk}/rerender")
    for answer in (renamed, again):
        assert answer.status_code == 403
        words = answer.json()["error"]
        assert "An Admin may play it, download it and delete it" in words
    clip.refresh_from_db()
    assert clip.title == "Theirs"


def test_a_person_with_no_standing_deletes_nothing(a_case, owner, stranger, client):
    clip = a_ready_clip(a_recording(owner, a_case), owner, "Theirs")
    signed_in(client, stranger)
    assert client.post(f"/clip/{clip.pk}/delete").status_code == 404
    assert Clip.objects.filter(pk=clip.pk).exists()


def test_the_people_on_the_case_delete_as_before(a_case, owner, client):
    clip = a_ready_clip(a_recording(owner, a_case), owner, "Mine")
    signed_in(client, owner)
    assert client.post(f"/clip/{clip.pk}/delete").status_code == 200
    # Nobody else's material, so the row names nobody.
    assert Row.objects.get(event="Clip deleted").affected_user_id is None


def test_every_place_offers_the_admin_delete_and_nothing_else(
    a_case, owner, admin, client
):
    recording = a_recording(owner, a_case)
    clip = a_ready_clip(recording, owner, "Theirs")
    Clip.objects.filter(pk=clip.pk).update(state=RenderState.FAILED)
    signed_in(client, admin)

    # The Clips tab: Delete, and no Retry on a failed clip that is not theirs.
    tab = client.get(f"/case/{a_case.pk}?tab=clips").content.decode()
    assert f'data-clip="{clip.pk}" data-title="Theirs">Delete</button>' in tab
    assert 'class="small rerender"' not in tab

    # The Clips sheet's list: may delete, may not change.
    told = client.get(f"/recording/{recording.pk}/clips").json()["clips"]
    assert [(one["may_change"], one["may_delete"]) for one in told] == [(False, True)]

    # And for the people on the case both are true, as they were.
    signed_in(client, owner)
    told = client.get(f"/recording/{recording.pk}/clips").json()["clips"]
    assert [(one["may_change"], one["may_delete"]) for one in told] == [(True, True)]


def test_the_pages_scripts_say_a_refusal_and_offer_delete_alone():
    clips = (ROOT / "app" / "static" / "clips.js").read_text(encoding="utf-8")
    # A refused Delete or Retry is said; the page reloads only on a yes.
    assert "if (answer.ok) { window.location.reload(); return; }" in clips
    assert "told.error ||" in clips and "problem: true" in clips
    assert ".then(function () { window.location.reload(); })" not in clips

    tool = (ROOT / "app" / "static" / "clip-tool.js").read_text(encoding="utf-8")
    assert "one.may_delete === true" in tool and "tools += deleteOnly;" in tool
    assert "if (told && told.error) { UI.toast(told.error" in tool


# Many Transcripts as Word documents ------------------------------------------------


def test_a_batch_zip_comes_as_word_or_text(owner, client):
    batch = Batch.objects.create(user=owner)
    for title in ("Stop", "Interview"):
        a_transcript(a_recording(owner, title=title, batch=batch))
    # Not yet transcribed, so it is left out of both.
    a_recording(owner, title="Waiting", batch=batch)
    signed_in(client, owner)

    word = client.get(f"/batch/{batch.pk}/download?as=word")
    assert word.status_code == 200 and word.streaming
    assert "Transcripts%20Word%20" in word["Content-Disposition"]
    assert names_in(word) == ["Interview - transcript.docx", "Stop - transcript.docx"]
    rows = Row.objects.filter(category="exports", event="export made")
    assert [row.details["kind"] for row in rows] == ["transcript word"] * 2

    text = client.get(f"/batch/{batch.pk}/download")
    assert "Word" not in text["Content-Disposition"]
    assert names_in(text) == ["Interview - transcript.txt", "Stop - transcript.txt"]
    kinds = sorted(row.details["kind"] for row in rows.all())
    assert kinds == ["transcript text"] * 2 + ["transcript word"] * 2

    # Anything but "word" is the text, as the zip always was.
    assert names_in(client.get(f"/batch/{batch.pk}/download?as=pdf")) == names_in(
        client.get(f"/batch/{batch.pk}/download")
    )


def test_each_word_file_is_the_recordings_own_export(owner, client):
    from docx import Document

    batch = Batch.objects.create(user=owner)
    a_transcript(a_recording(owner, title="Stop", batch=batch))
    signed_in(client, owner)

    answer = client.get(f"/batch/{batch.pk}/download?as=word")
    body = b"".join(answer.streaming_content)
    with zipfile.ZipFile(io.BytesIO(body)) as bundle:
        document = Document(io.BytesIO(bundle.read("Stop - transcript.docx")))
    words = "\n".join(one.text for one in document.paragraphs)
    tables = "\n".join(
        cell.text
        for table in document.tables
        for row in table.rows
        for cell in row.cells
    )
    assert "Good morning." in words + tables
    # Exported by the person who asked, as the single export says.
    assert "jsmith" in words + tables


def test_the_workspace_and_case_zips_come_as_word_too(a_case, owner, client):
    a_transcript(a_recording(owner, title="Loose"))
    a_transcript(a_recording(owner, a_case, title="Filed"))
    signed_in(client, owner)

    loose = client.get("/download/transcripts?as=word")
    assert names_in(loose) == ["Loose - transcript.docx"]
    assert names_in(client.get("/download/transcripts")) == ["Loose - transcript.txt"]
    # Download everything is untouched: both files of each, whatever is asked.
    assert names_in(client.get("/download/everything?as=word")) == [
        "Loose - transcript.docx",
        "Loose - transcript.txt",
    ]

    filed = client.get(f"/case/{a_case.pk}/download?as=word")
    assert filed.status_code == 200 and filed.streaming
    assert "Ramirez%20transcripts%20Word%20" in filed["Content-Disposition"]
    assert names_in(filed) == ["Filed - transcript.docx"]
    assert names_in(client.get(f"/case/{a_case.pk}/download")) == [
        "Filed - transcript.txt"
    ]


def test_a_zip_writes_one_row_per_file_of_its_kind(a_case, owner, client):
    for title in ("One", "Two", "Three"):
        a_transcript(a_recording(owner, a_case, title=title))
    signed_in(client, owner)
    before = Row.objects.filter(category="exports").count()

    b"".join(client.get(f"/case/{a_case.pk}/download?as=word").streaming_content)
    rows = list(Row.objects.filter(category="exports").order_by("at")[before:])
    assert len(rows) == 3
    assert [row.event for row in rows] == ["export made"] * 3
    assert [row.details["kind"] for row in rows] == ["transcript word"] * 3


def test_the_pages_carry_the_menu_with_both_choices(a_case, owner, client):
    batch = Batch.objects.create(user=owner)
    a_transcript(a_recording(owner, title="Loose", batch=batch))
    a_transcript(a_recording(owner, a_case, title="Filed"))
    signed_in(client, owner)

    mine = client.get("/recordings").content.decode()
    # The page's own menu, and the batch's.
    assert mine.count('class="menu transcripts-menu"') == 2
    assert 'href="/download/transcripts?as=word"' in mine
    assert 'href="/download/transcripts"' in mine
    assert f'href="/batch/{batch.pk}/download?as=word"' in mine
    assert f'href="/batch/{batch.pk}/download"' in mine
    assert "As Word (.docx)" in mine and "As text (.txt)" in mine

    recordings_tab = client.get(f"/case/{a_case.pk}").content.decode()
    assert recordings_tab.count('class="menu transcripts-menu"') == 1
    assert f'href="/case/{a_case.pk}/download?as=word"' in recordings_tab
    assert f'href="/case/{a_case.pk}/download"' in recordings_tab

    details = client.get(f"/case/{a_case.pk}?tab=details").content.decode()
    assert f'href="/case/{a_case.pk}/download?as=word"' in details


def test_no_menu_while_nothing_is_ready(owner, client):
    a_recording(owner, title="Waiting")
    signed_in(client, owner)
    assert "transcripts-menu" not in client.get("/recordings").content.decode()
