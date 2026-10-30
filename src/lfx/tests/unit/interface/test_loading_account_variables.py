"""Authoritative deployment account failures must survive fallback loaders."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from lfx.interface.initialize import loading
from lfx.services.variable.exceptions import RuntimeVariableError


@pytest.mark.asyncio
@pytest.mark.parametrize("table", [False, True])
async def test_account_failure_never_reaches_environment(monkeypatch, table):
    @asynccontextmanager
    async def session_scope():
        yield SimpleNamespace()

    monkeypatch.setattr(loading, "session_scope", session_scope)
    monkeypatch.setattr(
        loading, "get_settings_service", lambda: SimpleNamespace(settings=SimpleNamespace(use_noop_database=False))
    )

    def forbidden_lookup(*_):
        msg = "An account failure must never query the process environment"
        raise AssertionError(msg)

    monkeypatch.setattr(loading, "safe_getenv", forbidden_lookup)
    component = SimpleNamespace(get_variable=AsyncMock(side_effect=RuntimeVariableError("unavailable")))
    if table:
        params = {
            "headers": [{"value": "KEY", "__load_from_db_fields": {"value": True}}],
            "headers_load_from_db_columns": ["value"],
        }
        fields = ["table:headers"]
    else:
        params, fields = {"api_key": "KEY"}, ["api_key"]  # pragma: allowlist secret
    with pytest.raises(RuntimeVariableError, match="unavailable"):
        await loading.update_params_with_load_from_db_fields(component, params, fields, fallback_to_env_vars=True)


@pytest.mark.asyncio
async def test_account_resolution_precedes_request_variable_override(monkeypatch):
    from lfx.custom.custom_component import custom_component

    service = SimpleNamespace(
        get_account_bound_variable=AsyncMock(return_value=SimpleNamespace(value="owned-value")),
        get_variable=AsyncMock(),
    )
    monkeypatch.setattr(custom_component, "get_variable_service", lambda: service)
    component = SimpleNamespace(
        _user_id="owner",
        user_id="owner",
        graph=SimpleNamespace(context={"request_variables": {"KEY": "request-override"}}),
    )
    result = await custom_component.CustomComponent.get_variable(component, "KEY", "api_key", SimpleNamespace())
    assert result == "owned-value"
    service.get_variable.assert_not_awaited()
