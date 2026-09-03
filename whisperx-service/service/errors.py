"""The nine reason classes, and the refusals that carry them.

A failed job carries one of these in `failure.reason_class`, and a refused
submission carries one in the body of its 400 or 413. They are fixed words and
never free text, because a Consumer records them: the app writes the service's
class into its own audit log as the Job's reason class.

The message beside a class is short and safe. It never holds a file name, a
Consumer's own text, or anything from a transcript.
"""

from __future__ import annotations

# No decodable audio: found by an ffprobe at submit, or a decode that fails
# part way through a job.
BAD_INPUT = "bad_input"

# The request body was over the size limit.
TOO_LARGE = "too_large"

# The audio was longer than the limit, measured at submit.
TOO_LONG = "too_long"

# A model that is not cached and cannot be fetched, or one the licence gate
# refused. A missing alignment model is not this: it is the no_alignment_model
# flag on an otherwise finished job.
MODEL_UNAVAILABLE = "model_unavailable"

# A CUDA fault or an out-of-memory. The only class that is retried, once, after
# the model process has been reloaded.
GPU_ERROR = "gpu_error"

# Past the job time limit.
TIMEOUT = "timeout"

# Deleted by its Consumer, or by an admin token, while queued or running.
CANCELLED = "cancelled"

# Interrupted by a service restart twice. The first interruption puts a job
# back at the head of the line.
SERVICE_RESTARTED = "service_restarted"

# Anything else. The details go to the journal, never to the Consumer.
INTERNAL = "internal"

REASON_CLASSES = (
    BAD_INPUT,
    TOO_LARGE,
    TOO_LONG,
    MODEL_UNAVAILABLE,
    GPU_ERROR,
    TIMEOUT,
    CANCELLED,
    SERVICE_RESTARTED,
    INTERNAL,
)

# The classes a job may be retried for, and how many attempts it gets in all.
RETRIED = (GPU_ERROR,)
MAX_ATTEMPTS = 2


class ServiceError(Exception):
    """A refusal with an HTTP code and, where one applies, a reason class.

    Everything the API refuses raises this, so that one handler turns it into
    the body the contract describes and nothing invents its own shape.
    """

    def __init__(
        self,
        status_code: int,
        message: str,
        reason_class: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.reason_class = reason_class

    def body(self) -> dict[str, str]:
        body = {"error": self.message}
        if self.reason_class:
            body["reason_class"] = self.reason_class
        return body


def invalid(message: str) -> ServiceError:
    """A request the service will not accept, with no reason class of its own.

    Unknown fields, a model outside the allow-list, a speaker hint without
    diarization, a min above a max, a context line or a vocabulary over the
    caps: all of these are the Consumer's own mistake, found before any work
    starts.
    """
    return ServiceError(400, message)


def bad_input(message: str = "no decodable audio stream") -> ServiceError:
    return ServiceError(400, message, BAD_INPUT)


def too_long(message: str) -> ServiceError:
    return ServiceError(400, message, TOO_LONG)


def too_large(message: str) -> ServiceError:
    return ServiceError(413, message, TOO_LARGE)


def model_unavailable(message: str) -> ServiceError:
    return ServiceError(400, message, MODEL_UNAVAILABLE)


def unauthorised() -> ServiceError:
    return ServiceError(401, "a bearer token is needed")


def not_found() -> ServiceError:
    """Also what a Consumer gets for another Consumer's job.

    A job belongs to the token that made it. Anything else is not told that
    the job exists at all, which is why this is 404 and not 403.
    """
    return ServiceError(404, "no such job")


def not_ready() -> ServiceError:
    return ServiceError(409, "the result is not ready")


def gone() -> ServiceError:
    return ServiceError(410, "the result has been deleted")
