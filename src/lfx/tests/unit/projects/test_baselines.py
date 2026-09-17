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
