"""Language detection, the mixed rule, and which task actually runs.

The service detects the language once, before transcription, and never
switches language part way through a file. It samples three 30-second windows,
each of which reports one language and a probability, and decides from those
three whether the file holds one language or more than one.

None of this needs a GPU or a model, so it is tested on its own.
"""

from __future__ import annotations

from dataclasses import dataclass

# Three windows: the start, one third in, and two thirds in. A file too short
# for three gets as many non-overlapping windows as fit, and always at least
# one.
WINDOW_SECONDS = 30.0
WINDOW_COUNT = 3

# A file is mixed when at least two windows report different languages, each
# with a probability of this much or more.
MIXED_PROBABILITY = 0.5

ENGLISH = "en"

# The three tasks a Consumer may ask for.
TRANSCRIBE = "transcribe"
TRANSLATE = "translate"
TRANSLATE_IF_NEEDED = "translate_if_needed"
TASKS = (TRANSCRIBE, TRANSLATE, TRANSLATE_IF_NEEDED)

# What the service actually ran, and why. Both are echoed in every result.
REASON_REQUESTED = "requested"
REASON_ENGLISH_DETECTED = "english_detected"
REASON_MIXED_DETECTED = "mixed_detected"


@dataclass(frozen=True)
class Window:
    """One 30-second sample, and the language the model heard in it."""

    offset_seconds: float
    language: str
    probability: float


@dataclass(frozen=True)
class Detection:
    """What the windows said, together."""

    windows: tuple[Window, ...]
    combined: dict[str, float]
    mixed: bool
    detected: str
    probability: float


@dataclass(frozen=True)
class Decision:
    """What to run, why, and which language to tell Whisper."""

    task_run: str
    task_reason: str
    language: str | None


def window_offsets(duration_seconds: float) -> list[float]:
    """Where the windows start.

    Three windows at the start, a third in, and two thirds in, which is what a
    file of 90 seconds or more can hold without them overlapping. A shorter
    file gets as many non-overlapping windows as fit, and never fewer than one,
    because a language has to be guessed from something.
    """
    if duration_seconds >= WINDOW_SECONDS * WINDOW_COUNT:
        return [
            0.0,
            duration_seconds / 3.0,
            duration_seconds * 2.0 / 3.0,
        ]

    fit = int(duration_seconds // WINDOW_SECONDS)
    return [index * WINDOW_SECONDS for index in range(max(1, fit))]


def combine(windows: list[Window]) -> Detection:
    """Read the windows together: the totals, the winner, and mixed or not.

    A language's combined figure is the mean of the probabilities of the
    windows that heard it, counting a window that heard something else as zero.
    Averaging rather than adding keeps the figure between 0 and 1 whether a
    file got one window or three, which is what lets a Consumer compare it
    against a threshold. When every window agrees, the figure is simply that
    probability.
    """
    if not windows:
        raise ValueError("detection needs at least one window")

    totals: dict[str, float] = {}
    for window in windows:
        totals[window.language] = totals.get(window.language, 0.0) + window.probability
    combined = {
        language: total / len(windows) for language, total in sorted(totals.items())
    }

    confident = [
        window for window in windows if window.probability >= MIXED_PROBABILITY
    ]
    mixed = len({window.language for window in confident}) >= 2

    detected = max(combined, key=lambda language: (combined[language], language))
    return Detection(
        windows=tuple(windows),
        combined=combined,
        mixed=mixed,
        detected=detected,
        probability=combined[detected],
    )


def strongest_non_english(detection: Detection) -> str:
    """The non-English language with the highest combined figure.

    This is what Whisper is told under translate, because English speech passes
    through the translate task untranslated anyway. A file in which nothing but
    English was heard falls back to English.
    """
    others = {
        language: total
        for language, total in detection.combined.items()
        if language != ENGLISH
    }
    if not others:
        return ENGLISH
    return max(others, key=lambda language: (others[language], language))


def decide(
    task: str,
    language: str | None,
    translate_if_mixed: bool,
    detection: Detection | None,
) -> Decision:
    """What the service runs, given the request and what detection found.

    `detection` is None exactly when the Consumer named a language, because a
    named language switches detection off, and with it the mixed rule: the
    Consumer then gets precisely what it asked for.
    """
    if task not in TASKS:
        raise ValueError(f"unknown task {task!r}")

    if language:
        if task == TRANSCRIBE:
            return Decision(TRANSCRIBE, REASON_REQUESTED, language)
        if task == TRANSLATE:
            return Decision(TRANSLATE, REASON_REQUESTED, language)
        # translate_if_needed: English is already English, anything else is
        # translated. Either way there is nothing to detect.
        if language == ENGLISH:
            return Decision(TRANSCRIBE, REASON_REQUESTED, ENGLISH)
        return Decision(TRANSLATE, REASON_REQUESTED, language)

    if detection is None:
        raise ValueError("detection is needed when no language was given")

    if task == TRANSLATE:
        return Decision(TRANSLATE, REASON_REQUESTED, strongest_non_english(detection))

    if task == TRANSCRIBE:
        if detection.mixed and translate_if_mixed:
            return Decision(
                TRANSLATE, REASON_MIXED_DETECTED, strongest_non_english(detection)
            )
        return Decision(TRANSCRIBE, REASON_REQUESTED, detection.detected)

    # translate_if_needed with nothing named. A mixed file is translated
    # whatever its winning language: the point of this task is English out, and
    # under translate the English half passes through untouched. The
    # translate_if_mixed flag is not consulted, because it belongs to the plain
    # transcribe task; here the behaviour is the task's own.
    if detection.mixed:
        return Decision(
            TRANSLATE, REASON_MIXED_DETECTED, strongest_non_english(detection)
        )
    if detection.detected == ENGLISH:
        return Decision(TRANSCRIBE, REASON_ENGLISH_DETECTED, ENGLISH)
    return Decision(TRANSLATE, REASON_REQUESTED, detection.detected)
