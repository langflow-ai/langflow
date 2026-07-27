"""Shared GreenPT bundle helpers."""

from pydantic import SecretStr


def secret_value(value: str | SecretStr) -> str:
    """Return the plain value of a string or Pydantic secret."""
    return value.get_secret_value() if isinstance(value, SecretStr) else value
