from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.components.avian.avian import AVIAN_DEFAULT_MODELS, AvianModelComponent
from lfx.schema.message import Message


@pytest.mark.integration
class TestAvianIntegration:
    """Integration tests for the Avian LLM provider component."""

    @pytest.mark.asyncio
    @patch("langchain_openai.ChatOpenAI")
    async def test_end_to_end_text_generation(self, mock_chat_openai):
        """Test complete flow from component setup through model invocation to message output."""
        mock_model = MagicMock()
        mock_chat_openai.return_value = mock_model

        component = AvianModelComponent()
        component.api_key = "test-key"
        component.model_name = "deepseek/deepseek-v3.2"
        component.temperature = 0.7
        component.max_tokens = 256
        component.model_kwargs = {}
        component.api_base = "https://api.avian.io/v1"
        component.seed = 1
        component.json_mode = False

        model = component.build_model()
        assert model is not None

        mock_message = Message(text="Hello from Avian!")
        with patch.object(component, "text_response", new_callable=AsyncMock, return_value=mock_message):
            result = await component.text_response()
            assert isinstance(result, Message)
            assert result.text == "Hello from Avian!"

        mock_chat_openai.assert_called_once_with(
            model="deepseek/deepseek-v3.2",
            temperature=0.7,
            max_tokens=256,
            model_kwargs={},
            base_url="https://api.avian.io/v1",
            api_key="test-key",
            streaming=False,
            seed=1,
        )

    @pytest.mark.asyncio
    @patch("langchain_openai.ChatOpenAI")
    async def test_end_to_end_json_mode(self, mock_chat_openai):
        """Test complete flow with JSON mode enabled, verifying response_format binding."""
        mock_model = MagicMock()
        mock_bound_model = MagicMock()
        mock_model.bind.return_value = mock_bound_model
        mock_chat_openai.return_value = mock_model

        component = AvianModelComponent()
        component.api_key = "test-key"
        component.model_name = "minimax/minimax-m2.5"
        component.temperature = 0.1
        component.max_tokens = 512
        component.model_kwargs = {}
        component.api_base = "https://api.avian.io/v1"
        component.seed = 42
        component.json_mode = True

        model = component.build_model()
        assert model is mock_bound_model

        mock_model.bind.assert_called_once_with(response_format={"type": "json_object"})

        json_response = '{"name": "test", "value": 42}'
        mock_message = Message(text=json_response)
        with patch.object(component, "text_response", new_callable=AsyncMock, return_value=mock_message):
            result = await component.text_response()
            assert isinstance(result, Message)
            assert '"name"' in result.text

    @pytest.mark.asyncio
    @patch("requests.get")
    async def test_dynamic_model_listing(self, mock_get):
        """Test that get_models fetches and parses the model list from the API."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"id": "deepseek/deepseek-v3.2"},
                {"id": "moonshotai/kimi-k2.5"},
                {"id": "custom/model-1"},
            ]
        }
        mock_get.return_value = mock_response

        component = AvianModelComponent()
        component.api_key = "test-key"
        component.api_base = "https://api.avian.io/v1"

        models = component.get_models()

        assert len(models) == 3
        assert "deepseek/deepseek-v3.2" in models
        assert "custom/model-1" in models

        mock_get.assert_called_once_with(
            "https://api.avian.io/v1/models",
            headers={"Authorization": "Bearer test-key", "Accept": "application/json"},
            timeout=10,
        )

    @pytest.mark.asyncio
    @patch("requests.get")
    async def test_model_listing_fallback_on_error(self, mock_get):
        """Test that get_models falls back to defaults when the API is unreachable."""
        import requests

        mock_get.side_effect = requests.RequestException("Connection refused")

        component = AvianModelComponent()
        component.api_key = "test-key"
        component.api_base = "https://api.avian.io/v1"

        models = component.get_models()
        assert models == AVIAN_DEFAULT_MODELS

    @pytest.mark.asyncio
    @patch("requests.get")
    async def test_model_listing_fallback_no_key(self, mock_get):
        """Test that get_models returns defaults when no API key is configured."""
        component = AvianModelComponent()
        component.api_key = None

        models = component.get_models()
        assert models == AVIAN_DEFAULT_MODELS
        mock_get.assert_not_called()

    @pytest.mark.asyncio
    async def test_build_config_update_refreshes_models(self):
        """Test that updating api_key or model_name in build config triggers model list refresh."""
        component = AvianModelComponent()
        component.api_key = None

        build_config = {"model_name": {"options": []}}

        updated = component.update_build_config(build_config, "new-key", "api_key")
        assert updated["model_name"]["options"] == AVIAN_DEFAULT_MODELS

        # Updating an unrelated field should NOT refresh
        build_config_2 = {"model_name": {"options": ["original"]}}
        updated_2 = component.update_build_config(build_config_2, "val", "temperature")
        assert updated_2["model_name"]["options"] == ["original"]

    @pytest.mark.asyncio
    @patch("langchain_openai.ChatOpenAI")
    async def test_error_propagation(self, mock_chat_openai):
        """Test that build errors from the underlying ChatOpenAI propagate correctly."""
        mock_chat_openai.side_effect = Exception("Invalid API key")

        component = AvianModelComponent()
        component.api_key = "bad-key"
        component.model_name = "deepseek/deepseek-v3.2"
        component.temperature = 0.7
        component.max_tokens = 100
        component.model_kwargs = {}
        component.api_base = "https://api.avian.io/v1"
        component.seed = 1
        component.json_mode = False

        with pytest.raises(Exception, match="Invalid API key"):
            component.build_model()
