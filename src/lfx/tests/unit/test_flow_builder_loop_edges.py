"""Tests for loop feedback edges in the flow_builder connect layer.

The Loop component's ``item`` output doubles as the loop-body feedback
input (``allows_loop=True``). The canvas serializes that edge with an
output-shaped targetHandle ``{dataType, id, name, output_types}`` — the
shape the runtime branches on in ``lfx.graph.edge.base.Edge``
(``"name" in target_handle`` -> ``TargetHandle.from_loop_target_handle``).
These tests pin ``add_connection`` to that exact contract so every
builder path (connect_components, create/update/build_flow_from_spec)
can wire loop flows.
"""

import pytest
from lfx.graph.edge.schema import TargetHandle
from lfx.graph.flow_builder import (
    add_component,
    add_connection,
    empty_flow,
    list_connections,
    remove_connection,
)
from lfx.graph.flow_builder.builder import build_flow_from_spec
from lfx.graph.flow_builder.connect import _scaped_json_stringify

REGISTRY = {
    "LoopComponent": {
        "display_name": "Loop",
        "base_classes": ["Data"],
        "outputs": [
            {
                "name": "item",
                "types": ["Data", "JSON"],
                "selected": "Data",
                "allows_loop": True,
                "loop_types": ["Message"],
            },
            {"name": "done", "types": ["DataFrame", "Table"], "allows_loop": False},
        ],
        "template": {
            "data": {
                "display_name": "Inputs",
                "type": "other",
                "value": "",
                "input_types": ["DataFrame", "Table", "Data", "Message"],
            },
        },
    },
    "MessagetoData": {
        "display_name": "Message to Data",
        "base_classes": ["Data"],
        "outputs": [{"name": "data", "types": ["Data"]}],
        "template": {
            "message": {
                "display_name": "Message",
                "type": "str",
                "value": "",
                "input_types": ["Message"],
            },
        },
    },
    "ToolProducer": {
        "display_name": "Tool Producer",
        "base_classes": ["Tool"],
        "outputs": [{"name": "tool", "types": ["Tool"]}],
        "template": {},
    },
    "MessageSink": {
        # Message-only input (the Agent.input_value shape) — the mismatch the
        # loop-body recipe hits when Loop.item is wired into it directly.
        "display_name": "Message Sink",
        "base_classes": ["Message"],
        "outputs": [{"name": "response", "types": ["Message"]}],
        "template": {
            "input_value": {
                "display_name": "Input",
                "type": "str",
                "value": "",
                "input_types": ["Message"],
            },
        },
    },
    "DataSink": {
        "display_name": "Data Sink",
        "base_classes": ["Data"],
        "outputs": [{"name": "data", "types": ["Data"]}],
        "template": {
            "data_in": {
                "display_name": "Data In",
                "type": "other",
                "value": "",
                "input_types": ["Data"],
            },
        },
    },
    "CollidingPorts": {
        # A template input AND an allows_loop output both named "item":
        # the template input must keep priority (backward compatibility).
        "display_name": "Colliding Ports",
        "base_classes": ["Message"],
        "outputs": [
            {
                "name": "item",
                "types": ["Data"],
                "selected": "Data",
                "allows_loop": True,
                "loop_types": ["Message"],
            },
        ],
        "template": {
            "item": {
                "display_name": "Item",
                "type": "str",
                "value": "",
                "input_types": ["Message"],
            },
        },
    },
}


def _loop_flow():
    flow = empty_flow(name="Loop Flow")
    loop = add_component(flow, "LoopComponent", REGISTRY, component_id="LoopComponent-loop1")
    tail = add_component(flow, "MessagetoData", REGISTRY, component_id="MessagetoData-tail1")
    return flow, loop["id"], tail["id"]


class TestLoopFeedbackEdge:
    def test_emits_output_shaped_target_handle(self):
        flow, loop_id, tail_id = _loop_flow()
        edge = add_connection(flow, tail_id, "data", loop_id, "item")
        target_handle = edge["data"]["targetHandle"]
        assert target_handle == {
            "dataType": "LoopComponent",
            "id": loop_id,
            "name": "item",
            "output_types": ["Data", "Message"],
        }
        assert "fieldName" not in target_handle

    def test_target_handle_string_matches_dict(self):
        flow, loop_id, tail_id = _loop_flow()
        edge = add_connection(flow, tail_id, "data", loop_id, "item")
        assert edge["targetHandle"] == _scaped_json_stringify(edge["data"]["targetHandle"])
        assert edge["id"].startswith(f"reactflow__edge-{tail_id}")

    def test_runtime_parses_edge_as_loop_target(self):
        flow, loop_id, tail_id = _loop_flow()
        edge = add_connection(flow, tail_id, "data", loop_id, "item")
        handle = TargetHandle.from_loop_target_handle(edge["data"]["targetHandle"])
        assert handle.field_name == "item"
        assert handle.input_types == ["Data", "Message"]
        assert handle.type is None

    def test_type_mismatch_raises(self):
        flow = empty_flow(name="Bad Loop")
        loop = add_component(flow, "LoopComponent", REGISTRY)
        tool = add_component(flow, "ToolProducer", REGISTRY)
        with pytest.raises(ValueError, match="Type mismatch"):
            add_connection(flow, tool["id"], "tool", loop["id"], "item")

    def test_is_idempotent(self):
        flow, loop_id, tail_id = _loop_flow()
        add_connection(flow, tail_id, "data", loop_id, "item")
        add_connection(flow, tail_id, "data", loop_id, "item")
        assert len(flow["data"]["edges"]) == 1

    def test_remove_connection_matches_loop_target(self):
        flow, loop_id, tail_id = _loop_flow()
        add_connection(flow, tail_id, "data", loop_id, "item")
        removed = remove_connection(flow, tail_id, loop_id, target_input="item")
        assert removed == 1
        assert flow["data"]["edges"] == []

    def test_list_connections_reports_loop_target(self):
        flow, loop_id, tail_id = _loop_flow()
        add_connection(flow, tail_id, "data", loop_id, "item")
        connections = list_connections(flow)
        assert connections == [
            {
                "source_id": tail_id,
                "target_id": loop_id,
                "source_output": "data",
                "target_input": "item",
                "source_types": ["Data"],
                "target_types": ["Data", "Message"],
            }
        ]

    def test_template_input_wins_on_name_collision(self):
        flow = empty_flow(name="Collision")
        collider = add_component(flow, "CollidingPorts", REGISTRY)
        source = add_component(flow, "MessagetoData", REGISTRY)
        # MessagetoData has no Message output, so use ChatInput-like source:
        # the template input "item" accepts Message; the loop output accepts Data.
        # Wiring a Data source must therefore FAIL (template input has priority),
        # proving the loop output did not shadow the template input.
        with pytest.raises(ValueError, match="Type mismatch"):
            add_connection(flow, source["id"], "data", collider["id"], "item")

    def test_template_input_wins_on_name_collision_with_explicit_types(self):
        # Regression: the explicit-types branch consulted _resolve_loop_target
        # unconditionally, so a same-named allows_loop output shadowed the
        # template input and emitted an output-shaped targetHandle.
        flow = empty_flow(name="Collision Explicit")
        collider = add_component(flow, "CollidingPorts", REGISTRY)
        source = add_component(flow, "MessageSink", REGISTRY)

        edge = add_connection(
            flow,
            source["id"],
            "response",
            collider["id"],
            "item",
            source_types=["Message"],
            target_types=["Message"],
        )

        target_handle = edge["data"]["targetHandle"]
        assert target_handle == {
            "fieldName": "item",
            "id": collider["id"],
            "inputTypes": ["Message"],
            "type": "str",
        }
        assert "name" not in target_handle

    def test_explicit_types_still_resolve_true_loop_port(self):
        flow, loop_id, tail_id = _loop_flow()

        edge = add_connection(
            flow,
            tail_id,
            "data",
            loop_id,
            "item",
            source_types=["Data"],
            target_types=["Data", "Message"],
        )

        target_handle = edge["data"]["targetHandle"]
        assert target_handle["name"] == "item"
        assert "fieldName" not in target_handle

    def test_unknown_port_error_lists_loop_inputs(self):
        flow, loop_id, tail_id = _loop_flow()
        with pytest.raises(ValueError, match=r"Input 'nope' not found.*item"):
            add_connection(flow, tail_id, "data", loop_id, "nope")

    def test_normal_edges_unchanged(self):
        flow = empty_flow(name="Normal")
        loop = add_component(flow, "LoopComponent", REGISTRY)
        sink = add_component(flow, "DataSink", REGISTRY)
        # Loop.item as a SOURCE is a normal edge into a template input.
        edge = add_connection(flow, loop["id"], "item", sink["id"], "data_in")
        assert edge["data"]["targetHandle"] == {
            "fieldName": "data_in",
            "id": sink["id"],
            "inputTypes": ["Data"],
            "type": "other",
        }


class TestTypeMismatchConversionHint:
    """The type-mismatch error must carry the deterministic converter fix.

    A bare "Type mismatch" dead-ends the flow-builder agent into a discovery
    spiral that exhausts its recursion budget (loop_flow eval failure).
    """

    def test_data_to_message_mismatch_suggests_parser_component(self):
        flow = empty_flow(name="Loop Agent")
        loop = add_component(flow, "LoopComponent", REGISTRY, component_id="LoopComponent-loop1")
        sink = add_component(flow, "MessageSink", REGISTRY, component_id="MessageSink-sink1")
        with pytest.raises(ValueError, match="Type mismatch") as excinfo:
            add_connection(flow, loop["id"], "item", sink["id"], "input_value")
        message = str(excinfo.value)
        assert "ParserComponent" in message
        assert f"{loop['id']}.item -> ParserComponent.input_data" in message
        assert f"ParserComponent.parsed_text -> {sink['id']}.input_value" in message

    def test_message_to_data_mismatch_suggests_type_converter(self):
        flow = empty_flow(name="Reverse")
        source = add_component(flow, "MessageSink", REGISTRY, component_id="MessageSink-src1")
        sink = add_component(flow, "DataSink", REGISTRY, component_id="DataSink-sink1")
        with pytest.raises(ValueError, match="Type mismatch") as excinfo:
            add_connection(flow, source["id"], "response", sink["id"], "data_in")
        message = str(excinfo.value)
        assert "TypeConverterComponent" in message
        assert f"{source['id']}.response -> TypeConverterComponent.input_data" in message
        assert f"TypeConverterComponent.data_output -> {sink['id']}.data_in" in message

    def test_unrelated_mismatch_gets_no_converter_hint(self):
        flow = empty_flow(name="Bad Loop")
        loop = add_component(flow, "LoopComponent", REGISTRY)
        tool = add_component(flow, "ToolProducer", REGISTRY)
        with pytest.raises(ValueError, match="Type mismatch") as excinfo:
            add_connection(flow, tool["id"], "tool", loop["id"], "item")
        message = str(excinfo.value)
        assert "ParserComponent" not in message
        assert "TypeConverterComponent" not in message


class TestConversionHintNamesPinnedToRegistry:
    """The converter hint names concrete components/ports for the agent to wire.

    If those drift in the bundled registry (rename, legacy flag, port change),
    the hint would mislead the agent into unfixable retries — fail CI instead.
    """

    @staticmethod
    def _registry_component(name: str) -> dict:
        from lfx.graph.flow_builder.builder import load_local_registry

        registry = load_local_registry()
        assert name in registry, f"{name} missing from the bundled component index"
        component = registry[name]
        assert not component.get("legacy"), f"{name} is legacy — the hint must not recommend it"
        return component

    def test_parser_component_exposes_the_hinted_ports(self):
        component = self._registry_component("ParserComponent")

        template = component.get("template", {})
        input_data = template.get("input_data")
        assert isinstance(input_data, dict), "ParserComponent.input_data input missing"
        assert input_data, "ParserComponent.input_data input is empty"
        output_names = {o.get("name") for o in component.get("outputs", [])}
        assert "parsed_text" in output_names, "ParserComponent.parsed_text output missing"

    def test_type_converter_component_exposes_the_hinted_ports(self):
        component = self._registry_component("TypeConverterComponent")

        template = component.get("template", {})
        input_data = template.get("input_data")
        assert isinstance(input_data, dict), "TypeConverterComponent.input_data input missing"
        assert input_data, "TypeConverterComponent.input_data input is empty"
        output_names = {o.get("name") for o in component.get("outputs", [])}
        assert {"data_output", "dataframe_output"} <= output_names, (
            f"TypeConverterComponent outputs drifted: {sorted(output_names)}"
        )

    def test_hint_text_only_references_registry_verified_ports(self):
        from lfx.graph.flow_builder.connect import _conversion_hint

        data_to_message = _conversion_hint("A-1", "out", ["Data"], "B-1", "in", ["Message"])
        assert "ParserComponent.input_data" in data_to_message
        assert "ParserComponent.parsed_text" in data_to_message

        message_to_data = _conversion_hint("A-1", "out", ["Message"], "B-1", "in", ["Data"])
        assert "TypeConverterComponent.input_data" in message_to_data
        assert "TypeConverterComponent.data_output" in message_to_data

        message_to_frame = _conversion_hint("A-1", "out", ["Message"], "B-1", "in", ["DataFrame"])
        assert "TypeConverterComponent.dataframe_output" in message_to_frame


class TestDropdownSelectedOutput:
    """Dropdown components must pin ``selected_output`` to the wired output.

    Otherwise the canvas auto-flips to the first output and drops the wired
    edge (the loop feedback from ``TypeConverter.data_output``).
    """

    _LOOP_DATA_SPEC = """\
name: Loop Data Flow

nodes:
  I: ChatInput
  L: LoopComponent
  P: ParserComponent
  TC: TypeConverterComponent
  O: ChatOutput

edges:
  I.message -> L.data
  L.item -> P.input_data
  P.parsed_text -> TC.input_data
  TC.data_output -> L.item
  L.done -> O.input_value

config:
  TC.output_type: Data
"""

    def test_type_converter_pins_selected_output_to_wired_data_output(self):
        result = build_flow_from_spec(self._LOOP_DATA_SPEC)
        assert "flow" in result, f"Expected flow, got: {result}"
        assert result["edge_count"] == 5

        tc_id = result["node_id_map"]["TC"]
        tc_node = next(n for n in result["flow"]["data"]["nodes"] if n["id"] == tc_id)
        # Pinned to the wired output so the canvas will not auto-select the
        # first output (message_output) and clean away the feedback edge.
        assert tc_node["data"]["selected_output"] == "data_output"

    def test_feedback_edge_source_survives_with_matching_output(self):
        result = build_flow_from_spec(self._LOOP_DATA_SPEC)
        tc_id = result["node_id_map"]["TC"]
        loop_id = result["node_id_map"]["L"]
        feedback = [
            e
            for e in result["flow"]["data"]["edges"]
            if e["source"] == tc_id and e["data"]["targetHandle"].get("name") == "item"
        ]
        assert len(feedback) == 1
        assert feedback[0]["target"] == loop_id
        assert feedback[0]["data"]["sourceHandle"]["name"] == "data_output"

    _LOOP_DEFAULT_TAB_SPEC = """\
name: Loop Data Flow

nodes:
  I: ChatInput
  L: LoopComponent
  P: ParserComponent
  TC: TypeConverterComponent
  O: ChatOutput

edges:
  I.message -> L.data
  L.item -> P.input_data
  P.parsed_text -> TC.input_data
  TC.data_output -> L.item
  L.done -> O.input_value
"""

    def _tc_output_type_tab(self, result):
        tc_id = result["node_id_map"]["TC"]
        tc_node = next(n for n in result["flow"]["data"]["nodes"] if n["id"] == tc_id)
        return tc_node["data"]["node"]["template"]["output_type"]

    def test_output_type_tab_follows_wired_output(self):
        # Unconfigured tab stays on "Message", whose hydration path deletes
        # data_output and dangles the feedback edge — the sync must flip it.
        result = build_flow_from_spec(self._LOOP_DEFAULT_TAB_SPEC)
        assert "flow" in result, f"Expected flow, got: {result}"
        assert self._tc_output_type_tab(result)["value"] == "JSON"

    def test_spec_configured_output_type_alias_is_preserved(self):
        # "Data" is not an output type but update_outputs accepts it; the sync
        # must not clobber a value it cannot prove selects another output.
        result = build_flow_from_spec(self._LOOP_DATA_SPEC)
        assert self._tc_output_type_tab(result)["value"] == "Data"

    def test_single_output_node_gets_no_selected_output(self):
        # ChatInput has a single output — nothing to disambiguate, so the
        # builder must not stamp a selected_output on it.
        spec = """\
name: Simple

nodes:
  I: ChatInput
  O: ChatOutput

edges:
  I.message -> O.input_value
"""
        result = build_flow_from_spec(spec)
        for node in result["flow"]["data"]["nodes"]:
            assert "selected_output" not in node["data"]


class TestGeneratedComponentSourceDataType:
    """A generated component wears ``data.type == "CustomComponent"`` but a class-named id.

    Its node id keeps the generated class name (e.g. ``MessageToData-Arf``), so the
    loop-feedback edge's ``sourceHandle.dataType`` must equal the node's real
    ``data.type`` (``CustomComponent``), not the id prefix (``MessageToData``).
    Otherwise the frontend ``cleanEdges`` / handle-DOM lookup strips the edge and
    the loop lands on the canvas with no feedback connection ("loop appears
    without connections" apply bug). ``_resolve_loop_target`` already reads the
    node's real type for the target handle; the source handle must match.
    """

    _GEN_REGISTRY = {
        **REGISTRY,
        # A generated component: tagged ``custom`` so ``_make_node`` relabels its
        # canvas type to ``CustomComponent`` while the node id keeps its class name.
        "MessageToData": {
            "display_name": "MessageToData",
            "base_classes": ["Data"],
            "custom": True,
            "outputs": [{"name": "data", "types": ["JSON"], "selected": "JSON"}],
            "template": {
                "input_value": {
                    "display_name": "Input Value",
                    "type": "str",
                    "value": "",
                    "input_types": ["Message"],
                },
            },
        },
    }

    def _gen_loop_flow(self):
        flow = empty_flow(name="Gen Loop")
        loop = add_component(flow, "LoopComponent", self._GEN_REGISTRY, component_id="LoopComponent-loop1")
        tail = add_component(flow, "MessageToData", self._GEN_REGISTRY, component_id="MessageToData-ArfIf")
        return flow, loop["id"], tail["id"]

    def test_generated_node_is_typed_custom_component(self):
        flow, _, tail_id = self._gen_loop_flow()
        tail_node = next(n for n in flow["data"]["nodes"] if n["data"]["id"] == tail_id)
        # The bug precondition: id prefix ("MessageToData") != data.type ("CustomComponent").
        assert tail_node["data"]["type"] == "CustomComponent"
        assert tail_id.rsplit("-", 1)[0] == "MessageToData"

    def test_source_handle_datatype_matches_live_node_type(self):
        flow, loop_id, tail_id = self._gen_loop_flow()
        edge = add_connection(flow, tail_id, "data", loop_id, "item")
        source_handle = edge["data"]["sourceHandle"]
        # Must equal the node's real data.type so the frontend keeps the edge.
        assert source_handle["dataType"] == "CustomComponent"

    def test_registry_component_source_datatype_unchanged(self):
        # Non-regression: a registry component (id prefix == data.type) still
        # emits its component type as the source-handle dataType.
        flow, loop_id, tail_id = _loop_flow()
        edge = add_connection(flow, tail_id, "data", loop_id, "item")
        assert edge["data"]["sourceHandle"]["dataType"] == "MessagetoData"


class TestLoopFlowFromSpec:
    def test_spec_builds_loop_feedback_edge(self):
        spec = """\
name: Loop Flow

nodes:
  A: ChatInput
  M: MessagetoData
  L: LoopComponent

edges:
  A.message -> M.message
  M.data -> L.item
"""
        result = build_flow_from_spec(spec)
        assert "flow" in result, f"Expected flow, got: {result}"
        assert result["edge_count"] == 2
        loop_id = result["node_id_map"]["L"]
        loop_edges = [e for e in result["flow"]["data"]["edges"] if e["data"]["targetHandle"].get("name") == "item"]
        assert len(loop_edges) == 1
        target_handle = loop_edges[0]["data"]["targetHandle"]
        assert target_handle["id"] == loop_id
        assert target_handle["dataType"] == "LoopComponent"
        assert "fieldName" not in target_handle
        assert "Data" in target_handle["output_types"]
