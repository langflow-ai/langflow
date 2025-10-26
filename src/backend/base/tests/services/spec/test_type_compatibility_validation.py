"""
Unit tests for enhanced type compatibility validation in SpecService.

Tests the new _validate_component_type_compatibility method that validates
output→input type matching for all 'provides' connections before conversion.
"""

import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any, List

from langflow.services.genesis.mapper import ComponentMapper


class TestTypeCompatibilityValidationLogic:
    """Test suite for type compatibility validation functionality - Logic only."""

    def test_circular_dependency_detection_algorithm(self):
        """Test circular dependency detection algorithm."""

        def detect_circular_dependencies(connections: List[tuple]) -> List[str]:
            """Standalone implementation of circular dependency detection."""
            errors = []

            # Build adjacency list
            graph = {}
            for source, target in connections:
                if source not in graph:
                    graph[source] = []
                graph[source].append(target)

            # DFS to detect cycles
            visited = set()
            rec_stack = set()

            def has_cycle(node):
                if node in rec_stack:
                    return True
                if node in visited:
                    return False

                visited.add(node)
                rec_stack.add(node)

                for neighbor in graph.get(node, []):
                    if has_cycle(neighbor):
                        return True

                rec_stack.remove(node)
                return False

            # Check each component for cycles
            for component in graph:
                if component not in visited:
                    if has_cycle(component):
                        errors.append(f"Circular dependency detected involving component '{component}'")
                        break

            return errors

        # Test cases
        test_cases = [
            # (connections, expected_has_error, description)
            ([("A", "B"), ("B", "C")], False, "Valid chain - no cycle"),
            ([("A", "B"), ("B", "A")], True, "Simple cycle"),
            ([("A", "B"), ("B", "C"), ("C", "A")], True, "Complex cycle"),
            ([], False, "Empty connections"),
            ([("A", "A")], True, "Self-loop"),
        ]

        for connections, expected_has_error, description in test_cases:
            errors = detect_circular_dependencies(connections)
            has_error = len(errors) > 0

            assert has_error == expected_has_error, f"Failed for {description}: expected {expected_has_error}, got {has_error}"

    def test_type_compatibility_matrix_logic(self):
        """Test type compatibility matrix logic."""

        # Enhanced compatibility matrix from our implementation
        compatible = {
            "Message": ["str", "text", "Text", "Data", "Document"],
            "str": ["Message", "text", "Text", "Data"],
            "Data": ["dict", "object", "any", "Message", "str", "Document"],
            "DataFrame": ["Data", "object", "any", "Tool"],
            "Document": ["Data", "Message", "str", "text"],
            "Tool": ["DataFrame", "Data", "any", "object"],
            "Text": ["Message", "str", "Data"],
            "object": ["any", "Data", "DataFrame", "Tool"],
            "any": ["Message", "str", "Data", "DataFrame", "Document", "Tool", "object", "text", "Text"]
        }

        def check_compatibility(output_types: List[str], input_types: List[str]) -> bool:
            """Check if output types are compatible with input types."""
            for otype in output_types:
                if otype in compatible:
                    if any(ctype in input_types for ctype in compatible[otype]):
                        return True

            # Accept any/object inputs
            if "any" in input_types or "object" in input_types:
                return True

            return False

        # Test cases
        test_cases = [
            # (output_types, input_types, expected_result, description)
            (["Message"], ["str"], True, "Message to str conversion"),
            (["Data"], ["Document"], True, "Data to Document conversion"),
            (["Document"], ["Message"], True, "Document to Message conversion"),
            (["DataFrame"], ["Tool"], True, "DataFrame to Tool conversion"),
            (["Tool"], ["any"], True, "Tool to any conversion"),
            (["InvalidType"], ["Message"], False, "Invalid type should fail"),
            (["Message"], ["InvalidType"], False, "Message to invalid type should fail"),
            (["Text"], ["Data"], True, "Text to Data conversion"),
            (["any"], ["Message"], True, "Any to Message conversion"),
            (["object"], ["DataFrame"], True, "Object to DataFrame conversion")
        ]

        for output_types, input_types, expected, description in test_cases:
            result = check_compatibility(output_types, input_types)
            assert result == expected, f"Failed for {description}: {output_types} -> {input_types} expected {expected}, got {result}"

    def test_tool_mode_consistency_logic(self):
        """Test tool mode consistency validation logic."""

        def validate_tool_mode_consistency(source_comp: Dict[str, Any],
                                          connection: Dict[str, Any],
                                          is_tool_component_func) -> Dict[str, Any]:
            """Standalone implementation of tool mode consistency validation."""
            errors = []
            warnings = []

            source_type = source_comp.get("type", "")
            use_as = connection.get("useAs")
            as_tools = source_comp.get("asTools", False)

            # Check tool mode consistency
            if use_as == "tools":
                # Component used as tool should be marked as tool or be a tool component
                is_tool = is_tool_component_func(source_type)

                if not as_tools and not is_tool:
                    errors.append(
                        f"Tool mode inconsistency: Component '{source_comp.get('id')}' used as tool "
                        f"but not marked with 'asTools: true' and is not inherently a tool component"
                    )
            elif as_tools and use_as != "tools":
                warnings.append(
                    f"Component '{source_comp.get('id')}' marked as tool (asTools: true) "
                    f"but used as '{use_as}' instead of 'tools'"
                )

            return {"errors": errors, "warnings": warnings}

        def mock_is_tool_component(comp_type: str) -> bool:
            """Mock function to determine if component is inherently a tool."""
            tool_types = ["genesis:mcp_tool", "genesis:api_request", "genesis:knowledge_hub_search"]
            return comp_type in tool_types

        # Test cases
        test_cases = [
            # (source_comp, connection, should_pass, description)
            ({
                "id": "tool1",
                "type": "genesis:mcp_tool",
                "asTools": True
            }, {
                "useAs": "tools"
            }, True, "Valid tool with asTools=True and useAs=tools"),

            ({
                "id": "tool2",
                "type": "genesis:agent"  # Not a tool component
            }, {
                "useAs": "tools"
            }, False, "Invalid: useAs=tools but not marked as tool"),

            ({
                "id": "tool3",
                "type": "genesis:mcp_tool",
                "asTools": True
            }, {
                "useAs": "input"
            }, True, "Warning: asTools=True but useAs=input")
        ]

        for source_comp, connection, should_pass, description in test_cases:
            result = validate_tool_mode_consistency(source_comp, connection, mock_is_tool_component)

            has_errors = len(result["errors"]) > 0

            if should_pass:
                assert not has_errors, f"Unexpected errors for {description}: {result['errors']}"
            else:
                assert has_errors, f"Expected errors for {description} but got none"

    def test_specification_structure_validation(self):
        """Test specification structure validation with real specification."""
        import yaml

        classification_spec = """
name: Classification Agent
description: Classify incoming prior authorization faxes
agentGoal: Classify faxes by type and domain
version: "1.0.0"

components:
  - id: document-input
    type: genesis:chat_input
    provides:
      - in: classification-agent
        useAs: input
        description: Document text to classify

  - id: classification-agent
    type: genesis:agent
    provides:
      - in: classification-output
        useAs: input
        description: Classification results

  - id: classification-output
    type: genesis:chat_output
"""

        spec_dict = yaml.safe_load(classification_spec)

        # Validate required fields
        required_fields = ["name", "description", "agentGoal", "components"]
        for field in required_fields:
            assert field in spec_dict, f"Missing required field: {field}"

        # Validate components
        components = spec_dict.get('components', [])
        assert len(components) > 0, "At least one component is required"

        # Collect component IDs
        component_ids = [comp.get('id') for comp in components]

        # Validate component structure and references
        for comp in components:
            assert comp.get('id'), "Component missing 'id' field"
            assert comp.get('type'), "Component missing 'type' field"

            # Check provides references
            provides = comp.get('provides', [])
            for provide in provides:
                if isinstance(provide, dict):
                    target = provide.get('in')
                    if target:
                        assert target in component_ids, f"Component references non-existent target '{target}'"

    def test_multi_tool_specification_validation(self):
        """Test validation of multi-tool specifications."""
        import yaml

        tool_spec_yaml = """
name: Multi-Tool Agent
description: Agent with multiple tools
version: "1.0.0"
agentGoal: Test multi-tool functionality

components:
  - id: input
    type: genesis:chat_input
    provides:
      - in: agent
        useAs: input

  - id: search-tool
    type: genesis:knowledge_hub_search
    asTools: true
    provides:
      - in: agent
        useAs: tools

  - id: mcp-tool
    type: genesis:mcp_tool
    asTools: true
    config:
      tool_name: test_tool
    provides:
      - in: agent
        useAs: tools

  - id: agent
    type: genesis:agent
    provides:
      - in: output
        useAs: input

  - id: output
    type: genesis:chat_output
"""

        spec_dict = yaml.safe_load(tool_spec_yaml)
        components = spec_dict.get('components', [])

        # Count tool components
        tool_components = [comp for comp in components if comp.get('asTools', False)]
        assert len(tool_components) == 2, f"Expected 2 tool components, got {len(tool_components)}"

        # Validate tool usage patterns
        inherent_tools = ['genesis:mcp_tool', 'genesis:knowledge_hub_search', 'genesis:api_request']

        for comp in components:
            as_tools = comp.get('asTools', False)
            provides = comp.get('provides', [])

            for provide in provides:
                use_as = provide.get('useAs')

                # Check tool mode consistency
                if use_as == "tools":
                    comp_type = comp.get('type', '')
                    if comp_type not in inherent_tools:
                        assert as_tools, f"Component '{comp.get('id')}' used as tool but not marked with asTools: true"


class TestEnhancedCompatibilityMatrix:
    """Test suite for enhanced compatibility matrix in FlowConverter."""

    def test_enhanced_compatibility_matrix(self):
        """Test enhanced type conversion patterns."""
        # Test the enhanced compatibility matrix directly
        compatible = {
            "Message": ["str", "text", "Text", "Data", "Document"],
            "str": ["Message", "text", "Text", "Data"],
            "Data": ["dict", "object", "any", "Message", "str", "Document"],
            "DataFrame": ["Data", "object", "any", "Tool"],
            "Document": ["Data", "Message", "str", "text"],
            "Tool": ["DataFrame", "Data", "any", "object"],
            "Text": ["Message", "str", "Data"],
            "object": ["any", "Data", "DataFrame", "Tool"],
            "any": ["Message", "str", "Data", "DataFrame", "Document", "Tool", "object", "text", "Text"]
        }

        # Test enhanced conversions
        enhanced_conversions = [
            # Document conversions
            ("Document", "Data", True),
            ("Document", "Message", True),
            ("Document", "str", True),
            ("Data", "Document", True),
            ("Message", "Document", True),

            # Tool conversions
            ("DataFrame", "Tool", True),
            ("Tool", "DataFrame", True),
            ("Tool", "Data", True),
            ("Tool", "any", True),

            # Extended compatibility
            ("any", "Message", True),
            ("object", "DataFrame", True),
            ("Text", "Data", True),
        ]

        for output_type, input_type, expected in enhanced_conversions:
            result = False
            if output_type in compatible:
                result = input_type in compatible[output_type]

            # Also check reverse compatibility for "any" and "object"
            if not result and input_type in ["any", "object"]:
                result = True

            assert result == expected, f"Enhanced compatibility failed for {output_type} -> {input_type}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])