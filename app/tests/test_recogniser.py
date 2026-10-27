"""Phase 1 chapter 7, The recogniser (ADR 0025).

The rules checked here: the Recogniser setting exists on the Transcription
defaults page and starts at whisper; the Model setting is Whisper's and greys
under the other choice; every job carries the choice, a Live recording and
the clock re-read stay on Whisper, and nothing that asks for English goes to
Qwen3-ASR; the Upload page greys Translate to English under it with its
reason; the Details tab and the exports say which recogniser wrote the words;
a Transcript Qwen3-ASR wrote gets no clock re-read; the catalogue has the row.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from core import clock_check, exports, queue, settings_store, uploads, whisperx
from core.jobs import Job, Run, Transcript
from core.models import LoginSession, User
from core.recordings import Batch, MediaState, Recording, Side
from django.urls import reverse

PASSWORD = "a-long-enough-password"
ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def person(db):
    return User.objects.create_local_admin("asker", PASSWORD)


@pytest.fixture
def whisper_again():
    yield
    settings_store.set_to("recogniser", "whisper")


def a_run(person, **fields) -> Run:
    recording = Recording.objects.create(
        batch=Batch.objects.create(user=person),
        user=person,
        title="a stop",
        original_filename="a-stop.mp4",
        media_state=MediaState.READY,
        diarize=True,
        **fields,
    )
    side = Side.objects.create(recording=recording, number=1)
    job = Job.objects.create(recording=recording, batch=recording.batch)
    return Run.objects.create(job=job, side=side)


@pytest.mark.django_db
def test_the_setting_starts_at_whisper_and_the_model_setting_is_whispers(
    whisper_again,
):
    assert settings_store.recogniser() == "whisper"
    known = settings_store.definition("recogniser")
    assert known.page == settings_store.TRANSCRIPTION
    assert known.choices == ("whisper", "qwen3-asr")
    model = settings_store.definition("model")
    assert model.needs_value == ("recogniser", "whisper")
    assert settings_store.greyed_because(model) == ""
    settings_store.set_to("recogniser", "qwen3-asr")
    assert "Greyed unless Recogniser is whisper" in settings_store.greyed_because(model)


@pytest.mark.django_db
def test_every_job_carries_the_choice_and_english_is_whispers(person, whisper_again):
    run = a_run(person, translate=True)
    asked = queue.request_for(run)
    assert asked["recogniser"] == "whisper"
    assert asked["task"] == "translate_if_needed"

    settings_store.set_to("recogniser", "qwen3-asr")
    asked = queue.request_for(run)
    assert asked["recogniser"] == "qwen3-asr"
    # Qwen3-ASR never writes English: the recording is transcribed in the
    # language spoken, and the mixed rule is not sent either.
    assert asked["task"] == "transcribe"
    assert "translate_if_mixed" not in asked
    plain = queue.request_for(a_run(person))
    assert plain["task"] == "transcribe" and "translate_if_mixed" not in plain

    # A Live recording stays on Whisper, as the Fast lane does.
    live = a_run(person, live={"started": "2026-10-27T09:00:00"})
    assert live.job.recording.is_live
    assert queue.request_for(live)["recogniser"] == "whisper"


@pytest.mark.django_db
def test_the_clock_reread_runs_on_whisper_and_only_for_whispers_transcripts(
    person, whisper_again, monkeypatch
):
    run = a_run(person)
    recording = run.job.recording
    transcript = Transcript.objects.create(recording=recording, language="en")
    settings_store.set_to("recogniser", "qwen3-asr")
    asked = clock_check.reread_request(recording, transcript, head=1)
    assert asked["recogniser"] == "whisper"
    assert asked["fit_words_over_whole"] is True

    # A Transcript Qwen3-ASR wrote keeps its marks and gets no re-read.
    monkeypatch.setattr(
        exports,
        "runs_of",
        lambda t: [{"settings_used": {"recogniser": "qwen3-asr", "model": "x"}}],
    )
    assert exports.recogniser_of(transcript) == "qwen3-asr"
    monkeypatch.setattr(
        exports,
        "runs_of",
        lambda t: [{"settings_used": {"model": "large-v3-turbo"}}],
    )
    # A result from before the choice existed is Whisper's.
    assert exports.recogniser_of(transcript) == "whisper"


@pytest.mark.django_db
def test_the_upload_page_greys_translate_under_qwen(
    client, person, monkeypatch, whisper_again
):
    monkeypatch.setattr(whisperx, "is_alive", lambda *a, **k: True)
    monkeypatch.setattr(uploads, "free_disk_bytes", lambda: 10**15)
    client.force_login(person)
    LoginSession.objects.create(user=person, session_key=client.session.session_key)
    page = client.get(reverse("upload")).content.decode()
    assert 'id="translate" disabled' not in page
    settings_store.set_to("recogniser", "qwen3-asr")
    page = client.get(reverse("upload")).content.decode()
    assert 'id="translate" disabled' in page
    assert "Not offered under the Qwen3-ASR recogniser yet" in page


def test_the_words_for_which_recogniser_wrote_the_words():
    assert exports.recogniser_words({"model": "large-v3-turbo"}) == (
        "Whisper large-v3-turbo"
    )
    assert exports.recogniser_words({"recogniser": "whisper", "model": "large-v3"}) == (
        "Whisper large-v3"
    )
    assert (
        exports.recogniser_words(
            {
                "recogniser": "qwen3-asr",
                "model": "qwen3-asr-1.7b",
                "recogniser_version": "7278e1e70fe2",
            }
        )
        == "Qwen3-ASR 1.7B (7278e1e7)"
    )
    assert exports.pieces_words({"recogniser": "whisper"}) == ""
    assert exports.pieces_words(
        {
            "recogniser": "qwen3-asr",
            "pieces": 3,
            "piece_seconds": 45.0,
            "words_unlengthed": 1,
        }
    ) == (
        "3 pieces of about 45 s, the lines built from the aligner's words; "
        "1 word given a span"
    )


def test_the_catalogue_and_the_guides_carry_the_recogniser():
    catalogue = (ROOT / "docs" / "spec" / "ADMIN-SETTINGS-CATALOGUE.md").read_text(
        encoding="utf-8"
    )
    assert "| Recogniser | whisper or qwen3-asr | whisper |" in catalogue
    assert (
        "not yet built" not in catalogue.split("| Recogniser |", 1)[1].split("\n", 1)[0]
    )
    compose = (ROOT / "whisperx-service" / "compose.yaml").read_text(encoding="utf-8")
    assert "gideon-transcribe-recogniser:${RELEASE_TAG:-dev}" in compose
    assert 'RECOGNISER_URL: ""' in compose
    rules = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "Four images are built here" in rules


SAMPLE_CHANGELOG = """# Changelog

## Unreleased

- a line

## v1.160.2, 2026-10-27

```
Models: changed
Database: unchanged
```

## v1.160.1, 2026-10-27

```
Models: unchanged
Database: unchanged
```

## v1.160.0, 2026-10-27

```
Models: changed
Database: unchanged
```

## v1.159.2, 2026-10-26

```
Models: unchanged
Database: migrates
```

## v1.159.1, 2026-10-26

```
Models: changed
Database: unchanged
```
"""


def sections_between(tag: str, before: str) -> str:
    """Run the script's own reader on the sample, through bash."""
    import shutil
    import subprocess

    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("no bash on this machine")
    script = (ROOT / "transcribe").read_text(encoding="utf-8")
    function = script.split("sections_between() {", 1)[1].split("\n}\n", 1)[0]
    program = (
        f"sections_between() {{{function}\n}}\nsections_between '{tag}' '{before}'"
    )
    done = subprocess.run(
        [bash, "-c", program],
        input=SAMPLE_CHANGELOG,
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout


def test_the_upgrade_reads_every_release_it_steps_over():
    # v1.160.2: an office that went from v1.159.2 to v1.160.1 was never asked
    # for v1.160.0's models.
    stepped = sections_between("v1.160.1", "v1.159.2")
    assert "## v1.160.1" in stepped and "## v1.160.0" in stepped
    assert "## v1.159.2" not in stepped and "Unreleased" not in stepped
    assert stepped.count("Models: changed") == 1
    # The target alone when nothing is stepped over.
    own = sections_between("v1.160.1", "v1.160.0")
    assert "## v1.160.1" in own and "## v1.160.0" not in own
    assert "Models: changed" not in own
    # A running release the changelog does not name: read to the end, which
    # errs towards fetching.
    unknown = sections_between("v1.160.1", "v0.9.0")
    assert "## v1.159.1" in unknown and "Models: changed" in unknown
    # No running release given: the same.
    assert "## v1.159.1" in sections_between("v1.160.1", "")
    # A tag is matched whole: v1.16 is not v1.160.1.
    assert sections_between("v1.16", "") == ""
    script = (ROOT / "transcribe").read_text(encoding="utf-8")
    assert 'models_changed "$tag" "$before"' in script
    assert 'read_the_release_lines "$tag" "$before"' in script
    assert 'sections_between "$1" "${2:-}" | grep -qE' in script
