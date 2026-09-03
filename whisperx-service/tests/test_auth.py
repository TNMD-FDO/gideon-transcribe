"""Tokens: who is let in, and what happens when the file changes."""

import os

from service.auth import Tokens, bearer
from service.tokens import Consumer, format_line

APP = "a" * 64
IT = "b" * 64


def write(path, *consumers):
    path.write_text("\n".join(format_line(one) for one in consumers))
    # Two writes inside the same clock tick would look unchanged, and this is
    # a test, not a race worth engineering around.
    stamp = os.stat(path).st_mtime + 1
    os.utime(path, (stamp, stamp))


def test_a_token_finds_its_consumer(tmp_path):
    path = tmp_path / "tokens"
    write(path, Consumer("transcribe", APP))
    assert Tokens(path).consumer_for(APP).name == "transcribe"


def test_an_unknown_token_finds_nobody(tmp_path):
    path = tmp_path / "tokens"
    write(path, Consumer("transcribe", APP))
    assert Tokens(path).consumer_for("z" * 64) is None


def test_no_token_finds_nobody(tmp_path):
    path = tmp_path / "tokens"
    write(path, Consumer("transcribe", APP))
    tokens = Tokens(path)
    assert tokens.consumer_for(None) is None
    assert tokens.consumer_for("") is None


def test_the_admin_mark_is_carried(tmp_path):
    path = tmp_path / "tokens"
    write(path, Consumer("it", IT, admin=True))
    assert Tokens(path).consumer_for(IT).admin is True


def test_a_new_consumer_is_picked_up_without_a_restart(tmp_path):
    path = tmp_path / "tokens"
    write(path, Consumer("transcribe", APP))
    tokens = Tokens(path)
    assert tokens.consumer_for(IT) is None

    write(path, Consumer("transcribe", APP), Consumer("it", IT, admin=True))
    assert tokens.consumer_for(IT).name == "it"


def test_a_file_being_edited_does_not_lock_everyone_out(tmp_path):
    path = tmp_path / "tokens"
    write(path, Consumer("transcribe", APP))
    tokens = Tokens(path)
    assert tokens.consumer_for(APP) is not None

    # A half-written line: the last good reading has to stand, or a slip of
    # the hand would stop every Consumer at once.
    path.write_text("transcribe")
    stamp = os.stat(path).st_mtime + 1
    os.utime(path, (stamp, stamp))
    assert tokens.consumer_for(APP) is not None


def test_no_file_at_all_lets_nobody_in(tmp_path):
    assert Tokens(tmp_path / "missing").consumer_for(APP) is None


def test_the_names_are_readable_and_the_tokens_are_not(tmp_path):
    path = tmp_path / "tokens"
    write(path, Consumer("transcribe", APP), Consumer("it", IT, admin=True))
    assert Tokens(path).names() == ["transcribe", "it"]


def test_a_bearer_header_is_read():
    assert bearer("Bearer abc123") == "abc123"
    assert bearer("bearer abc123") == "abc123"


def test_anything_that_is_not_a_bearer_header_is_nothing():
    assert bearer(None) is None
    assert bearer("") is None
    assert bearer("abc123") is None
    assert bearer("Basic abc123") is None
    assert bearer("Bearer ") is None
