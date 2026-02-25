"""Tests for flow validation utilities (langflow.api.utils.flow_validation).

Covers:
- Hash-based validation: blocked (unknown type) and outdated (hash mismatch)
- code_hash_matches_any_template utility
- check_flow_and_raise integration
- Nested/group node recursion
- Security: edited=False with custom code still gets blocked
- Security: all execution endpoints validate flows before graph building and execution
"""

import hashlib
import inspect

import pytest
from langflow.api.utils.flow_validation import (
    _compute_code_hash,
    _get_invalid_components,
    check_flow_and_raise,
    code_hash_matches_any_template,
)
from langflow.api.v1.chat import build_flow, build_public_tmp, build_vertex, retrieve_vertices_order
from langflow.api.v1.endpoints import (
    _run_flow_internal,
    custom_component,
    custom_component_update,
    experimental_run_flow,
    webhook_run_flow,
)
from langflow.api.v1.mcp_utils import handle_call_tool
from langflow.api.v1.openai_responses import create_response
from langflow.api.v2.workflow import execute_sync_workflow, execute_workflow_background

# ==================== Helpers ====================


def _hash(code: str) -> str:
    """Compute code hash the same way the component index does."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()[:12]


def _make_node(
    *,
    node_type: str = "ChatInput",
    node_id: str = "node-1",
    code: str = "current_code",
    edited: bool = False,
    display_name: str | None = None,
    nested_nodes: list | None = None,
) -> dict:
    """Helper to build a flow node dict."""
    node_info = {
        "template": {"code": {"value": code}},
        "edited": edited,
    }
    if display_name:
        node_info["display_name"] = display_name
    if nested_nodes is not None:
        node_info["flow"] = {"data": {"nodes": nested_nodes}}
    return {
        "id": node_id,
        "data": {
            "type": node_type,
            "id": node_id,
            "node": node_info,
        },
    }


def _make_type_hash_dict(
    components: dict[str, str] | None = None,
) -> dict[str, str]:
    """Helper to build a type_to_current_hash dict.

    Args:
        components: dict of {component_type: code_string}
            The code is hashed to produce the expected hash.
    """
    if components is None:
        components = {
            "ChatInput": "chat_input_code",
            "ChatOutput": "chat_output_code",
        }
    return {comp_type: _hash(code) for comp_type, code in components.items()}


# ==================== Tests ====================


class TestComputeCodeHash:
    def test_returns_12_char_hex(self):
        result = _compute_code_hash("some code")
        assert len(result) == 12
        assert all(c in "0123456789abcdef" for c in result)

    def test_consistent(self):
        assert _compute_code_hash("code") == _compute_code_hash("code")

    def test_different_codes_different_hashes(self):
        assert _compute_code_hash("code_a") != _compute_code_hash("code_b")


class TestGetInvalidComponents:
    def test_empty_nodes(self):
        blocked, outdated = _get_invalid_components([], {})
        assert blocked == []
        assert outdated == []

    def test_current_code_passes(self):
        hash_dict = _make_type_hash_dict({"ChatInput": "current_code"})
        nodes = [_make_node(code="current_code", node_type="ChatInput")]
        blocked, outdated = _get_invalid_components(nodes, hash_dict)
        assert blocked == []
        assert outdated == []

    def test_unknown_type_is_blocked(self):
        hash_dict = _make_type_hash_dict({"ChatInput": "code"})
        nodes = [_make_node(code="anything", node_type="TotallyCustom", display_name="Custom", node_id="n1")]
        blocked, outdated = _get_invalid_components(nodes, hash_dict)
        assert len(blocked) == 1
        assert "Custom" in blocked[0]
        assert outdated == []

    def test_hash_mismatch_is_outdated(self):
        hash_dict = _make_type_hash_dict({"ChatInput": "v2_code"})
        nodes = [_make_node(code="v1_code", node_type="ChatInput", display_name="Chat Input")]
        blocked, outdated = _get_invalid_components(nodes, hash_dict)
        assert blocked == []
        assert len(outdated) == 1
        assert "Chat Input" in outdated[0]

    def test_edited_false_with_custom_code_still_blocked(self):
        """Security: edited=False does NOT prevent blocking when code is unknown type."""
        hash_dict = _make_type_hash_dict({"ChatInput": "legitimate_code"})
        nodes = [_make_node(code="evil_code", node_type="UnknownType", edited=False, display_name="Sneaky")]
        blocked, _outdated = _get_invalid_components(nodes, hash_dict)
        assert len(blocked) == 1
        assert "Sneaky" in blocked[0]

    def test_edited_false_with_modified_code_is_outdated(self):
        """Security: edited=False with modified code for a known type is caught as outdated."""
        hash_dict = _make_type_hash_dict({"ChatInput": "legitimate_code"})
        nodes = [_make_node(code="modified_code", node_type="ChatInput", edited=False, display_name="Sneaky")]
        blocked, outdated = _get_invalid_components(nodes, hash_dict)
        assert blocked == []
        assert len(outdated) == 1
        assert "Sneaky" in outdated[0]

    def test_nested_unknown_type_blocked(self):
        hash_dict = _make_type_hash_dict({"ChatInput": "known"})
        inner = _make_node(code="anything", node_type="CustomType", display_name="Nested", node_id="inner")
        outer = _make_node(code="known", node_type="ChatInput", nested_nodes=[inner])
        blocked, _outdated = _get_invalid_components([outer], hash_dict)
        assert len(blocked) == 1
        assert "Nested" in blocked[0]

    def test_nested_outdated_detection(self):
        hash_dict = _make_type_hash_dict({"ChatInput": "v2"})
        inner = _make_node(code="v1", node_type="ChatInput", display_name="Nested Chat")
        outer = _make_node(code="v2", node_type="ChatInput", nested_nodes=[inner])
        blocked, outdated = _get_invalid_components([outer], hash_dict)
        assert blocked == []
        assert len(outdated) == 1
        assert "Nested Chat" in outdated[0]

    def test_node_without_code_skipped(self):
        hash_dict = _make_type_hash_dict({"ChatInput": "code"})
        node = {
            "data": {
                "type": "NoCodeNode",
                "node": {"template": {}},
            }
        }
        blocked, outdated = _get_invalid_components([node], hash_dict)
        assert blocked == []
        assert outdated == []


class TestCodeHashMatchesAnyTemplate:
    def test_matching_code(self):
        known = {_hash("my_code")}
        assert code_hash_matches_any_template("my_code", known) is True

    def test_non_matching_code(self):
        known = {_hash("my_code")}
        assert code_hash_matches_any_template("other_code", known) is False

    def test_empty_set(self):
        assert code_hash_matches_any_template("any", set()) is False


class TestCheckFlowAndRaise:
    def test_allows_when_custom_components_enabled(self):
        """Should not raise when allow_custom_components=True."""
        flow_data = {"nodes": [_make_node(code="custom_evil_code", edited=True)]}
        # Should not raise
        check_flow_and_raise(flow_data, allow_custom_components=True)

    def test_none_flow_data_ok(self):
        check_flow_and_raise(None, allow_custom_components=False)

    def test_empty_nodes_ok(self):
        check_flow_and_raise({"nodes": []}, allow_custom_components=False)

    def test_blocks_unknown_type(self):
        """Primary path: unknown component type is blocked even with edited=False."""
        hash_dict = _make_type_hash_dict({"ChatInput": "known_code"})
        flow_data = {"nodes": [_make_node(code="evil_code", node_type="CustomEvil", edited=False)]}
        with pytest.raises(ValueError, match="custom components are not allowed"):
            check_flow_and_raise(flow_data, allow_custom_components=False, type_to_current_hash=hash_dict)

    def test_blocks_outdated_components(self):
        """Primary path: outdated code (hash mismatch for known type) is blocked."""
        hash_dict = _make_type_hash_dict({"ChatInput": "v2_code"})
        flow_data = {"nodes": [_make_node(code="v1_code", node_type="ChatInput")]}
        with pytest.raises(ValueError, match="outdated components must be updated"):
            check_flow_and_raise(flow_data, allow_custom_components=False, type_to_current_hash=hash_dict)

    def test_allows_current_code(self):
        """Primary path: current code passes."""
        hash_dict = _make_type_hash_dict({"ChatInput": "current_code"})
        flow_data = {"nodes": [_make_node(code="current_code", node_type="ChatInput")]}
        # Should not raise
        check_flow_and_raise(flow_data, allow_custom_components=False, type_to_current_hash=hash_dict)

    def test_fail_closed_when_hash_dict_is_none(self):
        """When type_to_current_hash is None (cache not loaded), all flows are blocked.

        This is the fail-closed behavior: if we can't verify code against templates,
        we block execution rather than falling back to the client-controlled edited flag.
        """
        flow_data = {"nodes": [_make_node(edited=False)]}
        with pytest.raises(ValueError, match="server is still initializing"):
            check_flow_and_raise(flow_data, allow_custom_components=False)

    def test_fail_closed_blocks_edited_true_without_cache(self):
        """Fail-closed blocks even edited=True nodes when cache is unavailable."""
        flow_data = {"nodes": [_make_node(edited=True, display_name="Edited")]}
        with pytest.raises(ValueError, match="server is still initializing"):
            check_flow_and_raise(flow_data, allow_custom_components=False)

    def test_security_edited_false_custom_code_blocked(self):
        """Security test: a node with edited=False but modified code MUST be caught.

        This is the core security property — the edited flag is client-controlled
        and must not be trusted when type_to_current_hash is available.
        """
        hash_dict = _make_type_hash_dict({"ChatInput": "legitimate_code"})
        flow_data = {
            "nodes": [
                _make_node(
                    code="injected_malicious_code",
                    node_type="ChatInput",
                    edited=False,  # Attacker sets this to bypass checks
                    display_name="Innocent Looking",
                )
            ]
        }
        with pytest.raises(ValueError, match="outdated components must be updated"):
            check_flow_and_raise(flow_data, allow_custom_components=False, type_to_current_hash=hash_dict)


class TestEndpointValidationCoverage:
    """Source-level tests verifying all execution endpoints call check_flow_and_raise.

    This catches regressions if someone adds a new endpoint or refactors
    an existing one without adding validation.
    """

    @staticmethod
    def _source(func) -> str:
        return inspect.getsource(func)

    def test_build_flow_validates_both_data_and_db_flow(self):
        source = self._source(build_flow)
        assert source.count("check_flow_and_raise") >= 2, (
            "build_flow must call check_flow_and_raise for both user-provided data and DB flow.data"
        )

    def test_retrieve_vertices_order_validates_db_flow(self):
        source = self._source(retrieve_vertices_order)
        assert source.count("check_flow_and_raise") >= 2, (
            "retrieve_vertices_order must validate DB flow.data when user provides no data"
        )

    def test_build_vertex_validates_db_flow(self):
        source = self._source(build_vertex)
        assert "check_flow_and_raise" in source, "build_vertex must call check_flow_and_raise before building from DB"

    def test_build_public_tmp_validates_db_flow(self):
        source = self._source(build_public_tmp)
        assert source.count("check_flow_and_raise") >= 2, (
            "build_public_tmp must validate both user-provided data and DB flow.data"
        )

    def test_run_flow_validates(self):
        source = self._source(_run_flow_internal)
        assert "check_flow_and_raise" in source, "_run_flow_internal must call check_flow_and_raise"

    def test_webhook_run_flow_validates(self):
        source = self._source(webhook_run_flow)
        assert "check_flow_and_raise" in source, "webhook_run_flow must call check_flow_and_raise"

    def test_experimental_run_flow_validates(self):
        source = self._source(experimental_run_flow)
        assert "check_flow_and_raise" in source, "experimental_run_flow must call check_flow_and_raise"

    def test_v2_workflow_sync_validates(self):
        source = self._source(execute_sync_workflow)
        assert "check_flow_and_raise" in source, (
            "execute_sync_workflow must call check_flow_and_raise to prevent custom code bypass via V2 API"
        )

    def test_v2_workflow_background_validates(self):
        source = self._source(execute_workflow_background)
        assert "check_flow_and_raise" in source, (
            "execute_workflow_background must call check_flow_and_raise to prevent custom code bypass via V2 API"
        )

    def test_openai_responses_validates(self):
        source = self._source(create_response)
        assert "check_flow_and_raise" in source, (
            "create_response must call check_flow_and_raise to prevent custom code bypass via OpenAI API"
        )

    def test_mcp_call_tool_validates(self):
        source = self._source(handle_call_tool)
        assert "check_flow_and_raise" in source, (
            "handle_call_tool must call check_flow_and_raise to prevent custom code bypass via MCP"
        )

    def test_custom_component_create_checks_allow_custom(self):
        source = self._source(custom_component)
        assert "allow_custom_components" in source, "custom_component must check allow_custom_components setting"

    def test_custom_component_update_checks_allow_custom(self):
        source = self._source(custom_component_update)
        assert "allow_custom_components" in source, (
            "custom_component_update must check allow_custom_components setting. "
            "Without this check, arbitrary code can be executed via POST /custom_component/update."
        )
        assert "code_hash_matches_any_template" in source, (
            "custom_component_update must verify code hash against known templates"
        )
