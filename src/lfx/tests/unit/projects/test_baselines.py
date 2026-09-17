"""Shipped slot defaults are runnable graphs, not empty placeholders."""

import pytest
from lfx.graph.graph.base import Graph
from lfx.projects.baselines import build_slot_baseline
from lfx.projects.bindings import instruction_outputs
from lfx.projects.registry import get_slot


async def test_baseline_resolves_the_registered_contract_and_executes():
    contract = get_slot("SystemPromptBuilder")
    baseline = build_slot_baseline(contract.default_flow_ref, "Cite primary sources.")
    outputs = instruction_outputs(baseline["data"])
    assert len(outputs) == 1
    graph = Graph.from_payload(baseline["data"])
    results = [result async for result in graph.async_start()]
    assert any(getattr(result, "valid", False) for result in results)
    terminal = graph.get_vertex(outputs[0]["node_id"])
    assert terminal.custom_component.get_output("instructions").value == "Cite primary sources."


def test_unknown_baselines_cannot_import_code():
    with pytest.raises(ValueError, match="working baseline"):
        build_slot_baseline("arbitrary.module:factory")


def test_whitespace_instructions_are_not_an_eligible_output():
    baseline = build_slot_baseline("builtin:instructions", "Real instructions")
    baseline["data"]["nodes"][0]["data"]["node"]["template"]["input_value"]["value"] = "   "
    with pytest.raises(ValueError, match="Configure"):
        instruction_outputs(baseline["data"])


def test_context_baseline_preserves_the_current_strategy_and_turn_count():
    flow = build_slot_baseline(
        "builtin:context", initial_config={"context_strategy": "recent_turns", "context_turns": 3}
    )
    template = flow["data"]["nodes"][-1]["data"]["node"]["template"]
    assert template["strategy"]["value"] == "recent_turns"
    assert template["turns"]["value"] == 3


async def test_context_baseline_preview_preserves_message_records():
    baseline = build_slot_baseline("builtin:context")
    graph = Graph.from_payload(baseline["data"])
    results = [result async for result in graph.async_start()]
    terminal_id = baseline["data"]["nodes"][-1]["id"]
    terminal = graph.get_vertex(terminal_id)
    expected = terminal.custom_component.get_output("context").value.to_dict(orient="records")
    assert expected[0]["type"] == "human"
    assert expected[0]["data"]["content"]
    preview = next(result for result in results if getattr(result, "vertex", None) is terminal)
    assert preview.result_dict.model_dump()["outputs"]["context"]["message"] == expected


@pytest.mark.parametrize("value", [0, -1, "3", 1.5])
def test_context_baseline_rejects_invalid_turn_counts(value):
    with pytest.raises(ValueError, match="context_turns"):
        build_slot_baseline("builtin:context", initial_config={"context_turns": value})
