"""The assistant's writes pass the flow history's table rules and are recorded with the cause ``assistant``.

Components the assistant adds come with their default table rows, which have
no ids; the history refuses a write that adds a table without row ids. These
tests run the real history seam against the database.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from fastapi import status
from langflow.agentic.utils.assistant_runner import run_assistant_and_persist
from langflow.agentic.utils.flow_component import update_component_field_value
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_operation import FlowOperation
from langflow.services.deps import session_scope
from langflow.services.flow_history.envelope import decode_row
from sqlmodel import col, select

if TYPE_CHECKING:
    from httpx import AsyncClient

RUNNER_MODULE = "langflow.agentic.utils.assistant_runner"
DEFAULT_HEADERS = [{"key": "User-Agent", "value": "Langflow/1.0"}]


def _api_request_node(node_id: str, rows: list[dict]) -> dict:
    return {
        "id": node_id,
        "type": "genericNode",
        "position": {"x": 0, "y": 0},
        "data": {
            "id": node_id,
            "type": "APIRequest",
            "node": {
                "template": {
                    "headers": {"name": "headers", "type": "table", "_input_type": "TableInput", "value": rows},
                    "url_input": {"name": "url_input", "type": "str", "value": ""},
                }
            },
        },
    }


async def _create_flow(client: AsyncClient, headers: dict, data: dict) -> str:
    payload = {"name": f"assistant-{uuid4().hex[:8]}", "data": data}
    response = await client.post("api/v1/flows/", json=payload, headers=headers)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()["id"]


async def _stored(flow_id: str) -> tuple[dict, list]:
    async with session_scope() as session:
        flow = await session.get(Flow, UUID(flow_id))
        statement = (
            select(FlowOperation)
            .where(FlowOperation.flow_id == UUID(flow_id))
            .order_by(col(FlowOperation.start_revision))
        )
        rows = list((await session.exec(statement)).all())
        return flow.data, [operation for row in rows for operation in decode_row(row)]


def _rows_of(data: dict, node_id: str) -> list[dict]:
    (node,) = [node for node in data["nodes"] if node["id"] == node_id]
    return node["data"]["node"]["template"]["headers"]["value"]


def _stream_of(events: list[dict]):
    def factory(*_args, **_kwargs):
        async def gen():
            for event in events:
                yield f"data: {json.dumps(event)}\n\n"

        return gen()

    return factory


async def test_components_the_assistant_adds_get_row_ids_and_the_assistant_cause(
    client: AsyncClient, logged_in_headers, active_user
):
    flow_id = await _create_flow(client, logged_in_headers, {"nodes": [], "edges": []})
    events = [
        {"event": "flow_update", "action": "add_component", "node": _api_request_node("APIRequest-1", DEFAULT_HEADERS)},
        {"event": "complete", "data": {"result": "Added an API Request."}},
    ]
    context = SimpleNamespace(
        provider="Ollama",
        model_name="m",
        api_key_name="OLLAMA_BASE_URL",  # pragma: allowlist secret
        session_id="s",
        global_vars={},
        max_retries=0,
    )

    with (
        patch(f"{RUNNER_MODULE}._resolve_assistant_context", new_callable=AsyncMock, return_value=context),
        patch(f"{RUNNER_MODULE}.execute_flow_with_validation_streaming", side_effect=_stream_of(events)),
        patch(f"{RUNNER_MODULE}.get_working_flow", return_value=None),
        patch(f"{RUNNER_MODULE}._validate_catalog_policy_for_write"),
        patch(f"{RUNNER_MODULE}._save_flow_to_fs", new_callable=AsyncMock),
        patch(f"{RUNNER_MODULE}.get_storage_service", MagicMock()),
    ):
        async with session_scope() as session:
            result = await run_assistant_and_persist(
                session=session, user_id=active_user.id, instruction="Add an API Request", flow_id=flow_id
            )

    assert result["flow_changed"] is True
    data, operations = await _stored(flow_id)
    (row,) = _rows_of(data, "APIRequest-1")
    assert row["key"] == "User-Agent"
    assert row["_id"]
    assert row["_pos"]
    assert operations
    assert {operation.cause for operation in operations} == {"assistant"}


async def test_a_table_the_assistant_writes_keeps_the_ids_of_rows_it_still_holds(
    client: AsyncClient, logged_in_headers, active_user
):
    stored_rows = [{"_id": "r1", "_pos": "a0", "key": "User-Agent", "value": "Langflow/1.0"}]
    flow_id = await _create_flow(
        client, logged_in_headers, {"nodes": [_api_request_node("APIRequest-1", stored_rows)], "edges": []}
    )

    result = await update_component_field_value(
        flow_id,
        "APIRequest-1",
        "headers",
        [*DEFAULT_HEADERS, {"key": "Accept", "value": "json"}],
        user_id=str(active_user.id),
    )

    assert result["success"] is True, result
    data, operations = await _stored(flow_id)
    rows = _rows_of(data, "APIRequest-1")
    assert rows[0] == stored_rows[0]
    assert rows[1]["key"] == "Accept"
    assert rows[1]["_id"]
    assert rows[1]["_pos"] > "a0"
    assert operations
    assert {operation.cause for operation in operations} == {"assistant"}


async def test_the_flow_tool_takes_the_writers_turn_like_any_other_graph_write(
    client: AsyncClient, logged_in_headers, active_user
):
    """A write that does not rotate the token is invisible to every open editor.

    Reproduced against a running assistant: the tool edited the flow, the token
    stayed put, and a human holding the pre-edit token then saved with 200,
    overwriting the agent's work with nobody told.
    """
    flow_id = await _create_flow(
        client, logged_in_headers, {"nodes": [_api_request_node("APIRequest-1", [])], "edges": []}
    )
    async with session_scope() as session:
        before = (await session.get(Flow, UUID(flow_id))).version_token

    result = await update_component_field_value(
        flow_id, "APIRequest-1", "url_input", "https://example.com", user_id=str(active_user.id)
    )

    assert result["success"] is True, result
    async with session_scope() as session:
        flow = await session.get(Flow, UUID(flow_id))
    assert flow.version_token != before
    assert flow.last_modified_by == active_user.id
