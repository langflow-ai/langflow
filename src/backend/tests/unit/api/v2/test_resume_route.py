"""HTTP resume route (LE-1450): POST /api/v2/workflows/{job_id}/resume.

Route-level tests against a hand-written SUSPENDED job row (the full HTTP
round-trip gates on a real pausing flow): owner-or-superuser auth with
deny-to-404, single-use 409, and accepted-resume 200.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.jobs.model import Job, JobStatus, JobType
from lfx.services.deps import session_scope

pytestmark = pytest.mark.usefixtures("client")


def _headers(api_key) -> dict:
    return {"x-api-key": api_key.api_key}


@pytest.fixture
async def suspended_job(created_api_key):
    """A hand-written SUSPENDED workflow job owned by the api-key user, with a real flow."""
    user_id = created_api_key.user_id
    flow_id, job_id = uuid4(), uuid4()
    request = {"flow_id": str(flow_id), "mode": "background", "stream_protocol": "langflow", "input_value": "hi"}
    async with session_scope() as session:
        session.add(Flow(id=flow_id, name=f"f-{flow_id}", data={"nodes": [], "edges": []}, user_id=user_id))
        session.add(
            Job(
                job_id=job_id,
                flow_id=flow_id,
                user_id=user_id,
                type=JobType.WORKFLOW,
                status=JobStatus.SUSPENDED,
                job_metadata={"pending_request_id": "req-1", "request": request},
            )
        )
        await session.flush()
    yield job_id
    async with session_scope() as session:
        job = await session.get(Job, job_id)
        if job:
            await session.delete(job)
        flow = await session.get(Flow, flow_id)
        if flow:
            await session.delete(flow)


async def test_resume_owner_accepts_200(client, created_api_key, suspended_job):
    body = {"request_id": "req-1", "decision": {"action_id": "approve"}}
    resp = await client.post(f"api/v2/workflows/{suspended_job}/resume", json=body, headers=_headers(created_api_key))
    assert resp.status_code == 200
    assert resp.json()["status"] == "resuming"


async def test_resume_stale_request_id_409(client, created_api_key, suspended_job):
    body = {"request_id": "WRONG", "decision": {"action_id": "approve"}}
    resp = await client.post(f"api/v2/workflows/{suspended_job}/resume", json=body, headers=_headers(created_api_key))
    assert resp.status_code == 409


async def test_resume_unknown_job_404(client, created_api_key):
    body = {"request_id": "req-1", "decision": {}}
    resp = await client.post(f"api/v2/workflows/{uuid4()}/resume", json=body, headers=_headers(created_api_key))
    assert resp.status_code == 404


async def test_resume_non_suspended_job_409(client, created_api_key):
    """A QUEUED (not suspended) job is not resumable → 409."""
    user_id = created_api_key.user_id
    flow_id, job_id = uuid4(), uuid4()
    async with session_scope() as session:
        session.add(Flow(id=flow_id, name=f"f-{flow_id}", data={"nodes": [], "edges": []}, user_id=user_id))
        session.add(Job(job_id=job_id, flow_id=flow_id, user_id=user_id, type=JobType.WORKFLOW, status=JobStatus.QUEUED))
        await session.flush()
    try:
        body = {"request_id": "req-1", "decision": {}}
        resp = await client.post(f"api/v2/workflows/{job_id}/resume", json=body, headers=_headers(created_api_key))
        assert resp.status_code == 409
    finally:
        async with session_scope() as session:
            for model, key in ((Job, job_id), (Flow, flow_id)):
                row = await session.get(model, key)
                if row:
                    await session.delete(row)


async def test_resume_invalid_job_id_404(client, created_api_key):
    body = {"request_id": "req-1", "decision": {}}
    resp = await client.post("api/v2/workflows/not-a-uuid/resume", json=body, headers=_headers(created_api_key))
    assert resp.status_code == 404
