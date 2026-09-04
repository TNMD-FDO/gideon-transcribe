"""What a person is told about how long they will wait.

The arithmetic is the specification's, and the words matter as much as the
figures: "about" is a measurement of this office's own card and "roughly" is
a reference point from research, and somebody planning an afternoon around
the difference deserves to know which they were given.
"""

from datetime import datetime

from core import waiting

# What the service publishes once it has measured itself: audio minutes
# finished per wall-clock minute.
MEASURED = {"large-v3-turbo": {"with_diarization": 30.0, "without_diarization": 60.0}}
NOT_YET = {"large-v3-turbo": {"with_diarization": None, "without_diarization": None}}


def test_a_measured_speed_is_used_when_the_service_has_one():
    speed, measured = waiting.speed_from(MEASURED, "large-v3-turbo", True)
    assert speed == 30.0
    assert measured is True


def test_the_reference_figures_stand_in_until_it_has_measured():
    speed, measured = waiting.speed_from(NOT_YET, "large-v3-turbo", False)
    assert speed == waiting.REFERENCE_SPEED
    assert measured is False


def test_diarization_makes_the_reference_figure_slower():
    assert waiting.reference_speed(True) < waiting.reference_speed(False)


def test_the_wait_is_the_audio_ahead_over_the_speed_plus_a_moment_per_run():
    # Sixty audio minutes ahead at thirty a minute is two minutes, and two
    # runs ahead add fifteen seconds each.
    minutes, measured = waiting.minutes_for(60, 2, MEASURED, "large-v3-turbo", True)
    assert measured is True
    assert abs(minutes - (2 + 0.5)) < 0.001


def test_it_is_rounded_up_because_running_over_is_worse_than_ending_early():
    assert waiting.in_words(2.1, True).startswith("about 3 minutes")
    assert waiting.in_words(3.0, True).startswith("about 3 minutes")


def test_one_minute_is_not_plural():
    assert waiting.in_words(0.5, True) == "about 1 minute"


def test_a_measured_figure_says_about_and_a_reference_one_says_roughly():
    assert waiting.in_words(5, True).startswith("about")
    assert waiting.in_words(5, False).startswith("roughly")


def test_over_ten_minutes_it_carries_a_time_of_day():
    said = waiting.in_words(35, True, now=datetime(2026, 9, 4, 15, 5))
    assert said == "about 35 minutes, around 3:40 pm"


def test_under_ten_minutes_it_does_not():
    assert "around" not in waiting.in_words(9, True, now=datetime(2026, 9, 4, 15, 5))


def test_the_clock_reads_as_an_office_writes_it():
    assert waiting.on_the_clock(datetime(2026, 9, 4, 15, 40)) == "3:40 pm"
    assert waiting.on_the_clock(datetime(2026, 9, 4, 9, 5)) == "9:05 am"
    assert waiting.on_the_clock(datetime(2026, 9, 4, 0, 30)) == "12:30 am"
    assert waiting.on_the_clock(datetime(2026, 9, 4, 12, 0)) == "12:00 pm"


def test_nothing_ahead_means_it_is_starting():
    assert waiting.in_words(0, True) == "starting now"


class Run:
    def __init__(self, minutes_ahead, position=1, state="queued"):
        self.audio_minutes_ahead = minutes_ahead
        self.position = position
        self.state = state


def test_the_overall_line_covers_the_last_recording_and_its_own_audio():
    # One recording, nothing ahead of it, sixty minutes of its own audio at
    # thirty a minute: two minutes of work.
    said = waiting.everything_done_by(
        [{"run": Run(0), "model": "large-v3-turbo", "diarize": True, "minutes": 60}],
        MEASURED,
        now=datetime(2026, 9, 4, 15, 0),
    )
    assert said == "Everything done by about 3:03 pm"


def test_the_overall_line_is_nothing_when_nothing_is_running():
    assert waiting.everything_done_by([], MEASURED) is None
