"""Whisper's prompt: the context line, then the names and terms.

The service builds the prompt itself rather than letting a Consumer send one,
because the prompt has to stay short and there is exactly one sensible way to
shorten it. Whisper's previous-text slot holds 223 tokens, and whisperx applies
the same prompt to every 30-second chunk, so a long prompt is paid for over and
over and crowds out the text being recognised.

The prompt goes in as `initial_prompt`. `hotwords` and `prefix` are not used:
all three share the same slot, and `prefix` would silence the hotwords.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

# The cap the contract fixes, comfortably inside both the 223-token
# previous-text slot and the 448-token generation limit that whisperx passes to
# the engine without checking.
PROMPT_TOKEN_LIMIT = 200

# The sentence the terms are put in. A plain English sentence works better than
# a bare list, because the model is completing text, not reading a field.
TERMS_LEAD = "Names and terms: "

# What counts as the end of the context line. Anything else gets a full stop,
# so the terms sentence does not run into it.
SENTENCE_ENDS = ".!?"


@dataclass(frozen=True)
class Prompt:
    """The prompt, and what a Consumer's Provenance records about it."""

    text: str | None
    vocabulary_terms_used: int
    prompt_tokens: int


def _terms_sentence(terms: list[str]) -> str:
    return TERMS_LEAD + ", ".join(terms) + "."


def _join(context: str, terms: list[str]) -> str:
    parts: list[str] = []
    if context:
        line = context.strip()
        if line and line[-1] not in SENTENCE_ENDS:
            line += "."
        parts.append(line)
    if terms:
        parts.append(_terms_sentence(terms))
    return " ".join(parts)


def build(
    context: str,
    vocabulary: list[str],
    count_tokens: Callable[[str], int],
    limit: int = PROMPT_TOKEN_LIMIT,
) -> Prompt:
    """Build the prompt, dropping terms from the end until it fits.

    Terms go from the end because a Consumer sends the terms it cares about
    most first. The app sends the office's own vocabulary ahead of a batch's
    own, so what a batch added is what gets dropped.

    A context line long enough to break the cap on its own is kept as it
    stands: it is capped at 500 characters when it is submitted, a Consumer
    wrote it deliberately, and cutting a sentence in half would be worse than
    a slightly long prompt.
    """
    context = context.strip()
    terms = [term.strip() for term in vocabulary if term.strip()]

    if not context and not terms:
        return Prompt(text=None, vocabulary_terms_used=0, prompt_tokens=0)

    while True:
        text = _join(context, terms)
        tokens = count_tokens(text)
        if tokens <= limit or not terms:
            return Prompt(
                text=text,
                vocabulary_terms_used=len(terms),
                prompt_tokens=tokens,
            )
        terms = terms[:-1]
