"""What the sign-out dialog says, without a database.

The rules that decide when a Discard runs need real rows and are checked on
the server. What is checked here is the wording, because it is the part a
person reads and the part that is easy to get wrong at zero and at one.
"""

from unittest import mock

from core import lifecycle

TALLY = {
    "recordings": 0,
    "transcripts": 0,
    "summaries": 0,
    "chats": 0,
    "clips": 0,
    "clips_not_downloaded": 0,
    "running": 0,
    "gigabytes": 0.0,
}


def lines_for(**counts):
    # The counts come from the database and the hours from a setting; neither
    # is what these check, so both are stood in for.
    with (
        mock.patch.object(lifecycle, "counts", return_value={**TALLY, **counts}),
        mock.patch.object(lifecycle.settings_store, "get", return_value=8 * 60),
    ):
        return lifecycle.sign_out_lines(user=None)


def test_an_empty_workspace_says_there_is_nothing_to_remove():
    assert lines_for() == ["There is nothing here to remove."]


def test_one_recording_reads_in_the_singular():
    assert lines_for(recordings=1, transcripts=1) == [
        "Signing out removes 1 recording and its transcript."
    ]


def test_several_recordings_are_counted():
    assert lines_for(recordings=3, transcripts=3) == [
        "Signing out removes 3 recordings and their transcripts."
    ]


def test_a_recording_without_a_transcript_is_still_counted():
    assert lines_for(recordings=2) == ["Signing out removes 2 recordings."]


def test_a_running_transcription_is_said_to_finish_first():
    lines = lines_for(recordings=1, running=1)
    assert lines[1].startswith("1 transcription is still running.")
    assert "8 hours after that unless you sign in again" in lines[1]


def test_two_running_transcriptions_read_in_the_plural():
    lines = lines_for(recordings=2, running=2)
    assert lines[1].startswith("2 transcriptions are still running.")
    assert "They will finish" in lines[1]
