"""Only background runs may execute a flow that pauses at a Human Input node.

``sync`` and ``stream`` runs (and the public stream endpoint) have no durable job
to suspend into, so they used to run straight through the Human Input node: every
branch received an empty message and ran before any human decided. These tests
drive a real flow (Chat Input -> Human Input -> one Chat Output per branch)
through the HTTP API and check that no branch runs outside background mode.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient, codes
from langflow.services.database.models.flow.model import AccessTypeEnum, Flow
from langflow.services.database.models.jobs.model import Job, JobStatus
from langflow.services.database.models.message.model import MessageTable
from lfx.services.deps import session_scope
from sqlmodel import func, select

pytestmark = pytest.mark.usefixtures("client")

_BRANCH_SENDERS = ("BRANCH-APPROVE", "BRANCH-REJECT")


def _encode_handle(handle: dict) -> str:
    return json.dumps(dict(sorted(handle.items())), separators=(",", ":")).replace('"', "œ")


def _edge(source: str, output: str, data_type: str, target: str, field: str, input_types: list[str]) -> dict:
    source_handle = {"dataType": data_type, "id": source, "name": output, "output_types": ["Message"]}
    target_handle = {"fieldName": field, "id": target, "inputTypes": input_types, "type": "str"}
    return {
        "id": f"{source}-{output}-{target}",
        "source": source,
        "target": target,
        "sourceHandle": _encode_handle(source_handle),
        "targetHandle": _encode_handle(target_handle),
        "data": {"sourceHandle": source_handle, "targetHandle": target_handle},
    }


def _node(node_id: str, node_type: str, template: dict) -> dict:
    return {
        "id": node_id,
        "type": "genericNode",
        "position": {"x": 0, "y": 0},
        "data": {"id": node_id, "type": node_type, "node": template},
    }


@pytest.fixture
async def approval_flow(client, created_api_key, logged_in_headers):
    """Public flow: Chat Input ``In`` -> Human Input ``Ask`` -> ``OutYes`` (Approve) / ``OutNo`` (Reject)."""
    response = await client.get("api/v1/all", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    components = response.json()

    def template(name: str) -> dict:
        return next(category[name] for category in components.values() if name in category)

    chat_input, human_input, chat_output = template("ChatInput"), template("HumanInput"), template("ChatOutput")
    prompt_types = human_input["template"]["prompt"].get("input_types") or ["Message"]
    output_types = chat_output["template"]["input_value"]["input_types"]
    out_yes, out_no = json.loads(json.dumps(chat_output)), json.loads(json.dumps(chat_output))
    out_yes["template"]["sender_name"]["value"] = _BRANCH_SENDERS[0]
    out_no["template"]["sender_name"]["value"] = _BRANCH_SENDERS[1]
    data = {
        "nodes": [
            _node("In", "ChatInput", chat_input),
            _node("Ask", "HumanInput", human_input),
            _node("OutYes", "ChatOutput", out_yes),
            _node("OutNo", "ChatOutput", out_no),
        ],
        "edges": [
            _edge("In", "message", "ChatInput", "Ask", "prompt", prompt_types),
            _edge("Ask", "branch_approve", "HumanInput", "OutYes", "input_value", output_types),
            _edge("Ask", "branch_reject", "HumanInput", "OutNo", "input_value", output_types),
        ],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }
    flow_id = uuid4()
    async with session_scope() as session:
        session.add(
            Flow(
                id=flow_id,
                name=f"hitl-modes-{flow_id}",
                data=data,
                user_id=created_api_key.user_id,
                access_type=AccessTypeEnum.PUBLIC,
            )
        )
        await session.flush()
    yield str(flow_id)
    async with session_scope() as session:
        flow = await session.get(Flow, flow_id)
        if flow:
            await session.delete(flow)


async def _branch_message_count() -> int:
    """Messages written by either branch's Chat Output, i.e. after the Human Input node."""
    async with session_scope() as session:
        query = select(func.count()).where(MessageTable.sender_name.in_(_BRANCH_SENDERS))
        return (await session.exec(query)).one()


async def _wait_for_status(job_id: str, statuses: set[JobStatus]) -> JobStatus | None:
    for _ in range(150):
        async with session_scope() as session:
            row = await session.get(Job, UUID(job_id))
        if row is not None and row.status in statuses:
            return row.status
        await asyncio.sleep(0.1)
    return None


def _assert_hitl_refused(response, flow_id: str) -> None:
    assert response.status_code == codes.BAD_REQUEST, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "HITL_REQUIRES_BACKGROUND"
    assert "Human-in-the-Loop" in detail["message"]
    assert "mode='background'" in detail["message"]
    assert detail["flow_id"] == flow_id


async def test_sync_run_of_hitl_flow_is_refused_before_any_branch_runs(client, created_api_key, approval_flow):
    before = await _branch_message_count()

    response = await client.post(
        "api/v2/workflows",
        json={"flow_id": approval_flow, "input_value": "delete prod db?"},
        headers={"x-api-key": created_api_key.api_key},
    )

    _assert_hitl_refused(response, approval_flow)
    assert await _branch_message_count() == before


async def test_stream_run_of_hitl_flow_is_refused_before_any_branch_runs(client, created_api_key, approval_flow):
    before = await _branch_message_count()

    response = await client.post(
        "api/v2/workflows",
        json={"flow_id": approval_flow, "input_value": "delete prod db?", "mode": "stream"},
        headers={"x-api-key": created_api_key.api_key},
    )

    _assert_hitl_refused(response, approval_flow)
    assert await _branch_message_count() == before


async def test_stream_run_is_refused_when_request_data_adds_human_input(client, created_api_key, approval_flow):
    """The live-canvas ``data`` override is what runs, so it is what the guard inspects."""
    async with session_scope() as session:
        flow = await session.get(Flow, UUID(approval_flow))
        canvas = flow.data
        flow.data = {"nodes": [], "edges": []}
        session.add(flow)

    response = await client.post(
        "api/v2/workflows",
        json={"flow_id": approval_flow, "input_value": "delete prod db?", "mode": "stream", "data": canvas},
        headers={"x-api-key": created_api_key.api_key},
    )

    _assert_hitl_refused(response, approval_flow)


async def test_public_run_of_hitl_flow_is_refused_before_any_branch_runs(client: AsyncClient, approval_flow):
    before = await _branch_message_count()
    client.cookies.clear()
    client.cookies.set("client_id", "hitl-public-visitor")

    response = await client.post(
        "api/v2/workflows/public",
        json={"flow_id": approval_flow, "input_value": "delete prod db?"},
    )

    assert response.status_code == codes.BAD_REQUEST, response.text
    assert "Human-in-the-Loop" in response.json()["detail"]
    assert await _branch_message_count() == before


async def test_background_run_of_hitl_flow_still_suspends(client, created_api_key, approval_flow):
    before = await _branch_message_count()

    response = await client.post(
        "api/v2/workflows",
        json={"flow_id": approval_flow, "input_value": "delete prod db?", "mode": "background"},
        headers={"x-api-key": created_api_key.api_key},
    )

    assert response.status_code == codes.OK, response.text
    job_id = response.json()["job_id"]
    assert await _wait_for_status(job_id, {JobStatus.SUSPENDED, JobStatus.FAILED}) == JobStatus.SUSPENDED
    assert await _branch_message_count() == before


def _tool_flow(approval_actions: list[str]) -> dict:
    template = {"tools_metadata": {"value": [{"name": "fetch_content", "approval_actions": approval_actions}]}}
    return {"nodes": [{"id": "Tool", "data": {"id": "Tool", "type": "URLComponent", "node": {"template": template}}}]}


@pytest.mark.parametrize("mode", ["sync", "stream"])
def test_tweak_that_adds_tool_approval_is_refused(mode):
    """Tweaks are applied before the run, so the guard must see the tweaked graph."""
    from fastapi import HTTPException
    from langflow.api.v2.workflow_validation import _reject_hitl_outside_background
    from lfx.workflow.converters import ParsedWorkflowRun

    stored = _tool_flow([])
    parsed = ParsedWorkflowRun(
        flow_id="flow",
        mode=mode,
        tweaks={"Tool": {"tools_metadata": [{"name": "fetch_content", "approval_actions": ["approve"]}]}},
    )

    with pytest.raises(HTTPException) as exc_info:
        _reject_hitl_outside_background(parsed, SimpleNamespace(data=stored))

    assert exc_info.value.detail["code"] == "HITL_REQUIRES_BACKGROUND"
    assert stored == _tool_flow([]), "the guard must not mutate the stored graph"


def test_refused_tweak_still_raises_tweak_refused_error(monkeypatch):
    from langflow.api.v2.workflow_validation import _reject_hitl_outside_background
    from lfx.exceptions.tweaks import TweakRefusedError
    from lfx.processing import process
    from lfx.workflow.converters import ParsedWorkflowRun

    def _refuse(*_args, **_kwargs):
        raise TweakRefusedError(["tools_metadata"], reason="protected")

    monkeypatch.setattr(process, "process_tweaks", _refuse)
    parsed = ParsedWorkflowRun(flow_id="flow", mode="sync", tweaks={"Tool": {"tools_metadata": []}})

    with pytest.raises(TweakRefusedError):
        _reject_hitl_outside_background(parsed, SimpleNamespace(data=_tool_flow([])))


def test_malformed_graph_with_tweaks_is_left_to_run_validation():
    """The guard only inspects; a graph process_tweaks cannot read must not become a 500 here."""
    from langflow.api.v2.workflow_validation import _reject_hitl_outside_background
    from lfx.workflow.converters import ParsedWorkflowRun

    parsed = ParsedWorkflowRun(flow_id="flow", mode="stream", data={"edges": []}, tweaks={"Tool": {"x": 1}})

    _reject_hitl_outside_background(parsed, SimpleNamespace(data=None))
