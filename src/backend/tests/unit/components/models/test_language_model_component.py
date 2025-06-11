from unittest.mock import MagicMock, patch

import pytest
from langflow.base.models.anthropic_constants import ANTHROPIC_MODELS
from langflow.base.models.openai_constants import OPENAI_MODEL_NAMES
from langflow.components.models.language_model import LanguageModelComponent

from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestLanguageModelComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return LanguageModelComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "provider": "OpenAI",
            "model_name": "gpt-3.5-turbo",
            "api_key": "test-api-key",
            "temperature": 0.1,
            "system_message": "You are a helpful assistant.",
            "input_value": "Hello, how are you?",
            "stream": False,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return the file names mapping for version-specific files."""

    async def test_update_build_config_openai(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {
            "model_name": {"options": [], "value": ""},
            "api_key": {"display_name": "API Key"},
        }
        updated_config = component.update_build_config(build_config, "OpenAI", "provider")
        assert updated_config["model_name"]["options"] == OPENAI_MODEL_NAMES
        assert updated_config["model_name"]["value"] == OPENAI_MODEL_NAMES[0]
        assert updated_config["api_key"]["display_name"] == "OpenAI API Key"

    async def test_update_build_config_anthropic(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {
            "model_name": {"options": [], "value": ""},
            "api_key": {"display_name": "API Key"},
        }
        updated_config = component.update_build_config(build_config, "Anthropic", "provider")
        assert updated_config["model_name"]["options"] == ANTHROPIC_MODELS
        assert updated_config["model_name"]["value"] == ANTHROPIC_MODELS[0]
        assert updated_config["api_key"]["display_name"] == "Anthropic API Key"

    @patch("langflow.components.models.language_model.ChatOpenAI")
    async def test_build_model_openai(self, mock_chat_openai, component_class, default_kwargs):
        # Setup mock
        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance

        # Create and configure the component
        component = component_class(**default_kwargs)
        component.provider = "OpenAI"
        component.model_name = "gpt-3.5-turbo"
        component.api_key = "test-key"
        component.temperature = 0.5
        component.stream = False

        # Build the model
        model = component.build_model()

        # Verify the ChatOpenAI was called with the correct parameters
        mock_chat_openai.assert_called_once_with(
            model_name="gpt-3.5-turbo",
            temperature=0.5,
            streaming=False,
            openai_api_key="test-key",
        )
        assert model == mock_instance

    @patch("langflow.components.models.language_model.ChatAnthropic")
    async def test_build_model_anthropic(self, mock_chat_anthropic, component_class, default_kwargs):
        # Setup mock
        mock_instance = MagicMock()
        mock_chat_anthropic.return_value = mock_instance

        # Create and configure the component
        component = component_class(**default_kwargs)
        component.provider = "Anthropic"
        component.model_name = ANTHROPIC_MODELS[0]  # Use the first model from the constants
        component.api_key = "test-key"
        component.temperature = 0.7
        component.stream = False

        # Build the model
        model = component.build_model()

        # Verify the ChatAnthropic was called with the correct parameters
        mock_chat_anthropic.assert_called_once_with(
            model=ANTHROPIC_MODELS[0],
            temperature=0.7,
            streaming=False,
            anthropic_api_key="test-key",
        )
        assert model == mock_instance

    async def test_build_model_openai_missing_api_key(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.provider = "OpenAI"
        component.api_key = None

        with pytest.raises(ValueError, match="OpenAI API key is required when using OpenAI provider"):
            component.build_model()

    async def test_build_model_anthropic_missing_api_key(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.provider = "Anthropic"
        component.api_key = None

        with pytest.raises(ValueError, match="Anthropic API key is required when using Anthropic provider"):
            component.build_model()

    async def test_build_model_unknown_provider(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.provider = "Unknown"

        with pytest.raises(ValueError, match="Unknown provider: Unknown"):
            component.build_model()
