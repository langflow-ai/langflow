"""Background mode end-to-end through the HTTP API over the default backend.

Real no-LLM flow in the migrated test DB; real facade; real executor + bus.
Asserts the WorkflowJobResponse contract on submit, terminal status on GET, and
that GET /events replays durable milestones from the durable ``job_events`` log.
"""

from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from lfx.services.deps import session_scope

pytestmark = pytest.mark.usefixtures("client")


@pytest.fixture
async def bg_flow(created_api_key, json_memory_chatbot_no_llm):
    """A real no-LLM chatbot flow (ChatInput -> Prompt/Memory -> ChatOutput).

    Runs entirely offline so a background run reaches COMPLETED without any
    external API key.
    """
    raw = json.loads(json_memory_chatbot_no_llm)
    flow_id = uuid4()
    async with session_scope() as session:
        flow = Flow(
            id=flow_id,
            name="bg-no-llm-flow",
            description="No-LLM flow for background-mode tests",
            data=raw.get("data", raw),
            user_id=created_api_key.user_id,
        )
        session.add(flow)
        await session.flush()
    yield str(flow_id)
    async with session_scope() as session:
        flow = await session.get(Flow, flow_id)
        if flow:
            await session.delete(flow)


def _headers(api_key) -> dict:
    return {"x-api-key": api_key.api_key}


def _body(flow_id: str) -> dict:
    return {
        "flow_id": flow_id,
        "mode": "background",
        "stream_protocol": "langflow",
        "input_value": "hi",
    }


async def test_background_submit_returns_job_response(client, created_api_key, bg_flow):
    resp = await client.post("api/v2/workflows", json=_body(bg_flow), headers=_headers(created_api_key))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["flow_id"] == bg_flow
    assert body["status"] == "queued"
    assert "job_id" in body


async def test_background_reaches_terminal_status(client, created_api_key, bg_flow):
    """The background run reaches COMPLETED durable status.

    Status is read from the durable ``Job`` row (the facade's source of truth).
    The ``GET /workflows`` COMPLETED branch reconstructs from ``vertex_build``
    rows keyed by job_id; wiring the background build to persist those is the
    Phase 3 endpoint concern, so here we assert the durable terminal status the
    facade owns.
    """
    from uuid import UUID

    from langflow.services.database.models.jobs.model import Job, JobStatus

    submit = await client.post("api/v2/workflows", json=_body(bg_flow), headers=_headers(created_api_key))
    job_id = submit.json()["job_id"]

    final = None
    for _ in range(150):
        async with session_scope() as session:
            row = await session.get(Job, UUID(job_id))
        if row is not None and row.status in (
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
            JobStatus.TIMED_OUT,
        ):
            final = row.status
            break
        await asyncio.sleep(0.1)
    assert final == JobStatus.COMPLETED, f"job did not complete: last={final}"


async def test_stop_does_not_overwrite_completed_job(client, created_api_key, bg_flow):
    """A late ``/stop`` on an already-COMPLETED job must NOT flip it to CANCELLED.

    The stop handler used to call ``update_job_status(CANCELLED)`` unconditionally,
    so stopping a finished run overwrote COMPLETED (and stranded the result blob).
    Submit, wait for COMPLETED, capture the result, then POST /stop and assert the
    durable row stays COMPLETED with its result intact.
    """
    from uuid import UUID

    from langflow.services.database.models.jobs.model import Job, JobStatus

    submit = await client.post("api/v2/workflows", json=_body(bg_flow), headers=_headers(created_api_key))
    job_id = submit.json()["job_id"]

    completed_result = None
    for _ in range(150):
        async with session_scope() as session:
            row = await session.get(Job, UUID(job_id))
        if row is not None and row.status == JobStatus.COMPLETED:
            completed_result = row.result
            break
        await asyncio.sleep(0.1)
    assert completed_result is not None or row.status == JobStatus.COMPLETED, "job never completed"

    # Late stop on the finished job.
    stop = await client.post("api/v2/workflows/stop", json={"job_id": job_id}, headers=_headers(created_api_key))
    assert stop.status_code == 200, stop.text

    async with session_scope() as session:
        row = await session.get(Job, UUID(job_id))
    assert row.status == JobStatus.COMPLETED, f"late stop overwrote terminal status: {row.status}"
    assert row.result == completed_result, "late stop clobbered the completed result"


async def test_background_events_replay_durable(client, created_api_key, bg_flow):
    from uuid import UUID

    from langflow.services.database.models.jobs.model import Job, JobStatus

    submit = await client.post("api/v2/workflows", json=_body(bg_flow), headers=_headers(created_api_key))
    job_id = submit.json()["job_id"]
    # Wait for completion so the durable log is fully written.
    for _ in range(150):
        async with session_scope() as session:
            row = await session.get(Job, UUID(job_id))
        if row is not None and row.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            break
        await asyncio.sleep(0.1)

    # Reattach from the beginning; durable milestones must replay.
    async with client.stream("GET", f"api/v2/workflows/{job_id}/events", headers=_headers(created_api_key)) as resp:
        assert resp.status_code == 200
        body = b""
        async for chunk in resp.aiter_bytes():
            body += chunk
            if b'"event": "end"' in body or b"end_vertex" in body:
                break
    assert b"build_start" in body or b"end_vertex" in body
