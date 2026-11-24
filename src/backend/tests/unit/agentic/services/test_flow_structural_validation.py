"""Unit tests for structural (no-execution) flow validation."""

from __future__ import annotations

from langflow.agentic.services.flow_structural_validation import structural_failures


def _node(node_id, ntype, *, template=None, outputs=None):
    return {
        "id": node_id,
        "data": {"id": node_id, "type": ntype, "node": {"template": template or {}, "outputs": outputs or []}},
    }


def _input_edge(source, target, field, *, source_output="message"):
    return {
        "source": source,
        "target": target,
        "data": {
            "sourceHandle": {"name": source_output, "id": source},
            "targetHandle": {"fieldName": field, "id": target},
        },
    }


def _feedback_edge(source, loop_id, port="item"):
    return {
        "source": source,
        "target": loop_id,
        "data": {
            "sourceHandle": {"name": "data_output", "id": source},
            "targetHandle": {"name": port, "id": loop_id, "output_types": ["Data"]},
        },
    }


_LOOP_OUTPUTS = [
    {"name": "item", "types": ["Data"], "allows_loop": True, "group_outputs": True},
    {"name": "done", "types": ["DataFrame"], "allows_loop": False, "group_outputs": True},
]


def _complete_loop_flow():
    nodes = [
        _node("ChatInput-1", "ChatInput"),
        _node("LoopComponent-1", "LoopComponent", template={"data": {"input_types": ["Data"]}}, outputs=_LOOP_OUTPUTS),
        _node("Parser-1", "ParserComponent", template={"input_data": {"required": True, "input_types": ["Data"]}}),
        _node(
            "Type-1", "TypeConverterComponent", template={"input_data": {"required": True, "input_types": ["Message"]}}
        ),
        _node("ChatOutput-1", "ChatOutput", template={"input_value": {"required": True, "input_types": ["Message"]}}),
    ]
    edges = [
        _input_edge("ChatInput-1", "LoopComponent-1", "data"),
        {
            "source": "LoopComponent-1",
            "target": "Parser-1",
            "data": {
                "sourceHandle": {"name": "item", "id": "LoopComponent-1"},
                "targetHandle": {"fieldName": "input_data", "id": "Parser-1"},
            },
        },
        _input_edge("Parser-1", "Type-1", "input_data", source_output="parsed_text"),
        _feedback_edge("Type-1", "LoopComponent-1"),
        {
            "source": "LoopComponent-1",
            "target": "ChatOutput-1",
            "data": {
                "sourceHandle": {"name": "done", "id": "LoopComponent-1"},
                "targetHandle": {"fieldName": "input_value", "id": "ChatOutput-1"},
            },
        },
    ]
    return {"data": {"nodes": nodes, "edges": edges}}


def test_should_pass_when_loop_flow_is_structurally_complete():
    assert structural_failures(_complete_loop_flow()) == []


def test_should_return_empty_for_empty_flow():
    assert structural_failures({"data": {"nodes": [], "edges": []}}) == []


def test_should_flag_loop_without_data_source():
    flow = _complete_loop_flow()
    flow["data"]["edges"] = [
        e
        for e in flow["data"]["edges"]
        if not (e["target"] == "LoopComponent-1" and e["data"]["targetHandle"].get("fieldName") == "data")
    ]
    # Drop the now-orphaned ChatInput so only the data-source issue remains.
    flow["data"]["nodes"] = [n for n in flow["data"]["nodes"] if n["id"] != "ChatInput-1"]
    issues = structural_failures(flow)
    assert any("no data source" in i for i in issues)


def test_should_flag_loop_whose_item_is_never_consumed():
    flow = {
        "data": {
            "nodes": [
                _node("LoopComponent-1", "LoopComponent", outputs=_LOOP_OUTPUTS),
                _node("Type-1", "TypeConverterComponent"),
            ],
            "edges": [_feedback_edge("Type-1", "LoopComponent-1")],
        }
    }
    issues = structural_failures(flow)
    assert any("never starts" in i for i in issues)
    assert any("no data source" in i for i in issues)


def test_should_flag_open_loop_missing_feedback():
    flow = _complete_loop_flow()
    flow["data"]["edges"] = [
        e
        for e in flow["data"]["edges"]
        if not (e["target"] == "LoopComponent-1" and e["data"]["targetHandle"].get("name") == "item")
    ]
    issues = structural_failures(flow)
    assert any("not a closed cycle" in i for i in issues)


def test_should_flag_required_input_neither_connected_nor_set():
    flow = {
        "data": {
            "nodes": [
                _node("ChatInput-1", "ChatInput"),
                _node(
                    "ChatOutput-1",
                    "ChatOutput",
                    template={"input_value": {"required": True, "input_types": ["Message"], "value": ""}},
                ),
            ],
            "edges": [_input_edge("ChatInput-1", "ChatOutput-1", "session_id")],
        }
    }
    issues = structural_failures(flow)
    assert any("required input" in i for i in issues)


def test_should_not_flag_required_input_satisfied_by_value():
    flow = {
        "data": {
            "nodes": [
                _node("A-1", "ChatInput"),
                _node(
                    "B-1",
                    "ChatOutput",
                    template={"input_value": {"required": True, "input_types": ["Message"], "value": "hello"}},
                ),
            ],
            "edges": [_input_edge("A-1", "B-1", "session_id")],
        }
    }
    assert structural_failures(flow) == []


def test_should_skip_advanced_and_hidden_required_inputs():
    flow = {
        "data": {
            "nodes": [
                _node("A-1", "ChatInput"),
                _node(
                    "B-1",
                    "ChatOutput",
                    template={
                        "adv": {"required": True, "input_types": ["Message"], "value": "", "advanced": True},
                        "hidden": {"required": True, "input_types": ["Message"], "value": "", "show": False},
                    },
                ),
            ],
            "edges": [_input_edge("A-1", "B-1", "adv")],
        }
    }
    assert structural_failures(flow) == []


def test_should_flag_orphan_node_in_multi_node_flow():
    flow = {
        "data": {
            "nodes": [_node("A-1", "ChatInput"), _node("B-1", "ChatOutput"), _node("C-1", "TextInput")],
            "edges": [_input_edge("A-1", "B-1", "input_value")],
        }
    }
    issues = structural_failures(flow)
    assert any("disconnected" in i for i in issues)


def test_should_not_flag_orphan_in_single_node_flow():
    flow = {"data": {"nodes": [_node("A-1", "ChatInput")], "edges": []}}
    assert structural_failures(flow) == []
