"""Settings: what the environment says, and how long a job may take."""

import pytest
from service.settings import Settings


def read(monkeypatch, **environment):
    for key in list(environment):
        monkeypatch.setenv(key, environment[key])
    return Settings.from_environment()


def test_the_defaults_are_the_ones_the_contract_names(monkeypatch):
    for key in list(vars(Settings)):
        monkeypatch.delenv(key, raising=False)
    for key in (
        "WHISPERX_MAX_UPLOAD_GB",
        "WHISPERX_MAX_AUDIO_HOURS",
        "WHISPERX_BATCH_SIZE",
        "WHISPERX_VAD_ONSET",
        "WHISPERX_VAD_OFFSET",
        "WHISPERX_ALIGN_LANGUAGES",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = Settings.from_environment()
    assert settings.max_upload_bytes == 2 * 1024**3
    assert settings.max_audio_seconds == 8 * 3600
    assert settings.batch_size == 16
    assert settings.vad_onset == 0.50
    assert settings.vad_offset == 0.363
    assert settings.align_languages == ("en", "es")


def test_a_setting_that_is_not_a_number_says_which_one(monkeypatch):
    monkeypatch.setenv("WHISPERX_BATCH_SIZE", "sixteen")
    with pytest.raises(ValueError, match="WHISPERX_BATCH_SIZE"):
        Settings.from_environment()


def test_a_batch_size_that_is_not_whole_is_refused(monkeypatch):
    monkeypatch.setenv("WHISPERX_BATCH_SIZE", "16.5")
    with pytest.raises(ValueError, match="whole number"):
        Settings.from_environment()


def test_an_empty_setting_falls_back_to_the_default(monkeypatch):
    monkeypatch.setenv("WHISPERX_BATCH_SIZE", "")
    assert Settings.from_environment().batch_size == 16


def test_the_languages_are_read_as_a_list(monkeypatch):
    monkeypatch.setenv("WHISPERX_ALIGN_LANGUAGES", " en , es ,fr ")
    assert Settings.from_environment().align_languages == ("en", "es", "fr")


def test_a_job_gets_the_base_time_plus_time_for_its_own_length(monkeypatch):
    settings = read(
        monkeypatch,
        WHISPERX_JOB_TIMEOUT_BASE_MINUTES="30",
        WHISPERX_JOB_TIMEOUT_PER_AUDIO_HOUR_MINUTES="60",
    )
    # Half an hour to start with, and a minute for every minute of audio.
    assert settings.timeout_seconds(0) == 30 * 60
    assert settings.timeout_seconds(3600) == 30 * 60 + 3600
    assert settings.timeout_seconds(8 * 3600) == 30 * 60 + 8 * 3600


def test_the_folders_hang_off_the_state_folder(monkeypatch):
    monkeypatch.setenv("WHISPERX_STATE_DIR", "/srv/state")
    settings = Settings.from_environment()
    assert settings.audio_dir.name == "audio"
    assert settings.results_dir.name == "results"
    assert settings.database_file.name == "jobs.sqlite3"
    assert settings.database_file.parent == settings.state_dir
