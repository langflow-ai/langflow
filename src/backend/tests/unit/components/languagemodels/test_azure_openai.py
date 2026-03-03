from unittest.mock import MagicMock, patch

import pytest
from lfx.components.azure.azure_openai import AzureChatOpenAIComponent
from pydantic.v1 import SecretStr

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
            "azure_deployment": "gpt-5.1",
            "api_key": "test-api-key",
            "use_legacy_api": False,
            "temperature": 0.7,
            "max_tokens": 1000,
            "model_kwargs": {},
        }

    @pytest.fixture
    def file_names_mapping(self):
        return []

    # ------------------------------------------------------------------
    # build_model: V1 reasoning (default path)
    # ------------------------------------------------------------------

    @patch("lfx.components.azure.azure_openai.ChatOpenAI")
    async def test_build_model_v1(self, mock_chat_openai, component_class, default_kwargs):
        """Test V1 Foundry API model building (default)."""
        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance
        component = component_class(**default_kwargs)
        model = component.build_model()

        mock_chat_openai.assert_called_once_with(
            model="gpt-5.1",
            api_key="test-api-key",
            base_url="https://example.azure.openai.com/openai/v1",
            streaming=False,
            model_kwargs={"reasoning_effort": "medium"},
            max_completion_tokens=1000,
        )
        assert model == mock_instance

    # ------------------------------------------------------------------
    # build_model: V1 non-reasoning (temperature + seed included)
    # ------------------------------------------------------------------

    @patch("lfx.components.azure.azure_openai.ChatOpenAI")
    async def test_build_model_v1_non_reasoning(self, mock_chat_openai, component_class, default_kwargs):
        """V1 non-reasoning model includes temperature and seed."""
        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance

        default_kwargs["model_name"] = "gpt-4.1"
        default_kwargs["azure_deployment"] = "my-gpt4-deploy"
        default_kwargs["seed"] = 42
        component = component_class(**default_kwargs)
        model = component.build_model()

        mock_chat_openai.assert_called_once_with(
            model="my-gpt4-deploy",
            api_key="test-api-key",
            base_url="https://example.azure.openai.com/openai/v1",
            streaming=False,
            model_kwargs={},
            temperature=0.7,
            seed=42,
            max_tokens=1000,
        )
        assert model == mock_instance

    # ------------------------------------------------------------------
    # build_model: legacy reasoning
    # ------------------------------------------------------------------

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
            azure_deployment="gpt-5.1",
            api_version="2025-04-01-preview",
            api_key="test-api-key",
            streaming=False,
            model_kwargs={"reasoning_effort": "medium"},
            max_completion_tokens=1000,
        )
        assert model == mock_instance

    # ------------------------------------------------------------------
    # build_model: legacy non-reasoning
    # ------------------------------------------------------------------

    @patch("lfx.components.azure.azure_openai.AzureChatOpenAI")
    async def test_build_model_legacy_non_reasoning(self, mock_azure_chat_openai, component_class, default_kwargs):
        """Legacy non-reasoning model includes temperature and seed."""
        mock_instance = MagicMock()
        mock_azure_chat_openai.return_value = mock_instance

        default_kwargs["use_legacy_api"] = True
        default_kwargs["api_version"] = "2025-04-01-preview"
        default_kwargs["model_name"] = "gpt-4.1-mini"
        default_kwargs["azure_deployment"] = "gpt-4.1-mini"
        default_kwargs["seed"] = 7
        component = component_class(**default_kwargs)
        model = component.build_model()

        _args, kwargs = mock_azure_chat_openai.call_args
        assert kwargs["temperature"] == 0.7
        assert kwargs["seed"] == 7
        assert kwargs["max_tokens"] == 1000
        assert "reasoning_effort" not in kwargs.get("model_kwargs", {})
        assert model == mock_instance

    # ------------------------------------------------------------------
    # build_model: reasoning model excludes temperature/seed
    # ------------------------------------------------------------------

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

        _args, kwargs = mock_chat_openai.call_args
        assert "temperature" not in kwargs
        assert "seed" not in kwargs
        assert kwargs["model_kwargs"]["reasoning_effort"] == "high"
        assert model == mock_instance

    # ------------------------------------------------------------------
    # build_model: error scenarios
    # ------------------------------------------------------------------

    @patch(
        "lfx.components.azure.azure_openai.ChatOpenAI",
        side_effect=RuntimeError("connection refused"),
    )
    async def test_build_model_v1_connection_error(self, _mock, component_class, default_kwargs):
        """V1 build wraps SDK errors in a descriptive ValueError."""
        component = component_class(**default_kwargs)

        with pytest.raises(ValueError, match="Could not connect to Azure OpenAI V1 API"):
            component.build_model()

    @patch(
        "lfx.components.azure.azure_openai.AzureChatOpenAI",
        side_effect=RuntimeError("timeout"),
    )
    async def test_build_model_legacy_connection_error(self, _mock, component_class, default_kwargs):
        """Legacy build wraps SDK errors in a descriptive ValueError."""
        default_kwargs["use_legacy_api"] = True
        default_kwargs["api_version"] = "2025-04-01-preview"
        component = component_class(**default_kwargs)

        with pytest.raises(ValueError, match="Could not connect to Azure OpenAI API"):
            component.build_model()

    # ------------------------------------------------------------------
    # update_build_config: reasoning vs non-reasoning
    # ------------------------------------------------------------------

    async def test_update_build_config_reasoning(self, component_class, default_kwargs):
        """Test build config for reasoning vs non-reasoning models."""
        component = await self.component_setup(component_class, default_kwargs)

        frontend_node = component.to_frontend_node()
        build_config = frontend_node["data"]["node"]["template"]

        updated_config = component.update_build_config(build_config, "gpt-5.1", "model_name")
        assert updated_config["temperature"]["show"] is False
        assert updated_config["seed"]["show"] is False
        assert updated_config["reasoning_effort"]["show"] is True
        assert updated_config["azure_deployment"]["value"] == "gpt-5.1"

        build_config["temperature"]["show"] = True
        build_config["seed"]["show"] = True

        updated_config = component.update_build_config(build_config, "gpt-4", "model_name")
        assert updated_config["temperature"]["show"] is True
        assert updated_config["seed"]["show"] is True
        assert updated_config["reasoning_effort"]["show"] is False
        assert updated_config["azure_deployment"]["value"] == "gpt-4"

    # ------------------------------------------------------------------
    # update_build_config: use_legacy_api toggling api_version visibility
    # ------------------------------------------------------------------

    async def test_update_build_config_use_legacy_api_true(self, component_class, default_kwargs):
        """Enabling legacy API makes api_version visible."""
        component = await self.component_setup(component_class, default_kwargs)

        frontend_node = component.to_frontend_node()
        build_config = frontend_node["data"]["node"]["template"]

        assert build_config["api_version"]["show"] is False

        updated = component.update_build_config(build_config, True, "use_legacy_api")
        assert updated["api_version"]["show"] is True

    async def test_update_build_config_use_legacy_api_false(self, component_class, default_kwargs):
        """Disabling legacy API hides api_version."""
        component = await self.component_setup(component_class, default_kwargs)

        frontend_node = component.to_frontend_node()
        build_config = frontend_node["data"]["node"]["template"]
        build_config["api_version"]["show"] = True

        updated = component.update_build_config(build_config, False, "use_legacy_api")
        assert updated["api_version"]["show"] is False

    # ------------------------------------------------------------------
    # update_build_config: partial config (KeyError guard)
    # ------------------------------------------------------------------

    async def test_update_build_config_partial_config_no_keyerror(self, component_class, default_kwargs):
        """Partial build_config missing keys must not raise KeyError."""
        component = component_class(**default_kwargs)
        sparse_config: dict = {}

        result = component.update_build_config(sparse_config, True, "use_legacy_api")
        assert result == {}

        result = component.update_build_config(sparse_config, "gpt-5.1", "model_name")
        assert result == {}

    # ------------------------------------------------------------------
    # _is_reasoning_model
    # ------------------------------------------------------------------

    async def test_is_reasoning_model_positive(self, component_class, default_kwargs):
        """Known reasoning model names should be detected."""
        component = component_class(**default_kwargs)
        assert component._is_reasoning_model("gpt-5.1") is True
        assert component._is_reasoning_model("gpt-5-mini") is True
        assert component._is_reasoning_model("o1") is True
        assert component._is_reasoning_model("GPT-5.1") is True

    async def test_is_reasoning_model_negative(self, component_class, default_kwargs):
        """Non-reasoning model names should not be detected."""
        component = component_class(**default_kwargs)
        assert component._is_reasoning_model("gpt-4") is False
        assert component._is_reasoning_model("gpt-4.1-mini") is False
        assert component._is_reasoning_model("some-custom-model") is False

    # ------------------------------------------------------------------
    # _resolve_deployment_name
    # ------------------------------------------------------------------

    async def test_deployment_name_override(self, component_class, default_kwargs):
        """Custom azure_deployment overrides the model-to-deployment mapping."""
        default_kwargs["azure_deployment"] = "my-custom-deployment"
        component = component_class(**default_kwargs)

        result = component._resolve_deployment_name()
        assert result == "my-custom-deployment"

        component.azure_deployment = ""
        component.model_name = "gpt-5.1"
        assert component._resolve_deployment_name() == "gpt-5.1"

    async def test_deployment_name_falls_back_to_model_name(self, component_class, default_kwargs):
        """Empty MODEL_TO_DEPLOYMENT falls back to model_name."""
        default_kwargs["azure_deployment"] = ""
        default_kwargs["model_name"] = "gpt-4.1"
        component = component_class(**default_kwargs)
        assert component._resolve_deployment_name() == "gpt-4.1"

    # ------------------------------------------------------------------
    # _resolve_api_key
    # ------------------------------------------------------------------

    async def test_resolve_api_key_plain_string(self, component_class, default_kwargs):
        """Plain string API key is returned as-is."""
        component = component_class(**default_kwargs)
        assert component._resolve_api_key() == "test-api-key"

    async def test_resolve_api_key_secret_str(self, component_class, default_kwargs):
        """SecretStr API key is unwrapped."""
        default_kwargs["api_key"] = SecretStr("secret-value")
        component = component_class(**default_kwargs)
        assert component._resolve_api_key() == "secret-value"

    async def test_resolve_api_key_none(self, component_class, default_kwargs):
        """None API key returns None."""
        default_kwargs["api_key"] = None
        component = component_class(**default_kwargs)
        assert component._resolve_api_key() is None

    # ------------------------------------------------------------------
    # _prepare_model_kwargs
    # ------------------------------------------------------------------

    async def test_prepare_model_kwargs_strips_api_key(self, component_class, default_kwargs):
        """api_key inside model_kwargs must be stripped."""
        default_kwargs["model_kwargs"] = {
            "api_key": "leaked",
            "custom_param": 42,
        }
        component = component_class(**default_kwargs)

        result = component._prepare_model_kwargs()
        assert "api_key" not in result
        assert result["custom_param"] == 42

    async def test_prepare_model_kwargs_empty(self, component_class, default_kwargs):
        """Empty or None model_kwargs returns an empty dict."""
        default_kwargs["model_kwargs"] = None
        component = component_class(**default_kwargs)
        assert component._prepare_model_kwargs() == {}

    # ------------------------------------------------------------------
    # api_version visibility alignment
    # ------------------------------------------------------------------

    async def test_api_version_hidden_by_default(self, component_class, default_kwargs):
        """api_version starts hidden when use_legacy_api is False."""
        component = await self.component_setup(component_class, default_kwargs)
        frontend_node = component.to_frontend_node()
        build_config = frontend_node["data"]["node"]["template"]
        assert build_config["api_version"]["show"] is False

    async def test_api_version_visible_when_legacy(self, component_class, default_kwargs):
        """api_version becomes visible when use_legacy_api is True."""
        component = await self.component_setup(component_class, default_kwargs)
        frontend_node = component.to_frontend_node()
        build_config = frontend_node["data"]["node"]["template"]

        component.update_build_config(build_config, True, "use_legacy_api")
        assert build_config["api_version"]["show"] is True

        component.update_build_config(build_config, False, "use_legacy_api")
        assert build_config["api_version"]["show"] is False
