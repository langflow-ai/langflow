"""Anonymous flows keep API Request destinations under the author's control."""

import copy
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from lfx.base.tools.constants import TOOL_OUTPUT_NAME
from lfx.components.data_source.api_request import APIRequestComponent
from lfx.graph import Graph
from lfx.graph.graph.utils import process_flow
from lfx.services.model_provider_policy import (
    reset_current_model_provider_policy_context,
    set_current_model_provider_policy_context,
)
from lfx.utils import flow_validation as fv


def _node(node_id, component_type, node_info):
    return {"id": node_id, "type": "genericNode", "data": {"id": node_id, "type": component_type, "node": node_info}}


def _edge(source, target, field_name, output_name="message"):
    source_handle = {"id": source, "name": output_name, "dataType": "ChatInput", "output_types": ["Message"]}
    target_handle = {"id": target, "fieldName": field_name, "type": "str", "inputTypes": ["Message"]}
    return {
        "source": source,
        "target": target,
        "sourceHandle": json.dumps(source_handle).replace('"', "œ"),
        "targetHandle": json.dumps(target_handle).replace('"', "œ"),
        "data": {"sourceHandle": source_handle, "targetHandle": target_handle},
    }


@pytest.fixture
def request_flow():
    template = APIRequestComponent(_session_id="test-session").to_frontend_node()["data"]["node"]
    template["template"]["url_input"]["value"] = "https://api.example/v1"
    return {
        "nodes": [
            _node("chat", "ChatInput", {"template": {}}),
            _node("request", "APIRequest", template),
        ],
        "edges": [_edge("chat", "request", "url_input")],
    }


@pytest.mark.parametrize("component_type", ["APIRequest", "APIRequestComponent", "API Request"])
@pytest.mark.parametrize("field_name", ["url_input", "curl_input"])
def test_public_flow_blocks_wired_api_request_url(request_flow, component_type, field_name):
    request_flow["nodes"][1]["data"]["type"] = component_type
    request_flow["edges"] = [_edge("chat", "request", field_name)]

    with pytest.raises(fv.PublicFlowValidationError, match="API Request destinations"):
        fv.validate_public_flow_no_code_execution(request_flow)


def test_public_flow_matches_relabelled_request_by_trusted_hash(request_flow):
    node_info = request_flow["nodes"][1]["data"]["node"]
    node_info["display_name"] = "Renamed"
    request_flow["nodes"][1]["data"]["type"] = "Renamed"
    code_hash = hashlib.sha256(node_info["template"]["code"]["value"].encode()).hexdigest()[:12]

    with pytest.raises(fv.PublicFlowValidationError, match="API Request destinations"):
        fv.validate_public_flow_no_code_execution(request_flow, type_to_current_hash={"APIRequest": {code_hash}})


@pytest.mark.parametrize("field_key", ["field_name", "name"])
def test_public_flow_matches_executor_target_handle_variants(request_flow, field_key):
    handle = request_flow["edges"][0]["data"]["targetHandle"]
    handle[field_key] = handle.pop("fieldName")
    if field_key == "name":
        handle["output_types"] = handle.pop("inputTypes")

    with pytest.raises(fv.PublicFlowValidationError, match="API Request destinations"):
        fv.validate_public_flow_no_code_execution(request_flow)


@pytest.mark.parametrize("field_name", ["body", "headers", "query_params"])
def test_public_flow_keeps_wired_payload_with_static_url(request_flow, field_name):
    request_flow["edges"] = [_edge("chat", "request", field_name)]

    fv.validate_public_flow_no_code_execution(request_flow)


def test_public_flow_keeps_static_url(request_flow):
    request_flow["edges"] = []

    fv.validate_public_flow_no_code_execution(request_flow)


def test_public_flow_blocks_nested_wired_destination(request_flow):
    grouped = {
        "nodes": [_node("group", "GroupNode", {"template": {}, "flow": {"data": request_flow}})],
        "edges": [],
    }

    with pytest.raises(fv.PublicFlowValidationError, match="API Request destinations"):
        fv.validate_public_flow_no_code_execution(grouped)


def test_public_flow_blocks_group_proxy_destination(request_flow):
    child = request_flow["nodes"].pop()
    group = _node(
        "group",
        "GroupNode",
        {
            "template": {
                "destination": {
                    "name": "destination",
                    "value": "https://api.example/v1",
                    "proxy": {"id": "request", "field": "url_input"},
                }
            },
            "flow": {"data": {"nodes": [child], "edges": []}},
        },
    )
    request_flow["nodes"].append(group)
    edge = _edge("chat", "group", "destination")
    edge["data"]["targetHandle"]["proxy"] = {"id": "request", "field": "url_input"}
    request_flow["edges"] = [edge]
    original = copy.deepcopy(request_flow)
    expanded = process_flow(request_flow)
    assert expanded["edges"][0]["target"] == "request"
    assert expanded["edges"][0]["data"]["targetHandle"]["fieldName"] == "url_input"

    with pytest.raises(fv.PublicFlowValidationError, match="API Request destinations"):
        fv.validate_public_flow_no_code_execution(request_flow)

    assert request_flow == original


def test_public_flow_blocks_api_request_tool_destination(request_flow):
    request_flow["nodes"].append(_node("agent", "Agent", {"template": {}}))
    request_flow["nodes"][1]["data"]["node"]["tool_mode"] = True
    edge = _edge("request", "agent", "tools", TOOL_OUTPUT_NAME)
    edge["data"]["sourceHandle"].update(dataType="APIRequest", output_types=["Tool"])
    edge["data"]["targetHandle"].update(type="other", inputTypes=["Tool"])
    request_flow["edges"] = [edge]

    with pytest.raises(fv.PublicFlowValidationError, match="API Request destinations"):
        fv.validate_public_flow_no_code_execution(request_flow)


@pytest.mark.parametrize("ui_tool_mode", [False, True])
async def test_public_flow_blocks_runtime_destination_tools_despite_saved_flags(request_flow, ui_tool_mode):
    request = request_flow["nodes"][1]
    node_info = request["data"]["node"]
    node_info["tool_mode"] = ui_tool_mode
    for name in ("url_input", "curl_input"):
        node_info["template"][name]["tool_mode"] = False
    node_info["template"]["headers"]["value"] = [{"key": "Authorization", "value": "test-credential"}]

    token = set_current_model_provider_policy_context(user_id="local-admin", attributes={"is_superuser": True})
    try:
        graph = Graph.from_payload({"nodes": [copy.deepcopy(request)], "edges": []}, user_id="local-admin")
        vertex = graph.get_vertex("request")
        component = vertex.custom_component
        component.set_attributes({name: value for name, value in vertex.params.items() if name != "code"})
        tools = await component.to_toolkit()
    finally:
        reset_current_model_provider_policy_context(token)

    assert tools
    for tool in tools:
        assert {"url_input", "curl_input"} <= tool.args.keys()
    assert component.headers == [{"key": "Authorization", "value": "test-credential"}]

    request_flow["nodes"].append(_node("agent", "Agent", {"template": {}}))
    request_flow["edges"] = [_edge("request", "agent", "tools", TOOL_OUTPUT_NAME)]
    with pytest.raises(fv.PublicFlowValidationError, match="API Request destinations"):
        fv.validate_public_flow_no_code_execution(request_flow)


def test_public_flow_blocks_tool_mode_without_a_connected_output(request_flow):
    node_info = request_flow["nodes"][1]["data"]["node"]
    node_info["tool_mode"] = True
    for name in ("url_input", "curl_input"):
        node_info["template"][name]["tool_mode"] = False
    request_flow["edges"] = []

    with pytest.raises(fv.PublicFlowValidationError, match="API Request destinations"):
        fv.validate_public_flow_no_code_execution(request_flow)


def test_public_flow_checks_tool_output_even_without_ui_tool_mode(request_flow):
    request_flow["nodes"].append(_node("agent", "Agent", {"template": {}}))
    request_flow["nodes"][1]["data"]["node"]["tool_mode"] = False
    request_flow["edges"] = [_edge("request", "agent", "tools", TOOL_OUTPUT_NAME)]

    with pytest.raises(fv.PublicFlowValidationError, match="API Request destinations"):
        fv.validate_public_flow_no_code_execution(request_flow)


def test_public_flow_uses_execution_handle_not_display_handle(request_flow):
    request_flow["edges"][0]["targetHandle"] = "str|body|request"

    with pytest.raises(fv.PublicFlowValidationError, match="API Request destinations"):
        fv.validate_public_flow_no_code_execution(request_flow)


def test_public_flow_checks_legacy_destination_handle(request_flow):
    edge = request_flow["edges"][0]
    del edge["data"]
    edge["targetHandle"] = "str|url_input|request"

    with pytest.raises(fv.PublicFlowValidationError, match="API Request destinations"):
        fv.validate_public_flow_no_code_execution(request_flow)


async def test_public_preparation_checks_destination_after_sanitization(monkeypatch, request_flow):
    settings = SimpleNamespace(allow_public_custom_components=False, allow_custom_components=True)
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: SimpleNamespace(settings=settings))
    codes = {"ChatInput": "# trusted chat", "APIRequest": "# trusted request"}
    hashes = {name: {hashlib.sha256(code.encode()).hexdigest()[:12]} for name, code in codes.items()}
    monkeypatch.setattr(fv, "_ensure_public_component_lookup_snapshot", AsyncMock(return_value=(codes, hashes)))

    with pytest.raises(fv.PublicFlowValidationError, match="API Request destinations"):
        await fv.prepare_public_flow_build(request_flow)
