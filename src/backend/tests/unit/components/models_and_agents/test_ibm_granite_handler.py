"""Tests for IBM Granite handler functions.

This module tests the specialized handling for IBM Granite models
which have different tool calling behavior compared to other LLMs.
"""

import contextlib
from unittest.mock import Mock, patch

import pytest
from langchain_core.messages import AIMessage
from lfx.components.langchain_utilities.ibm_granite_handler import (
    PLACEHOLDER_PATTERN,
    create_granite_agent,
    detect_placeholder_in_args,
    get_enhanced_system_prompt,
    is_granite_model,
    is_watsonx_model,
)

# =============================================================================
# Tests for is_watsonx_model function
# =============================================================================


def create_mock_tool(tool_name: str) -> Mock:
    """Create a mock tool with proper name attribute."""
    mock = Mock()
    mock.name = tool_name
    return mock


class TestIsWatsonxModel:
    """Test suite for is_watsonx_model function."""

    def test_detects_chatwatsonx_class(self):
        """Test detection of ChatWatsonx class by name."""
        mock_llm = Mock()
        mock_llm.__class__.__name__ = "ChatWatsonx"

        result = is_watsonx_model(mock_llm)

        assert result is True

    def test_detects_watsonx_in_class_name(self):
        """Test detection when class name contains 'watsonx'."""
        mock_llm = Mock()
        mock_llm.__class__.__name__ = "WatsonxLLM"

        result = is_watsonx_model(mock_llm)

        assert result is True

    def test_detects_by_module_langchain_ibm(self):
        """Test detection by langchain_ibm module."""
        mock_llm = Mock()
        mock_llm.__class__.__name__ = "SomeModel"
        mock_llm.__class__.__module__ = "langchain_ibm.chat"

        result = is_watsonx_model(mock_llm)

        assert result is True

    def test_detects_by_module_watsonx(self):
        """Test detection by watsonx in module name."""
        mock_llm = Mock()
        mock_llm.__class__.__name__ = "SomeModel"
        mock_llm.__class__.__module__ = "some.watsonx.module"

        result = is_watsonx_model(mock_llm)

        assert result is True

    def test_returns_false_for_openai(self):
        """Test returns False for OpenAI models."""
        mock_llm = Mock()
        mock_llm.__class__.__name__ = "ChatOpenAI"
        mock_llm.__class__.__module__ = "langchain_openai.chat_models"

        result = is_watsonx_model(mock_llm)

        assert result is False

    def test_returns_false_for_anthropic(self):
        """Test returns False for Anthropic models."""
        mock_llm = Mock()
        mock_llm.__class__.__name__ = "ChatAnthropic"
        mock_llm.__class__.__module__ = "langchain_anthropic"

        result = is_watsonx_model(mock_llm)

        assert result is False

    def test_case_insensitive_class_name(self):
        """Test case insensitive detection for class name."""
        mock_llm = Mock()
        mock_llm.__class__.__name__ = "CHATWATSONX"

        result = is_watsonx_model(mock_llm)

        assert result is True

    def test_case_insensitive_module_name(self):
        """Test case insensitive detection for module name."""
        mock_llm = Mock()
        mock_llm.__class__.__name__ = "SomeModel"
        mock_llm.__class__.__module__ = "LANGCHAIN_IBM.chat"

        result = is_watsonx_model(mock_llm)

        assert result is True

    def test_works_with_real_mock_structure(self):
        """Test with a more realistic mock structure."""

        # Simulate what a real ChatWatsonx instance would look like
        class FakeChatWatsonx:
            pass

        mock_llm = FakeChatWatsonx()

        result = is_watsonx_model(mock_llm)

        assert result is True

    def test_detects_llama_on_watsonx(self):
        """Test detection of Llama model running on WatsonX."""
        mock_llm = Mock()
        mock_llm.__class__.__name__ = "ChatWatsonx"
        mock_llm.model_id = "meta-llama/llama-3-2-11b-vision"

        result = is_watsonx_model(mock_llm)

        assert result is True

    def test_detects_mistral_on_watsonx(self):
        """Test detection of Mistral model running on WatsonX."""
        mock_llm = Mock()
        mock_llm.__class__.__name__ = "ChatWatsonx"
        mock_llm.model_id = "mistralai/mistral-large"

        result = is_watsonx_model(mock_llm)

        assert result is True


# =============================================================================
# Tests for is_granite_model function (deprecated but kept for compatibility)
# =============================================================================


class TestIsGraniteModel:
    """Test suite for is_granite_model function."""

    def test_is_granite_model_with_model_id_granite(self):
        """Test detection when model_id contains 'granite'."""
        mock_llm = Mock()
        mock_llm.model_id = "ibm/granite-13b-chat-v2"

        result = is_granite_model(mock_llm)

        assert result is True

    def test_is_granite_model_with_model_name_granite(self):
        """Test detection when model_name contains 'granite'."""
        mock_llm = Mock(spec=["model_name"])
        mock_llm.model_name = "granite-3.1-8b-instruct"

        result = is_granite_model(mock_llm)

        assert result is True

    def test_is_granite_model_case_insensitive(self):
        """Test that detection is case insensitive."""
        mock_llm = Mock()
        mock_llm.model_id = "IBM/GRANITE-13B-CHAT"

        result = is_granite_model(mock_llm)

        assert result is True

    def test_is_granite_model_mixed_case(self):
        """Test detection with mixed case."""
        mock_llm = Mock()
        mock_llm.model_id = "ibm/GrAnItE-model"

        result = is_granite_model(mock_llm)

        assert result is True

    def test_is_granite_model_not_granite(self):
        """Test returns False for non-Granite models."""
        mock_llm = Mock()
        mock_llm.model_id = "meta-llama/llama-3-70b-instruct"

        result = is_granite_model(mock_llm)

        assert result is False

    def test_is_granite_model_openai(self):
        """Test returns False for OpenAI models."""
        mock_llm = Mock()
        mock_llm.model_id = "gpt-4"
        mock_llm.model_name = "gpt-4-turbo"

        result = is_granite_model(mock_llm)

        assert result is False

    def test_is_granite_model_empty_model_id(self):
        """Test with empty model_id."""
        mock_llm = Mock()
        mock_llm.model_id = ""
        mock_llm.model_name = ""

        result = is_granite_model(mock_llm)

        assert result is False

    def test_is_granite_model_none_model_id(self):
        """Test with None model_id."""
        mock_llm = Mock()
        mock_llm.model_id = None
        mock_llm.model_name = None

        result = is_granite_model(mock_llm)

        assert result is False

    def test_is_granite_model_no_attributes(self):
        """Test with model that has neither model_id nor model_name."""
        mock_llm = Mock(spec=[])  # No attributes

        result = is_granite_model(mock_llm)

        assert result is False

    def test_is_granite_model_fallback_to_model_name(self):
        """Test fallback to model_name when model_id is not available."""
        mock_llm = Mock(spec=["model_name"])
        mock_llm.model_name = "granite-3b"

        result = is_granite_model(mock_llm)

        assert result is True

    def test_is_granite_model_partial_match(self):
        """Test that partial match works (granite anywhere in string)."""
        mock_llm = Mock()
        mock_llm.model_id = "some-prefix-granite-suffix"

        result = is_granite_model(mock_llm)

        assert result is True


# =============================================================================
# Tests for get_enhanced_system_prompt function
# =============================================================================


class TestGetEnhancedSystemPrompt:
    """Test suite for get_enhanced_system_prompt function."""

    def test_enhances_prompt_with_multiple_tools(self):
        """Test that prompt is enhanced when multiple tools are provided."""
        base_prompt = "You are a helpful assistant."
        mock_tools = [
            create_mock_tool("search_tool"),
            create_mock_tool("calculator_tool"),
            create_mock_tool("date_tool"),
        ]

        result = get_enhanced_system_prompt(base_prompt, mock_tools)

        assert base_prompt in result
        assert "TOOL USAGE GUIDELINES" in result
        assert "search_tool" in result
        assert "calculator_tool" in result
        assert "date_tool" in result

    def test_no_enhancement_with_empty_tools(self):
        """Test that prompt is not enhanced when tools list is empty."""
        base_prompt = "You are a helpful assistant."

        result = get_enhanced_system_prompt(base_prompt, [])

        assert result == base_prompt

    def test_no_enhancement_with_none_tools(self):
        """Test that prompt is not enhanced when tools is None."""
        base_prompt = "You are a helpful assistant."

        result = get_enhanced_system_prompt(base_prompt, None)

        assert result == base_prompt

    def test_no_enhancement_with_single_tool(self):
        """Test that prompt is not enhanced with only one tool."""
        base_prompt = "You are a helpful assistant."
        mock_tools = [create_mock_tool("single_tool")]

        result = get_enhanced_system_prompt(base_prompt, mock_tools)

        assert result == base_prompt

    def test_enhancement_with_two_tools(self):
        """Test that prompt is enhanced with exactly two tools."""
        base_prompt = "You are a helpful assistant."
        mock_tools = [create_mock_tool("tool1"), create_mock_tool("tool2")]

        result = get_enhanced_system_prompt(base_prompt, mock_tools)

        assert "TOOL USAGE GUIDELINES" in result

    def test_empty_base_prompt(self):
        """Test with empty base prompt."""
        mock_tools = [create_mock_tool("tool1"), create_mock_tool("tool2")]

        result = get_enhanced_system_prompt("", mock_tools)

        assert "TOOL USAGE GUIDELINES" in result

    def test_enhancement_contains_key_instructions(self):
        """Test that enhancement contains all key instructions."""
        base_prompt = "Base prompt"
        mock_tools = [create_mock_tool("tool1"), create_mock_tool("tool2")]

        result = get_enhanced_system_prompt(base_prompt, mock_tools)

        assert "ALWAYS call tools" in result
        assert "one tool at a time" in result
        assert "placeholder syntax" in result
        assert "AVAILABLE TOOLS" in result

    def test_tool_names_listed(self):
        """Test that all tool names are listed in the enhancement."""
        mock_tools = [
            create_mock_tool("perform_search"),
            create_mock_tool("get_current_date"),
            create_mock_tool("evaluate_expression"),
        ]

        result = get_enhanced_system_prompt("Base", mock_tools)

        assert "perform_search" in result
        assert "get_current_date" in result
        assert "evaluate_expression" in result


# =============================================================================
# Tests for detect_placeholder_in_args function
# =============================================================================


class TestDetectPlaceholderInArgs:
    """Test suite for detect_placeholder_in_args function."""

    def test_detects_result_from_placeholder(self):
        """Test detection of <result-from-...> placeholder."""
        tool_calls = [{"name": "calculator", "args": {"expression": "<result-from-search>"}}]

        has_placeholder, value = detect_placeholder_in_args(tool_calls)

        assert has_placeholder is True
        assert value == "<result-from-search>"

    def test_detects_extracted_date_placeholder(self):
        """Test detection of <extracted_date> placeholder."""
        tool_calls = [{"name": "calculator", "args": {"expression": "<extracted_date>-18"}}]

        has_placeholder, value = detect_placeholder_in_args(tool_calls)

        assert has_placeholder is True
        assert "<extracted_date>" in value

    def test_detects_previous_value_placeholder(self):
        """Test detection of <previous-value> placeholder."""
        tool_calls = [{"name": "tool", "args": {"input": "<previous-value>"}}]

        has_placeholder, _ = detect_placeholder_in_args(tool_calls)

        assert has_placeholder is True

    def test_detects_output_placeholder(self):
        """Test detection of <output-...> placeholder."""
        tool_calls = [{"name": "tool", "args": {"data": "<output-from-api>"}}]

        has_placeholder, _ = detect_placeholder_in_args(tool_calls)

        assert has_placeholder is True

    def test_detects_response_placeholder(self):
        """Test detection of <response-...> placeholder."""
        tool_calls = [{"name": "tool", "args": {"value": "<response-data>"}}]

        has_placeholder, _ = detect_placeholder_in_args(tool_calls)

        assert has_placeholder is True

    def test_detects_current_placeholder(self):
        """Test detection of <current-...> placeholder."""
        tool_calls = [{"name": "tool", "args": {"date": "<current-date>"}}]

        has_placeholder, _ = detect_placeholder_in_args(tool_calls)

        assert has_placeholder is True

    def test_detects_search_result_placeholder(self):
        """Test detection of <search-result> placeholder."""
        tool_calls = [{"name": "tool", "args": {"query": "<search-result>"}}]

        has_placeholder, _ = detect_placeholder_in_args(tool_calls)

        assert has_placeholder is True

    def test_detects_tool_result_placeholder(self):
        """Test detection of <tool-output> placeholder."""
        tool_calls = [{"name": "tool", "args": {"input": "<tool-output>"}}]

        has_placeholder, _ = detect_placeholder_in_args(tool_calls)

        assert has_placeholder is True

    def test_no_placeholder_returns_false(self):
        """Test returns False when no placeholder is present."""
        tool_calls = [{"name": "calculator", "args": {"expression": "2 + 2"}}]

        has_placeholder, value = detect_placeholder_in_args(tool_calls)

        assert has_placeholder is False
        assert value is None

    def test_empty_tool_calls(self):
        """Test with empty tool_calls list."""
        has_placeholder, value = detect_placeholder_in_args([])

        assert has_placeholder is False
        assert value is None

    def test_none_tool_calls(self):
        """Test with None tool_calls."""
        has_placeholder, value = detect_placeholder_in_args(None)

        assert has_placeholder is False
        assert value is None

    def test_args_as_string(self):
        """Test detection when args is a string instead of dict."""
        tool_calls = [{"name": "tool", "args": "<result-from-previous>"}]

        has_placeholder, _ = detect_placeholder_in_args(tool_calls)

        assert has_placeholder is True

    def test_multiple_tool_calls_first_has_placeholder(self):
        """Test with multiple tool calls where first has placeholder."""
        tool_calls = [
            {"name": "tool1", "args": {"value": "<result-from-api>"}},
            {"name": "tool2", "args": {"value": "normal"}},
        ]

        has_placeholder, _ = detect_placeholder_in_args(tool_calls)

        assert has_placeholder is True

    def test_multiple_tool_calls_second_has_placeholder(self):
        """Test with multiple tool calls where second has placeholder."""
        tool_calls = [
            {"name": "tool1", "args": {"value": "normal"}},
            {"name": "tool2", "args": {"value": "<result-placeholder>"}},
        ]

        has_placeholder, _ = detect_placeholder_in_args(tool_calls)

        assert has_placeholder is True

    def test_nested_args_with_placeholder(self):
        """Test with nested args structure."""
        tool_calls = [{"name": "tool", "args": {"outer": {"inner": "<result>"}}}]

        # Note: Current implementation only checks top-level values
        has_placeholder, _ = detect_placeholder_in_args(tool_calls)

        # Should not detect nested placeholders with current implementation
        assert has_placeholder is False

    def test_case_insensitive_detection(self):
        """Test that detection is case insensitive."""
        tool_calls = [{"name": "tool", "args": {"value": "<RESULT-FROM-API>"}}]

        has_placeholder, _ = detect_placeholder_in_args(tool_calls)

        assert has_placeholder is True

    def test_tool_call_without_name(self):
        """Test tool call without name field."""
        tool_calls = [{"args": {"value": "<result>"}}]

        has_placeholder, _ = detect_placeholder_in_args(tool_calls)

        assert has_placeholder is True

    def test_tool_call_without_args(self):
        """Test tool call without args field."""
        tool_calls = [{"name": "tool"}]

        has_placeholder, _ = detect_placeholder_in_args(tool_calls)

        assert has_placeholder is False

    def test_normal_angle_brackets_not_detected(self):
        """Test that normal angle brackets in code are not detected."""
        tool_calls = [{"name": "tool", "args": {"code": "if x < 10 and y > 5:"}}]

        has_placeholder, _ = detect_placeholder_in_args(tool_calls)

        assert has_placeholder is False

    def test_html_tags_not_detected(self):
        """Test that HTML tags are not detected as placeholders."""
        tool_calls = [{"name": "tool", "args": {"html": "<div>content</div>"}}]

        has_placeholder, _ = detect_placeholder_in_args(tool_calls)

        assert has_placeholder is False


# =============================================================================
# Tests for PLACEHOLDER_PATTERN regex
# =============================================================================


class TestPlaceholderPattern:
    """Test suite for PLACEHOLDER_PATTERN regex."""

    @pytest.mark.parametrize(
        ("test_input", "expected"),
        [
            # Should match
            ("<result-from-search>", True),
            ("<value-extracted>", True),
            ("<output-data>", True),
            ("<response-from-api>", True),
            ("<data-field>", True),
            ("<from-previous-step>", True),
            ("<extract-this>", True),
            ("<previous-result>", True),
            ("<current-date>", True),
            ("<date-value>", True),
            ("<input-from-user>", True),
            ("<query-result>", True),
            ("<search-output>", True),
            ("<tool-output>", True),
            ("<RESULT-FROM-API>", True),  # Case insensitive
            ("<Result-Value>", True),  # Mixed case
            # Should not match
            ("<div>", False),
            ("<span>", False),
            ("<button>", False),
            ("<html>", False),
            ("<p>", False),
            ("<a>", False),
            ("< >", False),
            ("<>", False),
            ("<123>", False),
            ("<abc>", False),  # No keywords
            ("normal text", False),
            ("", False),
        ],
    )
    def test_placeholder_pattern_matching(self, test_input, expected):
        """Test PLACEHOLDER_PATTERN matches expected patterns."""
        result = bool(PLACEHOLDER_PATTERN.search(test_input))
        assert result == expected, f"Pattern '{test_input}' should {'match' if expected else 'not match'}"

    def test_pattern_extracts_full_placeholder(self):
        """Test that pattern extracts the full placeholder."""
        text = "Calculate <result-from-search> minus 5"
        match = PLACEHOLDER_PATTERN.search(text)

        assert match is not None
        assert match.group() == "<result-from-search>"

    def test_pattern_finds_multiple_placeholders(self):
        """Test pattern can find multiple placeholders."""
        text = "Use <result-from-a> and <output-from-b>"
        matches = PLACEHOLDER_PATTERN.findall(text)

        assert len(matches) == 2


# =============================================================================
# Tests for create_granite_agent function
# =============================================================================


class TestCreateGraniteAgent:
    """Test suite for create_granite_agent function."""

    def test_raises_error_without_bind_tools(self):
        """Test that ValueError is raised when LLM lacks bind_tools."""
        mock_llm = Mock(spec=[])  # No bind_tools method
        mock_tools = [Mock(name="tool1")]
        mock_prompt = Mock()

        with pytest.raises(ValueError, match="bind_tools"):
            create_granite_agent(mock_llm, mock_tools, mock_prompt)

    def test_creates_agent_with_valid_inputs(self):
        """Test agent creation with valid inputs."""
        mock_llm = Mock()
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        mock_tools = [Mock(name="tool1")]
        mock_prompt = Mock()
        mock_prompt.invoke = Mock(return_value=Mock(messages=[]))

        agent = create_granite_agent(mock_llm, mock_tools, mock_prompt)

        assert agent is not None
        # Verify bind_tools was called with both tool_choice options
        assert mock_llm.bind_tools.call_count == 2

    def test_bind_tools_called_with_required(self):
        """Test that bind_tools is called with tool_choice='required'."""
        mock_llm = Mock()
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        mock_tools = [Mock(name="tool1")]
        mock_prompt = Mock()

        create_granite_agent(mock_llm, mock_tools, mock_prompt)

        calls = mock_llm.bind_tools.call_args_list
        tool_choices = [call[1].get("tool_choice") for call in calls]
        assert "required" in tool_choices

    def test_bind_tools_called_with_auto(self):
        """Test that bind_tools is called with tool_choice='auto'."""
        mock_llm = Mock()
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        mock_tools = [Mock(name="tool1")]
        mock_prompt = Mock()

        create_granite_agent(mock_llm, mock_tools, mock_prompt)

        calls = mock_llm.bind_tools.call_args_list
        tool_choices = [call[1].get("tool_choice") for call in calls]
        assert "auto" in tool_choices

    def test_empty_tools_list(self):
        """Test agent creation with empty tools list."""
        mock_llm = Mock()
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        mock_prompt = Mock()

        agent = create_granite_agent(mock_llm, [], mock_prompt)

        assert agent is not None

    def test_custom_forced_iterations(self):
        """Test agent creation with custom forced_iterations."""
        mock_llm = Mock()
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        mock_tools = [Mock(name="tool1")]
        mock_prompt = Mock()

        agent = create_granite_agent(mock_llm, mock_tools, mock_prompt, forced_iterations=5)

        assert agent is not None


class TestCreateGraniteAgentDynamicInvoke:
    """Test suite for the dynamic_invoke inner function in create_granite_agent."""

    def setup_method(self):
        """Set up common mocks for each test."""
        self.mock_llm = Mock()
        self.mock_llm_required = Mock()
        self.mock_llm_auto = Mock()

        def bind_tools_side_effect(_tools, tool_choice=None):
            if tool_choice == "required":
                return self.mock_llm_required
            return self.mock_llm_auto

        self.mock_llm.bind_tools = Mock(side_effect=bind_tools_side_effect)

        self.mock_prompt = Mock()
        self.mock_prompt.invoke = Mock(return_value=Mock(messages=[]))

        self.mock_tools = [Mock(name="tool1")]

    def test_uses_required_for_first_iteration(self):
        """Test that tool_choice='required' is used for first iteration."""
        self.mock_llm_required.invoke = Mock(return_value=AIMessage(content="response"))

        agent = create_granite_agent(self.mock_llm, self.mock_tools, self.mock_prompt)

        # Invoke with no intermediate steps (first iteration)
        inputs = {"input": "test", "intermediate_steps": []}

        # The agent is a RunnableLambda | ToolsAgentOutputParser chain
        # We need to invoke the first part (RunnableLambda)
        # This will raise because ToolsAgentOutputParser expects AIMessage with tool_calls
        with (
            patch("lfx.components.langchain_utilities.ibm_granite_handler.format_to_tool_messages", return_value=[]),
            contextlib.suppress(Exception),
        ):
            agent.invoke(inputs)

        self.mock_llm_required.invoke.assert_called()

    def test_uses_auto_after_forced_iterations(self):
        """Test that tool_choice='auto' is used after forced iterations."""
        self.mock_llm_auto.invoke = Mock(return_value=AIMessage(content="final response"))

        agent = create_granite_agent(self.mock_llm, self.mock_tools, self.mock_prompt, forced_iterations=2)

        # Invoke with 2 intermediate steps (past forced iterations)
        inputs = {"input": "test", "intermediate_steps": [("action1", "result1"), ("action2", "result2")]}

        with (
            patch("lfx.components.langchain_utilities.ibm_granite_handler.format_to_tool_messages", return_value=[]),
            contextlib.suppress(Exception),
        ):
            agent.invoke(inputs)

        self.mock_llm_auto.invoke.assert_called()

    def test_placeholder_detection_triggers_corrective_message(self):
        """Test that placeholder detection triggers corrective message."""
        # Create response with placeholder in tool calls
        mock_response = Mock()
        mock_response.tool_calls = [{"name": "calculator", "args": {"expression": "<result-from-search>"}}]
        self.mock_llm_required.invoke = Mock(return_value=mock_response)
        self.mock_llm_auto.invoke = Mock(return_value=AIMessage(content="corrected response"))

        agent = create_granite_agent(self.mock_llm, self.mock_tools, self.mock_prompt)

        inputs = {"input": "test", "intermediate_steps": []}

        with (
            patch("lfx.components.langchain_utilities.ibm_granite_handler.format_to_tool_messages", return_value=[]),
            contextlib.suppress(Exception),
        ):
            agent.invoke(inputs)

        # After placeholder detection, llm_auto should be called with corrective message
        assert self.mock_llm_auto.invoke.called


# =============================================================================
# Integration tests with ToolCallingAgentComponent
# =============================================================================


class TestToolCallingAgentIntegration:
    """Integration tests for ToolCallingAgentComponent with IBM WatsonX."""

    def test_watsonx_detection_in_create_agent_runnable(self):
        """Test that WatsonX models are detected in create_agent_runnable."""
        from lfx.components.langchain_utilities import ToolCallingAgentComponent

        # Create a mock WatsonX LLM (simulating ChatWatsonx)
        mock_llm = Mock()
        mock_llm.__class__.__name__ = "ChatWatsonx"
        mock_llm.model_id = "ibm/granite-13b-chat-v2"
        mock_llm.bind_tools = Mock(return_value=mock_llm)

        mock_tools = [create_mock_tool("test_tool"), create_mock_tool("test_tool2")]

        component = ToolCallingAgentComponent()
        component.llm = mock_llm
        component.tools = mock_tools
        component.system_prompt = "Test prompt"

        with patch("lfx.components.langchain_utilities.tool_calling.create_granite_agent") as mock_create:
            mock_create.return_value = Mock()

            component.create_agent_runnable()

            # Verify create_granite_agent was called (for WatsonX models)
            mock_create.assert_called_once()

    def test_watsonx_llama_uses_default_agent(self):
        """Test that Llama model on WatsonX uses default agent (not Granite-specific)."""
        from lfx.components.langchain_utilities import ToolCallingAgentComponent

        # Create a mock WatsonX LLM with Llama model (non-Granite)
        mock_llm = Mock()
        mock_llm.__class__.__name__ = "ChatWatsonx"
        mock_llm.model_id = "meta-llama/llama-3-2-11b-vision"
        mock_llm.bind_tools = Mock(return_value=mock_llm)

        mock_tools = [create_mock_tool("tool1"), create_mock_tool("tool2")]

        component = ToolCallingAgentComponent()
        component.llm = mock_llm
        component.tools = mock_tools
        component.system_prompt = "Test prompt"

        with patch("lfx.components.langchain_utilities.tool_calling.create_tool_calling_agent") as mock_default:
            mock_default.return_value = Mock()

            component.create_agent_runnable()

            # Verify create_tool_calling_agent was called (default behavior for non-Granite)
            mock_default.assert_called_once()

    def test_non_watsonx_uses_default_agent(self):
        """Test that non-WatsonX models use the default agent creation."""
        from lfx.components.langchain_utilities import ToolCallingAgentComponent

        # Create a mock non-WatsonX LLM (e.g., OpenAI)
        mock_llm = Mock()
        mock_llm.__class__.__name__ = "ChatOpenAI"
        mock_llm.__class__.__module__ = "langchain_openai"
        mock_llm.model_id = "gpt-4"
        mock_llm.bind_tools = Mock(return_value=mock_llm)

        mock_tools = [create_mock_tool("test_tool")]

        component = ToolCallingAgentComponent()
        component.llm = mock_llm
        component.tools = mock_tools
        component.system_prompt = "Test prompt"

        with patch("lfx.components.langchain_utilities.tool_calling.create_tool_calling_agent") as mock_create:
            mock_create.return_value = Mock()

            component.create_agent_runnable()

            # Verify create_tool_calling_agent was called
            mock_create.assert_called_once()

    def test_system_prompt_enhanced_for_watsonx(self):
        """Test that system prompt is enhanced for WatsonX models."""
        from lfx.components.langchain_utilities import ToolCallingAgentComponent

        mock_llm = Mock()
        mock_llm.__class__.__name__ = "ChatWatsonx"
        mock_llm.model_id = "ibm/granite-13b-chat-v2"
        mock_llm.bind_tools = Mock(return_value=mock_llm)

        mock_tools = [create_mock_tool("tool1"), create_mock_tool("tool2")]

        component = ToolCallingAgentComponent()
        component.llm = mock_llm
        component.tools = mock_tools
        component.system_prompt = "Original prompt"

        with patch("lfx.components.langchain_utilities.tool_calling.create_granite_agent") as mock_create:
            mock_create.return_value = Mock()

            component.create_agent_runnable()

            # Verify enhanced prompt is stored separately (original is not mutated)
            assert component.system_prompt == "Original prompt"
            assert hasattr(component, "_effective_system_prompt")
            assert "TOOL USAGE GUIDELINES" in component._effective_system_prompt

    def test_system_prompt_not_enhanced_without_tools(self):
        """Test that system prompt is not enhanced when no tools."""
        from lfx.components.langchain_utilities import ToolCallingAgentComponent

        mock_llm = Mock()
        mock_llm.__class__.__name__ = "ChatWatsonx"
        mock_llm.model_id = "ibm/granite-13b-chat-v2"
        mock_llm.bind_tools = Mock(return_value=mock_llm)

        component = ToolCallingAgentComponent()
        component.llm = mock_llm
        component.tools = []
        component.system_prompt = "Original prompt"

        with patch("lfx.components.langchain_utilities.tool_calling.create_tool_calling_agent") as mock_create:
            mock_create.return_value = Mock()

            component.create_agent_runnable()

            # Verify system prompt was NOT enhanced (no _effective_system_prompt set)
            assert component.system_prompt == "Original prompt"
            assert not hasattr(component, "_effective_system_prompt")


# =============================================================================
# Edge case and error handling tests
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_is_granite_model_with_integer_model_id(self):
        """Test handling of non-string model_id."""
        mock_llm = Mock()
        mock_llm.model_id = 12345

        result = is_granite_model(mock_llm)

        assert result is False

    def test_detect_placeholder_with_special_characters(self):
        """Test placeholder detection with special regex characters."""
        tool_calls = [{"name": "tool", "args": {"value": "<result-from-search.+*?>"}}]

        # Should not raise regex error
        has_placeholder, _ = detect_placeholder_in_args(tool_calls)

        assert has_placeholder is True

    def test_get_enhanced_system_prompt_preserves_base(self):
        """Test that base prompt is always preserved."""
        base_prompt = "Very important system instructions that must be kept."
        mock_tools = [create_mock_tool("t1"), create_mock_tool("t2")]

        result = get_enhanced_system_prompt(base_prompt, mock_tools)

        assert result.startswith(base_prompt)

    def test_create_granite_agent_with_none_tools(self):
        """Test agent creation when tools is None."""
        mock_llm = Mock()
        mock_llm.bind_tools = Mock(return_value=mock_llm)
        mock_prompt = Mock()

        # Should handle None tools gracefully
        agent = create_granite_agent(mock_llm, None, mock_prompt)

        assert agent is not None

    def test_placeholder_in_numeric_value(self):
        """Test that numeric values don't trigger placeholder detection."""
        tool_calls = [{"name": "calculator", "args": {"value": 12345}}]

        has_placeholder, _ = detect_placeholder_in_args(tool_calls)

        assert has_placeholder is False

    def test_placeholder_in_list_value(self):
        """Test handling of list values in args."""
        tool_calls = [{"name": "tool", "args": {"items": ["<result>", "normal"]}}]

        # Current implementation doesn't check list items
        has_placeholder, _ = detect_placeholder_in_args(tool_calls)

        assert has_placeholder is False

    def test_is_granite_with_watsonx_model_id(self):
        """Test detection with full WatsonX model ID format."""
        mock_llm = Mock()
        mock_llm.model_id = "ibm/granite-3-8b-instruct"

        result = is_granite_model(mock_llm)

        assert result is True

    def test_empty_args_dict(self):
        """Test with empty args dictionary."""
        tool_calls = [{"name": "tool", "args": {}}]

        has_placeholder, _ = detect_placeholder_in_args(tool_calls)

        assert has_placeholder is False
