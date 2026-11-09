"""The recording page's head and height (Phase 13 chapter 2, release 1,
v1.221.0; the drawing phase-13-recording-page.html, figures 2, 5, 7 and
8): the recording walker in place of the list under the video, the head on
one line, the marking strip as the timeline's tooltip, the speakers folded
on a short window with the hint behind a mark, and the follow state in the
tab bar in place of the floating pill."""

from pathlib import Path

from core.viewer import _walk

APP = Path(__file__).resolve().parent.parent
PAGE = (APP / "templates" / "viewer.html").read_text(encoding="utf-8")
SCRIPT = (APP / "static" / "viewer.js").read_text(encoding="utf-8")
CSS = (APP / "static" / "app.css").read_text(encoding="utf-8")


def rows(*marks):
    # "h" here, "r" ready, "." not ready; the recording is its index.
    return [
        {"here": m == "h", "ready": m in "hr", "recording": i}
        for i, m in enumerate(marks)
    ]


def test_the_walker_finds_the_ready_neighbours():
    walk = _walk(rows("r", ".", "h", ".", "r", "r"))
    assert walk["place"] == 3 and walk["count"] == 6
    assert walk["prev"] == 0 and walk["next"] == 4


def test_the_walker_stops_at_the_ends_and_outside_a_case():
    first = {"place": 1, "count": 2, "prev": None, "next": 1}
    assert _walk(rows("h", "r")) == first
    last = {"place": 3, "count": 3, "prev": 1, "next": None}
    assert _walk(rows(".", "r", "h")) == last
    assert _walk([]) == {}
    assert _walk(rows("r", "r")) == {}


def test_the_hand_off_keeps_the_moment_between_cameras():
    # Release 2 (v1.222.0): a recording's start on one scale across days,
    # None off the clock; the walker and its arrows carry the starts and
    # lengths, and the script keeps the moment when both are on the clock.
    import datetime as dt
    from types import SimpleNamespace

    from core.viewer import _clock_seconds

    on = SimpleNamespace(clock_date=dt.date(2025, 11, 6), clock_start=51600.0)
    later = SimpleNamespace(clock_date=dt.date(2025, 11, 7), clock_start=0.0)
    assert _clock_seconds(later) - _clock_seconds(on) == 86400 - 51600
    assert _clock_seconds(SimpleNamespace(clock_date=None, clock_start=5.0)) is None
    assert _clock_seconds(None) is None
    assert "data-start=\"{{ walk.here_start|default_if_none:'' }}\"" in PAGE
    assert "data-start=\"{{ walk.next_start|default_if_none:'' }}\"" in PAGE
    assert 'data-length="{{ walk.next_length }}"' in PAGE
    assert "var same = hereStart + at - otherStart;" in SCRIPT
    assert 'if (same >= 0 && (!length || same <= length)) { href += "?t="' in SCRIPT
    assert "window.VIEWER.walkTo = walkTo;" in SCRIPT
    # The reader's next assigned recording at the list's foot.
    assert "{% if walk.assigned_next %}" in PAGE
    assert 'class="walker-assigned"><b>Next assigned to you:' in PAGE


def test_the_walker_stands_in_the_head_and_the_rail_is_gone():
    assert '<nav class="walker" id="walker"' in PAGE
    assert 'id="walk-prev"' in PAGE and 'id="walk-next"' in PAGE
    assert '<details class="menu which" id="walker-menu">' in PAGE
    assert "{{ walk.place }} of {{ walk.count }}" in PAGE
    assert "Download all transcripts" in PAGE
    assert 'class="caserail"' not in PAGE and 'id="case-more"' not in PAGE
    assert "caserail-fold" not in SCRIPT and 'getElementById("case-more")' not in SCRIPT
    # The keys, and the shortcuts list saying so.
    assert 'event.key === "<" || event.key === ">"' in SCRIPT
    assert "<kbd>&lt; &gt;</kbd>" in PAGE


def test_the_head_is_one_line_with_the_title_cut():
    assert '<h1 id="recording-title" title="{{ recording.title }}">' in PAGE
    assert 'class="btn ghost icon rename" id="rename-title"' in PAGE
    for rule in (
        "@media (min-width: 1280px) {\n  .desk .head { flex-direction: row;",
        "min-width: 12rem; white-space: nowrap; overflow: hidden;",
        ".desk .head .head-title .rename { opacity: 0;",
        ".desk .caption:not(.marking) { display: none; }",
    ):
        assert rule in CSS, rule
    assert 'id="timeline" title="Click to jump; drag along it to mark a clip"' in PAGE


def test_the_speakers_fold_and_the_hint_sits_behind_its_mark():
    assert 'id="cast-help"' in PAGE
    assert '<div class="hint" id="cast-hint" hidden>' in PAGE
    assert 'data-hint="speakers"' not in PAGE
    fold = 'rememberedFold ? rememberedFold === "yes" : window.innerHeight < 900'
    assert fold in SCRIPT
    row = ".cast.folded .speakerchips { display: flex; flex-wrap: nowrap;"
    assert row in CSS


def test_the_follow_state_lives_in_the_tab_bar():
    assert '<span class="followstate small" id="follow-state" data-paused="no">' in PAGE
    assert 'id="follow-pause"' in PAGE and 'id="resume-follow"' in PAGE
    assert 'class="followhold"' not in PAGE and 'id="follow-pill"' not in PAGE
    assert "function showFollowState()" in SCRIPT
    assert 'followState.dataset.paused = paused ? "yes" : "no"' in SCRIPT
    assert '.followstate[data-paused="yes"] .is-paused { display: inline-flex; }' in CSS
