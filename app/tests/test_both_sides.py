"""What both Sides of a call heard, found without a database.

A phone system plays its recorded announcement to both parties before the call
connects, so both channels carry it and both Sides transcribe it. The first
minutes of a jail call then read twice over, which is true to the file and
confusing to read.

What is checked here is the rule that finds those passages, because getting it
wrong in either direction matters: missing them leaves the transcript doubled,
and finding them where they are not would take two people saying the same
thing at once and print it as one.
"""

from core.queue import _plainly, _the_stretch_on_both_sides


class Segment:
    """Just enough of a Segment for the rule."""

    def __init__(self, side, start, text):
        self.side_id = side
        self.start = start
        self.end = start + 3.0
        self.text = text
        self.speaker = f"Side {side}"
        self.same_as_other_side = False


class Recording:
    def __init__(self, two_channel=True):
        self.is_two_channel_call = two_channel


PREAMBLE = [
    "This call is from a correctional facility and may be recorded.",
    "You have a collect call from an inmate at the county jail.",
    "To accept this call, press one now.",
    "Thank you for using our service.",
]


def a_call(**changes):
    """Both Sides carrying the announcement, then one party each."""
    segments = []
    at = 0.0
    for line in PREAMBLE:
        segments.append(Segment(1, at, line))
        segments.append(Segment(2, at + changes.get("apart", 0.2), line))
        at += 6.0
    segments.append(Segment(1, at, "Hey, it is me. Can you hear me all right?"))
    segments.append(Segment(2, at + 4.0, "Yeah, I can hear you fine."))
    return segments


def test_the_announcement_is_named_for_both_sides():
    segments = a_call()
    found = _the_stretch_on_both_sides(segments, Recording())

    assert found == len(PREAMBLE)
    kept = [one for one in segments if one.side_id == 1][: len(PREAMBLE)]
    copies = [one for one in segments if one.side_id == 2][: len(PREAMBLE)]
    assert all(one.speaker == "Side 1 and Side 2" for one in kept)
    assert all(one.same_as_other_side for one in copies)


def test_what_each_party_says_is_left_alone():
    segments = a_call()
    _the_stretch_on_both_sides(segments, Recording())

    talk = [one for one in segments if one.text.startswith(("Hey,", "Yeah,"))]
    assert len(talk) == 2
    assert not any(one.same_as_other_side for one in talk)
    assert [one.speaker for one in talk] == ["Side 1", "Side 2"]


def test_nothing_is_ever_removed():
    segments = a_call()
    before = len(segments)
    _the_stretch_on_both_sides(segments, Recording())
    assert len(segments) == before


# The guards against coincidence -------------------------------------------------


def test_two_people_saying_the_same_short_word_at_once_is_not_a_stretch():
    segments = [
        Segment(1, 0.0, "Yeah."),
        Segment(2, 0.1, "Yeah."),
        Segment(1, 6.0, "Okay."),
        Segment(2, 6.1, "Okay."),
        Segment(1, 12.0, "Right."),
        Segment(2, 12.1, "Right."),
    ]
    assert _the_stretch_on_both_sides(segments, Recording()) == 0
    assert not any(one.same_as_other_side for one in segments)


def test_one_matching_passage_is_not_a_stretch():
    segments = [
        Segment(1, 0.0, "This call is from a correctional facility."),
        Segment(2, 0.2, "This call is from a correctional facility."),
        Segment(1, 6.0, "Hey, it is me. Can you hear me all right?"),
        Segment(2, 10.0, "Yeah, I can hear you fine."),
    ]
    assert _the_stretch_on_both_sides(segments, Recording()) == 0


def test_the_same_words_at_different_moments_are_two_different_things():
    segments = a_call(apart=9.0)
    assert _the_stretch_on_both_sides(segments, Recording()) == 0


def test_a_recording_that_is_not_a_two_channel_call_is_left_alone():
    segments = a_call()
    assert _the_stretch_on_both_sides(segments, Recording(two_channel=False)) == 0
    assert not any(one.same_as_other_side for one in segments)


def test_one_side_is_left_alone():
    segments = [Segment(1, at * 6.0, line) for at, line in enumerate(PREAMBLE)]
    assert _the_stretch_on_both_sides(segments, Recording()) == 0


# Reading the words alone --------------------------------------------------------


def test_punctuation_and_capitals_do_not_part_a_pair():
    # The two channels are the same sound, but the engine hears each on its
    # own and may punctuate them differently.
    segments = [
        Segment(1, 0.0, "To accept this call, press one now."),
        Segment(2, 0.2, "to accept this call press one now"),
        Segment(1, 6.0, "Thank you for using our service."),
        Segment(2, 6.2, "Thank you for using our service!"),
        Segment(1, 12.0, "This call may be monitored and recorded."),
        Segment(2, 12.2, "This call may be monitored, and recorded"),
    ]
    assert _the_stretch_on_both_sides(segments, Recording()) == 3


def test_different_words_are_different_words():
    segments = [
        Segment(1, 0.0, "To accept this call, press one now."),
        Segment(2, 0.2, "To refuse this call, press two now."),
        Segment(1, 6.0, "Thank you for using our service."),
        Segment(2, 6.2, "Thank you for calling our service."),
        Segment(1, 12.0, "This call may be monitored and recorded."),
        Segment(2, 12.2, "This call will be monitored and recorded."),
    ]
    assert _the_stretch_on_both_sides(segments, Recording()) == 0


def test_the_words_alone():
    assert _plainly("To accept, press ONE now!") == "to accept press one now"
    assert _plainly("  spaced   out  ") == "spaced out"
