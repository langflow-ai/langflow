import copy
import inspect
import json
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from langchain_core.tools import StructuredTool
from langflow.api.v1 import endpoints
from lfx.components.flow_controls.run_flow import RunFlowComponent
from lfx.components.input_output.chat import ChatInput
from lfx.components.input_output.chat_output import ChatOutput
from lfx.components.input_output.text import TextInputComponent
from lfx.components.models_and_agents.mcp_component import MCPToolsComponent
from lfx.custom.custom_component.component import Component
from lfx.custom.utils import build_custom_component_template, update_rebuilt_node
from lfx.graph.graph.base import Graph

HARD_FLOWS = Path(__file__).parents[5] / "lfx" / "tests" / "data" / "component_compat" / "hard_flows" / "v1.13.0"


def _saved_component(fixture: str, component_type: str) -> tuple[dict[str, Any], dict[str, Any]]:
    flow = json.loads((HARD_FLOWS / fixture).read_text(encoding="utf-8"))
    node = next(node for node in flow["data"]["nodes"] if node["data"]["type"] == component_type)
    return flow, node


def _build_current(component_class: type[Component]) -> tuple[dict[str, Any], Component]:
    code = Path(inspect.getsourcefile(component_class)).read_text(encoding="utf-8")
    return build_custom_component_template(Component(_code=code))


def _selected_flow_graph(*, include_text: bool = True) -> Graph:
    nodes = []
    for component_class, component_type, node_id in (
        (ChatInput, "ChatInput", "ChatInput-NrNFA"),
        (TextInputComponent, "TextInput", "TextInput-v7wpH"),
        (ChatOutput, "ChatOutput", "ChatOutput-evE3l"),
    ):
        if component_class is TextInputComponent and not include_text:
            continue
        frontend, _ = _build_current(component_class)
        nodes.append(
            {"id": node_id, "type": "genericNode", "data": {"id": node_id, "type": component_type, "node": frontend}}
        )
    return Graph.from_payload({"nodes": nodes, "edges": []})


def _assert_connected_fields_preserved(flow: dict, saved_node: dict, rebuilt: dict) -> None:
    for edge in flow["data"]["edges"]:
        if edge["target"] != saved_node["id"]:
            continue
        handle = edge["data"]["targetHandle"]
        field = rebuilt["template"][handle["fieldName"]]
        assert field["type"] == handle["type"]
        assert set(handle["inputTypes"]) <= set(field["input_types"])


async def test_update_rebuilt_run_flow_keeps_generated_inputs_and_selected_flow_id(monkeypatch) -> None:
    flow, node = _saved_component("run_flow_inputs.json", "RunFlow")
    saved = node["data"]["node"]
    saved["template"]["TextInput-v7wpH~input_value"]["value"] = "global_text"
    saved["template"]["TextInput-v7wpH~input_value"]["load_from_db"] = True
    saved["template"]["ChatInput-NrNFA~sender_name"]["value"] = "Zoë 🚀"
    saved["template"]["ChatInput-NrNFA~should_store_message"]["value"] = False
    original = copy.deepcopy(saved)
    built, component = _build_current(RunFlowComponent)
    graph = _selected_flow_graph()
    component._user_id = "saved-owner"
    calls = []

    async def get_graph(**kwargs):
        assert component.user_id == "saved-owner"
        calls.append(kwargs)
        return graph

    monkeypatch.setattr(component, "get_graph", get_graph)
    generated = {name for name in saved["template"] if "~" in name}
    assert not generated.intersection(built["template"])

    updated = await update_rebuilt_node(component, built, saved)

    assert generated <= updated["template"].keys()
    for name in generated:
        for key in ("value", "load_from_db"):
            if key in saved["template"][name]:
                assert updated["template"][name][key] == saved["template"][name][key]
    selected = saved["template"]["flow_name_selected"]["selected_metadata"]
    assert updated["template"]["flow_name_selected"]["selected_metadata"] == selected
    assert calls
    assert all(call["flow_id_selected"] == selected["id"] for call in calls)
    assert {out["name"] for out in saved["outputs"]} <= {out["name"] for out in updated["outputs"]}
    _assert_connected_fields_preserved(flow, node, updated)
    assert saved == original


async def test_run_flow_discovery_confirms_removed_generated_input(monkeypatch) -> None:
    _, node = _saved_component("run_flow_inputs.json", "RunFlow")
    saved = node["data"]["node"]
    built, component = _build_current(RunFlowComponent)
    graph = _selected_flow_graph(include_text=False)

    async def get_graph(**_kwargs):
        return graph

    monkeypatch.setattr(component, "get_graph", get_graph)
    warnings = []

    updated = await update_rebuilt_node(component, built, saved, warnings=warnings)

    assert "TextInput-v7wpH~input_value" not in updated["template"]
    assert "ChatInput-NrNFA~sender_name" in updated["template"]
    assert len(warnings) == 1
    assert set(warnings[0]["fields"]) == {
        "TextInput-v7wpH~input_value",
        "TextInput-v7wpH~use_global_variable",
    }
    assert warnings[0]["unverified"] is False


async def test_failed_output_refresh_marks_discovery_unverified(monkeypatch) -> None:
    _, node = _saved_component("run_flow_inputs.json", "RunFlow")
    saved = node["data"]["node"]
    built, component = _build_current(RunFlowComponent)
    graph = _selected_flow_graph()

    async def get_graph(**_kwargs):
        return graph

    async def unavailable_outputs(**_kwargs):
        message = "Output discovery is unavailable"
        raise OSError(message)

    monkeypatch.setattr(component, "get_graph", get_graph)
    monkeypatch.setattr(component, "run_and_validate_update_outputs", unavailable_outputs)
    warnings = []

    updated = await update_rebuilt_node(component, built, saved, warnings=warnings)

    assert "TextInput-v7wpH~input_value" in updated["template"]
    assert len(warnings) == 1
    assert warnings[0]["fields"] == []
    assert warnings[0]["unverified"] is True


def _greet_tool() -> StructuredTool:
    def greet(name: str, times: int = 1) -> str:
        return " ".join([f"Hello {name}"] * times)

    return StructuredTool.from_function(greet, description="Return a greeting.")


async def test_update_rebuilt_mcp_keeps_selected_tool_arguments_and_source_mode(monkeypatch) -> None:
    flow, node = _saved_component("mcp_tools_arguments.json", "MCPTools")
    saved = node["data"]["node"]
    saved["template"]["name"]["value"] = "global_name"
    saved["template"]["name"]["load_from_db"] = True
    saved["template"]["times"]["value"] = 0
    original = copy.deepcopy(saved)
    built, component = _build_current(MCPToolsComponent)
    tool = _greet_tool()
    discovered = []

    async def update_tool_list(**kwargs):
        discovered.append(kwargs)
        assert component.mcp_server == saved["template"]["mcp_server"]["value"]
        return [tool], copy.deepcopy(saved["template"]["mcp_server"]["value"])

    monkeypatch.setattr(component, "update_tool_list", update_tool_list)
    assert "name" not in built["template"]
    assert "times" not in built["template"]

    updated = await update_rebuilt_node(component, built, saved)

    assert updated["template"]["name"]["value"] == "global_name"
    assert updated["template"]["name"]["load_from_db"] is True
    assert updated["template"]["times"]["value"] == 0
    assert updated["template"]["tool"]["value"] == "greet"
    assert "greet" in updated["template"]["tool"]["options"]
    assert discovered
    _assert_connected_fields_preserved(flow, node, updated)
    assert saved == original


@pytest.mark.parametrize(
    ("fixture", "component_type", "component_class", "discovery_method", "required_refresh_fields"),
    [
        ("run_flow_inputs.json", "RunFlow", RunFlowComponent, "get_graph", {"flow_name_selected"}),
        ("mcp_tools_arguments.json", "MCPTools", MCPToolsComponent, "update_tool_list", {"mcp_server", "tool"}),
    ],
)
async def test_unavailable_generated_fields_are_named_without_exposing_discovery_error(
    monkeypatch, fixture, component_type, component_class, discovery_method, required_refresh_fields
) -> None:
    _, node = _saved_component(fixture, component_type)
    saved = node["data"]["node"]
    original = copy.deepcopy(saved)
    built, component = _build_current(component_class)
    missing = set(saved["template"]) - set(built["template"])
    assert missing

    async def unavailable(**_kwargs):
        message = "Discovery failed with private details"
        raise ValueError(message)

    monkeypatch.setattr(component, discovery_method, unavailable)
    warnings = []

    updated = await update_rebuilt_node(component, built, saved, warnings=warnings)

    assert not missing.intersection(updated["template"])
    assert len(warnings) == 1
    assert warnings[0]["code"] == "generated_fields_not_restored"
    assert set(warnings[0]["fields"]) == missing
    assert required_refresh_fields <= set(warnings[0]["refresh_fields"])
    assert warnings[0]["unverified"] is True
    assert set(warnings[0]) == {"code", "fields", "refresh_fields", "unverified"}
    assert "private details" not in json.dumps(warnings)
    assert saved == original


@pytest.mark.parametrize("catalog", ["empty", "different_tool", "fewer_arguments"])
async def test_mcp_discovery_reports_whether_missing_arguments_are_verified(monkeypatch, catalog) -> None:
    _, node = _saved_component("mcp_tools_arguments.json", "MCPTools")
    saved = node["data"]["node"]
    built, component = _build_current(MCPToolsComponent)

    def greet(name: str) -> str:
        return f"Hello {name}"

    tools = (
        []
        if catalog == "empty"
        else [
            StructuredTool.from_function(
                greet,
                name="greet" if catalog == "fewer_arguments" else "other_tool",
                description="Return a greeting.",
            )
        ]
    )

    async def discover(**_kwargs):
        return tools, copy.deepcopy(saved["template"]["mcp_server"]["value"])

    monkeypatch.setattr(component, "update_tool_list", discover)
    warnings = []

    updated = await update_rebuilt_node(component, built, saved, warnings=warnings)

    assert ("name" in updated["template"]) == (catalog == "fewer_arguments")
    assert "times" not in updated["template"]
    assert len(warnings) == 1
    assert warnings[0]["code"] == "generated_fields_not_restored"
    assert set(warnings[0]["fields"]) == ({"times"} if catalog == "fewer_arguments" else {"name", "times"})
    assert warnings[0]["unverified"] is (catalog == "empty")


async def test_fresh_mcp_template_does_not_discover_tools_without_saved_selection(monkeypatch) -> None:
    built, component = _build_current(MCPToolsComponent)

    async def unexpected_discovery(**_kwargs):
        pytest.fail("A fresh component should not discover tools during a rebuild")

    monkeypatch.setattr(component, "update_tool_list", unexpected_discovery)
    warnings = []

    updated = await update_rebuilt_node(component, built, None, warnings=warnings)

    assert updated["template"]["tool"]["value"] == built["template"]["tool"]["value"]
    assert warnings == []


@pytest.mark.parametrize("discovery_available", [True, False])
async def test_editor_update_returns_generated_field_warnings_outside_the_saved_node(
    client: AsyncClient, logged_in_headers: dict, monkeypatch, *, discovery_available: bool
) -> None:
    _, node = _saved_component("mcp_tools_arguments.json", "MCPTools")
    saved = node["data"]["node"]
    saved["template"]["name"]["value"] = "Saved name"
    saved["template"]["times"]["value"] = 3
    original_builder = endpoints.build_custom_component_template
    tool = _greet_tool()
    owners = []

    def build_with_discovery(*args, **kwargs):
        built, component = original_builder(*args, **kwargs)

        async def discover(**_kwargs):
            owners.append(component.user_id)
            if not discovery_available:
                message = "Private discovery details"
                raise ValueError(message)
            return [tool], copy.deepcopy(saved["template"]["mcp_server"]["value"])

        monkeypatch.setattr(component, "update_tool_list", discover)
        return built, component

    monkeypatch.setattr(endpoints, "build_custom_component_template", build_with_discovery)
    code = Path(inspect.getsourcefile(MCPToolsComponent)).read_text(encoding="utf-8")

    response = await client.post(
        "api/v1/custom_component", json={"code": code, "frontend_node": saved}, headers=logged_in_headers
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert owners
    assert all(owners)
    assert "warnings" not in result["data"]
    if discovery_available:
        assert result.get("warnings", []) == []
        assert result["data"]["template"]["name"]["value"] == "Saved name"
        assert result["data"]["template"]["times"]["value"] == 3
    else:
        assert len(result["warnings"]) == 1
        assert result["warnings"][0]["code"] == "generated_fields_not_restored"
        assert set(result["warnings"][0]["fields"]) == {"name", "times"}
        assert result["warnings"][0]["unverified"] is True
        assert "Private discovery details" not in json.dumps(result["warnings"])
