from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from lfx.base.models.unified_models import (
    apply_provider_variable_config_to_build_config,
    get_all_variables_for_provider,
)
from lfx.schema.dotdict import dotdict


@pytest.mark.asyncio
async def test_apply_provider_variable_config_prefill_watsonx(monkeypatch):
    # Mock environment variables
    monkeypatch.setenv("WATSONX_APIKEY", "test-api-key")
    monkeypatch.setenv("WATSONX_PROJECT_ID", "test-project-id")
    monkeypatch.setenv("WATSONX_URL", "https://test.watsonx.ai")

    build_config = dotdict(
        {
            "api_key": {"value": ""},
            "project_id": {"value": ""},
            "base_url_ibm_watsonx": {"value": "https://us-south.ml.cloud.ibm.com"},  # Default
        }
    )

    # Test pre-filling for IBM WatsonX
    updated_config = apply_provider_variable_config_to_build_config(build_config, "IBM WatsonX", user_id=uuid4())

    assert updated_config["api_key"]["value"] == "test-api-key"
    assert updated_config["project_id"]["value"] == "test-project-id"
    # Should override the default URL
    assert updated_config["base_url_ibm_watsonx"]["value"] == "https://test.watsonx.ai"


@pytest.mark.asyncio
async def test_get_all_variables_for_provider_env(monkeypatch):
    monkeypatch.setenv("WATSONX_APIKEY", "test-api-key")
    variables = get_all_variables_for_provider(None, "IBM WatsonX")
    assert variables.get("WATSONX_APIKEY") == "test-api-key"


@pytest.mark.asyncio
async def test_apply_provider_variable_config_no_override_manual(monkeypatch):
    # Mock environment variables
    monkeypatch.setenv("WATSONX_APIKEY", "test-api-key")

    build_config = dotdict(
        {
            "api_key": {"value": "manual-key"},
        }
    )

    # Test that manual value is NOT overridden
    updated_config = apply_provider_variable_config_to_build_config(build_config, "IBM WatsonX")

    assert updated_config["api_key"]["value"] == "manual-key"


@pytest.mark.asyncio
async def test_apply_provider_variable_config_ollama_default_override(monkeypatch):
    # Mock environment variables
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://my-ollama:11434")

    build_config = dotdict(
        {
            "ollama_base_url": {"value": "http://localhost:11434"}  # Default
        }
    )

    # Test pre-filling for Ollama
    updated_config = apply_provider_variable_config_to_build_config(build_config, "Ollama")

    assert updated_config["ollama_base_url"]["value"] == "http://my-ollama:11434"


@pytest.mark.asyncio
async def test_apply_provider_variable_config_db_override(monkeypatch):
    # Mock environment variable
    monkeypatch.setenv("WATSONX_APIKEY", "env-key")

    # Mock variable service
    mock_service = MagicMock()
    mock_service.get_variable = AsyncMock(return_value="db-key")

    with patch("lfx.base.models.unified_models.get_variable_service", return_value=mock_service):
        build_config = dotdict(
            {
                "api_key": {"value": ""},
            }
        )

        updated_config = apply_provider_variable_config_to_build_config(build_config, "IBM WatsonX", user_id=uuid4())

        # DB key should override env key
        assert updated_config["api_key"]["value"] == "db-key"
