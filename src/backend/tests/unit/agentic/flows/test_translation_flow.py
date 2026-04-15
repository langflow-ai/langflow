"""Tests for TranslationFlow.

Tests the graph construction and model configuration for the translation flow.
"""

from unittest.mock import MagicMock, patch

from langflow.agentic.flows.translation_flow import (
    TRANSLATION_PROMPT,
    _build_model_config,
    get_graph,
)


class TestBuildModelConfig:
    """Tests for _build_model_config function."""

    def test_should_build_config_for_openai(self):
        """Should build correct config for OpenAI provider."""
        result = _build_model_config("OpenAI", "gpt-4o-mini")

        assert len(result) == 1
        config = result[0]
        assert config["provider"] == "OpenAI"
        assert config["name"] == "gpt-4o-mini"
        assert config["icon"] == "OpenAI"
        assert config["metadata"]["model_class"] == "ChatOpenAI"
        assert config["metadata"]["model_name_param"] == "model"
        assert config["metadata"]["api_key_param"] == "api_key"

    def test_should_build_config_for_anthropic(self):
        """Should build correct config for Anthropic provider."""
        result = _build_model_config("Anthropic", "claude-3-haiku")

        config = result[0]
        assert config["provider"] == "Anthropic"
        assert config["name"] == "claude-3-haiku"
        assert config["metadata"]["model_class"] == "ChatAnthropic"

    def test_should_build_config_for_google(self):
        """Should build correct config for Google Generative AI."""
        result = _build_model_config("Google Generative AI", "gemini-flash")

        config = result[0]
        assert config["metadata"]["model_class"] == "ChatGoogleGenerativeAI"

    def test_should_build_config_for_groq(self):
        """Should build correct config for Groq."""
        result = _build_model_config("Groq", "mixtral-8x7b")

        config = result[0]
        assert config["metadata"]["model_class"] == "ChatGroq"

    def test_should_build_config_for_azure_openai(self):
        """Should build correct config for Azure OpenAI."""
        result = _build_model_config("Azure OpenAI", "gpt-35-turbo")

        config = result[0]
        assert config["metadata"]["model_class"] == "AzureChatOpenAI"

    def test_should_default_to_openai_for_unknown_provider(self):
        """Should default to ChatOpenAI for unknown provider."""
        result = _build_model_config("CustomProvider", "custom-model")

        config = result[0]
        assert config["metadata"]["model_class"] == "ChatOpenAI"

    def test_should_include_context_length(self):
        """Should include context_length in metadata."""
        result = _build_model_config("OpenAI", "gpt-4")

        config = result[0]
        assert config["metadata"]["context_length"] == 128000


class TestGetGraph:
    """Tests for get_graph function."""

    def test_should_create_graph_with_default_provider(self):
        """Should create graph with OpenAI as default provider."""
        with (
            patch("langflow.agentic.flows.translation_flow.ChatInput"),
            patch("langflow.agentic.flows.translation_flow.ChatOutput"),
            patch("langflow.agentic.flows.translation_flow.LanguageModelComponent") as mock_llm,
            patch("langflow.agentic.flows.translation_flow.Graph"),
        ):
            mock_llm_instance = MagicMock()
            mock_llm.return_value = mock_llm_instance

            get_graph()

            call_args = mock_llm_instance.set_input_value.call_args
            model_config = call_args[0][1]
            assert model_config[0]["provider"] == "OpenAI"
            assert model_config[0]["name"] == "gpt-4o-mini"

    def test_should_use_provided_provider_and_model(self):
        """Should use provided provider and model_name."""
        with (
            patch("langflow.agentic.flows.translation_flow.ChatInput"),
            patch("langflow.agentic.flows.translation_flow.ChatOutput"),
            patch("langflow.agentic.flows.translation_flow.LanguageModelComponent") as mock_llm,
            patch("langflow.agentic.flows.translation_flow.Graph"),
        ):
            mock_llm_instance = MagicMock()
            mock_llm.return_value = mock_llm_instance

            get_graph(provider="Anthropic", model_name="claude-3-haiku")

            call_args = mock_llm_instance.set_input_value.call_args
            model_config = call_args[0][1]
            assert model_config[0]["provider"] == "Anthropic"
            assert model_config[0]["name"] == "claude-3-haiku"

    def test_should_include_api_key_when_provided(self):
        """Should include api_key in LLM config when api_key_var is provided."""
        with (
            patch("langflow.agentic.flows.translation_flow.ChatInput"),
            patch("langflow.agentic.flows.translation_flow.ChatOutput"),
            patch("langflow.agentic.flows.translation_flow.LanguageModelComponent") as mock_llm,
            patch("langflow.agentic.flows.translation_flow.Graph"),
        ):
            mock_llm_instance = MagicMock()
            mock_llm.return_value = mock_llm_instance

            get_graph(api_key_var="OPENAI_API_KEY")

            set_call = mock_llm_instance.set.call_args
            assert "api_key" in set_call[1]
            assert set_call[1]["api_key"] == "OPENAI_API_KEY"

    def test_should_not_include_api_key_when_not_provided(self):
        """Should not include api_key when api_key_var is None."""
        with (
            patch("langflow.agentic.flows.translation_flow.ChatInput"),
            patch("langflow.agentic.flows.translation_flow.ChatOutput"),
            patch("langflow.agentic.flows.translation_flow.LanguageModelComponent") as mock_llm,
            patch("langflow.agentic.flows.translation_flow.Graph"),
        ):
            mock_llm_instance = MagicMock()
            mock_llm.return_value = mock_llm_instance

            get_graph()

            set_call = mock_llm_instance.set.call_args
            assert "api_key" not in set_call[1]

    def test_should_set_low_temperature(self):
        """Should set low temperature for consistent JSON output."""
        with (
            patch("langflow.agentic.flows.translation_flow.ChatInput"),
            patch("langflow.agentic.flows.translation_flow.ChatOutput"),
            patch("langflow.agentic.flows.translation_flow.LanguageModelComponent") as mock_llm,
            patch("langflow.agentic.flows.translation_flow.Graph"),
        ):
            mock_llm_instance = MagicMock()
            mock_llm.return_value = mock_llm_instance

            get_graph()

            set_call = mock_llm_instance.set.call_args
            assert set_call[1]["temperature"] == 0.1

    def test_should_set_system_message(self):
        """Should set system_message to TRANSLATION_PROMPT."""
        with (
            patch("langflow.agentic.flows.translation_flow.ChatInput"),
            patch("langflow.agentic.flows.translation_flow.ChatOutput"),
            patch("langflow.agentic.flows.translation_flow.LanguageModelComponent") as mock_llm,
            patch("langflow.agentic.flows.translation_flow.Graph"),
        ):
            mock_llm_instance = MagicMock()
            mock_llm.return_value = mock_llm_instance

            get_graph()

            set_call = mock_llm_instance.set.call_args
            assert set_call[1]["system_message"] == TRANSLATION_PROMPT

    def test_should_configure_chat_input(self):
        """Should configure ChatInput with correct settings."""
        with (
            patch("langflow.agentic.flows.translation_flow.ChatInput") as mock_chat_input,
            patch("langflow.agentic.flows.translation_flow.ChatOutput"),
            patch("langflow.agentic.flows.translation_flow.LanguageModelComponent"),
            patch("langflow.agentic.flows.translation_flow.Graph"),
        ):
            mock_input_instance = MagicMock()
            mock_chat_input.return_value = mock_input_instance

            get_graph()

            mock_input_instance.set.assert_called_once()
            set_call = mock_input_instance.set.call_args
            assert set_call[1]["sender"] == "User"
            assert set_call[1]["should_store_message"] is True

    def test_should_configure_chat_output(self):
        """Should configure ChatOutput with correct settings."""
        with (
            patch("langflow.agentic.flows.translation_flow.ChatInput"),
            patch("langflow.agentic.flows.translation_flow.ChatOutput") as mock_chat_output,
            patch("langflow.agentic.flows.translation_flow.LanguageModelComponent"),
            patch("langflow.agentic.flows.translation_flow.Graph"),
        ):
            mock_output_instance = MagicMock()
            mock_chat_output.return_value = mock_output_instance

            get_graph()

            mock_output_instance.set.assert_called_once()
            set_call = mock_output_instance.set.call_args
            assert set_call[1]["sender"] == "Machine"
            assert set_call[1]["sender_name"] == "AI"
            assert set_call[1]["clean_data"] is True

    def test_should_create_graph_with_start_and_end(self):
        """Should create Graph with chat_input as start and chat_output as end."""
        with (
            patch("langflow.agentic.flows.translation_flow.ChatInput") as mock_chat_input,
            patch("langflow.agentic.flows.translation_flow.ChatOutput") as mock_chat_output,
            patch("langflow.agentic.flows.translation_flow.LanguageModelComponent"),
            patch("langflow.agentic.flows.translation_flow.Graph") as mock_graph_class,
        ):
            mock_input = MagicMock()
            mock_output = MagicMock()
            mock_chat_input.return_value = mock_input
            mock_chat_output.return_value = mock_output

            get_graph()

            mock_graph_class.assert_called_once_with(start=mock_input, end=mock_output)


class TestTranslationPrompt:
    """Tests for TRANSLATION_PROMPT constant."""

    def test_should_contain_translation_instructions(self):
        """Should contain instructions for translation."""
        assert "translation" in TRANSLATION_PROMPT.lower()
        assert "english" in TRANSLATION_PROMPT.lower()

    def test_should_contain_intent_classification_instructions(self):
        """Should contain instructions for intent classification."""
        assert "intent" in TRANSLATION_PROMPT.lower()
        assert "generate_component" in TRANSLATION_PROMPT
        assert "question" in TRANSLATION_PROMPT

    def test_should_specify_json_output_format(self):
        """Should specify JSON output format."""
        assert "json" in TRANSLATION_PROMPT.lower()
        assert "translation" in TRANSLATION_PROMPT
        assert "intent" in TRANSLATION_PROMPT

    def test_should_contain_examples(self):
        """Should contain classification examples."""
        # Should have examples showing both intents
        assert "generate_component" in TRANSLATION_PROMPT
        assert "question" in TRANSLATION_PROMPT

    def test_should_distinguish_how_to_from_create(self):
        """Should explain difference between 'how to create' and 'create'."""
        # The prompt should explain that "how to create" is a question
        # while "create a component that" is a generation request
        prompt_lower = TRANSLATION_PROMPT.lower()
        assert "how" in prompt_lower
        assert "create" in prompt_lower or "build" in prompt_lower or "generate" in prompt_lower
