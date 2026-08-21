import pytest
from lfx.services.settings.auth import PasswordContext


def test_password_context_hash_and_verify():
    ctx = PasswordContext()
    password = "correct_horse_battery_staple"

    hashed = ctx.hash(password)
    assert isinstance(hashed, str)
    assert hashed.startswith("$2b$")

    assert ctx.verify(password, hashed) is True
    assert ctx.verify("wrong_password", hashed) is False
    assert ctx.verify("", hashed) is False


def test_password_context_long_password():
    ctx = PasswordContext()
    # Passwords longer than 72 bytes should be safely handled without raising ValueError
    long_password = "a" * 200

    hashed = ctx.hash(long_password)
    assert ctx.verify(long_password, hashed) is True
    assert ctx.verify(long_password[:71], hashed) is False


def test_password_context_invalid_hash():
    ctx = PasswordContext()
    assert ctx.verify("some_password", "invalid_hash_string") is False
    assert ctx.verify("some_password", "") is False
