"""Tests for propose_field_edit -- JSON Patch generation and validation.

Tests the full pipeline: validation, patch generation, dry run, event emission.
"""

import copy
import json

import jsonpatch
from lfx.graph.flow_builder.builder import build_flow_from_spec
from lfx.mcp.flow_builder_tools import (
    ConfigureComponent,
    ProposeFieldEdit,
    drain_flow_events,
    init_working_flow,
    reset_working_flow,
    set_propose_existing_edits,
)

# LanguageModelComponent: in-tree model type (provider model components live
# in bundle packages not installed in this env).
SIMPLE_FLOW_SPEC = """\
name: Test Flow
nodes:
  A: ChatInput
  B: LanguageModelComponent
  C: ChatOutput
edges:
  A.message -> B.input_value
  B.text_output -> C.input_value
"""


def _build_test_flow():
    """Build a real flow for testing."""
    result = build_flow_from_spec(SIMPLE_FLOW_SPEC)
    assert "flow" in result
    return result["flow"]


def _get_component_id(flow, component_type):
    """Find a component ID by type."""
    for node in flow["data"]["nodes"]:
        if node["data"]["type"] == component_type:
            return node["data"]["id"]
    msg = f"No {component_type} in flow"
    raise ValueError(msg)


def _tool_row(name: str, description: str) -> dict:
    return {
        "name": name,
        "description": description,
        "tags": [name],
        "status": True,
        "approval_actions": ["approve"],
        "display_name": "message",
        "display_description": "Executes another flow.",
        "readonly": False,
        "args": {"input_value": {"type": "string", "title": "Input Value"}},
        "future_metadata": {"preserve": True},
    }


def _set_tools_metadata(flow: dict, component_id: str, rows: list[dict]) -> None:
    for node in flow["data"]["nodes"]:
        if node["data"]["id"] == component_id:
            node["data"]["node"]["template"]["tools_metadata"] = {
                "type": "tools",
                "value": copy.deepcopy(rows),
            }
            return
    msg = f"Component {component_id} not found"
    raise ValueError(msg)


class TestProposeFieldEditValidation:
    def test_rejects_unknown_component_id(self):
        reset_working_flow()
        flow = _build_test_flow()
        init_working_flow(flow, "test-flow-id")

        tool = ProposeFieldEdit()
        tool.set(component_id="FakeComponent-12345", field_name="input_value", new_value="hello")
        result = tool.propose_field_edit()

        assert "error" in result.data
        assert "not found" in result.data["error"].lower()
        assert len(drain_flow_events()) == 0  # no event on failure

    def test_rejects_unknown_field_name(self):
        reset_working_flow()
        flow = _build_test_flow()
        init_working_flow(flow, "test-flow-id")
        comp_id = _get_component_id(flow, "ChatInput")

        tool = ProposeFieldEdit()
        tool.set(component_id=comp_id, field_name="nonexistent_field", new_value="hello")
        result = tool.propose_field_edit()

        assert "error" in result.data
        assert "not found" in result.data["error"].lower()
        assert len(drain_flow_events()) == 0

    def test_rejects_when_no_working_flow(self):
        reset_working_flow()

        tool = ProposeFieldEdit()
        tool.set(component_id="ChatInput-abc", field_name="input_value", new_value="hello")
        result = tool.propose_field_edit()

        assert "error" in result.data
        assert len(drain_flow_events()) == 0


class TestProposeFieldEditPatchGeneration:
    def test_generates_valid_json_patch(self):
        reset_working_flow()
        flow = _build_test_flow()
        init_working_flow(flow, "test-flow-id")
        comp_id = _get_component_id(flow, "ChatInput")

        tool = ProposeFieldEdit()
        tool.set(component_id=comp_id, field_name="input_value", new_value="hello world")
        result = tool.propose_field_edit()

        assert "error" not in result.data
        events = drain_flow_events()
        assert len(events) == 1

        event = events[0]
        assert event["action"] == "edit_field"
        assert event["component_id"] == comp_id
        assert event["field"] == "input_value"
        assert event["new_value"] == "hello world"
        assert "patch" in event

        # Verify the patch is valid JSON Patch
        patch = jsonpatch.JsonPatch(event["patch"])
        assert len(list(patch)) == 1

    def test_patch_applies_correctly(self):
        """The generated patch, when applied, actually changes the field."""
        reset_working_flow()
        flow = _build_test_flow()
        init_working_flow(flow, "test-flow-id")
        comp_id = _get_component_id(flow, "ChatInput")

        tool = ProposeFieldEdit()
        tool.set(component_id=comp_id, field_name="input_value", new_value="patched!")
        tool.propose_field_edit()

        events = drain_flow_events()
        patch = jsonpatch.JsonPatch(events[0]["patch"])

        # Apply to a fresh copy
        patched_flow = patch.apply(copy.deepcopy(flow))

        # Find the node and verify the value changed
        for node in patched_flow["data"]["nodes"]:
            if node["data"]["id"] == comp_id:
                assert node["data"]["node"]["template"]["input_value"]["value"] == "patched!"
                break
        else:
            msg = "Component not found in patched flow"
            raise AssertionError(msg)

    def test_captures_old_value(self):
        reset_working_flow()
        flow = _build_test_flow()
        init_working_flow(flow, "test-flow-id")
        comp_id = _get_component_id(flow, "ChatInput")

        # Set a known value first
        for node in flow["data"]["nodes"]:
            if node["data"]["id"] == comp_id:
                node["data"]["node"]["template"]["input_value"]["value"] = "original"

        tool = ProposeFieldEdit()
        tool.set(component_id=comp_id, field_name="input_value", new_value="changed")
        tool.propose_field_edit()

        events = drain_flow_events()
        assert events[0]["old_value"] == "original"
        assert events[0]["new_value"] == "changed"

    def test_includes_description(self):
        reset_working_flow()
        flow = _build_test_flow()
        init_working_flow(flow, "test-flow-id")
        comp_id = _get_component_id(flow, "ChatInput")

        tool = ProposeFieldEdit()
        tool.set(component_id=comp_id, field_name="input_value", new_value="test")
        tool.propose_field_edit()

        events = drain_flow_events()
        assert "description" in events[0]
        assert "input_value" in events[0]["description"]


class TestProposeFieldEditDryRun:
    def test_dry_run_catches_bad_patch(self):
        """If the patch somehow can't be applied, it should fail before emitting."""
        reset_working_flow()
        flow = _build_test_flow()
        init_working_flow(flow, "test-flow-id")
        comp_id = _get_component_id(flow, "ChatInput")

        # Corrupt the flow so the patch path is invalid
        flow["data"]["nodes"] = []

        tool = ProposeFieldEdit()
        tool.set(component_id=comp_id, field_name="input_value", new_value="hello")
        result = tool.propose_field_edit()

        # Should fail because the node was removed
        assert "error" in result.data
        assert len(drain_flow_events()) == 0


class TestProposeFieldEditMultiple:
    def test_multiple_edits_produce_multiple_events(self):
        reset_working_flow()
        flow = _build_test_flow()
        init_working_flow(flow, "test-flow-id")
        input_id = _get_component_id(flow, "ChatInput")
        model_id = _get_component_id(flow, "LanguageModelComponent")

        tool1 = ProposeFieldEdit()
        tool1.set(component_id=input_id, field_name="input_value", new_value="hello")
        tool1.propose_field_edit()

        tool2 = ProposeFieldEdit()
        tool2.set(component_id=model_id, field_name="temperature", new_value="0.5")
        tool2.propose_field_edit()

        events = drain_flow_events()
        assert len(events) == 2
        assert events[0]["component_id"] == input_id
        assert events[1]["component_id"] == model_id

    def test_each_event_has_unique_id(self):
        reset_working_flow()
        flow = _build_test_flow()
        init_working_flow(flow, "test-flow-id")
        comp_id = _get_component_id(flow, "ChatInput")

        tool1 = ProposeFieldEdit()
        tool1.set(component_id=comp_id, field_name="input_value", new_value="a")
        tool1.propose_field_edit()

        tool2 = ProposeFieldEdit()
        tool2.set(component_id=comp_id, field_name="sender_name", new_value="Bot")
        tool2.propose_field_edit()

        events = drain_flow_events()
        assert events[0]["id"] != events[1]["id"]


class TestProposeFieldEditStructuredValues:
    def _setup_tools_field(self, rows: list[dict]) -> tuple[dict, str]:
        reset_working_flow()
        flow = _build_test_flow()
        component_id = _get_component_id(flow, "ChatInput")
        _set_tools_metadata(flow, component_id, rows)
        init_working_flow(flow, "test-flow-id")
        return flow, component_id

    def _setup_structured_field(self, field_name: str, value: object) -> str:
        reset_working_flow()
        flow = _build_test_flow()
        component_id = _get_component_id(flow, "ChatInput")
        for node in flow["data"]["nodes"]:
            if node["data"]["id"] == component_id:
                node["data"]["node"]["template"][field_name] = {"type": "data", "value": value}
                break
        init_working_flow(flow, "test-flow-id")
        return component_id

    def test_merges_actual_assistant_description_payload_into_single_tool_row(self):
        original = _tool_row("TEST-FLOW-1_TOOL", "Old description")
        flow, component_id = self._setup_tools_field([original])

        tool = ProposeFieldEdit()
        tool.set(
            component_id=component_id,
            field_name="tools_metadata",
            new_value='{"description":"Run Flow 1"}',
        )
        result = tool.propose_field_edit()

        assert "error" not in result.data
        event = drain_flow_events()[0]
        expected = [{**original, "description": "Run Flow 1"}]
        assert event["new_value"] == expected
        assert event["patch"][0]["value"] == expected
        assert flow["data"]["nodes"][0]["data"]["node"]["template"]["tools_metadata"]["value"] == [original]

    def test_merges_partial_array_without_discarding_metadata(self):
        original = _tool_row("TEST-FLOW-1_TOOL", "Old description")
        _, component_id = self._setup_tools_field([original])

        tool = ProposeFieldEdit()
        tool.set(
            component_id=component_id,
            field_name="tools_metadata",
            new_value='[{"description":"Run Flow 1"}]',
        )
        result = tool.propose_field_edit()

        assert "error" not in result.data
        event = drain_flow_events()[0]
        assert event["new_value"] == [{**original, "description": "Run Flow 1"}]

    def test_accepts_complete_array_for_existing_tool_row(self):
        original = _tool_row("TEST-FLOW-1_TOOL", "Old description")
        proposed = {**original, "description": "Run Flow 1"}
        _, component_id = self._setup_tools_field([original])

        tool = ProposeFieldEdit()
        tool.set(
            component_id=component_id,
            field_name="tools_metadata",
            new_value=json.dumps([proposed]),
        )
        result = tool.propose_field_edit()

        assert "error" not in result.data
        assert drain_flow_events()[0]["new_value"] == [proposed]

    def test_uses_stable_tool_tag_to_select_row_and_allows_name_change(self):
        first = _tool_row("FIRST_TOOL", "First old description")
        second = _tool_row("SECOND_TOOL", "Second old description")
        _, component_id = self._setup_tools_field([first, second])

        tool = ProposeFieldEdit()
        tool.set(
            component_id=component_id,
            field_name="tools_metadata",
            new_value=('{"tags":["SECOND_TOOL"],"name":"RENAMED_SECOND_TOOL","description":"Second new description"}'),
        )
        result = tool.propose_field_edit()

        assert "error" not in result.data
        assert drain_flow_events()[0]["new_value"] == [
            first,
            {**second, "name": "RENAMED_SECOND_TOOL", "description": "Second new description"},
        ]

    def test_merges_multiple_rows_by_stable_tag_and_preserves_order_and_metadata(self):
        first = _tool_row("FIRST_TOOL", "First old description")
        second = _tool_row("SECOND_TOOL", "Second old description")
        _, component_id = self._setup_tools_field([first, second])

        tool = ProposeFieldEdit()
        tool.set(
            component_id=component_id,
            field_name="tools_metadata",
            new_value=json.dumps(
                [
                    {"tags": ["SECOND_TOOL"], "description": "Second new description"},
                    {"tags": ["FIRST_TOOL"], "status": False},
                ]
            ),
        )
        result = tool.propose_field_edit()

        assert "error" not in result.data
        assert drain_flow_events()[0]["new_value"] == [
            {**first, "status": False},
            {**second, "description": "Second new description"},
        ]

    def test_rejects_description_without_unambiguous_tool_row(self):
        first = _tool_row("FIRST_TOOL", "First old description")
        second = _tool_row("SECOND_TOOL", "Second old description")
        _, component_id = self._setup_tools_field([first, second])

        tool = ProposeFieldEdit()
        tool.set(
            component_id=component_id,
            field_name="tools_metadata",
            new_value='{"description":"Ambiguous description"}',
        )
        result = tool.propose_field_edit()

        assert "error" in result.data
        assert "identify" in result.data["error"].lower()
        assert drain_flow_events() == []

    def test_rejects_malformed_json_without_emitting_edit(self):
        original = _tool_row("TEST-FLOW-1_TOOL", "Old description")
        _, component_id = self._setup_tools_field([original])

        tool = ProposeFieldEdit()
        tool.set(component_id=component_id, field_name="tools_metadata", new_value="{bad json")
        result = tool.propose_field_edit()

        assert "error" in result.data
        assert "json" in result.data["error"].lower()
        assert drain_flow_events() == []

    def test_rejects_empty_array_without_deleting_metadata(self):
        original = _tool_row("TEST-FLOW-1_TOOL", "Old description")
        _, component_id = self._setup_tools_field([original])

        tool = ProposeFieldEdit()
        tool.set(component_id=component_id, field_name="tools_metadata", new_value="[]")
        result = tool.propose_field_edit()

        assert "error" in result.data
        assert drain_flow_events() == []

    def test_allows_valid_status_and_approval_policy_changes(self):
        original = _tool_row("TEST-FLOW-1_TOOL", "Old description")
        _, component_id = self._setup_tools_field([original])

        tool = ProposeFieldEdit()
        tool.set(
            component_id=component_id,
            field_name="tools_metadata",
            new_value=(
                '[{"tags":["TEST-FLOW-1_TOOL"],"name":"RENAMED_TOOL",'
                '"description":"Run Flow 1","status":false,'
                '"approval_actions":["approve","reject"]}]'
            ),
        )
        result = tool.propose_field_edit()

        assert "error" not in result.data
        assert drain_flow_events()[0]["new_value"] == [
            {
                **original,
                "name": "RENAMED_TOOL",
                "description": "Run Flow 1",
                "status": False,
                "approval_actions": ["approve", "reject"],
            }
        ]

    def test_rejects_invalid_known_metadata_type(self):
        original = _tool_row("TEST-FLOW-1_TOOL", "Old description")
        _, component_id = self._setup_tools_field([original])

        tool = ProposeFieldEdit()
        tool.set(
            component_id=component_id,
            field_name="tools_metadata",
            new_value='{"description":"Run Flow 1","status":"false"}',
        )
        result = tool.propose_field_edit()

        assert "error" in result.data
        assert "status" in result.data["error"].lower()
        assert drain_flow_events() == []

    def test_keeps_json_looking_scalar_edit_as_a_string(self):
        reset_working_flow()
        flow = _build_test_flow()
        init_working_flow(flow, "test-flow-id")
        component_id = _get_component_id(flow, "ChatInput")
        new_value = '{"description":"ordinary text"}'

        tool = ProposeFieldEdit()
        tool.set(component_id=component_id, field_name="input_value", new_value=new_value)
        result = tool.propose_field_edit()

        assert "error" not in result.data
        event = drain_flow_events()[0]
        assert event["new_value"] == new_value
        assert event["patch"][0]["value"] == new_value

    def test_leaves_unrelated_array_valued_field_behavior_unchanged(self):
        component_id = self._setup_structured_field("structured_data", ["old"])

        tool = ProposeFieldEdit()
        tool.set(component_id=component_id, field_name="structured_data", new_value='["new"]')
        result = tool.propose_field_edit()

        assert "error" not in result.data
        event = drain_flow_events()[0]
        assert event["new_value"] == '["new"]'
        assert event["patch"][0]["value"] == '["new"]'

    def test_configure_component_bridge_normalizes_actual_assistant_payload(self):
        original = _tool_row("TEST-FLOW-1_TOOL", "Old description")
        _, component_id = self._setup_tools_field([original])
        set_propose_existing_edits(enabled=True)

        tool = ConfigureComponent()
        tool.set(
            component_id=component_id,
            params=json.dumps({"tools_metadata": '{"description":"Run Flow 1"}'}),
        )
        result = tool.configure_component()

        assert "error" not in result.data
        event = drain_flow_events()[0]
        expected = [{**original, "description": "Run Flow 1"}]
        assert event["new_value"] == expected
        assert event["patch"][0]["value"] == expected

    def test_configure_component_bridge_accepts_complete_metadata_update(self):
        original = _tool_row("TEST-FLOW-1_TOOL", "Old description")
        _, component_id = self._setup_tools_field([original])
        set_propose_existing_edits(enabled=True)
        replacement = {
            "tags": ["TEST-FLOW-1_TOOL"],
            "name": "RENAMED_TOOL",
            "description": "Run Flow 1",
            "status": False,
            "approval_actions": ["approve", "reject"],
        }

        tool = ConfigureComponent()
        tool.set(
            component_id=component_id,
            params=json.dumps({"tools_metadata": json.dumps([replacement])}),
        )
        result = tool.configure_component()

        assert "error" not in result.data
        assert drain_flow_events()[0]["new_value"] == [{**original, **replacement}]

    def test_configure_component_bridge_normalizes_native_metadata_object(self):
        original = _tool_row("TEST-FLOW-1_TOOL", "Old description")
        _, component_id = self._setup_tools_field([original])
        set_propose_existing_edits(enabled=True)

        tool = ConfigureComponent()
        tool.set(
            component_id=component_id,
            params={"tools_metadata": {"description": "Run Flow 1"}},
        )
        result = tool.configure_component()

        assert "error" not in result.data
        assert drain_flow_events()[0]["new_value"] == [{**original, "description": "Run Flow 1"}]

    def test_configure_component_bridge_normalizes_native_metadata_array(self):
        original = _tool_row("TEST-FLOW-1_TOOL", "Old description")
        _, component_id = self._setup_tools_field([original])
        set_propose_existing_edits(enabled=True)
        replacement = {
            "tags": ["TEST-FLOW-1_TOOL"],
            "description": "Run Flow 1",
            "status": False,
        }

        tool = ConfigureComponent()
        tool.set(component_id=component_id, params={"tools_metadata": [replacement]})
        result = tool.configure_component()

        assert "error" not in result.data
        assert drain_flow_events()[0]["new_value"] == [{**original, **replacement}]

    def test_configure_component_normalizes_native_metadata_when_applying_live(self):
        original = _tool_row("TEST-FLOW-1_TOOL", "Old description")
        flow, component_id = self._setup_tools_field([original])
        set_propose_existing_edits(enabled=False)

        tool = ConfigureComponent()
        tool.set(
            component_id=component_id,
            params={"tools_metadata": {"description": "Run Flow 1"}},
        )
        result = tool.configure_component()

        assert "error" not in result.data
        node = next(node for node in flow["data"]["nodes"] if node["data"]["id"] == component_id)
        assert node["data"]["node"]["template"]["tools_metadata"]["value"] == [
            {**original, "description": "Run Flow 1"}
        ]

    def test_configure_component_bridge_emits_nothing_when_later_proposal_is_invalid(self):
        original = _tool_row("TEST-FLOW-1_TOOL", "Old description")
        flow, component_id = self._setup_tools_field([original])
        set_propose_existing_edits(enabled=True)
        node = next(node for node in flow["data"]["nodes"] if node["data"]["id"] == component_id)
        old_input_value = node["data"]["node"]["template"]["input_value"]["value"]

        tool = ConfigureComponent()
        tool.set(
            component_id=component_id,
            params={
                "input_value": "Valid earlier proposal",
                "tools_metadata": {"status": "false"},
            },
        )
        result = tool.configure_component()

        assert "error" in result.data
        assert "status" in result.data["error"].lower()
        assert drain_flow_events() == []
        assert node["data"]["node"]["template"]["input_value"]["value"] == old_input_value
        assert node["data"]["node"]["template"]["tools_metadata"]["value"] == [original]

    def test_configure_component_bridge_emits_nothing_when_remaining_parameter_is_invalid(self):
        original = _tool_row("TEST-FLOW-1_TOOL", "Old description")
        flow, component_id = self._setup_tools_field([original])
        set_propose_existing_edits(enabled=True)

        tool = ConfigureComponent()
        tool.set(
            component_id=component_id,
            params={
                "tools_metadata": {"description": "Run Flow 1"},
                "unknown_numeric_parameter": 1,
            },
        )
        result = tool.configure_component()

        assert "error" in result.data
        assert "unknown parameter" in result.data["error"].lower()
        assert drain_flow_events() == []
        node = next(node for node in flow["data"]["nodes"] if node["data"]["id"] == component_id)
        assert node["data"]["node"]["template"]["tools_metadata"]["value"] == [original]

    def test_configure_component_bridge_rejects_invalid_metadata_without_falling_back_to_apply(self):
        original = _tool_row("TEST-FLOW-1_TOOL", "Old description")
        flow, component_id = self._setup_tools_field([original])
        set_propose_existing_edits(enabled=True)

        tool = ConfigureComponent()
        tool.set(component_id=component_id, params=json.dumps({"tools_metadata": "{bad json"}))
        result = tool.configure_component()

        assert "error" in result.data
        assert "json" in result.data["error"].lower()
        assert drain_flow_events() == []
        node = next(node for node in flow["data"]["nodes"] if node["data"]["id"] == component_id)
        assert node["data"]["node"]["template"]["tools_metadata"]["value"] == [original]
