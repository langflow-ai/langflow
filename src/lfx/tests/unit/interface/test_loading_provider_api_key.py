"""Tests for provider-aware API-key resolution in unified model components."""
# pragma: allowlist secret -- all credentials in this file are fake test data

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from lfx.interface.initialize.loading import update_params_with_load_from_db_fields
from lfx.services.session import NoopSession


def _unified_model_component(variable_values: dict[str, str]) -> MagicMock:
    component = MagicMock()
    component._inputs = {
        "model": SimpleNamespace(field_type=SimpleNamespace(value="model")),
        "api_key": SimpleNamespace(display_name="API Key"),
    }
    component.get_variable = AsyncMock(side_effect=lambda name, **_kwargs: variable_values[name])
    return component


@pytest.mark.parametrize(
    ("params", "load_from_db_fields", "variable_values", "expected_api_key"),
    [
        (
            {"model": [{"provider": "OpenAI"}], "api_key": "WATSONX_APIKEY"},  # pragma: allowlist secret
            ["api_key"],
            {"OPENAI_API_KEY": "openai-secret"},  # pragma: allowlist secret
            "openai-secret",
        ),
        (
            {
                "model": [{"provider": "OpenAI"}],
                "provider": "Anthropic",
                "api_key": "WATSONX_APIKEY",  # pragma: allowlist secret
            },
            ["api_key"],
            {"ANTHROPIC_API_KEY": "anthropic-secret"},  # pragma: allowlist secret
            "anthropic-secret",
        ),
        (
            {
                "model": [{"provider": "OpenAI"}],
                "provider": "RUNTIME_PROVIDER",
                "api_key": "ANTHROPIC_API_KEY",  # pragma: allowlist secret
            },
            ["provider", "api_key"],
            {
                "RUNTIME_PROVIDER": "Anthropic",
                "ANTHROPIC_API_KEY": "anthropic-secret",  # pragma: allowlist secret
            },
            "anthropic-secret",
        ),
        (
            {
                "model": [{"provider": "Anthropic"}],
                "provider": "Anthropic",
                "api_key": "ANTHROPIC_API_KEY",  # pragma: allowlist secret
            },
            ["provider", "api_key"],
            {
                "Anthropic": "OpenAI",
                "OPENAI_API_KEY": "openai-secret",  # pragma: allowlist secret
            },
            "openai-secret",
        ),
    ],
)
@pytest.mark.asyncio
async def test_rebinds_canonical_api_key_to_effective_provider(
    params,
    load_from_db_fields,
    variable_values,
    expected_api_key,
):
    component = _unified_model_component(variable_values)

    with (
        patch("lfx.interface.initialize.loading.session_scope") as mock_session_scope,
        patch("lfx.interface.initialize.loading.get_settings_service") as mock_get_settings,
    ):
        mock_session_scope.return_value.__aenter__.return_value = MagicMock()
        mock_get_settings.return_value.settings.use_noop_database = False

        result = await update_params_with_load_from_db_fields(component, params, load_from_db_fields)

    assert result["api_key"] == expected_api_key


@pytest.mark.parametrize(
    ("inputs", "api_key_reference"),
    [
        ({}, "WATSONX_APIKEY"),
        (
            {
                "model": SimpleNamespace(field_type=SimpleNamespace(value="model")),
                "api_key": SimpleNamespace(display_name="API Key"),
            },
            "MY_RUNTIME_KEY",
        ),
    ],
)
@pytest.mark.asyncio
async def test_preserves_load_order_outside_canonical_unified_keys(inputs, api_key_reference):
    component = MagicMock()
    component._inputs = inputs
    component.get_variable = AsyncMock(
        side_effect=lambda name, **_kwargs: {
            api_key_reference: "api-secret",  # pragma: allowlist secret
            "RUNTIME_PROVIDER": "OpenAI",
        }[name]
    )
    params = {
        "model": [{"provider": "Anthropic"}],
        "provider": "RUNTIME_PROVIDER",
        "api_key": api_key_reference,
    }

    with (
        patch("lfx.interface.initialize.loading.session_scope") as mock_session_scope,
        patch("lfx.interface.initialize.loading.get_settings_service") as mock_get_settings,
    ):
        session = MagicMock()
        mock_session_scope.return_value.__aenter__.return_value = session
        mock_get_settings.return_value.settings.use_noop_database = False

        result = await update_params_with_load_from_db_fields(component, params, ["api_key", "provider"])

    assert result["api_key"] == "api-secret"  # pragma: allowlist secret
    assert component.get_variable.await_args_list == [
        call(name=api_key_reference, field="api_key", session=session),
        call(name="RUNTIME_PROVIDER", field="provider", session=session),
    ]


@pytest.mark.asyncio
async def test_rebinds_api_key_from_request_variables_without_env_fallback():
    component = _unified_model_component({})
    component.graph = SimpleNamespace(
        context={
            "request_variables": {
                "WATSONX_APIKEY": "watsonx-secret",  # pragma: allowlist secret
                "OPENAI_API_KEY": "openai-secret",  # pragma: allowlist secret
            },
            "no_env_fallback": True,
        }
    )
    params = {
        "model": [{"provider": "OpenAI"}],
        "api_key": "WATSONX_APIKEY",  # pragma: allowlist secret
    }

    with patch("lfx.interface.initialize.loading.session_scope") as mock_session_scope:
        mock_session_scope.return_value.__aenter__.return_value = NoopSession()

        result = await update_params_with_load_from_db_fields(component, params, ["api_key"])

    assert result["api_key"] == "openai-secret"  # pragma: allowlist secret


@pytest.mark.asyncio
async def test_clears_canonical_api_key_when_effective_provider_has_no_key():
    component = _unified_model_component({})
    params = {
        "model": [{"provider": "Ollama"}],
        "api_key": "WATSONX_APIKEY",  # pragma: allowlist secret
    }

    with (
        patch("lfx.interface.initialize.loading.session_scope") as mock_session_scope,
        patch("lfx.interface.initialize.loading.get_settings_service") as mock_get_settings,
    ):
        mock_session_scope.return_value.__aenter__.return_value = MagicMock()
        mock_get_settings.return_value.settings.use_noop_database = False

        result = await update_params_with_load_from_db_fields(component, params, ["api_key"])

    assert result["api_key"] is None
    component.get_variable.assert_not_awaited()
