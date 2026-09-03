"""The tokens file: what a line means, and what is refused."""

from __future__ import annotations

import pytest
from service.tokens import Consumer, format_line, new_token, parse_file, parse_line


def test_a_token_is_64_hexadecimal_characters():
    token = new_token()
    assert len(token) == 64
    assert set(token) <= set("0123456789abcdef")


def test_two_tokens_are_never_the_same():
    assert new_token() != new_token()


def test_a_line_puts_the_name_in_a_column():
    line = format_line(Consumer(name="transcribe", token="a" * 64))
    assert line == "transcribe      " + "a" * 64


def test_an_admin_line_says_so():
    line = format_line(Consumer(name="it", token="b" * 64, admin=True))
    assert line.endswith("  admin")


def test_a_line_reads_back_as_it_was_written():
    consumer = Consumer(name="it", token="c" * 64, admin=True)
    assert parse_line(format_line(consumer)) == consumer


def test_blank_lines_and_comments_are_not_consumers():
    assert parse_line("") is None
    assert parse_line("   ") is None
    assert parse_line("# name    token    role") is None


def test_a_line_with_no_token_is_refused():
    with pytest.raises(ValueError, match="no token"):
        parse_line("transcribe")


def test_a_word_that_is_not_admin_is_refused():
    with pytest.raises(ValueError, match="unknown word"):
        parse_line("it  " + "d" * 64 + "  superuser")


def test_a_file_keeps_the_order_of_its_lines():
    text = "\n".join(
        [
            "# name        token",
            "transcribe    " + "1" * 64,
            "",
            "it            " + "2" * 64 + "  admin",
        ]
    )
    consumers = parse_file(text)
    assert [consumer.name for consumer in consumers] == ["transcribe", "it"]
    assert consumers[1].admin is True


def test_the_same_name_twice_is_refused():
    text = "app  " + "1" * 64 + "\napp  " + "2" * 64
    with pytest.raises(ValueError, match="used twice"):
        parse_file(text)


def test_the_same_token_twice_is_refused():
    text = "app  " + "1" * 64 + "\nother  " + "1" * 64
    with pytest.raises(ValueError, match="same token"):
        parse_file(text)
