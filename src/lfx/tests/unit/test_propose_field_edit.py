"""Tests for propose_field_edit -- JSON Patch generation and validation.

Tests the full pipeline: validation, patch generation, dry run, event emission.
"""

import copy

import jsonpatch
from lfx.graph.flow_builder.builder import build_flow_from_spec
from lfx.mcp.flow_builder_tools import (
    ProposeFieldEdit,
    drain_flow_events,
    init_working_flow,
    reset_working_flow,
)

SIMPLE_FLOW_SPEC = """\
name: Test Flow
nodes:
  A: ChatInput
  B: OpenAIModel
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
        model_id = _get_component_id(flow, "OpenAIModel")

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
