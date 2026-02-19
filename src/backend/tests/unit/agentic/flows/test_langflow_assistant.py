"""Tests for LangflowAssistant flow.

Tests the graph construction and model configuration for the assistant flow.
"""

from unittest.mock import MagicMock, patch

from langflow.agentic.flows.langflow_assistant import (
    ASSISTANT_PROMPT,
    _build_model_config,
    get_graph,
)


class TestBuildModelConfig:
    """Tests for _build_model_config function."""

    def test_should_build_config_for_openai(self):
        """Should build correct config for OpenAI provider."""
        result = _build_model_config("OpenAI", "gpt-4o")

        assert len(result) == 1
        config = result[0]
        assert config["provider"] == "OpenAI"
        assert config["name"] == "gpt-4o"
        assert config["icon"] == "OpenAI"
        assert config["metadata"]["model_class"] == "ChatOpenAI"
        assert config["metadata"]["model_name_param"] == "model"
        assert config["metadata"]["api_key_param"] == "api_key"

    def test_should_build_config_for_anthropic(self):
        """Should build correct config for Anthropic provider."""
        result = _build_model_config("Anthropic", "claude-sonnet-4-5-20250929")

        config = result[0]
        assert config["provider"] == "Anthropic"
        assert config["name"] == "claude-sonnet-4-5-20250929"
        assert config["metadata"]["model_class"] == "ChatAnthropic"

    def test_should_build_config_for_google(self):
        """Should build correct config for Google Generative AI provider."""
        result = _build_model_config("Google Generative AI", "gemini-pro")

        config = result[0]
        assert config["provider"] == "Google Generative AI"
        assert config["metadata"]["model_class"] == "ChatGoogleGenerativeAI"

    def test_should_build_config_for_groq(self):
        """Should build correct config for Groq provider."""
        result = _build_model_config("Groq", "llama3-70b")

        config = result[0]
        assert config["provider"] == "Groq"
        assert config["metadata"]["model_class"] == "ChatGroq"

    def test_should_build_config_for_azure_openai(self):
        """Should build correct config for Azure OpenAI provider."""
        result = _build_model_config("Azure OpenAI", "gpt-4")

        config = result[0]
        assert config["provider"] == "Azure OpenAI"
        assert config["metadata"]["model_class"] == "AzureChatOpenAI"

    def test_should_default_to_anthropic_for_unknown_provider(self):
        """Should default to ChatAnthropic for unknown provider."""
        result = _build_model_config("UnknownProvider", "model-x")

        config = result[0]
        assert config["provider"] == "UnknownProvider"
        assert config["metadata"]["model_class"] == "ChatAnthropic"

    def test_should_set_context_length(self):
        """Should set context_length in metadata."""
        result = _build_model_config("OpenAI", "gpt-4")

        config = result[0]
        assert config["metadata"]["context_length"] == 128000


class TestGetGraph:
    """Tests for get_graph function."""

    def test_should_create_graph_with_default_provider(self):
        """Should create graph with Anthropic as default provider."""
        with (
            patch("langflow.agentic.flows.langflow_assistant.ChatInput") as mock_chat_input,
            patch("langflow.agentic.flows.langflow_assistant.ChatOutput") as mock_chat_output,
            patch("langflow.agentic.flows.langflow_assistant.LanguageModelComponent") as mock_llm,
            patch("langflow.agentic.flows.langflow_assistant.Graph"),
        ):
            mock_chat_input_instance = MagicMock()
            mock_chat_input.return_value = mock_chat_input_instance

            mock_llm_instance = MagicMock()
            mock_llm.return_value = mock_llm_instance

            mock_chat_output_instance = MagicMock()
            mock_chat_output.return_value = mock_chat_output_instance

            get_graph()

            # Verify LLM model config was set with Anthropic defaults
            mock_llm_instance.set_input_value.assert_called_once()
            call_args = mock_llm_instance.set_input_value.call_args
            assert call_args[0][0] == "model"
            model_config = call_args[0][1]
            assert model_config[0]["provider"] == "Anthropic"
            assert model_config[0]["name"] == "claude-sonnet-4-5-20250929"

    def test_should_use_provided_provider_and_model(self):
        """Should use provided provider and model_name."""
        with (
            patch("langflow.agentic.flows.langflow_assistant.ChatInput"),
            patch("langflow.agentic.flows.langflow_assistant.ChatOutput"),
            patch("langflow.agentic.flows.langflow_assistant.LanguageModelComponent") as mock_llm,
            patch("langflow.agentic.flows.langflow_assistant.Graph"),
        ):
            mock_llm_instance = MagicMock()
            mock_llm.return_value = mock_llm_instance

            get_graph(provider="OpenAI", model_name="gpt-4o")

            call_args = mock_llm_instance.set_input_value.call_args
            model_config = call_args[0][1]
            assert model_config[0]["provider"] == "OpenAI"
            assert model_config[0]["name"] == "gpt-4o"

    def test_should_include_api_key_when_provided(self):
        """Should include api_key in LLM config when api_key_var is provided."""
        with (
            patch("langflow.agentic.flows.langflow_assistant.ChatInput"),
            patch("langflow.agentic.flows.langflow_assistant.ChatOutput"),
            patch("langflow.agentic.flows.langflow_assistant.LanguageModelComponent") as mock_llm,
            patch("langflow.agentic.flows.langflow_assistant.Graph"),
        ):
            mock_llm_instance = MagicMock()
            mock_llm.return_value = mock_llm_instance

            get_graph(api_key_var="MY_API_KEY")

            # Check that set was called with api_key in config
            set_call = mock_llm_instance.set.call_args
            assert "api_key" in set_call[1]
            assert set_call[1]["api_key"] == "MY_API_KEY"

    def test_should_not_include_api_key_when_not_provided(self):
        """Should not include api_key in LLM config when api_key_var is None."""
        with (
            patch("langflow.agentic.flows.langflow_assistant.ChatInput"),
            patch("langflow.agentic.flows.langflow_assistant.ChatOutput"),
            patch("langflow.agentic.flows.langflow_assistant.LanguageModelComponent") as mock_llm,
            patch("langflow.agentic.flows.langflow_assistant.Graph"),
        ):
            mock_llm_instance = MagicMock()
            mock_llm.return_value = mock_llm_instance

            get_graph()

            set_call = mock_llm_instance.set.call_args
            assert "api_key" not in set_call[1]

    def test_should_enable_streaming(self):
        """Should enable streaming in LLM configuration."""
        with (
            patch("langflow.agentic.flows.langflow_assistant.ChatInput"),
            patch("langflow.agentic.flows.langflow_assistant.ChatOutput"),
            patch("langflow.agentic.flows.langflow_assistant.LanguageModelComponent") as mock_llm,
            patch("langflow.agentic.flows.langflow_assistant.Graph"),
        ):
            mock_llm_instance = MagicMock()
            mock_llm.return_value = mock_llm_instance

            get_graph()

            set_call = mock_llm_instance.set.call_args
            assert set_call[1]["stream"] is True

    def test_should_set_system_message(self):
        """Should set system_message to ASSISTANT_PROMPT."""
        with (
            patch("langflow.agentic.flows.langflow_assistant.ChatInput"),
            patch("langflow.agentic.flows.langflow_assistant.ChatOutput"),
            patch("langflow.agentic.flows.langflow_assistant.LanguageModelComponent") as mock_llm,
            patch("langflow.agentic.flows.langflow_assistant.Graph"),
        ):
            mock_llm_instance = MagicMock()
            mock_llm.return_value = mock_llm_instance

            get_graph()

            set_call = mock_llm_instance.set.call_args
            assert set_call[1]["system_message"] == ASSISTANT_PROMPT

    def test_should_configure_chat_input(self):
        """Should configure ChatInput with correct settings."""
        with (
            patch("langflow.agentic.flows.langflow_assistant.ChatInput") as mock_chat_input,
            patch("langflow.agentic.flows.langflow_assistant.ChatOutput"),
            patch("langflow.agentic.flows.langflow_assistant.LanguageModelComponent"),
            patch("langflow.agentic.flows.langflow_assistant.Graph"),
        ):
            mock_input_instance = MagicMock()
            mock_chat_input.return_value = mock_input_instance

            get_graph()

            mock_input_instance.set.assert_called_once()
            set_call = mock_input_instance.set.call_args
            assert set_call[1]["sender"] == "User"
            assert set_call[1]["sender_name"] == "User"
            assert set_call[1]["should_store_message"] is True

    def test_should_configure_chat_output(self):
        """Should configure ChatOutput with correct settings."""
        with (
            patch("langflow.agentic.flows.langflow_assistant.ChatInput"),
            patch("langflow.agentic.flows.langflow_assistant.ChatOutput") as mock_chat_output,
            patch("langflow.agentic.flows.langflow_assistant.LanguageModelComponent"),
            patch("langflow.agentic.flows.langflow_assistant.Graph"),
        ):
            mock_output_instance = MagicMock()
            mock_chat_output.return_value = mock_output_instance

            get_graph()

            mock_output_instance.set.assert_called_once()
            set_call = mock_output_instance.set.call_args
            assert set_call[1]["sender"] == "Machine"
            assert set_call[1]["sender_name"] == "AI"
            assert set_call[1]["should_store_message"] is True
            assert set_call[1]["clean_data"] is True

    def test_should_create_graph_with_start_and_end(self):
        """Should create Graph with chat_input as start and chat_output as end."""
        with (
            patch("langflow.agentic.flows.langflow_assistant.ChatInput") as mock_chat_input,
            patch("langflow.agentic.flows.langflow_assistant.ChatOutput") as mock_chat_output,
            patch("langflow.agentic.flows.langflow_assistant.LanguageModelComponent"),
            patch("langflow.agentic.flows.langflow_assistant.Graph") as mock_graph_class,
        ):
            mock_input = MagicMock()
            mock_output = MagicMock()
            mock_chat_input.return_value = mock_input
            mock_chat_output.return_value = mock_output

            get_graph()

            mock_graph_class.assert_called_once_with(start=mock_input, end=mock_output)


class TestAssistantPrompt:
    """Tests for ASSISTANT_PROMPT constant."""

    def test_should_contain_component_generation_instructions(self):
        """Should contain instructions for component generation."""
        assert "generate" in ASSISTANT_PROMPT.lower() or "create" in ASSISTANT_PROMPT.lower()
        assert "component" in ASSISTANT_PROMPT.lower()

    def test_should_contain_langflow_references(self):
        """Should contain Langflow documentation references."""
        assert "langflow" in ASSISTANT_PROMPT.lower()
        assert "docs.langflow.org" in ASSISTANT_PROMPT

    def test_should_contain_code_requirements(self):
        """Should contain code requirements for components."""
        assert "lfx.custom" in ASSISTANT_PROMPT or "langflow.custom" in ASSISTANT_PROMPT
        assert "Component" in ASSISTANT_PROMPT

    def test_should_contain_input_output_instructions(self):
        """Should contain instructions about inputs and outputs."""
        assert "inputs" in ASSISTANT_PROMPT.lower()
        assert "outputs" in ASSISTANT_PROMPT.lower()
        assert "Output" in ASSISTANT_PROMPT
