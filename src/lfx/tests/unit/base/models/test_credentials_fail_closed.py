"""Fail-closed tests for database-backed provider variable resolution."""

from contextlib import asynccontextmanager
from unittest.mock import Mock
from uuid import UUID

import pytest
from lfx.base.models.unified_models import credentials
from lfx.services.variable.exceptions import RuntimeVariableError

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


@pytest.mark.parametrize("reason", ["absent", "variable_not_approved", "undecryptable", "target_disabled"])
def test_bound_account_optional_variable_never_falls_back_to_environment(monkeypatch, reason):
    class BoundAccountService:
        async def get_variable(self, *, name: str, **_kwargs):
            if name == "OPENAI_API_KEY":
                return "owned-provider-key"
            msg = "Account variable unavailable"
            raise RuntimeVariableError(msg, reason=reason)

    def forbidden_environment(*_):
        msg = "Bound account lookup must never query the environment"
        raise AssertionError(msg)

    monkeypatch.setattr(credentials, "get_provider_all_variables", lambda _provider: _PROVIDER_VARIABLES)
    monkeypatch.setattr(credentials, "get_variable_service", BoundAccountService)
    monkeypatch.setattr(credentials, "session_scope", _session_scope)
    monkeypatch.setattr(credentials, "provider_variable_from_env", forbidden_environment)
    if reason in {"absent", "variable_not_approved"}:
        assert credentials.get_all_variables_for_provider(_USER_ID, "OpenAI") == {
            "OPENAI_API_KEY": "owned-provider-key"  # pragma: allowlist secret
        }
    else:
        with pytest.raises(RuntimeVariableError):
            credentials.get_all_variables_for_provider(_USER_ID, "OpenAI")


def test_nonsecret_resolution_filters_definitions_before_any_lookup(monkeypatch):
    monkeypatch.setattr(
        credentials,
        "get_provider_all_variables",
        lambda _: [
            {"variable_key": "OPENAI_API_KEY", "is_secret": True},
            {"variable_key": "OTHER_SECRET", "is_secret": True},
            {"variable_key": "OPENAI_BASE_URL", "is_secret": False},
        ],
    )
    read = Mock(return_value="https://api.openai.com/v1")
    environment = Mock(side_effect=AssertionError("Environment must not be read"))
    monkeypatch.setattr(credentials, "_get_standalone_variable", read)
    monkeypatch.setattr(credentials, "provider_variable_from_env", environment)

    assert credentials.get_all_variables_for_provider(None, "OpenAI", include_secrets=False) == {
        "OPENAI_BASE_URL": "https://api.openai.com/v1"
    }
    read.assert_called_once_with("OPENAI_BASE_URL")
    environment.assert_not_called()
