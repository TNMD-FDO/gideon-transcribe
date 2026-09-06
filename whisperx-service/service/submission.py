"""What a Consumer may ask for, and everything the service refuses.

A submission is refused before any work starts, with a plain message and,
where the contract names one, a reason class. Nothing is silently ignored: a
request that does not mean what its sender thought is a bug in the sender, and
dropping part of it quietly hides that bug until somebody wonders why a result
looks wrong.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from service import errors
from service.detection import TASKS, TRANSCRIBE

# The caps the contract fixes.
MAX_VOCABULARY_TERMS = 200
MAX_CONTEXT_CHARACTERS = 500

# Whisper's own language list, which is the whole of what may be named. A
# language Whisper does not cover cannot be offered by a Consumer either, which
# is why this list is here rather than in an application: it is a fact about
# the model.
WHISPER_LANGUAGES = frozenset(
    {
        "af",
        "am",
        "ar",
        "as",
        "az",
        "ba",
        "be",
        "bg",
        "bn",
        "bo",
        "br",
        "bs",
        "ca",
        "cs",
        "cy",
        "da",
        "de",
        "el",
        "en",
        "es",
        "et",
        "eu",
        "fa",
        "fi",
        "fo",
        "fr",
        "gl",
        "gu",
        "ha",
        "haw",
        "he",
        "hi",
        "hr",
        "ht",
        "hu",
        "hy",
        "id",
        "is",
        "it",
        "ja",
        "jw",
        "ka",
        "kk",
        "km",
        "kn",
        "ko",
        "la",
        "lb",
        "ln",
        "lo",
        "lt",
        "lv",
        "mg",
        "mi",
        "mk",
        "ml",
        "mn",
        "mr",
        "ms",
        "mt",
        "my",
        "ne",
        "nl",
        "nn",
        "no",
        "oc",
        "pa",
        "pl",
        "ps",
        "pt",
        "ro",
        "ru",
        "sa",
        "sd",
        "si",
        "sk",
        "sl",
        "sn",
        "so",
        "sq",
        "sr",
        "su",
        "sv",
        "sw",
        "ta",
        "te",
        "tg",
        "th",
        "tk",
        "tl",
        "tr",
        "tt",
        "uk",
        "ur",
        "uz",
        "vi",
        "yi",
        "yo",
        "yue",
        "zh",
    }
)


FIELDS = {
    "task",
    "translate_if_mixed",
    "language",
    "model",
    "diarize",
    "speakers",
    "vocabulary",
    "context",
    "return_speaker_embeddings",
    "client_reference",
    "priority",
}


@dataclass(frozen=True)
class Speakers:
    """The speaker-count hint, in one of its three shapes."""

    exactly: int | None = None
    between: tuple[int, int] | None = None

    def as_json(self) -> dict[str, Any] | None:
        if self.exactly is not None:
            return {"exactly": self.exactly}
        if self.between is not None:
            return {"between": list(self.between)}
        return None


@dataclass(frozen=True)
class Submission:
    """A request that has been read and found sound."""

    task: str = TRANSCRIBE
    translate_if_mixed: bool = False
    language: str | None = None
    model: str = "large-v3"
    diarize: bool = False
    speakers: Speakers = field(default_factory=Speakers)
    vocabulary: tuple[str, ...] = ()
    context: str = ""
    return_speaker_embeddings: bool = False
    client_reference: str | None = None
    # 0 to 100; higher runs first, equal priorities in arrival order.
    priority: int = 0

    def as_json(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "translate_if_mixed": self.translate_if_mixed,
            "language": self.language,
            "model": self.model,
            "diarize": self.diarize,
            "speakers": self.speakers.as_json(),
            "vocabulary": list(self.vocabulary),
            "context": self.context,
            "return_speaker_embeddings": self.return_speaker_embeddings,
            "client_reference": self.client_reference,
            "priority": self.priority,
        }


def _boolean(body: dict[str, Any], name: str, default: bool) -> bool:
    value = body.get(name, default)
    if not isinstance(value, bool):
        raise errors.invalid(f"{name} must be true or false")
    return value


def _speakers(body: dict[str, Any], diarize: bool) -> Speakers:
    raw = body.get("speakers")
    if raw in (None, {}, ""):
        return Speakers()

    # A hint without diarization is refused rather than ignored. A Consumer
    # that sends one has a bug, and dropping it quietly would hide that bug
    # until somebody wondered why the result had no speakers in it.
    if not diarize:
        raise errors.invalid(
            "speakers was given without diarize. A speaker-count hint only "
            "means something when speakers are being separated"
        )

    if not isinstance(raw, dict) or set(raw) not in ({"exactly"}, {"between"}):
        raise errors.invalid(
            'speakers must be {"exactly": N} or {"between": [N, M]}, or left out'
        )

    if "exactly" in raw:
        count = raw["exactly"]
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            raise errors.invalid(
                "speakers.exactly must be a whole number of one or more"
            )
        return Speakers(exactly=count)

    pair = raw["between"]
    if (
        not isinstance(pair, list)
        or len(pair) != 2
        or any(not isinstance(one, int) or isinstance(one, bool) for one in pair)
    ):
        raise errors.invalid("speakers.between must be two whole numbers")
    least, most = pair
    if least < 1:
        raise errors.invalid("speakers.between must start at one or more")
    if least > most:
        raise errors.invalid(
            f"speakers.between has {least} as its least and {most} as its most"
        )
    return Speakers(between=(least, most))


def _vocabulary(body: dict[str, Any]) -> tuple[str, ...]:
    raw = body.get("vocabulary") or []
    if not isinstance(raw, list) or any(not isinstance(term, str) for term in raw):
        raise errors.invalid("vocabulary must be a list of words")
    if len(raw) > MAX_VOCABULARY_TERMS:
        raise errors.invalid(
            f"vocabulary holds {len(raw)} terms, and the most is {MAX_VOCABULARY_TERMS}"
        )
    return tuple(raw)


def _context(body: dict[str, Any]) -> str:
    raw = body.get("context") or ""
    if not isinstance(raw, str):
        raise errors.invalid("context must be one line of text")
    if len(raw) > MAX_CONTEXT_CHARACTERS:
        raise errors.invalid(
            f"context is {len(raw)} characters, and the most is "
            f"{MAX_CONTEXT_CHARACTERS}"
        )
    if "\n" in raw or "\r" in raw:
        raise errors.invalid("context must be one line, with no line breaks in it")
    return raw


def read(body: Any, models: tuple[str, ...]) -> Submission:
    """Read a request body, or refuse it.

    `models` is the allow-list from models.yaml. A model outside it is refused
    here rather than discovered when a job reaches the card.
    """
    if not isinstance(body, dict):
        raise errors.invalid("the request part must be a JSON object")

    unknown = sorted(set(body) - FIELDS)
    if unknown:
        raise errors.invalid(
            f"unknown field {unknown[0]!r}. The fields are: {', '.join(sorted(FIELDS))}"
        )

    task = body.get("task", TRANSCRIBE)
    if task not in TASKS:
        raise errors.invalid(f"task must be one of: {', '.join(TASKS)}")

    language = body.get("language") or None
    if language is not None and (
        not isinstance(language, str) or language not in WHISPER_LANGUAGES
    ):
        raise errors.invalid(
            f"{language!r} is not a language this model knows. Leave language "
            "out to have it detected"
        )

    model = body.get("model") or models[0]
    if model not in models:
        raise errors.invalid(f"model must be one of: {', '.join(models)}")

    diarize = _boolean(body, "diarize", False)
    embeddings = _boolean(body, "return_speaker_embeddings", False)
    if embeddings and not diarize:
        raise errors.invalid(
            "return_speaker_embeddings was asked for without diarize. There are "
            "no speakers to describe unless they are being separated"
        )

    reference = body.get("client_reference")
    if reference is not None and not isinstance(reference, str):
        raise errors.invalid("client_reference must be text")

    priority = body.get("priority", 0)
    if isinstance(priority, bool) or not isinstance(priority, int):
        raise errors.invalid("priority must be a whole number from 0 to 100")
    if not 0 <= priority <= 100:
        raise errors.invalid("priority must be a whole number from 0 to 100")

    return Submission(
        task=task,
        translate_if_mixed=_boolean(body, "translate_if_mixed", False),
        language=language,
        model=model,
        diarize=diarize,
        speakers=_speakers(body, diarize),
        vocabulary=_vocabulary(body),
        context=_context(body),
        return_speaker_embeddings=embeddings,
        client_reference=reference,
        priority=priority,
    )
