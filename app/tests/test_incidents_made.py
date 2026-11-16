"""v1.243.0: the Incidents tab once an incident is made (Phase 12 chapter 10
as amended; the drawing phase-12-incidents-tab-made.html).

The rules checked here: the day's incidents are a band across the top of the
tab and the lead's count and the panel under Your incident are gone; the one
Clear the ticks is at the head of the tick boxes; Make the incident asks in
the page's own voice and clears the ticks only once the incident exists, a
span set by hand staying; Add the ticked clears them the same way; the one
just made is marked and its name never gives way; and the words are in the
glossary, the guide, the specification and the changelog. What the app
answers Make the incident with is checked in test_incident_from_span.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from core import settings_store
from core.cases import Case
from core.models import User
from tests.helpers import signed_in
from tests.test_incidents_tidy import PASSWORD, video

APP = Path(__file__).resolve().parent.parent
ROOT = APP.parent


def static(name: str) -> str:
    return (APP / "static" / name).read_text(encoding="utf-8")


def body_of(script: str, head: str) -> str:
    """One function of the page script, from its head to its closing brace."""
    return script.split(head, 1)[1].split("\n  }\n", 1)[0]


@pytest.fixture(autouse=True)
def incidents_on(db):
    settings_store.set_to("folder_management", True)
    settings_store.set_to("incidents", True)


def test_the_tab_has_the_band_and_the_old_places_are_gone(client, db):
    person = User.objects.create_local_admin("band", PASSWORD)
    case = Case.objects.create(owner=person, name="Harbour Street stop")
    video(person, case, "BWC2-1")
    browser = signed_in(client, person)
    page = browser.get(f"/case/{case.pk}?tab=incidents").content.decode()
    # The band above the desk, with the list its two presses open.
    assert 'class="inc-band card" id="desk-band"' in page
    # Until the strip is read, the band says how many the case holds.
    assert "No incident built yet" in page
    assert 'id="incidents-list"' in page
    assert page.index('id="desk-band"') < page.index('id="incident-desk"')
    # The lead keeps Make the incident alone; the count and the panel left.
    assert 'id="desk-make"' in page
    for gone in ('id="desk-clear"', 'id="incidents-built"', 'id="desk-built"'):
        assert gone not in page, gone


def test_the_band_is_one_row_of_cards_newest_first_with_the_new_one_marked():
    strip = static("chronology.js")
    for wanted in (
        "function bandRows(d)",
        "function bandCard(one, d)",
        "function bandHtml(d, rows, shown)",
        "function bandDraw(d)",
        "Incidents on ",
        " built · newest first",
        "data-act='more-day'",
        "data-act='every-day'",
        "data-act='add-ticked'",
        "class='btn tiny primary'",
        '"Added to" : "New"',
        "made by you",
    ):
        assert wanted in strip, wanted
    # As many cards as fit the one row, never fewer than one.
    draw = body_of(strip, "function bandDraw(d) {")
    assert "while (shown > 1 && box.scrollWidth > box.clientWidth + 1)" in draw
    # Newest first in truth: the reading's `made`, sorted as it is taken.
    assert 'String(b.made || "") < String(a.made || "") ? -1' in strip
    # One just made of videos with no clock is still shown.
    assert "it is still shown, so what was made is never out of sight" in strip
    # The panel under Your incident and its code are gone.
    for gone in ("builtHtml", "builtDraw", "desk-built", "incidents-built"):
        assert gone not in strip, gone


def test_clear_the_ticks_is_at_the_head_of_the_tick_boxes_and_nowhere_else():
    strip = static("chronology.js")
    head = body_of(strip, "function ticksHead() {")
    assert "id='chron-ticks-head'" in head and "data-act='clear-ticks'" in head
    assert "Tick a camera to start" in head and " ticked</b>" in head
    assert "at most" in head
    # Drawn between the names' row and the lanes' box.
    assert (
        "id='chron-tags'></div></div>\" + ticksHead() + \"<div class='lanes-scroll'"
        in strip
    )
    # One press only: the lead's and Your incident's own are gone.
    assert strip.count("data-act='clear-ticks'") == 2  # the head, and its wiring
    assert "data-act='clear-ticks'" not in body_of(strip, "function yoursHtml(d) {")
    assert "desk-clear" not in strip


def test_the_ticks_are_cleared_only_once_the_incident_exists():
    strip = static("chronology.js")
    make = body_of(strip, "function makeIncident(box) {")
    # Asked in the page's own voice, never a form sent and the page left.
    assert 'form.append("answer", "json")' in make and "fetch(host.dataset.new" in make
    assert "form.submit()" not in strip
    # Cleared after the app's yes, before the page leaves for the incident.
    assert 'if (d) { madeClean(d, told.id, "made"); } location.href = told.url;' in make
    assert make.index("madeClean(") > make.index("if (!answer.ok || !told.url)")
    # A refusal clears nothing and says so.
    assert "Your ticks are as you left them." in make
    assert "madeClean" not in make.split(".catch(")[1]
    # What is cleared: the ticks, the name, the clock line, the handles'
    # narrowing; never the span set by hand.
    clean = body_of(strip, "function madeClean(d, id, kind) {")
    for wanted in (
        "ticks = {}",
        "state.buildSpan = null",
        "state.clockAt = null",
        "state.buildName = undefined",
        "remember(d)",
        "sessionStorage.setItem(freshKey",
    ):
        assert wanted in clean, wanted
    assert "setSpan" not in clean
    # Add the ticked clears them the same way.
    add = body_of(strip, "function addDay(incidentId, ids, d) {")
    assert 'madeClean(d, incidentId, "added"); location.href = done.url;' in add
    # Back out of the browser's own keep reads the strip again.
    assert 'window.addEventListener("pageshow"' in strip and "ev.persisted" in strip


def test_the_one_just_made_is_marked_on_the_lanes_and_never_gives_way():
    strip = static("chronology.js")
    columns = body_of(strip, "function columns(d) {")
    assert '(isFresh ? " fresh" : "")' in columns
    settle = body_of(strip, "function settleTags(box) {")
    assert 'q.classList.contains("fresh")' in settle
    assert settle.index("tags.sort(") < settle.index("tags.forEach(")


def test_the_styles_are_there_and_the_old_panels_are_not():
    css = static("app.css")
    for wanted in (
        ".inc-band-wrap {",
        ".inc-band {",
        ".inc-card {",
        ".inc-card.fresh {",
        ".new-mark {",
        ".chron .ticks-head {",
        ".chron .ticks-head .tk-mark.some {",
        ".chron .tags .tag.fresh {",
        ".chron .col.inc.fresh {",
        # Your incident's sitting bar, in view again with this release.
        ".desk-panel .sit {",
    ):
        assert wanted in css, wanted
    assert ".desk-built" not in css


def test_the_words_are_in_the_glossary_the_guide_the_spec_and_the_changelog():
    glossary = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
    assert "**Incidents band**:" in glossary
    assert "From v1.212.0 to v1.242.0, the panel under Your incident" in glossary
    assert "the one press at the head of the tick boxes" in glossary
    guide = (ROOT / "docs" / "user-guide.md").read_text(encoding="utf-8")
    assert "**Incidents on** the day is one row of cards, newest first" in guide
    assert "at the head of the tick boxes a row that says how many are ticked" in guide
    assert "your ticks are as you left them" in guide
    assert "**Built on this day**" not in guide and "**N incidents built**" not in guide
    spec = (ROOT / "docs" / "spec" / "SPEC-PHASE-12.md").read_text(encoding="utf-8")
    assert "### Once an incident is made, and where the built ones are" in spec
    assert "phase-12-incidents-tab-made.html" in spec
    drawing = ROOT / "docs" / "spec" / "mockups" / "phase-12-incidents-tab-made.html"
    # The drawing is kept; the local demo's picture is not.
    assert drawing.exists() and "<img" not in drawing.read_text(encoding="utf-8")
    log = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## v1.243.0" in log and "The ticks clear themselves." in log
