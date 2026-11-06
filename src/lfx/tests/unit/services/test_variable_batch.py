"""Batch variable reads retain standalone LFX request resolution."""

import pytest
from lfx.services.variable.request_scope import (
    activate_no_env_fallback,
    activate_request_variables,
    reset_no_env_fallback,
    reset_request_variables,
)
from lfx.services.variable.service import VariableService


@pytest.mark.asyncio
@pytest.mark.parametrize("disable_environment", [False, True])
async def test_batch_preserves_memory_request_alias_and_environment_precedence(monkeypatch, disable_environment):
    service = VariableService()
    service.set_variable("CACHED", "cached")
    monkeypatch.setenv("CACHED", "environment")
    monkeypatch.setenv("EXACT", "environment")
    monkeypatch.setenv("ALIASED", "environment")
    monkeypatch.setenv("ENV_ONLY", "environment")
    request = activate_request_variables(
        {
            "CACHED": "request",
            "EXACT": "request",
            "x-langflow-global-var-aliased": "request-alias",
        }
    )
    fallback = activate_no_env_fallback(disabled=disable_environment)
    try:
        values = await service.get_variables({"CACHED", "EXACT", "ALIASED", "ENV_ONLY", "MISSING"})
    finally:
        reset_no_env_fallback(fallback)
        reset_request_variables(request)
    assert values == {
        "CACHED": "cached",
        "EXACT": "request",
        "ALIASED": "request-alias",
        "ENV_ONLY": None if disable_environment else "environment",
        "MISSING": None,
    }
