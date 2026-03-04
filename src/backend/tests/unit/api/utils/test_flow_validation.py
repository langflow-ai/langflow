"""Unit tests for flow_validation utility functions.

Tests validate_flow_custom_components for:
- Metadata forgery bypass prevention (is_edited/type spoofing)
- Recursive group/sub-flow node validation
- require_flow_custom_components_valid / require_flows_custom_components_valid HTTP 403 behavior
- Exception handling (fail-closed)
- Whitespace-only code edge case
- Graph.from_payload() integration (CustomComponentNotAllowedError)
"""

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from langflow.api.utils.flow_validation import (
    require_flow_custom_components_valid,
    require_flows_custom_components_valid,
    validate_flow_custom_components,
)
from lfx.exceptions.component import CustomComponentNotAllowedError

# Custom code that will not be in the hash allowlist
CUSTOM_CODE = """
from lfx.custom import Component

class MyCustomComponent(Component):
    display_name = "Evil Component"

    def build(self):
        return "pwned"
"""


def _make_node(node_id, node_type, code, *, edited=False, nested_flow=None):
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
        # Mock is_code_hash_allowed to return True (simulating hash match)
        with patch("lfx.custom.hash_validator.is_code_hash_allowed") as mock_hash:
            mock_hash.return_value = True
            flow_data = {
                "nodes": [_make_node("n1", "ChatInput", known_code, edited=False)],
            }
            blocked = validate_flow_custom_components(flow_data)
            assert len(blocked) == 0
            mock_hash.assert_called_once_with(known_code)


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
        with patch("lfx.custom.hash_validator.is_code_hash_allowed") as mock_hash:
            mock_hash.return_value = True

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


class TestRequireFlowCustomComponentsValid:
    """Tests for the require_* helpers that raise HTTPException(403)."""

    def test_raises_403_when_blocked(self):
        """require_flow_custom_components_valid raises 403 for custom code."""
        flow_data = {
            "nodes": [_make_node("n1", "CustomComponent", CUSTOM_CODE)],
        }

        with pytest.raises(HTTPException) as exc_info:
            require_flow_custom_components_valid(flow_data)

        assert exc_info.value.status_code == 403
        assert "custom components are not allowed" in exc_info.value.detail

    def test_passes_when_all_allowed(self):
        """require_flow_custom_components_valid does not raise for allowed code."""
        with patch("lfx.custom.hash_validator.is_code_hash_allowed") as mock_hash:
            mock_hash.return_value = True
            flow_data = {
                "nodes": [_make_node("n1", "ChatInput", "some_code")],
            }
            # Should not raise
            require_flow_custom_components_valid(flow_data)

    def test_passes_for_empty_flow(self):
        """require_flow_custom_components_valid does not raise for flows with no nodes."""
        require_flow_custom_components_valid({"nodes": []})

    def test_blocked_detail_includes_component_name(self):
        """The 403 detail message should include the blocked component display name."""
        flow_data = {
            "nodes": [_make_node("n1", "CustomComponent", CUSTOM_CODE)],
        }
        with pytest.raises(HTTPException) as exc_info:
            require_flow_custom_components_valid(flow_data)

        # The display name is extracted from the code's class definition
        assert "Evil Component" in exc_info.value.detail


class TestRequireFlowsCustomComponentsValid:
    """Tests for require_flows_custom_components_valid (multi-flow variant)."""

    def test_raises_403_when_any_flow_blocked(self):
        """Should raise 403 when any flow in the list has blocked components."""
        flows = [
            {"name": "Good Flow", "data": {"nodes": []}},
            {
                "name": "Bad Flow",
                "data": {"nodes": [_make_node("n1", "CustomComponent", CUSTOM_CODE)]},
            },
        ]
        with pytest.raises(HTTPException) as exc_info:
            require_flows_custom_components_valid(flows)

        assert exc_info.value.status_code == 403
        assert "Bad Flow" in exc_info.value.detail

    def test_passes_when_all_flows_clean(self):
        """Should not raise when all flows have only allowed components."""
        with patch("lfx.custom.hash_validator.is_code_hash_allowed") as mock_hash:
            mock_hash.return_value = True
            flows = [
                {"name": "Flow A", "data": {"nodes": [_make_node("n1", "ChatInput", "code_a")]}},
                {"name": "Flow B", "data": {"nodes": [_make_node("n2", "ChatInput", "code_b")]}},
            ]
            require_flows_custom_components_valid(flows)


class TestExceptionHandlingFailsClosed:
    """Tests that validation fails closed when is_code_hash_allowed raises."""

    def test_blocks_on_value_error(self):
        """ValueError from hash validation should result in blocking (fail-closed)."""
        with patch("lfx.custom.hash_validator.is_code_hash_allowed") as mock_hash:
            mock_hash.side_effect = ValueError("Settings unavailable")
            flow_data = {
                "nodes": [_make_node("n1", "ChatInput", "some_code")],
            }
            blocked = validate_flow_custom_components(flow_data)
            assert len(blocked) == 1
            assert blocked[0]["node_id"] == "n1"

    def test_blocks_on_file_not_found(self):
        """FileNotFoundError from missing hash files should result in blocking."""
        with patch("lfx.custom.hash_validator.is_code_hash_allowed") as mock_hash:
            mock_hash.side_effect = FileNotFoundError("hash history missing")
            flow_data = {
                "nodes": [_make_node("n1", "ChatInput", "some_code")],
            }
            blocked = validate_flow_custom_components(flow_data)
            assert len(blocked) == 1

    def test_blocks_on_unexpected_exception(self):
        """Unexpected exceptions should also result in blocking (fail-closed)."""
        with patch("lfx.custom.hash_validator.is_code_hash_allowed") as mock_hash:
            mock_hash.side_effect = RuntimeError("unexpected bug")
            flow_data = {
                "nodes": [_make_node("n1", "ChatInput", "some_code")],
            }
            blocked = validate_flow_custom_components(flow_data)
            assert len(blocked) == 1


class TestWhitespaceCodeEdgeCases:
    """Tests for whitespace-only and edge-case code values."""

    def test_whitespace_only_code_is_skipped(self):
        """Nodes with whitespace-only code should be treated as empty (skipped)."""
        flow_data = {
            "nodes": [_make_node("n1", "ChatInput", "   \n\t  ")],
        }
        # Whitespace-only code is falsy after strip, so it's skipped at the node level.
        # But if it somehow reaches is_code_hash_allowed, that returns False (fail-closed).
        # The _validate_nodes loop checks `if not code:` which only catches empty string.
        # Whitespace-only code will reach is_code_hash_allowed, which blocks it.
        blocked = validate_flow_custom_components(flow_data)
        # Whitespace-only code should be blocked (fail-closed from is_code_hash_allowed)
        assert len(blocked) == 1

    def test_none_code_value_is_skipped(self):
        """Nodes where code value is None should be skipped."""
        node = {
            "id": "n1",
            "data": {
                "type": "ChatInput",
                "node": {
                    "display_name": "Test",
                    "edited": False,
                    "template": {"code": {"value": None}},
                },
            },
        }
        flow_data = {"nodes": [node]}
        blocked = validate_flow_custom_components(flow_data)
        assert len(blocked) == 0

    def test_missing_code_field_entirely(self):
        """Nodes with no 'code' key in template should be skipped."""
        node = {
            "id": "n1",
            "data": {
                "type": "ChatInput",
                "node": {
                    "display_name": "Test",
                    "edited": False,
                    "template": {},
                },
            },
        }
        flow_data = {"nodes": [node]}
        blocked = validate_flow_custom_components(flow_data)
        assert len(blocked) == 0


class TestCustomComponentEndpoint403:
    """Tests that custom_component and custom_component_update endpoints gate on hash validation."""

    def test_custom_component_blocks_unknown_hash(self):
        """custom_component endpoint should raise 403 when hash is not allowed."""
        with patch("langflow.api.v1.endpoints.is_code_hash_allowed") as mock_hash:
            mock_hash.return_value = False

            # Import after patching
            import asyncio

            from langflow.api.v1.endpoints import custom_component
            from langflow.api.v1.schemas import CustomComponentRequest

            request = CustomComponentRequest(code=CUSTOM_CODE)
            # Create a mock user
            from unittest.mock import MagicMock

            mock_user = MagicMock()
            mock_user.id = "test-user-id"

            with pytest.raises(HTTPException) as exc_info:
                asyncio.get_event_loop().run_until_complete(custom_component(request, mock_user))

            assert exc_info.value.status_code == 403

    def test_custom_component_update_blocks_unknown_hash(self):
        """custom_component_update endpoint should raise 403 when hash is not allowed."""
        with patch("langflow.api.v1.endpoints.is_code_hash_allowed") as mock_hash:
            mock_hash.return_value = False

            import asyncio
            from unittest.mock import MagicMock

            from langflow.api.v1.endpoints import custom_component_update
            from langflow.api.v1.schemas import UpdateCustomComponentRequest

            request = MagicMock(spec=UpdateCustomComponentRequest)
            request.code = CUSTOM_CODE
            mock_user = MagicMock()
            mock_user.id = "test-user-id"

            with pytest.raises(HTTPException) as exc_info:
                asyncio.get_event_loop().run_until_complete(custom_component_update(request, mock_user))

            assert exc_info.value.status_code == 403
            # Verify the 403 is NOT downgraded to 400 by the outer except
            assert exc_info.value.status_code != 400


class TestGraphFromPayloadValidation:
    """Tests that Graph.from_payload() raises CustomComponentNotAllowedError."""

    def test_from_payload_raises_on_blocked_custom_code(self):
        """Graph.from_payload() should raise CustomComponentNotAllowedError for blocked custom code."""
        from lfx.graph.graph.base import Graph

        payload = {
            "nodes": [_make_node("n1", "CustomComponent", CUSTOM_CODE)],
            "edges": [],
        }

        with pytest.raises(CustomComponentNotAllowedError) as exc_info:
            Graph.from_payload(payload)

        assert len(exc_info.value.blocked_components) == 1
        assert exc_info.value.blocked_components[0]["node_id"] == "n1"
        assert "Evil Component" in str(exc_info.value)

    def test_from_payload_no_error_when_custom_components_allowed(self):
        """validate_flow_nodes() should be a no-op when allow_custom_components=True."""
        from lfx.custom.hash_validator import validate_flow_nodes

        nodes = [_make_node("n1", "CustomComponent", CUSTOM_CODE)]

        with patch("lfx.custom.hash_validator.get_settings_service") as mock_settings:
            mock_settings.return_value.settings.allow_custom_components = True
            # Should not raise — validation is a no-op when allow_custom_components=True
            validate_flow_nodes(nodes)

    def test_from_payload_allows_known_hash_code(self):
        """validate_flow_nodes() should succeed when all code hashes are allowed."""
        from lfx.custom.hash_validator import validate_flow_nodes

        nodes = [_make_node("n1", "ChatInput", "some_builtin_code")]

        with patch("lfx.custom.hash_validator.is_code_hash_allowed") as mock_hash:
            mock_hash.return_value = True
            # Should not raise
            validate_flow_nodes(nodes)

    def test_from_payload_validates_nested_group_nodes(self):
        """validate_flow_nodes() should catch blocked code inside group nodes."""
        from lfx.custom.hash_validator import validate_flow_nodes

        inner_node = _make_node("inner-1", "CustomComponent", CUSTOM_CODE)
        group_flow = {"data": {"nodes": [inner_node], "edges": []}}
        group_node = _make_node("group-1", "GroupNode", "", nested_flow=group_flow)

        with pytest.raises(CustomComponentNotAllowedError) as exc_info:
            validate_flow_nodes([group_node])

        assert exc_info.value.blocked_components[0]["node_id"] == "inner-1"


def _simulate_workflow_exception_handler(nodes):
    """Simulate the try/except pattern from workflow.py execute_sync_workflow."""
    from lfx.custom.hash_validator import validate_flow_nodes

    try:
        validate_flow_nodes(nodes)
    except CustomComponentNotAllowedError:
        raise
    except Exception as e:
        msg = f"Failed to build graph: {e!s}"
        raise RuntimeError(msg) from e


def _simulate_chat_exception_handler(nodes):
    """Simulate the try/except pattern from chat.py/build.py."""
    from lfx.custom.hash_validator import validate_flow_nodes

    try:
        validate_flow_nodes(nodes)
    except CustomComponentNotAllowedError:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class TestCustomComponentNotAllowedErrorPropagation:
    """Tests that CustomComponentNotAllowedError propagates through intermediate exception handlers."""

    def test_error_not_wrapped_by_workflow_validation(self):
        """CustomComponentNotAllowedError should not be wrapped as WorkflowValidationError."""
        nodes = [_make_node("n1", "CustomComponent", CUSTOM_CODE)]

        with pytest.raises(CustomComponentNotAllowedError):
            _simulate_workflow_exception_handler(nodes)

    def test_error_not_wrapped_as_http_500(self):
        """CustomComponentNotAllowedError should not be caught by generic except Exception → 500."""
        nodes = [_make_node("n1", "CustomComponent", CUSTOM_CODE)]

        with pytest.raises(CustomComponentNotAllowedError):
            _simulate_chat_exception_handler(nodes)

    def test_error_not_swallowed_by_agentic_utility_pattern(self):
        """CustomComponentNotAllowedError should not be caught by agentic try/except → dict pattern."""
        from lfx.custom.hash_validator import validate_flow_nodes

        nodes = [_make_node("n1", "CustomComponent", CUSTOM_CODE)]

        def _simulate_agentic_handler(nodes):
            try:
                validate_flow_nodes(nodes)
            except CustomComponentNotAllowedError:
                raise
            except Exception as e:
                return {"error": str(e)}
            return {"result": "ok"}

        with pytest.raises(CustomComponentNotAllowedError):
            _simulate_agentic_handler(nodes)

    def test_error_message_contains_component_names(self):
        """CustomComponentNotAllowedError message should include blocked component names."""
        blocked = [
            {"display_name": "Evil Component", "node_id": "n1", "class_name": "Evil"},
            {"display_name": "Bad Widget", "node_id": "n2", "class_name": "Bad"},
        ]
        error = CustomComponentNotAllowedError(blocked)
        assert "Evil Component" in str(error)
        assert "Bad Widget" in str(error)
        assert error.blocked_components == blocked
