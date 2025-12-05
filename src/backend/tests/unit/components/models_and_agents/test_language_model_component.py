import os
from unittest.mock import MagicMock, patch

import pytest
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from lfx.base.models.anthropic_constants import ANTHROPIC_MODELS
from lfx.base.models.google_generative_ai_constants import GOOGLE_GENERATIVE_AI_MODELS
from lfx.base.models.openai_constants import OPENAI_REASONING_MODEL_NAMES
from lfx.components.models_and_agents import LanguageModelComponent

from tests.base import ComponentTestBaseWithoutClient


class TestLanguageModelComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return LanguageModelComponent

    @pytest.fixture
    def default_kwargs(self):
        return {
            "model": [
                {
                    "name": "gpt-3.5-turbo",
                    "provider": "OpenAI",
                    "metadata": {
                        "context_length": 128000,
                        "model_class": "ChatOpenAI",
                        "model_name_param": "model",
                        "api_key_param": "api_key",
                        "reasoning_models": OPENAI_REASONING_MODEL_NAMES,
                    },
                }
            ],
            "api_key": "test-api-key",
            "temperature": 0.1,
            "system_message": "You are a helpful assistant.",
            "input_value": "Hello, how are you?",
            "stream": False,
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return the file names mapping for version-specific files."""
        # No version-specific files for this component
        return []

    @pytest.fixture
    def openai_api_key(self):
        """Fixture to get OpenAI API key from environment variable."""
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            pytest.skip("OPENAI_API_KEY environment variable not set")
        return api_key

    @pytest.fixture
    def anthropic_api_key(self):
        """Fixture to get Anthropic API key from environment variable."""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            pytest.skip("ANTHROPIC_API_KEY environment variable not set")
        return api_key

    @pytest.fixture
    def google_api_key(self):
        """Fixture to get Google API key from environment variable."""
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            pytest.skip("GOOGLE_API_KEY environment variable not set")
        return api_key

    @patch("lfx.base.models.unified_models.get_model_classes")
    async def test_openai_model_creation(self, mock_get_model_classes, component_class, default_kwargs):
        """Test that the component returns an instance of ChatOpenAI for OpenAI provider."""
        # Setup mock
        mock_openai_class = MagicMock()
        mock_instance = MagicMock()
        mock_instance.model_name = "gpt-3.5-turbo"
        mock_instance.temperature = 0.5
        mock_instance.streaming = False
        mock_openai_class.return_value = mock_instance
        mock_model_classes_dict = MagicMock()
        mock_model_classes_dict.get.return_value = mock_openai_class
        mock_get_model_classes.return_value = mock_model_classes_dict

        component = component_class(**default_kwargs)
        component.api_key = "sk-test-key"
        component.temperature = 0.5
        component.stream = False

        model = component.build_model()

        # Verify the model class getter was called
        mock_model_classes_dict.get.assert_called_once_with("ChatOpenAI")

        # Verify the mock was called
        assert mock_openai_class.call_count == 1
        call_kwargs = mock_openai_class.call_args[1]

        assert call_kwargs["model"] == "gpt-3.5-turbo"
        assert call_kwargs["temperature"] == 0.5
        assert not call_kwargs["streaming"]
        assert call_kwargs["api_key"] == "sk-test-key"
        assert model == mock_instance

    @patch("lfx.base.models.unified_models.get_model_classes")
    async def test_anthropic_model_creation(self, mock_get_model_classes, component_class):
        """Test that the component returns an instance of ChatAnthropic for Anthropic provider."""
        # Setup mock
        mock_anthropic_class = MagicMock()
        mock_instance = MagicMock()
        mock_instance.model = ANTHROPIC_MODELS[0]
        mock_instance.temperature = 0.7
        mock_instance.streaming = False
        mock_anthropic_class.return_value = mock_instance
        mock_model_classes_dict = MagicMock()
        mock_model_classes_dict.get.return_value = mock_anthropic_class
        mock_get_model_classes.return_value = mock_model_classes_dict

        component = component_class(
            model=[
                {
                    "name": ANTHROPIC_MODELS[0],
                    "provider": "Anthropic",
                    "metadata": {
                        "context_length": 200000,
                        "model_class": "ChatAnthropic",
                        "model_name_param": "model",
                        "api_key_param": "api_key",
                    },
                }
            ],
            api_key="sk-ant-test-key",
            temperature=0.7,
            stream=False,
        )

        model = component.build_model()

        # Verify the model class getter was called
        mock_model_classes_dict.get.assert_called_once_with("ChatAnthropic")

        # Verify the mock was called
        assert mock_anthropic_class.call_count == 1
        call_kwargs = mock_anthropic_class.call_args[1]

        assert call_kwargs["model"] == ANTHROPIC_MODELS[0]
        assert call_kwargs["temperature"] == 0.7
        assert not call_kwargs["streaming"]
        assert call_kwargs["api_key"] == "sk-ant-test-key"
        assert model == mock_instance

    @patch("lfx.base.models.unified_models.get_model_classes")
    async def test_google_model_creation(self, mock_get_model_classes, component_class):
        """Test that the component returns an instance of ChatGoogleGenerativeAI for Google provider."""
        # Setup mock
        mock_google_class = MagicMock()
        mock_instance = MagicMock()
        mock_google_class.return_value = mock_instance
        mock_model_classes_dict = MagicMock()
        mock_model_classes_dict.get.return_value = mock_google_class
        mock_get_model_classes.return_value = mock_model_classes_dict

        component = component_class(
            model=[
                {
                    "name": GOOGLE_GENERATIVE_AI_MODELS[0],
                    "provider": "Google",
                    "metadata": {
                        "context_length": 32768,
                        "model_class": "ChatGoogleGenerativeAIFixed",
                        "model_name_param": "model",
                        "api_key_param": "google_api_key",
                    },
                }
            ],
            api_key="google-test-key",
            temperature=0.7,
            stream=False,
        )

        model = component.build_model()

        # Verify the model class getter was called
        mock_model_classes_dict.get.assert_called_once_with("ChatGoogleGenerativeAIFixed")

        # Verify the mock was called
        assert mock_google_class.call_count == 1
        call_kwargs = mock_google_class.call_args[1]

        assert call_kwargs["model"] == GOOGLE_GENERATIVE_AI_MODELS[0]
        assert call_kwargs["temperature"] == 0.7
        assert not call_kwargs["streaming"]
        assert call_kwargs["google_api_key"] == "google-test-key"
        assert model == mock_instance

    @patch("lfx.base.models.unified_models.get_variable_service")
    async def test_build_model_openai_missing_api_key(self, mock_get_variable_service, component_class, default_kwargs):
        # Mock get_variable_service to return None (no API key found)
        mock_service = MagicMock()
        mock_service.get_variable.return_value = None
        mock_get_variable_service.return_value = mock_service

        component = component_class(**default_kwargs)
        component.api_key = None

        with pytest.raises(ValueError, match="OpenAI API key is required when using OpenAI provider"):
            component.build_model()

    @patch("lfx.base.models.unified_models.get_variable_service")
    async def test_build_model_anthropic_missing_api_key(self, mock_get_variable_service, component_class):
        # Mock get_variable_service to return None (no API key found)
        mock_service = MagicMock()
        mock_service.get_variable.return_value = None
        mock_get_variable_service.return_value = mock_service

        component = component_class(
            model=[
                {
                    "name": ANTHROPIC_MODELS[0],
                    "provider": "Anthropic",
                    "metadata": {
                        "model_class": "ChatAnthropic",
                        "model_name_param": "model",
                        "api_key_param": "api_key",
                    },
                }
            ],
            api_key=None,
        )

        with pytest.raises(ValueError, match="Anthropic API key is required when using Anthropic provider"):
            component.build_model()

    @patch("lfx.base.models.unified_models.get_variable_service")
    async def test_build_model_google_missing_api_key(self, mock_get_variable_service, component_class):
        # Mock get_variable_service to return None (no API key found)
        mock_service = MagicMock()
        mock_service.get_variable.return_value = None
        mock_get_variable_service.return_value = mock_service

        component = component_class(
            model=[
                {
                    "name": GOOGLE_GENERATIVE_AI_MODELS[0],
                    "provider": "Google",
                    "metadata": {
                        "model_class": "ChatGoogleGenerativeAIFixed",
                        "model_name_param": "model",
                        "api_key_param": "google_api_key",
                    },
                }
            ],
            api_key=None,
        )

        with pytest.raises(ValueError, match="Google API key is required when using Google provider"):
            component.build_model()

    async def test_build_model_no_model_selection(self, component_class):
        component = component_class(
            model=[],
            api_key="test-key",
        )

        with pytest.raises(ValueError, match="A model selection is required"):
            component.build_model()

    async def test_build_model_no_model_class(self, component_class):
        component = component_class(
            model=[
                {
                    "name": "test-model",
                    "provider": "Test",
                    "metadata": {
                        # No model_class defined
                        "model_name_param": "model",
                        "api_key_param": "api_key",
                    },
                }
            ],
            api_key="test-key",
        )

        with pytest.raises(ValueError, match="No model class defined for test-model"):
            component.build_model()

    @patch("lfx.base.models.unified_models.get_model_classes")
    async def test_reasoning_model_no_temperature(self, mock_get_model_classes, component_class):
        """Test that reasoning models don't include temperature parameter."""
        # Setup mock
        mock_openai_class = MagicMock()
        mock_instance = MagicMock()
        mock_openai_class.return_value = mock_instance
        mock_model_classes_dict = MagicMock()
        mock_model_classes_dict.get.return_value = mock_openai_class
        mock_get_model_classes.return_value = mock_model_classes_dict

        # Use a reasoning model
        reasoning_model = OPENAI_REASONING_MODEL_NAMES[0] if OPENAI_REASONING_MODEL_NAMES else "o1-preview"

        component = component_class(
            model=[
                {
                    "name": reasoning_model,
                    "provider": "OpenAI",
                    "metadata": {
                        "model_class": "ChatOpenAI",
                        "model_name_param": "model",
                        "api_key_param": "api_key",
                        "reasoning_models": OPENAI_REASONING_MODEL_NAMES,
                    },
                }
            ],
            api_key="sk-test-key",
            temperature=0.5,  # This should be ignored
            stream=False,
        )

        _ = component.build_model()

        # Verify the mock was called
        assert mock_openai_class.call_count == 1
        call_kwargs = mock_openai_class.call_args[1]

        # Temperature should NOT be in kwargs for reasoning models
        assert "temperature" not in call_kwargs
        assert call_kwargs["model"] == reasoning_model
        assert not call_kwargs["streaming"]
        assert call_kwargs["api_key"] == "sk-test-key"

    async def test_openai_live_api(self, component_class, default_kwargs, openai_api_key):
        """Test that the component can create a model with a real API key."""
        component = component_class(**default_kwargs)
        component.api_key = openai_api_key
        component.temperature = 0.1
        component.stream = False

        model = component.build_model()
        assert isinstance(model, ChatOpenAI)

    async def test_anthropic_live_api(self, component_class, anthropic_api_key):
        """Test that the component can create a model with a real API key."""
        component = component_class(
            model=[
                {
                    "name": ANTHROPIC_MODELS[0],
                    "provider": "Anthropic",
                    "metadata": {
                        "context_length": 200000,
                        "model_class": "ChatAnthropic",
                        "model_name_param": "model",
                        "api_key_param": "api_key",
                    },
                }
            ],
            api_key=anthropic_api_key,
            temperature=0.1,
            stream=False,
        )

        model = component.build_model()
        assert isinstance(model, ChatAnthropic)

    async def test_google_live_api(self, component_class, google_api_key):
        """Test that the component can create a model with a real API key."""
        component = component_class(
            model=[
                {
                    "name": GOOGLE_GENERATIVE_AI_MODELS[0],
                    "provider": "Google",
                    "metadata": {
                        "context_length": 32768,
                        "model_class": "ChatGoogleGenerativeAIFixed",
                        "model_name_param": "model",
                        "api_key_param": "google_api_key",
                    },
                }
            ],
            api_key=google_api_key,
            temperature=0.1,
            stream=False,
        )

        model = component.build_model()
        assert isinstance(model, ChatGoogleGenerativeAI)
