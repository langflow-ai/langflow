"""A background run resumed after a Human Input pause keeps the run's tweaks.

Real flow (Chat Input -> Human Input -> one Chat Output per branch) through the
HTTP API: submit in background mode, wait for the pause, resume, then read the
stored messages. Nodes that run after the pause must see the same tweaks as
the nodes that ran before it.
"""

from __future__ import annotations

import asyncio
import json
from uuid import UUID, uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.jobs.model import Job, JobStatus
from langflow.services.database.models.message.model import MessageTable
from lfx.services.deps import session_scope
from sqlmodel import select

pytestmark = pytest.mark.usefixtures("client")


def _encode_handle(handle: dict) -> str:
    return json.dumps(dict(sorted(handle.items())), separators=(",", ":")).replace('"', "œ")


def _edge(source: str, output: str, data_type: str, target: str, field: str, input_types: list[str]) -> dict:
    source_handle = {"dataType": data_type, "id": source, "name": output, "output_types": ["Message"]}
    target_handle = {"fieldName": field, "id": target, "inputTypes": input_types, "type": "str"}
    return {
        "id": f"{source}-{target}",
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
    """Chat Input ``In`` -> Human Input ``Ask`` -> ``OutYes`` (Approve) / ``OutNo`` (Reject)."""
    response = await client.get("api/v1/all", headers=logged_in_headers)
    assert response.status_code == 200, response.text
    components = response.json()

    def template(name: str) -> dict:
        return next(category[name] for category in components.values() if name in category)

    chat_input, human_input, chat_output = template("ChatInput"), template("HumanInput"), template("ChatOutput")
    prompt_types = human_input["template"]["prompt"].get("input_types") or ["Message"]
    output_types = chat_output["template"]["input_value"]["input_types"]
    data = {
        "nodes": [
            _node("In", "ChatInput", chat_input),
            _node("Ask", "HumanInput", human_input),
            _node("OutYes", "ChatOutput", chat_output),
            _node("OutNo", "ChatOutput", chat_output),
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
        session.add(Flow(id=flow_id, name="resume-tweaks-flow", data=data, user_id=created_api_key.user_id))
        await session.flush()
    yield str(flow_id)
    async with session_scope() as session:
        flow = await session.get(Flow, flow_id)
        if flow:
            await session.delete(flow)


async def _wait_for_status(job_id: str, statuses: set[JobStatus]) -> JobStatus | None:
    for _ in range(150):
        async with session_scope() as session:
            row = await session.get(Job, UUID(job_id))
        if row is not None and row.status in statuses:
            return row.status
        await asyncio.sleep(0.1)
    return None


async def test_resumed_run_applies_tweaks_to_nodes_after_the_pause(client, created_api_key, approval_flow):
    headers = {"x-api-key": created_api_key.api_key}
    submit = await client.post(
        "api/v2/workflows",
        json={
            "flow_id": approval_flow,
            "mode": "background",
            "tweaks": {
                "In": {"input_value": "hello", "sender_name": "TWEAKED-BEFORE"},
                "OutNo": {"sender_name": "TWEAKED-AFTER"},
            },
        },
        headers=headers,
    )
    assert submit.status_code == 200, submit.text
    job_id = submit.json()["job_id"]
    assert await _wait_for_status(job_id, {JobStatus.SUSPENDED, JobStatus.FAILED}) == JobStatus.SUSPENDED

    resume = await client.post(
        f"api/v2/workflows/{job_id}/resume",
        json={"request_id": f"Ask:{job_id}", "decision": {"action_id": "reject"}},
        headers=headers,
    )
    assert resume.status_code == 200, resume.text
    assert await _wait_for_status(job_id, {JobStatus.COMPLETED, JobStatus.FAILED}) == JobStatus.COMPLETED

    async with session_scope() as session:
        messages = (await session.exec(select(MessageTable).where(MessageTable.flow_id == UUID(approval_flow)))).all()
    sender_names = {(message.sender_name, message.text) for message in messages}
    assert ("TWEAKED-BEFORE", "hello") in sender_names
    assert ("TWEAKED-AFTER", "hello") in sender_names
