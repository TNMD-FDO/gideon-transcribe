"""The prompt: how it is put together, and how it is kept short."""

from service.prompt import build


def words(text: str) -> int:
    """A stand-in tokenizer: one token per word.

    The real count comes from the model's own tokenizer inside the model
    process. What is tested here is the shape of the prompt and the dropping
    rule, neither of which depends on how a token is counted.
    """
    return len(text.split())


def test_nothing_given_means_no_prompt():
    prompt = build("", [], words)
    assert prompt.text is None
    assert prompt.prompt_tokens == 0
    assert prompt.vocabulary_terms_used == 0


def test_terms_alone_become_a_sentence():
    prompt = build("", ["Ramirez", "Escobar"], words)
    assert prompt.text == "Names and terms: Ramirez, Escobar."
    assert prompt.vocabulary_terms_used == 2


def test_the_context_line_comes_first():
    prompt = build("Interview of a witness about a robbery", ["Ramirez"], words)
    assert prompt.text == (
        "Interview of a witness about a robbery. Names and terms: Ramirez."
    )


def test_a_context_line_that_ends_a_sentence_is_left_alone():
    prompt = build("Is this a jail call?", [], words)
    assert prompt.text == "Is this a jail call?"


def test_a_context_line_alone_is_a_prompt():
    prompt = build("A recorded jail call", [], words)
    assert prompt.text == "A recorded jail call."
    assert prompt.vocabulary_terms_used == 0


def test_empty_terms_are_ignored():
    prompt = build("", ["Ramirez", "  ", ""], words)
    assert prompt.vocabulary_terms_used == 1


def test_terms_are_dropped_from_the_end_until_the_prompt_fits():
    terms = [f"term{number}" for number in range(50)]
    prompt = build("", terms, words, limit=10)
    assert prompt.prompt_tokens <= 10
    assert prompt.vocabulary_terms_used == 7
    assert "term0" in prompt.text
    assert "term49" not in prompt.text


def test_a_long_context_line_is_kept_even_when_it_breaks_the_cap():
    context = " ".join(["word"] * 30)
    prompt = build(context, ["Ramirez"], words, limit=10)
    assert prompt.vocabulary_terms_used == 0
    assert prompt.prompt_tokens > 10
    assert prompt.text.startswith("word word")
