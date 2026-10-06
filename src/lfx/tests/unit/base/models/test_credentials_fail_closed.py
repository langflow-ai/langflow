"""Fail-closed tests for database-backed provider variable resolution."""

from contextlib import asynccontextmanager
from uuid import UUID

import pytest
from lfx.base.models.unified_models import credentials

_USER_ID = UUID("11111111-1111-1111-1111-111111111111")
_PROVIDER_VARIABLES = [
    {"variable_key": "OPENAI_API_KEY"},
    {"variable_key": "OPENAI_BASE_URL"},
]


class DatabasePoolTimeoutError(Exception):
    """Model the timeout raised while acquiring a database connection."""


@asynccontextmanager
async def _session_scope():
    yield object()


class _PoolExhaustedVariableService:
    async def get_variable(self, *, name: str, **_kwargs):
        if name == "OPENAI_API_KEY":
            return "sk-from-db"  # pragma: allowlist secret
        raise DatabasePoolTimeoutError


def test_provider_variable_read_error_does_not_return_partial_configuration(monkeypatch):
    """A failed base URL read must abort resolution instead of enabling the provider default."""
    monkeypatch.setattr(credentials, "get_provider_all_variables", lambda _provider: _PROVIDER_VARIABLES)
    monkeypatch.setattr(credentials, "get_variable_service", _PoolExhaustedVariableService)
    monkeypatch.setattr(credentials, "session_scope", _session_scope)

    with pytest.raises(DatabasePoolTimeoutError):
        credentials.get_all_variables_for_provider(_USER_ID, "OpenAI")
