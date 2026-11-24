"""Compatibility tests for direct bcrypt password hashing."""

import pytest
from lfx.services.settings.password_hashing import PasswordContext

# Generated with Passlib 1.7.4 and bcrypt 4.0.1 using a fixed test salt.
_LEGACY_SHORT_HASH = "$2b$12$abcdefghijklmnopqrstuug.PDfErjLO7akt/d9b4dONc5gr7OUZu"
_LEGACY_LONG_HASH = "$2b$12$abcdefghijklmnopqrstuuZ81xcjFNJwkIx0gOMcN/qP.7YkCqp4."


@pytest.mark.parametrize("secret", ["test-secret", b"test-secret", ""])
def test_password_round_trip(secret: str | bytes) -> None:
    context = PasswordContext()
    hashed = context.hash(secret)

    assert hashed.startswith("$2b$12$")
    assert context.verify(secret, hashed)
    assert not context.verify("wrong-secret", hashed)


def test_stored_passlib_hashes_remain_valid() -> None:
    context = PasswordContext()

    assert context.verify("legacy-passlib-password", _LEGACY_SHORT_HASH)
    assert not context.verify("wrong-secret", _LEGACY_SHORT_HASH)


def test_long_utf8_passwords_keep_legacy_truncation() -> None:
    context = PasswordContext()
    secret = "ü" * 40  # 80 UTF-8 bytes; Passlib used the first 72.

    assert context.verify(secret, _LEGACY_LONG_HASH)
    assert context.verify(secret[:36] + "different", _LEGACY_LONG_HASH)
    assert not context.verify("ü" * 35 + "x", _LEGACY_LONG_HASH)
    assert context.verify(secret, context.hash(secret))


def test_malformed_hashes_and_null_passwords_fail_closed() -> None:
    context = PasswordContext()

    assert not context.verify("test-secret", "invalid-hash")
    assert not context.verify("test-secret", "")
    assert not context.verify("test\x00secret", _LEGACY_SHORT_HASH)
    with pytest.raises(ValueError, match="null byte"):
        context.hash("test\x00secret")


def test_passlib_size_limit_is_preserved() -> None:
    context = PasswordContext()
    oversized = "x" * 4097

    assert not context.verify(oversized, _LEGACY_SHORT_HASH)
    with pytest.raises(ValueError, match="maximum allowed size"):
        context.hash(oversized)


def test_unicode_passwords_keep_passlib_character_limit() -> None:
    context = PasswordContext()
    secret = "ü" * 4096

    assert context.verify(secret, _LEGACY_LONG_HASH)
    assert context.verify(secret, context.hash(secret))
    assert not context.verify(secret + "ü", _LEGACY_LONG_HASH)
    with pytest.raises(ValueError, match="maximum allowed size"):
        context.hash(secret + "ü")

    oversized_bytes = ("ü" * 2049).encode()
    assert not context.verify(oversized_bytes, _LEGACY_LONG_HASH)
    with pytest.raises(ValueError, match="maximum allowed size"):
        context.hash(oversized_bytes)
