"""Tests for multi-variable provider support in provider service."""

from unittest.mock import MagicMock, patch

import pytest
from langflow.agentic.services.provider_service import get_enabled_providers_for_user


class TestGetEnabledProvidersForUserMulti:
    """Tests for get_enabled_providers_for_user with multiple variables."""

    @pytest.mark.asyncio
    async def test_should_enable_provider_when_all_required_vars_present(self):
        """Should enable provider when all its required variables are present."""
        mock_session = MagicMock()
        user_id = "test-user"

        # Mock variables in database
        var1 = MagicMock()
        var1.name = "WATSONX_APIKEY"
        var1.type = "Credential"
        var2 = MagicMock()
        var2.name = "WATSONX_PROJECT_ID"
        var2.type = "Credential"
        var3 = MagicMock()
        var3.name = "WATSONX_URL"
        var3.type = "Credential"

        mock_variables = [var1, var2, var3]

        with patch("langflow.agentic.services.provider_service.get_variable_service") as mock_get_service:
            from langflow.services.variable.service import DatabaseVariableService

            mock_service = MagicMock(spec=DatabaseVariableService)
            mock_service.get_all.return_value = mock_variables
            mock_get_service.return_value = mock_service

            with patch(
                "langflow.agentic.services.provider_service.get_provider_required_variable_keys"
            ) as mock_get_keys:
                # WatsonX requires these 3 keys
                mock_get_keys.side_effect = (
                    lambda p: ["WATSONX_APIKEY", "WATSONX_PROJECT_ID", "WATSONX_URL"]
                    if p == "IBM WatsonX"
                    else ["OTHER_KEY"]
                )

                with patch(
                    "langflow.agentic.services.provider_service.get_model_provider_variable_mapping"
                ) as mock_get_map:
                    mock_get_map.return_value = {"IBM WatsonX": "WATSONX_APIKEY"}

                    enabled, status = await get_enabled_providers_for_user(user_id, mock_session)

                    assert "IBM WatsonX" in enabled
                    assert status["IBM WatsonX"] is True

    @pytest.mark.asyncio
    async def test_should_disable_provider_when_required_var_missing(self):
        """Should disable provider when at least one required variable is missing."""
        mock_session = MagicMock()
        user_id = "test-user"

        # Mock variables in database - WATSONX_URL is missing
        var1 = MagicMock()
        var1.name = "WATSONX_APIKEY"
        var1.type = "Credential"
        var2 = MagicMock()
        var2.name = "WATSONX_PROJECT_ID"
        var2.type = "Credential"

        mock_variables = [var1, var2]

        with patch("langflow.agentic.services.provider_service.get_variable_service") as mock_get_service:
            from langflow.services.variable.service import DatabaseVariableService

            mock_service = MagicMock(spec=DatabaseVariableService)
            mock_service.get_all.return_value = mock_variables
            mock_get_service.return_value = mock_service

            with patch(
                "langflow.agentic.services.provider_service.get_provider_required_variable_keys"
            ) as mock_get_keys:
                # WatsonX requires these 3 keys
                mock_get_keys.side_effect = (
                    lambda p: ["WATSONX_APIKEY", "WATSONX_PROJECT_ID", "WATSONX_URL"]
                    if p == "IBM WatsonX"
                    else ["OTHER_KEY"]
                )

                with patch(
                    "langflow.agentic.services.provider_service.get_model_provider_variable_mapping"
                ) as mock_get_map:
                    mock_get_map.return_value = {"IBM WatsonX": "WATSONX_APIKEY"}

                    enabled, status = await get_enabled_providers_for_user(user_id, mock_session)

                    assert "IBM WatsonX" not in enabled
                    assert status["IBM WatsonX"] is False
