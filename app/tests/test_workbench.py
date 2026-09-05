"""The Workbench Layout on the pages that are documents: Upload, Recordings, Batch.

Each page has two shapes, chosen by the width of the window, and the script
asks the same question as the stylesheet. These tests hold the pieces together
without a browser.
"""

from pathlib import Path

APP = Path(__file__).resolve().parent.parent
WIDE = "(min-width: 1280px)"


def page(name):
    return (APP / "templates" / name).read_text(encoding="utf-8")


def script(name):
    return (APP / "static" / name).read_text(encoding="utf-8")


def test_the_upload_page_keeps_its_three_steps_and_gains_the_wide_shape():
    upload = page("upload.html")
    assert 'class="page workbench"' in upload
    for step in ("step-1", "step-2", "step-3"):
        assert f'id="{step}"' in upload
    assert "<h2>1. Choose files</h2>" in upload
    assert 'id="exceptions-block"' in upload
    js = script("upload.js")
    assert f'window.matchMedia("{WIDE}")' in js
    # Every step is shown at once on the wide shape, and the review follows.
    assert "element.hidden = allAtOnce() ? false : each !== number;" in js
    assert "start.disabled = !usable().length;" in js


def test_the_recordings_page_is_a_table_with_one_details_block_per_row():
    recordings = page("recordings.html")
    assert 'id="recordings"' in recordings
    assert 'class="pick"' in recordings
    assert 'class="detail-row"' in recordings
    assert 'id="detail-{{ recording.pk }}"' in recordings
    assert 'id="detail-pane"' in recordings
    # The row and the details say the same word, worked out once.
    assert recordings.count("{{ recording.state_word }}") == 2
    js = script("recordings.js")
    assert f'window.matchMedia("{WIDE}")' in js
    assert "pane.appendChild(detail)" in js


def test_the_batch_page_has_the_ready_now_pane():
    batch = page("batch.html")
    assert 'id="ready"' in batch and 'id="ready-none"' in batch
    assert 'id="while-running"' in batch
    js = script("batch.js")
    assert "one.has_transcript" in js
    assert "still to come" in js


def test_the_stylesheet_has_both_shapes_for_the_pages():
    css = script("app.css")
    assert ".panes { display: grid;" in css
    assert "#detail-pane { display: none; }" in css
    wide = css[css.index("@media " + WIDE + " {\n  .page.workbench") :]
    assert "#detail-pane { display: block; }" in wide
    assert '"one two" "one three"' in wide
    assert ".workbench #exceptions-block { display: none; }" in wide


def test_the_cases_pages_share_the_strip_and_the_chooser():
    cases = page("cases.html")
    assert '{% include "cases-tabs.html" %}' in cases
    assert 'id="recordings"' in cases and 'id="detail-pane"' in cases
    assert "Everyone else's" not in cases
    strip = page("cases-tabs.html")
    for view in ("mine", "everyone", "bin"):
        assert f"who == '{view}'" in strip
    bin_page = page("recycle-bin.html")
    assert '{% include "cases-tabs.html" %}' in bin_page
    one = page("case.html")
    assert 'class="pane-detail about-case"' in one
    # The case page's rows open under themselves: no pane for them.
    assert 'id="recordings"' in one and 'id="detail-pane"' not in one
    js = script("recordings.js")
    assert "pane !== null" in js
    assert 'addEventListener("rows-changed", settle)' in js


def test_the_clips_page_is_one_table_with_a_player():
    clips = page("clips.html")
    assert 'id="clip-filter"' in clips
    assert 'data-of="{{ clip.recording.pk }}"' in clips
    assert 'class="clipplayer" src="{{ clip.url }}"' in clips
    assert "{% for group in groups %}" not in clips
    js = script("clips.js")
    assert 'new Event("rows-changed")' in js
