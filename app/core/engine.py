"""The engine the AI assistant talks to: one client, one check, one status row.

The app talks to one engine at a time through the engine's OpenAI-compatible
API, chat completions only, with the `openai` client. Which engine is a panel
matter, the Engine address and Model name settings; the bearer token is a
secret file and is never in the panel or the database.

Only `llm-worker` is on the engine's network, so everything here that reaches
the engine runs there: the once a minute check that decides whether the
viewer offers the assistant at all, the panel's Test connection, and every
call. The web container reads the status row those leave behind.

Nothing here logs a prompt or an answer. Failures are reported as one of six
reason classes, never as text.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from django.db import models
from django.utils import timezone

from core import settings_store

log = logging.getLogger("transcribe.engine")

# Where Compose mounts the token inside a container that declares the secret.
# The .env key of the same name names the file on the server, and the panel
# shows that name; this is the one the code reads.
TOKEN_PATH = Path("/run/secrets/llm_api_token")

# The six reason classes the AI assistant chapter adds to the catalogue.
UNREACHABLE = "llm_unreachable"
TIMEOUT = "llm_timeout"
REFUSED = "llm_refused"
TOO_LONG = "llm_too_long"
BAD_OUTPUT = "llm_bad_output"
ERROR = "llm_error"
# The Case Chat's own: a question over more talk than the ceiling allows.
CASE_TOO_LARGE = "llm_case_too_large"

WHAT_TO_SAY = {
    UNREACHABLE: "The assistant is not available right now.",
    TIMEOUT: "The assistant took too long. Try again.",
    REFUSED: "The engine refused the connection. Tell whoever looks after the server.",
    TOO_LONG: "This transcript is too long for the AI assistant.",
    BAD_OUTPUT: "The assistant's answer did not come through. Try again.",
    ERROR: "The assistant hit a problem. Try again.",
    CASE_TOO_LARGE: "This case is too large for one question.",
}

# The check and Test connection are quick questions, not calls.
CHECK_TIMEOUT = 10
# What Test connection asks the model, and the only answer it wants.
TINY_QUESTION = "Reply with the single word: ready"


class Problem(Exception):
    """A failed call, carrying its reason class and a line for the person."""

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(WHAT_TO_SAY.get(reason, WHAT_TO_SAY[ERROR]))
        self.reason = reason
        self.detail = detail


# The token and the client ------------------------------------------------------


def token_path() -> Path:
    """The secret where Compose mounts it, or the .env path on a workstation."""
    if TOKEN_PATH.exists():
        return TOKEN_PATH
    return Path(os.environ.get("LLM_API_TOKEN_FILE", "./secrets/llm_api_token"))


def token() -> str:
    path = token_path()
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def token_is_set() -> bool:
    return bool(token())


def address() -> str:
    return str(settings_store.get("engine_address") or "").strip()


def model_name() -> str:
    return str(settings_store.get("engine_model") or "").strip()


def configured() -> bool:
    """Whether there is an engine to talk to at all.

    An installation without one leaves the AI assistant off and everything
    else works; the check stays quiet rather than failing every minute.
    """
    return bool(settings_store.get("assistant_available")) or token_is_set()


def client(timeout: float):
    """One client per call, so a changed address or token is used at once."""
    from openai import OpenAI

    return OpenAI(
        base_url=address(),
        api_key=token() or "unset",
        timeout=timeout,
        # The app does its own one retry where the chapter allows one, and
        # never on a timeout.
        max_retries=0,
    )


def classify(problem: Exception) -> str:
    """Which of the six reason classes a failure is."""
    from openai import (
        APIConnectionError,
        APITimeoutError,
        AuthenticationError,
        BadRequestError,
        PermissionDeniedError,
    )

    if isinstance(problem, Problem):
        return problem.reason
    if isinstance(problem, (AuthenticationError, PermissionDeniedError)):
        return REFUSED
    if isinstance(problem, APITimeoutError):
        return TIMEOUT
    if isinstance(problem, APIConnectionError):
        return UNREACHABLE
    if isinstance(problem, BadRequestError) and "context length" in str(problem):
        return TOO_LONG
    return ERROR


# The status row ----------------------------------------------------------------


class EngineStatus(models.Model):
    """What the last minute's check found. One row, read by every page.

    `since` is when the answer last changed, so the status page can say
    "unreachable since 10:31" and the viewer can disable the buttons the
    moment the engine goes away, without either of them touching the network.
    """

    reachable = models.BooleanField(default=False)
    since = models.DateTimeField(default=timezone.now)
    checked_at = models.DateTimeField(null=True, blank=True)
    served_models = models.JSONField(default=list, blank=True)
    reason = models.CharField(max_length=40, blank=True, default="")
    # The panel's Test connection: when, what the engine listed, what it
    # answered, and how long it took. Never a prompt beyond the tiny question.
    last_test = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "engine status"

    @classmethod
    def the_one(cls) -> EngineStatus:
        row, _ = cls.objects.get_or_create(pk=1)
        return row

    def record(self, reachable: bool, *, served_models=None, reason="") -> None:
        now = timezone.now()
        if reachable != self.reachable or self.checked_at is None:
            self.since = now
        self.reachable = reachable
        self.checked_at = now
        self.served_models = list(served_models or [])
        self.reason = reason
        self.save()


def is_reachable() -> bool:
    """What the viewer and the tasks ask before offering or making a call."""
    return EngineStatus.the_one().reachable


# The check and Test connection -------------------------------------------------


def list_models() -> list[str]:
    answer = client(CHECK_TIMEOUT).models.list()
    return sorted(one.id for one in answer.data)


def check() -> EngineStatus:
    """The once a minute question: does the engine answer, with the token?

    Writes the status row and nothing else: no audit row, because a check that
    ran is not an event, and no log line while nothing changes.
    """
    status = EngineStatus.the_one()
    if not configured():
        status.record(False, reason="")
        return status
    try:
        served = list_models()
    except Exception as problem:  # noqa: BLE001 - every failure is a reason class
        reason = classify(problem)
        if status.reachable or status.checked_at is None:
            log.warning("the engine is unreachable: %s", reason)
        status.record(False, reason=reason)
        return status
    if not status.reachable:
        log.info("the engine answers; it serves %s", ", ".join(served) or "nothing")
    status.record(True, served_models=served)
    return status


def test_connection() -> dict:
    """The panel's Test connection: list the models, then one tiny completion.

    Runs on llm-worker, because only it can reach the engine; the result is
    kept on the status row for the panel to read on its next poll.
    """
    began = time.monotonic()
    result = {"at": timezone.now().isoformat(timespec="seconds"), "ok": False}
    try:
        served = list_models()
        result["models"] = served
        if model_name() not in served:
            result["warning"] = (
                f"The engine does not list {model_name() or '(no model name set)'}. "
                "Check the Model name setting."
            )
        answer = complete(
            [{"role": "user", "content": TINY_QUESTION}],
            max_completion_tokens=8,
            temperature=0,
            top_p=1,
            thinking=False,
            timeout=CHECK_TIMEOUT * 3,
        )
        result["answered"] = answer["text"].strip()[:80]
        result["ok"] = True
    except Exception as problem:  # noqa: BLE001 - reported, never raised at the page
        result["reason"] = classify(problem)
        result["says"] = WHAT_TO_SAY[result["reason"]]
    result["seconds"] = round(time.monotonic() - began, 1)

    status = EngineStatus.the_one()
    status.last_test = result
    status.save(update_fields=["last_test"])
    check()
    return result


def status_for_the_panel() -> dict:
    """The Status page's AI assistant line."""
    status = EngineStatus.the_one()
    local = timezone.localtime
    if not configured():
        return {
            "state": "off",
            "says": (
                "off; no engine token yet"
                if address() and not token_is_set()
                else "off; no engine is configured"
            ),
            "test": status.last_test,
        }
    if status.checked_at is None:
        return {"state": "unknown", "says": "not checked yet", "test": status.last_test}
    if status.reachable:
        return {
            "state": "reachable",
            "says": (
                f"reachable, model {model_name() or '(none set)'}, "
                f"checked {local(status.checked_at):%H:%M}"
            ),
            "models": status.served_models,
            "test": status.last_test,
        }
    return {
        "state": "unreachable",
        "says": f"unreachable since {local(status.since):%H:%M}",
        "reason": status.reason,
        "test": status.last_test,
    }


# One call ----------------------------------------------------------------------


def complete(
    messages: list[dict],
    *,
    max_completion_tokens: int,
    temperature: float,
    top_p: float,
    thinking: bool,
    timeout: float,
    schema: dict | None = None,
) -> dict:
    """One chat completion, whole, with the chapter's rules applied.

    Explicit sampling on every call, the answer cap always sent, thinking
    turned on or off per request, and a JSON schema through vLLM's structured
    output when a feature wants one. One automatic retry on a connection
    error and none on a timeout. Returns the text, the finish reason, the
    engine's usage figures, and the model, and raises Problem otherwise.
    """
    from openai import APIConnectionError, APITimeoutError

    extra: dict = {"chat_template_kwargs": {"enable_thinking": thinking}}
    if schema is not None:
        extra["structured_outputs"] = {"json": schema}

    def once():
        return client(timeout).chat.completions.create(
            model=model_name(),
            messages=messages,
            max_completion_tokens=max_completion_tokens,
            temperature=temperature,
            top_p=top_p,
            extra_body=extra,
        )

    try:
        try:
            answer = once()
        except APITimeoutError:
            raise
        except APIConnectionError:
            answer = once()
    except Exception as problem:  # noqa: BLE001 - every failure becomes a reason class
        raise Problem(classify(problem), str(problem)[:200]) from problem

    choice = answer.choices[0]
    usage = answer.usage
    return {
        "text": choice.message.content or "",
        "finish_reason": choice.finish_reason or "",
        "input_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
        "output_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
        "model": answer.model or model_name(),
    }
