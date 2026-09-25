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

# The seven reason classes the AI assistant chapter adds to the catalogue.
UNREACHABLE = "llm_unreachable"
TIMEOUT = "llm_timeout"
REFUSED = "llm_refused"
TOO_LONG = "llm_too_long"
BAD_OUTPUT = "llm_bad_output"
ERROR = "llm_error"
# A Moment asked of an engine that takes text only (Phase 4).
NO_VISION = "llm_no_vision"
# The Case Chat's own: a question over more talk than the ceiling allows.
CASE_TOO_LARGE = "llm_case_too_large"

WHAT_TO_SAY = {
    UNREACHABLE: "The assistant is not available right now.",
    TIMEOUT: "The assistant took too long. Try again.",
    REFUSED: "The engine refused the connection. Tell whoever looks after the server.",
    TOO_LONG: "This transcript is too long for the AI assistant.",
    BAD_OUTPUT: "The assistant's answer did not come through. Try again.",
    ERROR: "The assistant hit a problem. Try again.",
    NO_VISION: "This engine cannot look at video.",
    CASE_TOO_LARGE: "This case is too large for one question.",
}

# Every request carries a priority, as the box ledger's shared-engine paragraph
# asks of a client (GIDEON's line 17): 1 is the lowest the engine ranks, and
# the app's interactive calls never ask to go ahead of the engine's owner.
PRIORITY = 1

# What a vLLM says in its 400 when a text-only model is handed a picture or a
# clip. The words differ by version, so any of these means the same thing.
NO_VISION_WORDS = ("video", "image", "multimodal", "multi-modal", "modality")

# The engine reads at least this many tokens a second, so a call's time limit
# grows by one second for every 500 tokens it sends, on top of the feature's
# setting (v1.87.0): a Reading of a hundred thousand tokens gets more than
# three minutes on top, and a small chat call keeps its own limit. Measured on
# the office's engine, where two Readings of 125,000 tokens ran at once in 76
# and 92 seconds; the figure is a floor, not the rate.
TOKENS_PER_SECOND = 500
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
    if isinstance(problem, BadRequestError):
        said = str(problem).lower()
        if "context length" in said:
            return TOO_LONG
        if any(word in said for word in NO_VISION_WORDS):
            return NO_VISION
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
    # What the engine says it can read at once (vLLM's max_model_len on the
    # served model), read with the minute check; None when it did not say
    # (Phase 8 chapter 9). Every fit and every bar reads window() below.
    window_tokens = models.IntegerField(null=True, blank=True)
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

    def record(
        self, reachable: bool, *, served_models=None, reason="", window_tokens=None
    ) -> None:
        now = timezone.now()
        if reachable != self.reachable or self.checked_at is None:
            self.since = now
        self.reachable = reachable
        self.checked_at = now
        self.served_models = list(served_models or [])
        self.window_tokens = window_tokens
        self.reason = reason
        self.save()


def is_reachable() -> bool:
    """What the viewer and the tasks ask before offering or making a call."""
    return EngineStatus.the_one().reachable


def window() -> int:
    """What the engine can read at once: the figure the engine reported at its
    last check, else the Panel's Engine window setting (Phase 8 chapter 9).

    One place, so the fit checks and the incident page's bar never disagree.
    """
    read = EngineStatus.the_one().window_tokens
    if read:
        return int(read)
    return int(settings_store.get("engine_window_tokens"))


def window_source() -> str:
    """'engine' when the figure came from the engine, else 'setting'."""
    return "engine" if EngineStatus.the_one().window_tokens else "setting"


# The check and Test connection -------------------------------------------------


def list_models() -> list[str]:
    return sorted(served_models_and_windows())


def served_models_and_windows() -> dict[str, int | None]:
    """Each served model's id and the window it reports, or None when the
    listing carries no `max_model_len` (an engine that is not vLLM, or a relay
    that strips the field)."""
    answer = client(CHECK_TIMEOUT).models.list()
    found: dict[str, int | None] = {}
    for one in answer.data:
        extra = getattr(one, "model_extra", None) or {}
        raw = extra.get("max_model_len")
        try:
            found[one.id] = int(raw) if raw else None
        except (TypeError, ValueError):
            found[one.id] = None
    return found


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
        windows = served_models_and_windows()
    except Exception as problem:  # noqa: BLE001 - every failure is a reason class
        reason = classify(problem)
        if status.reachable or status.checked_at is None:
            log.warning("the engine is unreachable: %s", reason)
        status.record(False, reason=reason)
        return status
    served = sorted(windows)
    # The window of the model the app talks to; the only one, when the
    # engine names none of ours. A change is worth one log line, since every
    # bar in the app follows it.
    read = windows.get(model_name())
    if read is None and len(windows) == 1:
        read = next(iter(windows.values()))
    if not status.reachable:
        log.info("the engine answers; it serves %s", ", ".join(served) or "nothing")
    if read != status.window_tokens:
        log.info(
            "the engine's window is %s tokens (was %s)",
            read if read else "not reported",
            status.window_tokens or "not reported",
        )
    status.record(True, served_models=served, window_tokens=read)
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
            "window": window(),
            "window_source": window_source(),
            "window_says": (
                f"{window():,} tokens, read from the engine at "
                f"{local(status.checked_at):%H:%M}; the Panel's Engine window "
                f"setting ({int(settings_store.get('engine_window_tokens')):,}) "
                "is the fallback while the engine does not say"
                if status.window_tokens
                else f"{window():,} tokens, from the setting; the engine did not say"
            ),
        }
    return {
        "state": "unreachable",
        "says": f"unreachable since {local(status.since):%H:%M}",
        "reason": status.reason,
        "test": status.last_test,
    }


# One call ----------------------------------------------------------------------


def reading_allowance(messages: list[dict]) -> float:
    """The seconds a call's time limit grows by for what it sends: one for
    every TOKENS_PER_SECOND tokens, the text estimated at four characters a
    token. A picture or a clip in a message counts nothing here."""
    chars = 0
    for message in messages:
        content = message.get("content")
        if isinstance(content, str):
            chars += len(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    chars += len(part["text"])
    return chars / 4 / TOKENS_PER_SECOND


def complete(
    messages: list[dict],
    *,
    max_completion_tokens: int,
    temperature: float,
    top_p: float,
    thinking: bool,
    timeout: float,
    schema: dict | None = None,
    extra: dict | None = None,
) -> dict:
    """One chat completion, whole, with the chapter's rules applied.

    Explicit sampling on every call, the answer cap always sent, thinking
    turned on or off per request, a JSON schema through vLLM's structured
    output when a feature wants one, and the priority every request carries.
    `extra` is merged into the request's vLLM-only fields, for a feature that
    needs one more (a Moment's frame sampling). One automatic retry on a
    connection error and none on a timeout. Returns the text, the finish
    reason, the engine's usage figures, and the model, and raises Problem
    otherwise. A message's content may be a string or a list of parts, as the
    OpenAI shape allows; nothing here looks inside it.
    """
    from openai import APIConnectionError, APITimeoutError

    timeout = timeout + reading_allowance(messages)
    extra_body: dict = {
        "chat_template_kwargs": {"enable_thinking": thinking},
        "priority": PRIORITY,
    }
    if schema is not None:
        extra_body["structured_outputs"] = {"json": schema}
    if extra:
        extra_body.update(extra)

    def once():
        return client(timeout).chat.completions.create(
            model=model_name(),
            messages=messages,
            max_completion_tokens=max_completion_tokens,
            temperature=temperature,
            top_p=top_p,
            extra_body=extra_body,
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
