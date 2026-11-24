"""Regression test: expanding a compact flow must not mutate the component index.

``expand_compact_flow`` receives the process-wide component index
(``component_cache.all_types_dict``) and only shallow-copies it. Writing a
compact node's value straight into a template field used to store the value back
into that shared index, so the value became the default for every node of the
same type expanded afterwards (including nodes of other users).
"""

from __future__ import annotations

import copy

from langflow.processing.expand_flow import expand_compact_flow

COMPONENT_INDEX = {
    "input_output": {
        "ChatInput": {
            "display_name": "Chat Input",
            "template": {
                "_type": "ChatInput",
                "input_value": {"type": "str", "required": False, "value": "", "display_name": "Input"},
            },
            "base_classes": ["Message"],
            "outputs": [{"name": "message", "display_name": "Message", "types": ["Message"]}],
        }
    }
}


def test_expand_flow_does_not_write_values_back_into_the_component_index():
    index = copy.deepcopy(COMPONENT_INDEX)

    expanded = expand_compact_flow(
        {"nodes": [{"id": "node-A", "type": "ChatInput", "values": {"input_value": "set by node A"}}], "edges": []},
        index,
    )

    # The expanded node carries the requested value...
    assert expanded["nodes"][0]["data"]["node"]["template"]["input_value"]["value"] == "set by node A"
    # ...but the shared index keeps the registered default.
    assert index["input_output"]["ChatInput"]["template"]["input_value"]["value"] == ""

    # A later node of the same type, expanded from the same index, keeps the default.
    later = expand_compact_flow(
        {"nodes": [{"id": "node-B", "type": "ChatInput", "values": {}}], "edges": []},
        index,
    )
    assert later["nodes"][0]["data"]["node"]["template"]["input_value"]["value"] == ""
