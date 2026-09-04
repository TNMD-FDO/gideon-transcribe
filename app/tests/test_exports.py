"""What an export says, without a database and without Word.

The Word file itself is checked by opening one; what is checked here is the
wording, which is the part that has to be right on every export: the kind
line, the one notice, the head of the plain-text file, the cue shape, and the
file names a Windows machine has to accept.
"""

from datetime import datetime

import pytest
from core import exports, settings_store


@pytest.fixture(autouse=True)
def settings_at_their_defaults(monkeypatch):
    """The notices are admin settings now, and these checks have no database.

    Read at their defaults, which is what an office that has not changed them
    has, and what the catalogue's wording says they say.
    """
    monkeypatch.setattr(
        settings_store, "get", lambda key: settings_store.definition(key).default
    )


class Fake:
    """Anything with the fields the exports read, and nothing else."""

    def __init__(self, **fields):
        self.__dict__.update(fields)


class Segments:
    """Stands in for the related manager the exports walk.

    It answers filter() as well, because the exports leave out the second
    copy of what both Sides of a call heard, and a stand-in that could not be
    filtered would have hidden that rather than checked it.
    """

    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self

    def select_related(self, *_):
        return self

    def filter(self, **wanted):
        return Segments(
            [
                one
                for one in self.rows
                if all(getattr(one, name) == value for name, value in wanted.items())
            ]
        )

    def __iter__(self):
        return iter(self.rows)

    def __len__(self):
        return len(self.rows)


def segment(
    start,
    end,
    text,
    speaker="",
    label="",
    corrected=False,
    side=None,
    same_as_other_side=False,
):
    return Fake(
        same_as_other_side=same_as_other_side,
        start=start,
        end=end,
        text=text,
        speaker=speaker,
        speaker_label=label,
        corrected=corrected,
        side=side,
    )


def transcript(**fields):
    fields.setdefault("task_run", "transcribe")
    fields.setdefault("language", "en")
    fields.setdefault("language_mixed", False)
    fields.setdefault("language_probability", 0.99)
    fields.setdefault("detection", {})
    fields.setdefault("word_timestamps", True)
    fields.setdefault("word_timestamps_reason", "")
    fields.setdefault("created", datetime(2026, 9, 3, 10, 30))
    fields.setdefault(
        "provenance", {"one": {"settings_used": {"model": "large-v3-turbo"}}}
    )
    fields.setdefault("segments", Segments([]))
    # What both Sides of a call said together: none, unless a check says so.
    fields.setdefault("shared_segments", 0)
    return Fake(**fields)


def recording(**fields):
    fields.setdefault("title", "Call with the client")
    fields.setdefault("original_filename", "jail-call.mp3")
    fields.setdefault("duration_seconds", 1500)
    fields.setdefault("size_bytes", 12 * 1024 * 1024)
    fields.setdefault("sha256", "a" * 64)
    fields.setdefault("created", datetime(2026, 9, 2, 9, 0))
    fields.setdefault("user", Fake(username="dmeehan"))
    fields.setdefault("preprocessing", "standard")
    fields.setdefault("is_two_channel_call", False)
    one = Fake(**fields)
    one.transcript = fields.get("transcript") or transcript()
    return one


# The kind line ----------------------------------------------------------------


def test_an_english_transcript_is_just_a_transcript():
    assert exports.kind_line(transcript()) == "Transcript"


def test_a_transcript_left_in_its_own_language_says_so():
    assert exports.kind_line(transcript(language="es")) == "Transcript in Spanish"


def test_a_translation_names_the_language_it_came_from():
    assert (
        exports.kind_line(transcript(task_run="translate", language="es"))
        == "Translated to English from Spanish"
    )


def test_a_mixed_recording_names_every_language_heard():
    mixed = transcript(
        task_run="translate",
        language="es",
        language_mixed=True,
        detection={"combined": {"es": 9, "en": 4}},
    )
    assert exports.kind_line(mixed) == (
        "Translated to English (Spanish and English detected)"
    )


# The one notice ---------------------------------------------------------------


def test_a_transcript_carries_the_transcription_notice_and_not_the_other():
    notice = exports.notice_for(transcript())
    assert "Automatic transcription by Whisper large-v3-turbo" in notice
    assert "Machine translation" not in notice


def test_a_translation_carries_the_translation_notice_and_not_the_other():
    notice = exports.notice_for(transcript(task_run="translate", language="es"))
    assert "Machine translation to English from Spanish" in notice
    assert "Automatic transcription" not in notice


# The plain-text head ----------------------------------------------------------


def test_the_head_is_four_lines_then_a_blank_one():
    one = recording()
    one.transcript.segments = Segments(
        [segment(0, 4, "Hello.", "Speaker 1", "SPEAKER_00")]
    )
    lines = exports.plain_text(one).split("\r\n")

    assert lines[0] == "Call with the client"
    assert lines[1] == (
        "Transcript. jail-call.mp3, 25 min, uploaded 02 September 2026 by "
        "dmeehan. Processed 03 September 2026 with Whisper large-v3-turbo."
    )
    assert lines[2] == "Speakers: Speaker 1 (SPEAKER_00)"
    assert lines[3].startswith("Automatic transcription")
    assert lines[4] == ""
    assert lines[5] == "[00:00:00] Speaker 1: Hello."


def test_without_speakers_the_head_is_three_lines_and_the_lines_have_no_name():
    one = recording()
    one.transcript.segments = Segments([segment(65, 70, "Just talking.")])
    lines = exports.plain_text(one).split("\r\n")

    assert not lines[2].startswith("Speakers:")
    assert lines[2].startswith("Automatic transcription")
    assert lines[4] == "[00:01:05] Just talking."


def test_a_correction_is_marked_on_the_line_and_in_the_legend():
    one = recording()
    one.transcript.segments = Segments(
        [segment(0, 4, "Hello.", "Speaker 1", "SPEAKER_00", corrected=True)]
    )
    text = exports.plain_text(one)

    assert "Lines marked (corrected) were corrected by staff." in text
    assert "[00:00:00] Speaker 1 (corrected): Hello." in text


# Captions ---------------------------------------------------------------------


def test_a_cue_carries_the_speaker_and_the_times():
    one = recording()
    one.transcript.segments = Segments(
        [segment(3661.5, 3663.25, "Right.", "Speaker 2")]
    )
    assert exports.srt(one).split("\r\n")[:3] == [
        "1",
        "01:01:01,500 --> 01:01:03,250",
        "Speaker 2: Right.",
    ]


def test_a_clip_shifts_its_cues_back_to_zero():
    one = recording()
    one.transcript.segments = Segments([segment(120.0, 122.0, "Here.")])
    assert "00:00:00,000 --> 00:00:02,000" in exports.srt(one, offset=120.0)


# Speakers ---------------------------------------------------------------------


def test_appearances_are_in_the_order_they_were_first_heard():
    rows = [
        segment(10, 12, "Second.", "Speaker 2", "SPEAKER_01"),
        segment(0, 5, "First.", "Speaker 1", "SPEAKER_00"),
        segment(20, 26, "Again.", "Speaker 1", "SPEAKER_00"),
    ]
    who = exports.appearances(sorted(rows, key=lambda one: one.start))

    assert [one.name for one in who] == ["Speaker 1", "Speaker 2"]
    assert who[0].count == 2
    assert who[0].speaking_time == "0:11"
    assert exports.clock(who[1].first) == "00:00:10"


# File names -------------------------------------------------------------------


def test_a_colon_in_a_title_becomes_a_hyphen():
    assert exports.safe_name("Call: 3 August") == "Call- 3 August"


def test_a_windows_reserved_name_gets_a_suffix():
    assert exports.safe_name("CON") == "CON (file)"
    assert exports.safe_name("con.mp3") == "con.mp3 (file)"


def test_a_long_title_is_cut_to_eighty_characters():
    assert len(exports.safe_name("x" * 200)) == 80


def test_an_empty_title_still_makes_a_file_name():
    assert exports.safe_name("") == "recording"
    assert exports.safe_name("   ") == "recording"


def test_everything_else_really_does_become_a_hyphen():
    # Even when that is all a title was: the rule is worth more than a
    # prettier name for a title nobody meant.
    assert exports.safe_name("///") == "---"


def test_two_of_the_same_name_in_a_zip_are_told_apart():
    taken = set()
    first = exports.without_clashes(taken, "Call - transcript.txt")
    second = exports.without_clashes(taken, "Call - transcript.txt")
    third = exports.without_clashes(taken, "Call - transcript.txt")

    assert first == "Call - transcript.txt"
    assert second == "Call - transcript (2).txt"
    assert third == "Call - transcript (3).txt"


def test_the_export_name_follows_the_title_not_the_file():
    assert (
        exports.export_name(recording(), "transcript.docx")
        == "Call with the client - transcript.docx"
    )


def test_a_recording_without_a_title_falls_back_to_the_file_name():
    one = recording(title="")
    assert exports.title_of(one) == "jail-call"


# Lengths and clocks -----------------------------------------------------------


def test_a_length_reads_in_hours_and_minutes():
    assert exports.length_of(Fake(duration_seconds=5400)) == "1 h 30 min"
    assert exports.length_of(Fake(duration_seconds=3600)) == "1 h"
    assert exports.length_of(Fake(duration_seconds=90)) == "1 min"
    assert exports.length_of(Fake(duration_seconds=12)) == "12 sec"


def test_the_clock_always_shows_hours():
    assert exports.clock(0) == "00:00:00"
    assert exports.clock(59.9) == "00:00:59"
    assert exports.clock(3600) == "01:00:00"


# What both sides of a call heard ------------------------------------------------


def test_the_second_copy_is_not_printed_and_the_export_says_why():
    one = recording(is_two_channel_call=True)
    one.transcript.shared_segments = 2
    one.transcript.segments = Segments(
        [
            segment(0, 4, "This call may be recorded.", "Side 1 and Side 2"),
            segment(
                0, 4, "This call may be recorded.", "Side 2", same_as_other_side=True
            ),
            segment(6, 9, "To accept, press one.", "Side 1 and Side 2"),
            segment(6, 9, "To accept, press one.", "Side 2", same_as_other_side=True),
            segment(20, 24, "Hey, it is me.", "Side 1"),
        ]
    )
    text = exports.plain_text(one)

    # Once each, and never as Side 2's own words.
    assert text.count("This call may be recorded.") == 1
    assert text.count("To accept, press one.") == 1
    # Named for both, and never as Side 2's own words. Checked on the whole
    # line, because "Side 1 and Side 2:" holds "Side 2:" inside it.
    lines = text.splitlines()
    assert "[00:00:00] Side 1 and Side 2: This call may be recorded." in lines
    assert "[00:00:00] Side 2: This call may be recorded." not in lines
    assert "Side 1: Hey, it is me." in text

    # And it says what it did, because that is not the app's to decide quietly.
    assert "2 passages at the same moment on both sides" in text
    assert "printed once and named Side 1 and Side 2" in text
    assert "Both copies are kept." in text


def test_a_transcript_with_nothing_shared_says_nothing_about_it():
    one = recording()
    one.transcript.segments = Segments([segment(0, 4, "Hello.", "Speaker 1")])
    assert "on both sides" not in exports.plain_text(one)


def test_one_shared_passage_reads_in_the_singular():
    one = recording(is_two_channel_call=True)
    one.transcript.shared_segments = 1
    one.transcript.segments = Segments(
        [segment(0, 4, "This call may be recorded.", "Side 1 and Side 2")]
    )
    assert "1 passage at the same moment on both sides, which a phone" in (
        exports.plain_text(one)
    )
