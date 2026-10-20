"""The performance pass's browser findings (v1.134.0): what the scripts must
keep doing, held as guard rails in the files' own words, and the assistant
state's small busy question against its whole answer.

A hidden tab asks the server nothing and asks once when it comes back; the
Status and Queue pages slow down as they are left alone and stop after an
hour; the recording page's Find waits 150 ms after a keystroke; the
Speakers page reads the segments without their words; the incident and
recording pages ask only whether anything is still busy while it is; the
front door compresses the pages and their JSON, and nothing else.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from core import assistant, settings_store
from core.assistant import Chat, ChatTurn, Summary
from core.jobs import Segment, Transcript
from core.models import User
from core.recordings import Batch, MediaState, Recording
from django.db import connection
from django.test.utils import CaptureQueriesContext
from tests.helpers import signed_in

PASSWORD = "a-long-enough-password"
APP = Path(__file__).resolve().parent.parent
STATIC = APP / "static"
ROOT = APP.parent


def script(name: str) -> str:
    return (STATIC / name).read_text(encoding="utf-8")


# The hidden-tab rule --------------------------------------------------------


def test_the_shared_helper_holds_the_hidden_tab_rule_once():
    ui = script("ui.js")
    assert "function pollingAllowed() { return !document.hidden; }" in ui
    assert "function whenVisible() {" in ui
    assert 'document.addEventListener("visibilitychange"' in ui
    assert "function poll(ask, every, options) {" in ui
    # The waits as the page is left alone: 15 s after a minute, 60 s after
    # ten, and a stop after an hour that the page is told about.
    assert "if (alone >= 60 * A_MINUTE) { return -1; }" in ui
    assert "if (alone >= 10 * A_MINUTE) { return Math.max(every, 60000); }" in ui
    assert "if (alone >= A_MINUTE) { return Math.max(every, 15000); }" in ui
    assert "if (options.paused) { options.paused(true); }" in ui
    for touch in ("click", "keydown", "scroll", "pointerdown", "wheel", "touchstart"):
        assert f'"{touch}"' in ui
    assert "pollingAllowed: pollingAllowed, whenVisible: whenVisible, poll: poll" in ui


def test_the_panel_pages_poll_through_the_helper_and_say_when_paused():
    for name in ("panel-status.js", "panel-queue.js"):
        text = script(name)
        assert "window.UI.poll(ask, EVERY, {" in text, name
        assert "pausedLine.hidden = !isPaused" in text, name
        assert "window.setTimeout(ask, EVERY)" not in text, name
    for page in ("status.html", "queue.html"):
        html = (APP / "templates" / "panel" / page).read_text(encoding="utf-8")
        assert '<p id="poll-paused" class="muted small" hidden>' in html, page
    # The integrity check's answer is the worker's line, with the old
    # summary kept for an app that still walks the chain in the request.
    status = script("panel-status.js")
    assert "said.textContent = result.says || (result.message" in status
    # A cancel on the Queue page asks for a fresh reading, not a second chain.
    assert ".then(function () { polling.now(); });" in script("panel-queue.js")


@pytest.mark.parametrize(
    "name, line",
    [
        (
            "assistant.js",
            "window.UI.whenVisible().then(function () { return fetch("
            '"/recording/" + recording + "/assistant"); })',
        ),
        (
            "case-chat.js",
            "window.UI.whenVisible().then(function () { return fetch("
            '"/case/" + caseId + "/chat"); })',
        ),
        (
            "gideon.js",
            "window.UI.whenVisible().then(function () { return fetch("
            '"/case/" + caseId + "/incident/" + incidentId + "/chat"); })',
        ),
        (
            "incident.js",
            "window.UI.whenVisible().then(function () { return fetch(C.state); })",
        ),
        (
            "batch.js",
            "window.UI.whenVisible().then(function () { return fetch("
            '"/batch/" + window.BATCH + "/state"); })',
        ),
        (
            "speakers-page.js",
            "window.UI.whenVisible().then(function () { return fetch("
            '"/recording/" + V.recording + "/assistant"); })',
        ),
        ("dictations.js", "if (!window.UI.pollingAllowed()) { return; }"),
        ("record.js", "if (!window.UI.pollingAllowed()) { return; }"),
        ("viewer.js", "if (!window.UI.pollingAllowed()) { return; }"),
    ],
)
def test_every_poll_waits_for_the_tab(name, line):
    assert line in script(name), name


def test_no_poll_fetches_without_asking_the_tab_first():
    """Every fetch that a timer calls again goes behind the helper: the
    pollers named by the audit, held by the lines a timer schedules."""
    expected = {
        "assistant.js": ["timer = window.setTimeout(askIfBusy, EVERY)"],
        "case-chat.js": ["timer = window.setTimeout(refresh, EVERY)"],
        "gideon.js": ["timer = window.setTimeout(refresh, EVERY)"],
        "incident.js": ["pollTimer = window.setTimeout(askIfBusy, 3000)"],
        "batch.js": ["window.setTimeout(ask, EVERY)"],
        "speakers-page.js": [
            "suggestTimer = window.setTimeout(refreshSuggestions, 6000)"
        ],
    }
    for name, lines in expected.items():
        text = script(name)
        for line in lines:
            assert line in text, (name, line)
        assert "whenVisible" in text, name


# The viewer's watchers stop ---------------------------------------------------


def test_the_viewers_watchers_stop_when_the_work_has_ended():
    viewer = script("viewer.js")
    queue = viewer[viewer.index("function watchTheQueue()") :]
    queue = queue[: queue.index("function watchThePlayer()")]
    assert "var watching = window.setInterval(function () {" in queue
    assert "if (!mine) { window.clearInterval(watching); return; }" in queue
    assert (
        'job.state === "failed" || job.state === "cancelled" || job.state === "done"'
        in queue
    )
    assert 'mine.state === "rejected" || mine.state === "failed"' in queue
    player = viewer[viewer.index("function watchThePlayer()") :]
    player = player[: player.index("var cancel = ")]
    assert (
        "if (state.ready) { window.clearInterval(watching); "
        "window.location.reload(); return; }" in player
    )
    assert (
        "if (state.failed || state.gone) { window.clearInterval(watching); }" in player
    )


# The incident page's poll and tick -------------------------------------------


def test_the_incident_page_asks_only_whether_it_is_still_busy():
    incident = script("incident.js")
    assert 'fetch(C.state + "?what=busy")' in incident
    assert "if (Date.now() - busySince >= 30000) { refresh(); return; }" in incident
    # An app without the question answers with the whole state, taken as before.
    assert (
        "if (said && said.cameras) { busySince = 0; take(said); return; }" in incident
    )
    assert (
        'if (!said || typeof said.busy !== "boolean" || !said.busy) '
        "{ refresh(); return; }" in incident
    )
    assert "pollTimer = window.setTimeout(refresh, 3000)" not in incident
    assert incident.count("askLater();") >= 2


def test_the_incident_tick_rests_while_nothing_moves():
    incident = script("incident.js")
    assert "window.setInterval(tickIfMoved, 200);" in incident
    assert "window.setInterval(tick, 200);" not in incident
    assert (
        "if (!playing && now() === tickedAt && key === tickedKey) { return; }"
        in incident
    )
    # The line at a moment by a binary search; the words written only on a change.
    assert "var middle = (low + high) >> 1;" in incident
    assert (
        "if (entry.shownLine === shown && entry.shownIn === box) { return; }"
        in incident
    )
    assert "if (!entry.barParts || entry.barParts.bar !== bar) {" in incident


# The recording page's Find and rows -------------------------------------------


def test_find_waits_after_a_keystroke_and_touches_only_the_marked_rows():
    viewer = script("viewer.js")
    assert 'search.addEventListener("input", lookSoon);' in viewer
    assert (
        "lookTimer = window.setTimeout(function () { lookTimer = null; look(); }, "
        "150);" in viewer
    )
    assert 'row.lowered = (segment.text || "").toLowerCase();' in viewer
    assert "} else if (row.marked) {" in viewer
    # Enter before the pause is up searches now.
    assert (
        "if (lookTimer) { window.clearTimeout(lookTimer); lookTimer = null; look(); }"
        in viewer
    )


def test_a_note_or_a_reload_redraws_the_rows_that_changed():
    viewer = script("viewer.js")
    assert "function redrawChanged() {" in viewer
    assert "function signatureOf(segment, index) {" in viewer
    assert "if (sameCount) { redrawChanged(); } else { draw(); }" in viewer
    assert "if (rowAt < 0) { draw(); } else { redrawRow(segments[rowAt]); }" in viewer
    # The first build and a reload with another count still draw the whole column.
    assert "function draw() {" in viewer and viewer.count("draw();") >= 3


# The words left out ---------------------------------------------------------------


def test_the_window_reads_the_segments_without_words():
    # The window still reads lines alone. The Speakers page reads the words
    # again since v1.141.0 (the plan's section 12): the line in hand lights
    # each word as the voice reaches it, which v1.134.0's saving had cost.
    text = script("viewer-window.js")
    assert '"/segments?words=0"' in text
    assert ".words" not in text
    # Every reader of a segment's words tolerates a segment without them.
    tolerant = "!wordTiming || !segment.words || !segment.words.length"
    for name in ("viewer.js", "speakers-page.js"):
        assert tolerant in script(name), name


# The front door ---------------------------------------------------------------------


def test_the_front_door_compresses_the_pages_and_not_the_media():
    caddyfile = (ROOT / "caddy" / "Caddyfile").read_text(encoding="utf-8")
    catch_all = caddyfile[caddyfile.index("handle {\n\t\trequest_body") :]
    assert "\t\tencode zstd gzip\n" in catch_all
    assert caddyfile.count("encode zstd gzip") == 1
    media = caddyfile.index("handle /media/*")
    hook = caddyfile.index("handle /upload-hook*")
    assert "encode" not in caddyfile[media:hook]
    uploads = caddyfile.index("handle /files/*")
    assert "encode" not in caddyfile[uploads:media]


# The assistant's busy question ---------------------------------------------------


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("asker", PASSWORD)


@pytest.fixture
def ready(person, tmp_path, settings):
    settings.DATA_DIR = tmp_path
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        title="Interview",
        original_filename="interview.mp4",
        media_state=MediaState.READY,
        duration_seconds=900.0,
    )
    transcript = Transcript.objects.create(recording=recording, language="en")
    Segment.objects.create(
        transcript=transcript,
        start=0.0,
        end=5.0,
        text="This is Detective Ruiz.",
        speaker="Speaker 1",
        speaker_label="SPEAKER_1",
    )
    settings_store.set_to("assistant_available", True)
    settings_store.set_to("summary_available", True)
    settings_store.set_to("chat_available", True)
    return recording


def test_the_busy_question_says_what_the_whole_state_says(client, person, ready):
    signed_in(client, person)
    url = f"/recording/{ready.pk}/assistant"
    small = client.get(url + "?what=busy").json()
    assert small == {"busy": False, "stage": ""}
    whole = client.get(url).json()
    assert whole["busy"] is False and whole["stage"] == ""
    assert "summaries" in whole and "summaries" not in small

    summary = Summary.objects.create(
        recording=ready,
        asked_by=person,
        template_name="Default",
        state=assistant.QUEUED,
        stage="preparing",
    )
    chat = Chat.objects.create(recording=ready, asked_by=person)
    ChatTurn.objects.create(
        chat=chat, number=1, question="What car?", state=assistant.RUNNING
    )
    small = client.get(url + "?what=busy").json()
    whole = client.get(url).json()
    assert small["busy"] is True and whole["busy"] is True
    assert small["stage"] == f"summary {summary.pk} preparing; chat {chat.pk}"
    assert whole["stage"] == small["stage"]

    # The stage moves with the work, and the words empty when it ends.
    Summary.objects.filter(pk=summary.pk).update(stage="condensing 2 of 5")
    assert (
        client.get(url + "?what=busy")
        .json()["stage"]
        .startswith(f"summary {summary.pk} condensing 2 of 5")
    )
    Summary.objects.filter(pk=summary.pk).update(state=assistant.DONE, stage="")
    ChatTurn.objects.filter(chat=chat).update(state=assistant.DONE)
    assert client.get(url + "?what=busy").json() == {"busy": False, "stage": ""}


def test_the_busy_question_is_a_handful_of_queries(client, person, ready):
    """Measured against the simplest JSON answer on a recording, the media
    state, so the request's own queries (the session, the person, the
    settings) are not the thing counted."""
    signed_in(client, person)
    Summary.objects.create(
        recording=ready,
        asked_by=person,
        template_name="Default",
        state=assistant.QUEUED,
    )
    Chat.objects.create(recording=ready, asked_by=person)

    def queries_of(url):
        with CaptureQueriesContext(connection) as caught:
            answer = client.get(url).json()
        return len(caught), answer

    baseline, _ = queries_of(f"/recording/{ready.pk}/media")
    small, told = queries_of(f"/recording/{ready.pk}/assistant?what=busy")
    whole, _ = queries_of(f"/recording/{ready.pk}/assistant")
    assert told["busy"] is True
    # The transcript, two settings and one query a kind of work over the
    # request's own; the whole state is several times that.
    assert small <= baseline + 10
    assert small * 2 < whole


def test_the_summary_tab_is_built_again_only_when_a_summary_changed():
    text = script("assistant.js")
    assert "if (summariesKey === drawnSummaries) { return; }" in text
    assert "if (templateChoice && templatesKey !== drawnTemplates) {" in text
    assert 'fetch("/recording/" + recording + "/assistant?what=busy")' in text
    assert "if (Date.now() - busySince >= 30000) { refresh(); return; }" in text
    assert "said.stage !== state.stage" in text
