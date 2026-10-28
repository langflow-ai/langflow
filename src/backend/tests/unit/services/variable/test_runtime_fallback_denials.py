"""Every application credential reader preserves authoritative account failures."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from lfx.services.variable.exceptions import RuntimeVariableError


@asynccontextmanager
async def _session():
    yield SimpleNamespace()


def _forbidden_environment(*_args, **_kwargs):
    msg = "An account policy refusal must not query the process environment"
    raise AssertionError(msg)


def _refused_service():
    return SimpleNamespace(get_variable=AsyncMock(side_effect=RuntimeVariableError("Account lookup refused")))


@pytest.mark.asyncio
async def test_legacy_endpoint_loader_preserves_account_denial(monkeypatch):
    from langflow.interface.initialize import loading

    monkeypatch.setattr(loading, "session_scope", _session)
    monkeypatch.setattr(loading, "safe_getenv", _forbidden_environment)
    with pytest.raises(RuntimeVariableError, match="Account lookup refused"):
        await loading.update_params_with_load_from_db_fields(
            _refused_service(),
            {"api_key": "OPENAI_API_KEY"},  # pragma: allowlist secret
            ["api_key"],
            fallback_to_env_vars=True,
        )


@pytest.mark.asyncio
async def test_agentic_provider_preserves_account_denial(monkeypatch):
    from langflow.agentic.services import provider_service

    monkeypatch.setattr(provider_service.os, "getenv", _forbidden_environment)
    with pytest.raises(RuntimeVariableError, match="Account lookup refused"):
        await provider_service.check_api_key(_refused_service(), "user", "OPENAI_API_KEY", SimpleNamespace())


@pytest.mark.asyncio
async def test_elevenlabs_preserves_account_denial(monkeypatch):
    from langflow.api.v1 import voice_mode

    monkeypatch.setattr(voice_mode, "session_scope_readonly", _session)
    monkeypatch.setattr(voice_mode, "get_variable_service", _refused_service)
    monkeypatch.setattr(voice_mode.os, "getenv", _forbidden_environment)
    with pytest.raises(RuntimeVariableError, match="Account lookup refused"):
        await voice_mode.get_or_create_elevenlabs_client("user")


@pytest.mark.asyncio
@pytest.mark.parametrize("bulk", [False, True])
async def test_policy_database_failure_cannot_be_mistaken_for_ordinary_absence(monkeypatch, bulk):
    from langflow.services.variable import runtime_policy

    async def unavailable(**_):
        msg = "Database parameters containing sensitive values"
        raise RuntimeError(msg)

    monkeypatch.setattr(runtime_policy, "_bulk_resolver" if bulk else "_resolver", unavailable)
    resolve = runtime_policy.resolve_runtime_variables if bulk else runtime_policy.resolve_runtime_variable
    with pytest.raises(RuntimeVariableError, match="Deployment variable policy is unavailable") as caught:
        await resolve(user_id=uuid4())
    assert caught.value.reason == "policy_unavailable"
    assert "sensitive" not in str(caught.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("bulk", [False, True])
async def test_policy_load_failure_cannot_enable_fallback(monkeypatch, bulk):
    from langflow.services.deployment_artifacts import activation
    from langflow.services.variable import runtime_policy

    def unavailable():
        msg = "Broken extension"
        raise RuntimeError(msg)

    monkeypatch.setattr(activation, "load_activation_extensions", unavailable)
    resolve = runtime_policy.resolve_runtime_variables if bulk else runtime_policy.resolve_runtime_variable
    with pytest.raises(RuntimeVariableError, match="Deployment variable policy is unavailable"):
        await resolve(user_id=uuid4())
    with pytest.raises(RuntimeVariableError, match="Deployment variable policy is unavailable"):
        runtime_policy.runtime_variables_policy_enabled()
