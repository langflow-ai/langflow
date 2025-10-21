"""
Unit tests for enhanced type compatibility matrix in FlowConverter.

Tests the improved type compatibility validation for tool connections
and data flow scenarios.
"""

import pytest
from typing import List

from langflow.custom.genesis.spec.converter import FlowConverter


class TestEnhancedTypeCompatibility:
    """Test enhanced type compatibility matrix and validation logic."""

    @pytest.fixture
    def converter(self):
        """Create converter instance for testing."""
        return FlowConverter()

    def test_tool_to_tool_compatibility(self, converter):
        """Test direct Tool-to-Tool connections."""
        result = converter._validate_type_compatibility_fixed(
            ["Tool"], ["Tool"], "MCPTools", "Agent"
        )
        assert result is True

    def test_tool_capability_connections(self, converter):
        """Test that various component outputs can connect to Tool inputs."""
        compatible_outputs = ["DataFrame", "Data", "Message", "str", "Document", "object", "any"]

        for output_type in compatible_outputs:
            result = converter._validate_type_compatibility_fixed(
                [output_type], ["Tool"], "Component", "Agent"
            )
            assert result is True, f"{output_type} should be compatible with Tool input"

    def test_message_type_conversions(self, converter):
        """Test Message type compatibility with various inputs."""
        message_compatible = ["str", "text", "Text", "Data", "Document", "dict", "object"]

        for compatible_type in message_compatible:
            result = converter._validate_type_compatibility_fixed(
                ["Message"], [compatible_type], "Agent", "Component"
            )
            assert result is True, f"Message should be compatible with {compatible_type}"

    def test_data_type_conversions(self, converter):
        """Test Data type compatibility with various inputs."""
        data_compatible = ["dict", "object", "any", "Message", "str", "Document", "DataFrame", "text", "Text"]

        for compatible_type in data_compatible:
            result = converter._validate_type_compatibility_fixed(
                ["Data"], [compatible_type], "Component", "Component"
            )
            assert result is True, f"Data should be compatible with {compatible_type}"

    def test_dataframe_type_conversions(self, converter):
        """Test DataFrame type compatibility."""
        dataframe_compatible = ["Data", "object", "any", "Tool", "dict", "Message"]

        for compatible_type in dataframe_compatible:
            result = converter._validate_type_compatibility_fixed(
                ["DataFrame"], [compatible_type], "Component", "Component"
            )
            assert result is True, f"DataFrame should be compatible with {compatible_type}"

    def test_document_type_conversions(self, converter):
        """Test Document type compatibility."""
        document_compatible = ["Data", "Message", "str", "text", "Text", "dict", "object"]

        for compatible_type in document_compatible:
            result = converter._validate_type_compatibility_fixed(
                ["Document"], [compatible_type], "Component", "Component"
            )
            assert result is True, f"Document should be compatible with {compatible_type}"

    def test_string_text_type_conversions(self, converter):
        """Test string and text type compatibility."""
        string_types = ["str", "text", "Text"]
        compatible_types = ["Message", "Data", "Document"]

        for string_type in string_types:
            for compatible_type in compatible_types:
                result = converter._validate_type_compatibility_fixed(
                    [string_type], [compatible_type], "Component", "Component"
                )
                assert result is True, f"{string_type} should be compatible with {compatible_type}"

    def test_tool_output_conversions(self, converter):
        """Test Tool output type compatibility."""
        tool_compatible = ["DataFrame", "Data", "any", "object", "Message", "str", "dict"]

        for compatible_type in tool_compatible:
            result = converter._validate_type_compatibility_fixed(
                ["Tool"], [compatible_type], "Agent", "Component"
            )
            assert result is True, f"Tool should be compatible with {compatible_type}"

    def test_object_type_universal_compatibility(self, converter):
        """Test object type universal compatibility."""
        object_compatible = ["any", "Data", "DataFrame", "Tool", "Message", "str", "Document", "dict"]

        for compatible_type in object_compatible:
            result = converter._validate_type_compatibility_fixed(
                ["object"], [compatible_type], "Component", "Component"
            )
            assert result is True, f"object should be compatible with {compatible_type}"

    def test_any_type_universal_compatibility(self, converter):
        """Test any type universal compatibility."""
        any_compatible = ["Message", "str", "Data", "DataFrame", "Document", "Tool", "object", "text", "Text", "dict"]

        for compatible_type in any_compatible:
            result = converter._validate_type_compatibility_fixed(
                ["any"], [compatible_type], "Component", "Component"
            )
            assert result is True, f"any should be compatible with {compatible_type}"

    def test_direct_type_matches(self, converter):
        """Test direct type matching."""
        direct_matches = ["Message", "str", "Data", "DataFrame", "Document", "Tool", "object", "any"]

        for match_type in direct_matches:
            result = converter._validate_type_compatibility_fixed(
                [match_type], [match_type], "Component", "Component"
            )
            assert result is True, f"{match_type} should match itself"

    def test_data_to_input_value_compatibility(self, converter):
        """Test AutonomizeModel Data to input_value compatibility."""
        result = converter._validate_type_compatibility_fixed(
            ["Data"], ["input_value"], "AutonomizeModel", "Component"
        )
        assert result is True

    def test_multiple_output_types_compatibility(self, converter):
        """Test compatibility with multiple output types."""
        result = converter._validate_type_compatibility_fixed(
            ["Message", "Data"], ["str"], "Component", "Component"
        )
        assert result is True, "Multiple output types should find compatible match"

    def test_multiple_input_types_compatibility(self, converter):
        """Test compatibility with multiple input types."""
        result = converter._validate_type_compatibility_fixed(
            ["Message"], ["str", "object", "dict"], "Component", "Component"
        )
        assert result is True, "Output should match one of multiple input types"

    def test_incompatible_type_combinations(self, converter):
        """Test truly incompatible type combinations."""
        # This should only fail if no conversion path exists
        # Most types should have some compatibility in the enhanced matrix
        result = converter._validate_type_compatibility_fixed(
            ["UnknownType"], ["AnotherUnknownType"], "Component", "Component"
        )
        assert result is False, "Unknown types should not be compatible"

    def test_healthcare_workflow_scenarios(self, converter):
        """Test common healthcare workflow type scenarios."""
        # MCP tool (DataFrame) -> Agent (Tool)
        result1 = converter._validate_type_compatibility_fixed(
            ["DataFrame"], ["Tool"], "MCPTools", "Agent"
        )
        assert result1 is True, "MCP tool DataFrame should connect to Agent Tool input"

        # Knowledge search (Data) -> Agent (Tool)
        result2 = converter._validate_type_compatibility_fixed(
            ["Data"], ["Tool"], "KnowledgeHubSearch", "Agent"
        )
        assert result2 is True, "Knowledge search Data should connect to Agent Tool input"

        # Agent (Message) -> Output (Message)
        result3 = converter._validate_type_compatibility_fixed(
            ["Message"], ["Message"], "Agent", "ChatOutput"
        )
        assert result3 is True, "Agent Message should connect to Output Message"

        # Input (Message) -> Agent (Message)
        result4 = converter._validate_type_compatibility_fixed(
            ["Message"], ["Message"], "ChatInput", "Agent"
        )
        assert result4 is True, "Input Message should connect to Agent Message"

    def test_edge_case_type_scenarios(self, converter):
        """Test edge cases and complex type scenarios."""
        # Empty type lists
        result1 = converter._validate_type_compatibility_fixed(
            [], ["Message"], "Component", "Component"
        )
        assert result1 is False, "Empty output types should not be compatible"

        result2 = converter._validate_type_compatibility_fixed(
            ["Message"], [], "Component", "Component"
        )
        assert result2 is False, "Empty input types should not be compatible"

        # Case sensitivity
        result3 = converter._validate_type_compatibility_fixed(
            ["message"], ["Message"], "Component", "Component"
        )
        assert result3 is False, "Case mismatch should not be compatible"

    def test_bidirectional_compatibility(self, converter):
        """Test that compatibility is properly bidirectional where expected."""
        bidirectional_pairs = [
            ("Message", "str"),
            ("Data", "Message"),
            ("Document", "Data"),
            ("str", "text"),
            ("object", "any")
        ]

        for type1, type2 in bidirectional_pairs:
            # Test both directions
            result1 = converter._validate_type_compatibility_fixed(
                [type1], [type2], "Component", "Component"
            )
            result2 = converter._validate_type_compatibility_fixed(
                [type2], [type1], "Component", "Component"
            )

            assert result1 is True, f"{type1} -> {type2} should be compatible"
            assert result2 is True, f"{type2} -> {type1} should be compatible"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])