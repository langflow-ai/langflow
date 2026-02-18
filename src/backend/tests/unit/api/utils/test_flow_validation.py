"""Unit tests for flow_validation utility functions.

Tests validate_flow_custom_components for:
- Metadata forgery bypass prevention (is_edited/type spoofing)
- Recursive group/sub-flow node validation
"""

from unittest.mock import patch

from langflow.api.utils.flow_validation import validate_flow_custom_components

# Custom code that will not be in the hash allowlist
CUSTOM_CODE = """
from lfx.custom import Component

class MyCustomComponent(Component):
    display_name = "Evil Component"

    def build(self):
        return "pwned"
"""


def _make_node(node_id, node_type, code, edited=False, nested_flow=None):
    """Helper to create a node dict for testing."""
    node = {
        "id": node_id,
        "data": {
            "type": node_type,
            "node": {
                "display_name": f"Display {node_id}",
                "edited": edited,
                "template": {"code": {"value": code}},
            },
        },
    }
    if nested_flow:
        node["data"]["node"]["flow"] = nested_flow
    return node


class TestMetadataForgeryPrevention:
    """Tests that validation cannot be bypassed by forging node metadata."""

    def test_blocks_custom_code_with_edited_false(self):
        """Forging edited=False should not bypass validation for custom code."""
        # An attacker sets edited=False and type=ChatInput but inserts custom code
        flow_data = {
            "nodes": [_make_node("n1", "ChatInput", CUSTOM_CODE, edited=False)],
        }

        blocked = validate_flow_custom_components(flow_data)
        assert len(blocked) == 1
        assert blocked[0]["node_id"] == "n1"

    def test_blocks_custom_code_with_forged_builtin_type(self):
        """Forging type to a built-in name should not bypass validation."""
        flow_data = {
            "nodes": [_make_node("n1", "OpenAIModel", CUSTOM_CODE, edited=False)],
        }

        blocked = validate_flow_custom_components(flow_data)
        assert len(blocked) == 1

    def test_allows_empty_code(self):
        """Nodes without code should always pass validation."""
        flow_data = {
            "nodes": [_make_node("n1", "ChatInput", "", edited=False)],
        }

        blocked = validate_flow_custom_components(flow_data)
        assert len(blocked) == 0

    def test_allows_known_hash_code(self):
        """Nodes with code matching the hash allowlist should pass."""
        known_code = """
from lfx.custom import Component

class KnownComponent(Component):
    display_name = "Known"
"""
        # Mock validate_code to return no errors (simulating hash match)
        with patch("langflow.api.utils.flow_validation.validate_code") as mock_validate:
            mock_validate.return_value = {"function": {"errors": []}, "imports": {"errors": []}}
            flow_data = {
                "nodes": [_make_node("n1", "ChatInput", known_code, edited=False)],
            }
            blocked = validate_flow_custom_components(flow_data)
            assert len(blocked) == 0
            mock_validate.assert_called_once_with(known_code)


class TestRecursiveGroupNodeValidation:
    """Tests that group/sub-flow nodes are recursively validated."""

    def test_blocks_custom_code_in_group_node(self):
        """Custom code inside a group node's nested flow should be blocked."""
        inner_node = _make_node("inner-1", "CustomComponent", CUSTOM_CODE)
        group_flow = {
            "data": {
                "nodes": [inner_node],
                "edges": [],
            }
        }
        # The group node itself has no code, but contains a nested flow
        group_node = _make_node("group-1", "GroupNode", "", nested_flow=group_flow)

        flow_data = {"nodes": [group_node]}

        blocked = validate_flow_custom_components(flow_data)
        assert len(blocked) == 1
        assert blocked[0]["node_id"] == "inner-1"

    def test_blocks_custom_code_in_deeply_nested_group(self):
        """Custom code in a deeply nested group should be blocked."""
        # Inner-most node with custom code
        inner_node = _make_node("deep-inner", "CustomComponent", CUSTOM_CODE)

        # Level 2 group
        level2_flow = {"data": {"nodes": [inner_node], "edges": []}}
        level2_node = _make_node("level2", "GroupNode", "", nested_flow=level2_flow)

        # Level 1 group
        level1_flow = {"data": {"nodes": [level2_node], "edges": []}}
        level1_node = _make_node("level1", "GroupNode", "", nested_flow=level1_flow)

        flow_data = {"nodes": [level1_node]}

        blocked = validate_flow_custom_components(flow_data)
        assert len(blocked) == 1
        assert blocked[0]["node_id"] == "deep-inner"

    def test_blocks_multiple_custom_components_across_groups(self):
        """Multiple custom components across top-level and nested groups should all be blocked."""
        # Top-level custom component
        top_node = _make_node("top-1", "CustomComponent", CUSTOM_CODE)

        # Nested custom component in a group
        inner_node = _make_node("inner-1", "CustomComponent", CUSTOM_CODE)
        group_flow = {"data": {"nodes": [inner_node], "edges": []}}
        group_node = _make_node("group-1", "GroupNode", "", nested_flow=group_flow)

        flow_data = {"nodes": [top_node, group_node]}

        blocked = validate_flow_custom_components(flow_data)
        assert len(blocked) == 2
        blocked_ids = {comp["node_id"] for comp in blocked}
        assert blocked_ids == {"top-1", "inner-1"}

    def test_allows_group_with_no_custom_code(self):
        """Group nodes with only built-in code should pass."""
        with patch("langflow.api.utils.flow_validation.validate_code") as mock_validate:
            mock_validate.return_value = {"function": {"errors": []}, "imports": {"errors": []}}

            inner_node = _make_node("inner-1", "ChatInput", "some_builtin_code", edited=False)
            group_flow = {"data": {"nodes": [inner_node], "edges": []}}
            group_node = _make_node("group-1", "GroupNode", "", nested_flow=group_flow)

            flow_data = {"nodes": [group_node]}

            blocked = validate_flow_custom_components(flow_data)
            assert len(blocked) == 0

    def test_handles_empty_nested_flow(self):
        """Group nodes with empty nested flow data should not error."""
        group_node = _make_node("group-1", "GroupNode", "", nested_flow={"data": {}})
        flow_data = {"nodes": [group_node]}

        blocked = validate_flow_custom_components(flow_data)
        assert len(blocked) == 0

    def test_handles_missing_nested_flow_data(self):
        """Group nodes with missing 'data' key in flow should not error."""
        group_node = _make_node("group-1", "GroupNode", "", nested_flow={})
        flow_data = {"nodes": [group_node]}

        blocked = validate_flow_custom_components(flow_data)
        assert len(blocked) == 0
