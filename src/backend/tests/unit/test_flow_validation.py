"""Tests for flow validation utilities (langflow.api.utils.flow_validation).

Covers:
- Blocking by edited flag (fallback path)
- Blocking by code comparison against known templates (primary path)
- Outdated component detection
- Template code lookup with renamed components (legacy alias)
- code_matches_any_template utility
- check_flow_and_raise integration
- Nested/group node recursion
- Security: edited=False with custom code still gets blocked
- Security: all execution endpoints validate flows before exec()
"""

import pytest
from langflow.api.utils.flow_validation import (
    _collect_all_template_codes,
    _find_template_code,
    _get_blocked_by_code,
    _get_blocked_by_edited_flag,
    _get_outdated_components,
    check_flow_and_raise,
    code_matches_any_template,
    validate_flow_custom_components,
    validate_flows_custom_components,
)

# ==================== Fixtures ====================


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


def _make_all_types_dict(
    components: dict[str, dict] | None = None,
) -> dict:
    """Helper to build an all_types_dict structure.

    Args:
        components: dict of {component_key: {"code": "..."}}
            e.g. {"ChatInput": {"code": "code_here"}}
    """
    if components is None:
        components = {
            "ChatInput": {"code": "chat_input_code"},
            "ChatOutput": {"code": "chat_output_code"},
        }

    result = {"default_category": {}}
    for key, info in components.items():
        entry = {
            "template": {"code": {"value": info["code"]}},
            "display_name": key,
        }
        result["default_category"][key] = entry
    return result


class TestGetBlockedByEditedFlag:
    def test_empty_nodes(self):
        assert _get_blocked_by_edited_flag([]) == []

    def test_no_edited_nodes(self):
        nodes = [_make_node(edited=False)]
        assert _get_blocked_by_edited_flag(nodes) == []

    def test_edited_node_blocked(self):
        nodes = [_make_node(edited=True, display_name="My Chat", node_id="n1")]
        result = _get_blocked_by_edited_flag(nodes)
        assert len(result) == 1
        assert "My Chat" in result[0]
        assert "n1" in result[0]

    def test_multiple_edited_nodes(self):
        nodes = [
            _make_node(edited=True, node_id="n1", display_name="A"),
            _make_node(edited=False, node_id="n2"),
            _make_node(edited=True, node_id="n3", display_name="B"),
        ]
        result = _get_blocked_by_edited_flag(nodes)
        assert len(result) == 2

    def test_nested_edited_node_blocked(self):
        inner = _make_node(edited=True, display_name="Inner", node_id="inner-1")
        outer = _make_node(edited=False, node_id="outer-1", nested_nodes=[inner])
        result = _get_blocked_by_edited_flag([outer])
        assert len(result) == 1
        assert "Inner" in result[0]

    def test_display_name_falls_back_to_type(self):
        nodes = [_make_node(edited=True, node_type="CustomType", node_id="n1")]
        result = _get_blocked_by_edited_flag(nodes)
        assert "CustomType" in result[0]


class TestCollectAllTemplateCodes:
    def test_empty_dict(self):
        assert _collect_all_template_codes({}) == set()

    def test_collects_codes(self):
        atd = _make_all_types_dict(
            {
                "A": {"code": "code_a"},
                "B": {"code": "code_b"},
            }
        )
        codes = _collect_all_template_codes(atd)
        assert codes == {"code_a", "code_b"}

    def test_skips_non_dict_categories(self):
        atd = {"category": "not_a_dict"}
        assert _collect_all_template_codes(atd) == set()

    def test_skips_empty_code(self):
        atd = {"cat": {"comp": {"template": {"code": {"value": ""}}}}}
        assert _collect_all_template_codes(atd) == set()

    def test_skips_missing_code_field(self):
        atd = {"cat": {"comp": {"template": {}}}}
        assert _collect_all_template_codes(atd) == set()


class TestGetBlockedByCode:
    def test_empty_nodes(self):
        assert _get_blocked_by_code([], set()) == []

    def test_known_code_not_blocked(self):
        nodes = [_make_node(code="known_code")]
        assert _get_blocked_by_code(nodes, {"known_code"}) == []

    def test_unknown_code_blocked(self):
        nodes = [_make_node(code="custom_code", display_name="Custom", node_id="n1")]
        result = _get_blocked_by_code(nodes, {"known_code"})
        assert len(result) == 1
        assert "Custom" in result[0]

    def test_edited_false_with_custom_code_still_blocked(self):
        """Security: edited=False does NOT prevent blocking when code is unknown."""
        nodes = [_make_node(code="evil_code", edited=False, display_name="Sneaky")]
        result = _get_blocked_by_code(nodes, {"legitimate_code"})
        assert len(result) == 1
        assert "Sneaky" in result[0]

    def test_nested_unknown_code_blocked(self):
        inner = _make_node(code="unknown_nested", display_name="Nested", node_id="inner")
        outer = _make_node(code="known", nested_nodes=[inner])
        result = _get_blocked_by_code([outer], {"known"})
        assert len(result) == 1
        assert "Nested" in result[0]

    def test_node_without_code_not_blocked(self):
        node = {
            "data": {
                "type": "NoCodeNode",
                "node": {"template": {}},
            }
        }
        assert _get_blocked_by_code([node], {"some_code"}) == []


class TestFindTemplateCode:
    def test_direct_key_match(self):
        atd = _make_all_types_dict({"ChatInput": {"code": "chat_code"}})
        assert _find_template_code("ChatInput", atd) == "chat_code"

    def test_no_match_returns_none(self):
        atd = _make_all_types_dict({"ChatInput": {"code": "chat_code"}})
        assert _find_template_code("NonExistent", atd) is None

    def test_legacy_alias_prompt(self):
        """'Prompt' should resolve to 'Prompt Template' via legacy alias."""
        atd = _make_all_types_dict(
            {
                "Prompt Template": {"code": "prompt_code"},
            }
        )
        assert _find_template_code("Prompt", atd) == "prompt_code"

    def test_direct_match_takes_precedence_over_alias(self):
        """If both direct key and alias target exist, direct key wins."""
        atd = _make_all_types_dict(
            {
                "Prompt": {"code": "direct_code"},
                "Prompt Template": {"code": "renamed_code"},
            }
        )
        assert _find_template_code("Prompt", atd) == "direct_code"


class TestCodeMatchesAnyTemplate:
    def test_matching_code(self):
        atd = _make_all_types_dict({"A": {"code": "my_code"}})
        assert code_matches_any_template("my_code", atd) is True

    def test_non_matching_code(self):
        atd = _make_all_types_dict({"A": {"code": "my_code"}})
        assert code_matches_any_template("other_code", atd) is False

    def test_empty_dict(self):
        assert code_matches_any_template("any", {}) is False


class TestGetOutdatedComponents:
    def test_current_code_not_outdated(self):
        atd = _make_all_types_dict({"ChatInput": {"code": "current"}})
        nodes = [_make_node(code="current", node_type="ChatInput")]
        assert _get_outdated_components(nodes, atd) == []

    def test_old_known_code_detected_as_outdated(self):
        """Node has code from a previous version of the same component type."""
        atd = _make_all_types_dict(
            {
                "ChatInput": {"code": "v2_code"},
                "OldComponent": {"code": "v1_code"},  # Old code exists as another component
            }
        )
        nodes = [_make_node(code="v1_code", node_type="ChatInput", display_name="Chat Input")]
        result = _get_outdated_components(nodes, atd)
        assert len(result) == 1
        assert "Chat Input" in result[0]

    def test_unknown_code_not_reported_as_outdated(self):
        """Unknown code is caught by _get_blocked_by_code, not here."""
        atd = _make_all_types_dict({"ChatInput": {"code": "current"}})
        nodes = [_make_node(code="totally_unknown", node_type="ChatInput")]
        assert _get_outdated_components(nodes, atd) == []

    def test_renamed_component_outdated_detection(self):
        """Outdated detection works for renamed components via legacy alias (Prompt → Prompt Template)."""
        atd = _make_all_types_dict(
            {
                "Prompt Template": {"code": "v2_prompt_code"},
                "SomeOther": {"code": "v1_prompt_code"},  # Old Prompt code matches this
            }
        )
        nodes = [_make_node(code="v1_prompt_code", node_type="Prompt", display_name="Prompt")]
        result = _get_outdated_components(nodes, atd)
        assert len(result) == 1
        assert "Prompt" in result[0]

    def test_nested_outdated_detection(self):
        atd = _make_all_types_dict(
            {
                "ChatInput": {"code": "v2"},
                "Legacy": {"code": "v1"},
            }
        )
        inner = _make_node(code="v1", node_type="ChatInput", display_name="Nested Chat")
        outer = _make_node(code="v2", node_type="ChatInput", nested_nodes=[inner])
        result = _get_outdated_components([outer], atd)
        assert len(result) == 1
        assert "Nested Chat" in result[0]


class TestValidateFlowCustomComponents:
    def test_none_flow_data(self):
        assert validate_flow_custom_components(None) == []

    def test_empty_flow_data(self):
        assert validate_flow_custom_components({}) == []

    def test_no_edited_components(self):
        flow_data = {"nodes": [_make_node(edited=False)]}
        assert validate_flow_custom_components(flow_data) == []

    def test_edited_components_detected(self):
        flow_data = {"nodes": [_make_node(edited=True, display_name="Edited")]}
        result = validate_flow_custom_components(flow_data)
        assert len(result) == 1
        assert "Edited" in result[0]


class TestValidateFlowsCustomComponents:
    def test_no_blocked_flows(self):
        flows = [{"name": "Flow1", "data": {"nodes": [_make_node(edited=False)]}}]
        assert validate_flows_custom_components(flows) == {}

    def test_blocked_flow_included(self):
        flows = [
            {"name": "Clean", "data": {"nodes": [_make_node(edited=False)]}},
            {"name": "Dirty", "data": {"nodes": [_make_node(edited=True, display_name="Bad")]}},
        ]
        result = validate_flows_custom_components(flows)
        assert "Dirty" in result
        assert "Clean" not in result


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

    def test_blocks_unknown_code_with_all_types_dict(self):
        """Primary path: unknown code is blocked even with edited=False."""
        atd = _make_all_types_dict({"ChatInput": {"code": "known_code"}})
        flow_data = {"nodes": [_make_node(code="evil_code", edited=False)]}
        with pytest.raises(ValueError, match="custom components are not allowed"):
            check_flow_and_raise(flow_data, allow_custom_components=False, all_types_dict=atd)

    def test_blocks_outdated_components(self):
        """Primary path: outdated code (known but wrong version) is blocked."""
        atd = _make_all_types_dict(
            {
                "ChatInput": {"code": "v2_code"},
                "Legacy": {"code": "v1_code"},
            }
        )
        flow_data = {"nodes": [_make_node(code="v1_code", node_type="ChatInput")]}
        with pytest.raises(ValueError, match="outdated components must be updated"):
            check_flow_and_raise(flow_data, allow_custom_components=False, all_types_dict=atd)

    def test_allows_current_code(self):
        """Primary path: current code passes."""
        atd = _make_all_types_dict({"ChatInput": {"code": "current_code"}})
        flow_data = {"nodes": [_make_node(code="current_code", node_type="ChatInput")]}
        # Should not raise
        check_flow_and_raise(flow_data, allow_custom_components=False, all_types_dict=atd)

    def test_fail_closed_when_all_types_dict_is_none(self):
        """When all_types_dict is None (cache not loaded), all flows are blocked.

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
        """Security test: a node with edited=False but custom code MUST be blocked.

        This is the core security property — the edited flag is client-controlled
        and must not be trusted when all_types_dict is available.
        """
        atd = _make_all_types_dict({"ChatInput": {"code": "legitimate_code"}})
        flow_data = {
            "nodes": [
                _make_node(
                    code="injected_malicious_code",
                    edited=False,  # Attacker sets this to bypass checks
                    display_name="Innocent Looking",
                )
            ]
        }
        with pytest.raises(ValueError, match="custom components are not allowed"):
            check_flow_and_raise(flow_data, allow_custom_components=False, all_types_dict=atd)


class TestEndpointValidationCoverage:
    """Verify that all execution endpoints have calls to validate custom code blocking.

    These are source-level tests that inspect the endpoint code to ensure
    validation is present. This catches regressions if someone adds a new
    endpoint or refactors an existing one without adding validation.
    """

    def _read_function_source(self, func) -> str:
        import inspect

        return inspect.getsource(func)

    def test_build_flow_validates_both_data_and_db_flow(self):
        """build_flow should validate both user-provided data AND stored flow.data."""
        from langflow.api.v1.chat import build_flow

        source = self._read_function_source(build_flow)
        # Should have TWO check_flow_and_raise calls (one for data, one for flow.data)
        assert source.count("check_flow_and_raise") >= 2, (
            "build_flow must call check_flow_and_raise for both user-provided data and DB flow.data"
        )

    def test_retrieve_vertices_order_validates_db_flow(self):
        """Deprecated retrieve_vertices_order must validate DB flow when data is None."""
        from langflow.api.v1.chat import retrieve_vertices_order

        source = self._read_function_source(retrieve_vertices_order)
        assert source.count("check_flow_and_raise") >= 2, (
            "retrieve_vertices_order must validate DB flow.data when user provides no data"
        )

    def test_build_vertex_validates_db_flow(self):
        """Deprecated build_vertex must validate DB flow before building from cache miss."""
        from langflow.api.v1.chat import build_vertex

        source = self._read_function_source(build_vertex)
        assert "check_flow_and_raise" in source, "build_vertex must call check_flow_and_raise before building from DB"

    def test_build_public_tmp_validates_db_flow(self):
        """build_public_tmp must validate stored flow data, not just user-provided data."""
        from langflow.api.v1.chat import build_public_tmp

        source = self._read_function_source(build_public_tmp)
        assert source.count("check_flow_and_raise") >= 2, (
            "build_public_tmp must validate both user-provided data and DB flow.data"
        )

    def test_run_flow_validates(self):
        """Run flow internal must call check_flow_and_raise."""
        from langflow.api.v1.endpoints import _run_flow_internal

        source = self._read_function_source(_run_flow_internal)
        assert "check_flow_and_raise" in source, "_run_flow_internal must call check_flow_and_raise"

    def test_webhook_run_flow_validates(self):
        """webhook_run_flow must call check_flow_and_raise."""
        from langflow.api.v1.endpoints import webhook_run_flow

        source = self._read_function_source(webhook_run_flow)
        assert "check_flow_and_raise" in source, "webhook_run_flow must call check_flow_and_raise"

    def test_experimental_run_flow_validates(self):
        """experimental_run_flow must call check_flow_and_raise."""
        from langflow.api.v1.endpoints import experimental_run_flow

        source = self._read_function_source(experimental_run_flow)
        assert "check_flow_and_raise" in source, "experimental_run_flow must call check_flow_and_raise"

    def test_v2_workflow_sync_validates(self):
        """V2 sync workflow must call check_flow_and_raise before building graph."""
        from langflow.api.v2.workflow import execute_sync_workflow

        source = self._read_function_source(execute_sync_workflow)
        assert "check_flow_and_raise" in source, (
            "execute_sync_workflow must call check_flow_and_raise to prevent custom code bypass via V2 API"
        )

    def test_v2_workflow_background_validates(self):
        """V2 background workflow must call check_flow_and_raise before building graph."""
        from langflow.api.v2.workflow import execute_workflow_background

        source = self._read_function_source(execute_workflow_background)
        assert "check_flow_and_raise" in source, (
            "execute_workflow_background must call check_flow_and_raise to prevent custom code bypass via V2 API"
        )

    def test_openai_responses_validates(self):
        """OpenAI Responses API must call check_flow_and_raise before running flow."""
        from langflow.api.v1.openai_responses import create_response

        source = self._read_function_source(create_response)
        assert "check_flow_and_raise" in source, (
            "create_response must call check_flow_and_raise to prevent custom code bypass via OpenAI API"
        )

    def test_mcp_call_tool_validates(self):
        """MCP handle_call_tool must call check_flow_and_raise before running flow."""
        from langflow.api.v1.mcp_utils import handle_call_tool

        source = self._read_function_source(handle_call_tool)
        assert "check_flow_and_raise" in source, (
            "handle_call_tool must call check_flow_and_raise to prevent custom code bypass via MCP"
        )

    def test_custom_component_create_checks_allow_custom(self):
        """POST /custom_component must check allow_custom_components."""
        from langflow.api.v1.endpoints import custom_component

        source = self._read_function_source(custom_component)
        assert "allow_custom_components" in source, "custom_component must check allow_custom_components setting"

    def test_custom_component_update_checks_allow_custom(self):
        """POST /custom_component/update must check allow_custom_components.

        This was a CRITICAL vulnerability — the update endpoint had no validation,
        allowing arbitrary code execution via exec() even with custom components disabled.
        """
        from langflow.api.v1.endpoints import custom_component_update

        source = self._read_function_source(custom_component_update)
        assert "allow_custom_components" in source, (
            "custom_component_update must check allow_custom_components setting. "
            "Without this check, arbitrary code can be executed via POST /custom_component/update."
        )
        assert "code_matches_any_template" in source, "custom_component_update must verify code against known templates"
