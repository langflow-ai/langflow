"""Public MCP calls can use request credentials without inheriting owner secrets."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.api.utils.core import extract_global_variables_from_headers
from langflow.api.v1 import endpoints, mcp_utils
from langflow.services.authorization.public_access import public_execution_user
from langflow.services.database.models.flow.model import Flow
from lfx.custom.custom_component.custom_component import CustomComponent


def _flow_data(template: dict) -> dict:
    return {
        "nodes": [{"id": "credential-node", "data": {"type": "APIRequest", "node": {"template": template}}}],
        "edges": [],
    }


async def _call_public_tool(
    monkeypatch, flow: Flow, request_variables: dict
) -> tuple[list, MagicMock, SimpleNamespace]:
    """Dispatch a public MCP tool call with graph building and job execution stubbed."""
    graph = SimpleNamespace(vertices=[], set_run_id=MagicMock())
    build_graph = MagicMock(return_value=graph)
    jobs = SimpleNamespace(
        create_job=AsyncMock(),
        execute_with_status=AsyncMock(return_value=([], "public-session")),
    )

    monkeypatch.setattr(mcp_utils, "get_flow_snake_case", AsyncMock(return_value=flow))
    monkeypatch.setattr(mcp_utils, "with_db_session", lambda operation: operation(None))
    monkeypatch.setattr(mcp_utils, "prepare_public_flow_build", AsyncMock(return_value=None))
    monkeypatch.setattr(mcp_utils.get_mcp_config(), "enable_progress_notifications", False)
    monkeypatch.setattr(endpoints, "prepare_flow_build_for_user", AsyncMock(return_value=None))
    monkeypatch.setattr(endpoints, "try_warm_run_graph", AsyncMock(return_value=None))
    monkeypatch.setattr(endpoints, "apply_global_variable_defaults", AsyncMock(side_effect=lambda data, _user: data))
    monkeypatch.setattr(endpoints.Graph, "from_payload", build_graph)
    monkeypatch.setattr(endpoints, "get_job_service", lambda: jobs)

    user_token = mcp_utils.current_user_ctx.set(SimpleNamespace(id=flow.user_id, is_superuser=False))
    caller_token = mcp_utils.authenticated_caller_ctx.set(None)
    variables_token = mcp_utils.current_request_variables_ctx.set(request_variables)
    headers_token = mcp_utils.current_request_headers_ctx.set(None)
    try:
        result = await mcp_utils.handle_call_tool(
            "public_tool", {"input_value": "hello"}, SimpleNamespace(), project_id=flow.folder_id
        )
    finally:
        mcp_utils.current_request_headers_ctx.reset(headers_token)
        mcp_utils.current_request_variables_ctx.reset(variables_token)
        mcp_utils.authenticated_caller_ctx.reset(caller_token)
        mcp_utils.current_user_ctx.reset(user_token)
    return result, build_graph, jobs


@pytest.mark.parametrize("location", ["field", "table-dict", "table-list"])
@pytest.mark.parametrize(
    ("variable_name", "header_name"),
    [
        ("CALLER_TOKEN", "X-Langflow-Global-Var-CALLER_TOKEN"),
        ("x-api-key", "x-api-key"),
        ("authorization", "Authorization"),
    ],
)
async def test_public_mcp_executes_with_caller_supplied_credentials(
    monkeypatch, location: str, variable_name: str, header_name: str
) -> None:
    credential_field = {"name": "api_key", "password": True, "load_from_db": True, "value": variable_name}
    if location == "field":
        template = {"api_key": credential_field}
    else:
        row_metadata = {"value": True} if location == "table-dict" else ["value"]
        template = {
            "headers": {
                "name": "headers",
                "type": "table",
                "table_schema": [{"name": "value", "type": "str", "load_from_db": True}],
                "value": [{"key": "Authorization", "value": variable_name, "__load_from_db_fields": row_metadata}],
            }
        }
    template["owner_secret"] = {"name": "owner_secret", "password": True, "value": "owner-only-value"}
    flow = Flow(id=uuid4(), name="Public tool", user_id=uuid4(), folder_id=uuid4(), data=_flow_data(template))
    stored_data = deepcopy(flow.data)
    request_variables = extract_global_variables_from_headers(
        {header_name: "caller-only-value"}, include_auth_headers=True
    )
    result, build_graph, jobs = await _call_public_tool(monkeypatch, flow, request_variables)

    assert result == []
    jobs.execute_with_status.assert_awaited_once()
    built_data = build_graph.call_args.args[0]
    built_template = built_data["nodes"][0]["data"]["node"]["template"]
    assert built_template["owner_secret"]["value"] is None
    reference = (
        built_template["api_key"]["value"] if location == "field" else built_template["headers"]["value"][0]["value"]
    )
    assert reference == variable_name
    assert build_graph.call_args.kwargs["user_id"] == str(public_execution_user().id)
    context = build_graph.call_args.kwargs["context"]
    component = SimpleNamespace(graph=SimpleNamespace(context=context))
    resolved = await CustomComponent.get_variable(component, reference, "api_key", session=None)
    assert resolved == request_variables[variable_name]
    assert flow.data == stored_data


@pytest.mark.parametrize("flow_shape", ["plain-binding", "caller-key-and-plain-binding"])
async def test_public_mcp_request_variables_keep_plain_bindings(monkeypatch, flow_shape: str) -> None:
    # MCP routes capture an Authorization header as a request variable, so this
    # call sends variables even when the flow never asks for a caller credential.
    with_caller_credential = flow_shape == "caller-key-and-plain-binding"
    template = {"base_url": {"name": "base_url", "load_from_db": True, "value": "OLLAMA_BASE_URL"}}
    if with_caller_credential:
        template["api_key"] = {"name": "api_key", "password": True, "load_from_db": True, "value": "CALLER_TOKEN"}
    flow = Flow(id=uuid4(), name="Public tool", user_id=uuid4(), folder_id=uuid4(), data=_flow_data(template))
    request_variables = extract_global_variables_from_headers(
        {"Authorization": "Bearer client-token", "X-Langflow-Global-Var-CALLER_TOKEN": "caller-only-value"},
        include_auth_headers=True,
    )

    result, build_graph, jobs = await _call_public_tool(monkeypatch, flow, request_variables)

    assert result == []
    jobs.execute_with_status.assert_awaited_once()
    built_template = build_graph.call_args.args[0]["nodes"][0]["data"]["node"]["template"]
    assert built_template["base_url"]["value"] == "OLLAMA_BASE_URL"
    if with_caller_credential:
        assert built_template["api_key"]["value"] == "CALLER_TOKEN"


@pytest.mark.parametrize(
    "field",
    [
        {"name": "api_key", "password": True, "value": "owner-only-value"},
        {"name": "api_key", "password": True, "load_from_db": True, "value": "OWNER_TOKEN"},
        {"name": "api_key", "password": True, "load_from_db": False, "value": "CALLER_TOKEN"},
        {
            "name": "headers",
            "type": "table",
            "table_schema": [{"name": "value", "type": "str", "load_from_db": True}],
            "value": [{"key": "Authorization", "value": "CALLER_TOKEN", "__load_from_db_fields": {"value": False}}],
        },
    ],
    ids=["literal", "unmatched-reference", "literal-matches-request-name", "literal-table-cell"],
)
def test_shared_flow_rejects_variables_while_owner_credentials_remain(field: dict) -> None:
    template = {
        field["name"]: field,
        "caller_credential": {
            "name": "caller_credential",
            "password": True,
            "load_from_db": True,
            "value": "CALLER_TOKEN",
        },
    }
    flow = Flow(id=uuid4(), name="Shared tool", user_id=uuid4(), data=_flow_data(template))
    stored_data = deepcopy(flow.data)

    with pytest.raises(HTTPException, match="Cannot override variables") as error:
        endpoints._reject_shared_secret_variable_overrides(
            flow, public_execution_user(), {"CALLER_TOKEN": "caller-only-value"}
        )

    assert error.value.status_code == 400
    assert flow.data == stored_data
