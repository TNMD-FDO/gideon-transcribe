"""Qwen3-ASR's path (ADR 0025, service 0.8.0), the parts that need no card:
the pieces, the spanned words, the lines, the speaker split, the languages.
"""

import wave
from io import BytesIO

import numpy as np
from service import recognising
from service.recognising import Word

RATE = 16000


def quiet_at(seconds: float, gaps: list[float], loud: float = 0.5) -> np.ndarray:
    """Noise of a given length with 300 ms of silence at each gap."""
    rng = np.random.default_rng(1)
    audio = (rng.standard_normal(int(seconds * RATE)) * loud).astype("float32")
    for gap in gaps:
        a = int(gap * RATE)
        audio[a : a + int(0.3 * RATE)] = 0.0
    return audio


# The pieces -------------------------------------------------------------------


def test_a_short_file_is_one_piece():
    audio = quiet_at(30.0, [])
    assert recognising.cut_points(audio) == [(0, len(audio))]


def test_pieces_lie_end_to_end_and_cut_at_the_quietest_point():
    # A pause at 43.1 s sits inside the five-second search around the
    # 45-second target, so the cut lands in it; the second target at
    # about 88 s finds its pause at 90.5 s.
    audio = quiet_at(100.0, [43.1, 90.5])
    pieces = recognising.cut_points(audio)
    assert pieces[0][0] == 0 and pieces[-1][1] == len(audio)
    for (_, end), (start, _) in zip(pieces, pieces[1:], strict=False):
        assert end == start
    first_cut = pieces[0][1] / RATE
    assert 43.1 <= first_cut <= 43.4
    second_cut = pieces[1][1] / RATE
    assert 90.5 <= second_cut <= 90.8
    assert len(pieces) == 3


def test_a_tail_under_a_second_stays_on_the_last_piece():
    audio = quiet_at(45.5, [])
    assert len(recognising.cut_points(audio)) == 1


def test_the_piece_is_a_prepared_wav():
    data = recognising.wav_bytes(np.zeros(RATE, dtype="float32"))
    with wave.open(BytesIO(data), "rb") as handle:
        assert handle.getnchannels() == 1
        assert handle.getsampwidth() == 2
        assert handle.getframerate() == RATE
        assert handle.getnframes() == RATE


# The words --------------------------------------------------------------------


def test_language_names_become_codes_and_back():
    assert recognising.code_of("English") == "en"
    assert recognising.code_of("Spanish,English") == "es"
    assert recognising.code_of("") == ""
    assert recognising.code_of("Klingon") == "klingon"
    assert recognising.name_of("es") == "Spanish"
    assert recognising.name_of("") is None
    assert recognising.name_of("xx") is None


def test_words_move_to_the_whole_files_clock():
    words = recognising.words_of(
        [
            {"text": "Hello", "start": 0.5, "end": 0.9},
            {"text": " ", "start": 1, "end": 1},
        ],
        offset=45.25,
        piece=1,
    )
    assert words == [Word("Hello", 45.75, 46.15, 1)]


def test_a_word_with_no_length_takes_a_span_from_its_neighbours():
    words = [
        Word("one", 1.0, 1.4, 0),
        Word("two", 1.5, 1.5, 0),
        Word("three", 1.6, 2.0, 0),
        Word("four", 2.0, 2.0, 0),
        Word("five", 2.0, 2.4, 0),
    ]
    out, count = recognising.span_unlengthed(words)
    assert count == 2
    # Forward to the next word's start when there is room.
    assert (out[1].start, out[1].end) == (1.5, 1.6)
    # No room forward (the next word starts at the same time) and none back
    # (the previous word ends at the same time): the least span there is.
    assert (out[3].start, out[3].end) == (2.0, 2.05)
    assert all(word.end > word.start for word in out)


# The lines --------------------------------------------------------------------


def test_lines_cut_at_pauses_sentence_ends_and_language_changes():
    words = [
        Word("Good", 0.0, 0.2, 0),
        Word("morning.", 0.3, 0.6, 0),
        Word("How", 0.7, 0.8, 0),
        Word("are", 0.9, 1.0, 0),
        Word("you", 1.1, 1.3, 0),
        Word("fine", 2.5, 2.8, 0),
        Word("gracias", 46.0, 46.4, 1),
    ]
    segments = recognising.lines_of(words, {0: "en", 1: "es"})
    assert [one["text"] for one in segments] == [
        "Good morning.",
        "How are you",
        "fine",
        "gracias",
    ]
    assert [one["language"] for one in segments] == ["en", "en", "en", "es"]
    assert segments[1]["start"] == 0.7 and segments[1]["end"] == 1.3
    assert segments[1]["words"][0] == {"word": "How", "start": 0.7, "end": 0.8}


def test_a_long_line_is_cut_at_the_caps():
    words = [Word(f"w{i}", i * 0.5, i * 0.5 + 0.4, 0) for i in range(50)]
    segments = recognising.lines_of(words, {0: "en"})
    assert all(len(one["words"]) <= recognising.LONGEST_LINE_WORDS for one in segments)
    assert all(
        one["end"] - one["start"] <= recognising.LONGEST_LINE_SECONDS + 0.5
        for one in segments
    )
    assert sum(len(one["words"]) for one in segments) == 50


def test_a_line_is_split_where_the_speaker_changes():
    segments = [
        {
            "start": 0.0,
            "end": 2.0,
            "text": "yes no maybe so",
            "language": "en",
            "speaker": "speaker_0",
            "words": [
                {"word": "yes", "start": 0.0, "end": 0.4, "speaker": "speaker_0"},
                {"word": "no", "start": 0.5, "end": 0.9},
                {"word": "maybe", "start": 1.0, "end": 1.4, "speaker": "speaker_1"},
                {"word": "so", "start": 1.5, "end": 2.0, "speaker": "speaker_1"},
            ],
        }
    ]
    out = recognising.split_at_speakers(segments)
    assert [(one["text"], one["speaker"]) for one in out] == [
        ("yes no", "speaker_0"),
        ("maybe so", "speaker_1"),
    ]
    assert out[0]["end"] == 0.9 and out[1]["start"] == 1.0
    assert out[1]["language"] == "en"


def test_a_line_of_one_voice_is_left_alone():
    segment = {
        "start": 0.0,
        "end": 1.0,
        "text": "yes",
        "words": [{"word": "yes", "start": 0.0, "end": 1.0, "speaker": "speaker_0"}],
    }
    assert recognising.split_at_speakers([segment]) == [segment]


# The languages ----------------------------------------------------------------


def test_the_most_spoken_language_wins_and_mixed_needs_enough_of_the_other():
    pieces = [
        {"offset_seconds": 0.0, "seconds": 45.0, "language": "en"},
        {"offset_seconds": 45.0, "seconds": 45.0, "language": "en"},
        {"offset_seconds": 90.0, "seconds": 30.0, "language": "es"},
    ]
    part = recognising.language_part(pieces, None)
    assert part["detected"] == "en"
    assert part["probability"] == 0.75
    assert part["combined"] == {"en": 0.75, "es": 0.25}
    assert part["mixed"] is True
    assert part["windows"] == []
    assert len(part["pieces"]) == 3

    short = [
        {"offset_seconds": 0.0, "seconds": 45.0, "language": "en"},
        {"offset_seconds": 45.0, "seconds": 45.0, "language": "en"},
        {"offset_seconds": 90.0, "seconds": 4.0, "language": "es"},
    ]
    assert recognising.language_part(short, None)["mixed"] is False


def test_a_requested_language_stands_as_detected():
    part = recognising.language_part(
        [{"offset_seconds": 0.0, "seconds": 10.0, "language": "en"}], "es"
    )
    assert part["requested"] == "es" and part["detected"] == "es"


def test_an_empty_file_has_no_language():
    part = recognising.language_part([], None)
    assert part["detected"] == "" and part["probability"] is None
    assert part["mixed"] is False
