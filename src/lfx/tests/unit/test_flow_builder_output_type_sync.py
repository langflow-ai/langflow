"""Tests pinning the ``output_type`` tab to the wired output on every connect path.

Components like TypeConverter rebuild their whole ``outputs`` list from the
``output_type`` tab on re-hydration (``update_outputs``). An edge wired from
``data_output`` while the tab still reads ``Message`` therefore loses its source
output on the next load: the edge dangles and is dropped, silently and
permanently. A loop feedback edge destroyed this way turns the loop into a
linear pipeline (LE-1776).

``sync_dropdown_selected_outputs`` fixes the tab, but it used to run only in
``build_flow_from_spec`` — so the assistant's incremental edit path and the
external MCP tools, which both call ``add_connection`` directly, were exposed.
These tests pin the sync to ``add_connection`` itself so every current and
future caller inherits it.
"""

import pytest
from lfx.graph.flow_builder import add_component, add_connection, empty_flow
from lfx.graph.flow_builder.builder import build_flow_from_spec

# Mirrors the real TypeConverterComponent shape: a tab whose value decides
# which single output survives hydration, plus 3 non-group outputs.
REGISTRY = {
    "Source": {
        "display_name": "Source",
        "base_classes": ["Message"],
        "outputs": [{"name": "message", "types": ["Message"]}],
        "template": {},
    },
    "TypeConverter": {
        "display_name": "Type Convert",
        "base_classes": ["Message", "Data", "DataFrame"],
        "outputs": [
            {"name": "message_output", "types": ["Message"], "group_outputs": False},
            {"name": "data_output", "types": ["JSON"], "group_outputs": False},
            {"name": "dataframe_output", "types": ["Table"], "group_outputs": False},
        ],
        "template": {
            "output_type": {
                "display_name": "Output Type",
                "type": "tab",
                "value": "Message",
                "options": ["Message", "JSON", "Table"],
            },
            "input_data": {
                "display_name": "Input",
                "type": "other",
                "value": "",
                "input_types": ["Message", "Data", "DataFrame"],
            },
        },
    },
    "SingleOut": {
        "display_name": "Single Out",
        "base_classes": ["JSON"],
        "outputs": [{"name": "only", "types": ["JSON"]}],
        "template": {
            "value_in": {
                "display_name": "In",
                "type": "other",
                "value": "",
                "input_types": ["JSON"],
            },
        },
    },
}


def _tab_value(flow: dict, node_id: str) -> str | None:
    node = next(n for n in flow["data"]["nodes"] if n["id"] == node_id)
    return node["data"]["node"]["template"]["output_type"]["value"]


def _selected_output(flow: dict, node_id: str) -> str | None:
    node = next(n for n in flow["data"]["nodes"] if n["id"] == node_id)
    return node["data"].get("selected_output")


def _wire_converter_to_sink(flow: dict) -> tuple[str, str]:
    """Source -> TypeConverter.input_data, then TypeConverter.data_output -> sink."""
    src = add_component(flow, "Source", REGISTRY)["id"]
    conv = add_component(flow, "TypeConverter", REGISTRY)["id"]
    sink = add_component(flow, "SingleOut", REGISTRY)["id"]
    add_connection(flow, src, "message", conv, "input_data")
    add_connection(flow, conv, "data_output", sink, "value_in")
    return conv, sink


class TestAddConnectionSyncsOutputTypeTab:
    """The incremental path — the assistant editing an existing flow."""

    def test_should_pin_tab_to_the_wired_output(self):
        flow = empty_flow()
        conv, _ = _wire_converter_to_sink(flow)

        assert _tab_value(flow, conv) == "JSON", (
            "tab left on Message deletes data_output on re-hydration and drops its edge"
        )

    def test_should_also_pin_selected_output(self):
        flow = empty_flow()
        conv, _ = _wire_converter_to_sink(flow)

        assert _selected_output(flow, conv) == "data_output"

    def test_should_leave_tab_untouched_when_the_wired_output_matches_it(self):
        flow = empty_flow()
        src = add_component(flow, "Source", REGISTRY)["id"]
        conv = add_component(flow, "TypeConverter", REGISTRY)["id"]
        sink = add_component(flow, "Source", REGISTRY)["id"]
        add_connection(flow, src, "message", conv, "input_data")
        add_connection(flow, conv, "message_output", sink, "input_data", target_types=["Message"])

        assert _tab_value(flow, conv) == "Message"

    def test_should_stop_updating_once_two_different_outputs_are_wired(self):
        """Ambiguity freezes the tab instead of flipping it.

        A tab-driven node can only ever expose one output, so wiring two is
        broken whichever way the tab points. The sync refuses to guess between
        them: it keeps the value the first unambiguous edge pinned. Identical on
        the spec path, which reaches this same function per edge.
        """
        flow = empty_flow()
        conv = add_component(flow, "TypeConverter", REGISTRY)["id"]
        a = add_component(flow, "SingleOut", REGISTRY)["id"]
        b = add_component(flow, "Source", REGISTRY)["id"]
        add_connection(flow, conv, "data_output", a, "value_in")
        assert _tab_value(flow, conv) == "JSON"

        add_connection(flow, conv, "message_output", b, "input_data", target_types=["Message"])

        assert _tab_value(flow, conv) == "JSON", "ambiguity must freeze the tab, not flip it"

    def test_should_be_idempotent(self):
        flow = empty_flow()
        conv, _sink = _wire_converter_to_sink(flow)
        before = _tab_value(flow, conv)

        extra = add_component(flow, "SingleOut", REGISTRY)["id"]
        add_connection(flow, conv, "data_output", extra, "value_in")

        assert _tab_value(flow, conv) == before == "JSON"

    def test_should_not_touch_nodes_without_an_output_type_tab(self):
        flow = empty_flow()
        src = add_component(flow, "Source", REGISTRY)["id"]
        conv = add_component(flow, "TypeConverter", REGISTRY)["id"]
        add_connection(flow, src, "message", conv, "input_data")

        source_node = next(n for n in flow["data"]["nodes"] if n["id"] == src)
        assert "output_type" not in source_node["data"]["node"]["template"]


class TestBuildFromSpecStillSyncs:
    """Non-regression: the one path that was already protected must not change."""

    def test_spec_path_keeps_pinning_the_tab(self):
        spec = (
            "name: Control\n"
            "nodes:\n  A: Source\n  T: TypeConverter\n  S: SingleOut\n"
            "edges:\n  A.message -> T.input_data\n  T.data_output -> S.value_in\n"
        )
        result = build_flow_from_spec(spec, registry=REGISTRY)

        assert "error" not in result, result
        flow = result["flow"]
        conv = next(n for n in flow["data"]["nodes"] if n["data"]["type"] == "TypeConverter")
        assert conv["data"]["node"]["template"]["output_type"]["value"] == "JSON"
        assert conv["data"]["selected_output"] == "data_output"


class TestLoopFeedbackEdgeSurvivesRehydration:
    """The end-to-end consequence: the loop must still be a loop after a reload."""

    @staticmethod
    def _surviving_edges(flow: dict, conv_id: str) -> int:
        """Drop edges whose source output no longer exists after tab-driven rebuild."""
        tab = _tab_value(flow, conv_id)
        survivor = {"Message": "message_output", "JSON": "data_output", "Table": "dataframe_output"}[tab]
        return sum(
            1
            for e in flow["data"]["edges"]
            if not (e["source"] == conv_id and e["data"]["sourceHandle"]["name"] != survivor)
        )

    def test_edge_from_a_non_default_output_survives(self):
        flow = empty_flow()
        conv, _ = _wire_converter_to_sink(flow)
        total = len(flow["data"]["edges"])

        assert self._surviving_edges(flow, conv) == total, "re-hydration dropped a wired edge"


@pytest.mark.parametrize("wired", ["message_output", "data_output", "dataframe_output"])
def test_every_output_choice_is_preserved_across_rehydration(wired):
    expected_tab = {"message_output": "Message", "data_output": "JSON", "dataframe_output": "Table"}[wired]
    flow = empty_flow()
    conv = add_component(flow, "TypeConverter", REGISTRY)["id"]
    sink = add_component(flow, "SingleOut", REGISTRY)["id"]
    add_connection(flow, conv, wired, sink, "value_in", target_types=["Message", "JSON", "Table"])

    assert _tab_value(flow, conv) == expected_tab
