"""Fail-closed tests for database-backed primary API key resolution."""

from contextlib import asynccontextmanager
from uuid import UUID

import pytest
from lfx.base.models.unified_models import credentials

_USER_ID = UUID("11111111-1111-1111-1111-111111111111")


class DatabasePoolTimeoutError(Exception):
    """Model the timeout raised while acquiring a database connection."""


@asynccontextmanager
async def _session_scope():
    yield object()


class _PoolExhaustedVariableService:
    async def get_variable(self, **_kwargs):
        raise DatabasePoolTimeoutError


def test_api_key_read_error_does_not_fall_back_to_env(monkeypatch):
    """An unexpected DB error must propagate instead of silently resolving the process-wide env key."""
    monkeypatch.setattr(credentials, "get_provider_secret_variable_key", lambda _provider: "OPENAI_API_KEY")
    monkeypatch.setattr(credentials, "get_variable_service", _PoolExhaustedVariableService)
    monkeypatch.setattr(credentials, "session_scope", _session_scope)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")  # pragma: allowlist secret

    with pytest.raises(DatabasePoolTimeoutError):
        credentials.get_api_key_for_provider(_USER_ID, "OpenAI")
