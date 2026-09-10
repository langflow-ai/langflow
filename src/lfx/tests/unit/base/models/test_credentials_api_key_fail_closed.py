"""Fail-closed tests for database-backed primary API key resolution."""

import re
from contextlib import asynccontextmanager
from uuid import UUID

import pytest
from lfx.base.models.unified_models import credentials
from lfx.services.variable import VariableNotFoundError

_USER_ID = UUID("11111111-1111-1111-1111-111111111111")


class DatabasePoolTimeoutError(Exception):
    """Model the timeout raised while acquiring a database connection."""


@asynccontextmanager
async def _session_scope():
    yield object()


class _FailingVariableService:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def get_variable(self, **_kwargs):
        raise self.error


def _configure_lookup(monkeypatch, error: Exception) -> None:
    monkeypatch.setattr(credentials, "get_provider_secret_variable_key", lambda _provider: "OPENAI_API_KEY")
    monkeypatch.setattr(credentials, "get_provider_all_variables", lambda _provider: [])
    monkeypatch.setattr(credentials, "get_variable_service", lambda: _FailingVariableService(error))
    monkeypatch.setattr(credentials, "session_scope", _session_scope)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")  # pragma: allowlist secret


def test_api_key_read_error_does_not_fall_back_to_env(monkeypatch):
    """An unexpected DB error must propagate instead of silently resolving the process-wide env key."""
    _configure_lookup(monkeypatch, DatabasePoolTimeoutError())

    with pytest.raises(DatabasePoolTimeoutError):
        credentials.get_api_key_for_provider(_USER_ID, "OpenAI")


@pytest.mark.parametrize("api_key", [None, "OPENAI_API_KEY"], ids=["primary", "named"])
@pytest.mark.parametrize(
    "error_message",
    [
        "Could not decrypt credential variable 'OPENAI_API_KEY'.",
        "Multiple shared variables named 'OPENAI_API_KEY' are visible.",
    ],
    ids=["decrypt-failure", "ambiguous-shares"],
)
def test_api_key_value_error_does_not_fall_back_to_env(monkeypatch, api_key, error_message):
    """A non-missing ValueError must propagate instead of resolving the process-wide env key."""
    _configure_lookup(monkeypatch, ValueError(error_message))

    with pytest.raises(ValueError, match=re.escape(error_message)):
        credentials.get_api_key_for_provider(_USER_ID, "OpenAI", api_key)


@pytest.mark.parametrize("api_key", [None, "OPENAI_API_KEY"], ids=["primary", "named"])
def test_api_key_not_found_still_falls_back_to_env(monkeypatch, api_key):
    """A missing database variable must preserve the documented environment fallback."""
    _configure_lookup(monkeypatch, VariableNotFoundError("OPENAI_API_KEY variable not found."))

    assert credentials.get_api_key_for_provider(_USER_ID, "OpenAI", api_key) == "sk-from-env"
