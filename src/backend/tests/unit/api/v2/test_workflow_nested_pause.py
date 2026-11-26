"""A Run Flow whose child needs a human decision pauses and resumes through the v2 Workflows API.

Real flows: the parent is Run Flow [-> Chat Output]. The child is Chat Input -> Human Input -> one
Chat Output per branch, or Chat Input -> an Agent that asks before each tool call -> Chat Output.
A background run suspends on the child's request, and the decision posted to the resume endpoint
reaches the child.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from langflow.services.data_subjects.builder_flow_steps import _drain_flow_history
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.jobs.model import Job, JobCheckpoint, JobStatus
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import get_job_service, get_settings_service
from lfx.graph.checkpoint.schema import GraphCheckpoint
from lfx.run.hitl import nested_request_prefix
from lfx.services.deps import session_scope
from sqlmodel import select, update

from tests.unit.api.v2._scripted_agent import ScriptedAgent

pytestmark = pytest.mark.usefixtures("client")

_BRANCH_SENDERS = {"approve": "BRANCH-APPROVE", "reject": "BRANCH-REJECT"}
_AGENT_SENDER = "CHILD-AGENT"


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


def _copy(value):
    return json.loads(json.dumps(value))


async def _templates(client, headers) -> dict:
    response = await client.get("api/v1/all", headers=headers)
    assert response.status_code == 200, response.text
    components = response.json()
    return {
        name: _copy(next(category[name] for category in components.values() if name in category))
        for name in ("ChatInput", "HumanInput", "ChatOutput", "RunFlow")
    }


def _parent_data(templates: dict, child_id, output_vertex: str, *, terminal: bool = False) -> dict:
    """Run Flow running ``child_id`` [-> Chat Output reading ``output_vertex``'s message]."""
    chat_input, chat_output, run_flow = templates["ChatInput"], templates["ChatOutput"], templates["RunFlow"]
    run_flow["template"]["flow_id_selected"]["value"] = str(child_id)
    run_flow["template"]["flow_name_selected"]["value"] = f"nested-child-{child_id}"
    run_flow["template"]["In~input_value"] = {
        **_copy(chat_input["template"]["input_value"]),
        "name": "In~input_value",
        "value": "delete prod db?",
        "tool_mode": True,
    }
    run_flow["outputs"] = [
        {
            **_copy(chat_output["outputs"][0]),
            "name": f"{output_vertex}~message",
            "method": f"_resolve_flow_output__{output_vertex}__message",
        }
    ]
    output_types = chat_output["template"]["input_value"]["input_types"]
    nodes, edges = [_node("Runner", "RunFlow", run_flow)], []
    if not terminal:
        nodes.append(_node("Done", "ChatOutput", _copy(chat_output)))
        edges.append(_edge("Runner", f"{output_vertex}~message", "RunFlow", "Done", "input_value", output_types))
    return {"nodes": nodes, "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": 1}}


async def _store(user_id, child_data: dict, parent_for_child) -> tuple[UUID, UUID]:
    child_id, parent_id = uuid4(), uuid4()
    async with session_scope() as session:
        session.add(Flow(id=child_id, name=f"nested-child-{child_id}", data=child_data, user_id=user_id))
        session.add(
            Flow(id=parent_id, name=f"nested-parent-{parent_id}", data=parent_for_child(child_id), user_id=user_id)
        )
        await session.flush()
    return parent_id, child_id


async def _delete(*flow_ids) -> None:
    async with session_scope() as session:
        for flow_id in flow_ids:
            flow = await session.get(Flow, flow_id)
            if flow:
                await session.delete(flow)


@pytest.fixture(params=["approve", "reject", "approve-terminal"])
async def flows(request, client, created_api_key, logged_in_headers):
    """Returns (parent_flow_id, child_flow_id, action). The parent reads the output of the branch ``action`` takes.

    In ``approve-terminal`` the Run Flow is the parent's last vertex, so the pause is requested in the last layer.
    """
    action, _, terminal = request.param.partition("-")
    templates = await _templates(client, logged_in_headers)
    chat_input, human_input, chat_output = templates["ChatInput"], templates["HumanInput"], templates["ChatOutput"]
    prompt_types = human_input["template"]["prompt"].get("input_types") or ["Message"]
    output_types = chat_output["template"]["input_value"]["input_types"]
    out_yes, out_no = _copy(chat_output), _copy(chat_output)
    out_yes["template"]["sender_name"]["value"] = _BRANCH_SENDERS["approve"]
    out_no["template"]["sender_name"]["value"] = _BRANCH_SENDERS["reject"]
    child_data = {
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
    output_vertex = "OutYes" if action == "approve" else "OutNo"
    parent_id, child_id = await _store(
        created_api_key.user_id,
        child_data,
        lambda child: _parent_data(templates, child, output_vertex, terminal=bool(terminal)),
    )
    yield str(parent_id), str(child_id), action
    await _delete(parent_id, child_id)


@pytest.fixture
async def agent_flows(client, created_api_key, logged_in_headers, monkeypatch):
    """Returns (parent_flow_id, child_flow_id). The child's Agent asks before its one tool call."""
    # The Agent's model and tool are scripted in its own code, which makes it a custom component.
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "allow_custom_components", True)
    monkeypatch.setattr(settings, "custom_component_admin_only", False)
    templates = await _templates(client, logged_in_headers)
    chat_input, chat_output = templates["ChatInput"], templates["ChatOutput"]
    agent = ScriptedAgent(_id="Agent", tool_policy="ask").to_frontend_node()["data"]["node"]
    out = _copy(chat_output)
    out["template"]["sender_name"]["value"] = _AGENT_SENDER
    output_types = chat_output["template"]["input_value"]["input_types"]
    agent_types = agent["template"]["input_value"].get("input_types") or ["Message"]
    child_data = {
        "nodes": [
            _node("In", "ChatInput", chat_input),
            _node("Agent", "ScriptedAgent", agent),
            _node("Out", "ChatOutput", out),
        ],
        "edges": [
            _edge("In", "message", "ChatInput", "Agent", "input_value", agent_types),
            _edge("Agent", "response", "ScriptedAgent", "Out", "input_value", output_types),
        ],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }
    parent_id, child_id = await _store(
        created_api_key.user_id, child_data, lambda child: _parent_data(templates, child, "Out")
    )
    yield str(parent_id), str(child_id)
    await _delete(parent_id, child_id)


async def _wait_for_status(job_id: str, statuses: set[JobStatus]) -> JobStatus | None:
    for _ in range(150):
        async with session_scope() as session:
            row = await session.get(Job, UUID(job_id))
        if row is not None and row.status in statuses:
            return row.status
        await asyncio.sleep(0.1)
    return None


async def _messages(child_id: str, senders) -> list[tuple[str, str]]:
    async with session_scope() as session:
        rows = (await session.exec(select(MessageTable).where(MessageTable.flow_id == UUID(child_id)))).all()
    return sorted((row.sender_name, row.text) for row in rows if row.sender_name in senders)


async def _checkpoint_rows(job_id) -> list[tuple[UUID, str]]:
    async with session_scope() as session:
        rows = (await session.exec(select(JobCheckpoint).where(JobCheckpoint.job_id == UUID(str(job_id))))).all()
    return sorted((row.job_id, row.kind) for row in rows)


async def _child_run_id(job_id: str) -> str:
    blob = await get_job_service().load_checkpoint(UUID(job_id), "graph")
    return GraphCheckpoint.model_validate_json(blob).child_checkpoints[nested_request_prefix("Runner", job_id)].run_id


async def _submit_and_suspend(client, headers, flow_id: str) -> tuple[str, dict]:
    submit = await client.post("api/v2/workflows", json={"flow_id": flow_id, "mode": "background"}, headers=headers)
    assert submit.status_code == 200, submit.text
    job_id = submit.json()["job_id"]
    assert await _wait_for_status(job_id, {JobStatus.SUSPENDED, JobStatus.FAILED}) == JobStatus.SUSPENDED
    return job_id, await get_job_service().get_pending_human_request(UUID(job_id))


async def _resume(client, headers, job_id: str, request_id: str, action: str) -> None:
    resume = await client.post(
        f"api/v2/workflows/{job_id}/resume",
        json={"request_id": request_id, "decision": {"action_id": action}},
        headers=headers,
    )
    assert resume.status_code == 200, resume.text
    assert await _wait_for_status(job_id, {JobStatus.COMPLETED, JobStatus.FAILED}) == JobStatus.COMPLETED


async def test_run_flow_child_human_input_pauses_and_resumes(client, created_api_key, flows):
    parent_id, child_id, action = flows
    headers = {"x-api-key": created_api_key.api_key}

    job_id, pending = await _submit_and_suspend(client, headers, parent_id)
    assert await _messages(child_id, _BRANCH_SENDERS.values()) == [], "no branch may run before the decision"
    assert pending["request_id"].startswith(nested_request_prefix("Runner", job_id) + "Ask:")

    await _resume(client, headers, job_id, pending["request_id"], action)
    assert [sender for sender, _ in await _messages(child_id, _BRANCH_SENDERS.values())] == [_BRANCH_SENDERS[action]]


@pytest.mark.parametrize("removal", ["retention", "erasure"])
async def test_a_child_agent_approval_state_belongs_to_the_parent_job(client, created_api_key, agent_flows, removal):
    parent_id, child_id = agent_flows
    headers = {"x-api-key": created_api_key.api_key}

    job_id, pending = await _submit_and_suspend(client, headers, parent_id)
    assert pending["kind"] == "tool_approval"
    child_run_id = await _child_run_id(job_id)
    assert await _checkpoint_rows(job_id) == [
        (UUID(job_id), f"agent:{child_run_id}:Agent"),
        (UUID(job_id), "graph"),
    ]
    assert await _checkpoint_rows(child_run_id) == []

    await _resume(client, headers, job_id, pending["request_id"], "approve")
    # The resumed Agent found its saved approval under the parent job and ran the tool once.
    assert await _messages(child_id, {_AGENT_SENDER}) == [(_AGENT_SENDER, "done:effect")]

    if removal == "retention":
        stamp = datetime.now(timezone.utc) - timedelta(days=3650)
        async with session_scope() as session:
            await session.exec(
                update(Job)  # type: ignore[call-overload]
                .where(Job.job_id == UUID(job_id))
                .values(created_timestamp=stamp, finished_timestamp=stamp)
            )
        while await get_job_service().purge_terminal_jobs(older_than_days=3000, limit=100):
            pass
    else:
        async with session_scope() as session:
            while await _drain_flow_history(session, UUID(parent_id)):
                pass
    assert await _checkpoint_rows(job_id) == []
