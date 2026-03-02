from unittest.mock import MagicMock, patch

import pytest
from lfx.components.azure.azure_openai import AzureChatOpenAIComponent

from tests.base import ComponentTestBaseWithoutClient


class TestAzureChatOpenAIComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return AzureChatOpenAIComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "azure_endpoint": "https://example.azure.openai.com/",
            "model_name": "gpt-5.1",
            "azure_deployment": "YOUR-DEPLOYMENT-gpt-5.1",
            "api_key": "test-api-key",
            "use_legacy_api": False,
            "temperature": 0.7,
            "max_tokens": 1000,
            "model_kwargs": {},
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    @patch("lfx.components.azure.azure_openai.ChatOpenAI")
    async def test_build_model_v1(self, mock_chat_openai, component_class, default_kwargs):
        """Test V1 Foundry API model building (default)."""
        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance
        component = component_class(**default_kwargs)
        model = component.build_model()

        mock_chat_openai.assert_called_once_with(
            model="YOUR-DEPLOYMENT-gpt-5.1",
            api_key="test-api-key",
            base_url="https://example.azure.openai.com/openai/v1",
            streaming=False,
            model_kwargs={},
            temperature=0.7,
            max_tokens=1000,
        )
        assert model == mock_instance

    @patch("lfx.components.azure.azure_openai.AzureChatOpenAI")
    async def test_build_model_legacy(self, mock_azure_chat_openai, component_class, default_kwargs):
        """Test legacy API model building."""
        mock_instance = MagicMock()
        mock_azure_chat_openai.return_value = mock_instance
        default_kwargs["use_legacy_api"] = True
        default_kwargs["api_version"] = "2025-04-01-preview"
        component = component_class(**default_kwargs)
        model = component.build_model()

        mock_azure_chat_openai.assert_called_once_with(
            azure_endpoint="https://example.azure.openai.com/",
            azure_deployment="YOUR-DEPLOYMENT-gpt-5.1",
            api_version="2025-04-01-preview",
            api_key="test-api-key",
            streaming=False,
            model_kwargs={},
            temperature=0.7,
            max_tokens=1000,
        )
        assert model == mock_instance

    @patch("lfx.components.azure.azure_openai.ChatOpenAI")
    async def test_build_model_reasoning(self, mock_chat_openai, component_class, default_kwargs):
        """Test reasoning model handling with V1 API."""
        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance
        default_kwargs["model_name"] = "gpt-5.1"
        default_kwargs["reasoning_effort"] = "high"
        default_kwargs["seed"] = 42
        component = component_class(**default_kwargs)
        model = component.build_model()

        # For reasoning models, temperature and seed should be excluded
        # reasoning_effort should be in model_kwargs
        _args, kwargs = mock_chat_openai.call_args
        assert "temperature" not in kwargs
        assert "seed" not in kwargs
        assert kwargs["model_kwargs"]["reasoning_effort"] == "high"
        assert model == mock_instance

    async def test_update_build_config_reasoning(self, component_class, default_kwargs):
        """Test build config updates for reasoning vs non-reasoning models."""
        component = component_class(**default_kwargs)
        build_config = {
            "temperature": {"show": True},
            "seed": {"show": True},
            "reasoning_effort": {"show": True},
        }

        # Test with reasoning model (gpt-5.1)
        updated_config = component.update_build_config(build_config, "gpt-5.1", "model_name")
        assert updated_config["temperature"]["show"] is False
        assert updated_config["seed"]["show"] is False
        assert updated_config["reasoning_effort"]["show"] is True

        # Reset
        build_config["temperature"]["show"] = True
        build_config["seed"]["show"] = True

        # Test with non-reasoning model
        updated_config = component.update_build_config(build_config, "gpt-4", "model_name")
        assert updated_config["temperature"]["show"] is True
        assert updated_config["seed"]["show"] is True
        assert updated_config["reasoning_effort"]["show"] is False

    async def test_deployment_name_override(self, component_class, default_kwargs):
        """Test that custom azure_deployment value overrides the model-to-deployment mapping."""
        default_kwargs["azure_deployment"] = "my-custom-deployment"
        component = component_class(**default_kwargs)

        deployment = component._resolve_deployment_name()
        assert deployment == "my-custom-deployment"

        # Test that empty deployment falls back to mapping
        component.azure_deployment = ""
        component.model_name = "gpt-5.1"
        deployment = component._resolve_deployment_name()
        assert deployment == "YOUR-DEPLOYMENT-gpt-5.1"
