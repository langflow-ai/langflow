import pytest
from lfx.base.models.language_model_mixin import (
    DEFAULT_OLLAMA_URL,
    IBM_WATSONX_DEFAULT_MODELS,
    IBM_WATSONX_URLS,
    LLM_PROVIDERS,
    LLM_PROVIDERS_METADATA,
    LanguageModelMixin,
)
from lfx.base.models.openai_constants import OPENAI_CHAT_MODEL_NAMES, OPENAI_REASONING_MODEL_NAMES
from lfx.custom.custom_component.component import Component
from lfx.schema.dotdict import dotdict


class TestLanguageModelMixin:
    """Tests for LanguageModelMixin."""

    def test_get_llm_inputs_default(self):
        """Test that get_llm_inputs returns the expected default inputs."""
        inputs = LanguageModelMixin.get_llm_inputs()

        input_names = [i.name for i in inputs]
        assert "provider" in input_names
        assert "model_name" in input_names
        assert "api_key" in input_names
        assert "base_url_ibm_watsonx" in input_names
        assert "project_id" in input_names
        assert "ollama_base_url" in input_names
        assert "stream" in input_names
        assert "temperature" in input_names

        # By default, input_value and system_message are NOT included
        assert "input_value" not in input_names
        assert "system_message" not in input_names

    def test_get_llm_inputs_with_optional_fields(self):
        """Test that get_llm_inputs can include optional fields."""
        inputs = LanguageModelMixin.get_llm_inputs(
            include_input_value=True,
            include_system_message=True,
        )

        input_names = [i.name for i in inputs]
        assert "input_value" in input_names
        assert "system_message" in input_names

    def test_get_llm_inputs_without_stream_and_temperature(self):
        """Test that get_llm_inputs can exclude stream and temperature."""
        inputs = LanguageModelMixin.get_llm_inputs(
            include_stream=False,
            include_temperature=False,
        )

        input_names = [i.name for i in inputs]
        assert "stream" not in input_names
        assert "temperature" not in input_names

    def test_provider_dropdown_options(self):
        """Test that the provider dropdown has the expected options."""
        inputs = LanguageModelMixin.get_llm_inputs()
        provider_input = next(i for i in inputs if i.name == "provider")

        assert provider_input.options == LLM_PROVIDERS
        assert provider_input.value == "OpenAI"
        assert provider_input.options_metadata == LLM_PROVIDERS_METADATA

    def test_model_name_dropdown_default_options(self):
        """Test that model_name dropdown has OpenAI models by default."""
        inputs = LanguageModelMixin.get_llm_inputs()
        model_input = next(i for i in inputs if i.name == "model_name")

        expected_models = OPENAI_CHAT_MODEL_NAMES + OPENAI_REASONING_MODEL_NAMES
        assert model_input.options == expected_models
        assert model_input.value == OPENAI_CHAT_MODEL_NAMES[0]

    def test_ibm_watsonx_fields_hidden_by_default(self):
        """Test that IBM-specific fields are hidden by default."""
        inputs = LanguageModelMixin.get_llm_inputs()

        base_url_input = next(i for i in inputs if i.name == "base_url_ibm_watsonx")
        project_id_input = next(i for i in inputs if i.name == "project_id")

        assert base_url_input.show is False
        assert project_id_input.show is False
        assert base_url_input.options == IBM_WATSONX_URLS

    def test_ollama_url_hidden_by_default(self):
        """Test that Ollama URL field is hidden by default."""
        inputs = LanguageModelMixin.get_llm_inputs()
        ollama_input = next(i for i in inputs if i.name == "ollama_base_url")

        assert ollama_input.show is False
        assert ollama_input.value == DEFAULT_OLLAMA_URL


def _has_langchain_openai():
    try:
        import langchain_openai  # noqa: F401
    except ImportError:
        return False
    else:
        return True


def _has_langchain_anthropic():
    try:
        import langchain_anthropic  # noqa: F401
    except ImportError:
        return False
    else:
        return True


def _has_langchain_google():
    try:
        import langchain_google_genai  # noqa: F401
    except ImportError:
        return False
    else:
        return True


def _has_langchain_ibm():
    try:
        import langchain_ibm  # noqa: F401
    except ImportError:
        return False
    else:
        return True


def _has_langchain_ollama():
    try:
        import langchain_ollama  # noqa: F401
    except ImportError:
        return False
    else:
        return True


class TestLanguageModelMixinWithComponent:
    """Tests for LanguageModelMixin when used with a Component."""

    def test_mixin_with_component(self):
        """Test that the mixin can be used with Component."""

        class TestComponent(LanguageModelMixin, Component):
            inputs = [
                *LanguageModelMixin.get_llm_inputs(),
            ]

        comp = TestComponent()
        assert hasattr(comp, "build_llm")
        assert hasattr(comp, "update_llm_provider_config")
        assert len(comp.inputs) >= 8  # At least the LLM inputs

    @pytest.mark.skipif(not _has_langchain_openai(), reason="langchain_openai not installed")
    def test_build_llm_missing_api_key_openai(self):
        """Test that build_llm raises error when OpenAI API key is missing."""

        class TestComponent(LanguageModelMixin, Component):
            inputs = [*LanguageModelMixin.get_llm_inputs()]

        comp = TestComponent()
        comp.provider = "OpenAI"
        comp.model_name = "gpt-4"
        comp.api_key = None  # pragma: allowlist secret

        with pytest.raises(ValueError, match="OpenAI API key is required"):
            comp.build_llm()

    @pytest.mark.skipif(not _has_langchain_anthropic(), reason="langchain_anthropic not installed")
    def test_build_llm_missing_api_key_anthropic(self):
        """Test that build_llm raises error when Anthropic API key is missing."""

        class TestComponent(LanguageModelMixin, Component):
            inputs = [*LanguageModelMixin.get_llm_inputs()]

        comp = TestComponent()
        comp.provider = "Anthropic"
        comp.model_name = "claude-3-opus-20240229"
        comp.api_key = None  # pragma: allowlist secret

        with pytest.raises(ValueError, match="Anthropic API key is required"):
            comp.build_llm()

    @pytest.mark.skipif(not _has_langchain_google(), reason="langchain_google_genai not installed")
    def test_build_llm_missing_api_key_google(self):
        """Test that build_llm raises error when Google API key is missing."""

        class TestComponent(LanguageModelMixin, Component):
            inputs = [*LanguageModelMixin.get_llm_inputs()]

        comp = TestComponent()
        comp.provider = "Google"
        comp.model_name = "gemini-pro"
        comp.api_key = None  # pragma: allowlist secret

        with pytest.raises(ValueError, match="Google API key is required"):
            comp.build_llm()

    @pytest.mark.skipif(not _has_langchain_ibm(), reason="langchain_ibm not installed")
    def test_build_llm_ibm_missing_fields(self):
        """Test that build_llm raises errors when IBM fields are missing."""

        class TestComponent(LanguageModelMixin, Component):
            inputs = [*LanguageModelMixin.get_llm_inputs()]

        comp = TestComponent()
        comp.provider = "IBM watsonx.ai"
        comp.model_name = "ibm/granite-13b-instruct-v2"
        comp.api_key = None  # pragma: allowlist secret

        with pytest.raises(ValueError, match="IBM API key is required"):
            comp.build_llm()

        comp.api_key = "test-key"  # pragma: allowlist secret
        comp.base_url_ibm_watsonx = None

        with pytest.raises(ValueError, match="IBM watsonx API Endpoint is required"):
            comp.build_llm()

        comp.base_url_ibm_watsonx = IBM_WATSONX_URLS[0]
        comp.project_id = None

        with pytest.raises(ValueError, match="IBM watsonx Project ID is required"):
            comp.build_llm()

    @pytest.mark.skipif(not _has_langchain_ollama(), reason="langchain_ollama not installed")
    def test_build_llm_ollama_missing_fields(self):
        """Test that build_llm raises errors when Ollama fields are missing."""

        class TestComponent(LanguageModelMixin, Component):
            inputs = [*LanguageModelMixin.get_llm_inputs()]

        comp = TestComponent()
        comp.provider = "Ollama"
        comp.ollama_base_url = None
        comp.model_name = "llama2"

        with pytest.raises(ValueError, match="Ollama API URL is required"):
            comp.build_llm()

        comp.ollama_base_url = "http://localhost:11434"
        comp.model_name = None

        with pytest.raises(ValueError, match="Model name is required"):
            comp.build_llm()

    def test_build_llm_unknown_provider(self):
        """Test that build_llm raises error for unknown provider."""

        class TestComponent(LanguageModelMixin, Component):
            inputs = [*LanguageModelMixin.get_llm_inputs()]

        comp = TestComponent()
        comp.provider = "UnknownProvider"

        with pytest.raises(ValueError, match="Unknown provider: UnknownProvider"):
            comp.build_llm()


class TestUpdateLlmProviderConfig:
    """Tests for update_llm_provider_config method."""

    @pytest.fixture
    def component_with_mixin(self):
        """Create a component with the mixin for testing."""

        class TestComponent(LanguageModelMixin, Component):
            inputs = [
                *LanguageModelMixin.get_llm_inputs(
                    include_system_message=True,
                ),
            ]

        return TestComponent()

    @pytest.fixture
    def base_build_config(self):
        """Create a base build config for testing."""
        return dotdict(
            {
                "provider": {"value": "OpenAI", "options": LLM_PROVIDERS},
                "model_name": {"value": "", "options": []},
                "api_key": {"display_name": "API Key", "show": True},
                "base_url_ibm_watsonx": {"show": False},
                "project_id": {"show": False},
                "ollama_base_url": {"show": False, "value": DEFAULT_OLLAMA_URL},
                "system_message": {"show": True},
            }
        )

    @pytest.mark.asyncio
    async def test_switch_to_openai(self, component_with_mixin, base_build_config):
        """Test switching provider to OpenAI."""
        result = await component_with_mixin.update_llm_provider_config(base_build_config, "OpenAI", "provider")

        expected_models = OPENAI_CHAT_MODEL_NAMES + OPENAI_REASONING_MODEL_NAMES
        assert result["model_name"]["options"] == expected_models
        assert result["model_name"]["value"] == OPENAI_CHAT_MODEL_NAMES[0]
        assert result["api_key"]["display_name"] == "OpenAI API Key"
        assert result["api_key"]["show"] is True
        assert result["base_url_ibm_watsonx"]["show"] is False
        assert result["project_id"]["show"] is False
        assert result["ollama_base_url"]["show"] is False

    @pytest.mark.asyncio
    async def test_switch_to_ibm(self, component_with_mixin, base_build_config):
        """Test switching provider to IBM watsonx.ai."""
        result = await component_with_mixin.update_llm_provider_config(base_build_config, "IBM watsonx.ai", "provider")

        assert result["model_name"]["options"] == IBM_WATSONX_DEFAULT_MODELS
        assert result["model_name"]["value"] == IBM_WATSONX_DEFAULT_MODELS[0]
        assert result["api_key"]["display_name"] == "IBM API Key"
        assert result["api_key"]["show"] is True
        assert result["base_url_ibm_watsonx"]["show"] is True
        assert result["project_id"]["show"] is True
        assert result["ollama_base_url"]["show"] is False

    @pytest.mark.asyncio
    async def test_switch_to_ollama(self, component_with_mixin, base_build_config):
        """Test switching provider to Ollama (with invalid URL - no server)."""
        result = await component_with_mixin.update_llm_provider_config(base_build_config, "Ollama", "provider")

        # Without a running Ollama server, options should be empty
        assert result["api_key"]["show"] is False
        assert result["base_url_ibm_watsonx"]["show"] is False
        assert result["project_id"]["show"] is False
        assert result["ollama_base_url"]["show"] is True

    @pytest.mark.asyncio
    async def test_o1_model_hides_system_message(self, component_with_mixin, base_build_config):
        """Test that selecting an o1 model hides the system_message field."""
        component_with_mixin.provider = "OpenAI"

        result = await component_with_mixin.update_llm_provider_config(base_build_config, "o1-preview", "model_name")

        assert result["system_message"]["show"] is False

    @pytest.mark.asyncio
    async def test_non_o1_model_shows_system_message(self, component_with_mixin, base_build_config):
        """Test that selecting a non-o1 model shows the system_message field."""
        component_with_mixin.provider = "OpenAI"
        base_build_config["system_message"]["show"] = False

        result = await component_with_mixin.update_llm_provider_config(base_build_config, "gpt-4", "model_name")

        assert result["system_message"]["show"] is True


class TestLanguageModelComponentIntegration:
    """Integration tests for LanguageModelComponent using the mixin."""

    def test_language_model_component_uses_mixin(self):
        """Test that LanguageModelComponent properly uses the mixin."""
        from lfx.components.models_and_agents.language_model import LanguageModelComponent

        comp = LanguageModelComponent()

        # Check that it has mixin methods
        assert hasattr(comp, "build_llm")
        assert hasattr(comp, "update_llm_provider_config")

        # Check that build_model delegates to build_llm
        assert comp.build_model == comp.build_llm or callable(comp.build_model)

        # Check inputs
        input_names = [i.name for i in comp.inputs]
        assert "provider" in input_names
        assert "model_name" in input_names
        assert "input_value" in input_names
        assert "system_message" in input_names

    def test_language_model_component_input_order(self):
        """Test that LanguageModelComponent has inputs in expected order."""
        from lfx.components.models_and_agents.language_model import LanguageModelComponent

        comp = LanguageModelComponent()
        input_names = [i.name for i in comp.inputs]

        # Provider should come first
        assert input_names[0] == "provider"
        # Model name should come second
        assert input_names[1] == "model_name"
