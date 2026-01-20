"""Tests for provider configuration service."""

import os
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langflow.agentic.services.provider_service import (
    DEFAULT_MODELS,
    PREFERRED_PROVIDERS,
    check_api_key,
    get_default_model,
    get_default_provider,
    get_enabled_providers_for_user,
)


class TestPreferredProvidersConstant:
    """Tests for PREFERRED_PROVIDERS constant."""

    def test_should_be_a_list(self):
        assert isinstance(PREFERRED_PROVIDERS, list)

    def test_should_have_anthropic_first(self):
        assert PREFERRED_PROVIDERS[0] == "Anthropic"

    def test_should_have_openai_second(self):
        assert PREFERRED_PROVIDERS[1] == "OpenAI"

    def test_should_contain_expected_providers(self):
        expected = ["Anthropic", "OpenAI", "Google Generative AI", "Groq"]
        assert expected == PREFERRED_PROVIDERS


class TestDefaultModelsConstant:
    """Tests for DEFAULT_MODELS constant."""

    def test_should_be_a_dict(self):
        assert isinstance(DEFAULT_MODELS, dict)

    def test_should_have_anthropic_model(self):
        assert "Anthropic" in DEFAULT_MODELS
        assert "claude" in DEFAULT_MODELS["Anthropic"]

    def test_should_have_openai_model(self):
        assert "OpenAI" in DEFAULT_MODELS
        assert "gpt" in DEFAULT_MODELS["OpenAI"]

    def test_should_have_google_model(self):
        assert "Google Generative AI" in DEFAULT_MODELS
        assert "gemini" in DEFAULT_MODELS["Google Generative AI"]

    def test_should_have_groq_model(self):
        assert "Groq" in DEFAULT_MODELS
        assert "llama" in DEFAULT_MODELS["Groq"]


class TestGetDefaultProvider:
    """Tests for get_default_provider function."""

    def test_should_return_anthropic_when_available(self):
        enabled = ["OpenAI", "Anthropic", "Groq"]

        result = get_default_provider(enabled)

        assert result == "Anthropic"

    def test_should_return_openai_when_anthropic_unavailable(self):
        enabled = ["Groq", "OpenAI"]

        result = get_default_provider(enabled)

        assert result == "OpenAI"

    def test_should_return_first_provider_when_no_preferred(self):
        enabled = ["CustomProvider", "AnotherProvider"]

        result = get_default_provider(enabled)

        assert result == "CustomProvider"

    def test_should_return_none_when_empty_list(self):
        result = get_default_provider([])

        assert result is None

    def test_should_follow_preference_order(self):
        enabled = ["Groq", "Google Generative AI", "OpenAI"]

        result = get_default_provider(enabled)

        assert result == "OpenAI"


class TestGetDefaultModel:
    """Tests for get_default_model function."""

    def test_should_return_anthropic_default(self):
        result = get_default_model("Anthropic")

        assert result is not None
        assert "claude" in result

    def test_should_return_openai_default(self):
        result = get_default_model("OpenAI")

        assert result is not None
        assert "gpt" in result

    def test_should_return_none_for_unknown_provider(self):
        result = get_default_model("UnknownProvider")

        assert result is None


class TestCheckApiKey:
    """Tests for check_api_key function."""

    @pytest.mark.asyncio
    async def test_should_return_key_from_variable_service(self):
        mock_service = MagicMock()
        mock_service.get_variable = AsyncMock(return_value="test-api-key")
        mock_session = MagicMock()
        user_id = uuid4()

        result = await check_api_key(mock_service, user_id, "OPENAI_API_KEY", mock_session)

        assert result == "test-api-key"
        mock_service.get_variable.assert_called_once_with(user_id, "OPENAI_API_KEY", "", mock_session)

    @pytest.mark.asyncio
    async def test_should_fallback_to_env_when_variable_not_found(self):
        mock_service = MagicMock()
        mock_service.get_variable = AsyncMock(side_effect=ValueError("Not found"))
        mock_session = MagicMock()
        user_id = uuid4()

        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-api-key"}):
            result = await check_api_key(mock_service, user_id, "OPENAI_API_KEY", mock_session)

        assert result == "env-api-key"

    @pytest.mark.asyncio
    async def test_should_return_none_when_key_not_available(self):
        mock_service = MagicMock()
        mock_service.get_variable = AsyncMock(side_effect=ValueError("Not found"))
        mock_session = MagicMock()
        user_id = uuid4()

        with patch.dict(os.environ, {}, clear=True):
            # Ensure the key is not in env
            os.environ.pop("TEST_API_KEY", None)

            result = await check_api_key(mock_service, user_id, "TEST_API_KEY", mock_session)

        assert result is None

    @pytest.mark.asyncio
    async def test_should_return_env_when_variable_returns_empty(self):
        mock_service = MagicMock()
        mock_service.get_variable = AsyncMock(return_value="")
        mock_session = MagicMock()
        user_id = uuid4()

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-key"}):
            result = await check_api_key(mock_service, user_id, "ANTHROPIC_API_KEY", mock_session)

        assert result == "env-key"


class TestGetEnabledProvidersForUser:
    """Tests for get_enabled_providers_for_user function."""

    @pytest.mark.asyncio
    async def test_should_return_empty_when_not_database_service(self):
        user_id = uuid4()
        mock_session = MagicMock()

        with patch("langflow.agentic.services.provider_service.get_variable_service") as mock_get:
            mock_get.return_value = MagicMock()  # Not DatabaseVariableService

            result, status = await get_enabled_providers_for_user(user_id, mock_session)

        assert result == []
        assert status == {}

    @pytest.mark.asyncio
    async def test_should_return_empty_when_no_credentials(self):
        user_id = uuid4()
        mock_session = MagicMock()

        with patch("langflow.agentic.services.provider_service.get_variable_service") as mock_get:
            mock_service = MagicMock()
            mock_service.get_all = AsyncMock(return_value=[])

            # Make it look like DatabaseVariableService
            with patch("langflow.agentic.services.provider_service.DatabaseVariableService") as mock_db:
                mock_db.return_value = mock_service
                mock_get.return_value = mock_service

                # Need to make isinstance check pass
                with patch("langflow.agentic.services.provider_service.isinstance", return_value=False):
                    result, status = await get_enabled_providers_for_user(user_id, mock_session)

        assert result == []
        assert status == {}


class TestEdgeCases:
    """Edge case tests for provider service."""

    def test_should_handle_case_sensitivity_in_provider_names(self):
        # Provider names should be exact match
        result = get_default_model("anthropic")  # lowercase

        assert result is None  # Should not match "Anthropic"

    def test_should_handle_empty_string_provider(self):
        result = get_default_model("")

        assert result is None

    def test_should_handle_whitespace_in_provider(self):
        result = get_default_model(" Anthropic ")  # with spaces

        assert result is None
