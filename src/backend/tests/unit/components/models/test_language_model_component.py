import os

import pytest
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from lfx.base.models.anthropic_constants import ANTHROPIC_MODELS
from lfx.base.models.google_generative_ai_constants import GOOGLE_GENERATIVE_AI_MODELS
from lfx.base.models.openai_constants import OPENAI_CHAT_MODEL_NAMES, OPENAI_REASONING_MODEL_NAMES
from lfx.components.models.language_model import LanguageModelComponent
from tests.base import ComponentTestBaseWithoutClient


class TestLanguageModelComponent(ComponentTestBaseWithoutClient):
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

    async def test_update_build_config_openai(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {
            "model_name": {"options": [], "value": ""},
            "api_key": {"display_name": "API Key"},
        }
        updated_config = component.update_build_config(build_config, "OpenAI", "provider")
        assert updated_config["model_name"]["options"] == OPENAI_CHAT_MODEL_NAMES + OPENAI_REASONING_MODEL_NAMES
        assert updated_config["model_name"]["value"] == OPENAI_CHAT_MODEL_NAMES[0]
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

    async def test_update_build_config_google(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        build_config = {
            "model_name": {"options": [], "value": ""},
            "api_key": {"display_name": "API Key"},
        }
        updated_config = component.update_build_config(build_config, "Google", "provider")
        assert updated_config["model_name"]["options"] == GOOGLE_GENERATIVE_AI_MODELS
        assert updated_config["model_name"]["value"] == GOOGLE_GENERATIVE_AI_MODELS[0]
        assert updated_config["api_key"]["display_name"] == "Google API Key"

    async def test_openai_model_creation(self, component_class, default_kwargs):
        """Test that the component returns an instance of ChatOpenAI for OpenAI provider."""
        component = component_class(**default_kwargs)
        component.provider = "OpenAI"
        component.model_name = "gpt-3.5-turbo"
        component.api_key = "sk-test-key"  # Use a fake but correctly formatted key
        component.temperature = 0.5
        component.stream = False

        # The API key will be invalid, but we should still get a ChatOpenAI instance
        model = component.build_model()
        assert isinstance(model, ChatOpenAI)
        assert model.model_name == "gpt-3.5-turbo"
        assert model.temperature == 0.5
        assert model.streaming is False
        # API key is stored as a SecretStr object, so we can't directly compare values

    async def test_anthropic_model_creation(self, component_class, default_kwargs):
        """Test that the component returns an instance of ChatAnthropic for Anthropic provider."""
        component = component_class(**default_kwargs)
        component.provider = "Anthropic"
        component.model_name = ANTHROPIC_MODELS[0]
        component.api_key = "sk-ant-test-key"  # Use a fake but plausible key
        component.temperature = 0.7
        component.stream = False

        # The API key will be invalid, but we should still get a ChatAnthropic instance
        model = component.build_model()
        assert isinstance(model, ChatAnthropic)
        assert model.model == ANTHROPIC_MODELS[0]
        assert model.temperature == 0.7
        assert model.streaming is False
        # API key is stored as a SecretStr object, so we can't directly compare values

    async def test_google_model_creation(self, component_class, default_kwargs):
        """Test that the component returns an instance of ChatGoogleGenerativeAI for Google provider."""
        component = component_class(**default_kwargs)
        component.provider = "Google"
        component.model_name = GOOGLE_GENERATIVE_AI_MODELS[0]
        component.api_key = "google-test-key"  # Use a fake but plausible key
        component.temperature = 0.7
        component.stream = False

        # The API key will be invalid, but we should still get a ChatGoogleGenerativeAI instance
        model = component.build_model()
        assert isinstance(model, ChatGoogleGenerativeAI)
        # Google model automatically prepends "models/" to the model name
        assert model.model == f"models/{GOOGLE_GENERATIVE_AI_MODELS[0]}"
        assert model.temperature == 0.7
        # Google model uses 'stream' instead of 'streaming'
        # Skip this check for Google model since it has a different interface
        # API key is stored as a SecretStr object, so we can't directly compare values

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

    async def test_build_model_google_missing_api_key(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.provider = "Google"
        component.api_key = None

        with pytest.raises(ValueError, match="Google API key is required when using Google provider"):
            component.build_model()

    async def test_build_model_unknown_provider(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        component.provider = "Unknown"

        with pytest.raises(ValueError, match="Unknown provider: Unknown"):
            component.build_model()

    async def test_openai_live_api(self, component_class, default_kwargs, openai_api_key):
        """Test that the component can create a model with a real API key."""
        component = component_class(**default_kwargs)
        component.provider = "OpenAI"
        component.model_name = "gpt-3.5-turbo"
        component.api_key = openai_api_key
        component.temperature = 0.1
        component.stream = False

        model = component.build_model()
        assert isinstance(model, ChatOpenAI)
        # We could attempt a simple call here, but that would increase test time
        # and might fail due to network issues, so we'll just verify the instance

    async def test_anthropic_live_api(self, component_class, default_kwargs, anthropic_api_key):
        """Test that the component can create a model with a real API key."""
        component = component_class(**default_kwargs)
        component.provider = "Anthropic"
        component.model_name = ANTHROPIC_MODELS[0]
        component.api_key = anthropic_api_key
        component.temperature = 0.1
        component.stream = False

        model = component.build_model()
        assert isinstance(model, ChatAnthropic)
        # We could attempt a simple call here, but that would increase test time
        # and might fail due to network issues, so we'll just verify the instance

    async def test_google_live_api(self, component_class, default_kwargs, google_api_key):
        """Test that the component can create a model with a real API key."""
        component = component_class(**default_kwargs)
        component.provider = "Google"
        component.model_name = GOOGLE_GENERATIVE_AI_MODELS[0]
        component.api_key = google_api_key
        component.temperature = 0.1
        component.stream = False

        model = component.build_model()
        assert isinstance(model, ChatGoogleGenerativeAI)
        # We could attempt a simple call here, but that would increase test time
        # and might fail due to network issues, so we'll just verify the instance
