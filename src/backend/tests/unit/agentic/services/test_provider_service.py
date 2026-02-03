"""Tests for provider service.

Tests the provider configuration and API key checking functionality.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest
from langflow.agentic.services.provider_service import (
    DEFAULT_MODELS,
    PREFERRED_PROVIDERS,
    check_api_key,
    get_default_model,
    get_default_provider,
    get_enabled_providers_for_user,
)


class TestPreferredProviders:
    """Tests for PREFERRED_PROVIDERS configuration."""

    def test_should_have_expected_providers(self):
        """Should have expected providers in preferred order."""
        assert "Anthropic" in PREFERRED_PROVIDERS
        assert "OpenAI" in PREFERRED_PROVIDERS
        assert "Google Generative AI" in PREFERRED_PROVIDERS
        assert "Groq" in PREFERRED_PROVIDERS

    def test_anthropic_should_be_first_preference(self):
        """Anthropic should be the first preferred provider."""
        assert PREFERRED_PROVIDERS[0] == "Anthropic"

    def test_should_have_at_least_two_providers(self):
        """Should have at least two providers for fallback."""
        assert len(PREFERRED_PROVIDERS) >= 2


class TestDefaultModels:
    """Tests for DEFAULT_MODELS configuration."""

    def test_should_have_model_for_each_preferred_provider(self):
        """Should have a default model for each preferred provider."""
        for provider in PREFERRED_PROVIDERS:
            assert provider in DEFAULT_MODELS, f"Missing default model for {provider}"

    def test_default_models_should_be_non_empty_strings(self):
        """Default model names should be non-empty strings."""
        for model in DEFAULT_MODELS.values():
            assert isinstance(model, str)
            assert len(model) > 0


class TestGetDefaultProvider:
    """Tests for get_default_provider function."""

    def test_should_return_first_preferred_when_available(self):
        """Should return first preferred provider when available."""
        enabled = ["OpenAI", "Anthropic", "Groq"]

        result = get_default_provider(enabled)

        assert result == "Anthropic"  # First in PREFERRED_PROVIDERS that's enabled

    def test_should_return_second_preferred_when_first_not_available(self):
        """Should return second preferred when first is not available."""
        enabled = ["OpenAI", "Groq"]  # Anthropic not included

        result = get_default_provider(enabled)

        assert result == "OpenAI"  # Second in PREFERRED_PROVIDERS

    def test_should_return_first_enabled_when_no_preferred_available(self):
        """Should return first enabled when no preferred provider available."""
        enabled = ["CustomProvider", "AnotherProvider"]

        result = get_default_provider(enabled)

        assert result == "CustomProvider"

    def test_should_return_none_for_empty_list(self):
        """Should return None when no providers enabled."""
        result = get_default_provider([])

        assert result is None

    def test_should_respect_preferred_order(self):
        """Should respect the order of PREFERRED_PROVIDERS."""
        enabled = ["Groq", "Google Generative AI", "OpenAI"]

        result = get_default_provider(enabled)

        # Should be OpenAI since it comes before Groq and Google in PREFERRED_PROVIDERS
        assert result == "OpenAI"


class TestGetDefaultModel:
    """Tests for get_default_model function."""

    def test_should_return_model_for_known_provider(self):
        """Should return default model for known provider."""
        result = get_default_model("Anthropic")

        assert result is not None
        assert isinstance(result, str)
        assert "claude" in result.lower()

    def test_should_return_model_for_openai(self):
        """Should return default model for OpenAI."""
        result = get_default_model("OpenAI")

        assert result is not None
        assert "gpt" in result.lower()

    def test_should_return_none_for_unknown_provider(self):
        """Should return None for unknown provider."""
        result = get_default_model("UnknownProvider")

        assert result is None


class TestCheckApiKey:
    """Tests for check_api_key function."""

    @pytest.mark.asyncio
    async def test_should_return_key_from_variable_service(self):
        """Should return API key from variable service when available."""
        mock_service = MagicMock()
        mock_service.get_variable = AsyncMock(return_value="test-api-key")
        mock_session = MagicMock()
        user_id = UUID("12345678-1234-5678-1234-567812345678")

        result = await check_api_key(mock_service, user_id, "OPENAI_API_KEY", mock_session)

        assert result == "test-api-key"
        mock_service.get_variable.assert_called_once_with(user_id, "OPENAI_API_KEY", "", mock_session)

    @pytest.mark.asyncio
    async def test_should_fallback_to_env_when_not_in_service(self):
        """Should fallback to environment variable when not in service."""
        mock_service = MagicMock()
        mock_service.get_variable = AsyncMock(side_effect=ValueError("Not found"))
        mock_session = MagicMock()
        user_id = "test-user"

        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-api-key"}):
            result = await check_api_key(mock_service, user_id, "OPENAI_API_KEY", mock_session)

        assert result == "env-api-key"

    @pytest.mark.asyncio
    async def test_should_return_none_when_not_found_anywhere(self):
        """Should return None when key not found in service or env."""
        mock_service = MagicMock()
        mock_service.get_variable = AsyncMock(side_effect=ValueError("Not found"))
        mock_session = MagicMock()
        user_id = "test-user"

        # Ensure env var is not set
        with patch.dict(os.environ, {}, clear=True):
            # Remove the key if it exists
            os.environ.pop("TEST_API_KEY", None)
            result = await check_api_key(mock_service, user_id, "TEST_API_KEY", mock_session)

        assert result is None

    @pytest.mark.asyncio
    async def test_should_return_env_when_service_returns_empty(self):
        """Should check env when service returns empty string."""
        mock_service = MagicMock()
        mock_service.get_variable = AsyncMock(return_value="")
        mock_session = MagicMock()
        user_id = "test-user"

        with patch.dict(os.environ, {"TEST_KEY": "env-value"}):
            result = await check_api_key(mock_service, user_id, "TEST_KEY", mock_session)

        assert result == "env-value"

    @pytest.mark.asyncio
    async def test_should_accept_string_user_id(self):
        """Should accept string user_id."""
        mock_service = MagicMock()
        mock_service.get_variable = AsyncMock(return_value="key")
        mock_session = MagicMock()

        result = await check_api_key(mock_service, "string-user-id", "API_KEY", mock_session)

        assert result == "key"

    @pytest.mark.asyncio
    async def test_should_accept_uuid_user_id(self):
        """Should accept UUID user_id."""
        mock_service = MagicMock()
        mock_service.get_variable = AsyncMock(return_value="key")
        mock_session = MagicMock()
        user_id = UUID("12345678-1234-5678-1234-567812345678")

        result = await check_api_key(mock_service, user_id, "API_KEY", mock_session)

        assert result == "key"


class TestGetEnabledProvidersForUser:
    """Tests for get_enabled_providers_for_user function."""

    @pytest.mark.asyncio
    async def test_should_return_empty_when_service_not_database(self):
        """Should return empty lists when service is not DatabaseVariableService."""
        mock_session = MagicMock()
        user_id = "test-user"

        with patch("langflow.agentic.services.provider_service.get_variable_service") as mock_get_service:
            mock_get_service.return_value = MagicMock()  # Not DatabaseVariableService

            result = await get_enabled_providers_for_user(user_id, mock_session)

        assert result == ([], {})

    # Note: Testing get_enabled_providers_for_user with credentials requires
    # complex mocking of DatabaseVariableService and isinstance checks.
    # This is better suited for integration tests with actual database setup.


class TestProviderServiceIntegration:
    """Integration tests for provider service."""

    def test_default_provider_should_have_default_model(self):
        """Default provider should have a corresponding default model."""
        for provider in PREFERRED_PROVIDERS:
            model = get_default_model(provider)
            assert model is not None, f"No default model for preferred provider {provider}"

    def test_get_default_provider_returns_valid_provider(self):
        """get_default_provider should return a provider with a default model."""
        enabled = PREFERRED_PROVIDERS.copy()
        provider = get_default_provider(enabled)

        assert provider is not None
        assert get_default_model(provider) is not None
