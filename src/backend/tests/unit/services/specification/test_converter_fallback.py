"""Tests for enhanced fallback templates in FlowConverter."""

import pytest
from unittest.mock import Mock, patch
from langflow.custom.genesis.spec.converter import FlowConverter


class TestFlowConverterFallbackTemplates:
    """Test enhanced fallback template functionality."""

    @pytest.fixture
    def converter(self):
        """Create FlowConverter instance."""
        return FlowConverter()

    def test_fallback_template_agent(self, converter):
        """Test fallback template for Agent components."""
        template = converter._create_fallback_template("Agent")

        assert template is not None
        assert "template" in template
        assert "outputs" in template

        # Check critical Agent fields
        fields = template["template"]
        assert "agent_llm" in fields
        assert fields["agent_llm"]["value"] == "Azure OpenAI"
        assert "azure_deployment_name" in fields
        assert "temperature" in fields
        assert fields["temperature"]["value"] == 0.7
        assert "max_tokens" in fields
        assert fields["max_tokens"]["value"] == 2000
        assert "system_prompt" in fields
        assert "tools" in fields
        assert "memory" in fields

        # Check output
        outputs = template["outputs"]
        assert len(outputs) == 1
        assert outputs[0]["name"] == "response"
        assert outputs[0]["types"] == ["Message"]

    def test_fallback_template_autonomize_agent(self, converter):
        """Test fallback template for AutonomizeAgent."""
        template = converter._create_fallback_template("AutonomizeAgent")

        assert template is not None
        # Should use the same template as Agent
        fields = template["template"]
        assert "agent_llm" in fields
        assert "azure_deployment_name" in fields
        assert "temperature" in fields

    def test_fallback_template_mcp_tools(self, converter):
        """Test fallback template for MCP Tool components."""
        template = converter._create_fallback_template("MCPTools")

        assert template is not None
        fields = template["template"]

        # Check MCP-specific fields
        assert "tool_names" in fields
        assert "command" in fields
        assert "args" in fields
        assert "env" in fields
        assert "url" in fields
        assert "headers" in fields
        assert "timeout_seconds" in fields
        assert fields["timeout_seconds"]["value"] == 30
        assert "sse_read_timeout_seconds" in fields
        assert fields["sse_read_timeout_seconds"]["value"] == 30

        # Check outputs
        outputs = template["outputs"]
        assert outputs[0]["name"] == "tool_output"
        assert outputs[0]["types"] == ["Any"]

    def test_fallback_template_api_request(self, converter):
        """Test fallback template for API Request components."""
        template = converter._create_fallback_template("APIRequest")

        assert template is not None
        fields = template["template"]

        # Check API Request fields
        assert "method" in fields
        assert fields["method"]["value"] == "GET"
        assert "url_input" in fields
        assert "headers" in fields
        assert "body" in fields
        assert "timeout" in fields
        assert fields["timeout"]["value"] == 30
        assert "follow_redirects" in fields
        assert fields["follow_redirects"]["value"] is True

        # Check outputs
        outputs = template["outputs"]
        assert outputs[0]["name"] == "response"

    def test_fallback_template_prompt(self, converter):
        """Test fallback template for Prompt components."""
        template = converter._create_fallback_template("Prompt")

        assert template is not None
        fields = template["template"]

        # Check Prompt fields
        assert "template" in fields
        assert "input_variables" in fields
        assert "validate_template" in fields
        assert fields["validate_template"]["value"] is True

        # Check outputs
        outputs = template["outputs"]
        assert outputs[0]["name"] == "prompt"

    def test_fallback_template_chat_input(self, converter):
        """Test fallback template for ChatInput components."""
        template = converter._create_fallback_template("ChatInput")

        assert template is not None
        fields = template["template"]

        # Check ChatInput fields
        assert "input_value" in fields
        assert "sender" in fields
        assert fields["sender"]["value"] == "User"
        assert "sender_name" in fields
        assert fields["sender_name"]["value"] == "User"

        # Check outputs
        outputs = template["outputs"]
        assert outputs[0]["name"] == "message"

    def test_fallback_template_chat_output(self, converter):
        """Test fallback template for ChatOutput components."""
        template = converter._create_fallback_template("ChatOutput")

        assert template is not None
        fields = template["template"]

        # Check ChatOutput fields
        assert "input_value" in fields
        assert "sender" in fields
        assert fields["sender"]["value"] == "Machine"
        assert "sender_name" in fields
        assert fields["sender_name"]["value"] == "AI"

        # Check outputs
        outputs = template["outputs"]
        assert outputs[0]["name"] == "message"

    def test_fallback_template_file_component(self, converter):
        """Test fallback template for File components."""
        template = converter._create_fallback_template("FileComponent")

        assert template is not None
        fields = template["template"]

        # Check File fields
        assert "file_path" in fields
        assert "file_type" in fields
        assert fields["file_type"]["value"] == "Any"
        assert "parse_content" in fields
        assert fields["parse_content"]["value"] is True

        # Check outputs
        outputs = template["outputs"]
        assert outputs[0]["name"] == "data"

    def test_fallback_template_memory(self, converter):
        """Test fallback template for Memory components."""
        template = converter._create_fallback_template("Memory")

        assert template is not None
        fields = template["template"]

        # Check Memory fields
        assert "memory_type" in fields
        assert fields["memory_type"]["value"] == "Buffer"
        assert "max_messages" in fields
        assert fields["max_messages"]["value"] == 100

        # Check outputs
        outputs = template["outputs"]
        assert outputs[0]["name"] == "memory"

    def test_fallback_template_unknown_component(self, converter):
        """Test fallback template for unknown component types."""
        template = converter._create_fallback_template("UnknownComponentType")

        # Should return None for truly unknown types
        assert template is None

    def test_fallback_template_partial_match(self, converter):
        """Test fallback template with partial component name matches."""
        # Test with variations of Agent
        template = converter._create_fallback_template("CustomAgent")
        assert template is not None
        assert "agent_llm" in template["template"]

        # Test with variations of MCPTool
        template = converter._create_fallback_template("MCPTool")
        assert template is not None
        assert "tool_names" in template["template"]

    def test_fallback_template_preserves_config(self, converter):
        """Test that fallback templates preserve critical configurations."""
        # Test Agent preserves LLM config
        agent_template = converter._create_fallback_template("Agent")
        assert agent_template["template"]["temperature"]["value"] == 0.7
        assert agent_template["template"]["max_tokens"]["value"] == 2000
        assert agent_template["template"]["agent_llm"]["value"] == "Azure OpenAI"

        # Test MCP preserves timeout config
        mcp_template = converter._create_fallback_template("MCPTools")
        assert mcp_template["template"]["timeout_seconds"]["value"] == 30
        assert mcp_template["template"]["sse_read_timeout_seconds"]["value"] == 30

        # Test API preserves request config
        api_template = converter._create_fallback_template("APIRequest")
        assert api_template["template"]["timeout"]["value"] == 30
        assert api_template["template"]["follow_redirects"]["value"] is True

    def test_fallback_template_field_types(self, converter):
        """Test that fallback template fields have correct types."""
        template = converter._create_fallback_template("Agent")
        fields = template["template"]

        # Check field types
        assert fields["temperature"]["type"] == "float"
        assert fields["max_tokens"]["type"] == "int"
        assert fields["agent_llm"]["type"] == "str"
        assert fields["tools"]["type"] == "list"
        assert fields["memory"]["type"] == "dict"

    def test_fallback_template_display_names(self, converter):
        """Test that fallback templates have proper display names."""
        template = converter._create_fallback_template("Agent")
        fields = template["template"]

        # Check display names
        assert fields["agent_llm"]["display_name"] == "Model Provider"
        assert fields["azure_deployment_name"]["display_name"] == "Azure Deployment"
        assert fields["temperature"]["display_name"] == "Temperature"
        assert fields["max_tokens"]["display_name"] == "Max Tokens"
        assert fields["system_prompt"]["display_name"] == "System Prompt"