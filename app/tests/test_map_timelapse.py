"""Save a timelapse, and More unfolded (Phase 12 chapter 6.12, v1.241.0).

The rules checked here: the frames the browser drew are taken a batch at a
time into a working folder inside the case's own folder, and joined into
one GIF kept as a Document of a kind of its own, about the incident shown;
everything that would refuse the finished GIF is refused before a frame is
drawn; a frame that is not a JPEG, has no place, or comes for somebody
else's timelapse is refused; stopping keeps nothing, and a failed join
leaves nothing behind; a folder a closed page left is swept; the Document
moves on its page and stands still on the shelf, downloads as a GIF, is
never compared, and its row says counts and never a place; the Map page's
bar carries as many of the six presses as fit on its one row and keeps
the rest behind More (v1.241.1); the word is in the glossary.
"""

from __future__ import annotations

import io
import json
import os
import time
from pathlib import Path

import pytest
from core import documents, settings_store, timelapse, uploads
from core.audit import Row
from core.cases import Case
from core.models import User
from django.urls import reverse
from tests.helpers import signed_in
from tests.test_case_map import an_incident_with_a_path

PASSWORD = "a-long-enough-password"
HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent
GIF = b"GIF89a" + b"\x00" * 64


@pytest.fixture(autouse=True)
def switched_on(db, settings, tmp_path, monkeypatch):
    settings.DATA_DIR = tmp_path
    # Room on the disk, whatever the machine running the tests has.
    monkeypatch.setattr(uploads, "free_disk_bytes", lambda: 10**15)
    settings_store.set_to("folder_management", True)
    settings_store.set_to("incidents", True)
    settings_store.set_to("maps", True)
    settings_store.set_to("documents", True)


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("walker", PASSWORD)


@pytest.fixture
def a_case(person):
    return Case.objects.create(owner=person, name="Harbour Street stop")


@pytest.fixture
def joined(monkeypatch):
    """ffmpeg stood in for: the join writes a GIF and says what it was given."""
    seen = []

    def stand_in(folder, target):
        seen.append(sorted(one.name for one in folder.glob("f-*.jpg")))
        target.write_bytes(GIF)

    monkeypatch.setattr(timelapse, "_encode", stand_in)
    return seen


def a_frame(width=64, height=48) -> bytes:
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (width, height), (40, 80, 120)).save(out, format="JPEG")
    return out.getvalue()


def begun(case, by, frames=4, **changes) -> str:
    said = {"frames": frames, "width": 960, "height": 300, "cameras": 2, "span": 1927}
    said.update(changes)
    return timelapse.begin(case, by=by, **said)


def sent(client, case, **fields):
    return client.post(reverse("case-map-timelapse", args=[case.pk]), fields)


def frames_for(numbers):
    files = {}
    for number in numbers:
        one = io.BytesIO(a_frame())
        one.name = f"f{number}.jpg"
        files[f"f{number}"] = one
    return files


# The three steps, through the page's own address ------------------------------------


def test_the_frames_are_joined_and_kept_as_a_timelapse_about_the_incident(
    client, person, a_case, joined
):
    signed_in(client, person)
    incident, _camera = an_incident_with_a_path(person, a_case)
    told = sent(
        client,
        a_case,
        step="begin",
        frames=4,
        width=960,
        height=300,
        cameras=2,
        span=1927,
    )
    assert told.status_code == 200, told.content
    token = told.json()["token"]
    assert told.json()["batch"] == timelapse.BATCH
    work = a_case.folder / timelapse.WORK / token
    assert json.loads((work / "meta.json").read_text())["frames"] == 4
    # Two batches, out of order within a batch: kept by their numbers.
    got = sent(client, a_case, step="frames", token=token, **frames_for([1, 0]))
    assert got.json() == {"ok": True, "have": 2}
    got = sent(client, a_case, step="frames", token=token, **frames_for([2, 3]))
    assert got.json()["have"] == 4
    title = "Timelapse 14:20:03 to 14:52:10, 6 Nov 2025 · Stop"
    done = sent(
        client,
        a_case,
        step="finish",
        token=token,
        title=title,
        incident=str(incident.pk),
    )
    assert done.status_code == 200, done.content
    said = done.json()
    assert said["words"] == "Saved to the case's Documents tab, about Stop."
    assert said["title"] == title and said["bytes"] == len(GIF)
    assert joined == [["f-00000.jpg", "f-00001.jpg", "f-00002.jpg", "f-00003.jpg"]]
    assert not work.exists(), "the working folder goes once the GIF is kept"
    document = incident.documents.get()
    assert document.kind == documents.TIMELAPSE
    assert document.is_timelapse and document.is_picture
    assert document.state == documents.READY and document.pages == 1
    assert document.pages_line() == "A timelapse of the map"
    assert document.original_path.name == "original.gif"
    assert document.original_path.read_bytes() == GIF
    # The one page's picture is the first frame, still, as a PNG.
    assert document.picture_path(1).read_bytes().startswith(b"\x89PNG")
    page = document.page_rows.get()
    assert page.text == "" and page.paragraphs == []
    # The row: what it is and how much, never a place.
    row = Row.objects.get(event="Document added")
    assert row.details["kind"] == "timelapse" and row.details["about"] == "incident"
    assert row.details["frames"] == 4 and row.details["cameras"] == 2
    assert row.details["span_seconds"] == 1927
    # It moves on its own page, stands still on the shelf, downloads as a GIF.
    picture = reverse("document-picture", args=[a_case.pk, document.pk, 1])
    assert client.get(picture)["Content-Type"] == "image/png"
    assert client.get(picture + "?moving=1")["Content-Type"] == "image/gif"
    download = client.get(said["download"])
    assert download["Content-Type"] == "image/gif"
    assert "Timelapse%20142003%20to%20145210" in download["Content-Disposition"]
    assert download["Content-Disposition"].endswith(".gif")
    taken = Row.objects.get(event="Timelapse downloaded")
    assert taken.category == "exports" and taken.details["kind"] == "timelapse"
    own = client.get(said["url"]).content.decode()
    assert "?moving=1" in own and "A timelapse of the map" in own
    shelf = client.get(reverse("case", args=[a_case.pk]) + "?tab=documents")
    shelf = shelf.content.decode()
    assert "Pictures of the map" in shelf and "Save a timelapse" in shelf
    assert "Timelapse &middot;" in shelf and "?moving=1" not in shelf
    # On the map: the Map page at the timelapse's day and its first moment.
    at = 14 * 3600 + 20 * 60 + 3
    assert documents.picture_map_url(document).endswith(f"?day=2025-11-06&from={at}")
    # Never compared.
    from core import comparison

    patch = pytest.MonkeyPatch()
    patch.setattr(comparison, "on", lambda: True)
    can, why = comparison.possible(document, incident)
    patch.undo()
    assert not can and why == "A picture of the map has no words to compare."


def test_what_would_refuse_the_gif_is_refused_before_a_frame_is_drawn(
    person, a_case, monkeypatch
):
    with monkeypatch.context() as full:
        full.setattr(uploads, "free_disk_bytes", lambda: 0)
        with pytest.raises(timelapse.Refused, match="disk is full"):
            begun(a_case, person)
    with pytest.raises(timelapse.Refused, match="480 frames at most"):
        begun(a_case, person, frames=481)
    with pytest.raises(timelapse.Refused, match="480 frames at most"):
        begun(a_case, person, frames=1)
    with pytest.raises(timelapse.Refused, match="not a size"):
        begun(a_case, person, width=1920)
    with pytest.raises(timelapse.Refused, match="not a size"):
        begun(a_case, person, height=5000)
    with pytest.raises(timelapse.Refused, match="Tick at least one camera"):
        begun(a_case, person, cameras=0)
    settings_store.set_to("documents_per_case", 1)
    documents.Document.objects.create(
        case=a_case, title="A report", original_filename="r.pdf"
    )
    with pytest.raises(timelapse.Refused, match="already has 1 documents"):
        begun(a_case, person)
    settings_store.set_to("documents_per_case", 20)
    settings_store.set_to("documents", False)
    with pytest.raises(timelapse.Refused, match="nowhere to go"):
        begun(a_case, person)
    assert not (a_case.folder / timelapse.WORK).exists(), "nothing was made"


def test_a_frame_that_is_not_one_is_refused(person, a_case):
    other = User.objects.create_local_admin("other", PASSWORD)
    token = begun(a_case, person, frames=3)
    good = a_frame()
    with pytest.raises(timelapse.Refused, match="no place for"):
        timelapse.add_frames(a_case, token, by=person, frames=[(3, good)])
    with pytest.raises(timelapse.Refused, match="not a picture of the map"):
        timelapse.add_frames(a_case, token, by=person, frames=[(0, b"\x89PNG....")])
    with pytest.raises(timelapse.Refused, match="not a picture of the map"):
        big = good + b"\x00" * timelapse.FRAME_MOST
        timelapse.add_frames(a_case, token, by=person, frames=[(0, big)])
    with pytest.raises(timelapse.Refused, match="Too many frames"):
        many = [(0, good)] * (timelapse.BATCH + 1)
        timelapse.add_frames(a_case, token, by=person, frames=many)
    with pytest.raises(timelapse.Refused, match="somebody else's"):
        timelapse.add_frames(a_case, token, by=other, frames=[(0, good)])
    # A token is thirty-two hex digits and nothing else: never a path.
    for bad in ("", "../../etc", "g" * 32, token + "/.."):
        with pytest.raises(timelapse.Refused, match="not begun here"):
            timelapse.add_frames(a_case, bad, by=person, frames=[(0, good)])
    with pytest.raises(timelapse.Refused, match="no longer being made"):
        timelapse.add_frames(a_case, "0" * 32, by=person, frames=[(0, good)])
    assert timelapse.add_frames(a_case, token, by=person, frames=[(0, good)]) == 1


def test_stopping_keeps_nothing_and_a_failed_join_leaves_nothing_behind(
    person, a_case, monkeypatch
):
    token = begun(a_case, person, frames=2)
    timelapse.add_frames(a_case, token, by=person, frames=[(0, a_frame())])
    timelapse.stop(a_case, token, by=person)
    assert not (a_case.folder / timelapse.WORK / token).exists()
    timelapse.stop(a_case, token, by=person)  # a second stop is nothing
    # A frame short: refused, and the folder goes.
    token = begun(a_case, person, frames=2)
    timelapse.add_frames(a_case, token, by=person, frames=[(0, a_frame())])
    with pytest.raises(timelapse.Refused, match="Only 1 of 2 frames arrived"):
        timelapse.finish(a_case, token, by=person, about={}, title="")
    assert not (a_case.folder / timelapse.WORK / token).exists()
    # The join fails: refused in plain words, nothing kept.
    token = begun(a_case, person, frames=2)
    timelapse.add_frames(
        a_case, token, by=person, frames=[(0, a_frame()), (1, a_frame())]
    )

    def fails(folder, target):
        raise timelapse.Refused("The frames could not be joined into a GIF.")

    monkeypatch.setattr(timelapse, "_encode", fails)
    with pytest.raises(timelapse.Refused, match="could not be joined"):
        timelapse.finish(a_case, token, by=person, about={}, title="")
    assert not (a_case.folder / timelapse.WORK / token).exists()
    assert not documents.Document.objects.exists()
    assert not Row.objects.filter(event="Document added").exists()


def test_a_folder_a_closed_page_left_is_swept_when_the_next_begins(person, a_case):
    left = begun(a_case, person)
    folder = a_case.folder / timelapse.WORK / left
    old = time.time() - timelapse.STALE_SECONDS - 60
    os.utime(folder, (old, old))
    fresh = begun(a_case, person)
    assert not folder.exists()
    assert (a_case.folder / timelapse.WORK / fresh).exists()


def test_the_join_holds_the_last_frame_and_writes_one_palette(tmp_path):
    arguments = timelapse.encode_arguments(tmp_path, tmp_path / "out.gif")
    assert arguments[0] == "ffmpeg" and arguments[-1].endswith("out.gif")
    assert arguments[arguments.index("-framerate") + 1] == str(timelapse.FPS)
    chain = arguments[arguments.index("-filter_complex") + 1]
    assert f"tpad=stop_mode=clone:stop_duration={timelapse.HOLD_SECONDS}" in chain
    assert "palettegen=stats_mode=diff" in chain
    assert "paletteuse=dither=bayer" in chain and "diff_mode=rectangle" in chain
    assert arguments[arguments.index("-loop") + 1] == "0"
    assert timelapse.FRAMES_MOST == 480 and timelapse.RUNS == (15, 30, 60)


def test_the_address_refuses_whoever_cannot_add_and_an_unknown_step(
    client, person, a_case
):
    signed_in(client, person)
    assert sent(client, a_case, step="dance").status_code == 400
    assert sent(client, a_case, step="begin", frames="many").status_code == 400
    said = sent(client, a_case, step="frames", token="0" * 32, **frames_for([0]))
    assert said.status_code == 400 and "no longer being made" in said.json()["error"]
    stranger = User.objects.create_local_admin("stranger", PASSWORD)
    theirs = Case.objects.create(owner=stranger, name="Another case")
    settings_store.set_to("maps", False)
    assert sent(client, a_case, step="begin").status_code == 404
    settings_store.set_to("maps", True)
    client.logout()
    assert sent(client, theirs, step="begin").status_code in (302, 403, 404)


# The page -----------------------------------------------------------------------------


def test_the_map_page_carries_the_press_the_box_and_the_frames(client, person, a_case):
    signed_in(client, person)
    an_incident_with_a_path(person, a_case)
    page = client.get(reverse("case-map-page", args=[a_case.pk])).content.decode()
    address = reverse("case-map-timelapse", args=[a_case.pk])
    assert f'data-timelapse="{address}"' in page
    script = (HERE / "static" / "map.js").read_text(encoding="utf-8")
    for piece in (
        "data-act='timelapse'",
        'case "timelapse": lapseBox(); return;',
        "function lapseBox()",
        "function lapseMake(L, cameras, progress)",
        "function composeFrame(band, options)",
        # Only the ticked cameras, and never on the incident's pane.
        "return CLOCKED || PICK ? [] : shownCams().filter(",
        "disabled title='Tick at least one camera in the list first'",
        # Eight frames a second for 15, 30 or 60 seconds, in two sizes.
        "var LAPSE = { fps: 8, runs: [15, 30, 60], widths: [[960,",
        # The map drawn at the GIF's own size, then put back.
        'el.pane.style.width = outW + "px"',
        "zoom: kept.zoom + Math.log(outW / paneW) / Math.LN2",
        "function leave()",
        "map.jumpTo({ center: kept.center, zoom: kept.zoom })",
        # The frames: no tiles, the names when asked, a JPEG each.
        "{ noTiles: true, noNames: !L.names }",
        '"image/jpeg", 0.92',
        'form("stop")',
        "Keep this page open. Nothing is kept if you stop.",
        # The page's own clockwork stands still meanwhile.
        "if (document.hidden || !S.loaded || S.capturing) { return; }",
    ):
        assert piece in script, piece
    # Save a picture draws through the same frame.
    assert "composeFrame({ words: title }).toBlob(" in script


def test_the_bar_holds_as_many_presses_as_fit_and_more_holds_the_rest():
    """v1.241.1: v1.241.0 folded all six together, so a bar with room for
    three of them showed none. The row is filled, one fewer at a time."""
    script = (HERE / "static" / "map.js").read_text(encoding="utf-8")
    for piece in (
        "function morePresses()",
        "function moreHtml()",
        "function barWraps()",
        # Every press first, then one fewer until the bar is one row.
        "S.moreOn = morePresses().length; el.transport.innerHTML = bar();",
        "while (S.moreOn > 0 && barWraps()) { S.moreOn -= 1; "
        "el.transport.innerHTML = bar(); }",
        # The first of them on the bar, the rest behind More, which says
        # what it holds and is not drawn when it holds nothing.
        "on = all.slice(0, S.moreOn), behind = all.slice(S.moreOn);",
        "(on.length ? \"<span class='map-more-open' id='map-more-open'>\"",
        "(behind.length ? \"<details class='menu map-more' id='map-more'>",
        'behind.map(function (one) { return one[0]; }).join(", ")',
        # Measured again when the window changes and when the ticks do.
        "sizeFrame(); drawTransport();",
        "if (!CLOCKED && !PICK) { drawTransport(); }",
    ):
        assert piece in script, piece
    presses = script.split("function morePresses()", 1)[1].split(
        "function moreHtml", 1
    )[0]
    order = [
        "Note here",
        "Note on all shown",
        "Within a circle",
        "Save a picture",
        "Save a timelapse",
        "Tidy names",
    ]
    places = [
        presses.index(">" + words + "<")
        if words != "Within a circle"
        else presses.index('"Within a circle"')
        for words in order
    ]
    assert places == sorted(places), "the order More lists them"
    css = (HERE / "static" / "app.css").read_text(encoding="utf-8")
    for rule in (
        ".map-more-open { display: inline-flex;",
        ".map-layer-card.map-lapse { max-width: 760px; }",
        ".map-lapse-bar i { display: block;",
        ".map-tab.map-capturing .map-pane { margin: 0 auto; }",
    ):
        assert rule in css, rule


def test_the_word_is_in_the_glossary_the_spec_and_the_guide():
    glossary = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    assert "**Timelapse**" in glossary
    spec = (ROOT / "docs" / "spec" / "SPEC-PHASE-12.md").read_text(encoding="utf-8")
    assert "### 6.12 Save a timelapse, and More unfolded" in spec
    guide = (ROOT / "docs" / "user-guide.md").read_text(encoding="utf-8")
    assert "**Save a timelapse**" in guide
